import json
import tempfile
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
                "summary": result["summary"],
            }
        )
    return jsonify({"status": "ok", "rows": rows})


@app.post("/api/platform/run")
def run_platform_case():
    payload = request.get_json(silent=True) or {}
    playbook_id = payload.get("playbook", "baseline")
    if playbook_id not in playbooks():
        return jsonify({"status": "error", "message": f"Unknown playbook: {playbook_id}"}), 400

    return jsonify(run_case(playbook_id, payload.get("overrides") or {}))


def run_case(playbook_id, overrides):
    config = dict(playbooks()[playbook_id])
    config.update(clean_overrides(overrides))
    model_inputs = build_model_inputs(config)

    network = solve_platform_network_case(model_inputs["network"], config)
    replenishment = solve_platform_replenishment_case(model_inputs["replenishment"])
    service_mix = solve_platform_service_level_case(model_inputs["service_level"])
    staffing = solve_staffing_case(config)

    summary = build_management_summary(network, replenishment, service_mix, staffing, config)

    return {
        "status": "ok",
        "playbook": playbook_id,
        "playbook_name": config["name"],
        "config": public_config(config),
        "model_inputs": model_inputs,
        "summary": summary,
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


def decision_note(approval_level, total_shortage, operating_cost):
    if approval_level == "管理层审批":
        return f"缺口 {total_shortage:g} 且经营成本 {operating_cost:g}，适合让管理层决定是否加预算或放宽服务承诺。"
    if approval_level == "人工确认":
        return f"存在成本或缺口影响，建议运营负责人确认后执行。"
    return "缺口和金额都在低风险范围内，可以进入自动执行队列。"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5053, debug=False, use_reloader=False)
