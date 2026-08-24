from copy import deepcopy

from docplex.mp.model import Model

from cross_border_ecommerce_network_demo import default_network_data


def solve_soft_capacity_network(
    demand_multiplier=1.25,
    unfulfilled_penalty=50,
    log_output=True,
    print_output=True,
):
    warehouses, markets, last_mile_cost, delivery_days = default_network_data()
    markets = deepcopy(markets)
    for market in markets:
        markets[market]["demand"] = round(markets[market]["demand"] * demand_multiplier)

    model = Model(name="cross_border_ecommerce_soft_capacity")

    open_warehouse = {
        warehouse: model.binary_var(name=f"open_{warehouse}")
        for warehouse in warehouses
    }
    ship = {
        (warehouse, market): model.continuous_var(
            name=f"ship_{warehouse}_to_{market}",
            lb=0,
        )
        for warehouse in warehouses
        for market in markets
    }
    unfulfilled = {
        market: model.continuous_var(name=f"unfulfilled_{market}", lb=0)
        for market in markets
    }

    fixed_cost = model.sum(
        warehouses[warehouse]["fixed_cost"] * open_warehouse[warehouse]
        for warehouse in warehouses
    )
    variable_cost = model.sum(
        (
            warehouses[warehouse]["handling_cost"]
            + last_mile_cost[warehouse, market]
        )
        * ship[warehouse, market]
        for warehouse in warehouses
        for market in markets
    )
    shortage_cost = model.sum(
        unfulfilled_penalty * unfulfilled[market]
        for market in markets
    )

    model.minimize(shortage_cost + fixed_cost + variable_cost)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(ship[warehouse, market] for warehouse in warehouses)
            + unfulfilled[market]
            == data["demand"],
            ctname=f"demand_with_unfulfilled_{market}",
        )

    for warehouse, data in warehouses.items():
        model.add_constraint(
            model.sum(ship[warehouse, market] for market in markets)
            <= data["capacity"] * open_warehouse[warehouse],
            ctname=f"capacity_if_open_{warehouse}",
        )

    for warehouse in warehouses:
        for market, data in markets.items():
            if delivery_days[warehouse, market] > data["max_delivery_days"]:
                model.add_constraint(
                    ship[warehouse, market] == 0,
                    ctname=f"sla_block_{warehouse}_to_{market}",
                )

    solution = model.solve(log_output=log_output)
    if solution is None:
        return {
            "status": "infeasible",
            "message": "No solution found, even with unfulfilled demand allowed.",
        }

    opened_warehouses = []
    capacity_plan = []
    for warehouse in warehouses:
        if open_warehouse[warehouse].solution_value > 0.5:
            used_capacity = sum(
                ship[warehouse, market].solution_value
                for market in markets
            )
            opened_warehouses.append(warehouse)
            capacity_plan.append(
                {
                    "warehouse": warehouse,
                    "used_capacity": used_capacity,
                    "base_capacity": warehouses[warehouse]["capacity"],
                }
            )

    fulfillment_plan = {}
    total_unfulfilled = 0
    for market, data in markets.items():
        market_unfulfilled = unfulfilled[market].solution_value
        total_unfulfilled += market_unfulfilled
        fulfillment_plan[market] = []
        for warehouse in warehouses:
            amount = ship[warehouse, market].solution_value
            if amount > 1e-6:
                fulfillment_plan[market].append(
                    {"warehouse": warehouse, "orders": amount}
                )

    result = {
        "status": "optimal",
        "opened_warehouses": opened_warehouses,
        "capacity_plan": capacity_plan,
        "fulfillment_plan": fulfillment_plan,
        "fixed_cost": fixed_cost.solution_value,
        "variable_cost": variable_cost.solution_value,
        "unfulfilled_cost": shortage_cost.solution_value,
        "total_unfulfilled": total_unfulfilled,
        "total_cost": solution.objective_value,
    }

    if not print_output:
        return result

    print("Cross-border peak demand soft-capacity plan")
    print("===========================================")
    print(f"Demand multiplier: {demand_multiplier:g}")
    print(f"Unfulfilled order penalty: {unfulfilled_penalty:g}")
    print()

    print("Opened warehouses")
    print("-----------------")
    for row in capacity_plan:
        print(
            f"- {row['warehouse']}: used {row['used_capacity']:g} / "
            f"{row['base_capacity']}"
        )

    print()
    print("Market fulfillment")
    print("------------------")
    for market, data in markets.items():
        market_unfulfilled = unfulfilled[market].solution_value
        fulfilled = data["demand"] - market_unfulfilled
        print(
            f"{market}: demand={data['demand']}, "
            f"fulfilled={fulfilled:g}, unfulfilled={market_unfulfilled:g}"
        )
        for warehouse in warehouses:
            amount = ship[warehouse, market].solution_value
            if amount > 1e-6:
                print(f"  {warehouse}: {amount:g}")

    print()
    print(f"Total unfulfilled orders: {total_unfulfilled:g}")
    print(f"Monthly fixed cost: {fixed_cost.solution_value:g}")
    print(f"Monthly variable cost: {variable_cost.solution_value:g}")
    print(f"Unfulfilled penalty cost: {shortage_cost.solution_value:g}")
    print(f"Weighted total objective: {solution.objective_value:g}")
    return result


if __name__ == "__main__":
    solve_soft_capacity_network()
