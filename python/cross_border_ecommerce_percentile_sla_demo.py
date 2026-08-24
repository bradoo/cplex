from docplex.mp.model import Model


def solve_percentile_sla_routing():
    markets = {
        "US": {"demand": 6200, "fast_days": 5, "fast_share": 0.80},
        "EU": {"demand": 5200, "fast_days": 5, "fast_share": 0.75},
        "UK": {"demand": 2600, "fast_days": 5, "fast_share": 0.70},
    }

    routes = {
        "local_bonded": {
            "fixed_cost": 26000,
            "capacity": 9000,
            "unit_cost": {"US": 5.5, "EU": 5.9, "UK": 6.3},
            "delivery_days": {"US": 2, "EU": 2, "UK": 3},
        },
        "direct_ddu": {
            "fixed_cost": 3000,
            "capacity": 12000,
            "unit_cost": {"US": 6.3, "EU": 7.1, "UK": 6.9},
            "delivery_days": {"US": 9, "EU": 9, "UK": 8},
        },
        "direct_ddp_express": {
            "fixed_cost": 8000,
            "capacity": 5000,
            "unit_cost": {"US": 8.5, "EU": 9.0, "UK": 8.6},
            "delivery_days": {"US": 4, "EU": 5, "UK": 4},
        },
    }

    model = Model(name="cross_border_percentile_sla_routing")

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
    variable_cost = model.sum(
        routes[route]["unit_cost"][market] * orders[route, market]
        for route in routes
        for market in markets
    )

    model.minimize(fixed_cost + variable_cost)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(orders[route, market] for route in routes) == data["demand"],
            ctname=f"demand_{market}",
        )
        model.add_constraint(
            model.sum(
                orders[route, market]
                for route in routes
                if routes[route]["delivery_days"][market] <= data["fast_days"]
            )
            >= data["fast_share"] * data["demand"],
            ctname=f"fast_share_{market}",
        )

    for route, data in routes.items():
        model.add_constraint(
            model.sum(orders[route, market] for market in markets)
            <= data["capacity"] * use_route[route],
            ctname=f"capacity_if_used_{route}",
        )

    solution = model.solve(log_output=True)
    if solution is None:
        print("No feasible percentile-SLA routing plan found.")
        return

    print("Cross-border percentile SLA routing")
    print("===================================")
    print()
    print("Used routes")
    print("-----------")
    for route in routes:
        if use_route[route].solution_value > 0.5:
            total = sum(orders[route, market].solution_value for market in markets)
            print(f"- {route}: {total:g} orders")

    print()
    print("Market routing")
    print("--------------")
    for market, data in markets.items():
        fast_orders = 0
        print(
            f"{market}: demand={data['demand']}, "
            f"fast target={data['fast_share']:.0%} within {data['fast_days']} days"
        )
        for route in routes:
            amount = orders[route, market].solution_value
            if amount > 1e-6:
                days = routes[route]["delivery_days"][market]
                if days <= data["fast_days"]:
                    fast_orders += amount
                print(
                    f"  {route}: {amount:g} orders, "
                    f"unit_cost={routes[route]['unit_cost'][market]:g}, days={days}"
                )
        print(f"  fast_share={fast_orders / data['demand']:.1%}")

    print()
    print(f"Fixed route cost: {fixed_cost.solution_value:g}")
    print(f"Variable route cost: {variable_cost.solution_value:g}")
    print(f"Total cost: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_percentile_sla_routing()
