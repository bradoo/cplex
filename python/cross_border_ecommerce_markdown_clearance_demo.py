from docplex.mp.model import Model


def solve_markdown_clearance_case():
    skus = {
        "Winter Coat": {
            "inventory": 1800,
            "base_demand": 650,
            "price": 68,
            "unit_cost": 31,
            "holding_cost": 4.5,
            "demand_lift": {"full_price": 1.00, "light_10": 1.15, "medium_20": 1.65, "deep_30": 2.45},
        },
        "Phone Case": {
            "inventory": 5200,
            "base_demand": 2600,
            "price": 14,
            "unit_cost": 4.2,
            "holding_cost": 0.7,
            "demand_lift": {"full_price": 1.00, "light_10": 1.35, "medium_20": 1.55, "deep_30": 1.75},
        },
        "Desk Lamp": {
            "inventory": 1600,
            "base_demand": 780,
            "price": 42,
            "unit_cost": 19,
            "holding_cost": 2.2,
            "demand_lift": {"full_price": 1.00, "light_10": 1.18, "medium_20": 1.50, "deep_30": 1.95},
        },
        "Yoga Mat": {
            "inventory": 2400,
            "base_demand": 1100,
            "price": 26,
            "unit_cost": 9.5,
            "holding_cost": 1.4,
            "demand_lift": {"full_price": 1.00, "light_10": 1.22, "medium_20": 1.70, "deep_30": 2.05},
        },
    }

    discount_levels = {
        "full_price": {"discount": 0.00, "brand_penalty": 0},
        "light_10": {"discount": 0.10, "brand_penalty": 300},
        "medium_20": {"discount": 0.20, "brand_penalty": 1000},
        "deep_30": {"discount": 0.30, "brand_penalty": 2600},
    }

    warehouse_capacity_after_clearance = 3900

    model = Model(name="cross_border_markdown_clearance")

    choose = {
        (sku, level): model.binary_var(name=f"choose_{sku}_{level}")
        for sku in skus
        for level in discount_levels
    }
    sell = {
        (sku, level): model.continuous_var(name=f"sell_{sku}_{level}", lb=0)
        for sku in skus
        for level in discount_levels
    }
    leftover = {
        sku: model.continuous_var(name=f"leftover_{sku}", lb=0)
        for sku in skus
    }

    revenue = model.sum(
        skus[sku]["price"] * (1 - discount_levels[level]["discount"]) * sell[sku, level]
        for sku in skus
        for level in discount_levels
    )
    product_cost = model.sum(
        skus[sku]["unit_cost"] * sell[sku, level]
        for sku in skus
        for level in discount_levels
    )
    holding_cost = model.sum(
        skus[sku]["holding_cost"] * leftover[sku]
        for sku in skus
    )
    brand_penalty = model.sum(
        discount_levels[level]["brand_penalty"] * choose[sku, level]
        for sku in skus
        for level in discount_levels
    )

    model.maximize(revenue - product_cost - holding_cost - brand_penalty)

    for sku, data in skus.items():
        model.add_constraint(
            model.sum(choose[sku, level] for level in discount_levels) == 1,
            ctname=f"one_discount_{sku}",
        )
        model.add_constraint(
            model.sum(sell[sku, level] for level in discount_levels) + leftover[sku]
            == data["inventory"],
            ctname=f"inventory_balance_{sku}",
        )
        for level, discount_data in discount_levels.items():
            max_sales = data["base_demand"] * data["demand_lift"][level]
            model.add_constraint(
                sell[sku, level] <= max_sales * choose[sku, level],
                ctname=f"demand_under_discount_{sku}_{level}",
            )

    model.add_constraint(
        model.sum(leftover[sku] for sku in skus) <= warehouse_capacity_after_clearance,
        ctname="post_clearance_capacity",
    )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    plan = []
    for sku, data in skus.items():
        selected_level = next(
            level for level in discount_levels if choose[sku, level].solution_value > 0.5
        )
        sold_units = sell[sku, selected_level].solution_value
        plan.append(
            {
                "sku": sku,
                "discount_level": selected_level,
                "discount": discount_levels[selected_level]["discount"],
                "inventory": data["inventory"],
                "sold_units": sold_units,
                "leftover_units": leftover[sku].solution_value,
                "net_unit_price": data["price"] * (1 - discount_levels[selected_level]["discount"]),
            }
        )

    return {
        "status": "optimal",
        "plan": plan,
        "revenue": revenue.solution_value,
        "product_cost": product_cost.solution_value,
        "holding_cost": holding_cost.solution_value,
        "brand_penalty": brand_penalty.solution_value,
        "net_contribution": solution.objective_value,
        "ending_inventory": sum(leftover[sku].solution_value for sku in skus),
        "capacity_limit": warehouse_capacity_after_clearance,
    }


def print_result(result):
    print("Cross-border markdown clearance")
    print("===============================")
    print()
    print("Markdown plan")
    print("-------------")
    for row in result["plan"]:
        print(
            f"{row['sku']:12} discount={row['discount']:.0%}, "
            f"sold={row['sold_units']:7.0f}, leftover={row['leftover_units']:7.0f}, "
            f"net_price={row['net_unit_price']:5.2f}"
        )
    print()
    print(f"Revenue: {result['revenue']:.0f}")
    print(f"Product cost: {result['product_cost']:.0f}")
    print(f"Holding cost: {result['holding_cost']:.0f}")
    print(f"Brand penalty: {result['brand_penalty']:.0f}")
    print(f"Ending inventory: {result['ending_inventory']:.0f}")
    print(f"Capacity limit: {result['capacity_limit']:.0f}")
    print(f"Net contribution: {result['net_contribution']:.0f}")


def main():
    print_result(solve_markdown_clearance_case())


if __name__ == "__main__":
    main()
