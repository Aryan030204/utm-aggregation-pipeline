-- UTM Aggregate Pipeline Table Schemas
-- Exported from brand: Personal Touch Skincare

-- Schema for utm_source_daily
DROP TABLE IF EXISTS `utm_source_daily`;
CREATE TABLE `utm_source_daily` (
  `metric_date` date DEFAULT NULL,
  `utm_source` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_source_daily_dims` (`metric_date`,`utm_source`),
  KEY `idx_utm_source_daily_utm_source` (`utm_source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_medium_daily
DROP TABLE IF EXISTS `utm_medium_daily`;
CREATE TABLE `utm_medium_daily` (
  `metric_date` date DEFAULT NULL,
  `utm_medium` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_medium_daily_dims` (`metric_date`,`utm_medium`),
  KEY `idx_utm_medium_daily_utm_medium` (`utm_medium`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_campaign_daily
DROP TABLE IF EXISTS `utm_campaign_daily`;
CREATE TABLE `utm_campaign_daily` (
  `metric_date` date DEFAULT NULL,
  `utm_campaign` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_campaign_daily_dims` (`metric_date`,`utm_campaign`),
  KEY `idx_utm_campaign_daily_utm_campaign` (`utm_campaign`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_source_medium_daily
DROP TABLE IF EXISTS `utm_source_medium_daily`;
CREATE TABLE `utm_source_medium_daily` (
  `metric_date` date DEFAULT NULL,
  `utm_source` varchar(255) DEFAULT NULL,
  `utm_medium` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_source_medium_daily_dims` (`metric_date`,`utm_source`,`utm_medium`),
  KEY `idx_utm_source_medium_daily_utm_source` (`utm_source`),
  KEY `idx_utm_source_medium_daily_utm_medium` (`utm_medium`),
  KEY `idx_utm_source_medium_daily_src_med` (`utm_source`,`utm_medium`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_source_campaign_daily
DROP TABLE IF EXISTS `utm_source_campaign_daily`;
CREATE TABLE `utm_source_campaign_daily` (
  `metric_date` date DEFAULT NULL,
  `utm_source` varchar(255) DEFAULT NULL,
  `utm_campaign` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_source_campaign_daily_dims` (`metric_date`,`utm_source`,`utm_campaign`),
  KEY `idx_utm_source_campaign_daily_utm_source` (`utm_source`),
  KEY `idx_utm_source_campaign_daily_utm_campaign` (`utm_campaign`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_medium_campaign_daily
DROP TABLE IF EXISTS `utm_medium_campaign_daily`;
CREATE TABLE `utm_medium_campaign_daily` (
  `metric_date` date DEFAULT NULL,
  `utm_medium` varchar(255) DEFAULT NULL,
  `utm_campaign` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_medium_campaign_daily_dims` (`metric_date`,`utm_medium`,`utm_campaign`),
  KEY `idx_utm_medium_campaign_daily_utm_medium` (`utm_medium`),
  KEY `idx_utm_medium_campaign_daily_utm_campaign` (`utm_campaign`),
  KEY `idx_utm_medium_campaign_daily_med_cam` (`utm_medium`,`utm_campaign`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_source_medium_campaign_daily
DROP TABLE IF EXISTS `utm_source_medium_campaign_daily`;
CREATE TABLE `utm_source_medium_campaign_daily` (
  `metric_date` date DEFAULT NULL,
  `utm_source` varchar(255) DEFAULT NULL,
  `utm_medium` varchar(255) DEFAULT NULL,
  `utm_campaign` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_source_medium_campaign_daily_dims` (`metric_date`,`utm_source`,`utm_medium`,`utm_campaign`),
  KEY `idx_utm_source_medium_campaign_daily_utm_source` (`utm_source`),
  KEY `idx_utm_source_medium_campaign_daily_utm_medium` (`utm_medium`),
  KEY `idx_utm_source_medium_campaign_daily_utm_campaign` (`utm_campaign`),
  KEY `idx_utm_source_medium_campaign_daily_src_med` (`utm_source`,`utm_medium`),
  KEY `idx_utm_source_medium_campaign_daily_med_cam` (`utm_medium`,`utm_campaign`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_source_hourly
DROP TABLE IF EXISTS `utm_source_hourly`;
CREATE TABLE `utm_source_hourly` (
  `metric_date` date DEFAULT NULL,
  `metric_hour` int DEFAULT NULL,
  `utm_source` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_source_hourly_dims` (`metric_date`,`metric_hour`,`utm_source`),
  KEY `idx_utm_source_hourly_utm_source` (`utm_source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_medium_hourly
DROP TABLE IF EXISTS `utm_medium_hourly`;
CREATE TABLE `utm_medium_hourly` (
  `metric_date` date DEFAULT NULL,
  `metric_hour` int DEFAULT NULL,
  `utm_medium` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_medium_hourly_dims` (`metric_date`,`metric_hour`,`utm_medium`),
  KEY `idx_utm_medium_hourly_utm_medium` (`utm_medium`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_campaign_hourly
DROP TABLE IF EXISTS `utm_campaign_hourly`;
CREATE TABLE `utm_campaign_hourly` (
  `metric_date` date DEFAULT NULL,
  `metric_hour` int DEFAULT NULL,
  `utm_campaign` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_campaign_hourly_dims` (`metric_date`,`metric_hour`,`utm_campaign`),
  KEY `idx_utm_campaign_hourly_utm_campaign` (`utm_campaign`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_source_medium_hourly
DROP TABLE IF EXISTS `utm_source_medium_hourly`;
CREATE TABLE `utm_source_medium_hourly` (
  `metric_date` date DEFAULT NULL,
  `metric_hour` int DEFAULT NULL,
  `utm_source` varchar(255) DEFAULT NULL,
  `utm_medium` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_source_medium_hourly_dims` (`metric_date`,`metric_hour`,`utm_source`,`utm_medium`),
  KEY `idx_utm_source_medium_hourly_utm_source` (`utm_source`),
  KEY `idx_utm_source_medium_hourly_utm_medium` (`utm_medium`),
  KEY `idx_utm_source_medium_hourly_src_med` (`utm_source`,`utm_medium`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_source_campaign_hourly
DROP TABLE IF EXISTS `utm_source_campaign_hourly`;
CREATE TABLE `utm_source_campaign_hourly` (
  `metric_date` date DEFAULT NULL,
  `metric_hour` int DEFAULT NULL,
  `utm_source` varchar(255) DEFAULT NULL,
  `utm_campaign` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_source_campaign_hourly_dims` (`metric_date`,`metric_hour`,`utm_source`,`utm_campaign`),
  KEY `idx_utm_source_campaign_hourly_utm_source` (`utm_source`),
  KEY `idx_utm_source_campaign_hourly_utm_campaign` (`utm_campaign`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_medium_campaign_hourly
DROP TABLE IF EXISTS `utm_medium_campaign_hourly`;
CREATE TABLE `utm_medium_campaign_hourly` (
  `metric_date` date DEFAULT NULL,
  `metric_hour` int DEFAULT NULL,
  `utm_medium` varchar(255) DEFAULT NULL,
  `utm_campaign` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_medium_campaign_hourly_dims` (`metric_date`,`metric_hour`,`utm_medium`,`utm_campaign`),
  KEY `idx_utm_medium_campaign_hourly_utm_medium` (`utm_medium`),
  KEY `idx_utm_medium_campaign_hourly_utm_campaign` (`utm_campaign`),
  KEY `idx_utm_medium_campaign_hourly_med_cam` (`utm_medium`,`utm_campaign`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Schema for utm_source_medium_campaign_hourly
DROP TABLE IF EXISTS `utm_source_medium_campaign_hourly`;
CREATE TABLE `utm_source_medium_campaign_hourly` (
  `metric_date` date DEFAULT NULL,
  `metric_hour` int DEFAULT NULL,
  `utm_source` varchar(255) DEFAULT NULL,
  `utm_medium` varchar(255) DEFAULT NULL,
  `utm_campaign` varchar(255) DEFAULT NULL,
  `orders` int DEFAULT '0',
  `sales` decimal(15,2) DEFAULT '0.00',
  `average_order_value` decimal(15,2) DEFAULT '0.00',
  `sessions` int DEFAULT '0',
  `atc_sessions` int DEFAULT '0',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000',
  `cancellation_rate` decimal(5,4) DEFAULT '0.0000',
  `refund_rate` decimal(5,4) DEFAULT '0.0000',
  `prepaid_orders` int DEFAULT '0',
  `cod_orders` int DEFAULT '0',
  `ppcod_orders` int DEFAULT '0',
  `cancelled_orders` int DEFAULT '0',
  `refunded_orders` int DEFAULT '0',
  KEY `idx_utm_source_medium_campaign_hourly_dims` (`metric_date`,`metric_hour`,`utm_source`,`utm_medium`,`utm_campaign`),
  KEY `idx_utm_source_medium_campaign_hourly_utm_source` (`utm_source`),
  KEY `idx_utm_source_medium_campaign_hourly_utm_medium` (`utm_medium`),
  KEY `idx_utm_source_medium_campaign_hourly_utm_campaign` (`utm_campaign`),
  KEY `idx_utm_source_medium_campaign_hourly_src_med` (`utm_source`,`utm_medium`),
  KEY `idx_utm_source_medium_campaign_hourly_med_cam` (`utm_medium`,`utm_campaign`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

