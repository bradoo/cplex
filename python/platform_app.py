import hashlib
import json
import math
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from docplex.mp.model import Model
from flask import Flask, jsonify, render_template, request

from cross_border_ecommerce_replenishment_demo import solve_replenishment_plan
from scheduling_solver import (
    default_problem,
    solve_staff_scheduling,
    solve_staff_scheduling_soft,
)


app = Flask(__name__)
DATA_PATH = Path(__file__).resolve().parent / "data" / "platform_poc_data.json"
UPSTREAM_DATA_PATH = Path(__file__).resolve().parent / "data" / "platform_upstream_data.json"
RUN_HISTORY_PATH = Path(__file__).resolve().parent / "reports" / "platform_runs.jsonl"
APPROVAL_HISTORY_PATH = Path(__file__).resolve().parent / "reports" / "platform_approvals.jsonl"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
NETWORK_MODES = {"strict", "soft_capacity", "capacity_expansion"}
APPROVAL_ACTIONS = {"submit", "approve", "reject"}
ROLE_PERMISSIONS = {
    "viewer": {"view"},
    "data_admin": {"view", "edit_upstream"},
    "planner": {"view", "edit_config", "run_model", "submit_approval", "export_report"},
    "approver": {"view", "decide_approval"},
    "admin": {"view", "edit_upstream", "edit_config", "run_model", "submit_approval", "decide_approval", "export_report"},
}
ROLE_LABELS = {
    "viewer": "只读查看",
    "data_admin": "数据管理员",
    "planner": "计划员",
    "approver": "审批人",
    "admin": "管理员",
}
APPROVAL_TRANSITIONS = {
    "not_submitted": {"submit": "submitted"},
    "rejected": {"submit": "submitted"},
    "submitted": {"approve": "approved", "reject": "rejected"},
}
STARROCKS_DEFAULT_LIMIT = 1000
STARROCKS_SOURCE_TABLES = [
    ("upstream_orders", "订单事实表"),
    ("platform_playbooks", "场景方案配置"),
    ("platform_assets", "平台资产导航"),
    ("platform_capabilities", "平台能力说明"),
    ("platform_run_history", "求解运行主表"),
    ("platform_run_config_snapshot", "运行参数快照"),
    ("platform_run_model_results", "模型结果明细"),
    ("platform_run_version_snapshot", "运行版本快照"),
    ("platform_run_approvals", "审批流转记录"),
    ("upstream_network_warehouses", "仓库能力"),
    ("upstream_network_markets", "市场需求"),
    ("upstream_network_lanes", "仓网线路"),
    ("upstream_network_expansion_options", "扩容选项"),
    ("upstream_replenishment_weeks", "补货周序列"),
    ("upstream_replenishment_demand", "补货预测"),
    ("upstream_replenishment_lanes", "补货渠道能力"),
    ("upstream_replenishment_parameters", "补货全局参数"),
    ("upstream_service_markets", "服务市场需求"),
    ("upstream_service_providers", "服务商能力"),
    ("upstream_service_provider_market_terms", "服务商市场条款"),
]
CONFIG_AUDIT_KEYS = ["demand_multiplier", "sla_extra_days", "air_capacity", "ocean_lead_time", "unfulfilled_penalty", "network_mode", "staff_peak", "soft_staffing"]


def load_platform_data():
    with DATA_PATH.open(encoding="utf-8") as file:
        data = json.load(file)
    if starrocks_upstream_enabled():
        return load_starrocks_platform_data(data)
    return data


def load_upstream_data():
    with UPSTREAM_DATA_PATH.open(encoding="utf-8") as file:
        data = json.load(file)
    if starrocks_upstream_enabled():
        return load_starrocks_orders_into_upstream_data(data)
    return data


def load_json_upstream_data():
    with UPSTREAM_DATA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def starrocks_upstream_enabled():
    return os.getenv("PLATFORM_UPSTREAM_SOURCE", "json").lower() == "starrocks"


def current_role():
    role = request.headers.get("X-Platform-Role") or request.args.get("role") or "viewer"
    return role if role in ROLE_PERMISSIONS else "viewer"


def has_permission(permission, role=None):
    role = role or current_role()
    return permission in ROLE_PERMISSIONS.get(role, set())


def require_permission(permission):
    role = current_role()
    if has_permission(permission, role):
        return None
    return (
        jsonify(
            {
                "status": "error",
                "message": f"当前角色 {ROLE_LABELS.get(role, role)} 没有权限执行该操作。",
                "required_permission": permission,
                "role": role,
            }
        ),
        403,
    )


def starrocks_config():
    return {
        "host": os.getenv("STARROCKS_HOST", "127.0.0.1"),
        "port": int(os.getenv("STARROCKS_PORT", "9030")),
        "user": os.getenv("STARROCKS_USER", "root"),
        "password": os.getenv("STARROCKS_PASSWORD", ""),
        "database": os.getenv("STARROCKS_DATABASE", "cplex_poc"),
        "table": os.getenv("STARROCKS_ORDERS_TABLE", "upstream_orders"),
        "sample_limit": int(os.getenv("STARROCKS_SAMPLE_LIMIT", str(STARROCKS_DEFAULT_LIMIT))),
    }


def upstream_data_source_label(data=None):
    if starrocks_upstream_enabled():
        metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
        if metadata.get("upstream_storage"):
            return metadata["upstream_storage"]
        config = starrocks_config()
        return f"starrocks://{config['host']}:{config['port']}/{config['database']}"
    return str(UPSTREAM_DATA_PATH.relative_to(Path(__file__).resolve().parent.parent))


def platform_data_source_label():
    if starrocks_upstream_enabled():
        config = starrocks_config()
        return f"starrocks://{config['host']}:{config['port']}/{config['database']}.platform_playbooks"
    return str(DATA_PATH.relative_to(Path(__file__).resolve().parent.parent))


def starrocks_connection():
    try:
        import pymysql
    except ImportError as error:
        raise RuntimeError("StarRocks mode requires pymysql. Run: pip install -r python/requirements.txt") from error

    config = starrocks_config()
    return pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def load_starrocks_orders_into_upstream_data(data):
    config = starrocks_config()
    table = config["table"]
    limit = config["sample_limit"]
    with starrocks_connection() as connection:
        with connection.cursor() as cursor:
            data["network"] = load_starrocks_network(cursor)
            data["replenishment"] = load_starrocks_replenishment(cursor)
            data["service_level"] = load_starrocks_service_level(cursor)
            cursor.execute(f"SELECT COUNT(*) AS order_line_count FROM `{table}`")
            order_line_count = int(cursor.fetchone()["order_line_count"])
            cursor.execute(
                f"""
                SELECT order_id, market, channel, units, priority, requested_delivery_days, demand_share_bp
                FROM `{table}`
                ORDER BY order_id
                LIMIT %s
                """,
                (limit,),
            )
            data["orders"] = list(cursor.fetchall())
    metadata = data.setdefault("metadata", {})
    metadata["source_systems"] = sorted(set(metadata.get("source_systems", [])) | {"StarRocks"})
    metadata["order_line_count"] = order_line_count
    metadata["order_sample_limit"] = limit
    metadata["record_count"] = order_line_count
    metadata["description"] = (
        f"StarRocks 上游库表已接入 {format_number(order_line_count)} 条订单明细，"
        f"页面抽样展示 {format_number(min(limit, order_line_count))} 条；"
        "模型运行前使用聚合后的业务基础表生成 CPLEX 入参。"
    )
    metadata["upstream_storage"] = f"starrocks://{config['host']}:{config['port']}/{config['database']}"
    return data


def load_starrocks_network(cursor):
    cursor.execute("SELECT warehouse, capacity, fixed_cost, handling_cost FROM upstream_network_warehouses ORDER BY warehouse")
    warehouses = {
        row["warehouse"]: {
            "capacity": int(row["capacity"]),
            "fixed_cost": float(row["fixed_cost"]),
            "handling_cost": float(row["handling_cost"]),
        }
        for row in cursor.fetchall()
    }
    cursor.execute("SELECT market, demand, max_delivery_days FROM upstream_network_markets ORDER BY market")
    markets = {
        row["market"]: {
            "demand": int(row["demand"]),
            "max_delivery_days": int(row["max_delivery_days"]),
        }
        for row in cursor.fetchall()
    }
    cursor.execute("SELECT warehouse, market, last_mile_cost, delivery_days FROM upstream_network_lanes ORDER BY warehouse, market")
    lanes = [
        {
            "warehouse": row["warehouse"],
            "market": row["market"],
            "last_mile_cost": float(row["last_mile_cost"]),
            "delivery_days": int(row["delivery_days"]),
        }
        for row in cursor.fetchall()
    ]
    cursor.execute("SELECT warehouse, max_extra_capacity, unit_cost FROM upstream_network_expansion_options ORDER BY warehouse")
    expansion_options = {
        row["warehouse"]: {
            "max_extra_capacity": int(row["max_extra_capacity"]),
            "unit_cost": float(row["unit_cost"]),
        }
        for row in cursor.fetchall()
    }
    return {
        "warehouses": warehouses,
        "markets": markets,
        "lanes": lanes,
        "expansion_options": expansion_options,
    }


def load_starrocks_replenishment(cursor):
    cursor.execute("SELECT week_name FROM upstream_replenishment_weeks ORDER BY week_index")
    weeks = [row["week_name"] for row in cursor.fetchall()]
    cursor.execute("SELECT week_name, demand FROM upstream_replenishment_demand ORDER BY week_name")
    demand = {row["week_name"]: int(row["demand"]) for row in cursor.fetchall()}
    cursor.execute("SELECT lane, lead_time_weeks, unit_cost, weekly_capacity FROM upstream_replenishment_lanes ORDER BY lane")
    lanes = {
        row["lane"]: {
            "lead_time_weeks": int(row["lead_time_weeks"]),
            "unit_cost": float(row["unit_cost"]),
            "weekly_capacity": int(row["weekly_capacity"]),
        }
        for row in cursor.fetchall()
    }
    cursor.execute("SELECT initial_inventory, target_ending_inventory, holding_cost, stockout_penalty FROM upstream_replenishment_parameters LIMIT 1")
    parameters = cursor.fetchone() or {}
    return {
        "weeks": weeks,
        "demand": demand,
        "lanes": lanes,
        "initial_inventory": int(parameters.get("initial_inventory", 0)),
        "target_ending_inventory": int(parameters.get("target_ending_inventory", 0)),
        "holding_cost": float(parameters.get("holding_cost", 0)),
        "stockout_penalty": float(parameters.get("stockout_penalty", 0)),
    }


def load_starrocks_service_level(cursor):
    cursor.execute("SELECT market, demand, max_avg_delivery_days FROM upstream_service_markets ORDER BY market")
    markets = {
        row["market"]: {
            "demand": int(row["demand"]),
            "max_avg_delivery_days": int(row["max_avg_delivery_days"]),
        }
        for row in cursor.fetchall()
    }
    cursor.execute("SELECT service, capacity, fixed_cost FROM upstream_service_providers ORDER BY service")
    services = {
        row["service"]: {
            "capacity": int(row["capacity"]),
            "fixed_cost": float(row["fixed_cost"]),
            "unit_cost_by_market": {},
            "delivery_days_by_market": {},
        }
        for row in cursor.fetchall()
    }
    cursor.execute("SELECT service, market, unit_cost, delivery_days FROM upstream_service_provider_market_terms ORDER BY service, market")
    for row in cursor.fetchall():
        service = services[row["service"]]
        service["unit_cost_by_market"][row["market"]] = float(row["unit_cost"])
        service["delivery_days_by_market"][row["market"]] = int(row["delivery_days"])
    return {
        "markets": markets,
        "services": services,
    }


