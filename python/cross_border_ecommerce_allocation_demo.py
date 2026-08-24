from docplex.mp.model import Model


def solve_profit_priority_allocation():
    skus = {
        "Phone Case": {"available_inventory": 3600},
        "Bluetooth Earbuds": {"available_inventory": 2100},
        "Coffee Grinder": {"available_inventory": 900},
    }

    markets = ["US", "EU", "UK"]

    demand = {
        ("Phone Case", "US"): 2200,
        ("Phone Case", "EU"): 1500,
        ("Phone Case", "UK"): 900,
        ("Bluetooth Earbuds", "US"): 1200,
        ("Bluetooth Earbuds", "EU"): 900,
        ("Bluetooth Earbuds", "UK"): 650,
        ("Coffee Grinder", "US"): 700,
        ("Coffee Grinder", "EU"): 500,
        ("Coffee Grinder", "UK"): 300,
    }

    unit_contribution = {
        ("Phone Case", "US"): 5.2,
        ("Phone Case", "EU"): 4.8,
        ("Phone Case", "UK"): 4.5,
        ("Bluetooth Earbuds", "US"): 13.5,
        ("Bluetooth Earbuds", "EU"): 12.8,
        ("Bluetooth Earbuds", "UK"): 11.9,
        ("Coffee Grinder", "US"): 19.0,
        ("Coffee Grinder", "EU"): 16.5,
        ("Coffee Grinder", "UK"): 15.0,
    }

    minimum_service_rate = {
        "US": 0.75,
        "EU": 0.65,
        "UK": 0.50,
    }

    model = Model(name="cross_border_profit_priority_allocation")

    fulfill = {
        (sku, market): model.continuous_var(
            name=f"fulfill_{sku}_{market}",
            lb=0,
        )
        for sku in skus
        for market in markets
    }

    model.maximize(
        model.sum(
            unit_contribution[sku, market] * fulfill[sku, market]
            for sku in skus
            for market in markets
        )
    )

    for sku, data in skus.items():
        model.add_constraint(
            model.sum(fulfill[sku, market] for market in markets)
            <= data["available_inventory"],
            ctname=f"inventory_{sku}",
        )

    for sku in skus:
        for market in markets:
            model.add_constraint(
                fulfill[sku, market] <= demand[sku, market],
                ctname=f"demand_cap_{sku}_{market}",
            )

    for market, service_rate in minimum_service_rate.items():
        total_market_demand = sum(demand[sku, market] for sku in skus)
        model.add_constraint(
            model.sum(fulfill[sku, market] for sku in skus)
            >= service_rate * total_market_demand,
            ctname=f"minimum_service_{market}",
        )

    solution = model.solve(log_output=True)
    if solution is None:
        print("No feasible allocation found. Lower service rates or add inventory.")
        return

    print("Cross-border profit-priority fulfillment allocation")
    print("===================================================")
    print()

    print("SKU allocation")
    print("--------------")
    for sku, data in skus.items():
        used = sum(fulfill[sku, market].solution_value for market in markets)
        print(f"{sku}: used {used:g} / {data['available_inventory']}")
        for market in markets:
            amount = fulfill[sku, market].solution_value
            unmet = demand[sku, market] - amount
            print(
                f"  {market}: fulfill={amount:g}, "
                f"unmet={unmet:g}, "
                f"unit_contribution={unit_contribution[sku, market]:g}"
            )

    print()
    print("Market service rates")
    print("--------------------")
    for market in markets:
        total_demand = sum(demand[sku, market] for sku in skus)
        total_fulfilled = sum(
            fulfill[sku, market].solution_value
            for sku in skus
        )
        print(
            f"{market}: {total_fulfilled:g} / {total_demand} "
            f"({total_fulfilled / total_demand:.1%})"
        )

    print()
    print(f"Total contribution: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_profit_priority_allocation()
