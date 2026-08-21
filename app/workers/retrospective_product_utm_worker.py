from __future__ import annotations

import argparse

from app.product_utm.config import ProductUTMConfig
from app.product_utm.services.worker_service import ProductUTMWorkerService, parse_effective_date
from app.utils.self_scheduler import run_forever


def run_once(end_date: str | None = None, retrospective_days: int | None = None) -> None:
    worker = ProductUTMWorkerService(
        run_type="retrospective",
        effective_end_date=parse_effective_date(end_date),
        retrospective_days=retrospective_days or ProductUTMConfig.RETROSPECTIVE_DAYS,
    )
    worker.run()


def main():
    parser = argparse.ArgumentParser(description="Retrospective Product x UTM worker")
    parser.add_argument("--end-date", dest="end_date", default=None)
    parser.add_argument("--retrospective-days", dest="retrospective_days", type=int, default=None)
    parser.add_argument("--top-product-lookback-days", dest="top_product_lookback_days", type=int, default=None)
    parser.add_argument("--top-product-limit", dest="top_product_limit", type=int, default=None)
    args = parser.parse_args()

    if args.top_product_lookback_days is not None:
        ProductUTMConfig.TOP_PRODUCT_LOOKBACK_DAYS = args.top_product_lookback_days
    if args.top_product_limit is not None:
        ProductUTMConfig.TOP_PRODUCT_LIMIT = args.top_product_limit

    if args.end_date:
        # Explicit date passed (manual/CI use) -> run once and exit.
        run_once(args.end_date, args.retrospective_days)
    else:
        # Container startup with no overrides -> self-schedule forever.
        run_forever(
            lambda: run_once(None, args.retrospective_days),
            ProductUTMConfig.RETROSPECTIVE_WORKER_CRON,
            job_id="retrospective_product_utm_worker",
        )


if __name__ == "__main__":
    main()
