from docplex.mp.model import Model


def solve_cashflow_inventory_case():
    skus = {
        "Phone Case": {"initial": 1600, "unit_cost": 2.0, "holding_cost": 0.08},
        "USB Cable": {"initial": 2200, "unit_cost": 1.25, "holding_cost": 0.05},
        "Desk Lamp": {"initial": 520, "unit_cost": 8.5, "holding_cost": 0.22},
    }
    months = ["Sep", "Oct", "Nov"]
    demand = {
        ("Phone Case", "Sep"): 1800,
        ("Phone Case", "Oct"): 2400,
        ("Phone Case", "Nov"): 3100,
        ("USB Cable", "Sep"): 2600,
        ("USB Cable", "Oct"): 3300,
        ("USB Cable", "Nov"): 4200,
        ("Desk Lamp", "Sep"): 720,
        ("Desk Lamp", "Oct"): 950,
        ("Desk Lamp", "Nov"): 1300,
    }
    cash_budget = {"Sep": 10500, "Oct": 11800, "Nov": 13500}
    payment_ratio_now = 0.60
    payment_ratio_next_month = 0.40
    warehouse_capacity = 7200
    target_ending_cover = 0.25
    shortage_penalty = 9.0

    model = Model(name="cross_border_cashflow_inventory")

    buy = {
        (sku, month): model.continuous_var(name=f"buy_{sku}_{month}", lb=0)
        for sku in skus
        for month in months
    }
    inventory = {
        (sku, month): model.continuous_var(name=f"inventory_{sku}_{month}", lb=0)
        for sku in skus
        for month in months
    }
    shortage = {
        (sku, month): model.continuous_var(name=f"shortage_{sku}_{month}", lb=0)
        for sku in skus
        for month in months
    }

    purchase_cost = model.sum(
        skus[sku]["unit_cost"] * buy[sku, month]
        for sku in skus
        for month in months
    )
    holding_cost = model.sum(
        skus[sku]["holding_cost"] * inventory[sku, month]
        for sku in skus
        for month in months
    )
    shortage_cost = model.sum(shortage_penalty * shortage[sku, month] for sku in skus for month in months)

    model.minimize(purchase_cost + holding_cost + shortage_cost)

    for sku, data in skus.items():
        for index, month in enumerate(months):
            previous_inventory = data["initial"] if index == 0 else inventory[sku, months[index - 1]]
            model.add_constraint(
                previous_inventory + buy[sku, month] + shortage[sku, month]
                == demand[sku, month] + inventory[sku, month],
                ctname=f"inventory_balance_{sku}_{month}",
            )

    for index, month in enumerate(months):
        current_month_payment = model.sum(
            payment_ratio_now * skus[sku]["unit_cost"] * buy[sku, month]
            for sku in skus
        )
        prior_month_payment = 0
        if index > 0:
            previous_month = months[index - 1]
            prior_month_payment = model.sum(
                payment_ratio_next_month * skus[sku]["unit_cost"] * buy[sku, previous_month]
                for sku in skus
            )
        model.add_constraint(
            current_month_payment + prior_month_payment <= cash_budget[month],
            ctname=f"cash_budget_{month}",
        )
        model.add_constraint(
            model.sum(inventory[sku, month] for sku in skus) <= warehouse_capacity,
            ctname=f"warehouse_capacity_{month}",
        )

    last_month = months[-1]
    for sku in skus:
        model.add_constraint(
            inventory[sku, last_month] >= target_ending_cover * demand[sku, last_month],
            ctname=f"ending_cover_{sku}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    plan = []
    cash_plan = []
    for month_index, month in enumerate(months):
        current_payment = sum(
            payment_ratio_now * skus[sku]["unit_cost"] * buy[sku, month].solution_value
            for sku in skus
        )
        prior_payment = 0
        if month_index > 0:
            previous_month = months[month_index - 1]
            prior_payment = sum(
                payment_ratio_next_month * skus[sku]["unit_cost"] * buy[sku, previous_month].solution_value
                for sku in skus
            )
        cash_plan.append(
            {
                "month": month,
                "cash_used": current_payment + prior_payment,
                "cash_budget": cash_budget[month],
            }
        )
        for sku in skus:
            plan.append(
                {
                    "sku": sku,
                    "month": month,
                    "buy": buy[sku, month].solution_value,
                    "demand": demand[sku, month],
                    "ending_inventory": inventory[sku, month].solution_value,
                    "shortage": shortage[sku, month].solution_value,
                }
            )

    return {
        "status": "optimal",
        "plan": plan,
        "cash_plan": cash_plan,
        "purchase_cost": purchase_cost.solution_value,
        "holding_cost": holding_cost.solution_value,
        "shortage_cost": shortage_cost.solution_value,
        "total_cost": solution.objective_value,
    }


def print_result(result):
    print("Cross-border cashflow inventory planning")
    print("========================================")
    print()
    print("Monthly cash")
    print("------------")
    for row in result["cash_plan"]:
        print(f"{row['month']}: cash_used={row['cash_used']:.0f}, budget={row['cash_budget']:.0f}")
    print()
    print("Purchase and inventory plan")
    print("---------------------------")
    for row in result["plan"]:
        print(
            f"{row['month']} {row['sku']:10} buy={row['buy']:7.0f}, "
            f"demand={row['demand']:5.0f}, ending={row['ending_inventory']:6.0f}, "
            f"shortage={row['shortage']:5.0f}"
        )
    print()
    print(f"Purchase cost: {result['purchase_cost']:.0f}")
    print(f"Holding cost: {result['holding_cost']:.0f}")
    print(f"Shortage cost: {result['shortage_cost']:.0f}")
    print(f"Total cost: {result['total_cost']:.0f}")


def main():
    print_result(solve_cashflow_inventory_case())


if __name__ == "__main__":
    main()
