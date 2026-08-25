from docplex.mp.model import Model


def solve_resilience_case(reserve_backup=False):
    markets = {
        "US": {"demand": 5200, "max_avg_days": 5.5},
        "EU": {"demand": 4200, "max_avg_days": 5.5},
        "UK": {"demand": 2200, "max_avg_days": 5.5},
    }

    routes = {
        "bonded_warehouse": {
            "capacity": 6200,
            "unit_cost": {"US": 6.1, "EU": 5.9, "UK": 6.2},
            "days": {"US": 2, "EU": 2, "UK": 3},
            "disruption_capacity": 6200,
        },
        "direct_linehaul": {
            "capacity": 8500,
            "unit_cost": {"US": 4.8, "EU": 4.9, "UK": 4.7},
            "days": {"US": 9, "EU": 9, "UK": 8},
            "disruption_capacity": 3600,
        },
        "backup_express": {
            "capacity": 3600,
            "unit_cost": {"US": 8.2, "EU": 8.4, "UK": 8.0},
            "days": {"US": 4, "EU": 5, "UK": 4},
            "disruption_capacity": 3600,
        },
    }

    model = Model(name="cross_border_resilience_plan")

    normal_orders = {
        (route, market): model.continuous_var(name=f"normal_{route}_{market}", lb=0)
        for route in routes
        for market in markets
    }
    disruption_orders = {
        (route, market): model.continuous_var(name=f"disruption_{route}_{market}", lb=0)
        for route in routes
        for market in markets
    }
    reserve = {
        route: model.continuous_var(name=f"reserve_{route}", lb=0)
        for route in routes
    }
    shortage = {
        market: model.continuous_var(name=f"shortage_{market}", lb=0)
        for market in markets
    }

    normal_cost = model.sum(
        routes[route]["unit_cost"][market] * normal_orders[route, market]
        for route in routes
        for market in markets
    )
    reserve_cost = model.sum(0.9 * reserve[route] for route in routes)
    disruption_penalty = model.sum(65 * shortage[market] for market in markets)

    if reserve_backup:
        model.minimize(normal_cost + reserve_cost + disruption_penalty)
    else:
        model.minimize(normal_cost)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(normal_orders[route, market] for route in routes) == data["demand"],
            ctname=f"normal_demand_{market}",
        )
        model.add_constraint(
            model.sum(
                routes[route]["days"][market] * normal_orders[route, market]
                for route in routes
            )
            <= data["max_avg_days"] * data["demand"],
            ctname=f"normal_sla_{market}",
        )
        model.add_constraint(
            model.sum(disruption_orders[route, market] for route in routes)
            + shortage[market]
            == data["demand"],
            ctname=f"disruption_demand_{market}",
        )
        model.add_constraint(
            model.sum(
                routes[route]["days"][market] * disruption_orders[route, market]
                for route in routes
            )
            <= data["max_avg_days"] * data["demand"],
            ctname=f"disruption_sla_{market}",
        )

    for route, data in routes.items():
        model.add_constraint(
            model.sum(normal_orders[route, market] for market in markets)
            + (reserve[route] if reserve_backup else 0)
            <= data["capacity"],
            ctname=f"normal_capacity_{route}",
        )
        model.add_constraint(
            model.sum(disruption_orders[route, market] for market in markets)
            <= data["disruption_capacity"],
            ctname=f"disruption_capacity_{route}",
        )
        model.add_constraint(
            model.sum(disruption_orders[route, market] for market in markets)
            <= model.sum(normal_orders[route, market] for market in markets)
            + (reserve[route] if reserve_backup else 0),
            ctname=f"reserve_enables_disruption_{route}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    def allocation(var_dict):
        rows = []
        for market in markets:
            for route in routes:
                amount = var_dict[route, market].solution_value
                if amount > 1e-6:
                    rows.append(
                        {
                            "market": market,
                            "route": route,
                            "orders": amount,
                            "unit_cost": routes[route]["unit_cost"][market],
                            "days": routes[route]["days"][market],
                        }
                    )
        return rows

    return {
        "status": "optimal",
        "reserve_backup": reserve_backup,
        "normal_allocation": allocation(normal_orders),
        "disruption_allocation": allocation(disruption_orders),
        "reserved_capacity": {
            route: reserve[route].solution_value
            for route in routes
            if reserve[route].solution_value > 1e-6
        },
        "shortage": {
            market: shortage[market].solution_value
            for market in markets
            if shortage[market].solution_value > 1e-6
        },
        "normal_cost": normal_cost.solution_value,
        "reserve_cost": reserve_cost.solution_value if reserve_backup else 0,
        "disruption_penalty": disruption_penalty.solution_value,
        "objective_value": solution.objective_value,
    }


def print_plan(title, result):
    print(title)
    print("=" * len(title))
    print(f"Reserve backup capacity: {result['reserve_backup']}")
    print()
    print("Normal plan")
    print("-----------")
    for row in result["normal_allocation"]:
        print(
            f"{row['market']:2} -> {row['route']:17} "
            f"{row['orders']:7.0f} orders, cost={row['unit_cost']:4.1f}, days={row['days']}"
        )
    print()
    print("Disruption plan")
    print("---------------")
    for row in result["disruption_allocation"]:
        print(
            f"{row['market']:2} -> {row['route']:17} "
            f"{row['orders']:7.0f} orders, cost={row['unit_cost']:4.1f}, days={row['days']}"
        )
    print()
    print(f"Reserved capacity: {result['reserved_capacity'] or 'none'}")
    print(f"Shortage: {result['shortage'] or 'none'}")
    print(f"Normal cost: {result['normal_cost']:.0f}")
    print(f"Reserve cost: {result['reserve_cost']:.0f}")
    print(f"Disruption penalty: {result['disruption_penalty']:.0f}")
    print(f"Objective value: {result['objective_value']:.0f}")


def main():
    print_plan("Lean plan", solve_resilience_case(reserve_backup=False))
    print()
    print_plan("Resilient plan", solve_resilience_case(reserve_backup=True))


if __name__ == "__main__":
    main()
