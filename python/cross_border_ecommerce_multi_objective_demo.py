from docplex.mp.model import Model


def solve_tradeoff_case(carbon_weight=0.0, speed_weight=0.0, risk_weight=0.0):
    markets = {
        "US": {"demand": 5200, "max_avg_days": 6.0},
        "EU": {"demand": 4300, "max_avg_days": 6.0},
        "UK": {"demand": 2100, "max_avg_days": 6.0},
    }

    routes = {
        "regional_warehouse": {
            "capacity": 7600,
            "unit_cost": {"US": 6.2, "EU": 6.0, "UK": 6.3},
            "days": {"US": 2, "EU": 2, "UK": 3},
            "kg_co2": {"US": 2.2, "EU": 2.0, "UK": 2.4},
            "risk": {"US": 0.03, "EU": 0.03, "UK": 0.04},
        },
        "cross_border_economy": {
            "capacity": 9000,
            "unit_cost": {"US": 4.7, "EU": 4.9, "UK": 4.8},
            "days": {"US": 10, "EU": 9, "UK": 8},
            "kg_co2": {"US": 1.3, "EU": 1.2, "UK": 1.1},
            "risk": {"US": 0.08, "EU": 0.07, "UK": 0.07},
        },
        "rail_postal_low_carbon": {
            "capacity": 4800,
            "unit_cost": {"US": 6.8, "EU": 6.6, "UK": 6.5},
            "days": {"US": 6, "EU": 6, "UK": 6},
            "kg_co2": {"US": 0.8, "EU": 0.7, "UK": 0.7},
            "risk": {"US": 0.06, "EU": 0.05, "UK": 0.05},
        },
        "air_express": {
            "capacity": 4200,
            "unit_cost": {"US": 8.4, "EU": 8.8, "UK": 8.2},
            "days": {"US": 4, "EU": 5, "UK": 4},
            "kg_co2": {"US": 6.4, "EU": 6.8, "UK": 6.5},
            "risk": {"US": 0.02, "EU": 0.02, "UK": 0.02},
        },
    }

    model = Model(name="cross_border_multi_objective_tradeoff")

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
    total_days = model.sum(
        routes[route]["days"][market] * orders[route, market]
        for route in routes
        for market in markets
    )
    carbon_kg = model.sum(
        routes[route]["kg_co2"][market] * orders[route, market]
        for route in routes
        for market in markets
    )
    expected_risky_orders = model.sum(
        routes[route]["risk"][market] * orders[route, market]
        for route in routes
        for market in markets
    )

    model.minimize(
        logistics_cost
        + speed_weight * total_days
        + carbon_weight * carbon_kg
        + risk_weight * expected_risky_orders
    )

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
            model.sum(orders[route, market] for market in markets) <= data["capacity"],
            ctname=f"capacity_{route}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    allocation = []
    total_orders = sum(data["demand"] for data in markets.values())
    for market in markets:
        for route in routes:
            amount = orders[route, market].solution_value
            if amount > 1e-6:
                allocation.append(
                    {
                        "market": market,
                        "route": route,
                        "orders": amount,
                        "unit_cost": routes[route]["unit_cost"][market],
                        "days": routes[route]["days"][market],
                        "kg_co2": routes[route]["kg_co2"][market],
                        "risk": routes[route]["risk"][market],
                    }
                )

    return {
        "status": "optimal",
        "weights": {
            "carbon_weight": carbon_weight,
            "speed_weight": speed_weight,
            "risk_weight": risk_weight,
        },
        "allocation": allocation,
        "logistics_cost": logistics_cost.solution_value,
        "average_delivery_days": total_days.solution_value / total_orders,
        "carbon_kg": carbon_kg.solution_value,
        "expected_risky_orders": expected_risky_orders.solution_value,
        "objective_value": solution.objective_value,
    }


def print_result(name, result):
    print(name)
    print("=" * len(name))
    print(
        "Weights: "
        f"carbon={result['weights']['carbon_weight']}, "
        f"speed={result['weights']['speed_weight']}, "
        f"risk={result['weights']['risk_weight']}"
    )
    print()
    for item in result["allocation"]:
        print(
            f"{item['market']:2} -> {item['route']:22} "
            f"{item['orders']:7.0f} orders, "
            f"cost={item['unit_cost']:4.1f}, "
            f"days={item['days']:2}, "
            f"co2={item['kg_co2']:3.1f}, "
            f"risk={item['risk']:.0%}"
        )
    print()
    print(f"Logistics cost: {result['logistics_cost']:.0f}")
    print(f"Average delivery days: {result['average_delivery_days']:.2f}")
    print(f"Carbon kg: {result['carbon_kg']:.0f}")
    print(f"Expected risky orders: {result['expected_risky_orders']:.1f}")
    print(f"Objective value: {result['objective_value']:.0f}")


def main():
    cases = [
        ("Cost first", {"carbon_weight": 0.0, "speed_weight": 0.0, "risk_weight": 0.0}),
        ("Low carbon", {"carbon_weight": 1.8, "speed_weight": 0.0, "risk_weight": 0.0}),
        ("Fast and reliable", {"carbon_weight": 0.0, "speed_weight": 0.45, "risk_weight": 90.0}),
        ("Balanced score", {"carbon_weight": 0.8, "speed_weight": 0.25, "risk_weight": 45.0}),
    ]
    for name, weights in cases:
        print_result(name, solve_tradeoff_case(**weights))
        print()


if __name__ == "__main__":
    main()