def load_starrocks_platform_data(fallback_data):
    with starrocks_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT playbook_id, name, description, demand_multiplier, sla_extra_days,
                       air_capacity, ocean_lead_time, unfulfilled_penalty, network_mode,
                       staff_peak, soft_staffing
                FROM platform_playbooks
                ORDER BY display_order, playbook_id
                """
            )
            playbooks = {
                row["playbook_id"]: {
                    "name": row["name"],
                    "description": row["description"],
                    "demand_multiplier": float(row["demand_multiplier"]),
                    "sla_extra_days": int(row["sla_extra_days"]),
                    "air_capacity": int(row["air_capacity"]),
                    "ocean_lead_time": int(row["ocean_lead_time"]),
                    "unfulfilled_penalty": float(row["unfulfilled_penalty"]),
                    "network_mode": row["network_mode"],
                    "staff_peak": bool(row["staff_peak"]),
                    "soft_staffing": bool(row["soft_staffing"]),
                }
                for row in cursor.fetchall()
            }
            cursor.execute("SELECT name, area, url, path FROM platform_assets ORDER BY display_order, name")
            assets = [
                {key: value for key, value in row.items() if value not in (None, "")}
                for row in cursor.fetchall()
            ]
            cursor.execute("SELECT capability FROM platform_capabilities ORDER BY display_order, capability")
            capabilities = [row["capability"] for row in cursor.fetchall()]

    return {
        "playbooks": playbooks or fallback_data["playbooks"],
        "assets": assets or fallback_data["assets"],
        "capabilities": capabilities or fallback_data["capabilities"],
    }


def build_upstream_source_status():
    started_at = perf_counter()
    if not starrocks_upstream_enabled():
        data = load_json_upstream_data()
        metrics = build_data_quality_metrics(data)
        return {
            "status": "ok",
            "mode": "JSON",
            "source": upstream_data_source_label(data),
            "message": "当前使用本地 JSON 样例数据。",
            "timings_ms": {"total": round((perf_counter() - started_at) * 1000, 2)},
            "summary": {
                "order_lines": metrics["order_lines"],
                "sample_rows": len(data.get("orders", [])),
                "source_tables": count_source_tables(data),
            },
            "tables": [
                {"name": "orders", "rows": len(data.get("orders", [])), "role": "订单明细样例"},
                {"name": "network.warehouses", "rows": len(data["network"]["warehouses"]), "role": "仓库能力"},
                {"name": "network.markets", "rows": len(data["network"]["markets"]), "role": "市场需求"},
                {"name": "network.lanes", "rows": len(data["network"]["lanes"]), "role": "仓网线路"},
                {"name": "replenishment.demand", "rows": len(data["replenishment"]["demand"]), "role": "补货预测"},
                {"name": "service_level.services", "rows": len(data["service_level"]["services"]), "role": "服务商能力"},
            ],
        }

    config = starrocks_config()
    table_specs = [(config["table"] if table == "upstream_orders" else table, role) for table, role in STARROCKS_SOURCE_TABLES]
    try:
        with starrocks_connection() as connection:
            with connection.cursor() as cursor:
                ensure_starrocks_run_history_tables(cursor)
                tables = []
                for table, role in table_specs:
                    cursor.execute(f"SELECT COUNT(*) AS row_count FROM `{table}`")
                    tables.append({"name": f"{config['database']}.{table}", "rows": int(cursor.fetchone()["row_count"]), "role": role})
    except Exception as error:
        return {
            "status": "attention",
            "mode": "StarRocks",
            "source": upstream_data_source_label(),
            "message": str(error),
            "timings_ms": {"total": round((perf_counter() - started_at) * 1000, 2)},
            "summary": {"order_lines": 0, "sample_rows": 0, "source_tables": 0},
            "tables": [],
        }

    order_rows = next((row["rows"] for row in tables if row["name"].endswith(f".{config['table']}")), 0)
    return {
        "status": "ok",
        "mode": "StarRocks",
        "source": upstream_data_source_label(),
        "message": "当前使用 StarRocks 上游库表，页面仅抽样展示订单明细。",
        "timings_ms": {"total": round((perf_counter() - started_at) * 1000, 2)},
        "summary": {
            "order_lines": order_rows,
            "sample_rows": config["sample_limit"],
            "source_tables": len(tables),
        },
        "tables": tables,
    }


def playbooks():
    return load_platform_data()["playbooks"]


def save_platform_data(data, previous_data=None):
    if starrocks_upstream_enabled():
        save_starrocks_platform_data(data, previous_data)
        return
    save_json_file(DATA_PATH, data)


def save_starrocks_platform_data(data, previous_data=None):
    with starrocks_connection() as connection:
        with connection.cursor() as cursor:
            ensure_starrocks_config_audit_table(cursor)
            cursor.execute("TRUNCATE TABLE platform_playbooks")
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
                    for index, (playbook_id, values) in enumerate(data["playbooks"].items())
                ],
            )
            cursor.execute("TRUNCATE TABLE platform_assets")
            cursor.executemany(
                "INSERT INTO platform_assets (name, area, url, path, display_order) VALUES (%s, %s, %s, %s, %s)",
                [
                    (asset["name"], asset["area"], asset.get("url", ""), asset.get("path", ""), index)
                    for index, asset in enumerate(data["assets"])
                ],
            )
            cursor.execute("TRUNCATE TABLE platform_capabilities")
            cursor.executemany(
                "INSERT INTO platform_capabilities (capability, display_order) VALUES (%s, %s)",
                [(capability, index) for index, capability in enumerate(data["capabilities"])],
            )
            append_config_audit_rows(cursor, previous_data or {}, data)
        connection.commit()


def ensure_starrocks_config_audit_table(cursor):
    cursor.execute(
        """
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
        PROPERTIES ("replication_num" = "1")
        """
    )


def append_config_audit_rows(cursor, previous_data, next_data):
    previous_playbooks = previous_data.get("playbooks", {}) if isinstance(previous_data, dict) else {}
    rows = []
    created_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    for playbook_id, next_config in next_data.get("playbooks", {}).items():
        previous_config = previous_playbooks.get(playbook_id, {})
        changes = []
        for key in CONFIG_AUDIT_KEYS:
            if previous_config.get(key) != next_config.get(key):
                changes.append(
                    {
                        "field": key,
                        "before": previous_config.get(key),
                        "after": next_config.get(key),
                    }
                )
        if changes:
            rows.append(
                (
                    uuid.uuid4().hex[:12],
                    created_at,
                    "platform_ui",
                    playbook_id,
                    json.dumps(changes, ensure_ascii=False),
                    json.dumps(public_config(next_config), ensure_ascii=False),
                )
            )
    if rows:
        cursor.executemany(
            """
            INSERT INTO platform_config_audit
            (audit_id, created_at, actor, playbook_id, changed_fields, config_snapshot)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            rows,
        )


def load_config_audit(limit=10):
    if not starrocks_upstream_enabled():
        return []
    with starrocks_connection() as connection:
        with connection.cursor() as cursor:
            ensure_starrocks_config_audit_table(cursor)
            cursor.execute(
                """
                SELECT audit_id, created_at, actor, playbook_id, changed_fields, config_snapshot
                FROM platform_config_audit
                ORDER BY created_at DESC, audit_id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = []
            for row in cursor.fetchall():
                rows.append(
                    {
                        "audit_id": row["audit_id"],
                        "created_at": row["created_at"].isoformat(sep=" ") if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                        "actor": row["actor"],
                        "playbook_id": row["playbook_id"],
                        "changed_fields": json.loads(row["changed_fields"]),
                        "config_snapshot": json.loads(row["config_snapshot"]),
                    }
                )
            return rows


def save_upstream_data(data):
    save_json_file(UPSTREAM_DATA_PATH, data)


def save_starrocks_upstream_data(data):
    with starrocks_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE upstream_network_markets")
            cursor.executemany(
                "INSERT INTO upstream_network_markets (market, demand, max_delivery_days) VALUES (%s, %s, %s)",
                [
                    (market, values["demand"], values["max_delivery_days"])
                    for market, values in data["network"]["markets"].items()
                ],
            )
            cursor.execute("TRUNCATE TABLE upstream_network_warehouses")
            cursor.executemany(
                "INSERT INTO upstream_network_warehouses (warehouse, capacity, fixed_cost, handling_cost) VALUES (%s, %s, %s, %s)",
                [
                    (warehouse, values["capacity"], values["fixed_cost"], values["handling_cost"])
                    for warehouse, values in data["network"]["warehouses"].items()
                ],
            )
            cursor.execute("TRUNCATE TABLE upstream_network_lanes")
            cursor.executemany(
                "INSERT INTO upstream_network_lanes (warehouse, market, last_mile_cost, delivery_days) VALUES (%s, %s, %s, %s)",
                [
                    (lane["warehouse"], lane["market"], lane["last_mile_cost"], lane["delivery_days"])
                    for lane in data["network"]["lanes"]
                ],
            )
            cursor.execute("TRUNCATE TABLE upstream_network_expansion_options")
            cursor.executemany(
                "INSERT INTO upstream_network_expansion_options (warehouse, max_extra_capacity, unit_cost) VALUES (%s, %s, %s)",
                [
                    (warehouse, values["max_extra_capacity"], values["unit_cost"])
                    for warehouse, values in data["network"]["expansion_options"].items()
                ],
            )
            cursor.execute("TRUNCATE TABLE upstream_replenishment_weeks")
            cursor.executemany(
                "INSERT INTO upstream_replenishment_weeks (week_name, week_index) VALUES (%s, %s)",
                [(week, index) for index, week in enumerate(data["replenishment"]["weeks"])],
            )
            cursor.execute("TRUNCATE TABLE upstream_replenishment_demand")
            cursor.executemany(
                "INSERT INTO upstream_replenishment_demand (week_name, demand) VALUES (%s, %s)",
                list(data["replenishment"]["demand"].items()),
            )
            cursor.execute("TRUNCATE TABLE upstream_replenishment_lanes")
            cursor.executemany(
                "INSERT INTO upstream_replenishment_lanes (lane, lead_time_weeks, unit_cost, weekly_capacity) VALUES (%s, %s, %s, %s)",
                [
                    (lane, values["lead_time_weeks"], values["unit_cost"], values["weekly_capacity"])
                    for lane, values in data["replenishment"]["lanes"].items()
                ],
            )
            cursor.execute("TRUNCATE TABLE upstream_replenishment_parameters")
            cursor.execute(
                """
                INSERT INTO upstream_replenishment_parameters
                (parameter_id, initial_inventory, target_ending_inventory, holding_cost, stockout_penalty)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    "default",
                    data["replenishment"]["initial_inventory"],
                    data["replenishment"]["target_ending_inventory"],
                    data["replenishment"]["holding_cost"],
                    data["replenishment"]["stockout_penalty"],
                ),
            )
            cursor.execute("TRUNCATE TABLE upstream_service_markets")
            cursor.executemany(
                "INSERT INTO upstream_service_markets (market, demand, max_avg_delivery_days) VALUES (%s, %s, %s)",
                [
                    (market, values["demand"], values["max_avg_delivery_days"])
                    for market, values in data["service_level"]["markets"].items()
                ],
            )
            cursor.execute("TRUNCATE TABLE upstream_service_providers")
            cursor.executemany(
                "INSERT INTO upstream_service_providers (service, capacity, fixed_cost) VALUES (%s, %s, %s)",
                [
                    (service, values["capacity"], values["fixed_cost"])
                    for service, values in data["service_level"]["services"].items()
                ],
            )
            cursor.execute("TRUNCATE TABLE upstream_service_provider_market_terms")
            cursor.executemany(
                "INSERT INTO upstream_service_provider_market_terms (service, market, unit_cost, delivery_days) VALUES (%s, %s, %s, %s)",
                [
                    (service, market, values["unit_cost_by_market"][market], values["delivery_days_by_market"][market])
                    for service, values in data["service_level"]["services"].items()
                    for market in data["service_level"]["markets"]
                ],
            )
        connection.commit()


def save_json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
        temp_path = Path(file.name)
    temp_path.replace(path)


def append_run_history(result):
    record = build_run_history_record(result)
    if starrocks_upstream_enabled():
        try:
            save_starrocks_run_history(record, result)
            record["storage"] = platform_run_history_source_label()
            return record
        except Exception:
            # Keep demo runs usable if the local StarRocks instance is restarted mid-demo.
            record["storage"] = str(RUN_HISTORY_PATH.relative_to(Path(__file__).resolve().parent.parent))
    RUN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUN_HISTORY_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_run_history(limit=20):
    if starrocks_upstream_enabled():
        try:
            return load_starrocks_run_history(limit)
        except Exception:
            pass
    if not RUN_HISTORY_PATH.exists():
        return []
    with RUN_HISTORY_PATH.open(encoding="utf-8") as file:
        rows = [json.loads(line) for line in file if line.strip()]
    visible_rows = list(reversed(rows[-limit:]))
    approval_states = load_file_approval_states([row["run_id"] for row in visible_rows])
    for row in visible_rows:
        row["approval"] = approval_states.get(
            row["run_id"],
            row.get("approval") or default_approval_state(row["summary"]["approval_level"]),
        )
    return visible_rows


def platform_run_history_source_label():
    if starrocks_upstream_enabled():
        config = starrocks_config()
        return f"starrocks://{config['host']}:{config['port']}/{config['database']}.platform_run_history"
    try:
        return str(RUN_HISTORY_PATH.relative_to(Path(__file__).resolve().parent.parent))
    except ValueError:
        return str(RUN_HISTORY_PATH)


