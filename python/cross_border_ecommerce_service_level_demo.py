from docplex.mp.model import Model


def solve_service_level_mix(log_output=True, print_output=True):
    markets = {
        "US West": {"demand": 5200, "max_avg_delivery_days": 4.0},
        "US East": {"demand": 4800, "max_avg_delivery_days": 4.0},
        "UK": {"demand": 2400, "max_avg_delivery_days": 5.0},
        "EU": {"demand": 3600, "max_avg_delivery_days": 5.0},
    }

    services = {
        "local_standard": {
            "capacity": 9000,
            "fixed_cost": 28000,
            "cost": {
                "US West": 5.4,
                "US East": 5.2,
                "UK": 6.15,
                "EU": 4.95,
            },
            "delivery_days": {
                "US West": 2,
                "US East": 2,
                "UK": 3,
                "EU": 2,
            },
        },
        "cross_border_economy": {
            "capacity": 10000,
            "fixed_cost": 5000,
            "cost": {
                "US West": 4.6,
                "US East": 5.0,
                "UK": 4.8,
                "EU": 4.9,
            },
            "delivery_days": {
                "US West": 9,
                "US East": 10,
                "UK": 8,
                "EU": 9,
            },
        },
        "cross_border_express": {
            "capacity": 4500,
            "fixed_cost": 9000,
            "cost": {
                "US West": 7.9,
                "US East": 8.4,
                "UK": 7.6,
                "EU": 7.8,
            },
            "delivery_days": {
                "US West": 4,
                "US East": 5,
                "UK": 4,
                "EU": 5,
            },
        },
    }

    model = Model(name="cross_border_ecommerce_service_level")

    use_service = {
        service: model.binary_var(name=f"use_{service}")
        for service in services
    }
    orders = {
        (service, market): model.continuous_var(
            name=f"orders_{service}_to_{market}",
            lb=0,
        )
        for service in services
        for market in markets
    }

    fixed_cost = model.sum(
        services[service]["fixed_cost"] * use_service[service]
        for service in services
    )
    variable_cost = model.sum(
        services[service]["cost"][market] * orders[service, market]
        for service in services
        for market in markets
    )

    model.minimize(fixed_cost + variable_cost)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(orders[service, market] for service in services)
            == data["demand"],
            ctname=f"demand_{market}",
        )
        model.add_constraint(
            model.sum(
                services[service]["delivery_days"][market] * orders[service, market]
                for service in services
            )
            <= data["max_avg_delivery_days"] * data["demand"],
            ctname=f"avg_delivery_sla_{market}",
        )

    for service, data in services.items():
        model.add_constraint(
            model.sum(orders[service, market] for market in markets)
            <= data["capacity"] * use_service[service],
            ctname=f"capacity_if_used_{service}",
        )

    solution = model.solve(log_output=log_output)
    if solution is None:
        return {"status": "infeasible", "message": "No feasible service-level mix found."}

    used_services = []
    allocation = {}
    for service in services:
        used_orders = sum(
            orders[service, market].solution_value
            for market in markets
        )
        if used_orders > 1e-6:
            used_services.append({"service": service, "orders": used_orders})

    for market, data in markets.items():
        weighted_days = 0
        allocation[market] = []
        for service in services:
            amount = orders[service, market].solution_value
            if amount > 1e-6:
                days = services[service]["delivery_days"][market]
                weighted_days += days * amount
                allocation[market].append(
                    {
                        "service": service,
                        "orders": amount,
                        "unit_cost": services[service]["cost"][market],
                        "delivery_days": days,
                    }
                )
        allocation[market + "_average_days"] = weighted_days / data["demand"]

    result = {
        "status": "optimal",
        "used_services": used_services,
        "allocation": allocation,
        "fixed_cost": fixed_cost.solution_value,
        "variable_cost": variable_cost.solution_value,
        "total_cost": solution.objective_value,
    }

    if not print_output:
        return result

    print("Cross-border service-level mix")
    print("==============================")
    print("Used services")
    print("-------------")
    for service in services:
        if use_service[service].solution_value > 0.5:
            used = next(item for item in used_services if item["service"] == service)
            print(f"- {service}: {used['orders']:g} orders")

    print()
    print("Market allocation")
    print("-----------------")
    for market, data in markets.items():
        print(f"{market}: demand={data['demand']}")
        for item in allocation[market]:
            print(
                f"  {item['service']}: {item['orders']:g} orders, "
                f"unit_cost={item['unit_cost']:g}, "
                f"days={item['delivery_days']}"
            )
        print(f"  average_delivery_days={allocation[market + '_average_days']:.2f}")

    print()
    print(f"Monthly fixed cost: {fixed_cost.solution_value:g}")
    print(f"Monthly variable cost: {variable_cost.solution_value:g}")
    print(f"Monthly total cost: {solution.objective_value:g}")
    return result


if __name__ == "__main__":
    solve_service_level_mix()
