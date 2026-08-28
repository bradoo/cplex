import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
NETWORK_MODES = {"strict", "soft_capacity", "capacity_expansion"}


def load_platform_data():
    with DATA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def load_upstream_data():
    with UPSTREAM_DATA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def playbooks():
    return load_platform_data()["playbooks"]


def save_platform_data(data):
    save_json_file(DATA_PATH, data)


def save_upstream_data(data):
    save_json_file(UPSTREAM_DATA_PATH, data)


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
    RUN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUN_HISTORY_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_run_history(limit=20):
    if not RUN_HISTORY_PATH.exists():
        return []
    with RUN_HISTORY_PATH.open(encoding="utf-8") as file:
        rows = [json.loads(line) for line in file if line.strip()]
    return list(reversed(rows[-limit:]))


def build_run_history_record(result):
    summary = result["summary"]
    difference = result.get("difference", {})
    return {
        "run_id": uuid.uuid4().hex[:8],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "playbook": result["playbook"],
        "playbook_name": result["playbook_name"],
        "config": result["config"],
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
    lines.extend(["", "## 6. 风险提示", ""])
    lines.extend(f"- {risk}" for risk in summary["risks"])
    lines.extend(
        [
            "",
            "## 7. 模型结果摘要",
            "",
            "| 模型 | 状态 | 摘要 |",
            "| --- | --- | --- |",
            f"| 仓网选址与履约 | {markdown_cell(result['network']['status'])} | 开仓 {len(result['network'].get('opened_warehouses') or [])} 个，缺口 {format_number(result['network'].get('total_unfulfilled') or 0)} |",
            f"| 跨境补货 | {markdown_cell(result['replenishment']['status'])} | 缺货 {format_number(result['replenishment'].get('total_stockout') or 0)}，订单 {len(result['replenishment'].get('orders') or [])} 笔 |",
            f"| 服务水平组合 | {markdown_cell(result['service_mix']['status'])} | 成本 {format_number(result['service_mix'].get('total_cost') or 0)} |",
            f"| 人员排班 | {markdown_cell(result['staffing']['status'])} | 模式 {markdown_cell(result['staffing'].get('mode') or '-')}，缺口 {format_number(result['staffing'].get('total_shortage') or 0)} |",
            "",
            "## 8. 数据链路",
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
            if field not in values or not isinstance(values[field], (int, float)):
                return f"network.warehouses.{warehouse}.{field} must be numeric"

    for market, values in network["markets"].items():
        for field in ("demand", "max_delivery_days"):
            if field not in values or not isinstance(values[field], (int, float)):
                return f"network.markets.{market}.{field} must be numeric"

    lane_pairs = set()
    for lane in network["lanes"]:
        for field in ("warehouse", "market", "last_mile_cost", "delivery_days"):
            if field not in lane:
                return f"network lane is missing field: {field}"
        if lane["warehouse"] not in network["warehouses"]:
            return f"network lane references unknown warehouse: {lane['warehouse']}"
        if lane["market"] not in network["markets"]:
            return f"network lane references unknown market: {lane['market']}"
        if not isinstance(lane["last_mile_cost"], (int, float)):
            return "network lane last_mile_cost must be numeric"
        if not isinstance(lane["delivery_days"], (int, float)):
            return "network lane delivery_days must be numeric"
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

    service_level = data["service_level"]
    for key in ("markets", "services"):
        if key not in service_level or not isinstance(service_level[key], dict) or not service_level[key]:
            return f"service_level.{key} must be a non-empty object"

    return None


def build_data_quality_metrics(data):
    network = data["network"]
    replenishment = data["replenishment"]
    service_level = data["service_level"]
    total_market_demand = sum(market["demand"] for market in network["markets"].values())
    total_warehouse_capacity = sum(warehouse["capacity"] for warehouse in network["warehouses"].values())
    total_replenishment_demand = sum(replenishment["demand"].values())
    total_air_capacity = replenishment["lanes"]["air"]["weekly_capacity"] * len(replenishment["weeks"])
    total_service_capacity = sum(service["capacity"] for service in service_level["services"].values())
    return {
        "markets": len(network["markets"]),
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
    if validation_error:
        return [
            {
                "name": "数据结构",
                "level": "warn",
                "detail": validation_error,
                "action": "先修复 JSON 结构或必填字段，再运行模型。",
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
            "detail": "上游 JSON 已通过必填字段、类型和线路覆盖校验。",
            "action": "可以继续生成 CPLEX 模型入参。",
        },
        {
            "name": "仓网容量",
            "level": "pass" if metrics["capacity_buffer"] >= 0 else "warn",
            "detail": f"仓库总容量 {metrics['total_warehouse_capacity']:g}，市场总需求 {metrics['total_market_demand']:g}，缓冲 {metrics['capacity_buffer']:g}。",
            "action": "缓冲为负时，建议启用扩容模式或提高缺口罚分。",
        },
    ]

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
            "detail": f"计划期运输能力 {replenishment_capacity:g}，预测需求 {metrics['total_replenishment_demand']:g}。",
            "action": "能力不足时，可提升空运容量、缩短海运提前期或接受缺货罚分。",
        }
    )

    service_demand = sum(market["demand"] for market in service_level["markets"].values())
    checks.append(
        {
            "name": "服务商容量",
            "level": "pass" if metrics["service_capacity"] >= service_demand else "warn",
            "detail": f"服务商总能力 {metrics['service_capacity']:g}，服务订单需求 {service_demand:g}。",
            "action": "能力不足时，需引入服务商或降低市场承诺量。",
        }
    )
    return checks


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
            "data_source": str(DATA_PATH.relative_to(Path(__file__).resolve().parent.parent)),
        }
    )


