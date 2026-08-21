from scheduling_solver import default_problem, solve_staff_scheduling


def solve_case(name, cost_weight):
    problem = default_problem()
    result = solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        max_consecutive_work_days=problem["max_consecutive_work_days"],
        skills=problem["skills"],
        skill_requirements=problem["skill_requirements"],
        shift_costs=problem["shift_costs"],
        cost_weight=cost_weight,
        preferences=problem["preferences"],
        preference_weight=0.01,
    )
    return name, problem, result


def print_case(name, problem, result):
    print(f"\n{name}")
    print("-" * len(name))
    if result["status"] != "optimal":
        print(result["message"])
        return

    for day in problem["days"]:
        assigned = result["schedule"][day]
        day_cost = sum(problem["shift_costs"][employee][day] for employee in assigned)
        print(f"{day}: {', '.join(assigned)} | cost={day_cost}")

    print(f"\nTotal cost: {result['total_cost']}")
    print(f"Fairness spread: {result['fairness_spread']}")
    print(f"Preference matches: {result['preference_matches']}")


def main():
    cases = [
        solve_case("Fairness and preference only", cost_weight=0),
        solve_case("Cost-aware schedule", cost_weight=0.01),
    ]

    for name, problem, result in cases:
        print_case(name, problem, result)


if __name__ == "__main__":
    main()
