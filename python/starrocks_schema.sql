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

CREATE TABLE IF NOT EXISTS upstream_network_warehouses (
  warehouse VARCHAR(64) NOT NULL,
  capacity INT NOT NULL,
  fixed_cost DOUBLE NOT NULL,
  handling_cost DOUBLE NOT NULL
)
PRIMARY KEY(warehouse)
DISTRIBUTED BY HASH(warehouse) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_network_markets (
  market VARCHAR(64) NOT NULL,
  demand INT NOT NULL,
  max_delivery_days INT NOT NULL
)
PRIMARY KEY(market)
DISTRIBUTED BY HASH(market) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_network_lanes (
  warehouse VARCHAR(64) NOT NULL,
  market VARCHAR(64) NOT NULL,
  last_mile_cost DOUBLE NOT NULL,
  delivery_days INT NOT NULL
)
DUPLICATE KEY(warehouse, market)
DISTRIBUTED BY HASH(warehouse, market) BUCKETS 8
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_network_expansion_options (
  warehouse VARCHAR(64) NOT NULL,
  max_extra_capacity INT NOT NULL,
  unit_cost DOUBLE NOT NULL
)
PRIMARY KEY(warehouse)
DISTRIBUTED BY HASH(warehouse) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_replenishment_weeks (
  week_name VARCHAR(32) NOT NULL,
  week_index INT NOT NULL
)
PRIMARY KEY(week_name)
DISTRIBUTED BY HASH(week_name) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_replenishment_demand (
  week_name VARCHAR(32) NOT NULL,
  demand INT NOT NULL
)
PRIMARY KEY(week_name)
DISTRIBUTED BY HASH(week_name) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_replenishment_lanes (
  lane VARCHAR(64) NOT NULL,
  lead_time_weeks INT NOT NULL,
  unit_cost DOUBLE NOT NULL,
  weekly_capacity INT NOT NULL
)
PRIMARY KEY(lane)
DISTRIBUTED BY HASH(lane) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_replenishment_parameters (
  parameter_id VARCHAR(32) NOT NULL,
  initial_inventory INT NOT NULL,
  target_ending_inventory INT NOT NULL,
  holding_cost DOUBLE NOT NULL,
  stockout_penalty DOUBLE NOT NULL
)
PRIMARY KEY(parameter_id)
DISTRIBUTED BY HASH(parameter_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_service_markets (
  market VARCHAR(64) NOT NULL,
  demand INT NOT NULL,
  max_avg_delivery_days INT NOT NULL
)
PRIMARY KEY(market)
DISTRIBUTED BY HASH(market) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_service_providers (
  service VARCHAR(64) NOT NULL,
  capacity INT NOT NULL,
  fixed_cost DOUBLE NOT NULL
)
PRIMARY KEY(service)
DISTRIBUTED BY HASH(service) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS upstream_service_provider_market_terms (
  service VARCHAR(64) NOT NULL,
  market VARCHAR(64) NOT NULL,
  unit_cost DOUBLE NOT NULL,
  delivery_days INT NOT NULL
)
DUPLICATE KEY(service, market)
DISTRIBUTED BY HASH(service, market) BUCKETS 8
PROPERTIES ("replication_num" = "1");
