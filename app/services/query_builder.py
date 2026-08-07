from typing import List

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

def build_sessions_query(table_name: str, is_hourly: bool = False) -> str:
    """Sessions/ATC-sessions aggregated by the table's UTM dimensions. Orders/sales
    now come from Shopify GraphQL (see ShopifyOrdersFetcher), not this table."""
    dims = get_dimension_columns(table_name, is_hourly)
    sessions_table = "hourly_product_sessions" if is_hourly else "product_sessions_snapshot"

    session_select_dims = []
    group_by_dims = []

    for d in dims:
        if d == "metric_date":
            session_select_dims.append("date AS metric_date")
            group_by_dims.append("metric_date")
        elif d == "metric_hour":
            session_select_dims.append("hour AS metric_hour")
            group_by_dims.append("metric_hour")
        else:
            if d == "utm_source":
                session_select_dims.append(
                    "CASE "
                    f"WHEN LOWER(TRIM(COALESCE({d}, ''))) = 'direct' THEN 'direct' "
                    "WHEN LOWER(COALESCE(referrer_name, '')) = 'direct' THEN 'direct' "
                    f"WHEN LOWER(TRIM(COALESCE({d}, ''))) IN ('', 'unknown') THEN 'direct' "
                    f"ELSE {d} END AS {d}"
                )
            else:
                session_select_dims.append(f"IFNULL({d}, 'Unknown') AS {d}")
            group_by_dims.append(d)

    session_select_str = ", ".join(session_select_dims)
    group_by_str = ", ".join(group_by_dims)

    return f"""
    SELECT
        {session_select_str},
        SUM(IFNULL(sessions, 0)) AS sessions,
        SUM(IFNULL(sessions_with_cart_additions, 0)) AS atc_sessions
    FROM {sessions_table}
    WHERE date = %s
    GROUP BY {group_by_str};
    """


def build_returns_lookup_query(order_ids: List[str]) -> str:
    """Cancel/refund flags for a specific batch of order_ids fetched from GraphQL.
    returns_fact has no date column of its own, so scoping is done by order_id set
    rather than by date range."""
    placeholders = ", ".join(["%s"] * len(order_ids))
    return f"""
    SELECT order_id,
           MAX(CASE WHEN event_type = 'CANCEL' THEN 1 ELSE 0 END) AS is_cancelled,
           MAX(CASE WHEN event_type = 'REFUND' THEN 1 ELSE 0 END) AS is_refunded
    FROM returns_fact
    WHERE order_id IN ({placeholders})
    GROUP BY order_id;
    """

def build_bulk_insert_query(table_name: str, columns: List[str], num_rows: int) -> str:
    cols_csv = ", ".join(columns)
    placeholder_group = "(" + ", ".join(["%s"] * len(columns)) + ")"
    values_csv = ", ".join([placeholder_group] * num_rows)
    return f"INSERT INTO {table_name} ({cols_csv}) VALUES {values_csv};"
