from docplex.mp.model import Model


def solve_support_staffing_case():
    shifts = {
        "Asia_morning": {"capacity_hours": 6, "base_cost": 95, "overtime_cost": 38},
        "EU_afternoon": {"capacity_hours": 6, "base_cost": 105, "overtime_cost": 42},
        "US_evening": {"capacity_hours": 6, "base_cost": 115, "overtime_cost": 46},
    }

    agents = {
        "Alice": {"languages": ["EN"], "max_shifts": 2},
        "Ben": {"languages": ["EN", "DE"], "max_shifts": 2},
        "Chen": {"languages": ["EN", "ZH"], "max_shifts": 2},
        "Dora": {"languages": ["EN", "FR"], "max_shifts": 2},
        "Eva": {"languages": ["EN", "DE", "FR"], "max_shifts": 2},
        "Frank": {"languages": ["EN", "ZH"], "max_shifts": 2},
    }

    work = {
        ("Asia_morning", "EN"): 14,
        ("Asia_morning", "ZH"): 10,
        ("Asia_morning", "DE"): 2,
        ("Asia_morning", "FR"): 1,
        ("EU_afternoon", "EN"): 18,
        ("EU_afternoon", "ZH"): 3,
        ("EU_afternoon", "DE"): 8,
        ("EU_afternoon", "FR"): 7,
        ("US_evening", "EN"): 24,
        ("US_evening", "ZH"): 4,
        ("US_evening", "DE"): 4,
        ("US_evening", "FR"): 3,
    }

    languages = sorted({language for _, language in work})
    outsource_cost_per_hour = {"EN": 32, "ZH": 36, "DE": 44, "FR": 42}
    max_outsource_share = 0.28

    model = Model(name="cross_border_support_staffing")

    assign = {
        (agent, shift): model.binary_var(name=f"assign_{agent}_{shift}")
        for agent in agents
        for shift in shifts
    }
    handled = {
        (agent, shift, language): model.continuous_var(
            name=f"handled_{agent}_{shift}_{language}", lb=0
        )
        for agent in agents
        for shift in shifts
        for language in languages
    }
    overtime = {
        (agent, shift): model.continuous_var(name=f"overtime_{agent}_{shift}", lb=0, ub=2)
        for agent in agents
        for shift in shifts
    }
    outsource = {
        (shift, language): model.continuous_var(name=f"outsource_{shift}_{language}", lb=0)
        for shift in shifts
        for language in languages
    }

    labor_cost = model.sum(
        shifts[shift]["base_cost"] * assign[agent, shift]
        + shifts[shift]["overtime_cost"] * overtime[agent, shift]
        for agent in agents
        for shift in shifts
    )
    outsource_cost = model.sum(
        outsource_cost_per_hour[language] * outsource[shift, language]
        for shift in shifts
        for language in languages
    )

    model.minimize(labor_cost + outsource_cost)

    for shift in shifts:
        for language in languages:
            model.add_constraint(
                model.sum(handled[agent, shift, language] for agent in agents)
                + outsource[shift, language]
                >= work[shift, language],
                ctname=f"workload_{shift}_{language}",
            )

    for agent, data in agents.items():
        model.add_constraint(
            model.sum(assign[agent, shift] for shift in shifts) <= data["max_shifts"],
            ctname=f"max_shifts_{agent}",
        )
        for shift, shift_data in shifts.items():
            model.add_constraint(
                model.sum(handled[agent, shift, language] for language in languages)
                <= shift_data["capacity_hours"] * assign[agent, shift] + overtime[agent, shift],
                ctname=f"agent_capacity_{agent}_{shift}",
            )
            model.add_constraint(
                overtime[agent, shift] <= 2 * assign[agent, shift],
                ctname=f"overtime_if_assigned_{agent}_{shift}",
            )
            for language in languages:
                if language not in data["languages"]:
                    model.add_constraint(
                        handled[agent, shift, language] == 0,
                        ctname=f"language_skill_{agent}_{shift}_{language}",
                    )

    total_work = sum(work.values())
    model.add_constraint(
        model.sum(outsource[shift, language] for shift in shifts for language in languages)
        <= max_outsource_share * total_work,
        ctname="max_outsource_share",
    )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    shift_plan = []
    workload_plan = []
    for shift in shifts:
        for agent in agents:
            if assign[agent, shift].solution_value > 0.5:
                total_handled = sum(handled[agent, shift, language].solution_value for language in languages)
                shift_plan.append(
                    {
                        "shift": shift,
                        "agent": agent,
                        "hours": total_handled,
                        "overtime": overtime[agent, shift].solution_value,
                    }
                )
        for language in languages:
            internal = sum(handled[agent, shift, language].solution_value for agent in agents)
            outsourced = outsource[shift, language].solution_value
            workload_plan.append(
                {
                    "shift": shift,
                    "language": language,
                    "required_hours": work[shift, language],
                    "internal_hours": internal,
                    "outsourced_hours": outsourced,
                }
            )

    return {
        "status": "optimal",
        "shift_plan": shift_plan,
        "workload_plan": workload_plan,
        "labor_cost": labor_cost.solution_value,
        "outsource_cost": outsource_cost.solution_value,
        "total_cost": solution.objective_value,
    }


def print_result(result):
    print("Cross-border support staffing")
    print("=============================")
    print()
    print("Agent shift plan")
    print("----------------")
    for row in result["shift_plan"]:
        print(
            f"{row['shift']:13} {row['agent']:5} "
            f"hours={row['hours']:4.1f}, overtime={row['overtime']:3.1f}"
        )
    print()
    print("Workload coverage")
    print("-----------------")
    for row in result["workload_plan"]:
        if row["required_hours"] <= 0:
            continue
        print(
            f"{row['shift']:13} {row['language']} required={row['required_hours']:4.1f}, "
            f"internal={row['internal_hours']:4.1f}, outsource={row['outsourced_hours']:4.1f}"
        )
    print()
    print(f"Labor cost: {result['labor_cost']:.0f}")
    print(f"Outsource cost: {result['outsource_cost']:.0f}")
    print(f"Total support cost: {result['total_cost']:.0f}")


def main():
    print_result(solve_support_staffing_case())


if __name__ == "__main__":
    main()
