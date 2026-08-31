import argparse
import json
import time
from pathlib import Path

import pymysql

from benchmark_upstream_volume import build_orders


DATA_PATH = Path(__file__).resolve().parent / "data" / "platform_upstream_data.json"
PLATFORM_DATA_PATH = Path(__file__).resolve().parent / "data" / "platform_poc_data.json"


def connect(args, database=None):
    return pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=database,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def create_schema(args):
    with connect(args) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{args.database}`")
    with connect(args, args.database) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{args.table}` (
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
                DISTRIBUTED BY HASH(order_id) BUCKETS {args.buckets}
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_network_warehouses (
                  warehouse VARCHAR(64) NOT NULL,
                  capacity INT NOT NULL,
                  fixed_cost DOUBLE NOT NULL,
                  handling_cost DOUBLE NOT NULL
                )
                PRIMARY KEY(warehouse)
                DISTRIBUTED BY HASH(warehouse) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_network_markets (
                  market VARCHAR(64) NOT NULL,
                  demand INT NOT NULL,
                  max_delivery_days INT NOT NULL
                )
                PRIMARY KEY(market)
                DISTRIBUTED BY HASH(market) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_network_lanes (
                  warehouse VARCHAR(64) NOT NULL,
                  market VARCHAR(64) NOT NULL,
                  last_mile_cost DOUBLE NOT NULL,
                  delivery_days INT NOT NULL
                )
                DUPLICATE KEY(warehouse, market)
                DISTRIBUTED BY HASH(warehouse, market) BUCKETS 8
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_network_expansion_options (
                  warehouse VARCHAR(64) NOT NULL,
                  max_extra_capacity INT NOT NULL,
                  unit_cost DOUBLE NOT NULL
                )
                PRIMARY KEY(warehouse)
                DISTRIBUTED BY HASH(warehouse) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_weather_lane_impacts (
                  warehouse VARCHAR(64) NOT NULL,
                  market VARCHAR(64) NOT NULL,
                  risk_level VARCHAR(32) NOT NULL,
                  delay_days INT NOT NULL,
                  cost_multiplier DOUBLE NOT NULL,
                  reason VARCHAR(512) NOT NULL,
                  snapshot_time VARCHAR(64) NOT NULL
                )
                DUPLICATE KEY(warehouse, market)
                DISTRIBUTED BY HASH(warehouse, market) BUCKETS 8
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_replenishment_weeks (
                  week_name VARCHAR(32) NOT NULL,
                  week_index INT NOT NULL
                )
                PRIMARY KEY(week_name)
                DISTRIBUTED BY HASH(week_name) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_replenishment_demand (
                  week_name VARCHAR(32) NOT NULL,
                  demand INT NOT NULL
                )
                PRIMARY KEY(week_name)
                DISTRIBUTED BY HASH(week_name) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_replenishment_lanes (
                  lane VARCHAR(64) NOT NULL,
                  lead_time_weeks INT NOT NULL,
                  unit_cost DOUBLE NOT NULL,
                  weekly_capacity INT NOT NULL
                )
                PRIMARY KEY(lane)
                DISTRIBUTED BY HASH(lane) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_replenishment_parameters (
                  parameter_id VARCHAR(32) NOT NULL,
                  initial_inventory INT NOT NULL,
                  target_ending_inventory INT NOT NULL,
                  holding_cost DOUBLE NOT NULL,
                  stockout_penalty DOUBLE NOT NULL
                )
                PRIMARY KEY(parameter_id)
                DISTRIBUTED BY HASH(parameter_id) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_service_markets (
                  market VARCHAR(64) NOT NULL,
                  demand INT NOT NULL,
                  max_avg_delivery_days INT NOT NULL
                )
                PRIMARY KEY(market)
                DISTRIBUTED BY HASH(market) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_service_providers (
                  service VARCHAR(64) NOT NULL,
                  capacity INT NOT NULL,
                  fixed_cost DOUBLE NOT NULL
                )
                PRIMARY KEY(service)
                DISTRIBUTED BY HASH(service) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS upstream_service_provider_market_terms (
                  service VARCHAR(64) NOT NULL,
                  market VARCHAR(64) NOT NULL,
                  unit_cost DOUBLE NOT NULL,
                  delivery_days INT NOT NULL
                )
                DUPLICATE KEY(service, market)
                DISTRIBUTED BY HASH(service, market) BUCKETS 8
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
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
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS platform_assets (
                  name VARCHAR(128) NOT NULL,
                  area VARCHAR(128) NOT NULL,
                  url VARCHAR(256) NULL,
                  path VARCHAR(256) NULL,
                  display_order INT NOT NULL
                )
                DUPLICATE KEY(name)
                DISTRIBUTED BY HASH(name) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS platform_capabilities (
                  capability VARCHAR(256) NOT NULL,
                  display_order INT NOT NULL
                )
                DUPLICATE KEY(capability)
                DISTRIBUTED BY HASH(capability) BUCKETS 4
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )
            cursor.execute(
                f"""
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
                PROPERTIES ("replication_num" = "{args.replication_num}")
                """
            )


