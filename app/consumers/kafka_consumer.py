import json
import traceback
from datetime import datetime, timezone
from kafka import KafkaConsumer
from pydantic import ValidationError
from app.utils.config import Config
from app.utils.logger import get_logger
from app.utils.dates import generate_target_dates
from app.services.brand_fetcher import BrandFetcher
from app.models.kafka_event import EtlCompletedEvent, UtmAggregateCompletedEvent, UtmAggregateFailedEvent
from app.services.aggregate_runner import AggregateRunner
from app.producers.kafka_producer import ProducerService

logger = get_logger(__name__)

class ConsumerService:
    def __init__(self):
        self.topic = Config.KAFKA_TOPIC
        self.group_id = Config.KAFKA_CONSUMER_GROUP
        self.consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=[Config.KAFKA_BROKER],
            group_id=self.group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=False, # Manual offset commits only!
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        self.producer_service = ProducerService()

    def _get_current_utc(self):
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def run(self):
        logger.info(f"Started polling topic '{self.topic}' to Consumer Group '{self.group_id}'")
        for message in self.consumer:
            raw_data = message.value
            logger.debug(f"Received message: {raw_data}")
            
            if not isinstance(raw_data, dict) or raw_data.get('eventType') != 'ETL_COMPLETED':
                self.consumer.commit()
                continue
                
            try:
                event = EtlCompletedEvent(**raw_data)
                logger.info(f"Processing ETL completed event. jobId: {event.jobId}")
                
                # Setup dates
                target_dates = generate_target_dates(event.completedAt)
                
                # Fetch all valid brands
                brands = BrandFetcher.get_all_brands()
                if not brands:
                    logger.warning("No brands fetched. Ending cycle.")
                    self.consumer.commit()
                    continue
                    
                overall_failed = False
                failed_brands = []

                # Execute pipeline for every brand
                for b in brands:
                    try:
                        brand_name = b.get("brand_name", "unknown")
                        logger.info(f"Running aggregates for brand: {brand_name}")
                        
                        runner = AggregateRunner(b, target_dates)
                        runner.initialize()
                        runner.run_aggregations()
                        
                    except Exception as run_e:
                        logger.error(f"Failed processing brand {b.get('brand_name')}: {run_e}")
                        overall_failed = True
                        failed_brands.append(b.get('brand_name', 'unknown'))

                run_status = "FAILED" if overall_failed else "SUCCESS"
                
                # Once all brands processed, publish overarching status back to kafka
                if overall_failed:
                    failure_event = UtmAggregateFailedEvent(
                        eventType="UTM_AGGREGATES_FAILED",
                        brand="ALL_BRANDS",
                        jobId=event.jobId,
                        completedAt=self._get_current_utc(),
                        status=run_status,
                        error=f"Multiple brand failures: {', '.join(failed_brands)}"
                    )
                    self.producer_service.publish_failed(failure_event)
                else:
                    completion_event = UtmAggregateCompletedEvent(
                        eventType="UTM_AGGREGATES_COMPLETED",
                        brand="ALL_BRANDS",
                        jobId=event.jobId,
                        completedAt=self._get_current_utc(),
                        status=run_status
                    )
                    self.producer_service.publish_completed(completion_event)
                
            except ValidationError as ve:
                logger.error(f"Message validation error: {ve}")
            except Exception as e:
                logger.error(f"Fatal error processing message {raw_data.get('jobId', 'unknown')}: {e}")
                logger.error(traceback.format_exc())
            finally:
                self.consumer.commit()
                logger.info("Kafka auto offset committed manually.")

    def close(self):
        self.consumer.close()
        self.producer_service.close()
