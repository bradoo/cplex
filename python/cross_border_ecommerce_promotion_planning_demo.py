from docplex.mp.model import Model


def solve_promotion_plan():
    skus = {
        "Phone Case": {
            "base_demand": 3600,
            "available_inventory": 4600,
            "unit_margin": 5.2,
            "promo_lift": 0.35,
            "promo_cost": 2200,
        },
        "Bluetooth Earbuds": {
            "base_demand": 1700,
            "available_inventory": 2400,
            "unit_margin": 13.5,
            "promo_lift": 0.28,
            "promo_cost": 3600,
        },
        "Coffee Grinder": {
            "base_demand": 820,
            "available_inventory": 1050,
            "unit_margin": 19.0,
            "promo_lift": 0.22,
            "promo_cost": 2800,
        },
        "Desk Lamp": {
            "base_demand": 1000,
            "available_inventory": 1300,
            "unit_margin": 11.0,
            "promo_lift": 0.30,
            "promo_cost": 2500,
        },
    }

    promo_budget = 6200
    max_promoted_skus = 2

    model = Model(name="cross_border_promotion_planning")

    promote = {
        sku: model.binary_var(name=f"promote_{sku}")
        for sku in skus
    }
    fulfilled = {
        sku: model.continuous_var(name=f"fulfilled_{sku}", lb=0)
        for sku in skus
    }

    for sku, data in skus.items():
        promoted_demand = data["base_demand"] * (1 + data["promo_lift"] * promote[sku])
        model.add_constraint(
            fulfilled[sku] <= promoted_demand,
            ctname=f"demand_if_promoted_{sku}",
        )
        model.add_constraint(
            fulfilled[sku] <= data["available_inventory"],
            ctname=f"inventory_{sku}",
        )

    model.add_constraint(
        model.sum(data["promo_cost"] * promote[sku] for sku, data in skus.items())
        <= promo_budget,
        ctname="promo_budget",
    )
    model.add_constraint(
        model.sum(promote[sku] for sku in skus) <= max_promoted_skus,
        ctname="max_promoted_skus",
    )

    gross_contribution = model.sum(
        skus[sku]["unit_margin"] * fulfilled[sku]
        for sku in skus
    )
    promo_spend = model.sum(
        skus[sku]["promo_cost"] * promote[sku]
        for sku in skus
    )

    model.maximize(gross_contribution - promo_spend)

    solution = model.solve(log_output=True)
    if solution is None:
        print("No feasible promotion plan found.")
        return

    print("Cross-border promotion planning")
    print("===============================")
    print(f"Promotion budget: {promo_budget}")
    print(f"Max promoted SKUs: {max_promoted_skus}")
    print()

    total_orders = 0
    for sku, data in skus.items():
        is_promoted = promote[sku].solution_value > 0.5
        demand = data["base_demand"] * (1 + data["promo_lift"] * int(is_promoted))
        orders = fulfilled[sku].solution_value
        total_orders += orders
        print(
            f"{sku}: promoted={is_promoted}, "
            f"demand={demand:g}, fulfilled={orders:g}, "
            f"inventory={data['available_inventory']}"
        )

    print()
    print(f"Total fulfilled orders: {total_orders:g}")
    print(f"Gross contribution: {gross_contribution.solution_value:g}")
    print(f"Promotion spend: {promo_spend.solution_value:g}")
    print(f"Net contribution: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_promotion_plan()
