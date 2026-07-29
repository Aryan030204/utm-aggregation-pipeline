from __future__ import annotations

import argparse

from app.product_utm.config import ProductUTMConfig
from app.product_utm.services.worker_service import ProductUTMWorkerService, parse_effective_date


def main():
    parser = argparse.ArgumentParser(description="Retrospective Product x UTM worker")
    parser.add_argument("--end-date", dest="end_date", default=None)
    parser.add_argument("--retrospective-days", dest="retrospective_days", type=int, default=None)
    parser.add_argument("--top-product-lookback-days", dest="top_product_lookback_days", type=int, default=None)
    parser.add_argument("--top-product-limit", dest="top_product_limit", type=int, default=None)
    args = parser.parse_args()

    if args.retrospective_days is not None:
        ProductUTMConfig.RETROSPECTIVE_DAYS = args.retrospective_days
    if args.top_product_lookback_days is not None:
        ProductUTMConfig.TOP_PRODUCT_LOOKBACK_DAYS = args.top_product_lookback_days
    if args.top_product_limit is not None:
        ProductUTMConfig.TOP_PRODUCT_LIMIT = args.top_product_limit

    worker = ProductUTMWorkerService(
        run_type="retrospective",
        effective_end_date=parse_effective_date(args.end_date),
        retrospective_days=args.retrospective_days or ProductUTMConfig.RETROSPECTIVE_DAYS,
    )
    worker.run()


if __name__ == "__main__":
    main()
