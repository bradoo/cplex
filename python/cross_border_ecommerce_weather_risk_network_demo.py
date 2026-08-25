from docplex.mp.model import Model


def solve_weather_risk_network_case():
    markets = {
        "US West": {"demand": 3600, "max_delivery_days": 3},
        "US Central": {"demand": 2600, "max_delivery_days": 3},
        "US East": {"demand": 3400, "max_delivery_days": 3},
        "EU": {"demand": 3000, "max_delivery_days": 4},
    }

    warehouses = {
        "Los Angeles": {
            "fixed_cost": 30000,
            "capacity": 5200,
            "weather_risk": 0.18,
            "risk_cost_per_order": 2.8,
        },
        "Texas": {
            "fixed_cost": 28000,
            "capacity": 4800,
            "weather_risk": 0.12,
            "risk_cost_per_order": 2.2,
        },
        "New Jersey": {
            "fixed_cost": 32000,
            "capacity": 5000,
            "weather_risk": 0.10,
            "risk_cost_per_order": 1.9,
        },
        "Florida": {
            "fixed_cost": 24000,
            "capacity": 4200,
            "weather_risk": 0.24,
            "risk_cost_per_order": 3.4,
        },
        "Rotterdam": {
            "fixed_cost": 34000,
            "capacity": 4200,
            "weather_risk": 0.08,
            "risk_cost_per_order": 1.7,
        },
    }

    delivery_days = {
        ("Los Angeles", "US West"): 1,
        ("Los Angeles", "US Central"): 4,
        ("Los Angeles", "US East"): 5,
        ("Los Angeles", "EU"): 8,
        ("Texas", "US West"): 3,
        ("Texas", "US Central"): 2,
        ("Texas", "US East"): 3,
        ("Texas", "EU"): 7,
        ("New Jersey", "US West"): 5,
        ("New Jersey", "US Central"): 3,
        ("New Jersey", "US East"): 1,
        ("New Jersey", "EU"): 6,
        ("Florida", "US West"): 5,
        ("Florida", "US Central"): 3,
        ("Florida", "US East"): 2,
        ("Florida", "EU"): 7,
        ("Rotterdam", "US West"): 8,
        ("Rotterdam", "US Central"): 7,
        ("Rotterdam", "US East"): 6,
        ("Rotterdam", "EU"): 2,
    }

    unit_cost = {
        ("Los Angeles", "US West"): 4.8,
        ("Los Angeles", "US Central"): 6.0,
        ("Los Angeles", "US East"): 7.1,
        ("Los Angeles", "EU"): 9.4,
        ("Texas", "US West"): 5.7,
        ("Texas", "US Central"): 4.9,
        ("Texas", "US East"): 5.8,
        ("Texas", "EU"): 8.6,
        ("New Jersey", "US West"): 7.2,
        ("New Jersey", "US Central"): 5.8,
        ("New Jersey", "US East"): 4.7,
        ("New Jersey", "EU"): 8.2,
        ("Florida", "US West"): 7.4,
        ("Florida", "US Central"): 5.7,
        ("Florida", "US East"): 4.9,
        ("Florida", "EU"): 8.5,
        ("Rotterdam", "US West"): 9.0,
        ("Rotterdam", "US Central"): 8.5,
        ("Rotterdam", "US East"): 7.9,
        ("Rotterdam", "EU"): 4.6,
    }

    max_risky_order_share = 0.42
    risk_threshold = 0.15
    max_weather_score = 0.13

    model = Model(name="cross_border_weather_risk_network")

    open_warehouse = {
        warehouse: model.binary_var(name=f"open_{warehouse}")
        for warehouse in warehouses
    }
    ship = {
        (warehouse, market): model.continuous_var(name=f"ship_{warehouse}_{market}", lb=0)
        for warehouse in warehouses
        for market in markets
    }

    fixed_cost = model.sum(
        warehouses[warehouse]["fixed_cost"] * open_warehouse[warehouse]
        for warehouse in warehouses
    )
    fulfillment_cost = model.sum(
        unit_cost[warehouse, market] * ship[warehouse, market]
        for warehouse in warehouses
        for market in markets
    )
    weather_risk_cost = model.sum(
        warehouses[warehouse]["weather_risk"]
        * warehouses[warehouse]["risk_cost_per_order"]
        * ship[warehouse, market]
        for warehouse in warehouses
        for market in markets
    )

    model.minimize(fixed_cost + fulfillment_cost + weather_risk_cost)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(ship[warehouse, market] for warehouse in warehouses) == data["demand"],
            ctname=f"demand_{market}",
        )
        for warehouse in warehouses:
            if delivery_days[warehouse, market] > data["max_delivery_days"]:
                model.add_constraint(ship[warehouse, market] == 0, ctname=f"sla_block_{warehouse}_{market}")

    for warehouse, data in warehouses.items():
        model.add_constraint(
            model.sum(ship[warehouse, market] for market in markets)
            <= data["capacity"] * open_warehouse[warehouse],
            ctname=f"capacity_if_open_{warehouse}",
        )

    total_orders = sum(data["demand"] for data in markets.values())
    model.add_constraint(
        model.sum(
            ship[warehouse, market]
            for warehouse in warehouses
            for market in markets
            if warehouses[warehouse]["weather_risk"] >= risk_threshold
        )
        <= max_risky_order_share * total_orders,
        ctname="limit_high_weather_risk_exposure",
    )
    model.add_constraint(
        model.sum(
            warehouses[warehouse]["weather_risk"] * ship[warehouse, market]
            for warehouse in warehouses
            for market in markets
        )
        <= max_weather_score * total_orders,
        ctname="portfolio_average_weather_risk",
    )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    opened = []
    weather_exposure = {}
    fulfillment_plan = []
    for warehouse in warehouses:
        volume = sum(ship[warehouse, market].solution_value for market in markets)
        if volume > 1e-6:
            opened.append(warehouse)
            weather_exposure[warehouse] = {
                "orders": volume,
                "weather_risk": warehouses[warehouse]["weather_risk"],
                "expected_disruption_orders": volume * warehouses[warehouse]["weather_risk"],
            }
        for market in markets:
            amount = ship[warehouse, market].solution_value
            if amount > 1e-6:
                fulfillment_plan.append(
                    {
                        "warehouse": warehouse,
                        "market": market,
                        "orders": amount,
                        "delivery_days": delivery_days[warehouse, market],
                        "unit_cost": unit_cost[warehouse, market],
                    }
                )

    return {
        "status": "optimal",
        "opened_warehouses": opened,
        "fulfillment_plan": fulfillment_plan,
        "weather_exposure": weather_exposure,
        "fixed_cost": fixed_cost.solution_value,
        "fulfillment_cost": fulfillment_cost.solution_value,
        "weather_risk_cost": weather_risk_cost.solution_value,
        "total_cost": solution.objective_value,
        "average_weather_risk": sum(
            item["orders"] * item["weather_risk"] for item in weather_exposure.values()
        )
        / total_orders,
    }


