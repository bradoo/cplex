import json
import os

from docplex.mp.model import Model


def solve_inventory_transfer_case(warehouse_overrides=None):
    warehouses = {
        "LA_3PL": {"initial": 5200, "demand": 3300, "inbound_cost": 1.8},
        "NJ_3PL": {"initial": 1100, "demand": 2800, "inbound_cost": 1.9},
        "Rotterdam": {"initial": 900, "demand": 2400, "inbound_cost": 2.2},
        "Sydney": {"initial": 2600, "demand": 1200, "inbound_cost": 2.6},
    }
    for warehouse, values in (warehouse_overrides or {}).items():
        if warehouse not in warehouses:
            continue
        for key in ["initial", "demand"]:
            if key in values:
                warehouses[warehouse][key] = max(0, float(values[key]))

    transfer_cost = {
        ("LA_3PL", "NJ_3PL"): 1.1,
        ("LA_3PL", "Rotterdam"): 2.8,
        ("LA_3PL", "Sydney"): 3.2,
        ("NJ_3PL", "LA_3PL"): 1.1,
        ("NJ_3PL", "Rotterdam"): 2.4,
        ("NJ_3PL", "Sydney"): 3.4,
        ("Rotterdam", "LA_3PL"): 2.8,
        ("Rotterdam", "NJ_3PL"): 2.4,
        ("Rotterdam", "Sydney"): 3.6,
        ("Sydney", "LA_3PL"): 3.2,
        ("Sydney", "NJ_3PL"): 3.4,
        ("Sydney", "Rotterdam"): 3.1,
    }

    transfer_capacity = {
        ("LA_3PL", "NJ_3PL"): 1200,
        ("LA_3PL", "Rotterdam"): 700,
        ("LA_3PL", "Sydney"): 300,
        ("NJ_3PL", "LA_3PL"): 500,
        ("NJ_3PL", "Rotterdam"): 450,
        ("NJ_3PL", "Sydney"): 300,
        ("Rotterdam", "LA_3PL"): 300,
        ("Rotterdam", "NJ_3PL"): 350,
        ("Rotterdam", "Sydney"): 250,
        ("Sydney", "LA_3PL"): 500,
        ("Sydney", "NJ_3PL"): 600,
        ("Sydney", "Rotterdam"): 900,
    }

    shortage_penalty = 14
    max_domestic_replenishment = 2200

    model = Model(name="cross_border_inventory_transfer")

    transfer = {
        lane: model.continuous_var(name=f"transfer_{lane[0]}_to_{lane[1]}", lb=0)
        for lane in transfer_cost
    }
    replenish = {
        wh: model.continuous_var(name=f"replenish_{wh}", lb=0)
        for wh in warehouses
    }
    shortage = {
        wh: model.continuous_var(name=f"shortage_{wh}", lb=0)
        for wh in warehouses
    }
    ending_inventory = {
        wh: model.continuous_var(name=f"ending_inventory_{wh}", lb=0)
        for wh in warehouses
    }

    transfer_total_cost = model.sum(
        transfer_cost[lane] * transfer[lane]
        for lane in transfer
    )
    inbound_cost = model.sum(
        warehouses[wh]["inbound_cost"] * replenish[wh]
        for wh in warehouses
    )
    shortage_cost = model.sum(shortage_penalty * shortage[wh] for wh in warehouses)

    model.minimize(transfer_total_cost + inbound_cost + shortage_cost)

    for wh, data in warehouses.items():
        inbound_transfer = model.sum(transfer[src, dst] for (src, dst) in transfer if dst == wh)
        outbound_transfer = model.sum(transfer[src, dst] for (src, dst) in transfer if src == wh)
        model.add_constraint(
            data["initial"] + inbound_transfer + replenish[wh] + shortage[wh]
            == data["demand"] + outbound_transfer + ending_inventory[wh],
            ctname=f"inventory_balance_{wh}",
        )

    for lane, capacity in transfer_capacity.items():
        model.add_constraint(transfer[lane] <= capacity, ctname=f"transfer_capacity_{lane[0]}_{lane[1]}")

    model.add_constraint(
        model.sum(replenish[wh] for wh in warehouses) <= max_domestic_replenishment,
        ctname="domestic_replenishment_capacity",
    )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    transfer_plan = []
    for (src, dst), var in transfer.items():
        amount = var.solution_value
        if amount > 1e-6:
            transfer_plan.append(
                {
                    "from": src,
                    "to": dst,
                    "units": amount,
                    "unit_cost": transfer_cost[src, dst],
                }
            )

    warehouse_plan = []
    for wh, data in warehouses.items():
        warehouse_plan.append(
            {
                "warehouse": wh,
                "initial": data["initial"],
                "demand": data["demand"],
                "replenish": replenish[wh].solution_value,
                "shortage": shortage[wh].solution_value,
                "ending_inventory": ending_inventory[wh].solution_value,
            }
        )

    return {
        "status": "optimal",
        "transfer_plan": transfer_plan,
        "warehouse_plan": warehouse_plan,
        "transfer_cost": transfer_total_cost.solution_value,
        "inbound_cost": inbound_cost.solution_value,
        "shortage_cost": shortage_cost.solution_value,
        "total_cost": solution.objective_value,
    }


def print_result(result):
    print("Cross-border inventory transfer")
    print("===============================")
    print()
    print("Transfer plan")
    print("-------------")
    for row in result["transfer_plan"]:
        print(
            f"{row['from']:9} -> {row['to']:9} "
            f"{row['units']:7.0f} units, unit_cost={row['unit_cost']:3.1f}"
        )
    print()
    print("Warehouse plan")
    print("--------------")
    for row in result["warehouse_plan"]:
        print(
            f"{row['warehouse']:9} initial={row['initial']:5.0f}, "
            f"demand={row['demand']:5.0f}, replenish={row['replenish']:5.0f}, "
            f"shortage={row['shortage']:5.0f}, ending={row['ending_inventory']:5.0f}"
        )
    print()
    print(f"Transfer cost: {result['transfer_cost']:.0f}")
    print(f"Domestic inbound cost: {result['inbound_cost']:.0f}")
    print(f"Shortage cost: {result['shortage_cost']:.0f}")
    print(f"Total cost: {result['total_cost']:.0f}")


def main():
    raw_params = os.environ.get("CROSS_BORDER_SCENARIO_PARAMS", "{}")
    try:
        params = json.loads(raw_params)
    except json.JSONDecodeError:
        params = {}
    print_result(solve_inventory_transfer_case(params.get("warehouses")))


if __name__ == "__main__":
    main()
