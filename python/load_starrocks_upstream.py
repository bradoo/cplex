import argparse
import json
import time
from pathlib import Path

import pymysql

from benchmark_upstream_volume import build_orders


DATA_PATH = Path(__file__).resolve().parent / "data" / "platform_upstream_data.json"


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


def batched(rows, size):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def load_orders(args):
    source_data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rows = build_orders(source_data.get("orders", []), args.orders)
    create_schema(args)

    started_at = time.perf_counter()
    with connect(args, args.database) as connection:
        with connection.cursor() as cursor:
            if args.truncate:
                cursor.execute(f"TRUNCATE TABLE `{args.table}`")
            inserted = 0
            insert_sql = (
                f"INSERT INTO `{args.table}` "
                "(order_id, market, channel, units, priority, requested_delivery_days, demand_share_bp) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
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
        "timings_seconds": {
            "insert_orders": round(loaded_at - started_at, 3),
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
    parser.set_defaults(truncate=True)
    args = parser.parse_args()
    print(json.dumps(load_orders(args), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
