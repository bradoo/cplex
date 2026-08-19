from scheduling_solver import default_problem, solve_staff_scheduling


def run_case(name, preference_weight):
    problem = default_problem()
    result = solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        preferences=problem["preferences"],
        preference_weight=preference_weight,
    )

    print(f"\n{name}")
    print("-" * len(name))
    print(f"Preference weight: {preference_weight}")
    print(f"Fairness spread: {result['fairness_spread']}")
    print(f"Preference matches: {result['preference_matches']}")
    for day in problem["days"]:
        assigned = ", ".join(result["schedule"][day])
        print(f"- {day}: {assigned}")


def main():
    run_case("Fairness only", preference_weight=0)
    run_case("Fairness plus preferences", preference_weight=0.01)
    run_case("Preference-heavy", preference_weight=0.5)


if __name__ == "__main__":
    main()
