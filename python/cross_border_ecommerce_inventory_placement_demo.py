from docplex.mp.model import Model


def solve_inventory_placement():
    skus = {
        "Phone Case": {"monthly_demand": 4200, "unit_volume": 0.10, "margin": 8.0},
        "Bluetooth Earbuds": {"monthly_demand": 1800, "unit_volume": 0.25, "margin": 18.0},
        "Yoga Leggings": {"monthly_demand": 2600, "unit_volume": 0.35, "margin": 14.0},
        "Coffee Grinder": {"monthly_demand": 900, "unit_volume": 1.20, "margin": 28.0},
        "Desk Lamp": {"monthly_demand": 1100, "unit_volume": 1.60, "margin": 24.0},
    }

    warehouses = {
        "US Warehouse": {"volume_capacity": 1800, "storage_cost_per_volume": 2.4},
        "EU Warehouse": {"volume_capacity": 1400, "storage_cost_per_volume": 2.8},
    }

    markets = {
        "US": {
            "demand_share": 0.58,
            "warehouse": "US Warehouse",
            "local_ship_cost": 3.2,
            "direct_ship_cost": 6.4,
        },
        "EU": {
            "demand_share": 0.42,
            "warehouse": "EU Warehouse",
            "local_ship_cost": 3.6,
            "direct_ship_cost": 6.8,
        },
    }

    model = Model(name="cross_border_inventory_placement")

    place = {
        (sku, market): model.continuous_var(name=f"place_{sku}_for_{market}", lb=0)
        for sku in skus
        for market in markets
    }
    direct_ship = {
        (sku, market): model.continuous_var(
            name=f"direct_ship_{sku}_to_{market}",
            lb=0,
        )
        for sku in skus
        for market in markets
    }

    local_profit = model.sum(
        (
            skus[sku]["margin"]
            - markets[market]["local_ship_cost"]
            - warehouses[markets[market]["warehouse"]]["storage_cost_per_volume"]
            * skus[sku]["unit_volume"]
        )
        * place[sku, market]
        for sku in skus
        for market in markets
    )
    direct_profit = model.sum(
        (skus[sku]["margin"] - markets[market]["direct_ship_cost"])
        * direct_ship[sku, market]
        for sku in skus
        for market in markets
    )

    model.maximize(local_profit + direct_profit)

    for sku, data in skus.items():
        for market, market_data in markets.items():
            market_demand = round(data["monthly_demand"] * market_data["demand_share"])
            model.add_constraint(
                place[sku, market] + direct_ship[sku, market] == market_demand,
                ctname=f"demand_{sku}_{market}",
            )

    for warehouse, data in warehouses.items():
        model.add_constraint(
            model.sum(
                skus[sku]["unit_volume"] * place[sku, market]
                for sku in skus
                for market, market_data in markets.items()
                if market_data["warehouse"] == warehouse
            )
            <= data["volume_capacity"],
            ctname=f"volume_capacity_{warehouse}",
        )

    solution = model.solve(log_output=True)
    if solution is None:
        print("No feasible inventory placement found.")
        return

    print("Cross-border inventory placement")
    print("================================")
    print()
    for warehouse, data in warehouses.items():
        used_volume = 0
        print(warehouse)
        print("-" * len(warehouse))
        for market, market_data in markets.items():
            if market_data["warehouse"] != warehouse:
                continue
            for sku in skus:
                amount = place[sku, market].solution_value
                if amount > 1e-6:
                    volume = amount * skus[sku]["unit_volume"]
                    used_volume += volume
                    print(f"{sku}: {amount:g} units, volume={volume:g}")
        print(f"Used volume: {used_volume:g} / {data['volume_capacity']}")
        print()

    print("Direct-ship remainder")
    print("---------------------")
    for market in markets:
        for sku in skus:
            amount = direct_ship[sku, market].solution_value
            if amount > 1e-6:
                print(f"{market} {sku}: {amount:g} units")

    print()
    print(f"Monthly contribution after logistics/storage: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_inventory_placement()
