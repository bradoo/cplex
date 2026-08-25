from docplex.mp.model import Model


def solve_tariff_case(
    case_name,
    duty_multiplier=1.0,
    ddp_clearance_surcharge=0.0,
    ddu_compliance_surcharge=0.0,
    low_value_relief=True,
):
    markets = {
        "US": {"demand": 5800, "max_avg_days": 5.5, "low_value_share": 0.55},
        "EU": {"demand": 4600, "max_avg_days": 5.0, "low_value_share": 0.35},
        "UK": {"demand": 2400, "max_avg_days": 5.0, "low_value_share": 0.40},
    }

    routes = {
        "bonded_warehouse": {
            "fixed_cost": 26000,
            "capacity": 7600,
            "freight": {"US": 4.9, "EU": 4.7, "UK": 5.1},
            "base_duty": {"US": 0.8, "EU": 1.5, "UK": 1.3},
            "days": {"US": 2, "EU": 2, "UK": 3},
        },
        "direct_ddu": {
            "fixed_cost": 2500,
            "capacity": 10000,
            "freight": {"US": 4.4, "EU": 4.5, "UK": 4.6},
            "base_duty": {"US": 1.7, "EU": 2.7, "UK": 2.3},
            "days": {"US": 9, "EU": 9, "UK": 8},
        },
        "direct_ddp_express": {
            "fixed_cost": 6500,
            "capacity": 4800,
            "freight": {"US": 5.8, "EU": 6.0, "UK": 5.8},
            "base_duty": {"US": 0.3, "EU": 0.6, "UK": 0.5},
            "days": {"US": 4, "EU": 5, "UK": 4},
        },
    }

    model = Model(name=f"cross_border_tariff_sensitivity_{case_name}")

    use_route = {
        route: model.binary_var(name=f"use_{route}")
        for route in routes
    }
    orders = {
        (route, market): model.continuous_var(name=f"orders_{route}_{market}", lb=0)
        for route in routes
        for market in markets
    }

    def duty_cost(route, market):
        relief_discount = 0.65 if low_value_relief and route == "direct_ddu" else 1.0
        return routes[route]["base_duty"][market] * duty_multiplier * relief_discount

    fixed_cost = model.sum(routes[route]["fixed_cost"] * use_route[route] for route in routes)
    variable_cost = model.sum(
        (
            routes[route]["freight"][market]
            + duty_cost(route, market)
            + (ddp_clearance_surcharge if route == "direct_ddp_express" else 0)
            + (ddu_compliance_surcharge if route == "direct_ddu" else 0)
        )
        * orders[route, market]
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
            model.sum(routes[route]["days"][market] * orders[route, market] for route in routes)
            <= data["max_avg_days"] * data["demand"],
            ctname=f"avg_sla_{market}",
        )

    for route, data in routes.items():
        model.add_constraint(
            model.sum(orders[route, market] for market in markets)
            <= data["capacity"] * use_route[route],
            ctname=f"capacity_if_used_{route}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible", "case": case_name}

    route_totals = {}
    route_costs = {}
    for route in routes:
        volume = sum(orders[route, market].solution_value for market in markets)
        if volume > 1e-6:
            route_totals[route] = volume
            route_costs[route] = sum(
                (
                    routes[route]["freight"][market]
                    + duty_cost(route, market)
                    + (ddp_clearance_surcharge if route == "direct_ddp_express" else 0)
                    + (ddu_compliance_surcharge if route == "direct_ddu" else 0)
                )
                * orders[route, market].solution_value
                for market in markets
            )

    return {
        "status": "optimal",
        "case": case_name,
        "route_totals": route_totals,
        "route_costs": route_costs,
        "fixed_cost": fixed_cost.solution_value,
        "variable_cost": variable_cost.solution_value,
        "total_cost": solution.objective_value,
    }


def print_result(result):
    print(result["case"])
    print("=" * len(result["case"]))
    if result["status"] != "optimal":
        print("No feasible tariff routing plan.")
        return
    print("Route mix:")
    for route, amount in result["route_totals"].items():
        print(f"  {route}: {amount:.0f} orders, variable_cost={result['route_costs'][route]:.0f}")
    print(f"Fixed cost: {result['fixed_cost']:.0f}")
    print(f"Variable cost: {result['variable_cost']:.0f}")
    print(f"Total cost: {result['total_cost']:.0f}")


def main():
    cases = [
        ("Base tariff policy", {}),
        ("Duty +25%", {"duty_multiplier": 1.25}),
        ("DDU compliance surcharge", {"ddu_compliance_surcharge": 1.8}),
        ("Low-value relief removed", {"low_value_relief": False}),
    ]
    print("Cross-border tariff sensitivity")
    print("===============================")
    print()
    for name, params in cases:
        print_result(solve_tariff_case(name, **params))
        print()


if __name__ == "__main__":
    main()
