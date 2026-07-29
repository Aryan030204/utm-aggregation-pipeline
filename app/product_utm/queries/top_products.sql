SELECT
    product_id,
    landing_page_path,
    SUM(COALESCE(sessions, 0)) AS total_sessions
FROM mv_product_sessions_by_path_daily
WHERE date BETWEEN %s AND %s
  AND product_id IS NOT NULL
  AND landing_page_path IS NOT NULL
  AND landing_page_path <> ''
GROUP BY product_id, landing_page_path
ORDER BY total_sessions DESC, product_id ASC
LIMIT %s;
