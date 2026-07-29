from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


class MergeService:
    DAILY_KEYS = ("date", "product_id", "utm_source")
    HOURLY_KEYS = ("date", "hour", "product_id", "utm_source")

    @classmethod
    def merge_daily(cls, session_rows: list[dict], order_rows: list[dict]) -> list[dict]:
        return cls._merge_rows(cls.DAILY_KEYS, session_rows, order_rows)

    @classmethod
    def merge_hourly(cls, session_rows: list[dict], order_rows: list[dict]) -> list[dict]:
        return cls._merge_rows(cls.HOURLY_KEYS, session_rows, order_rows)

    @classmethod
    def _merge_rows(cls, key_fields: tuple[str, ...], session_rows: list[dict], order_rows: list[dict]) -> list[dict]:
        merged: dict[tuple, dict] = {}

        for row in session_rows:
            key = tuple(row[field] for field in key_fields)
            merged[key] = {
                **{field: row[field] for field in key_fields},
                "sessions": int(row.get("sessions", 0) or 0),
                "atc_sessions": int(row.get("atc_sessions", 0) or 0),
                "orders": 0,
                "sales": Decimal("0.00"),
                "average_order_value": Decimal("0.00"),
                "cod_orders": 0,
                "prepaid_orders": 0,
                "partially_prepaid_orders": 0,
                "cancelled_orders": 0,
                "refunded_orders": 0,
            }

        for row in order_rows:
            key = tuple(row[field] for field in key_fields)
            target = merged.setdefault(
                key,
                {
                    **{field: row[field] for field in key_fields},
                    "sessions": 0,
                    "atc_sessions": 0,
                    "orders": 0,
                    "sales": Decimal("0.00"),
                    "average_order_value": Decimal("0.00"),
                    "cod_orders": 0,
                    "prepaid_orders": 0,
                    "partially_prepaid_orders": 0,
                    "cancelled_orders": 0,
                    "refunded_orders": 0,
                },
            )
            target["orders"] = int(row.get("orders", 0) or 0)
            target["sales"] = Decimal(str(row.get("sales", 0) or 0))
            target["cod_orders"] = int(row.get("cod_orders", 0) or 0)
            target["prepaid_orders"] = int(row.get("prepaid_orders", 0) or 0)
            target["partially_prepaid_orders"] = int(row.get("partially_prepaid_orders", 0) or 0)
            target["cancelled_orders"] = int(row.get("cancelled_orders", 0) or 0)
            target["refunded_orders"] = int(row.get("refunded_orders", 0) or 0)

        for row in merged.values():
            orders = row["orders"]
            sales = row["sales"]
            row["average_order_value"] = (
                (sales / orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if orders
                else Decimal("0.00")
            )
            row["sales"] = sales.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return sorted(merged.values(), key=lambda row: tuple(row[field] for field in key_fields))
