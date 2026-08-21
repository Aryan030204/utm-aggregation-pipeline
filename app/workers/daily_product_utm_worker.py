from __future__ import annotations

import argparse

from app.product_utm.config import ProductUTMConfig
from app.product_utm.services.worker_service import ProductUTMWorkerService, parse_effective_date
from app.utils.self_scheduler import run_forever


def run_once(run_date: str | None = None) -> None:
    worker = ProductUTMWorkerService(run_type="daily", effective_end_date=parse_effective_date(run_date))
    worker.run()


def main():
    parser = argparse.ArgumentParser(description="Daily Product x UTM worker")
    parser.add_argument("--run-date", dest="run_date", default=None)
    parser.add_argument("--top-product-lookback-days", dest="top_product_lookback_days", type=int, default=None)
    parser.add_argument("--top-product-limit", dest="top_product_limit", type=int, default=None)
    args = parser.parse_args()

    if args.top_product_lookback_days is not None:
        ProductUTMConfig.TOP_PRODUCT_LOOKBACK_DAYS = args.top_product_lookback_days
    if args.top_product_limit is not None:
        ProductUTMConfig.TOP_PRODUCT_LIMIT = args.top_product_limit

    if args.run_date:
        # Explicit date passed (manual/CI use) -> run once and exit.
        run_once(args.run_date)
    else:
        # Container startup with no overrides -> self-schedule forever.
        run_forever(run_once, ProductUTMConfig.DAILY_WORKER_CRON, job_id="daily_product_utm_worker")


if __name__ == "__main__":
    main()