@app.get("/api/platform/data")
def get_platform_data():
    return jsonify(
        {
            "status": "ok",
            "data_source": str(DATA_PATH.relative_to(Path(__file__).resolve().parent.parent)),
            "data": load_platform_data(),
        }
    )


@app.put("/api/platform/data")
def update_platform_data():
    payload = request.get_json(silent=True) or {}
    data = payload.get("data")
    validation_error = validate_platform_data(data)
    if validation_error:
        return jsonify({"status": "error", "message": validation_error}), 400

    save_platform_data(data)
    return jsonify(
        {
            "status": "ok",
            "message": "Data layer saved",
            "data_source": str(DATA_PATH.relative_to(Path(__file__).resolve().parent.parent)),
        }
    )


@app.get("/api/platform/upstream-data")
def get_upstream_data():
    return jsonify(
        {
            "status": "ok",
            "data_source": str(UPSTREAM_DATA_PATH.relative_to(Path(__file__).resolve().parent.parent)),
            "data": load_upstream_data(),
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


@app.get("/api/platform/lineage")
def get_lineage():
    return jsonify(
        {
            "status": "ok",
            "nodes": [
                {
                    "id": "upstream",
                    "name": "上游数据接入层",
                    "source": str(UPSTREAM_DATA_PATH.relative_to(Path(__file__).resolve().parent.parent)),
                    "owner": "OMS / WMS / TMS / HR",
                    "description": "保存业务原始数据，例如订单需求、仓库能力、线路成本、补货预测和服务商能力。",
                },
                {
                    "id": "config",
                    "name": "场景配置层",
                    "source": str(DATA_PATH.relative_to(Path(__file__).resolve().parent.parent)),
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
                    "from": "default staffing data",
                    "config": "staff_peak, soft_staffing",
                    "to": "model_inputs.staffing",
                    "rule": "旺季场景提高周末人力需求；软约束场景允许缺口并计入罚分。",
                },
            ],
            "model_flows": [
                {
                    "model": "仓网选址与履约模型",
                    "upstream": ["network.warehouses", "network.markets", "network.lanes", "network.expansion_options"],
                    "config": ["demand_multiplier", "sla_extra_days", "network_mode", "unfulfilled_penalty"],
                    "transform": "build_network_model_input",
                    "input": ["sets.warehouses", "sets.markets", "parameters", "lane_costs_and_sla"],
                    "solver": "solve_platform_network_case",
                    "result": ["open_warehouses", "shipments", "unfulfilled", "cost"],
                },
                {
                    "model": "跨境补货模型",
                    "upstream": ["replenishment.weeks", "replenishment.demand", "replenishment.lanes", "replenishment.initial_inventory"],
                    "config": ["air_capacity", "ocean_lead_time", "unfulfilled_penalty"],
                    "transform": "build_replenishment_model_input",
                    "input": ["sets.weeks", "sets.lanes", "parameters", "demand"],
                    "solver": "solve_replenishment_plan",
                    "result": ["shipping_plan", "inventory", "stockouts", "cost"],
                },
                {
                    "model": "服务水平组合模型",
                    "upstream": ["service_level.markets", "service_level.services"],
                    "config": ["直接使用上游服务能力"],
                    "transform": "build_service_level_model_input",
                    "input": ["sets.markets", "sets.services", "markets", "services"],
                    "solver": "solve_platform_service_level_case",
                    "result": ["service_mix", "capacity_usage", "sla_risk", "cost"],
                },
                {
                    "model": "门店/仓内排班模型",
                    "upstream": ["default_problem.employees", "default_problem.availability", "default_problem.skills", "default_problem.required_staff"],
                    "config": ["staff_peak", "soft_staffing"],
                    "transform": "build_staffing_model_input",
                    "input": ["sets.employees", "sets.days", "required_staff", "availability", "skills"],
                    "solver": "solve_staffing_case",
                    "result": ["assignments", "shortages", "total_cost", "coverage"],
                },
            ],
            "field_map": [
                {"business_field": "市场需求", "upstream_path": "network.markets.*.demand", "model_input_path": "network.markets.*.demand", "used_by": "仓网需求约束"},
                {"business_field": "仓库容量", "upstream_path": "network.warehouses.*.capacity", "model_input_path": "network.warehouses.*.capacity", "used_by": "仓库容量约束"},
                {"business_field": "线路成本", "upstream_path": "network.lanes.*.last_mile_cost", "model_input_path": "network.lane_costs_and_sla.*.last_mile_cost", "used_by": "仓网目标函数"},
                {"business_field": "配送天数", "upstream_path": "network.lanes.*.delivery_days", "model_input_path": "network.lane_costs_and_sla.*.allowed_by_sla", "used_by": "SLA 禁用线路约束"},
                {"business_field": "补货预测", "upstream_path": "replenishment.demand.*", "model_input_path": "replenishment.demand.*", "used_by": "库存平衡约束"},
                {"business_field": "运输渠道能力", "upstream_path": "replenishment.lanes.*", "model_input_path": "replenishment.lanes.*", "used_by": "补货容量约束和成本目标"},
                {"business_field": "服务商能力", "upstream_path": "service_level.services.*.capacity", "model_input_path": "service_level.services.*.capacity", "used_by": "服务商容量约束"},
                {"business_field": "排班需求", "upstream_path": "staffing scenario defaults", "model_input_path": "staffing.required_staff", "used_by": "每日人力覆盖约束"},
            ],
        }
    )


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
    payload = request.get_json(silent=True) or {}
    data = payload.get("data")
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
    return jsonify({"status": "ok", "rows": rows, "matrix": build_compare_matrix(rows)})


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


@app.post("/api/platform/run")
def run_platform_case():
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
            "data_source": str(RUN_HISTORY_PATH.relative_to(Path(__file__).resolve().parent.parent)),
            "rows": load_run_history(limit),
        }
    )


@app.post("/api/platform/export-report")
def export_platform_report():
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
            "upstream_source": str(UPSTREAM_DATA_PATH.relative_to(Path(__file__).resolve().parent.parent)),
            "scenario_config_source": str(DATA_PATH.relative_to(Path(__file__).resolve().parent.parent)),
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
        "decision_note": decision_note(approval_level, total_shortage, network_cost + replenishment_cost),
        "message": "这不是单个模型 demo，而是把仓网、补货、服务和排班接到同一个决策入口。",
    }


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