def stable_digest(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def current_model_version():
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        version = completed.stdout.strip()
        if version:
            dirty = subprocess.run(
                ["git", "diff", "--quiet"],
                cwd=Path(__file__).resolve().parent.parent,
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            return f"{version}-dirty" if dirty.returncode else version
    except Exception:
        pass
    return stable_digest(Path(__file__).read_text(encoding="utf-8"))


def build_run_version_snapshot(result):
    model_inputs = result["model_inputs"]
    upstream_digest_source = {
        "source": model_inputs["lineage"]["upstream_source"],
        "network": model_inputs["network"],
        "replenishment": model_inputs["replenishment"],
        "service_level": model_inputs["service_level"],
    }
    config_digest = stable_digest(result["config"])
    upstream_digest = stable_digest(upstream_digest_source)
    model_version = current_model_version()
    run_batch_id = f"RUN-{datetime.now(timezone.utc).astimezone().strftime('%Y%m%d')}-{result['playbook']}-{uuid.uuid4().hex[:6]}"
    return {
        "run_batch_id": run_batch_id,
        "upstream_version": f"UP-{upstream_digest}",
        "config_version": f"CFG-{config_digest}",
        "model_version": f"CODE-{model_version}",
        "solver_version": "docplex",
    }


def ensure_starrocks_run_history_tables(cursor):
    cursor.execute(
        """
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
        PROPERTIES ("replication_num" = "1")
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS platform_run_config_snapshot (
          run_id VARCHAR(32) NOT NULL,
          config_key VARCHAR(64) NOT NULL,
          config_value VARCHAR(512) NOT NULL
        )
        DUPLICATE KEY(run_id, config_key)
        DISTRIBUTED BY HASH(run_id) BUCKETS 4
        PROPERTIES ("replication_num" = "1")
        """
    )
    cursor.execute(
        """
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
        PROPERTIES ("replication_num" = "1")
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS platform_run_version_snapshot (
          run_id VARCHAR(32) NOT NULL,
          version_key VARCHAR(64) NOT NULL,
          version_value VARCHAR(512) NOT NULL
        )
        DUPLICATE KEY(run_id, version_key)
        DISTRIBUTED BY HASH(run_id) BUCKETS 4
        PROPERTIES ("replication_num" = "1")
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS platform_run_approvals (
          approval_id VARCHAR(32) NOT NULL,
          run_id VARCHAR(32) NOT NULL,
          created_at DATETIME NOT NULL,
          action VARCHAR(32) NOT NULL,
          status VARCHAR(32) NOT NULL,
          actor VARCHAR(64) NOT NULL,
          comment VARCHAR(2048) NOT NULL
        )
        DUPLICATE KEY(approval_id)
        DISTRIBUTED BY HASH(run_id) BUCKETS 4
        PROPERTIES ("replication_num" = "1")
        """
    )


def save_starrocks_run_history(record, result):
    summary = record["summary"]
    lineage = result["model_inputs"]["lineage"]
    model_rows = build_run_model_result_rows(record["run_id"], result)
    with starrocks_connection() as connection:
        with connection.cursor() as cursor:
            ensure_starrocks_run_history_tables(cursor)
            cursor.execute(
                """
                INSERT INTO platform_run_history
                (run_id, created_at, playbook_id, playbook_name, status, total_cost, network_cost,
                 replenishment_cost, staffing_cost, service_cost, total_shortage, approval_level,
                 next_action, difference_headline, management_readout, upstream_source, config_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record["run_id"],
                    record["created_at"].replace("T", " ")[:19],
                    record["playbook"],
                    record["playbook_name"],
                    result["status"],
                    summary["total_cost"],
                    summary["network_cost"],
                    summary["replenishment_cost"],
                    summary["staffing_cost"],
                    summary["service_cost"],
                    summary["total_shortage"],
                    summary["approval_level"],
                    record["next_action"],
                    record["difference"]["headline"],
                    record["difference"]["management_readout"],
                    lineage["upstream_source"],
                    lineage["scenario_config_source"],
                ),
            )
            cursor.executemany(
                "INSERT INTO platform_run_config_snapshot (run_id, config_key, config_value) VALUES (%s, %s, %s)",
                [(record["run_id"], key, json.dumps(value, ensure_ascii=False)) for key, value in record["config"].items()],
            )
            cursor.executemany(
                """
                INSERT INTO platform_run_model_results
                (run_id, model_key, model_status, cost, shortage, result_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                model_rows,
            )
            cursor.executemany(
                "INSERT INTO platform_run_version_snapshot (run_id, version_key, version_value) VALUES (%s, %s, %s)",
                [(record["run_id"], key, value) for key, value in record["versions"].items()],
            )
        connection.commit()


def build_run_model_result_rows(run_id, result):
    specs = [
        ("network", result["network"], "cost", "total_unfulfilled"),
        ("replenishment", result["replenishment"], "total_cost", "total_stockout"),
        ("service_mix", result["service_mix"], "total_cost", "sla_risk"),
        ("staffing", result["staffing"], "total_cost", "total_shortage"),
    ]
    return [
        (
            run_id,
            key,
            model_result.get("status", "-"),
            float(model_result.get(cost_key) or 0),
            float(model_result.get(shortage_key) or 0),
            json.dumps(model_result, ensure_ascii=False, default=str),
        )
        for key, model_result, cost_key, shortage_key in specs
    ]


def load_starrocks_run_history(limit=20):
    with starrocks_connection() as connection:
        with connection.cursor() as cursor:
            ensure_starrocks_run_history_tables(cursor)
            cursor.execute(
                """
                SELECT run_id, created_at, playbook_id, playbook_name, total_cost, network_cost,
                       replenishment_cost, staffing_cost, service_cost, total_shortage,
                       approval_level, next_action, difference_headline, management_readout
                FROM platform_run_history
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = list(cursor.fetchall())
            run_ids = [row["run_id"] for row in rows]
            configs = {run_id: {} for run_id in run_ids}
            if run_ids:
                placeholders = ",".join(["%s"] * len(run_ids))
                cursor.execute(
                    f"""
                    SELECT run_id, config_key, config_value
                    FROM platform_run_config_snapshot
                    WHERE run_id IN ({placeholders})
                    """,
                    run_ids,
                )
                for row in cursor.fetchall():
                    try:
                        configs[row["run_id"]][row["config_key"]] = json.loads(row["config_value"])
                    except json.JSONDecodeError:
                        configs[row["run_id"]][row["config_key"]] = row["config_value"]
                versions = {run_id: {} for run_id in run_ids}
                cursor.execute(
                    f"""
                    SELECT run_id, version_key, version_value
                    FROM platform_run_version_snapshot
                    WHERE run_id IN ({placeholders})
                    """,
                    run_ids,
                )
                for row in cursor.fetchall():
                    versions[row["run_id"]][row["version_key"]] = row["version_value"]
                approvals = load_starrocks_approval_states(cursor, run_ids)
            else:
                versions = {}
                approvals = {}
    return [
        {
            "run_id": row["run_id"],
            "created_at": row["created_at"].isoformat(timespec="seconds") if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
            "playbook": row["playbook_id"],
            "playbook_name": row["playbook_name"],
            "config": configs.get(row["run_id"], {}),
            "summary": {
                "total_cost": float(row["total_cost"]),
                "network_cost": float(row["network_cost"]),
                "replenishment_cost": float(row["replenishment_cost"]),
                "staffing_cost": float(row["staffing_cost"]),
                "service_cost": float(row["service_cost"]),
                "total_shortage": float(row["total_shortage"]),
                "approval_level": row["approval_level"],
            },
            "difference": {
                "headline": row["difference_headline"],
                "management_readout": row["management_readout"],
            },
            "next_action": row["next_action"],
            "versions": versions.get(row["run_id"], {}),
            "approval": approvals.get(row["run_id"], default_approval_state(row["approval_level"])),
            "storage": platform_run_history_source_label(),
        }
        for row in rows
    ]


def default_approval_state(approval_level):
    return {
        "status": "auto_approved" if approval_level == "自动执行" else "not_submitted",
        "status_label": "自动通过" if approval_level == "自动执行" else "待提交",
        "actor": "system" if approval_level == "自动执行" else "",
        "comment": "自动执行层级无需人工审批。" if approval_level == "自动执行" else "",
        "created_at": "",
    }


def approval_status_label(status):
    return {
        "submitted": "待审批",
        "approved": "已批准",
        "rejected": "已驳回",
        "auto_approved": "自动通过",
        "not_submitted": "待提交",
    }.get(status, status)


def approval_status_for_action(action):
    return {
        "submit": "submitted",
        "approve": "approved",
        "reject": "rejected",
    }[action]


def load_starrocks_approval_states(cursor, run_ids):
    if not run_ids:
        return {}
    placeholders = ",".join(["%s"] * len(run_ids))
    cursor.execute(
        f"""
        SELECT run_id, created_at, action, status, actor, comment
        FROM platform_run_approvals
        WHERE run_id IN ({placeholders})
        ORDER BY created_at ASC, approval_id ASC
        """,
        run_ids,
    )
    states = {}
    for row in cursor.fetchall():
        states[row["run_id"]] = {
            "status": row["status"],
            "status_label": approval_status_label(row["status"]),
            "actor": row["actor"],
            "comment": row["comment"],
            "created_at": row["created_at"].isoformat(timespec="seconds") if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
            "last_action": row["action"],
        }
    return states


def load_file_approval_states(run_ids=None):
    if not APPROVAL_HISTORY_PATH.exists():
        return {}
    wanted = set(run_ids or [])
    states = {}
    with APPROVAL_HISTORY_PATH.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            run_id = row.get("run_id")
            if wanted and run_id not in wanted:
                continue
            states[run_id] = {
                "status": row["status"],
                "status_label": approval_status_label(row["status"]),
                "actor": row.get("actor", ""),
                "comment": row.get("comment", ""),
                "created_at": row.get("created_at", ""),
                "last_action": row.get("action", ""),
            }
    return states


def load_run_approval_state(run_id):
    if starrocks_upstream_enabled():
        with starrocks_connection() as connection:
            with connection.cursor() as cursor:
                ensure_starrocks_run_history_tables(cursor)
                cursor.execute("SELECT approval_level FROM platform_run_history WHERE run_id = %s", (run_id,))
                run_row = cursor.fetchone()
                if not run_row:
                    return None
                states = load_starrocks_approval_states(cursor, [run_id])
                return states.get(run_id, default_approval_state(run_row["approval_level"]))
    file_state = load_file_approval_states([run_id]).get(run_id)
    if file_state:
        return file_state
    for row in load_run_history(100):
        if row.get("run_id") == run_id:
            return row.get("approval") or default_approval_state(row["summary"]["approval_level"])
    return None


def run_exists(run_id):
    if starrocks_upstream_enabled():
        with starrocks_connection() as connection:
            with connection.cursor() as cursor:
                ensure_starrocks_run_history_tables(cursor)
                cursor.execute("SELECT COUNT(*) AS row_count FROM platform_run_history WHERE run_id = %s", (run_id,))
                return int(cursor.fetchone()["row_count"]) > 0
    return any(row.get("run_id") == run_id for row in load_run_history(100))


def append_approval_event(run_id, action, actor, comment):
    if action not in APPROVAL_ACTIONS:
        return None, f"Unknown approval action: {action}"
    if not run_exists(run_id):
        return None, f"Unknown run_id: {run_id}"
    current_state = load_run_approval_state(run_id)
    current_status = current_state["status"] if current_state else "not_submitted"
    next_status = APPROVAL_TRANSITIONS.get(current_status, {}).get(action)
    if not next_status:
        return None, f"审批状态不允许从 {approval_status_label(current_status)} 执行 {action}"
    event = {
        "approval_id": uuid.uuid4().hex[:8],
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "action": action,
        "status": next_status,
        "status_label": approval_status_label(next_status),
        "actor": actor or "demo.cio",
        "comment": comment or "",
    }
    if starrocks_upstream_enabled():
        with starrocks_connection() as connection:
            with connection.cursor() as cursor:
                ensure_starrocks_run_history_tables(cursor)
                cursor.execute(
                    """
                    INSERT INTO platform_run_approvals
                    (approval_id, run_id, created_at, action, status, actor, comment)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event["approval_id"],
                        event["run_id"],
                        event["created_at"].replace("T", " ")[:19],
                        event["action"],
                        event["status"],
                        event["actor"],
                        event["comment"],
                    ),
                )
            connection.commit()
        return event, None
    APPROVAL_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with APPROVAL_HISTORY_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event, None


def build_run_history_record(result):
    summary = result["summary"]
    difference = result.get("difference", {})
    versions = build_run_version_snapshot(result)
    return {
        "run_id": uuid.uuid4().hex[:8],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "run_batch_id": versions["run_batch_id"],
        "playbook": result["playbook"],
        "playbook_name": result["playbook_name"],
        "config": result["config"],
        "versions": versions,
        "summary": {
            "total_cost": summary["total_cost"],
            "network_cost": summary["network_cost"],
            "replenishment_cost": summary["replenishment_cost"],
            "staffing_cost": summary["staffing_cost"],
            "service_cost": summary["service_cost"],
            "total_shortage": summary["total_shortage"],
            "approval_level": summary["approval_level"],
        },
        "difference": {
            "headline": difference.get("headline", ""),
            "management_readout": difference.get("management_readout", ""),
        },
        "approval": default_approval_state(summary["approval_level"]),
        "next_action": summary["execution_plan"][0]["action"] if summary.get("execution_plan") else "",
    }


def export_demo_report(result):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone()
    filename = f"platform_report_{timestamp.strftime('%Y%m%d_%H%M%S')}_{result['playbook']}.md"
    report_path = REPORTS_DIR / filename
    report_path.write_text(build_demo_report_markdown(result, timestamp), encoding="utf-8")
    return {
        "file": filename,
        "path": str(report_path.relative_to(Path(__file__).resolve().parent.parent)),
        "created_at": timestamp.isoformat(timespec="seconds"),
    }


def build_demo_report_markdown(result, timestamp):
    summary = result["summary"]
    config = result["config"]
    difference = result["difference"]
    lines = [
        "# CPLEX 优化平台 POC 演示报告",
        "",
        f"- 导出时间：{timestamp.isoformat(timespec='seconds')}",
        f"- 运行方案：{result['playbook_name']} (`{result['playbook']}`)",
        f"- 审批分层：{summary['approval_level']}",
        "",
        "## 1. 决策摘要",
        "",
        summary["decision_note"],
        "",
        difference["headline"],
        "",
        difference["management_readout"],
        "",
        "## 2. 核心 KPI",
        "",
        "| 指标 | 当前值 |",
        "| --- | ---: |",
        f"| 综合成本 | {format_number(summary['total_cost'])} |",
        f"| 仓网成本 | {format_number(summary['network_cost'])} |",
        f"| 补货成本 | {format_number(summary['replenishment_cost'])} |",
        f"| 排班成本 | {format_number(summary['staffing_cost'])} |",
        f"| 服务组合成本 | {format_number(summary['service_cost'])} |",
        f"| 总缺口 | {format_number(summary['total_shortage'])} |",
        "",
        "## 3. 方案参数",
        "",
        "| 参数 | 值 |",
        "| --- | --- |",
    ]
    for key, value in config.items():
        lines.append(f"| `{key}` | {markdown_cell(value)} |")
    lines.extend(
        [
            "",
            "## 4. 相对基准差异",
            "",
            "| 指标 | 当前 | 基准 | 变化 |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for metric in difference["metrics"]:
        lines.append(
            f"| {markdown_cell(metric['label'])} | {format_number(metric['current'])} | "
            f"{format_number(metric['baseline'])} | {format_signed(metric['delta'])} |"
        )
    lines.extend(["", "### 变化原因", ""])
    lines.extend(f"- {driver}" for driver in difference["drivers"])
    lines.extend(["", "## 5. 建议动作", ""])
    lines.extend(f"- {action}" for action in summary["actions"])
    lines.extend(
        [
            "",
            "## 6. 执行计划",
            "",
            "| 负责人 | 优先级 | 触发条件 | 执行动作 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in summary["execution_plan"]:
        lines.append(
            f"| {markdown_cell(row['owner'])} | {markdown_cell(row['priority'])} | "
            f"{markdown_cell(row['trigger'])} | {markdown_cell(row['action'])} |"
        )
    lines.extend(["", "## 7. 风险提示", ""])
    lines.extend(f"- {risk}" for risk in summary["risks"])
    lines.extend(
        [
            "",
            "## 8. 模型结果摘要",
            "",
            "| 模型 | 状态 | 摘要 |",
            "| --- | --- | --- |",
            f"| 仓网选址与履约 | {markdown_cell(result['network']['status'])} | 开仓 {len(result['network'].get('opened_warehouses') or [])} 个，缺口 {format_number(result['network'].get('total_unfulfilled') or 0)} |",
            f"| 跨境补货 | {markdown_cell(result['replenishment']['status'])} | 缺货 {format_number(result['replenishment'].get('total_stockout') or 0)}，订单 {len(result['replenishment'].get('orders') or [])} 笔 |",
            f"| 服务水平组合 | {markdown_cell(result['service_mix']['status'])} | 成本 {format_number(result['service_mix'].get('total_cost') or 0)} |",
            f"| 人员排班 | {markdown_cell(result['staffing']['status'])} | 模式 {markdown_cell(result['staffing'].get('mode') or '-')}，缺口 {format_number(result['staffing'].get('total_shortage') or 0)} |",
            "",
            "## 9. 数据链路",
            "",
            f"- 上游数据：{result['model_inputs']['lineage']['upstream_source']}",
            f"- 场景配置：{result['model_inputs']['lineage']['scenario_config_source']}",
            f"- 转换逻辑：{result['model_inputs']['lineage']['transform']}",
            "",
        ]
    )
    return "\n".join(lines)


def format_number(value):
    number = float(value or 0)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def format_signed(value):
    number = float(value or 0)
    if abs(number) < 1e-9:
        return "0"
    prefix = "+" if number > 0 else "-"
    return f"{prefix}{format_number(abs(number))}"


def upstream_order_line_count(data):
    metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
    if isinstance(metadata, dict) and "order_line_count" in metadata:
        return int(metadata["order_line_count"])
    return len(data.get("orders", [])) if isinstance(data, dict) else 0


def markdown_cell(value):
    return str(value).replace("|", "\\|")


def validate_platform_data(data):
    if not isinstance(data, dict):
        return "data must be a JSON object"

    for key in ("playbooks", "assets", "capabilities"):
        if key not in data:
            return f"data is missing required key: {key}"

    if not isinstance(data["playbooks"], dict) or not data["playbooks"]:
        return "playbooks must be a non-empty object"
    if not isinstance(data["assets"], list):
        return "assets must be a list"
    if not isinstance(data["capabilities"], list):
        return "capabilities must be a list"

    required_fields = {
        "name": str,
        "description": str,
        "demand_multiplier": (int, float),
        "sla_extra_days": int,
        "air_capacity": int,
        "ocean_lead_time": int,
        "unfulfilled_penalty": (int, float),
        "network_mode": str,
        "staff_peak": bool,
        "soft_staffing": bool,
    }
    for playbook_id, config in data["playbooks"].items():
        if not isinstance(playbook_id, str) or not playbook_id:
            return "playbook ids must be non-empty strings"
        if not isinstance(config, dict):
            return f"playbook {playbook_id} must be an object"
        for field, expected_type in required_fields.items():
            if field not in config:
                return f"playbook {playbook_id} is missing field: {field}"
            if not isinstance(config[field], expected_type):
                return f"playbook {playbook_id}.{field} has invalid type"
        if config["network_mode"] not in NETWORK_MODES:
            return f"playbook {playbook_id}.network_mode must be one of: {', '.join(sorted(NETWORK_MODES))}"
        if config["demand_multiplier"] <= 0:
            return f"playbook {playbook_id}.demand_multiplier must be greater than 0"
        if config["air_capacity"] < 0:
            return f"playbook {playbook_id}.air_capacity must be non-negative"
        if config["ocean_lead_time"] < 0:
            return f"playbook {playbook_id}.ocean_lead_time must be non-negative"
        if config["unfulfilled_penalty"] < 0:
            return f"playbook {playbook_id}.unfulfilled_penalty must be non-negative"
    return None


def validate_number(value, path, minimum=None, exclusive_minimum=False):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        return f"{path} must be a finite number"
    if minimum is not None:
        if exclusive_minimum and value <= minimum:
            return f"{path} must be greater than {minimum}"
        if not exclusive_minimum and value < minimum:
            return f"{path} must be at least {minimum}"
    return None


def validate_upstream_data(data):
    if not isinstance(data, dict):
        return "data must be a JSON object"

    for key in ("metadata", "network", "replenishment", "service_level"):
        if key not in data:
            return f"upstream data is missing required key: {key}"

    network = data["network"]
    for key in ("warehouses", "markets", "lanes", "expansion_options"):
        if key not in network:
            return f"network is missing required key: {key}"
    if not isinstance(network["warehouses"], dict) or not network["warehouses"]:
        return "network.warehouses must be a non-empty object"
    if not isinstance(network["markets"], dict) or not network["markets"]:
        return "network.markets must be a non-empty object"
    if not isinstance(network["lanes"], list) or not network["lanes"]:
        return "network.lanes must be a non-empty list"

    for warehouse, values in network["warehouses"].items():
        for field in ("capacity", "fixed_cost", "handling_cost"):
            if field not in values:
                return f"network.warehouses.{warehouse}.{field} is required"
            error = validate_number(values[field], f"network.warehouses.{warehouse}.{field}", minimum=0)
            if error:
                return error

    for market, values in network["markets"].items():
        for field in ("demand", "max_delivery_days"):
            if field not in values:
                return f"network.markets.{market}.{field} is required"
        error = validate_number(values["demand"], f"network.markets.{market}.demand", minimum=0)
        if error:
            return error
        error = validate_number(values["max_delivery_days"], f"network.markets.{market}.max_delivery_days", minimum=0, exclusive_minimum=True)
        if error:
            return error

    for warehouse, values in network["expansion_options"].items():
        if warehouse not in network["warehouses"]:
            return f"network.expansion_options references unknown warehouse: {warehouse}"
        for field in ("max_extra_capacity", "unit_cost"):
            if field not in values:
                return f"network.expansion_options.{warehouse}.{field} is required"
            error = validate_number(values[field], f"network.expansion_options.{warehouse}.{field}", minimum=0)
            if error:
                return error

    lane_pairs = set()
    for lane in network["lanes"]:
        for field in ("warehouse", "market", "last_mile_cost", "delivery_days"):
            if field not in lane:
                return f"network lane is missing field: {field}"
        if lane["warehouse"] not in network["warehouses"]:
            return f"network lane references unknown warehouse: {lane['warehouse']}"
        if lane["market"] not in network["markets"]:
            return f"network lane references unknown market: {lane['market']}"
        error = validate_number(lane["last_mile_cost"], "network lane last_mile_cost", minimum=0)
        if error:
            return error
        error = validate_number(lane["delivery_days"], "network lane delivery_days", minimum=0, exclusive_minimum=True)
        if error:
            return error
        lane_pairs.add((lane["warehouse"], lane["market"]))

    expected_lane_pairs = {
        (warehouse, market)
        for warehouse in network["warehouses"]
        for market in network["markets"]
    }
    missing_pairs = expected_lane_pairs - lane_pairs
    if missing_pairs:
        warehouse, market = sorted(missing_pairs)[0]
        return f"network.lanes is missing warehouse-market pair: {warehouse} -> {market}"

    replenishment = data["replenishment"]
    for key in ("weeks", "lanes", "demand", "initial_inventory", "target_ending_inventory", "holding_cost", "stockout_penalty"):
        if key not in replenishment:
            return f"replenishment is missing required key: {key}"
    if not isinstance(replenishment["weeks"], list) or not replenishment["weeks"]:
        return "replenishment.weeks must be a non-empty list"
    if not isinstance(replenishment["lanes"], dict) or not replenishment["lanes"]:
        return "replenishment.lanes must be a non-empty object"
    for week in replenishment["weeks"]:
        if week not in replenishment["demand"]:
            return f"replenishment.demand is missing week: {week}"
        error = validate_number(replenishment["demand"][week], f"replenishment.demand.{week}", minimum=0)
        if error:
            return error
    for lane, values in replenishment["lanes"].items():
        for field in ("lead_time_weeks", "unit_cost", "weekly_capacity"):
            if field not in values:
                return f"replenishment.lanes.{lane}.{field} is required"
            minimum = 0
            exclusive = field == "lead_time_weeks"
            error = validate_number(values[field], f"replenishment.lanes.{lane}.{field}", minimum=minimum, exclusive_minimum=exclusive)
            if error:
                return error
    for field in ("initial_inventory", "target_ending_inventory", "holding_cost", "stockout_penalty"):
        error = validate_number(replenishment[field], f"replenishment.{field}", minimum=0)
        if error:
            return error

    service_level = data["service_level"]
    for key in ("markets", "services"):
        if key not in service_level or not isinstance(service_level[key], dict) or not service_level[key]:
            return f"service_level.{key} must be a non-empty object"
    for market, values in service_level["markets"].items():
        for field in ("demand", "max_avg_delivery_days"):
            if field not in values:
                return f"service_level.markets.{market}.{field} is required"
        error = validate_number(values["demand"], f"service_level.markets.{market}.demand", minimum=0)
        if error:
            return error
        error = validate_number(values["max_avg_delivery_days"], f"service_level.markets.{market}.max_avg_delivery_days", minimum=0, exclusive_minimum=True)
        if error:
            return error
    for service, values in service_level["services"].items():
        for field in ("capacity", "fixed_cost", "unit_cost_by_market", "delivery_days_by_market"):
            if field not in values:
                return f"service_level.services.{service}.{field} is required"
        for field in ("capacity", "fixed_cost"):
            error = validate_number(values[field], f"service_level.services.{service}.{field}", minimum=0)
            if error:
                return error
        for market in service_level["markets"]:
            if market not in values["unit_cost_by_market"]:
                return f"service_level.services.{service}.unit_cost_by_market is missing market: {market}"
            if market not in values["delivery_days_by_market"]:
                return f"service_level.services.{service}.delivery_days_by_market is missing market: {market}"
            error = validate_number(values["unit_cost_by_market"][market], f"service_level.services.{service}.unit_cost_by_market.{market}", minimum=0)
            if error:
                return error
            error = validate_number(values["delivery_days_by_market"][market], f"service_level.services.{service}.delivery_days_by_market.{market}", minimum=0, exclusive_minimum=True)
            if error:
                return error

    return None


def build_data_quality_metrics(data):
    network = data["network"]
    replenishment = data["replenishment"]
    service_level = data["service_level"]
    order_line_count = upstream_order_line_count(data)
    total_market_demand = sum(market["demand"] for market in network["markets"].values())
    total_warehouse_capacity = sum(warehouse["capacity"] for warehouse in network["warehouses"].values())
    total_replenishment_demand = sum(replenishment["demand"].values())
    total_air_capacity = replenishment["lanes"]["air"]["weekly_capacity"] * len(replenishment["weeks"])
    total_service_capacity = sum(service["capacity"] for service in service_level["services"].values())
    return {
        "markets": len(network["markets"]),
        "order_lines": order_line_count,
        "warehouses": len(network["warehouses"]),
        "lanes": len(network["lanes"]),
        "total_market_demand": total_market_demand,
        "total_warehouse_capacity": total_warehouse_capacity,
        "capacity_buffer": total_warehouse_capacity - total_market_demand,
        "replenishment_weeks": len(replenishment["weeks"]),
        "total_replenishment_demand": total_replenishment_demand,
        "total_air_capacity": total_air_capacity,
        "service_capacity": total_service_capacity,
    }


def build_data_quality_checks(data, validation_error):
    source_label = "StarRocks 上游库表" if starrocks_upstream_enabled() else "本地 JSON 样例数据"
    if validation_error:
        return [
            {
                "name": "数据结构",
                "level": "warn",
                "detail": validation_error,
                "action": f"先修复 {source_label} 的结构或必填字段，再运行模型。",
            }
        ]

    metrics = build_data_quality_metrics(data)
    network = data["network"]
    replenishment = data["replenishment"]
    service_level = data["service_level"]
    checks = [
        {
            "name": "数据结构",
            "level": "pass",
            "detail": f"{source_label} 已通过必填字段、类型和线路覆盖校验。",
            "action": "可以继续生成 CPLEX 模型入参。",
        },
        {
            "name": "仓网容量",
            "level": "pass" if metrics["capacity_buffer"] >= 0 else "warn",
            "detail": f"仓库总容量 {format_number(metrics['total_warehouse_capacity'])}，市场总需求 {format_number(metrics['total_market_demand'])}，缓冲 {format_number(metrics['capacity_buffer'])}。",
            "action": "缓冲为负时，建议启用扩容模式或提高缺口罚分。",
        },
    ]
    order_line_count = upstream_order_line_count(data)
    sample_count = len(data.get("orders", []))
    sample_note = f"页面抽样展示 {format_number(sample_count)} 条，" if sample_count and sample_count != order_line_count else ""
    checks.append(
        {
            "name": "订单明细规模",
            "level": "pass" if order_line_count >= 1000 else "warn",
            "detail": f"当前接入 {format_number(order_line_count)} 条上游订单明细，{sample_note}模型前会聚合到市场需求和服务需求。",
            "action": "用于观察数据接入吞吐；求解层继续使用聚合入参，避免把交易明细直接推给 MIP。",
        }
    )

    blocked_markets = []
    for market, market_data in network["markets"].items():
        allowed = [
            lane for lane in network["lanes"]
            if lane["market"] == market and lane["delivery_days"] <= market_data["max_delivery_days"]
        ]
        if not allowed:
            blocked_markets.append(market)
    checks.append(
        {
            "name": "SLA 可用线路",
            "level": "pass" if not blocked_markets else "warn",
            "detail": "所有市场至少有一条满足 SLA 的线路。" if not blocked_markets else f"{', '.join(blocked_markets)} 没有满足当前 SLA 的仓库线路。",
            "action": "如有市场无可用线路，可放宽 SLA、调整仓库布局或进入软容量/扩容方案。",
        }
    )

    replenishment_capacity = sum(
        values.get("weekly_capacity", 0) * len(replenishment["weeks"])
        for values in replenishment["lanes"].values()
    )
    checks.append(
        {
            "name": "补货供给能力",
            "level": "pass" if replenishment_capacity >= metrics["total_replenishment_demand"] else "warn",
            "detail": f"计划期运输能力 {format_number(replenishment_capacity)}，预测需求 {format_number(metrics['total_replenishment_demand'])}。",
            "action": "能力不足时，可提升空运容量、缩短海运提前期或接受缺货罚分。",
        }
    )

    service_demand = sum(market["demand"] for market in service_level["markets"].values())
    checks.append(
        {
            "name": "服务商容量",
            "level": "pass" if metrics["service_capacity"] >= service_demand else "warn",
            "detail": f"服务商总能力 {format_number(metrics['service_capacity'])}，服务订单需求 {format_number(service_demand)}。",
            "action": "能力不足时，需引入服务商或降低市场承诺量。",
        }
    )
    return checks


def build_platform_scale_snapshot():
    started_at = perf_counter()
    upstream_data = load_upstream_data()
    loaded_at = perf_counter()
    validation_error = validate_upstream_data(upstream_data)
    validated_at = perf_counter()
    if validation_error:
        return {
            "status": "attention",
            "message": validation_error,
            "timings_ms": {
                "load_upstream": round((loaded_at - started_at) * 1000, 2),
                "validate_upstream": round((validated_at - loaded_at) * 1000, 2),
                "build_model_inputs": 0,
                "total_prepare": round((validated_at - started_at) * 1000, 2),
            },
            "throughput": {
                "order_lines": upstream_order_line_count(upstream_data),
                "source_tables": count_source_tables(upstream_data) if isinstance(upstream_data, dict) else 0,
                "model_input_blocks": 0,
                "estimated_variables": 0,
                "estimated_constraints": 0,
            },
            "models": [],
        }
    baseline_config = dict(playbooks()["baseline"])
    model_inputs = build_model_inputs(baseline_config)
    input_ready_at = perf_counter()
    models = build_model_scale_rows(model_inputs, baseline_config)
    total_variables = sum(model["variables_estimate"] for model in models)
    total_constraints = sum(model["constraints_estimate"] for model in models)
    return {
        "status": "attention" if validation_error else "ok",
        "message": validation_error or "上游数据已完成读取、结构校验和 CPLEX 入参生成。",
        "timings_ms": {
            "load_upstream": round((loaded_at - started_at) * 1000, 2),
            "validate_upstream": round((validated_at - loaded_at) * 1000, 2),
            "build_model_inputs": round((input_ready_at - validated_at) * 1000, 2),
            "total_prepare": round((input_ready_at - started_at) * 1000, 2),
        },
        "throughput": {
            "order_lines": upstream_order_line_count(upstream_data),
            "source_tables": count_source_tables(upstream_data),
            "model_input_blocks": len([key for key in model_inputs if key != "lineage"]),
            "estimated_variables": total_variables,
            "estimated_constraints": total_constraints,
        },
        "models": models,
    }


def count_source_tables(upstream_data):
    network = upstream_data.get("network", {})
    replenishment = upstream_data.get("replenishment", {})
    service_level = upstream_data.get("service_level", {})
    return sum(
        bool(value)
        for value in (
            upstream_data.get("orders"),
            network.get("warehouses"),
            network.get("markets"),
            network.get("lanes"),
            replenishment.get("demand"),
            replenishment.get("lanes"),
            service_level.get("markets"),
            service_level.get("services"),
        )
    )


def build_model_scale_rows(model_inputs, config):
    network = model_inputs["network"]
    replenishment = model_inputs["replenishment"]
    service_level = model_inputs["service_level"]
    staffing = model_inputs["staffing"]

    warehouse_count = len(network["sets"]["warehouses"])
    market_count = len(network["sets"]["markets"])
    lane_count = len(network["lane_costs_and_sla"])
    network_extra_variables = 0
    if config.get("network_mode") in {"soft_capacity", "capacity_expansion"}:
        network_extra_variables += market_count
    if config.get("network_mode") == "capacity_expansion":
        network_extra_variables += len(network.get("expansion_options", {}))
    network_constraints = market_count + warehouse_count + sum(
        1 for lane in network["lane_costs_and_sla"] if not lane["allowed_by_sla"]
    )

    week_count = len(replenishment["sets"]["weeks"])
    replenishment_lane_count = len(replenishment["sets"]["lanes"])
    service_count = len(service_level["sets"]["services"])
    service_market_count = len(service_level["sets"]["markets"])
    employee_count = len(staffing["sets"]["employees"])
    day_count = len(staffing["sets"]["days"])
    staffing_soft = bool(staffing["parameters"].get("soft_constraints"))

    return [
        {
            "id": "network",
            "name": "仓网选址与履约",
            "source_rows": lane_count,
            "input_sets": f"{warehouse_count} 仓 / {market_count} 市场 / {lane_count} 线路",
            "variables_estimate": warehouse_count + lane_count + network_extra_variables,
            "constraints_estimate": network_constraints,
            "prepare_note": "订单明细先聚合为市场需求，再进入仓网 MIP。",
        },
        {
            "id": "replenishment",
            "name": "跨境补货",
            "source_rows": week_count * replenishment_lane_count,
            "input_sets": f"{week_count} 周 / {replenishment_lane_count} 渠道",
            "variables_estimate": week_count * replenishment_lane_count + week_count * 2,
            "constraints_estimate": week_count * 2 + replenishment_lane_count,
            "prepare_note": "按周生成运输、库存和缺货变量。",
        },
        {
            "id": "service_level",
            "name": "服务水平组合",
            "source_rows": service_count * service_market_count,
            "input_sets": f"{service_count} 服务商 / {service_market_count} 市场",
            "variables_estimate": service_count + service_count * service_market_count,
            "constraints_estimate": service_market_count * 2 + service_count,
            "prepare_note": "服务商能力和市场 SLA 生成分配矩阵。",
        },
        {
            "id": "staffing",
            "name": "人员排班",
            "source_rows": employee_count * day_count,
            "input_sets": f"{employee_count} 员工 / {day_count} 天",
            "variables_estimate": employee_count * day_count + (day_count if staffing_soft else 0),
            "constraints_estimate": day_count * 2 + employee_count,
            "prepare_note": "员工可用性、技能和每日需求生成排班约束。",
        },
    ]


@app.get("/")
def index():
    return render_template("platform_app.html", active_layer="upstream")


@app.get("/upstream")
def upstream_page():
    return render_template("platform_app.html", active_layer="upstream")


@app.get("/config")
def config_page():
    return render_template("platform_app.html", active_layer="config")


@app.get("/inputs")
def inputs_page():
    return render_template("platform_app.html", active_layer="inputs")


@app.get("/results")
def results_page():
    return render_template("platform_app.html", active_layer="results")


@app.get("/lineage")
def lineage_page():
    return render_template("platform_app.html", active_layer="lineage")


@app.get("/constraints")
def constraints_page():
    return render_template("platform_app.html", active_layer="constraints")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "cplex-optimization-platform-poc"})


@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.get("/api/platform/overview")
def overview():
    data = load_platform_data()
    return jsonify(
        {
            "status": "ok",
            "playbooks": [
                {
                    "id": key,
                    "name": value["name"],
                    "description": value["description"],
                    "defaults": public_config(value),
                }
                for key, value in data["playbooks"].items()
            ],
            "assets": data["assets"],
            "capabilities": data["capabilities"],
            "data_source": platform_data_source_label(),
            "roles": [
                {"id": key, "name": ROLE_LABELS[key], "permissions": sorted(value)}
                for key, value in ROLE_PERMISSIONS.items()
            ],
        }
    )


@app.get("/api/platform/data")
def get_platform_data():
    return jsonify(
        {
            "status": "ok",
            "data_source": platform_data_source_label(),
            "data": load_platform_data(),
        }
    )


@app.put("/api/platform/data")
def update_platform_data():
    permission_error = require_permission("edit_config")
    if permission_error:
        return permission_error
    payload = request.get_json(silent=True) or {}
    data = payload.get("data")
    previous_data = load_platform_data() if starrocks_upstream_enabled() else None
    validation_error = validate_platform_data(data)
    if validation_error:
        return jsonify({"status": "error", "message": validation_error}), 400

    save_platform_data(data, previous_data)
    return jsonify(
        {
            "status": "ok",
            "message": "Data layer saved",
            "data_source": platform_data_source_label(),
        }
    )


@app.get("/api/platform/config-audit")
def get_config_audit():
    limit = request.args.get("limit", default=10, type=int)
    limit = max(1, min(limit, 50))
    return jsonify(
        {
            "status": "ok",
            "data_source": platform_data_source_label(),
            "rows": load_config_audit(limit),
        }
    )


@app.get("/api/platform/upstream-data")
def get_upstream_data():
    data = load_upstream_data()
    return jsonify(
        {
            "status": "ok",
            "data_source": upstream_data_source_label(data),
            "source_summary": {
                "source_tables": len(STARROCKS_SOURCE_TABLES) if starrocks_upstream_enabled() else count_source_tables(data),
                "business_groups": count_source_tables(data),
                "order_lines": upstream_order_line_count(data),
                "sample_rows": len(data.get("orders", [])),
            },
            "data": data,
        }
    )


@app.get("/api/platform/data-quality")
def get_data_quality():
    upstream_data = load_upstream_data()
    validation_error = validate_upstream_data(upstream_data)
    checks = build_data_quality_checks(upstream_data, validation_error)
    return jsonify(
        {
            "status": "ok",
            "overall": "pass" if all(check["level"] == "pass" for check in checks) else "attention",
            "checks": checks,
            "metrics": build_data_quality_metrics(upstream_data),
        }
    )


@app.get("/api/platform/source-status")
def get_source_status():
    return jsonify(build_upstream_source_status())


@app.get("/api/platform/scale-snapshot")
def get_scale_snapshot():
    return jsonify(build_platform_scale_snapshot())


@app.get("/api/platform/lineage")
def get_lineage():
    upstream_source = upstream_data_source_label()
    lineage_paths = starrocks_lineage_paths() if starrocks_upstream_enabled() else json_lineage_paths()
    return jsonify(
        {
            "status": "ok",
            "nodes": [
                {
                    "id": "upstream",
                    "name": "上游数据接入层",
                    "source": upstream_source,
                    "owner": "OMS / WMS / TMS / HR",
                    "description": "保存业务原始数据，例如订单需求、仓库能力、线路成本、补货预测和服务商能力。",
                },
                {
                    "id": "config",
                    "name": "场景配置层",
                    "source": platform_data_source_label(),
                    "owner": "运营 / 计划",
                    "description": "保存管理假设，例如需求倍率、空运能力、缺口罚分、SLA 放宽和模型模式。",
                },
                {
                    "id": "inputs",
                    "name": "模型入参层",
                    "source": "runtime payload",
                    "owner": "优化服务",
                    "description": "把上游数据和场景参数转换为 CPLEX 可以求解的 sets、parameters 和约束数据。",
                },
                {
                    "id": "results",
                    "name": "求解结果层",
                    "source": "CPLEX solve result",
                    "owner": "优化服务 / 管理驾驶舱",
                    "description": "输出成本、缺口、启用仓库、补货计划、排班结果、风险提示和审批建议。",
                },
            ],
            "transforms": [
                {
                    "from": "upstream.network.markets",
                    "config": "demand_multiplier, sla_extra_days",
                    "to": "model_inputs.network.markets",
                    "rule": "市场需求按倍率放大；严格 SLA 模型会放宽最大配送天数。",
                },
                {
                    "from": "upstream.network.lanes",
                    "config": "network_mode",
                    "to": "model_inputs.network.lane_costs_and_sla",
                    "rule": "把线路成本和配送天数展开成仓库-市场矩阵，并标记是否满足 SLA。",
                },
                {
                    "from": "upstream.replenishment",
                    "config": "air_capacity, ocean_lead_time, unfulfilled_penalty",
                    "to": "model_inputs.replenishment",
                    "rule": "用场景参数覆盖空运容量、海运提前期和缺货惩罚。",
                },
                {
                    "from": "upstream.service_level",
                    "config": "none",
                    "to": "model_inputs.service_level",
                    "rule": "服务商成本、容量和时效直接进入服务水平组合模型。",
                },
                {
                    "from": "upstream.staffing",
                    "config": "staff_peak, soft_staffing",
                    "to": "model_inputs.staffing",
                    "rule": "上游排班基础数据提供员工、可用性、技能和每日需求；旺季场景提高周末人力需求，软约束场景允许缺口并计入罚分。",
                },
            ],
            "model_flows": [
                {
                    "model": "仓网选址与履约模型",
                    "upstream": lineage_paths["network"],
                    "config": ["demand_multiplier", "sla_extra_days", "network_mode", "unfulfilled_penalty"],
                    "transform": "build_network_model_input",
                    "input": ["sets.warehouses", "sets.markets", "parameters", "lane_costs_and_sla"],
                    "solver": "solve_platform_network_case",
                    "result": ["open_warehouses", "shipments", "unfulfilled", "cost"],
                },
                {
                    "model": "跨境补货模型",
                    "upstream": lineage_paths["replenishment"],
                    "config": ["air_capacity", "ocean_lead_time", "unfulfilled_penalty"],
                    "transform": "build_replenishment_model_input",
                    "input": ["sets.weeks", "sets.lanes", "parameters", "demand"],
                    "solver": "solve_replenishment_plan",
                    "result": ["shipping_plan", "inventory", "stockouts", "cost"],
                },
                {
                    "model": "服务水平组合模型",
                    "upstream": lineage_paths["service_level"],
                    "config": ["直接使用上游服务能力"],
                    "transform": "build_service_level_model_input",
                    "input": ["sets.markets", "sets.services", "markets", "services"],
                    "solver": "solve_platform_service_level_case",
                    "result": ["service_mix", "capacity_usage", "sla_risk", "cost"],
                },
                {
                    "model": "门店/仓内排班模型",
                    "upstream": lineage_paths["staffing"],
                    "config": ["staff_peak", "soft_staffing"],
                    "transform": "build_staffing_model_input",
                    "input": ["sets.employees", "sets.days", "required_staff", "availability", "skills"],
                    "solver": "solve_staffing_case",
                    "result": ["assignments", "shortages", "total_cost", "coverage"],
                },
            ],
            "field_map": [
                {"business_field": "订单明细", "upstream_path": lineage_paths["orders"], "model_input_path": "network.markets.*.demand", "used_by": "上游吞吐统计与需求聚合说明"},
                {"business_field": "市场需求", "upstream_path": lineage_paths["network_markets"], "model_input_path": "network.markets.*.demand", "used_by": "仓网需求约束"},
                {"business_field": "仓库容量", "upstream_path": lineage_paths["network_warehouses"], "model_input_path": "network.warehouses.*.capacity", "used_by": "仓库容量约束"},
                {"business_field": "线路成本", "upstream_path": lineage_paths["network_lanes"], "model_input_path": "network.lane_costs_and_sla.*.last_mile_cost", "used_by": "仓网目标函数"},
                {"business_field": "配送天数", "upstream_path": lineage_paths["network_lanes"], "model_input_path": "network.lane_costs_and_sla.*.allowed_by_sla", "used_by": "SLA 禁用线路约束"},
                {"business_field": "补货预测", "upstream_path": lineage_paths["replenishment_demand"], "model_input_path": "replenishment.demand.*", "used_by": "库存平衡约束"},
                {"business_field": "运输渠道能力", "upstream_path": lineage_paths["replenishment_lanes"], "model_input_path": "replenishment.lanes.*", "used_by": "补货容量约束和成本目标"},
                {"business_field": "服务商能力", "upstream_path": lineage_paths["service_providers"], "model_input_path": "service_level.services.*.capacity", "used_by": "服务商容量约束"},
                {"business_field": "排班需求", "upstream_path": lineage_paths["staffing_required"], "model_input_path": "staffing.required_staff", "used_by": "每日人力覆盖约束"},
            ],
        }
    )


def json_lineage_paths():
    return {
        "orders": "orders[*]",
        "network": ["network.warehouses", "network.markets", "network.lanes", "network.expansion_options"],
        "network_markets": "network.markets.*.demand",
        "network_warehouses": "network.warehouses.*.capacity",
        "network_lanes": "network.lanes.*",
        "replenishment": ["replenishment.weeks", "replenishment.demand", "replenishment.lanes", "replenishment.initial_inventory"],
        "replenishment_demand": "replenishment.demand.*",
        "replenishment_lanes": "replenishment.lanes.*",
        "service_level": ["service_level.markets", "service_level.services"],
        "service_providers": "service_level.services.*.capacity",
        "staffing": ["staffing.employees", "staffing.availability", "staffing.skills", "staffing.required_staff"],
        "staffing_required": "staffing.required_staff",
    }


def starrocks_lineage_paths():
    config = starrocks_config()
    prefix = f"{config['database']}."
    return {
        "orders": prefix + config["table"],
        "network": [
            prefix + "upstream_network_warehouses",
            prefix + "upstream_network_markets",
            prefix + "upstream_network_lanes",
            prefix + "upstream_network_expansion_options",
        ],
        "network_markets": prefix + "upstream_network_markets.demand",
        "network_warehouses": prefix + "upstream_network_warehouses.capacity",
        "network_lanes": prefix + "upstream_network_lanes",
        "replenishment": [
            prefix + "upstream_replenishment_weeks",
            prefix + "upstream_replenishment_demand",
            prefix + "upstream_replenishment_lanes",
            prefix + "upstream_replenishment_parameters",
        ],
        "replenishment_demand": prefix + "upstream_replenishment_demand.demand",
        "replenishment_lanes": prefix + "upstream_replenishment_lanes",
        "service_level": [
            prefix + "upstream_service_markets",
            prefix + "upstream_service_providers",
            prefix + "upstream_service_provider_market_terms",
        ],
        "service_providers": prefix + "upstream_service_providers.capacity",
        "staffing": [
            "embedded_upstream.staffing.employees",
            "embedded_upstream.staffing.availability",
            "embedded_upstream.staffing.skills",
            "embedded_upstream.staffing.required_staff",
        ],
        "staffing_required": "embedded_upstream.staffing.required_staff",
    }


@app.get("/api/platform/model-explanations")
def get_model_explanations():
    return jsonify(
        {
            "status": "ok",
            "models": [
                {
                    "id": "network",
                    "name": "仓网选址与履约模型",
                    "business_question": "决定开哪些仓、每个市场由哪个仓履约，以及在高峰或扩容场景下如何处理不可满足需求。",
                    "variables": [
                        {"name": "open_warehouse[w]", "type": "0/1 变量", "meaning": "仓库 w 是否启用"},
                        {"name": "ship[w,m]", "type": "连续变量", "meaning": "仓库 w 发往市场 m 的订单量"},
                        {"name": "unfulfilled[m]", "type": "连续变量", "meaning": "软容量或扩容模式下市场 m 的未履约订单量"},
                        {"name": "extra_capacity[w]", "type": "连续变量", "meaning": "扩容模式下仓库 w 购买的临时产能"},
                    ],
                    "objective": "最小化固定开仓成本、处理成本、末端配送成本、临时扩容成本和未履约罚分。",
                    "constraints": [
                        {"name": "需求覆盖", "formula": "sum_w ship[w,m] + unfulfilled[m] = demand[m]", "meaning": "每个市场的需求要么被仓库履约，要么显式计入缺口"},
                        {"name": "仓库容量", "formula": "sum_m ship[w,m] <= capacity[w] * open_warehouse[w] + extra_capacity[w]", "meaning": "未启用仓不能发货，启用仓不能超过基础或临时容量"},
                        {"name": "SLA 可用线路", "formula": "ship[w,m] = 0 if delivery_days[w,m] > max_delivery_days[m]", "meaning": "超过承诺时效的线路不能被 CPLEX 选择"},
                    ],
                    "outputs": ["opened_warehouses", "fulfillment_plan", "capacity_plan", "total_unfulfilled", "total_cost"],
                },
                {
                    "id": "replenishment",
                    "name": "跨境补货模型",
                    "business_question": "决定每周走空运还是海运补货，平衡运输成本、持有成本和缺货风险。",
                    "variables": [
                        {"name": "orders[lane,week]", "type": "连续变量", "meaning": "某周通过某运输渠道发出的补货量"},
                        {"name": "inventory[week]", "type": "连续变量", "meaning": "每周末剩余库存"},
                        {"name": "stockout[week]", "type": "连续变量", "meaning": "每周未满足需求"},
                    ],
                    "objective": "最小化运输成本、库存持有成本和缺货罚分。",
                    "constraints": [
                        {"name": "库存平衡", "formula": "inventory[t] = inventory[t-1] + arrivals[t] - demand[t] + stockout[t]", "meaning": "把采购到货、需求消耗、库存和缺货连成时间序列"},
                        {"name": "渠道容量", "formula": "orders[lane,t] <= weekly_capacity[lane]", "meaning": "空运等渠道不能超过每周可用能力"},
                        {"name": "期末库存", "formula": "inventory[last_week] >= target_ending_inventory", "meaning": "避免方案只顾眼前缺货、不保留安全库存"},
                    ],
                    "outputs": ["orders", "inventory_projection", "total_stockout", "transport_cost", "total_cost"],
                },
                {
                    "id": "service_level",
                    "name": "服务水平组合模型",
                    "business_question": "决定使用哪些服务商，以及各市场订单如何分配，满足平均时效承诺并控制成本。",
                    "variables": [
                        {"name": "use_service[s]", "type": "0/1 变量", "meaning": "服务商 s 是否启用"},
                        {"name": "orders[s,m]", "type": "连续变量", "meaning": "服务商 s 承接市场 m 的订单量"},
                    ],
                    "objective": "最小化服务商固定成本和订单履约变动成本。",
                    "constraints": [
                        {"name": "市场需求", "formula": "sum_s orders[s,m] = demand[m]", "meaning": "每个市场的订单必须全部分配给服务商"},
                        {"name": "平均时效", "formula": "sum_s delivery_days[s,m] * orders[s,m] <= max_avg_days[m] * demand[m]", "meaning": "用加权平均时效控制市场 SLA"},
                        {"name": "服务商容量", "formula": "sum_m orders[s,m] <= capacity[s] * use_service[s]", "meaning": "未启用服务商不能接单，启用后也不能超过能力"},
                    ],
                    "outputs": ["used_services", "allocation", "average_days", "total_cost"],
                },
                {
                    "id": "staffing",
                    "name": "门店/仓内排班模型",
                    "business_question": "决定员工每天是否上班，满足每日人力和技能覆盖，同时控制班次成本和偏好损失。",
                    "variables": [
                        {"name": "work[e,d]", "type": "0/1 变量", "meaning": "员工 e 在日期 d 是否排班"},
                        {"name": "shortage[d]", "type": "连续变量", "meaning": "软约束模式下日期 d 的人力缺口"},
                    ],
                    "objective": "最小化排班成本、偏好违背罚分和软约束缺口罚分。",
                    "constraints": [
                        {"name": "每日覆盖", "formula": "sum_e work[e,d] + shortage[d] >= required_staff[d]", "meaning": "每天至少满足需求，软约束模式允许显式缺口"},
                        {"name": "员工可用性", "formula": "work[e,d] <= availability[e,d]", "meaning": "员工不可用的日期不能被排班"},
                        {"name": "技能覆盖", "formula": "sum_e skill[e,k] * work[e,d] >= skill_requirement[d,k]", "meaning": "关键岗位或技能每天都要有人覆盖"},
                        {"name": "最大班次数", "formula": "sum_d work[e,d] <= max_shifts_per_employee", "meaning": "控制员工工作负荷，避免排班不可执行"},
                    ],
                    "outputs": ["assignments", "total_shortage", "coverage", "total_cost"],
                },
            ],
        }
    )


@app.put("/api/platform/upstream-data")
def update_upstream_data():
    permission_error = require_permission("edit_upstream")
    if permission_error:
        return permission_error
    payload = request.get_json(silent=True) or {}
    data = payload.get("data")
    if starrocks_upstream_enabled() and isinstance(data, dict):
        validation_data = dict(data)
        if not validation_data.get("orders"):
            validation_data["orders"] = load_upstream_data().get("orders", [])
        validation_error = validate_upstream_data(validation_data)
        if validation_error:
            return jsonify({"status": "error", "message": validation_error}), 400
        save_starrocks_upstream_data(data)
        return jsonify(
            {
                "status": "ok",
                "message": "StarRocks 上游基础表已保存",
                "data_source": upstream_data_source_label(data),
            }
        )

    validation_error = validate_upstream_data(data)
    if validation_error:
        return jsonify({"status": "error", "message": validation_error}), 400
    save_upstream_data(data)
    return jsonify(
        {
            "status": "ok",
            "message": "Upstream data saved",
            "data_source": str(UPSTREAM_DATA_PATH.relative_to(Path(__file__).resolve().parent.parent)),
        }
    )


@app.get("/api/platform/compare")
def compare_platform_cases():
    rows = []
    for playbook_id in playbooks():
        result = run_case(playbook_id, {})
        rows.append(
            {
                "playbook": playbook_id,
                "name": result["playbook_name"],
                "config": result["config"],
                "summary": result["summary"],
                "difference": result["difference"],
                "recommendation": result["summary"]["actions"][0] if result["summary"]["actions"] else "-",
            }
        )
    return jsonify(
        {
            "status": "ok",
            "rows": rows,
            "matrix": build_compare_matrix(rows),
            "recommendation": build_scenario_recommendation(rows),
        }
    )


def build_compare_matrix(rows):
    metric_rows = [
        ("定位", lambda row: row["config"].get("description", "-")),
        ("需求倍率", lambda row: row["config"].get("demand_multiplier", "-")),
        ("空运周容量", lambda row: row["config"].get("air_capacity", "-")),
        ("SLA 放宽天数", lambda row: row["config"].get("sla_extra_days", "-")),
        ("仓网模式", lambda row: row["config"].get("network_mode", "-")),
        ("综合成本", lambda row: row["summary"].get("total_cost", 0)),
        ("总缺口", lambda row: row["summary"].get("total_shortage", 0)),
        ("审批分层", lambda row: row["summary"].get("approval_level", "-")),
        ("相对基准", lambda row: row["difference"].get("headline", "-")),
        ("推荐动作", lambda row: row.get("recommendation", "-")),
    ]
    return {
        "columns": [{"playbook": row["playbook"], "name": row["name"]} for row in rows],
        "rows": [
            {
                "metric": metric,
                "values": [reader(row) for row in rows],
            }
            for metric, reader in metric_rows
        ],
    }


def build_scenario_recommendation(rows):
    ranked = sorted(
        rows,
        key=lambda row: (
            row["summary"].get("total_shortage", 0),
            row["summary"].get("approval_level") == "管理层审批",
            row["summary"].get("total_cost", 0),
        ),
    )
    winner = ranked[0]
    alternatives = [row for row in ranked[1:]]
    reason = (
        f"{winner['name']} 在当前三方案中总缺口最低，为 {winner['summary']['total_shortage']:g}，"
        f"综合成本为 {winner['summary']['total_cost']:g}，审批分层为 {winner['summary']['approval_level']}。"
    )
    if alternatives:
        next_best = alternatives[0]
        reason += (
            f" 相比次优方案 {next_best['name']}，缺口差异为 "
            f"{winner['summary']['total_shortage'] - next_best['summary']['total_shortage']:g}，"
            f"成本差异为 {winner['summary']['total_cost'] - next_best['summary']['total_cost']:g}。"
        )
    return {
        "playbook": winner["playbook"],
        "name": winner["name"],
        "reason": reason,
        "recommended_action": winner["recommendation"],
        "criteria": "优先最小化总缺口；缺口相同时避免管理层审批；再比较综合成本。",
    }


@app.post("/api/platform/run")
def run_platform_case():
    permission_error = require_permission("run_model")
    if permission_error:
        return permission_error
    payload = request.get_json(silent=True) or {}
    playbook_id = payload.get("playbook", "baseline")
    if playbook_id not in playbooks():
        return jsonify({"status": "error", "message": f"Unknown playbook: {playbook_id}"}), 400

    result = run_case(playbook_id, payload.get("overrides") or {})
    if payload.get("save_history", True):
        result["run_record"] = append_run_history(result)
    return jsonify(result)


@app.get("/api/platform/run-history")
def get_run_history():
    limit = request.args.get("limit", default=20, type=int)
    limit = max(1, min(limit, 100))
    return jsonify(
        {
            "status": "ok",
            "data_source": platform_run_history_source_label(),
            "rows": load_run_history(limit),
        }
    )


@app.post("/api/platform/approval")
def update_run_approval():
    payload = request.get_json(silent=True) or {}
    run_id = str(payload.get("run_id") or "").strip()
    action = str(payload.get("action") or "").strip()
    actor = str(payload.get("actor") or "demo.cio").strip()
    comment = str(payload.get("comment") or "").strip()
    if action not in APPROVAL_ACTIONS:
        return jsonify({"status": "error", "message": f"Unknown approval action: {action}"}), 400
    permission = "submit_approval" if action == "submit" else "decide_approval"
    permission_error = require_permission(permission)
    if permission_error:
        return permission_error
    if not run_id:
        return jsonify({"status": "error", "message": "run_id is required"}), 400
    event, error = append_approval_event(run_id, action, actor, comment)
    if error:
        return jsonify({"status": "error", "message": error}), 400
    return jsonify(
        {
            "status": "ok",
            "message": "审批状态已更新",
            "approval": event,
            "data_source": platform_run_history_source_label(),
        }
    )


@app.post("/api/platform/export-report")
def export_platform_report():
    permission_error = require_permission("export_report")
    if permission_error:
        return permission_error
    payload = request.get_json(silent=True) or {}
    playbook_id = payload.get("playbook", "baseline")
    if playbook_id not in playbooks():
        return jsonify({"status": "error", "message": f"Unknown playbook: {playbook_id}"}), 400

    result = run_case(playbook_id, payload.get("overrides") or {})
    report = export_demo_report(result)
    return jsonify(
        {
            "status": "ok",
            "message": "Demo report exported",
            "report": report,
            "summary": result["summary"],
            "difference": result["difference"],
        }
    )


def run_case(playbook_id, overrides):
    config = dict(playbooks()[playbook_id])
    config.update(clean_overrides(overrides))
    model_inputs = build_model_inputs(config)

    network = solve_platform_network_case(model_inputs["network"], config)
    replenishment = solve_platform_replenishment_case(model_inputs["replenishment"])
    service_mix = solve_platform_service_level_case(model_inputs["service_level"])
    staffing = solve_staffing_case(config)

    summary = build_management_summary(network, replenishment, service_mix, staffing, config)
    difference = build_difference_explanation(
        playbook_id,
        config,
        summary,
        network,
        replenishment,
        service_mix,
        staffing,
    )

    return {
        "status": "ok",
        "playbook": playbook_id,
        "playbook_name": config["name"],
        "config": public_config(config),
        "model_inputs": model_inputs,
        "summary": summary,
        "difference": difference,
        "network": network,
        "replenishment": replenishment,
        "service_mix": service_mix,
        "staffing": staffing,
    }


def clean_overrides(overrides):
    allowed = {
        "demand_multiplier": float,
        "sla_extra_days": int,
        "air_capacity": int,
        "ocean_lead_time": int,
        "unfulfilled_penalty": float,
    }
    cleaned = {}
    for key, caster in allowed.items():
        if key in overrides and overrides[key] not in ("", None):
            cleaned[key] = caster(overrides[key])
    return cleaned


def public_config(config):
    keys = [
        "description",
        "demand_multiplier",
        "sla_extra_days",
        "air_capacity",
        "ocean_lead_time",
        "unfulfilled_penalty",
        "network_mode",
        "staff_peak",
        "soft_staffing",
    ]
    return {key: config[key] for key in keys if key in config}


def build_model_inputs(config):
    upstream_data = load_upstream_data()
    network_input = build_network_model_input(config, upstream_data["network"])
    replenishment_input = build_replenishment_model_input(config, upstream_data["replenishment"])
    service_input = build_service_level_model_input(upstream_data["service_level"])
    staffing_input = build_staffing_model_input(config)
    return {
        "lineage": {
            "upstream_source": upstream_data_source_label(upstream_data),
            "scenario_config_source": platform_data_source_label(),
            "transform": "上游原始数据 + 当前方案参数 -> CPLEX 模型运行入参",
        },
        "network": network_input,
        "replenishment": replenishment_input,
        "service_level": service_input,
        "staffing": staffing_input,
    }


def build_network_model_input(config, upstream_network):
    warehouses = upstream_network["warehouses"]
    markets = {
        market: dict(values)
        for market, values in upstream_network["markets"].items()
    }
    lane_lookup = {
        (lane["warehouse"], lane["market"]): lane
        for lane in upstream_network["lanes"]
    }
    effective_sla_extra_days = int(config["sla_extra_days"]) if config.get("network_mode") == "strict" else 0
    for market in markets:
        markets[market]["base_demand"] = markets[market]["demand"]
        markets[market]["demand"] = round(markets[market]["demand"] * float(config["demand_multiplier"]))
        markets[market]["max_delivery_days"] += effective_sla_extra_days

    input_data = {
        "model_name": network_model_name(config),
        "sets": {
            "warehouses": list(warehouses),
            "markets": list(markets),
        },
        "parameters": {
            "demand_multiplier": float(config["demand_multiplier"]),
            "sla_extra_days": effective_sla_extra_days,
            "unfulfilled_penalty": float(config["unfulfilled_penalty"]),
        },
        "warehouses": warehouses,
        "markets": markets,
        "lane_costs_and_sla": [
            {
                "warehouse": warehouse,
                "market": market,
                "last_mile_cost": lane_lookup[warehouse, market]["last_mile_cost"],
                "delivery_days": lane_lookup[warehouse, market]["delivery_days"],
                "allowed_by_sla": lane_lookup[warehouse, market]["delivery_days"] <= markets[market]["max_delivery_days"],
            }
            for warehouse in warehouses
            for market in markets
        ],
    }
    if config.get("network_mode") == "capacity_expansion":
        input_data["expansion_options"] = upstream_network["expansion_options"]
    return input_data


def network_model_name(config):
    mode = config.get("network_mode")
    if mode == "soft_capacity":
        return "cross_border_ecommerce_soft_capacity"
    if mode == "capacity_expansion":
        return "cross_border_ecommerce_capacity_expansion"
    return "cross_border_ecommerce_network"


def build_replenishment_model_input(config, upstream_replenishment):
    data = {
        key: dict(value) if isinstance(value, dict) else list(value) if isinstance(value, list) else value
        for key, value in upstream_replenishment.items()
    }
    data["lanes"] = {
        lane: dict(values)
        for lane, values in upstream_replenishment["lanes"].items()
    }
    data["lanes"]["air"]["weekly_capacity"] = int(config["air_capacity"])
    data["lanes"]["ocean"]["lead_time_weeks"] = int(config["ocean_lead_time"])
    data["stockout_penalty"] = float(config["unfulfilled_penalty"])
    return {
        "model_name": "cross_border_ecommerce_replenishment",
        "sets": {
            "weeks": data["weeks"],
            "lanes": list(data["lanes"]),
        },
        "parameters": {
            "initial_inventory": data["initial_inventory"],
            "target_ending_inventory": data["target_ending_inventory"],
            "holding_cost": data["holding_cost"],
            "stockout_penalty": data["stockout_penalty"],
        },
        "demand": data["demand"],
        "lanes": data["lanes"],
    }


def build_service_level_model_input(upstream_service_level):
    return {
        "model_name": "cross_border_ecommerce_service_level",
        "sets": {
            "markets": list(upstream_service_level["markets"]),
            "services": list(upstream_service_level["services"]),
        },
        "markets": upstream_service_level["markets"],
        "services": upstream_service_level["services"],
    }


def build_staffing_model_input(config):
    problem = default_problem()
    if config.get("staff_peak"):
        problem["required_staff"]["Fri"] = 4
        problem["required_staff"]["Sat"] = 4
        problem["required_staff"]["Sun"] = 3
        problem["max_shifts_per_employee"] = 3
    return {
        "model_name": "staff_scheduling_soft" if config.get("soft_staffing") else "staff_scheduling",
        "sets": {
            "employees": problem["employees"],
            "days": problem["days"],
        },
        "parameters": {
            "max_shifts_per_employee": problem["max_shifts_per_employee"],
            "cost_weight": 0.002,
            "preference_weight": 0.04,
            "soft_constraints": bool(config.get("soft_staffing")),
        },
        "required_staff": problem["required_staff"],
        "availability": problem["availability"],
        "skills": problem["skills"],
        "skill_requirements": problem["skill_requirements"],
        "shift_costs": problem["shift_costs"],
        "preferences": problem["preferences"],
    }


def solve_staffing_case(config):
    problem = default_problem()
    if config.get("staff_peak"):
        problem["required_staff"]["Fri"] = 4
        problem["required_staff"]["Sat"] = 4
        problem["required_staff"]["Sun"] = 3
        problem["max_shifts_per_employee"] = 3

    solver = solve_staff_scheduling_soft if config.get("soft_staffing") else solve_staff_scheduling
    return solver(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        skills=problem["skills"],
        skill_requirements=problem["skill_requirements"],
        shift_costs=problem["shift_costs"],
        cost_weight=0.002,
        preferences=problem["preferences"],
        preference_weight=0.04,
        log_output=False,
    )


def solve_platform_network_case(input_data, config):
    warehouses = input_data["warehouses"]
    markets = input_data["markets"]
    lane_costs = {
        (lane["warehouse"], lane["market"]): lane
        for lane in input_data["lane_costs_and_sla"]
    }
    network_mode = config.get("network_mode", "strict")
    allow_unfulfilled = network_mode in {"soft_capacity", "capacity_expansion"}
    expansion_options = input_data.get("expansion_options", {})
    unfulfilled_penalty = float(input_data["parameters"]["unfulfilled_penalty"])

    model = Model(name=input_data["model_name"])
    open_warehouse = {
        warehouse: model.binary_var(name=f"open_{warehouse}")
        for warehouse in warehouses
    }
    ship = {
        (warehouse, market): model.continuous_var(name=f"ship_{warehouse}_to_{market}", lb=0)
        for warehouse in warehouses
        for market in markets
    }
    unfulfilled = {
        market: model.continuous_var(name=f"unfulfilled_{market}", lb=0)
        for market in markets
    } if allow_unfulfilled else {}
    extra_capacity = {
        warehouse: model.continuous_var(
            name=f"extra_capacity_{warehouse}",
            lb=0,
            ub=expansion_options[warehouse]["max_extra_capacity"],
        )
        for warehouse in expansion_options
    } if network_mode == "capacity_expansion" else {}

    fixed_cost = model.sum(
        warehouses[warehouse]["fixed_cost"] * open_warehouse[warehouse]
        for warehouse in warehouses
    )
    variable_cost = model.sum(
        (
            warehouses[warehouse]["handling_cost"]
            + lane_costs[warehouse, market]["last_mile_cost"]
        )
        * ship[warehouse, market]
        for warehouse in warehouses
        for market in markets
    )
    unfulfilled_cost = model.sum(
        unfulfilled_penalty * unfulfilled[market]
        for market in markets
    ) if allow_unfulfilled else 0
    expansion_cost = model.sum(
        expansion_options[warehouse]["unit_cost"] * extra_capacity[warehouse]
        for warehouse in extra_capacity
    ) if extra_capacity else 0

    model.minimize(fixed_cost + variable_cost + unfulfilled_cost + expansion_cost)

    for market, data in markets.items():
        demand_expr = model.sum(ship[warehouse, market] for warehouse in warehouses)
        if allow_unfulfilled:
            demand_expr += unfulfilled[market]
        model.add_constraint(demand_expr == data["demand"], ctname=f"demand_{market}")

    for warehouse, data in warehouses.items():
        capacity_expr = data["capacity"] * open_warehouse[warehouse]
        if warehouse in extra_capacity:
            capacity_expr += extra_capacity[warehouse]
            model.add_constraint(
                extra_capacity[warehouse]
                <= expansion_options[warehouse]["max_extra_capacity"] * open_warehouse[warehouse],
                ctname=f"expand_only_if_open_{warehouse}",
            )
        model.add_constraint(
            model.sum(ship[warehouse, market] for market in markets) <= capacity_expr,
            ctname=f"capacity_{warehouse}",
        )

    for (warehouse, market), lane in lane_costs.items():
        if not lane["allowed_by_sla"]:
            model.add_constraint(ship[warehouse, market] == 0, ctname=f"sla_block_{warehouse}_to_{market}")

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible", "message": "No feasible network found from upstream data."}

    opened_warehouses = []
    capacity_plan = []
    for warehouse in warehouses:
        if open_warehouse[warehouse].solution_value > 0.5:
            used_capacity = sum(ship[warehouse, market].solution_value for market in markets)
            opened_warehouses.append(warehouse)
            row = {
                "warehouse": warehouse,
                "used_capacity": used_capacity,
                "base_capacity": warehouses[warehouse]["capacity"],
            }
            if warehouse in extra_capacity:
                row["extra_capacity"] = extra_capacity[warehouse].solution_value
            capacity_plan.append(row)

    fulfillment_plan = {}
    total_unfulfilled = 0
    for market in markets:
        if allow_unfulfilled:
            total_unfulfilled += unfulfilled[market].solution_value
        fulfillment_plan[market] = []
        for warehouse in warehouses:
            amount = ship[warehouse, market].solution_value
            if amount > 1e-6:
                fulfillment_plan[market].append(
                    {
                        "warehouse": warehouse,
                        "orders": amount,
                        "unit_cost": warehouses[warehouse]["handling_cost"] + lane_costs[warehouse, market]["last_mile_cost"],
                        "delivery_days": lane_costs[warehouse, market]["delivery_days"],
                    }
                )

    return {
        "status": "optimal",
        "opened_warehouses": opened_warehouses,
        "capacity_plan": capacity_plan,
        "fulfillment_plan": fulfillment_plan,
        "fixed_cost": fixed_cost.solution_value,
        "variable_cost": variable_cost.solution_value,
        "expansion_cost": expansion_cost.solution_value if extra_capacity else 0,
        "unfulfilled_cost": unfulfilled_cost.solution_value if allow_unfulfilled else 0,
        "total_unfulfilled": total_unfulfilled,
        "total_cost": solution.objective_value,
    }


def solve_platform_replenishment_case(input_data):
    data = {
        "weeks": input_data["sets"]["weeks"],
        "lanes": input_data["lanes"],
        "demand": input_data["demand"],
        "initial_inventory": input_data["parameters"]["initial_inventory"],
        "target_ending_inventory": input_data["parameters"]["target_ending_inventory"],
        "holding_cost": input_data["parameters"]["holding_cost"],
        "stockout_penalty": input_data["parameters"]["stockout_penalty"],
    }
    result = solve_replenishment_plan(data=data, log_output=False)
    if result["status"] != "optimal":
        return result

    orders = []
    for (lane, week), amount in result["orders"].items():
        if amount > 1e-6:
            orders.append({"week": week, "lane": lane, "units": round(amount, 2)})
    return {
        "status": "optimal",
        "orders": orders,
        "inventory_projection": result["inventory_projection"],
        "total_stockout": round(result["total_stockout"], 2),
        "transport_cost": round(result["transport_cost"], 2),
        "holding_cost": round(result["holding_cost"], 2),
        "stockout_penalty": round(result["stockout_penalty"], 2),
        "total_cost": round(result["total_cost"], 2),
    }


def solve_platform_service_level_case(input_data):
    markets = input_data["markets"]
    services = input_data["services"]
    model = Model(name=input_data["model_name"])

    use_service = {
        service: model.binary_var(name=f"use_{service}")
        for service in services
    }
    orders = {
        (service, market): model.continuous_var(name=f"orders_{service}_to_{market}", lb=0)
        for service in services
        for market in markets
    }

    fixed_cost = model.sum(
        services[service]["fixed_cost"] * use_service[service]
        for service in services
    )
    variable_cost = model.sum(
        services[service]["unit_cost_by_market"][market] * orders[service, market]
        for service in services
        for market in markets
    )
    model.minimize(fixed_cost + variable_cost)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(orders[service, market] for service in services) == data["demand"],
            ctname=f"demand_{market}",
        )
        model.add_constraint(
            model.sum(
                services[service]["delivery_days_by_market"][market] * orders[service, market]
                for service in services
            )
            <= data["max_avg_delivery_days"] * data["demand"],
            ctname=f"avg_delivery_sla_{market}",
        )

    for service, data in services.items():
        model.add_constraint(
            model.sum(orders[service, market] for market in markets)
            <= data["capacity"] * use_service[service],
            ctname=f"capacity_if_used_{service}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible", "message": "No feasible service-level mix found from upstream data."}

    used_services = []
    allocation = {}
    for service in services:
        used_orders = sum(orders[service, market].solution_value for market in markets)
        if used_orders > 1e-6:
            used_services.append({"service": service, "orders": used_orders})

    for market, data in markets.items():
        weighted_days = 0
        allocation[market] = []
        for service in services:
            amount = orders[service, market].solution_value
            if amount > 1e-6:
                days = services[service]["delivery_days_by_market"][market]
                weighted_days += days * amount
                allocation[market].append(
                    {
                        "service": service,
                        "orders": amount,
                        "unit_cost": services[service]["unit_cost_by_market"][market],
                        "delivery_days": days,
                    }
                )
        allocation[f"{market}_average_days"] = weighted_days / data["demand"]

    return {
        "status": "optimal",
        "used_services": used_services,
        "allocation": allocation,
        "fixed_cost": fixed_cost.solution_value,
        "variable_cost": variable_cost.solution_value,
        "total_cost": solution.objective_value,
    }


def build_management_summary(network, replenishment, service_mix, staffing, config):
    network_cost = float(network.get("total_cost") or 0)
    replenishment_cost = float(replenishment.get("total_cost") or 0)
    staffing_cost = float(staffing.get("total_cost") or 0)
    total_shortage = float(network.get("total_unfulfilled") or 0) + float(
        replenishment.get("total_stockout") or 0
    ) + float(staffing.get("total_shortage") or 0)

    actions = []
    if network.get("opened_warehouses"):
        actions.append(f"启用仓库：{', '.join(network['opened_warehouses'])}")
    if replenishment.get("orders"):
        top_orders = replenishment["orders"][:3]
        actions.append(
            "补货计划：" + ", ".join(
                f"{row['week']}周{row['lane']} {row['units']:g}件" for row in top_orders
            )
        )
    if staffing.get("total_shortage", 0):
        actions.append(f"客服/运营排班缺口：{staffing['total_shortage']:g} 人班")
    else:
        actions.append("排班覆盖：满足每日人力需求")

    risks = []
    if network.get("total_unfulfilled", 0):
        risks.append(f"仓网未履约 {network['total_unfulfilled']:g} 单")
    if replenishment.get("total_stockout", 0):
        risks.append(f"补货缺货 {replenishment['total_stockout']:g} 件")
    if staffing.get("total_shortage", 0):
        risks.append(f"排班缺口 {staffing['total_shortage']:g} 人班")
    if not risks:
        risks.append("核心约束均满足")

    approval_level = "自动执行"
    if network_cost + replenishment_cost > 15000 or total_shortage > 0:
        approval_level = "人工确认"
    if config["demand_multiplier"] >= 1.25 and total_shortage > 100:
        approval_level = "管理层审批"

    return {
        "total_cost": round(network_cost + replenishment_cost + staffing_cost, 2),
        "network_cost": round(network_cost, 2),
        "replenishment_cost": round(replenishment_cost, 2),
        "staffing_cost": round(staffing_cost, 2),
        "total_shortage": round(total_shortage, 2),
        "service_cost": round(float(service_mix.get("total_cost") or 0), 2),
        "approval_level": approval_level,
        "actions": actions,
        "risks": risks,
        "execution_plan": build_execution_plan(network, replenishment, staffing, approval_level),
        "decision_note": decision_note(approval_level, total_shortage, network_cost + replenishment_cost),
        "message": "这不是单个模型 demo，而是把仓网、补货、服务和排班接到同一个决策入口。",
    }


def build_execution_plan(network, replenishment, staffing, approval_level):
    plan = []
    if network.get("opened_warehouses"):
        plan.append(
            {
                "owner": "仓网运营",
                "priority": "P0" if network.get("total_unfulfilled", 0) else "P1",
                "trigger": "仓网模型已输出开仓与履约分配",
                "action": f"确认 {', '.join(network['opened_warehouses'])} 的启用窗口、预算和容量排期。",
            }
        )
    if replenishment.get("orders"):
        first_orders = replenishment["orders"][:2]
        plan.append(
            {
                "owner": "补货计划",
                "priority": "P0" if replenishment.get("total_stockout", 0) else "P1",
                "trigger": "补货模型已输出运输渠道与周计划",
                "action": "锁定" + "、".join(f"{row['week']}周{row['lane']} {row['units']:g}件" for row in first_orders) + "等首批补货动作。",
            }
        )
    if staffing.get("total_shortage", 0):
        plan.append(
            {
                "owner": "客服/仓内排班",
                "priority": "P0",
                "trigger": f"排班模型发现 {staffing['total_shortage']:g} 人班缺口",
                "action": "安排临时人力、加班池或降低低优先级服务承诺。",
            }
        )
    else:
        plan.append(
            {
                "owner": "客服/仓内排班",
                "priority": "P2",
                "trigger": "排班模型覆盖所有每日需求",
                "action": "按当前排班执行，并保留异常订单应急班次。",
            }
        )
    plan.append(
        {
            "owner": "业务负责人",
            "priority": "P0" if approval_level == "管理层审批" else "P1",
            "trigger": f"审批分层为 {approval_level}",
            "action": "确认是否按建议动作执行，并在运行记录中保留本次决策口径。",
        }
    )
    return plan


def build_difference_explanation(playbook_id, config, summary, network, replenishment, service_mix, staffing):
    baseline_summary = None
    baseline_network = None
    baseline_replenishment = None
    baseline_service_mix = None
    baseline_staffing = None
    if playbook_id != "baseline" or has_baseline_override(config):
        baseline_config = dict(playbooks()["baseline"])
        baseline_inputs = build_model_inputs(baseline_config)
        baseline_network = solve_platform_network_case(baseline_inputs["network"], baseline_config)
        baseline_replenishment = solve_platform_replenishment_case(baseline_inputs["replenishment"])
        baseline_service_mix = solve_platform_service_level_case(baseline_inputs["service_level"])
        baseline_staffing = solve_staffing_case(baseline_config)
        baseline_summary = build_management_summary(
            baseline_network,
            baseline_replenishment,
            baseline_service_mix,
            baseline_staffing,
            baseline_config,
        )

    if not baseline_summary:
        return {
            "baseline": "基准运营方案",
            "headline": "当前是基准方案，用作其他方案的对比锚点。",
            "metrics": [
                {"label": "综合成本", "current": summary["total_cost"], "baseline": summary["total_cost"], "delta": 0, "direction": "flat"},
                {"label": "总缺口", "current": summary["total_shortage"], "baseline": summary["total_shortage"], "delta": 0, "direction": "flat"},
            ],
            "drivers": ["基准方案使用当前需求、当前空运能力和严格仓网 SLA。"],
            "management_readout": "建议先用这个方案确认数据口径，再切换旺季或稳健方案观察增量影响。",
        }

    cost_delta = round(summary["total_cost"] - baseline_summary["total_cost"], 2)
    shortage_delta = round(summary["total_shortage"] - baseline_summary["total_shortage"], 2)
    service_delta = round(summary["service_cost"] - baseline_summary["service_cost"], 2)
    opened_delta = len(network.get("opened_warehouses") or []) - len(baseline_network.get("opened_warehouses") or [])
    order_delta = len(replenishment.get("orders") or []) - len(baseline_replenishment.get("orders") or [])
    staffing_shortage_delta = round(
        float(staffing.get("total_shortage") or 0) - float(baseline_staffing.get("total_shortage") or 0),
        2,
    )

    drivers = []
    if config["demand_multiplier"] != playbooks()["baseline"]["demand_multiplier"]:
        drivers.append(f"需求倍率从 1.0 调整到 {config['demand_multiplier']:g}，仓网、补货和服务模型的需求约束同步抬升。")
    if config["air_capacity"] != playbooks()["baseline"]["air_capacity"]:
        drivers.append(f"空运周容量从 {playbooks()['baseline']['air_capacity']} 调整到 {config['air_capacity']}，直接影响补货模型的运输容量约束。")
    if config["network_mode"] != playbooks()["baseline"]["network_mode"]:
        drivers.append(f"仓网模式从 strict 切换到 {config['network_mode']}，允许用缺口或扩容吸收不可满足需求。")
    if config["sla_extra_days"] != playbooks()["baseline"]["sla_extra_days"]:
        drivers.append(f"SLA 放宽 {config['sla_extra_days']} 天，仓网模型会重新判断可用线路。")
    if config.get("staff_peak"):
        drivers.append("旺季排班开关已打开，周五到周日的人力需求提高。")
    if config.get("soft_staffing"):
        drivers.append("排班启用软约束，缺口会进入结果解释而不是直接让模型不可行。")
    if not drivers:
        drivers.append("当前参数与基准接近，差异主要来自上游数据调整。")

    headline = "相对基准方案"
    if cost_delta > 0:
        headline += f"成本增加 {cost_delta:g}"
    elif cost_delta < 0:
        headline += f"成本降低 {abs(cost_delta):g}"
    else:
        headline += "成本持平"
    headline += "，"
    if shortage_delta > 0:
        headline += f"缺口增加 {shortage_delta:g}。"
    elif shortage_delta < 0:
        headline += f"缺口减少 {abs(shortage_delta):g}。"
    else:
        headline += "缺口持平。"

    return {
        "baseline": "基准运营方案",
        "headline": headline,
        "metrics": [
            {"label": "综合成本", "current": summary["total_cost"], "baseline": baseline_summary["total_cost"], "delta": cost_delta, "direction": delta_direction(cost_delta, lower_is_better=True)},
            {"label": "总缺口", "current": summary["total_shortage"], "baseline": baseline_summary["total_shortage"], "delta": shortage_delta, "direction": delta_direction(shortage_delta, lower_is_better=True)},
            {"label": "服务组合成本", "current": summary["service_cost"], "baseline": baseline_summary["service_cost"], "delta": service_delta, "direction": delta_direction(service_delta, lower_is_better=True)},
            {"label": "启用仓库数", "current": len(network.get("opened_warehouses") or []), "baseline": len(baseline_network.get("opened_warehouses") or []), "delta": opened_delta, "direction": delta_direction(opened_delta, lower_is_better=False)},
            {"label": "补货订单数", "current": len(replenishment.get("orders") or []), "baseline": len(baseline_replenishment.get("orders") or []), "delta": order_delta, "direction": "info"},
            {"label": "排班缺口", "current": float(staffing.get("total_shortage") or 0), "baseline": float(baseline_staffing.get("total_shortage") or 0), "delta": staffing_shortage_delta, "direction": delta_direction(staffing_shortage_delta, lower_is_better=True)},
        ],
        "drivers": drivers,
        "management_readout": management_readout(cost_delta, shortage_delta, summary["approval_level"], baseline_summary["approval_level"]),
    }


def has_baseline_override(config):
    baseline = playbooks()["baseline"]
    return any(config.get(key) != baseline.get(key) for key in baseline)


def delta_direction(delta, lower_is_better):
    if abs(delta) < 1e-9:
        return "flat"
    if lower_is_better:
        return "good" if delta < 0 else "bad"
    return "info"


def management_readout(cost_delta, shortage_delta, approval_level, baseline_approval_level):
    if shortage_delta > 0:
        return f"核心取舍是用更高风险承接需求变化，审批从 {baseline_approval_level} 变为 {approval_level}，需要确认是否接受缺口。"
    if cost_delta > 0:
        return f"核心取舍是用额外成本换服务稳定性，审批从 {baseline_approval_level} 变为 {approval_level}，适合讨论预算边界。"
    if cost_delta < 0:
        return f"该方案相对基准降低成本且没有增加缺口，可优先进入执行评审。"
    return f"该方案与基准的核心 KPI 接近，审批分层为 {approval_level}，重点看执行动作是否更容易落地。"


def decision_note(approval_level, total_shortage, operating_cost):
    if approval_level == "管理层审批":
        return f"缺口 {total_shortage:g} 且经营成本 {operating_cost:g}，适合让管理层决定是否加预算或放宽服务承诺。"
    if approval_level == "人工确认":
        return f"存在成本或缺口影响，建议运营负责人确认后执行。"
    return "缺口和金额都在低风险范围内，可以进入自动执行队列。"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5053, debug=False, use_reloader=False)