def batched(rows, size):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def load_dimension_tables(cursor, source_data):
    tables = [
        "upstream_network_warehouses",
        "upstream_network_markets",
        "upstream_network_lanes",
        "upstream_network_expansion_options",
        "upstream_weather_lane_impacts",
        "upstream_replenishment_weeks",
        "upstream_replenishment_demand",
        "upstream_replenishment_lanes",
        "upstream_replenishment_parameters",
        "upstream_service_markets",
        "upstream_service_providers",
        "upstream_service_provider_market_terms",
    ]
    for table in tables:
        cursor.execute(f"TRUNCATE TABLE `{table}`")

    network = source_data["network"]
    cursor.executemany(
        "INSERT INTO upstream_network_warehouses (warehouse, capacity, fixed_cost, handling_cost) VALUES (%s, %s, %s, %s)",
        [
            (warehouse, values["capacity"], values["fixed_cost"], values["handling_cost"])
            for warehouse, values in network["warehouses"].items()
        ],
    )
    cursor.executemany(
        "INSERT INTO upstream_network_markets (market, demand, max_delivery_days) VALUES (%s, %s, %s)",
        [
            (market, values["demand"], values["max_delivery_days"])
            for market, values in network["markets"].items()
        ],
    )
    cursor.executemany(
        "INSERT INTO upstream_network_lanes (warehouse, market, last_mile_cost, delivery_days) VALUES (%s, %s, %s, %s)",
        [
            (row["warehouse"], row["market"], row["last_mile_cost"], row["delivery_days"])
            for row in network["lanes"]
        ],
    )
    cursor.executemany(
        "INSERT INTO upstream_network_expansion_options (warehouse, max_extra_capacity, unit_cost) VALUES (%s, %s, %s)",
        [
            (warehouse, values["max_extra_capacity"], values["unit_cost"])
            for warehouse, values in network["expansion_options"].items()
        ],
    )
    weather = source_data.get("weather", {})
    weather_rows = [
        (
            row["warehouse"],
            row["market"],
            row["risk_level"],
            row["delay_days"],
            row["cost_multiplier"],
            row["reason"],
            weather.get("snapshot_time", ""),
        )
        for row in weather.get("lane_impacts", [])
    ]
    if weather_rows:
        cursor.executemany(
            """
            INSERT INTO upstream_weather_lane_impacts
            (warehouse, market, risk_level, delay_days, cost_multiplier, reason, snapshot_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            weather_rows,
        )

    replenishment = source_data["replenishment"]
    cursor.executemany(
        "INSERT INTO upstream_replenishment_weeks (week_name, week_index) VALUES (%s, %s)",
        [(week, index) for index, week in enumerate(replenishment["weeks"])],
    )
    cursor.executemany(
        "INSERT INTO upstream_replenishment_demand (week_name, demand) VALUES (%s, %s)",
        list(replenishment["demand"].items()),
    )
    cursor.executemany(
        "INSERT INTO upstream_replenishment_lanes (lane, lead_time_weeks, unit_cost, weekly_capacity) VALUES (%s, %s, %s, %s)",
        [
            (lane, values["lead_time_weeks"], values["unit_cost"], values["weekly_capacity"])
            for lane, values in replenishment["lanes"].items()
        ],
    )
    cursor.execute(
        """
        INSERT INTO upstream_replenishment_parameters
        (parameter_id, initial_inventory, target_ending_inventory, holding_cost, stockout_penalty)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            "default",
            replenishment["initial_inventory"],
            replenishment["target_ending_inventory"],
            replenishment["holding_cost"],
            replenishment["stockout_penalty"],
        ),
    )

    service_level = source_data["service_level"]
    cursor.executemany(
        "INSERT INTO upstream_service_markets (market, demand, max_avg_delivery_days) VALUES (%s, %s, %s)",
        [
            (market, values["demand"], values["max_avg_delivery_days"])
            for market, values in service_level["markets"].items()
        ],
    )
    cursor.executemany(
        "INSERT INTO upstream_service_providers (service, capacity, fixed_cost) VALUES (%s, %s, %s)",
        [
            (service, values["capacity"], values["fixed_cost"])
            for service, values in service_level["services"].items()
        ],
    )
    terms = []
    for service, values in service_level["services"].items():
        for market, unit_cost in values["unit_cost_by_market"].items():
            terms.append((service, market, unit_cost, values["delivery_days_by_market"][market]))
    cursor.executemany(
        "INSERT INTO upstream_service_provider_market_terms (service, market, unit_cost, delivery_days) VALUES (%s, %s, %s, %s)",
        terms,
    )
    return {
        "network_warehouses": len(network["warehouses"]),
        "network_markets": len(network["markets"]),
        "network_lanes": len(network["lanes"]),
        "network_expansion_options": len(network["expansion_options"]),
        "weather_lane_impacts": len(weather_rows),
        "replenishment_weeks": len(replenishment["weeks"]),
        "replenishment_lanes": len(replenishment["lanes"]),
        "service_markets": len(service_level["markets"]),
        "service_providers": len(service_level["services"]),
        "service_provider_market_terms": len(terms),
    }


