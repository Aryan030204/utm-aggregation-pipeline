from __future__ import annotations

from typing import Any, Dict, List, Tuple


class UtmMergeService:
    """Joins order-level Shopify rows (already payment-classified) against a
    returns_fact cancel/refund lookup keyed by order_id, then collapses everything
    down to the UTM-dimension buckets a given aggregate table needs, merging in the
    matching session rows and computing the derived rate columns."""

    @staticmethod
    def merge(
        dims: List[str],
        metric_date: str,
        order_rows: List[Dict[str, Any]],
        returns_lookup: Dict[str, Dict[str, int]],
        session_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        is_hourly = "metric_hour" in dims
        utm_dims = [d for d in dims if d not in ("metric_date", "metric_hour")]

        buckets: Dict[Tuple[Any, ...], Dict[str, Any]] = {}

        def bucket(key: Tuple[Any, ...]) -> Dict[str, Any]:
            return buckets.setdefault(key, {
                "orders": 0,
                "sales": 0.0,
                "prepaid_orders": 0,
                "cod_orders": 0,
                "ppcod_orders": 0,
                "cancelled_orders": 0,
                "refunded_orders": 0,
                "sessions": 0,
                "atc_sessions": 0,
            })

        for row in order_rows:
            key = UtmMergeService._order_key(row, utm_dims, is_hourly)
            m = bucket(key)
            m["orders"] += 1
            m["sales"] += float(row.get("sales", 0) or 0)

            payment_type = row.get("payment_type")
            if payment_type == "PREPAID":
                m["prepaid_orders"] += 1
            elif payment_type == "COD":
                m["cod_orders"] += 1
            elif payment_type == "PPCOD":
                m["ppcod_orders"] += 1

            returns = returns_lookup.get(row.get("order_id"), {})
            m["cancelled_orders"] += int(returns.get("is_cancelled", 0) or 0)
            m["refunded_orders"] += int(returns.get("is_refunded", 0) or 0)

        for row in session_rows:
            key = UtmMergeService._session_key(row, utm_dims, is_hourly)
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
            row["average_order_value"] = (m["sales"] / orders) if orders > 0 else 0
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
    def _order_key(row: Dict[str, Any], utm_dims: List[str], is_hourly: bool) -> Tuple[Any, ...]:
        key = tuple(row.get(d, "Unknown") for d in utm_dims)
        if is_hourly:
            key = (row.get("hour", 0),) + key
        return key

    @staticmethod
    def _session_key(row: Dict[str, Any], utm_dims: List[str], is_hourly: bool) -> Tuple[Any, ...]:
        key = tuple(row.get(d, "Unknown") for d in utm_dims)
        if is_hourly:
            key = (row.get("metric_hour", 0),) + key
        return key