def print_result(result):
    print("Cross-border weather-risk warehouse network")
    print("===========================================")
    print()
    print("Opened warehouses")
    print("-----------------")
    for warehouse in result["opened_warehouses"]:
        exposure = result["weather_exposure"][warehouse]
        print(
            f"- {warehouse}: {exposure['orders']:.0f} orders, "
            f"weather_risk={exposure['weather_risk']:.0%}, "
            f"expected_disruption_orders={exposure['expected_disruption_orders']:.0f}"
        )

    print()
    print("Fulfillment plan")
    print("----------------")
    for row in result["fulfillment_plan"]:
        print(
            f"{row['market']:10} <- {row['warehouse']:11} "
            f"{row['orders']:6.0f} orders, days={row['delivery_days']}, "
            f"unit_cost={row['unit_cost']:3.1f}"
        )

    print()
    print(f"Fixed cost: {result['fixed_cost']:.0f}")
    print(f"Fulfillment cost: {result['fulfillment_cost']:.0f}")
    print(f"Weather risk cost: {result['weather_risk_cost']:.0f}")
    print(f"Average weather risk: {result['average_weather_risk']:.1%}")
    print(f"Total cost: {result['total_cost']:.0f}")


def main():
    print_result(solve_weather_risk_network_case())


if __name__ == "__main__":
    main()
