from docplex.mp.model import Model


def solve_packaging_case():
    order_types = {
        "Phone Case single": {"orders": 2600, "item_weight": 0.12, "item_volume": 0.25, "fragile": 0},
        "Earbuds single": {"orders": 1100, "item_weight": 0.28, "item_volume": 0.45, "fragile": 1},
        "Desk Lamp single": {"orders": 720, "item_weight": 1.8, "item_volume": 4.8, "fragile": 1},
        "Mixed small bundle": {"orders": 900, "item_weight": 0.75, "item_volume": 1.3, "fragile": 0},
    }

    boxes = {
        "poly_mailer": {"volume": 0.8, "max_weight": 0.7, "pack_cost": 0.18, "damage_rate": 0.035},
        "small_box": {"volume": 1.6, "max_weight": 1.2, "pack_cost": 0.42, "damage_rate": 0.018},
        "padded_box": {"volume": 3.2, "max_weight": 2.4, "pack_cost": 0.72, "damage_rate": 0.010},
        "large_box": {"volume": 6.4, "max_weight": 4.0, "pack_cost": 1.05, "damage_rate": 0.012},
    }

    carrier_rate_per_kg = 3.8
    dimensional_weight_factor = 0.22
    damage_penalty = 18
    max_damage_rate = 0.018

    model = Model(name="cross_border_packaging_optimization")

    assign = {
        (order_type, box): model.continuous_var(name=f"assign_{order_type}_{box}", lb=0)
        for order_type in order_types
        for box in boxes
    }

    shipping_cost = model.sum(
        carrier_rate_per_kg
        * max(order_types[order_type]["item_weight"], boxes[box]["volume"] * dimensional_weight_factor)
        * assign[order_type, box]
        for order_type in order_types
        for box in boxes
    )
    packaging_cost = model.sum(
        boxes[box]["pack_cost"] * assign[order_type, box]
        for order_type in order_types
        for box in boxes
    )
    expected_damage_cost = model.sum(
        damage_penalty
        * boxes[box]["damage_rate"]
        * (1.8 if order_types[order_type]["fragile"] else 1.0)
        * assign[order_type, box]
        for order_type in order_types
        for box in boxes
    )

    model.minimize(shipping_cost + packaging_cost + expected_damage_cost)

    for order_type, data in order_types.items():
        model.add_constraint(
            model.sum(assign[order_type, box] for box in boxes) == data["orders"],
            ctname=f"orders_{order_type}",
        )
        for box, box_data in boxes.items():
            if data["item_volume"] > box_data["volume"] or data["item_weight"] > box_data["max_weight"]:
                model.add_constraint(assign[order_type, box] == 0, ctname=f"fit_{order_type}_{box}")

    total_orders = sum(data["orders"] for data in order_types.values())
    model.add_constraint(
        model.sum(
            boxes[box]["damage_rate"]
            * (1.8 if order_types[order_type]["fragile"] else 1.0)
            * assign[order_type, box]
            for order_type in order_types
            for box in boxes
        )
        <= max_damage_rate * total_orders,
        ctname="portfolio_damage_rate",
    )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    plan = []
    box_totals = {}
    for order_type in order_types:
        for box in boxes:
            amount = assign[order_type, box].solution_value
            if amount > 1e-6:
                billable_weight = max(
                    order_types[order_type]["item_weight"],
                    boxes[box]["volume"] * dimensional_weight_factor,
                )
                box_totals[box] = box_totals.get(box, 0) + amount
                plan.append(
                    {
                        "order_type": order_type,
                        "box": box,
                        "orders": amount,
                        "billable_weight": billable_weight,
                        "pack_cost": boxes[box]["pack_cost"],
                        "damage_rate": boxes[box]["damage_rate"]
                        * (1.8 if order_types[order_type]["fragile"] else 1.0),
                    }
                )

    expected_damage_rate = sum(
        row["damage_rate"] * row["orders"] for row in plan
    ) / total_orders

    return {
        "status": "optimal",
        "plan": plan,
        "box_totals": box_totals,
        "shipping_cost": shipping_cost.solution_value,
        "packaging_cost": packaging_cost.solution_value,
        "expected_damage_cost": expected_damage_cost.solution_value,
        "expected_damage_rate": expected_damage_rate,
        "total_cost": solution.objective_value,
    }


def print_result(result):
    print("Cross-border packaging optimization")
    print("===================================")
    print()
    print("Box totals")
    print("----------")
    for box, amount in result["box_totals"].items():
        print(f"- {box}: {amount:.0f} orders")
    print()
    print("Packaging plan")
    print("--------------")
    for row in result["plan"]:
        print(
            f"{row['order_type']:18} -> {row['box']:11} "
            f"{row['orders']:6.0f} orders, billable_weight={row['billable_weight']:.2f}, "
            f"damage_rate={row['damage_rate']:.1%}"
        )
    print()
    print(f"Shipping cost: {result['shipping_cost']:.0f}")
    print(f"Packaging cost: {result['packaging_cost']:.0f}")
    print(f"Expected damage cost: {result['expected_damage_cost']:.0f}")
    print(f"Expected damage rate: {result['expected_damage_rate']:.1%}")
    print(f"Total cost: {result['total_cost']:.0f}")


def main():
    print_result(solve_packaging_case())


if __name__ == "__main__":
    main()
