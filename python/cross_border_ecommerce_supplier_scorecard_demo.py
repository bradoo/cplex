from docplex.mp.model import Model


def solve_supplier_scorecard_case():
    skus = {
        "Phone Case": {"demand": 3600, "safety_stock": 500},
        "USB Cable": {"demand": 5200, "safety_stock": 700},
        "Desk Lamp": {"demand": 1600, "safety_stock": 300},
    }

    suppliers = {
        "Shenzhen_A": {
            "unit_cost": {"Phone Case": 2.2, "USB Cable": 1.45, "Desk Lamp": 8.3},
            "capacity": 5600,
            "min_order": 1000,
            "fixed_cost": 1800,
            "history_orders": 42,
            "history_amount": 186000,
            "last_purchase_months": 1,
            "overall_rating": 4,
            "risk_score": 4,
            "location_weather": 3,
            "reliability": 4,
            "after_sales": 4,
            "on_time_delivery": 4,
            "quick_response": 5,
        },
        "Ningbo_B": {
            "unit_cost": {"Phone Case": 2.0, "USB Cable": 1.35, "Desk Lamp": 8.8},
            "capacity": 5200,
            "min_order": 900,
            "fixed_cost": 1300,
            "history_orders": 28,
            "history_amount": 124000,
            "last_purchase_months": 3,
            "overall_rating": 4,
            "risk_score": 3,
            "location_weather": 4,
            "reliability": 3,
            "after_sales": 3,
            "on_time_delivery": 3,
            "quick_response": 3,
        },
        "Vietnam_C": {
            "unit_cost": {"Phone Case": 1.75, "USB Cable": 1.18, "Desk Lamp": 7.5},
            "capacity": 4600,
            "min_order": 1000,
            "fixed_cost": 2200,
            "history_orders": 9,
            "history_amount": 42000,
            "last_purchase_months": 8,
            "overall_rating": 3,
            "risk_score": 2,
            "location_weather": 2,
            "reliability": 3,
            "after_sales": 2,
            "on_time_delivery": 2,
            "quick_response": 2,
        },
        "Local_Backup": {
            "unit_cost": {"Phone Case": 2.9, "USB Cable": 2.05, "Desk Lamp": 9.4},
            "capacity": 2600,
            "min_order": 300,
            "fixed_cost": 900,
            "history_orders": 18,
            "history_amount": 91000,
            "last_purchase_months": 1,
            "overall_rating": 5,
            "risk_score": 5,
            "location_weather": 5,
            "reliability": 5,
            "after_sales": 5,
            "on_time_delivery": 5,
            "quick_response": 5,
        },
    }

    minimum_scores = {
        "overall_rating": 3,
        "risk_score": 3,
        "reliability": 3,
        "on_time_delivery": 3,
        "quick_response": 3,
    }
    max_single_supplier_share = 0.48
    quality_risk_penalty = 0.55
    service_bonus = 0.18
    shortage_penalty = 20

    eligible_suppliers = {
        supplier: data
        for supplier, data in suppliers.items()
        if all(data[field] >= score for field, score in minimum_scores.items())
    }

    model = Model(name="cross_border_supplier_scorecard")

    use_supplier = {
        supplier: model.binary_var(name=f"use_{supplier}")
        for supplier in eligible_suppliers
    }
    buy = {
        (supplier, sku): model.continuous_var(name=f"buy_{supplier}_{sku}", lb=0)
        for supplier in eligible_suppliers
        for sku in skus
    }
    shortage = {
        sku: model.continuous_var(name=f"shortage_{sku}", lb=0)
        for sku in skus
    }

    purchase_cost = model.sum(
        eligible_suppliers[supplier]["unit_cost"][sku] * buy[supplier, sku]
        for supplier in eligible_suppliers
        for sku in skus
    )
    fixed_cost = model.sum(
        eligible_suppliers[supplier]["fixed_cost"] * use_supplier[supplier]
        for supplier in eligible_suppliers
    )
    risk_cost = model.sum(
        quality_risk_penalty
        * (5 - eligible_suppliers[supplier]["risk_score"])
        * buy[supplier, sku]
        for supplier in eligible_suppliers
        for sku in skus
    )
    weather_risk_cost = model.sum(
        0.35
        * (5 - eligible_suppliers[supplier]["location_weather"])
        * buy[supplier, sku]
        for supplier in eligible_suppliers
        for sku in skus
    )
    service_credit = model.sum(
        service_bonus
        * (
            eligible_suppliers[supplier]["after_sales"]
            + eligible_suppliers[supplier]["quick_response"]
            + eligible_suppliers[supplier]["on_time_delivery"]
        )
        * buy[supplier, sku]
        for supplier in eligible_suppliers
        for sku in skus
    )
    shortage_cost = model.sum(shortage_penalty * shortage[sku] for sku in skus)

    model.minimize(
        purchase_cost
        + fixed_cost
        + risk_cost
        + weather_risk_cost
        + shortage_cost
        - service_credit
    )

    total_required_units = sum(data["demand"] + data["safety_stock"] for data in skus.values())

    for sku, data in skus.items():
        model.add_constraint(
            model.sum(buy[supplier, sku] for supplier in eligible_suppliers) + shortage[sku]
            >= data["demand"] + data["safety_stock"],
            ctname=f"demand_plus_safety_stock_{sku}",
        )

    for supplier, data in eligible_suppliers.items():
        supplier_total = model.sum(buy[supplier, sku] for sku in skus)
        model.add_constraint(supplier_total <= data["capacity"] * use_supplier[supplier])
        model.add_constraint(supplier_total >= data["min_order"] * use_supplier[supplier])
        model.add_constraint(
            supplier_total <= max_single_supplier_share * total_required_units,
            ctname=f"single_supplier_share_{supplier}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    allocation = []
    supplier_totals = {}
    for supplier, data in eligible_suppliers.items():
        total = sum(buy[supplier, sku].solution_value for sku in skus)
        if total > 1e-6:
            supplier_totals[supplier] = {
                "units": total,
                "overall_rating": data["overall_rating"],
                "risk_score": data["risk_score"],
                "location_weather": data["location_weather"],
                "reliability": data["reliability"],
                "after_sales": data["after_sales"],
                "on_time_delivery": data["on_time_delivery"],
                "quick_response": data["quick_response"],
                "history_orders": data["history_orders"],
                "last_purchase_months": data["last_purchase_months"],
            }
        for sku in skus:
            amount = buy[supplier, sku].solution_value
            if amount > 1e-6:
                allocation.append(
                    {
                        "supplier": supplier,
                        "sku": sku,
                        "units": amount,
                        "unit_cost": data["unit_cost"][sku],
                    }
                )

    rejected_suppliers = sorted(set(suppliers) - set(eligible_suppliers))

    return {
        "status": "optimal",
        "allocation": allocation,
        "supplier_totals": supplier_totals,
        "rejected_suppliers": rejected_suppliers,
        "purchase_cost": purchase_cost.solution_value,
        "fixed_cost": fixed_cost.solution_value,
        "risk_cost": risk_cost.solution_value,
        "weather_risk_cost": weather_risk_cost.solution_value,
        "service_credit": service_credit.solution_value,
        "shortage_cost": shortage_cost.solution_value,
        "total_score_cost": solution.objective_value,
    }


def print_result(result):
    print("Cross-border supplier scorecard sourcing")
    print("========================================")
    print()
    print("Rejected suppliers")
    print("------------------")
    print(", ".join(result["rejected_suppliers"]) or "none")
    print()
    print("Supplier totals")
    print("---------------")
    for supplier, data in result["supplier_totals"].items():
        print(
            f"- {supplier}: {data['units']:.0f} units, "
            f"rating={data['overall_rating']}/5, risk={data['risk_score']}/5, "
            f"weather={data['location_weather']}/5, on_time={data['on_time_delivery']}/5"
        )
    print()
    print("SKU allocation")
    print("--------------")
    for row in result["allocation"]:
        print(
            f"{row['sku']:10} <- {row['supplier']:12} "
            f"{row['units']:7.0f} units, unit_cost={row['unit_cost']:4.2f}"
        )
    print()
    print(f"Purchase cost: {result['purchase_cost']:.0f}")
    print(f"Fixed supplier cost: {result['fixed_cost']:.0f}")
    print(f"Quality/legal risk cost: {result['risk_cost']:.0f}")
    print(f"Weather/location risk cost: {result['weather_risk_cost']:.0f}")
    print(f"Service and response credit: {result['service_credit']:.0f}")
    print(f"Shortage cost: {result['shortage_cost']:.0f}")
    print(f"Total score-adjusted cost: {result['total_score_cost']:.0f}")


def main():
    print_result(solve_supplier_scorecard_case())


if __name__ == "__main__":
    main()
