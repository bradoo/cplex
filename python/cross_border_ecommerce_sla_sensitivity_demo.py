from docplex.mp.model import Model


def solve_sla_case(fast_days):
    markets = {
        "US": {"demand": 6200, "fast_share": 0.80},
        "EU": {"demand": 5200, "fast_share": 0.75},
        "UK": {"demand": 2600, "fast_share": 0.70},
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
            "unit_cost": {"US": 6.0, "EU": 6.6, "UK": 6.4},
            "delivery_days": {"US": 9, "EU": 9, "UK": 8},
        },
        "direct_ddp_express": {
            "fixed_cost": 8000,
            "capacity": 5000,
            "unit_cost": {"US": 8.5, "EU": 9.0, "UK": 8.6},
            "delivery_days": {"US": 4, "EU": 5, "UK": 4},
        },
    }

    model = Model(name=f"cross_border_sla_sensitivity_{fast_days}_days")

    use_route = {route: model.binary_var(name=f"use_{route}") for route in routes}
    orders = {
        (route, market): model.continuous_var(name=f"orders_{route}_{market}", lb=0)
        for route in routes
        for market in markets
    }

    fixed_cost = model.sum(routes[route]["fixed_cost"] * use_route[route] for route in routes)
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
                if routes[route]["delivery_days"][market] <= fast_days
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

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible", "fast_days": fast_days}

    route_totals = {}
    fast_orders = {}
    for route in routes:
        total = sum(orders[route, market].solution_value for market in markets)
        if total > 1e-6:
            route_totals[route] = total

    for market, data in markets.items():
        fast = sum(
            orders[route, market].solution_value
            for route in routes
            if routes[route]["delivery_days"][market] <= fast_days
        )
        fast_orders[market] = {
            "target": data["fast_share"],
            "actual": fast / data["demand"],
        }

    return {
        "status": "optimal",
        "fast_days": fast_days,
        "total_cost": solution.objective_value,
        "fixed_cost": fixed_cost.solution_value,
        "variable_cost": variable_cost.solution_value,
        "route_totals": route_totals,
        "fast_orders": fast_orders,
    }


def print_result(result):
    print(f"SLA promise: {result['fast_days']} days")
    print("-" * 26)
    if result["status"] != "optimal":
        print("No feasible routing plan.")
        return

    print(f"Total cost: {result['total_cost']:.0f}")
    print(f"Fixed cost: {result['fixed_cost']:.0f}")
    print(f"Variable cost: {result['variable_cost']:.0f}")
    print("Route mix:")
    for route, amount in result["route_totals"].items():
        print(f"  {route}: {amount:.0f} orders")
    print("Fast share:")
    for market, share in result["fast_orders"].items():
        print(f"  {market}: target={share['target']:.0%}, actual={share['actual']:.1%}")


def main():
    print("Cross-border SLA sensitivity")
    print("============================")
    print()
    for fast_days in [3, 4, 5, 6, 8, 9]:
        print_result(solve_sla_case(fast_days))
        print()


if __name__ == "__main__":
    main()
