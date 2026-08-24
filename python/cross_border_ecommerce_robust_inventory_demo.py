from docplex.mp.model import Model


def solve_robust_inventory_plan():
    skus = {
        "Phone Case": {"purchase_cost": 2.2, "holding_cost": 0.25, "stockout_loss": 5.2},
        "Bluetooth Earbuds": {"purchase_cost": 10.5, "holding_cost": 0.85, "stockout_loss": 13.5},
        "Coffee Grinder": {"purchase_cost": 19.0, "holding_cost": 1.70, "stockout_loss": 19.0},
        "Desk Lamp": {"purchase_cost": 14.5, "holding_cost": 2.10, "stockout_loss": 11.0},
    }

    scenarios = {
        "low": {
            "probability": 0.25,
            "demand": {
                "Phone Case": 2800,
                "Bluetooth Earbuds": 1200,
                "Coffee Grinder": 520,
                "Desk Lamp": 720,
            },
        },
        "base": {
            "probability": 0.50,
            "demand": {
                "Phone Case": 3600,
                "Bluetooth Earbuds": 1700,
                "Coffee Grinder": 820,
                "Desk Lamp": 1000,
            },
        },
        "high": {
            "probability": 0.25,
            "demand": {
                "Phone Case": 4700,
                "Bluetooth Earbuds": 2300,
                "Coffee Grinder": 1250,
                "Desk Lamp": 1450,
            },
        },
    }

    warehouse_capacity_units = 6800
    procurement_budget = 52000

    model = Model(name="cross_border_robust_inventory")

    buy = {
        sku: model.continuous_var(name=f"buy_{sku}", lb=0)
        for sku in skus
    }
    leftover = {
        (sku, scenario): model.continuous_var(
            name=f"leftover_{sku}_{scenario}",
            lb=0,
        )
        for sku in skus
        for scenario in scenarios
    }
    stockout = {
        (sku, scenario): model.continuous_var(
            name=f"stockout_{sku}_{scenario}",
            lb=0,
        )
        for sku in skus
        for scenario in scenarios
    }

    for sku in skus:
        for scenario, scenario_data in scenarios.items():
            model.add_constraint(
                buy[sku] - scenario_data["demand"][sku]
                == leftover[sku, scenario] - stockout[sku, scenario],
                ctname=f"inventory_balance_{sku}_{scenario}",
            )

    model.add_constraint(
        model.sum(buy[sku] for sku in skus) <= warehouse_capacity_units,
        ctname="warehouse_capacity",
    )
    model.add_constraint(
        model.sum(skus[sku]["purchase_cost"] * buy[sku] for sku in skus)
        <= procurement_budget,
        ctname="procurement_budget",
    )

    purchase_cost = model.sum(
        skus[sku]["purchase_cost"] * buy[sku]
        for sku in skus
    )
    expected_holding_cost = model.sum(
        scenarios[scenario]["probability"]
        * skus[sku]["holding_cost"]
        * leftover[sku, scenario]
        for sku in skus
        for scenario in scenarios
    )
    expected_stockout_loss = model.sum(
        scenarios[scenario]["probability"]
        * skus[sku]["stockout_loss"]
        * stockout[sku, scenario]
        for sku in skus
        for scenario in scenarios
    )

    model.minimize(purchase_cost + expected_holding_cost + expected_stockout_loss)

    solution = model.solve(log_output=True)
    if solution is None:
        print("No feasible robust inventory plan found.")
        return

    print("Cross-border robust inventory plan")
    print("==================================")
    print(f"Warehouse capacity: {warehouse_capacity_units}")
    print(f"Procurement budget: {procurement_budget}")
    print()

    print("Purchase plan")
    print("-------------")
    total_units = 0
    for sku in skus:
        units = buy[sku].solution_value
        total_units += units
        print(f"{sku}: buy {units:g} units")
    print(f"Total units: {total_units:g}")

    print()
    print("Scenario outcomes")
    print("-----------------")
    for scenario in scenarios:
        print(scenario)
        for sku in skus:
            print(
                f"  {sku}: leftover={leftover[sku, scenario].solution_value:g}, "
                f"stockout={stockout[sku, scenario].solution_value:g}"
            )

    print()
    print(f"Purchase cost: {purchase_cost.solution_value:g}")
    print(f"Expected holding cost: {expected_holding_cost.solution_value:g}")
    print(f"Expected stockout loss: {expected_stockout_loss.solution_value:g}")
    print(f"Expected total cost: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_robust_inventory_plan()
