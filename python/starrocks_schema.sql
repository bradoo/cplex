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

CREATE TABLE IF NOT EXISTS platform_playbooks (
  playbook_id VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  description VARCHAR(512) NOT NULL,
  demand_multiplier DOUBLE NOT NULL,
  sla_extra_days INT NOT NULL,
  air_capacity INT NOT NULL,
  ocean_lead_time INT NOT NULL,
  unfulfilled_penalty DOUBLE NOT NULL,
  network_mode VARCHAR(64) NOT NULL,
  staff_peak BOOLEAN NOT NULL,
  soft_staffing BOOLEAN NOT NULL,
  display_order INT NOT NULL
)
PRIMARY KEY(playbook_id)
DISTRIBUTED BY HASH(playbook_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS platform_assets (
  name VARCHAR(128) NOT NULL,
  area VARCHAR(128) NOT NULL,
  url VARCHAR(256) NULL,
  path VARCHAR(256) NULL,
  display_order INT NOT NULL
)
DUPLICATE KEY(name)
DISTRIBUTED BY HASH(name) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS platform_capabilities (
  capability VARCHAR(256) NOT NULL,
  display_order INT NOT NULL
)
DUPLICATE KEY(capability)
DISTRIBUTED BY HASH(capability) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS platform_config_audit (
  audit_id VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  actor VARCHAR(64) NOT NULL,
  playbook_id VARCHAR(64) NOT NULL,
  changed_fields VARCHAR(2048) NOT NULL,
  config_snapshot VARCHAR(4096) NOT NULL
)
DUPLICATE KEY(audit_id)
DISTRIBUTED BY HASH(audit_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS platform_run_history (
  run_id VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  playbook_id VARCHAR(64) NOT NULL,
  playbook_name VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL,
  total_cost DOUBLE NOT NULL,
  network_cost DOUBLE NOT NULL,
  replenishment_cost DOUBLE NOT NULL,
  staffing_cost DOUBLE NOT NULL,
  service_cost DOUBLE NOT NULL,
  total_shortage DOUBLE NOT NULL,
  approval_level VARCHAR(64) NOT NULL,
  next_action VARCHAR(1024) NOT NULL,
  difference_headline VARCHAR(1024) NOT NULL,
  management_readout VARCHAR(2048) NOT NULL,
  upstream_source VARCHAR(512) NOT NULL,
  config_source VARCHAR(512) NOT NULL
)
PRIMARY KEY(run_id)
DISTRIBUTED BY HASH(run_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS platform_run_config_snapshot (
  run_id VARCHAR(32) NOT NULL,
  config_key VARCHAR(64) NOT NULL,
  config_value VARCHAR(512) NOT NULL
)
DUPLICATE KEY(run_id, config_key)
DISTRIBUTED BY HASH(run_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS platform_run_model_results (
  run_id VARCHAR(32) NOT NULL,
  model_key VARCHAR(64) NOT NULL,
  model_status VARCHAR(32) NOT NULL,
  cost DOUBLE NOT NULL,
  shortage DOUBLE NOT NULL,
  result_json VARCHAR(65533) NOT NULL
)
DUPLICATE KEY(run_id, model_key)
DISTRIBUTED BY HASH(run_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");
