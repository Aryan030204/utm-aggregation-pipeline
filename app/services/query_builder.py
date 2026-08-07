from typing import List
from app.services.payment_classifier import PAYMENT_TYPE_CASE_SQL

METRIC_COLUMNS = [
    "orders",
    "sales",
    "average_order_value",
    "sessions",
    "atc_sessions",
    "conversion_rate",
    "cancellation_rate",
    "refund_rate",
    "prepaid_orders",
    "cod_orders",
    "ppcod_orders",
    "cancelled_orders",
    "refunded_orders",
]

def get_dimension_columns(table_name: str, is_hourly: bool = False) -> List[str]:
    parts = table_name.replace('_daily', '').replace('_hourly', '').split('_')[1:]
    columns = ["metric_date"]
    if is_hourly:
        columns.append("metric_hour")
    for part in parts:
        columns.append(f"utm_{part}")
    return columns

def get_all_columns(table_name: str, is_hourly: bool = False) -> List[str]:
    return get_dimension_columns(table_name, is_hourly) + list(METRIC_COLUMNS)

def build_delete_query(table_name: str) -> str:
    return f"DELETE FROM {table_name} WHERE metric_date = %s;"

def build_orders_query(table_name: str, is_hourly: bool = False) -> str:
    """Orders + sales + payment-type split + cancel/refund counts, aggregated by the
    table's UTM dimensions. Sessions/atc_sessions are fetched separately from Shopify
    GraphQL (see ShopifySessionsFetcher), not from this query."""
    dims = get_dimension_columns(table_name, is_hourly)

    order_select_dims = []
    group_by_dims = []

    for d in dims:
        if d == "metric_date":
            order_select_dims.append("DATE(so.created_at) AS metric_date")
            group_by_dims.append("metric_date")
        elif d == "metric_hour":
            order_select_dims.append("HOUR(so.created_at) AS metric_hour")
            group_by_dims.append("metric_hour")
        else:
            order_select_dims.append(f"IFNULL(so.{d}, 'Unknown') AS {d}")
            group_by_dims.append(d)

    order_select_str = ", ".join(order_select_dims)
    group_by_str = ", ".join(group_by_dims)

    return f"""
    SELECT
        {order_select_str},
        COUNT(DISTINCT so.order_id) AS orders,
        COALESCE(SUM(so.total_price), 0) AS sales,
        SUM(CASE WHEN payment_type = 'PREPAID' THEN 1 ELSE 0 END) AS prepaid_orders,
        SUM(CASE WHEN payment_type = 'COD' THEN 1 ELSE 0 END) AS cod_orders,
        SUM(CASE WHEN payment_type = 'PPCOD' THEN 1 ELSE 0 END) AS ppcod_orders,
        SUM(IFNULL(r.is_cancelled, 0)) AS cancelled_orders,
        SUM(IFNULL(r.is_refunded, 0)) AS refunded_orders
    FROM (
        SELECT *, ({PAYMENT_TYPE_CASE_SQL}) AS payment_type
        FROM shopify_orders
        WHERE created_at >= %s AND created_at < %s
    ) so
    LEFT JOIN (
        SELECT order_id,
               MAX(CASE WHEN event_type = 'CANCEL' THEN 1 ELSE 0 END) AS is_cancelled,
               MAX(CASE WHEN event_type = 'REFUND' THEN 1 ELSE 0 END) AS is_refunded
        FROM returns_fact
        GROUP BY order_id
    ) r ON so.order_id = r.order_id
    GROUP BY {group_by_str};
    """

def build_bulk_insert_query(table_name: str, columns: List[str], num_rows: int) -> str:
    cols_csv = ", ".join(columns)
    placeholder_group = "(" + ", ".join(["%s"] * len(columns)) + ")"
    values_csv = ", ".join([placeholder_group] * num_rows)
    return f"INSERT INTO {table_name} ({cols_csv}) VALUES {values_csv};"
