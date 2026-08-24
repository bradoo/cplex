from copy import deepcopy

from docplex.mp.model import Model

from cross_border_ecommerce_network_demo import default_network_data


def solve_capacity_expansion_network(
    demand_multiplier=1.25,
    unfulfilled_penalty=50,
):
    warehouses, markets, last_mile_cost, delivery_days = default_network_data()
    markets = deepcopy(markets)
    for market in markets:
        markets[market]["demand"] = round(markets[market]["demand"] * demand_multiplier)

    expansion_options = {
        "Los Angeles 3PL": {"max_extra_capacity": 1500, "unit_cost": 3.5},
        "New Jersey 3PL": {"max_extra_capacity": 1200, "unit_cost": 3.0},
        "Rotterdam EU Hub": {"max_extra_capacity": 1000, "unit_cost": 4.0},
        "Shenzhen Direct Ship": {"max_extra_capacity": 4000, "unit_cost": 1.8},
    }

    model = Model(name="cross_border_ecommerce_capacity_expansion")

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
    extra_capacity = {
        warehouse: model.continuous_var(
            name=f"extra_capacity_{warehouse}",
            lb=0,
            ub=expansion_options[warehouse]["max_extra_capacity"],
        )
        for warehouse in warehouses
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
    expansion_cost = model.sum(
        expansion_options[warehouse]["unit_cost"] * extra_capacity[warehouse]
        for warehouse in warehouses
    )
    unfulfilled_cost = model.sum(
        unfulfilled_penalty * unfulfilled[market]
        for market in markets
    )

    model.minimize(fixed_cost + variable_cost + expansion_cost + unfulfilled_cost)

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
            <= (
                data["capacity"] * open_warehouse[warehouse]
                + extra_capacity[warehouse]
            ),
            ctname=f"capacity_with_expansion_{warehouse}",
        )
        model.add_constraint(
            extra_capacity[warehouse]
            <= expansion_options[warehouse]["max_extra_capacity"]
            * open_warehouse[warehouse],
            ctname=f"expand_only_if_open_{warehouse}",
        )

    for warehouse in warehouses:
        for market, data in markets.items():
            if delivery_days[warehouse, market] > data["max_delivery_days"]:
                model.add_constraint(
                    ship[warehouse, market] == 0,
                    ctname=f"sla_block_{warehouse}_to_{market}",
                )

    solution = model.solve(log_output=True)
    if solution is None:
        print("No solution found, even with expansion and unfulfilled demand allowed.")
        return

    print("Cross-border peak demand capacity expansion plan")
    print("================================================")
    print(f"Demand multiplier: {demand_multiplier:g}")
    print(f"Unfulfilled order penalty: {unfulfilled_penalty:g}")
    print()

    print("Warehouse capacity plan")
    print("-----------------------")
    for warehouse in warehouses:
        if open_warehouse[warehouse].solution_value > 0.5:
            used_capacity = sum(
                ship[warehouse, market].solution_value
                for market in markets
            )
            extra = extra_capacity[warehouse].solution_value
            base = warehouses[warehouse]["capacity"]
            print(
                f"- {warehouse}: used={used_capacity:g}, "
                f"base={base}, extra={extra:g}"
            )

    print()
    print("Market fulfillment")
    print("------------------")
    total_unfulfilled = 0
    for market, data in markets.items():
        market_unfulfilled = unfulfilled[market].solution_value
        total_unfulfilled += market_unfulfilled
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
    print(f"Temporary expansion cost: {expansion_cost.solution_value:g}")
    print(f"Unfulfilled penalty cost: {unfulfilled_cost.solution_value:g}")
    print(f"Weighted total objective: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_capacity_expansion_network()
