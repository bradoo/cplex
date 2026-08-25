from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import json
import os

from flask import Flask, jsonify, render_template, request

from cross_border_ecommerce_capacity_expansion_demo import (
    solve_capacity_expansion_network,
)
from cross_border_ecommerce_network_demo import (
    default_network_data,
    solve_cross_border_network,
)
from cross_border_ecommerce_replenishment_demo import (
    default_replenishment_data,
    solve_replenishment_plan,
)
from cross_border_ecommerce_service_level_demo import solve_service_level_mix
from cross_border_ecommerce_soft_capacity_demo import solve_soft_capacity_network


app = Flask(__name__)


SCRIPT_SCENARIOS = {
    "inventory_placement": "cross_border_ecommerce_inventory_placement_demo.py",
    "market_entry": "cross_border_ecommerce_market_entry_demo.py",
    "replenishment_scenarios": "cross_border_ecommerce_replenishment_scenarios_demo.py",
    "supplier_sourcing": "cross_border_ecommerce_supplier_sourcing_demo.py",
    "inventory_transfer": "cross_border_ecommerce_inventory_transfer_demo.py",
    "weather_risk_network": "cross_border_ecommerce_weather_risk_network_demo.py",
    "profit_allocation": "cross_border_ecommerce_allocation_demo.py",
    "landed_cost": "cross_border_ecommerce_landed_cost_demo.py",
    "tariff_sensitivity": "cross_border_ecommerce_tariff_sensitivity_demo.py",
    "percentile_sla": "cross_border_ecommerce_percentile_sla_demo.py",
    "sla_sensitivity": "cross_border_ecommerce_sla_sensitivity_demo.py",
    "returns": "cross_border_ecommerce_returns_demo.py",
    "return_grading": "cross_border_ecommerce_return_grading_demo.py",
    "safety_stock": "cross_border_ecommerce_safety_stock_demo.py",
    "green_logistics": "cross_border_ecommerce_green_logistics_demo.py",
    "multi_objective": "cross_border_ecommerce_multi_objective_demo.py",
    "resilience": "cross_border_ecommerce_resilience_demo.py",
    "robust_inventory": "cross_border_ecommerce_robust_inventory_demo.py",
    "channel_allocation": "cross_border_ecommerce_channel_allocation_demo.py",
    "ad_inventory": "cross_border_ecommerce_ad_inventory_demo.py",
    "promotion_planning": "cross_border_ecommerce_promotion_planning_demo.py",
    "promotion_sensitivity": "cross_border_ecommerce_promotion_sensitivity_demo.py",
    "markdown_clearance": "cross_border_ecommerce_markdown_clearance_demo.py",
    "penalty_sensitivity": "cross_border_ecommerce_penalty_sensitivity_demo.py",
    "dashboard": "cross_border_ecommerce_dashboard_demo.py",
}


@app.get("/")
def index():
    return render_template("cross_border_ecommerce_app.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "cross-border-ecommerce-simulator"})


@app.post("/api/simulate")
def simulate():
    data = request.get_json(force=True) or {}
    scenario = data.get("scenario", "strict_sla")
    demand_multiplier = float(data.get("demand_multiplier") or 1)
    sla_extra_days = int(data.get("sla_extra_days") or 0)
    unfulfilled_penalty = float(data.get("unfulfilled_penalty") or 50)
    air_capacity = int(data.get("air_capacity") or 900)
    ocean_lead_time = int(data.get("ocean_lead_time") or 3)
    scenario_params = data.get("scenario_params") or {}

    if scenario in SCRIPT_SCENARIOS:
        return jsonify(run_script_scenario(scenario, scenario_params))

    if scenario == "strict_sla":
        network = solve_network_case(demand_multiplier, sla_extra_days)
    elif scenario == "soft_capacity":
        network = solve_soft_capacity_network(
            demand_multiplier=demand_multiplier,
            unfulfilled_penalty=unfulfilled_penalty,
            log_output=False,
            print_output=False,
        )
    elif scenario == "capacity_expansion":
        network = solve_capacity_expansion_network(
            demand_multiplier=demand_multiplier,
            unfulfilled_penalty=unfulfilled_penalty,
            log_output=False,
            print_output=False,
        )
    else:
        return jsonify({"status": "error", "message": f"Unknown scenario: {scenario}"}), 400

    replenishment = solve_replenishment_case(
        air_capacity=air_capacity,
        ocean_lead_time=ocean_lead_time,
        stockout_penalty=unfulfilled_penalty,
    )
    service_mix = solve_service_level_case()

    return jsonify(
        {
            "status": "ok",
            "scenario": scenario,
            "network": network,
            "replenishment": replenishment,
            "service_mix": service_mix,
        }
    )


def solve_network_case(demand_multiplier, sla_extra_days):
    _, markets, _, _ = default_network_data()
    markets = deepcopy(markets)
    for market in markets:
        markets[market]["demand"] = round(markets[market]["demand"] * demand_multiplier)
        markets[market]["max_delivery_days"] += sla_extra_days
    result = solve_cross_border_network(markets=markets, log_output=False)
    return normalize_network_result(result)


def normalize_network_result(result):
    if result["status"] != "optimal":
        return result
    return {
        "status": "optimal",
        "opened_warehouses": result["opened_warehouses"],
        "fulfillment_plan": result["fulfillment_plan"],
        "fixed_cost": round(result["fixed_cost"], 2),
        "variable_cost": round(result["variable_cost"], 2),
        "total_cost": round(result["total_cost"], 2),
        "total_unfulfilled": round(result.get("total_unfulfilled", 0), 2),
        "expansion_cost": round(result.get("expansion_cost", 0), 2),
        "unfulfilled_cost": round(result.get("unfulfilled_cost", 0), 2),
        "capacity_plan": result.get("capacity_plan", []),
    }


def solve_replenishment_case(air_capacity, ocean_lead_time, stockout_penalty):
    data = default_replenishment_data()
    data["lanes"]["air"]["weekly_capacity"] = air_capacity
    data["lanes"]["ocean"]["lead_time_weeks"] = ocean_lead_time
    data["stockout_penalty"] = stockout_penalty
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


def solve_service_level_case():
    result = solve_service_level_mix(log_output=False, print_output=False)
    return result


def run_script_scenario(scenario, scenario_params=None):
    script_path = Path(__file__).resolve().parent / SCRIPT_SCENARIOS[scenario]
    env = os.environ.copy()
    env["CROSS_BORDER_SCENARIO_PARAMS"] = json.dumps(scenario_params or {})
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=script_path.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "status": "ok" if completed.returncode == 0 else "error",
        "scenario": scenario,
        "text_output": completed.stdout.strip(),
        "error_output": completed.stderr.strip(),
        "return_code": completed.returncode,
    }


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5052, debug=True)
