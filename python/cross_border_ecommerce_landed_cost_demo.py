from docplex.mp.model import Model


def solve_landed_cost_routing():
    markets = {
        "US": {"demand": 6200, "max_avg_delivery_days": 4.0},
        "EU": {"demand": 5200, "max_avg_delivery_days": 5.0},
        "UK": {"demand": 2600, "max_avg_delivery_days": 5.0},
    }

    routes = {
        "local_bonded": {
            "fixed_cost": 26000,
            "capacity": 9000,
            "freight_cost": {"US": 4.8, "EU": 4.6, "UK": 5.2},
            "duty_cost": {"US": 0.7, "EU": 1.3, "UK": 1.1},
            "delivery_days": {"US": 2, "EU": 2, "UK": 3},
        },
        "direct_ddu": {
            "fixed_cost": 3000,
            "capacity": 12000,
            "freight_cost": {"US": 4.4, "EU": 4.3, "UK": 4.5},
            "duty_cost": {"US": 1.9, "EU": 2.8, "UK": 2.4},
            "delivery_days": {"US": 9, "EU": 9, "UK": 8},
        },
        "direct_ddp_express": {
            "fixed_cost": 8000,
            "capacity": 5000,
            "freight_cost": {"US": 7.5, "EU": 7.2, "UK": 7.0},
            "duty_cost": {"US": 1.0, "EU": 1.8, "UK": 1.6},
            "delivery_days": {"US": 4, "EU": 5, "UK": 4},
        },
    }

    model = Model(name="cross_border_landed_cost_routing")

    use_route = {
        route: model.binary_var(name=f"use_{route}")
        for route in routes
    }
    orders = {
        (route, market): model.continuous_var(name=f"orders_{route}_{market}", lb=0)
        for route in routes
        for market in markets
    }

    fixed_cost = model.sum(
        routes[route]["fixed_cost"] * use_route[route]
        for route in routes
    )
    landed_variable_cost = model.sum(
        (
            routes[route]["freight_cost"][market]
            + routes[route]["duty_cost"][market]
        )
        * orders[route, market]
        for route in routes
        for market in markets
    )

    model.minimize(fixed_cost + landed_variable_cost)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(orders[route, market] for route in routes) == data["demand"],
            ctname=f"demand_{market}",
        )
        model.add_constraint(
            model.sum(
                routes[route]["delivery_days"][market] * orders[route, market]
                for route in routes
            )
            <= data["max_avg_delivery_days"] * data["demand"],
            ctname=f"avg_delivery_sla_{market}",
        )

    for route, data in routes.items():
        model.add_constraint(
            model.sum(orders[route, market] for market in markets)
            <= data["capacity"] * use_route[route],
            ctname=f"capacity_if_used_{route}",
        )

    solution = model.solve(log_output=True)
    if solution is None:
        print("No feasible landed-cost routing plan found.")
        return

    print("Cross-border landed-cost routing")
    print("================================")
    print()
    print("Used routes")
    print("-----------")
    for route in routes:
        if use_route[route].solution_value > 0.5:
            volume = sum(orders[route, market].solution_value for market in markets)
            print(f"- {route}: {volume:g} orders")

    print()
    print("Market routing")
    print("--------------")
    for market, data in markets.items():
        weighted_days = 0
        print(f"{market}: demand={data['demand']}")
        for route in routes:
            amount = orders[route, market].solution_value
            if amount > 1e-6:
                freight = routes[route]["freight_cost"][market]
                duty = routes[route]["duty_cost"][market]
                days = routes[route]["delivery_days"][market]
                weighted_days += amount * days
                print(
                    f"  {route}: {amount:g} orders, "
                    f"freight={freight:g}, duty={duty:g}, "
                    f"landed_unit_cost={freight + duty:g}, days={days}"
                )
        print(f"  average_delivery_days={weighted_days / data['demand']:.2f}")

    print()
    print(f"Fixed route cost: {fixed_cost.solution_value:g}")
    print(f"Landed variable cost: {landed_variable_cost.solution_value:g}")
    print(f"Total landed cost: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_landed_cost_routing()
