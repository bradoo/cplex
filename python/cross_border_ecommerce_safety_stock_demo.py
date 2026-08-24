from math import sqrt

from docplex.mp.model import Model


def solve_safety_stock_plan():
    skus = {
        "Phone Case": {
            "daily_demand_std": 55,
            "lead_time_days": 18,
            "unit_inventory_cost": 0.35,
            "stockout_loss": 5.2,
        },
        "Bluetooth Earbuds": {
            "daily_demand_std": 28,
            "lead_time_days": 21,
            "unit_inventory_cost": 0.90,
            "stockout_loss": 13.5,
        },
        "Coffee Grinder": {
            "daily_demand_std": 16,
            "lead_time_days": 28,
            "unit_inventory_cost": 1.80,
            "stockout_loss": 19.0,
        },
        "Desk Lamp": {
            "daily_demand_std": 22,
            "lead_time_days": 24,
            "unit_inventory_cost": 2.10,
            "stockout_loss": 11.0,
        },
    }

    service_levels = {
        "basic": {"z": 1.28, "target_fill": 0.90},
        "standard": {"z": 1.65, "target_fill": 0.95},
        "premium": {"z": 2.05, "target_fill": 0.98},
    }

    safety_stock_budget = 800

    recommended_stock = {
        (sku, level): round(
            level_data["z"]
            * data["daily_demand_std"]
            * sqrt(data["lead_time_days"])
        )
        for sku, data in skus.items()
        for level, level_data in service_levels.items()
    }

    model = Model(name="cross_border_safety_stock")

    choose_level = {
        (sku, level): model.binary_var(name=f"choose_{sku}_{level}")
        for sku in skus
        for level in service_levels
    }

    for sku in skus:
        model.add_constraint(
            model.sum(choose_level[sku, level] for level in service_levels) == 1,
            ctname=f"one_service_level_{sku}",
        )

    model.add_constraint(
        model.sum(
            skus[sku]["unit_inventory_cost"]
            * recommended_stock[sku, level]
            * choose_level[sku, level]
            for sku in skus
            for level in service_levels
        )
        <= safety_stock_budget,
        ctname="safety_stock_budget",
    )

    model.maximize(
        model.sum(
            skus[sku]["stockout_loss"]
            * service_levels[level]["target_fill"]
            * recommended_stock[sku, level]
            * choose_level[sku, level]
            for sku in skus
            for level in service_levels
        )
    )

    solution = model.solve(log_output=True)
    if solution is None:
        print("No feasible safety stock plan found.")
        return

    print("Cross-border safety stock plan")
    print("==============================")
    print(f"Safety stock budget: {safety_stock_budget}")
    print()

    total_units = 0
    total_cost = 0
    for sku, data in skus.items():
        for level in service_levels:
            if choose_level[sku, level].solution_value > 0.5:
                units = recommended_stock[sku, level]
                cost = units * data["unit_inventory_cost"]
                total_units += units
                total_cost += cost
                print(
                    f"{sku}: {level}, safety_stock={units}, "
                    f"cost={cost:g}, target_fill={service_levels[level]['target_fill']:.0%}"
                )

    print()
    print(f"Total safety stock units: {total_units:g}")
    print(f"Total safety stock cost: {total_cost:g}")
    print(f"Protection score: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_safety_stock_plan()
