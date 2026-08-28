import json
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from cross_border_ecommerce_capacity_expansion_demo import solve_capacity_expansion_network
from cross_border_ecommerce_app import (
    solve_network_case,
    solve_replenishment_case,
    solve_service_level_case,
)
from cross_border_ecommerce_soft_capacity_demo import solve_soft_capacity_network
from scheduling_solver import (
    default_problem,
    solve_staff_scheduling,
    solve_staff_scheduling_soft,
)


app = Flask(__name__)
DATA_PATH = Path(__file__).resolve().parent / "data" / "platform_poc_data.json"
NETWORK_MODES = {"strict", "soft_capacity", "capacity_expansion"}


def load_platform_data():
    with DATA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def playbooks():
    return load_platform_data()["playbooks"]


def save_platform_data(data):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=DATA_PATH.parent,
        delete=False,
    ) as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
        temp_path = Path(file.name)
    temp_path.replace(DATA_PATH)


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


@app.get("/")
def index():
    return render_template("platform_app.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "cplex-optimization-platform-poc"})


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

    network = solve_platform_network_case(config)
    replenishment = solve_replenishment_case(
        int(config["air_capacity"]),
        int(config["ocean_lead_time"]),
        float(config["unfulfilled_penalty"]),
    )
    service_mix = solve_service_level_case()
    staffing = solve_staffing_case(config)

    summary = build_management_summary(network, replenishment, service_mix, staffing, config)

    return {
        "status": "ok",
        "playbook": playbook_id,
        "playbook_name": config["name"],
        "config": public_config(config),
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


def solve_platform_network_case(config):
    demand_multiplier = float(config["demand_multiplier"])
    unfulfilled_penalty = float(config["unfulfilled_penalty"])
    network_mode = config.get("network_mode", "strict")

    if network_mode == "soft_capacity":
        return solve_soft_capacity_network(
            demand_multiplier=demand_multiplier,
            unfulfilled_penalty=unfulfilled_penalty,
            log_output=False,
            print_output=False,
        )
    if network_mode == "capacity_expansion":
        return solve_capacity_expansion_network(
            demand_multiplier=demand_multiplier,
            unfulfilled_penalty=unfulfilled_penalty,
            log_output=False,
            print_output=False,
        )
    return solve_network_case(demand_multiplier, int(config["sla_extra_days"]))


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
    app.run(host="127.0.0.1", port=5053, debug=True)
