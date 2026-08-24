from docplex.mp.model import Model


def default_network_data():
    warehouses = {
        "Los Angeles 3PL": {
            "capacity": 9000,
            "fixed_cost": 18000,
            "handling_cost": 1.20,
        },
        "New Jersey 3PL": {
            "capacity": 8500,
            "fixed_cost": 17000,
            "handling_cost": 1.10,
        },
        "Rotterdam EU Hub": {
            "capacity": 7000,
            "fixed_cost": 16000,
            "handling_cost": 1.35,
        },
        "Shenzhen Direct Ship": {
            "capacity": 12000,
            "fixed_cost": 6000,
            "handling_cost": 0.80,
        },
    }

    markets = {
        "US West": {"demand": 5200, "max_delivery_days": 3},
        "US East": {"demand": 4800, "max_delivery_days": 3},
        "Canada": {"demand": 1800, "max_delivery_days": 5},
        "UK": {"demand": 2400, "max_delivery_days": 4},
        "EU": {"demand": 3600, "max_delivery_days": 3},
    }

    last_mile_cost = {
        ("Los Angeles 3PL", "US West"): 4.2,
        ("Los Angeles 3PL", "US East"): 6.8,
        ("Los Angeles 3PL", "Canada"): 7.4,
        ("Los Angeles 3PL", "UK"): 12.5,
        ("Los Angeles 3PL", "EU"): 13.0,
        ("New Jersey 3PL", "US West"): 6.5,
        ("New Jersey 3PL", "US East"): 4.1,
        ("New Jersey 3PL", "Canada"): 5.9,
        ("New Jersey 3PL", "UK"): 10.8,
        ("New Jersey 3PL", "EU"): 11.5,
        ("Rotterdam EU Hub", "US West"): 13.0,
        ("Rotterdam EU Hub", "US East"): 11.7,
        ("Rotterdam EU Hub", "Canada"): 12.4,
        ("Rotterdam EU Hub", "UK"): 4.8,
        ("Rotterdam EU Hub", "EU"): 3.6,
        ("Shenzhen Direct Ship", "US West"): 5.8,
        ("Shenzhen Direct Ship", "US East"): 6.4,
        ("Shenzhen Direct Ship", "Canada"): 6.6,
        ("Shenzhen Direct Ship", "UK"): 5.9,
        ("Shenzhen Direct Ship", "EU"): 6.1,
    }

    delivery_days = {
        ("Los Angeles 3PL", "US West"): 2,
        ("Los Angeles 3PL", "US East"): 5,
        ("Los Angeles 3PL", "Canada"): 5,
        ("Los Angeles 3PL", "UK"): 8,
        ("Los Angeles 3PL", "EU"): 8,
        ("New Jersey 3PL", "US West"): 5,
        ("New Jersey 3PL", "US East"): 2,
        ("New Jersey 3PL", "Canada"): 4,
        ("New Jersey 3PL", "UK"): 7,
        ("New Jersey 3PL", "EU"): 7,
        ("Rotterdam EU Hub", "US West"): 8,
        ("Rotterdam EU Hub", "US East"): 7,
        ("Rotterdam EU Hub", "Canada"): 8,
        ("Rotterdam EU Hub", "UK"): 3,
        ("Rotterdam EU Hub", "EU"): 2,
        ("Shenzhen Direct Ship", "US West"): 9,
        ("Shenzhen Direct Ship", "US East"): 10,
        ("Shenzhen Direct Ship", "Canada"): 10,
        ("Shenzhen Direct Ship", "UK"): 8,
        ("Shenzhen Direct Ship", "EU"): 9,
    }

    return warehouses, markets, last_mile_cost, delivery_days


def solve_cross_border_network(markets=None, log_output=True):
    warehouses, base_markets, last_mile_cost, delivery_days = default_network_data()
    markets = markets or base_markets

    model = Model(name="cross_border_ecommerce_network")

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

    model.minimize(fixed_cost + variable_cost)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(ship[warehouse, market] for warehouse in warehouses)
            == data["demand"],
            ctname=f"demand_{market}",
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
            "message": "No feasible network found. Try relaxing SLA or adding capacity.",
        }

    opened_warehouses = [
        warehouse
        for warehouse in warehouses
        if open_warehouse[warehouse].solution_value > 0.5
    ]
    fulfillment_plan = {}
    for market in markets:
        fulfillment_plan[market] = []
        for warehouse in warehouses:
            amount = ship[warehouse, market].solution_value
            if amount > 1e-6:
                unit_cost = (
                    warehouses[warehouse]["handling_cost"]
                    + last_mile_cost[warehouse, market]
                )
                fulfillment_plan[market].append(
                    {
                        "warehouse": warehouse,
                        "orders": amount,
                        "unit_cost": unit_cost,
                        "delivery_days": delivery_days[warehouse, market],
                    }
                )

    return {
        "status": "optimal",
        "opened_warehouses": opened_warehouses,
        "fulfillment_plan": fulfillment_plan,
        "fixed_cost": fixed_cost.solution_value,
        "variable_cost": variable_cost.solution_value,
        "total_cost": solution.objective_value,
    }


def print_network_result(result, markets):
    if result["status"] != "optimal":
        print(result["message"])
        return

    print("\nBest cross-border ecommerce network")
    print("------------------------------------")
    for warehouse in result["opened_warehouses"]:
        print(f"- Open {warehouse}")

    print("\nFulfillment plan")
    print("----------------")
    for market, data in markets.items():
        print(f"{market} demand: {data['demand']}")
        for assignment in result["fulfillment_plan"][market]:
            print(
                f"  {assignment['warehouse']}: {assignment['orders']:g} orders, "
                f"unit_cost={assignment['unit_cost']:g}, "
                f"delivery_days={assignment['delivery_days']}"
            )

    print()
    print(f"Monthly fixed cost: {result['fixed_cost']:g}")
    print(f"Monthly variable cost: {result['variable_cost']:g}")
    print(f"Monthly total cost: {result['total_cost']:g}")


def main():
    _, markets, _, _ = default_network_data()
    result = solve_cross_border_network(markets=markets, log_output=True)
    print_network_result(result, markets)


if __name__ == "__main__":
    main()