def load_platform_tables(cursor, platform_data):
    for table in ("platform_playbooks", "platform_assets", "platform_capabilities"):
        cursor.execute(f"TRUNCATE TABLE `{table}`")
    cursor.executemany(
        """
        INSERT INTO platform_playbooks
        (playbook_id, name, description, demand_multiplier, sla_extra_days,
         air_capacity, ocean_lead_time, unfulfilled_penalty, network_mode,
         staff_peak, soft_staffing, display_order)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                playbook_id,
                values["name"],
                values["description"],
                values["demand_multiplier"],
                values["sla_extra_days"],
                values["air_capacity"],
                values["ocean_lead_time"],
                values["unfulfilled_penalty"],
                values["network_mode"],
                int(values["staff_peak"]),
                int(values["soft_staffing"]),
                index,
            )
            for index, (playbook_id, values) in enumerate(platform_data["playbooks"].items())
        ],
    )
    cursor.executemany(
        "INSERT INTO platform_assets (name, area, url, path, display_order) VALUES (%s, %s, %s, %s, %s)",
        [
            (asset["name"], asset["area"], asset.get("url", ""), asset.get("path", ""), index)
            for index, asset in enumerate(platform_data["assets"])
        ],
    )
    cursor.executemany(
        "INSERT INTO platform_capabilities (capability, display_order) VALUES (%s, %s)",
        [(capability, index) for index, capability in enumerate(platform_data["capabilities"])],
    )
    return {
        "playbooks": len(platform_data["playbooks"]),
        "assets": len(platform_data["assets"]),
        "capabilities": len(platform_data["capabilities"]),
    }


def load_orders(args):
    source_data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    platform_data = json.loads(PLATFORM_DATA_PATH.read_text(encoding="utf-8"))
    rows = [] if args.skip_orders else build_orders(source_data.get("orders", []), args.orders)
    create_schema(args)

    started_at = time.perf_counter()
    with connect(args, args.database) as connection:
        with connection.cursor() as cursor:
            dimension_counts = load_dimension_tables(cursor, source_data)
            platform_counts = load_platform_tables(cursor, platform_data)
            dimensions_loaded_at = time.perf_counter()
            if args.truncate and not args.skip_orders:
                cursor.execute(f"TRUNCATE TABLE `{args.table}`")
            inserted = 0
            insert_sql = (
                f"INSERT INTO `{args.table}` "
                "(order_id, market, channel, units, priority, requested_delivery_days, demand_share_bp) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
            if not args.skip_orders:
                for batch in batched(rows, args.batch_size):
                    cursor.executemany(
                        insert_sql,
                        [
                            (
                                row["order_id"],
                                row["market"],
                                row["channel"],
                                row["units"],
                                row["priority"],
                                row["requested_delivery_days"],
                                row["demand_share_bp"],
                            )
                            for row in batch
                        ],
                    )
                    inserted += len(batch)
                    if args.progress and inserted % args.progress == 0:
                        print(f"inserted={inserted}")
    loaded_at = time.perf_counter()

    with connect(args, args.database) as connection:
        with connection.cursor() as cursor:
            counted_at = time.perf_counter()
            cursor.execute(f"SELECT COUNT(*) AS order_line_count FROM `{args.table}`")
            order_line_count = int(cursor.fetchone()["order_line_count"])
            count_ready_at = time.perf_counter()
            cursor.execute(
                f"""
                SELECT market, COUNT(*) AS order_lines, SUM(units) AS units
                FROM `{args.table}`
                GROUP BY market
                ORDER BY market
                """
            )
            market_rows = list(cursor.fetchall())
            aggregated_at = time.perf_counter()

    return {
        "database": args.database,
        "table": args.table,
        "target_order_lines": args.orders,
        "loaded_order_lines": order_line_count,
        "dimension_rows": dimension_counts,
        "platform_rows": platform_counts,
        "timings_seconds": {
            "load_dimensions": round(dimensions_loaded_at - started_at, 3),
            "insert_orders": round(loaded_at - dimensions_loaded_at, 3),
            "count_orders": round(count_ready_at - counted_at, 3),
            "aggregate_by_market": round(aggregated_at - count_ready_at, 3),
        },
        "market_rows": market_rows,
    }


def main():
    parser = argparse.ArgumentParser(description="Load synthetic upstream orders into local StarRocks.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--database", default="cplex_poc")
    parser.add_argument("--table", default="upstream_orders")
    parser.add_argument("--orders", type=int, default=1_000_000)
    parser.add_argument("--batch-size", type=int, default=10_000)
    parser.add_argument("--buckets", type=int, default=16)
    parser.add_argument("--replication-num", default="1")
    parser.add_argument("--progress", type=int, default=100_000)
    parser.add_argument("--no-truncate", action="store_false", dest="truncate")
    parser.add_argument("--skip-orders", action="store_true")
    parser.set_defaults(truncate=True)
    args = parser.parse_args()
    print(json.dumps(load_orders(args), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
