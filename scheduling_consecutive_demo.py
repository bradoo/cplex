from scheduling_solver import default_problem, solve_staff_scheduling


def solve_case(name, max_consecutive_work_days):
    problem = default_problem()
    result = solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        max_consecutive_work_days=max_consecutive_work_days,
        preferences=problem["preferences"],
        preference_weight=0.01,
    )
    return name, problem, result


def max_run_for_employee(schedule, days, employee):
    longest = 0
    current = 0
    for day in days:
        if employee in schedule[day]:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def print_case(name, problem, result):
    print(f"\n{name}")
    print("-" * len(name))
    if result["status"] != "optimal":
        print(result["message"])
        return

    for day in problem["days"]:
        print(f"{day}: {', '.join(result['schedule'][day])}")

    print("\nLongest consecutive work run")
    for employee in problem["employees"]:
        longest = max_run_for_employee(result["schedule"], problem["days"], employee)
        print(f"- {employee}: {longest} days")

    print(f"Fairness spread: {result['fairness_spread']}")
    print(f"Preference matches: {result['preference_matches']}")


def main():
    cases = [
        solve_case("No consecutive limit", None),
        solve_case("Max 2 consecutive work days", 2),
    ]

    for name, problem, result in cases:
        print_case(name, problem, result)


if __name__ == "__main__":
    main()
