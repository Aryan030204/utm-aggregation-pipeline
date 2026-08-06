from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def process_single_brand(brand_info: Dict[str, Any], target_dates: List[str], max_retries: int) -> tuple[str, bool, str | None]:
    brand_name = brand_info.get("brand_name", "unknown")
    brand_start_time = time.perf_counter()
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[{brand_name}] Attempt {attempt}/{max_retries} starting...")
            runner = AggregateRunner(brand_info, target_dates)
            runner.initialize()
            runner.run_aggregations()
            elapsed = round(time.perf_counter() - brand_start_time, 2)
            logger.info(f"[{brand_name}] Successfully completed aggregations in {elapsed}s.")
            return (brand_name, True, None)
        except Exception as e:
            last_exception = e
            logger.warning(
                f"[{brand_name}] Attempt {attempt}/{max_retries} failed with error: {e}"
            )
            if attempt < max_retries:
                sleep_sec = 2 ** attempt
                logger.info(f"[{brand_name}] Retrying in {sleep_sec}s...")
                time.sleep(sleep_sec)

    elapsed = round(time.perf_counter() - brand_start_time, 2)
    logger.error(
        f"[{brand_name}] Exhausted all {max_retries} retries after {elapsed}s. Final error: {last_exception}"
    )
    return (brand_name, False, str(last_exception))


class GlobalUtmRetrospectiveWorker:
    def __init__(
        self,
        run_date: date,
        lookback_days: int,
        max_retries: int | None = None,
        max_concurrent_brands: int | None = None
    ):
        self.run_date = run_date
        self.lookback_days = lookback_days
        self.max_retries = max_retries or Config.MAX_BRAND_RETRIES
        self.max_concurrent_brands = max_concurrent_brands or Config.MAX_CONCURRENT_BRANDS

    def run(self) -> bool:
        start_time = time.perf_counter()
        target_dates = generate_retrospective_target_dates(self.run_date, self.lookback_days)
        logger.info(
            f"Starting Global UTM Retrospective Worker | Run Date: {self.run_date.isoformat()} | "
            f"Lookback Days: {self.lookback_days} | Target Dates: {target_dates} | "
            f"Max Retries: {self.max_retries} | Max Concurrent Brands: {self.max_concurrent_brands}"
        )

        brands = BrandFetcher.get_all_brands()
        if not brands:
            logger.warning("No active brands fetched. Exiting retrospective worker cycle.")
            return True

        total_brands = len(brands)
        succeeded_brands: List[str] = []
        failed_brands: List[Dict[str, Any]] = []

        max_workers = min(self.max_concurrent_brands, max(1, total_brands))
        logger.info(f"Executing retrospective aggregations for {total_brands} brand(s) using {max_workers} worker thread(s)...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_single_brand, brand, target_dates, self.max_retries): brand.get("brand_name", "unknown")
                for brand in brands
            }
            for future in as_completed(futures):
                brand_name, success, error_msg = future.result()
                if success:
                    succeeded_brands.append(brand_name)
                else:
                    failed_brands.append({
                        "brand_name": brand_name,
                        "error": error_msg
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
    parser.add_argument(
        "--max-concurrent-brands",
        dest="max_concurrent_brands",
        type=int,
        default=None,
        help="Max concurrent brand worker threads (defaults to Config.MAX_CONCURRENT_BRANDS)"
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
    max_concurrent_brands = args.max_concurrent_brands if args.max_concurrent_brands is not None else Config.MAX_CONCURRENT_BRANDS

    worker = GlobalUtmRetrospectiveWorker(
        run_date=run_date,
        lookback_days=lookback_days,
        max_retries=max_retries,
        max_concurrent_brands=max_concurrent_brands
    )

    success = worker.run()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
