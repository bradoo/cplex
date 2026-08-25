from docplex.mp.model import Model


def solve_wave_picking_case():
    waves = ["morning", "midday", "afternoon", "evening"]
    order_groups = {
        "marketplace_priority": {
            "orders": 900,
            "pick_hours": 18,
            "pack_hours": 16,
            "due_wave": "midday",
            "late_penalty": 9.0,
        },
        "standard_dtc": {
            "orders": 1300,
            "pick_hours": 24,
            "pack_hours": 22,
            "due_wave": "afternoon",
            "late_penalty": 4.5,
        },
        "tiktok_flash_sale": {
            "orders": 1100,
            "pick_hours": 30,
            "pack_hours": 24,
            "due_wave": "evening",
            "late_penalty": 6.0,
        },
        "wholesale_cases": {
            "orders": 620,
            "pick_hours": 16,
            "pack_hours": 10,
            "due_wave": "evening",
            "late_penalty": 2.0,
        },
    }

    pick_capacity = {"morning": 28, "midday": 24, "afternoon": 24, "evening": 10}
    pack_capacity = {"morning": 22, "midday": 20, "afternoon": 20, "evening": 12}
    overtime_cost = {"pick": 42, "pack": 38}
    max_overtime = {"pick": 8, "pack": 7}
    wave_index = {wave: index for index, wave in enumerate(waves)}

    model = Model(name="cross_border_wave_picking")

    assign = {
        (group, wave): model.binary_var(name=f"assign_{group}_{wave}")
        for group in order_groups
        for wave in waves
    }
    pick_overtime = {
        wave: model.continuous_var(name=f"pick_overtime_{wave}", lb=0, ub=max_overtime["pick"])
        for wave in waves
    }
    pack_overtime = {
        wave: model.continuous_var(name=f"pack_overtime_{wave}", lb=0, ub=max_overtime["pack"])
        for wave in waves
    }
    late_orders = {
        group: model.continuous_var(name=f"late_orders_{group}", lb=0)
        for group in order_groups
    }

    late_penalty = model.sum(
        order_groups[group]["late_penalty"] * late_orders[group]
        for group in order_groups
    )
    overtime_total_cost = model.sum(
        overtime_cost["pick"] * pick_overtime[wave]
        + overtime_cost["pack"] * pack_overtime[wave]
        for wave in waves
    )

    model.minimize(late_penalty + overtime_total_cost)

    for group in order_groups:
        model.add_constraint(
            model.sum(assign[group, wave] for wave in waves) == 1,
            ctname=f"one_wave_{group}",
        )
        due_index = wave_index[order_groups[group]["due_wave"]]
        model.add_constraint(
            late_orders[group]
            == order_groups[group]["orders"]
            * model.sum(assign[group, wave] for wave in waves if wave_index[wave] > due_index),
            ctname=f"late_if_after_due_{group}",
        )

    for wave in waves:
        model.add_constraint(
            model.sum(order_groups[group]["pick_hours"] * assign[group, wave] for group in order_groups)
            <= pick_capacity[wave] + pick_overtime[wave],
            ctname=f"pick_capacity_{wave}",
        )
        model.add_constraint(
            model.sum(order_groups[group]["pack_hours"] * assign[group, wave] for group in order_groups)
            <= pack_capacity[wave] + pack_overtime[wave],
            ctname=f"pack_capacity_{wave}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    wave_plan = []
    for group, data in order_groups.items():
        selected_wave = next(wave for wave in waves if assign[group, wave].solution_value > 0.5)
        wave_plan.append(
            {
                "order_group": group,
                "wave": selected_wave,
                "orders": data["orders"],
                "due_wave": data["due_wave"],
                "late_orders": late_orders[group].solution_value,
                "pick_hours": data["pick_hours"],
                "pack_hours": data["pack_hours"],
            }
        )

    capacity_plan = []
    for wave in waves:
        used_pick = sum(order_groups[group]["pick_hours"] * assign[group, wave].solution_value for group in order_groups)
        used_pack = sum(order_groups[group]["pack_hours"] * assign[group, wave].solution_value for group in order_groups)
        capacity_plan.append(
            {
                "wave": wave,
                "pick_hours": used_pick,
                "pick_capacity": pick_capacity[wave],
                "pick_overtime": pick_overtime[wave].solution_value,
                "pack_hours": used_pack,
                "pack_capacity": pack_capacity[wave],
                "pack_overtime": pack_overtime[wave].solution_value,
            }
        )

    return {
        "status": "optimal",
        "wave_plan": wave_plan,
        "capacity_plan": capacity_plan,
        "late_penalty": late_penalty.solution_value,
        "overtime_cost": overtime_total_cost.solution_value,
        "total_cost": solution.objective_value,
    }


def print_result(result):
    print("Cross-border wave picking and packing")
    print("=====================================")
    print()
    print("Wave plan")
    print("---------")
    for row in result["wave_plan"]:
        print(
            f"{row['order_group']:20} -> {row['wave']:9} "
            f"orders={row['orders']:5.0f}, due={row['due_wave']:9}, "
            f"late={row['late_orders']:5.0f}"
        )
    print()
    print("Capacity plan")
    print("-------------")
    for row in result["capacity_plan"]:
        print(
            f"{row['wave']:9} pick={row['pick_hours']:4.1f}/{row['pick_capacity']:4.1f} "
            f"ot={row['pick_overtime']:3.1f}, "
            f"pack={row['pack_hours']:4.1f}/{row['pack_capacity']:4.1f} "
            f"ot={row['pack_overtime']:3.1f}"
        )
    print()
    print(f"Late penalty: {result['late_penalty']:.0f}")
    print(f"Overtime cost: {result['overtime_cost']:.0f}")
    print(f"Total warehouse execution cost: {result['total_cost']:.0f}")


def main():
    print_result(solve_wave_picking_case())


if __name__ == "__main__":
    main()
