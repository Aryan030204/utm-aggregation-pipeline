import uvicorn
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from app.utils.logger import get_logger, get_recent_logs
from app.utils.config import Config
from app.models.events import EtlTriggerEvent, ManualTriggerRequest
from app.services.brand_fetcher import BrandFetcher
from app.services.aggregate_runner import AggregateRunner, RunLockNotAcquired
from app.utils.dates import generate_target_dates, select_dates_to_rebuild, mark_dates_rebuilt
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import os
import sys
import threading
import requests
import re

logger = get_logger(__name__)

app = FastAPI(title="UTM Aggregate Pipeline Trigger API")

class PipelineInitializationError(Exception):
    pass


def _exception_to_error_code(exc: Exception) -> str:
    name = exc.__class__.__name__ or "UnknownError"
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


# Single-flight state: a run takes longer than the 10-minute trigger cadence, so
# concurrent runs would pile up and rewrite the same tables against the shared RDS.
_state = threading.Condition()
_running = False
_pending = False


def run_pipeline_task(event: EtlTriggerEvent, is_manual: bool = False, run_id: str | None = None):
    """
    Runs the pipeline for all brands, never more than one run at a time. Webhook and
    scheduled triggers that arrive during a run are coalesced into a single follow-up
    run (with a fresh completedAt); manual runs wait their turn so their status
    callbacks stay accurate.
    """
    global _running, _pending
    with _state:
        if _running:
            if not is_manual:
                _pending = True
                logger.info(f"A pipeline run is already in progress; coalescing trigger {event.jobId} into one follow-up run.")
                return
            while _running:
                _state.wait()
        _running = True
        _pending = False

    released = False
    try:
        current_event, manual, current_run_id = event, is_manual, run_id
        while True:
            _execute_pipeline_run(current_event, manual, current_run_id)
            with _state:
                if not _pending:
                    _running = False
                    released = True
                    _state.notify_all()
                    break
                _pending = False
            logger.info("Triggers arrived during the run; running once more.")
            now = datetime.now()
            current_event = EtlTriggerEvent(
                eventType="ETL_COMPLETED",
                jobId=f"coalesced_{now.strftime('%Y%m%d_%H%M%S')}",
                completedAt=now.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            manual, current_run_id = False, None
    finally:
        if not released:
            with _state:
                _running = False
                _state.notify_all()


def _execute_pipeline_run(event: EtlTriggerEvent, is_manual: bool = False, run_id: str | None = None):
    run_failed = False
    failure_exception = None
    try:
        if is_manual:
            try:
                requests.post(
                    Config.MANAGER_STARTED_ENDPOINT,
                    json={
                        "runId": run_id,
                        "pipelineId": Config.PIPELINE_ID,
                        "status": "running"
                    },
                    headers={"x-pipeline-key": Config.PIPELINE_AUTH_HEADER},
                    timeout=10
                )
                logger.info(f"Sent started status to manager for runId: {run_id}")
            except Exception as e:
                logger.error(f"Failed to send started status to manager: {e}")

        logger.info(f"Background process started for jobId: {event.jobId}")
        
        # Setup dates
        target_dates = generate_target_dates(event.completedAt, event.recomputeDays or 2)
        if not target_dates:
            raise PipelineInitializationError("No target dates generated")
        dates_to_rebuild = select_dates_to_rebuild(target_dates)

        # Fetch all valid brands
        brands = BrandFetcher.get_all_brands()
        if not brands:
            raise PipelineInitializationError("No brands fetched")

        # Execute pipeline for every brand
        skipped_brands = 0
        for b in brands:
            try:
                brand_name = b.get("brand_name", "unknown")
                logger.info(f"Running aggregates for brand: {brand_name}")

                runner = AggregateRunner(b, dates_to_rebuild)
                runner.initialize()
                runner.run_aggregations()

            except RunLockNotAcquired as lock_e:
                skipped_brands += 1
                logger.warning(f"Skipping brand {b.get('brand_name')}: {lock_e}")
            except Exception as run_e:
                run_failed = True
                if failure_exception is None:
                    failure_exception = run_e
                BrandFetcher.invalidate_cache()
                logger.error(f"Failed processing brand {b.get('brand_name')}: {run_e}")

        if not run_failed and not skipped_brands:
            mark_dates_rebuilt(dates_to_rebuild[:-1])

        logger.info(f"Pipeline execution completed for jobId: {event.jobId}")
    except Exception as e:
        run_failed = True
        failure_exception = e
        logger.error(f"Fatal error in background pipeline execution: {e}")
    finally:
        if is_manual and run_id:
            try:
                if run_failed:
                    error_code = "UNKNOWN_ERROR"
                    if failure_exception is not None:
                        error_code = _exception_to_error_code(failure_exception)
                    error_body = "\n".join(get_recent_logs(2))
                    requests.post(
                        Config.MANAGER_FAILED_ENDPOINT,
                        json={
                            "runId": run_id,
                            "pipelineId": Config.PIPELINE_ID,
                            "errorCode": error_code,
                            "errorBody": error_body
                        },
                        headers={"x-pipeline-key": Config.PIPELINE_AUTH_HEADER},
                        timeout=10
                    )
                    logger.info(f"Sent failed status to manager for runId: {run_id}")
                else:
                    requests.post(
                        Config.MANAGER_COMPLETED_ENDPOINT,
                        json={
                            "runId": run_id,
                            "pipelineId": Config.PIPELINE_ID,
                            "status": "completed"
                        },
                        headers={"x-pipeline-key": Config.PIPELINE_AUTH_HEADER},
                        timeout=10
                    )
                    logger.info(f"Sent completed status to manager for runId: {run_id}")
            except Exception as e:
                logger.error(f"Failed to send status to manager: {e}")

@app.post("/utm-pipeline/trigger")
async def trigger_pipeline(
    event: EtlTriggerEvent,
    background_tasks: BackgroundTasks,
    x_pipeline_key: str = Header(None)
):
    # Verify Authentication Header
    if x_pipeline_key != Config.PIPELINE_AUTH_HEADER:
        logger.warning(f"Unauthorized trigger attempt with key: {x_pipeline_key}")
        raise HTTPException(status_code=403, detail="Invalid pipeline key")

    # Triggering the pipeline logic for "ETL_COMPLETED" type
    # (Checking eventType as per original Kafka logic)
    if event.eventType != "ETL_COMPLETED":
        logger.info(f"Received event with untracked eventType: {event.eventType}. No action taken.")
        return {"status": "ignored", "message": "Only ETL_COMPLETED events are processed."}

    logger.info(f"Authorized trigger received for jobId: {event.jobId}. Dispatching background task.")
    
    # Add to background tasks to keep HTTP response snappy
    background_tasks.add_task(run_pipeline_task, event)

    return {
        "status": "success",
        "message": "Pipeline triggered successfully in background.",
        "jobId": event.jobId
    }

@app.post("/utm-pipeline/manual-trigger")
async def manual_trigger(
    request: ManualTriggerRequest,
    background_tasks: BackgroundTasks,
    x_pipeline_key: str = Header(None)
):
    # Verify Authentication Header
    if x_pipeline_key != Config.PIPELINE_AUTH_HEADER:
        logger.warning(f"Unauthorized manual trigger attempt with key: {x_pipeline_key}")
        raise HTTPException(status_code=403, detail="Invalid pipeline key")

    logger.info("Authorized manual trigger received. Dispatching background task.")
    
    # Create a manual trigger event
    event = EtlTriggerEvent(
        eventType="ETL_COMPLETED",
        jobId=f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        completedAt=datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    )
    
    background_tasks.add_task(run_pipeline_task, event, is_manual=True, run_id=request.runId)

    return {
        "status": "success",
        "message": "Manual pipeline trigger successful.",
        "jobId": event.jobId,
        "runId": request.runId
    }

@app.get("/")
async def root():
    return {"status": "running", "service": "UTM Aggregation Pipeline"}

def main():
    logger.info("Initializing UTM Aggregate Pipeline (Webhook Mode)...")
    
    # Check for FREE_RUN mode first
    if Config.FREE_RUN:
        logger.info("FREE_RUN is enabled. Bypassing Webhook and running autonomously...")
        from app.utils.dates import generate_free_run_dates
        
        target_dates = generate_free_run_dates()
        if not target_dates:
            logger.error("No valid dates generated for FREE_RUN. Exiting.")
            sys.exit(1)
            
        brands = BrandFetcher.get_all_brands()
        if not brands:
            logger.error("No valid brands fetched for FREE_RUN. Exiting.")
            sys.exit(1)
            
        for b in brands:
            brand_name = b.get("brand_name", "unknown")
            logger.info(f"FREE_RUN executing for brand: {brand_name}")
            try:
                runner = AggregateRunner(b, target_dates)
                runner.initialize()
                runner.run_aggregations()
            except Exception as run_e:
                logger.error(f"Failed processing brand {brand_name} during FREE_RUN: {run_e}")
        
        logger.info("FREE_RUN completed for all brands. Exiting autonomously.")
        sys.exit(0)
    
    # Normal server mode
    if Config.SELF_RUN:
        logger.info(f"SELF_RUN is enabled. Starting scheduler with pattern: {Config.PIPELINE_SCHEDULE}")
        scheduler = BackgroundScheduler()

        def scheduled_job():
            logger.info("Executing scheduled pipeline run...")
            event = EtlTriggerEvent(
                eventType="ETL_COMPLETED",
                jobId=f"scheduled_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                completedAt=datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            )
            run_pipeline_task(event)

        scheduler.add_job(
            scheduled_job,
            CronTrigger.from_crontab(Config.PIPELINE_SCHEDULE),
            id="utm_pipeline_job"
        )
        scheduler.start()

        # One catch-up run shortly after startup so a container reboot/rebuild doesn't have to wait for
        # the next trigger. It is delayed (STARTUP_DELAY_SECONDS, set per container in docker-compose)
        # so a host restart doesn't start every pipeline at once, and it can be switched off with
        # UTM_RUN_ON_STARTUP=false because every completed ETL run also triggers this pipeline.
        if os.getenv("UTM_RUN_ON_STARTUP", "true").strip().lower() == "true":
            from app.utils.self_scheduler import startup_delay_seconds

            delay = startup_delay_seconds()
            logger.info(f"Running pipeline once on startup in {delay}s...")
            scheduler.add_job(
                scheduled_job,
                "date",
                run_date=datetime.now() + timedelta(seconds=delay),
                id="utm_pipeline_startup_job",
            )
        else:
            logger.info("UTM_RUN_ON_STARTUP=false: no startup run.")
    else:
        logger.info("SELF_RUN is disabled. Pipeline will only run via manual triggers.")

    uvicorn.run(app, host=Config.HOST, port=Config.PORT)

if __name__ == "__main__":
    main()
