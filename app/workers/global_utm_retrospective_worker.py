from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from typing import List, Dict, Any

from app.utils.config import Config
from app.utils.logger import get_logger
from app.services.brand_fetcher import BrandFetcher
from app.services.aggregate_runner import AggregateRunner

logger = get_logger(__name__)


def generate_retrospective_target_dates(run_date: date, lookback_days: int) -> List[str]:
    """
    Generates target date strings for the lookback window.
    For lookback_days=2 and run_date=T, returns [T-2, T-1] (day before yesterday, yesterday).
    """
    days = max(1, lookback_days)
    target_dates = []
    for i in range(days, 0, -1):
        target_date = run_date - timedelta(days=i)
        target_dates.append(target_date.isoformat())
    return target_dates


class GlobalUtmRetrospectiveWorker:
    def __init__(self, run_date: date, lookback_days: int, max_retries: int | None = None):
        self.run_date = run_date
        self.lookback_days = lookback_days
        self.max_retries = max_retries or Config.MAX_BRAND_RETRIES

    def run(self) -> bool:
        start_time = time.perf_counter()
        target_dates = generate_retrospective_target_dates(self.run_date, self.lookback_days)
        logger.info(
            f"Starting Global UTM Retrospective Worker | Run Date: {self.run_date.isoformat()} | "
            f"Lookback Days: {self.lookback_days} | Target Dates: {target_dates} | Max Retries: {self.max_retries}"
        )

        brands = BrandFetcher.get_all_brands()
        if not brands:
            logger.warning("No active brands fetched. Exiting retrospective worker cycle.")
            return True

        total_brands = len(brands)
        succeeded_brands: List[str] = []
        failed_brands: List[Dict[str, Any]] = []

        for index, brand in enumerate(brands, start=1):
            brand_name = brand.get("brand_name", f"brand_{index}")
            logger.info(f"[{index}/{total_brands}] Processing retrospective aggregations for brand: {brand_name}")

            brand_start_time = time.perf_counter()
            brand_success = False
            last_exception: Exception | None = None

            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info(f"[{brand_name}] Attempt {attempt}/{self.max_retries} starting...")
                    runner = AggregateRunner(brand, target_dates)
                    runner.initialize()
                    runner.run_aggregations()
                    brand_success = True
                    elapsed = round(time.perf_counter() - brand_start_time, 2)
                    logger.info(f"[{brand_name}] Successfully completed aggregations in {elapsed}s.")
                    succeeded_brands.append(brand_name)
                    break
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"[{brand_name}] Attempt {attempt}/{self.max_retries} failed with error: {e}"
                    )
                    if attempt < self.max_retries:
                        sleep_sec = 2 ** attempt
                        logger.info(f"[{brand_name}] Retrying in {sleep_sec}s...")
                        time.sleep(sleep_sec)

            if not brand_success:
                elapsed = round(time.perf_counter() - brand_start_time, 2)
                logger.error(
                    f"[{brand_name}] Exhausted all {self.max_retries} retries after {elapsed}s. "
                    f"Final error: {last_exception}"
                )
                failed_brands.append({
                    "brand_name": brand_name,
                    "error": str(last_exception)
                })

        total_elapsed = round(time.perf_counter() - start_time, 2)
        logger.info("=" * 60)
        logger.info(f"Global UTM Retrospective Worker Execution Summary:")
        logger.info(f"  Total Brands Discovered : {total_brands}")
        logger.info(f"  Total Succeeded        : {len(succeeded_brands)}")
        logger.info(f"  Total Failed           : {len(failed_brands)}")
        logger.info(f"  Total Execution Time   : {total_elapsed}s")
        logger.info("=" * 60)

        if failed_brands:
            failed_names = [f["brand_name"] for f in failed_brands]
            logger.error(f"Retrospective worker completed with failures in brands: {', '.join(failed_names)}")
            return False

        logger.info("Global UTM Retrospective Worker completed successfully for all brands.")
        return True


def parse_args():
    parser = argparse.ArgumentParser(description="Global UTM Retrospective Worker")
    parser.add_argument(
        "--run-date",
        dest="run_date",
        default=None,
        help="Effective run date in YYYY-MM-DD format (defaults to current UTC date)"
    )
    parser.add_argument(
        "--lookback-days",
        dest="lookback_days",
        type=int,
        default=None,
        help="Number of historical days to re-aggregate (defaults to Config.GLOBAL_RETROSPECTIVE_LOOKBACK_DAYS)"
    )
    parser.add_argument(
        "--max-retries",
        dest="max_retries",
        type=int,
        default=None,
        help="Max retries per brand (defaults to Config.MAX_BRAND_RETRIES)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    run_date = datetime.utcnow().date()
    if args.run_date:
        try:
            run_date = date.fromisoformat(args.run_date)
        except ValueError:
            logger.error(f"Invalid --run-date format: {args.run_date}. Expected YYYY-MM-DD.")
            sys.exit(1)

    lookback_days = args.lookback_days if args.lookback_days is not None else Config.GLOBAL_RETROSPECTIVE_LOOKBACK_DAYS
    max_retries = args.max_retries if args.max_retries is not None else Config.MAX_BRAND_RETRIES

    worker = GlobalUtmRetrospectiveWorker(
        run_date=run_date,
        lookback_days=lookback_days,
        max_retries=max_retries
    )

    success = worker.run()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
