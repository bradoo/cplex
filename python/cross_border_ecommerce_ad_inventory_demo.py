from docplex.mp.model import Model


def solve_ad_inventory_case():
    skus = {
        "Phone Case": {
            "inventory": 4200,
            "base_sales": 1800,
            "unit_margin": 8.5,
            "fulfillment_capacity": 3600,
        },
        "Desk Lamp": {
            "inventory": 1100,
            "base_sales": 520,
            "unit_margin": 18.0,
            "fulfillment_capacity": 950,
        },
        "Yoga Mat": {
            "inventory": 1900,
            "base_sales": 820,
            "unit_margin": 12.5,
            "fulfillment_capacity": 1600,
        },
        "Earbuds": {
            "inventory": 900,
            "base_sales": 430,
            "unit_margin": 24.0,
            "fulfillment_capacity": 820,
        },
    }

    ad_levels = {
        "none": {"budget": 0, "extra_sales": 0, "brand_lift": 0},
        "test": {"budget": 800, "extra_sales": 180, "brand_lift": 250},
        "standard": {"budget": 1800, "extra_sales": 420, "brand_lift": 650},
        "aggressive": {"budget": 3600, "extra_sales": 780, "brand_lift": 1050},
    }

    total_ad_budget = 7200
    max_aggressive_campaigns = 2

    model = Model(name="cross_border_ad_inventory")

    choose = {
        (sku, level): model.binary_var(name=f"choose_{sku}_{level}")
        for sku in skus
        for level in ad_levels
    }
    fulfilled = {
        sku: model.continuous_var(name=f"fulfilled_{sku}", lb=0)
        for sku in skus
    }
    lost_sales = {
        sku: model.continuous_var(name=f"lost_sales_{sku}", lb=0)
        for sku in skus
    }

    ad_spend = model.sum(
        ad_levels[level]["budget"] * choose[sku, level]
        for sku in skus
        for level in ad_levels
    )
    gross_profit = model.sum(skus[sku]["unit_margin"] * fulfilled[sku] for sku in skus)
    brand_lift = model.sum(
        ad_levels[level]["brand_lift"] * choose[sku, level]
        for sku in skus
        for level in ad_levels
    )
    lost_sales_penalty = model.sum(6 * lost_sales[sku] for sku in skus)

    model.maximize(gross_profit + brand_lift - ad_spend - lost_sales_penalty)

    for sku, data in skus.items():
        model.add_constraint(
            model.sum(choose[sku, level] for level in ad_levels) == 1,
            ctname=f"one_ad_level_{sku}",
        )
        expected_sales = data["base_sales"] + model.sum(
            ad_levels[level]["extra_sales"] * choose[sku, level]
            for level in ad_levels
        )
        model.add_constraint(
            fulfilled[sku] + lost_sales[sku] == expected_sales,
            ctname=f"sales_balance_{sku}",
        )
        model.add_constraint(fulfilled[sku] <= data["inventory"], ctname=f"inventory_{sku}")
        model.add_constraint(
            fulfilled[sku] <= data["fulfillment_capacity"],
            ctname=f"fulfillment_capacity_{sku}",
        )

    model.add_constraint(ad_spend <= total_ad_budget, ctname="ad_budget")
    model.add_constraint(
        model.sum(choose[sku, "aggressive"] for sku in skus) <= max_aggressive_campaigns,
        ctname="max_aggressive_campaigns",
    )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    plan = []
    for sku, data in skus.items():
        selected_level = next(level for level in ad_levels if choose[sku, level].solution_value > 0.5)
        expected = data["base_sales"] + ad_levels[selected_level]["extra_sales"]
        plan.append(
            {
                "sku": sku,
                "ad_level": selected_level,
                "ad_budget": ad_levels[selected_level]["budget"],
                "expected_sales": expected,
                "fulfilled": fulfilled[sku].solution_value,
                "lost_sales": lost_sales[sku].solution_value,
                "inventory": data["inventory"],
                "unit_margin": data["unit_margin"],
            }
        )

    return {
        "status": "optimal",
        "plan": plan,
        "ad_spend": ad_spend.solution_value,
        "gross_profit": gross_profit.solution_value,
        "brand_lift": brand_lift.solution_value,
        "lost_sales_penalty": lost_sales_penalty.solution_value,
        "net_contribution": solution.objective_value,
        "budget_limit": total_ad_budget,
    }


def print_result(result):
    print("Cross-border ad and inventory planning")
    print("======================================")
    print()
    print("Campaign plan")
    print("-------------")
    for row in result["plan"]:
        print(
            f"{row['sku']:10} ad={row['ad_level']:10} "
            f"budget={row['ad_budget']:4.0f}, expected={row['expected_sales']:5.0f}, "
            f"fulfilled={row['fulfilled']:5.0f}, lost={row['lost_sales']:5.0f}, "
            f"inventory={row['inventory']:5.0f}"
        )
    print()
    print(f"Ad spend: {result['ad_spend']:.0f}")
    print(f"Gross profit: {result['gross_profit']:.0f}")
    print(f"Brand lift: {result['brand_lift']:.0f}")
    print(f"Lost sales penalty: {result['lost_sales_penalty']:.0f}")
    print(f"Budget limit: {result['budget_limit']:.0f}")
    print(f"Net contribution: {result['net_contribution']:.0f}")


def main():
    print_result(solve_ad_inventory_case())


if __name__ == "__main__":
    main()
