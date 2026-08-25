from docplex.mp.model import Model


def solve_supplier_sourcing_case():
    skus = {
        "Phone Case": {"demand": 4200, "safety_stock": 500},
        "USB Cable": {"demand": 6800, "safety_stock": 800},
        "Desk Lamp": {"demand": 1800, "safety_stock": 300},
    }

    suppliers = {
        "Shenzhen_A": {
            "fixed_cost": 1800,
            "capacity": 6200,
            "min_order": 1200,
            "lead_time_days": 12,
            "reliability": 0.94,
            "unit_cost": {"Phone Case": 2.1, "USB Cable": 1.4, "Desk Lamp": 8.2},
        },
        "Ningbo_B": {
            "fixed_cost": 1300,
            "capacity": 5200,
            "min_order": 900,
            "lead_time_days": 18,
            "reliability": 0.90,
            "unit_cost": {"Phone Case": 2.0, "USB Cable": 1.35, "Desk Lamp": 8.6},
        },
        "Vietnam_C": {
            "fixed_cost": 2200,
            "capacity": 4200,
            "min_order": 1000,
            "lead_time_days": 24,
            "reliability": 0.86,
            "unit_cost": {"Phone Case": 1.8, "USB Cable": 1.2, "Desk Lamp": 7.6},
        },
        "Local_Backup": {
            "fixed_cost": 900,
            "capacity": 2400,
            "min_order": 300,
            "lead_time_days": 5,
            "reliability": 0.98,
            "unit_cost": {"Phone Case": 2.9, "USB Cable": 2.1, "Desk Lamp": 9.5},
        },
    }

    required_reliability = 0.91
    max_avg_lead_time = 16
    shortage_penalty = 18

    model = Model(name="cross_border_supplier_sourcing")

    use_supplier = {
        supplier: model.binary_var(name=f"use_{supplier}")
        for supplier in suppliers
    }
    buy = {
        (supplier, sku): model.continuous_var(name=f"buy_{supplier}_{sku}", lb=0)
        for supplier in suppliers
        for sku in skus
    }
    shortage = {
        sku: model.continuous_var(name=f"shortage_{sku}", lb=0)
        for sku in skus
    }

    purchase_cost = model.sum(
        suppliers[supplier]["unit_cost"][sku] * buy[supplier, sku]
        for supplier in suppliers
        for sku in skus
    )
    onboarding_cost = model.sum(
        suppliers[supplier]["fixed_cost"] * use_supplier[supplier]
        for supplier in suppliers
    )
    shortage_cost = model.sum(shortage_penalty * shortage[sku] for sku in skus)

    model.minimize(purchase_cost + onboarding_cost + shortage_cost)

    for sku, data in skus.items():
        model.add_constraint(
            model.sum(buy[supplier, sku] for supplier in suppliers) + shortage[sku]
            >= data["demand"] + data["safety_stock"],
            ctname=f"demand_plus_safety_stock_{sku}",
        )

    for supplier, data in suppliers.items():
        total_order = model.sum(buy[supplier, sku] for sku in skus)
        model.add_constraint(total_order <= data["capacity"] * use_supplier[supplier])
        model.add_constraint(total_order >= data["min_order"] * use_supplier[supplier])

    total_units = model.sum(buy[supplier, sku] for supplier in suppliers for sku in skus)
    model.add_constraint(
        model.sum(
            suppliers[supplier]["lead_time_days"] * buy[supplier, sku]
            for supplier in suppliers
            for sku in skus
        )
        <= max_avg_lead_time * total_units,
        ctname="weighted_average_lead_time",
    )
    model.add_constraint(
        model.sum(
            suppliers[supplier]["reliability"] * buy[supplier, sku]
            for supplier in suppliers
            for sku in skus
        )
        >= required_reliability * total_units,
        ctname="weighted_average_reliability",
    )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    allocation = []
    supplier_totals = {}
    sku_totals = {}
    for supplier in suppliers:
        total = sum(buy[supplier, sku].solution_value for sku in skus)
        if total > 1e-6:
            supplier_totals[supplier] = total
    for sku in skus:
        total = sum(buy[supplier, sku].solution_value for supplier in suppliers)
        sku_totals[sku] = total
        for supplier in suppliers:
            amount = buy[supplier, sku].solution_value
            if amount > 1e-6:
                allocation.append(
                    {
                        "supplier": supplier,
                        "sku": sku,
                        "units": amount,
                        "unit_cost": suppliers[supplier]["unit_cost"][sku],
                        "lead_time_days": suppliers[supplier]["lead_time_days"],
                        "reliability": suppliers[supplier]["reliability"],
                    }
                )

    bought_units = sum(supplier_totals.values())
    average_lead_time = sum(
        row["lead_time_days"] * row["units"] for row in allocation
    ) / bought_units
    average_reliability = sum(
        row["reliability"] * row["units"] for row in allocation
    ) / bought_units

    return {
        "status": "optimal",
        "allocation": allocation,
        "supplier_totals": supplier_totals,
        "sku_totals": sku_totals,
        "shortage": {
            sku: shortage[sku].solution_value
            for sku in skus
            if shortage[sku].solution_value > 1e-6
        },
        "purchase_cost": purchase_cost.solution_value,
        "onboarding_cost": onboarding_cost.solution_value,
        "shortage_cost": shortage_cost.solution_value,
        "total_cost": solution.objective_value,
        "average_lead_time": average_lead_time,
        "average_reliability": average_reliability,
    }


def print_result(result):
    print("Cross-border supplier sourcing")
    print("==============================")
    print()
    print("Supplier totals")
    print("---------------")
    for supplier, amount in result["supplier_totals"].items():
        print(f"- {supplier}: {amount:.0f} units")

    print()
    print("SKU allocation")
    print("--------------")
    for row in result["allocation"]:
        print(
            f"{row['sku']:10} <- {row['supplier']:13} "
            f"{row['units']:7.0f} units, "
            f"unit_cost={row['unit_cost']:4.2f}, "
            f"lead_time={row['lead_time_days']} days, "
            f"reliability={row['reliability']:.0%}"
        )

    print()
    print(f"Purchase cost: {result['purchase_cost']:.0f}")
    print(f"Supplier onboarding cost: {result['onboarding_cost']:.0f}")
    print(f"Shortage cost: {result['shortage_cost']:.0f}")
    print(f"Total cost: {result['total_cost']:.0f}")
    print(f"Average lead time: {result['average_lead_time']:.1f} days")
    print(f"Average reliability: {result['average_reliability']:.1%}")
    print(f"Shortage: {result['shortage'] or 'none'}")


def main():
    print_result(solve_supplier_sourcing_case())


if __name__ == "__main__":
    main()
