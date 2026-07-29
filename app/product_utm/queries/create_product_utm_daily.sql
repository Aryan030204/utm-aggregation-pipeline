CREATE TABLE IF NOT EXISTS product_utm_daily (
    date DATE NOT NULL,
    product_id BIGINT NOT NULL,
    utm_source VARCHAR(255) NOT NULL,
    sessions INT NOT NULL DEFAULT 0,
    atc_sessions INT NOT NULL DEFAULT 0,
    orders INT NOT NULL DEFAULT 0,
    sales DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    average_order_value DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    cod_orders INT NOT NULL DEFAULT 0,
    prepaid_orders INT NOT NULL DEFAULT 0,
    partially_prepaid_orders INT NOT NULL DEFAULT 0,
    cancelled_orders INT NOT NULL DEFAULT 0,
    refunded_orders INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_product_utm_daily_dims (date, product_id, utm_source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
