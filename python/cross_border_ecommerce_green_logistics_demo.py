from docplex.mp.model import Model


def solve_green_logistics(carbon_price_per_kg=0):
    markets = {
        "US": {"demand": 6200, "max_avg_delivery_days": 5.0},
        "EU": {"demand": 5200, "max_avg_delivery_days": 5.0},
        "UK": {"demand": 2600, "max_avg_delivery_days": 5.0},
    }

    routes = {
        "air_express": {
            "capacity": 6000,
            "unit_cost": {"US": 8.5, "EU": 9.0, "UK": 8.6},
            "delivery_days": {"US": 4, "EU": 5, "UK": 4},
            "kg_co2_per_order": {"US": 6.2, "EU": 6.8, "UK": 6.5},
        },
        "ocean_consolidated": {
            "capacity": 9000,
            "unit_cost": {"US": 5.8, "EU": 6.1, "UK": 6.0},
            "delivery_days": {"US": 14, "EU": 15, "UK": 14},
            "kg_co2_per_order": {"US": 1.1, "EU": 1.3, "UK": 1.2},
        },
        "regional_warehouse": {
            "capacity": 11000,
            "unit_cost": {"US": 6.2, "EU": 6.0, "UK": 6.4},
            "delivery_days": {"US": 2, "EU": 2, "UK": 3},
            "kg_co2_per_order": {"US": 2.4, "EU": 2.2, "UK": 2.5},
        },
    }

    model = Model(name="cross_border_green_logistics")

    orders = {
        (route, market): model.continuous_var(name=f"orders_{route}_{market}", lb=0)
        for route in routes
        for market in markets
    }

    logistics_cost = model.sum(
        routes[route]["unit_cost"][market] * orders[route, market]
        for route in routes
        for market in markets
    )
    carbon_kg = model.sum(
        routes[route]["kg_co2_per_order"][market] * orders[route, market]
        for route in routes
        for market in markets
    )

    model.minimize(logistics_cost + carbon_price_per_kg * carbon_kg)

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
            <= data["capacity"],
            ctname=f"capacity_{route}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    allocation = {}
    for market in markets:
        allocation[market] = []
        for route in routes:
            amount = orders[route, market].solution_value
            if amount > 1e-6:
                allocation[market].append(
                    {
                        "route": route,
                        "orders": amount,
                        "unit_cost": routes[route]["unit_cost"][market],
                        "delivery_days": routes[route]["delivery_days"][market],
                        "kg_co2_per_order": routes[route]["kg_co2_per_order"][market],
                    }
                )

    return {
        "status": "optimal",
        "carbon_price_per_kg": carbon_price_per_kg,
        "allocation": allocation,
        "logistics_cost": logistics_cost.solution_value,
        "carbon_kg": carbon_kg.solution_value,
        "carbon_cost": carbon_price_per_kg * carbon_kg.solution_value,
        "objective_value": solution.objective_value,
    }


def print_result(result):
    print("Cross-border green logistics")
    print("============================")
    print(f"Carbon price per kg: {result['carbon_price_per_kg']}")
    print()
    for market, assignments in result["allocation"].items():
        print(market)
        for assignment in assignments:
            print(
                f"  {assignment['route']}: {assignment['orders']:g} orders, "
                f"cost={assignment['unit_cost']:g}, days={assignment['delivery_days']}, "
                f"kg_co2={assignment['kg_co2_per_order']:g}"
            )
    print()
    print(f"Logistics cost: {result['logistics_cost']:g}")
    print(f"Carbon kg: {result['carbon_kg']:g}")
    print(f"Carbon cost: {result['carbon_cost']:g}")
    print(f"Objective value: {result['objective_value']:g}")


def main():
    for carbon_price in [0, 1.5]:
        result = solve_green_logistics(carbon_price_per_kg=carbon_price)
        print_result(result)
        print()


if __name__ == "__main__":
    main()
