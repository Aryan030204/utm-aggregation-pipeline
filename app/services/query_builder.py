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

def build_orders_query() -> str:
    """Orders + sales + payment-type split + cancel/refund counts at the finest grain
    (date, hour, source, medium, campaign), for one [start, end) created_at window.
    Every aggregate table is derived from these rows in Python (see
    UtmMergeService.rollup_orders), so this runs once per date instead of once per
    table. Every column is additive across buckets, including orders: an order
    carries a single created_at and UTM set, so it lands in exactly one bucket.
    Sessions/atc_sessions come from Shopify GraphQL (ShopifySessionsFetcher)."""
    # GROUP BY repeats the expressions instead of using the aliases: for GROUP BY,
    # MySQL resolves a name to the FROM-clause column before the select alias, which
    # would group on the raw (NULL-able) utm columns rather than the filled-in values.
    return f"""
    SELECT
        DATE(so.created_at) AS metric_date,
        HOUR(so.created_at) AS metric_hour,
        IFNULL(so.utm_source, 'direct') AS utm_source,
        IFNULL(so.utm_medium, 'Unknown') AS utm_medium,
        IFNULL(so.utm_campaign, 'Unknown') AS utm_campaign,
        COUNT(DISTINCT so.order_id) AS orders,
        COALESCE(SUM(so.total_price), 0) AS sales,
        SUM(CASE WHEN so.payment_type = 'PREPAID' THEN 1 ELSE 0 END) AS prepaid_orders,
        SUM(CASE WHEN so.payment_type = 'COD' THEN 1 ELSE 0 END) AS cod_orders,
        SUM(CASE WHEN so.payment_type = 'PPCOD' THEN 1 ELSE 0 END) AS ppcod_orders,
        SUM(IFNULL(r.is_cancelled, 0)) AS cancelled_orders,
        SUM(IFNULL(r.is_refunded, 0)) AS refunded_orders
    FROM (
        SELECT order_id, created_at, total_price, utm_source, utm_medium, utm_campaign,
               ({PAYMENT_TYPE_CASE_SQL}) AS payment_type
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
    GROUP BY DATE(so.created_at), HOUR(so.created_at),
             IFNULL(so.utm_source, 'direct'), IFNULL(so.utm_medium, 'Unknown'), IFNULL(so.utm_campaign, 'Unknown');
    """

def build_bulk_insert_query(table_name: str, columns: List[str], num_rows: int) -> str:
    cols_csv = ", ".join(columns)
    placeholder_group = "(" + ", ".join(["%s"] * len(columns)) + ")"
    values_csv = ", ".join([placeholder_group] * num_rows)
    return f"INSERT INTO {table_name} ({cols_csv}) VALUES {values_csv};"
