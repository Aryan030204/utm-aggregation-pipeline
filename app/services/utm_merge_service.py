from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Tuple

_ORDER_COUNT_COLUMNS = (
    "orders",
    "prepaid_orders",
    "cod_orders",
    "ppcod_orders",
    "cancelled_orders",
    "refunded_orders",
)


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


class UtmMergeService:
    """Builds the rows for one aggregate table from two independently-sourced inputs --
    orders/sales/returns from MySQL (queried once per date at the finest grain and
    rolled up per table by rollup_orders) and sessions/atc_sessions from Shopify
    GraphQL (collapsed here to whatever subset of dims the table needs) -- and
    computes the derived rate columns."""

    @staticmethod
    def rollup_orders(finest_rows: List[Dict[str, Any]], dims: List[str]) -> List[Dict[str, Any]]:
        """Projects finest-grain order rows (date, hour, source, medium, campaign) onto a
        table's dimensions, summing the additive columns."""
        is_hourly = "metric_hour" in dims
        utm_dims = [d for d in dims if d not in ("metric_date", "metric_hour")]

        grouped: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        for row in finest_rows:
            key = tuple(row[d] for d in utm_dims)
            if is_hourly:
                key = (row["metric_hour"],) + key

            agg = grouped.get(key)
            if agg is None:
                agg = grouped[key] = {column: 0 for column in _ORDER_COUNT_COLUMNS}
                agg["sales"] = Decimal("0")

            for column in _ORDER_COUNT_COLUMNS:
                agg[column] += int(row.get(column, 0) or 0)
            agg["sales"] += _to_decimal(row.get("sales"))

        rolled: List[Dict[str, Any]] = []
        for key, agg in grouped.items():
            out: Dict[str, Any] = {}
            if is_hourly:
                out["metric_hour"] = key[0]
                dim_values = key[1:]
            else:
                dim_values = key
            for dim_name, dim_value in zip(utm_dims, dim_values):
                out[dim_name] = dim_value
            out.update(agg)
            rolled.append(out)
        return rolled

    @staticmethod
    def merge(
        dims: List[str],
        metric_date: str,
        order_rows: List[Dict[str, Any]],
        session_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        is_hourly = "metric_hour" in dims
        utm_dims = [d for d in dims if d not in ("metric_date", "metric_hour")]

        buckets: Dict[Tuple[Any, ...], Dict[str, Any]] = {}

        def bucket(key: Tuple[Any, ...]) -> Dict[str, Any]:
            return buckets.setdefault(key, {
                "orders": 0,
                "sales": Decimal("0"),
                "prepaid_orders": 0,
                "cod_orders": 0,
                "ppcod_orders": 0,
                "cancelled_orders": 0,
                "refunded_orders": 0,
                "sessions": 0,
                "atc_sessions": 0,
            })

        for row in order_rows:
            key = UtmMergeService._key(row, utm_dims, is_hourly, hour_field="metric_hour")
            m = bucket(key)
            m["orders"] += int(row.get("orders", 0) or 0)
            m["sales"] += _to_decimal(row.get("sales"))
            m["prepaid_orders"] += int(row.get("prepaid_orders", 0) or 0)
            m["cod_orders"] += int(row.get("cod_orders", 0) or 0)
            m["ppcod_orders"] += int(row.get("ppcod_orders", 0) or 0)
            m["cancelled_orders"] += int(row.get("cancelled_orders", 0) or 0)
            m["refunded_orders"] += int(row.get("refunded_orders", 0) or 0)

        for row in session_rows:
            key = UtmMergeService._collapse_key(row, utm_dims, is_hourly)
            m = bucket(key)
            m["sessions"] += int(row.get("sessions", 0) or 0)
            m["atc_sessions"] += int(row.get("atc_sessions", 0) or 0)

        results: List[Dict[str, Any]] = []
        for key, m in buckets.items():
            row: Dict[str, Any] = {"metric_date": metric_date}
            if is_hourly:
                row["metric_hour"] = key[0]
                dim_values = key[1:]
            else:
                dim_values = key
            for dim_name, dim_value in zip(utm_dims, dim_values):
                row[dim_name] = dim_value

            orders = m["orders"]
            sessions = m["sessions"]
            row["orders"] = orders
            row["sales"] = m["sales"]
            row["average_order_value"] = (
                (m["sales"] / orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if orders > 0
                else Decimal("0.00")
            )
            row["sessions"] = sessions
            row["atc_sessions"] = m["atc_sessions"]
            row["conversion_rate"] = (orders / sessions) if sessions > 0 else 0.0
            row["cancellation_rate"] = (m["cancelled_orders"] / orders) if orders > 0 else 0.0
            row["refund_rate"] = (m["refunded_orders"] / orders) if orders > 0 else 0.0
            row["prepaid_orders"] = m["prepaid_orders"]
            row["cod_orders"] = m["cod_orders"]
            row["ppcod_orders"] = m["ppcod_orders"]
            row["cancelled_orders"] = m["cancelled_orders"]
            row["refunded_orders"] = m["refunded_orders"]
            results.append(row)

        return results

    @staticmethod
    def _key(row: Dict[str, Any], utm_dims: List[str], is_hourly: bool, hour_field: str) -> Tuple[Any, ...]:
        """Key for rows already aggregated at exactly the table's UTM dims (order_rows)."""
        key = tuple(row.get(d, "Unknown") for d in utm_dims)
        if is_hourly:
            key = (row.get(hour_field, 0),) + key
        return key

    @staticmethod
    def _collapse_key(row: Dict[str, Any], utm_dims: List[str], is_hourly: bool) -> Tuple[Any, ...]:
        """Key for session rows, which always carry the full utm_source/medium/campaign
        combo -- collapsed down to whichever subset this table's dims actually use."""
        key = tuple(row.get(d, "Unknown") for d in utm_dims)
        if is_hourly:
            key = (row.get("hour", 0),) + key
        return key
