SELECT
    {date_select}
    {extra_select},
    product_id,
    COALESCE(NULLIF(TRIM(utm_source), ''), 'Unknown') AS utm_source,
    COUNT(DISTINCT order_id) AS orders,
    COALESCE(SUM(total_price), 0) AS sales,
    SUM(CASE WHEN payment_type = 'COD' THEN 1 ELSE 0 END) AS cod_orders,
    SUM(CASE WHEN payment_type = 'PREPAID' THEN 1 ELSE 0 END) AS prepaid_orders,
    SUM(CASE WHEN payment_type = 'PPCOD' THEN 1 ELSE 0 END) AS partially_prepaid_orders,
    SUM(CASE WHEN cancelled_at IS NOT NULL THEN 1 ELSE 0 END) AS cancelled_orders,
    SUM(CASE WHEN financial_status IN ('refunded', 'partially_refunded') THEN 1 ELSE 0 END) AS refunded_orders
FROM (
    SELECT
        *,
        COALESCE(CONVERT_TZ(created_at, '+00:00', %s), created_at) AS local_created_at,
        CASE
            WHEN LOWER(payment_gateway_names) LIKE '%gokwik ppcod%' THEN 'PPCOD'
            WHEN (payment_gateway_names IS NULL
                OR payment_gateway_names = ''
                OR payment_gateway_names LIKE '%Cash on Delivery (COD)%'
                OR payment_gateway_names LIKE '%cash_on_delivery%')
                AND (payment_gateway_names NOT LIKE '%Gokwik PPCOD%' OR payment_gateway_names IS NULL)
                THEN 'COD'
            ELSE 'PREPAID'
        END AS payment_type
    FROM shopify_orders
    WHERE DATE(COALESCE(CONVERT_TZ(created_at, '+00:00', %s), created_at)) BETWEEN %s AND %s
      AND product_id IN ({product_placeholders})
) scoped_orders
GROUP BY {group_by_prefix}, product_id, utm_source
ORDER BY {group_by_prefix}, product_id;
