CREATE DATABASE IF NOT EXISTS cplex_poc;

USE cplex_poc;

CREATE TABLE IF NOT EXISTS upstream_orders (
  order_id VARCHAR(32) NOT NULL,
  market VARCHAR(64) NOT NULL,
  channel VARCHAR(64) NOT NULL,
  units INT NOT NULL,
  priority VARCHAR(32) NOT NULL,
  requested_delivery_days INT NOT NULL,
  demand_share_bp DOUBLE NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 16
PROPERTIES (
  "replication_num" = "1"
);
