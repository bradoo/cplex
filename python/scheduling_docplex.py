from scheduling_solver import default_problem, solve_staff_scheduling


def main():
    problem = default_problem()
    result = solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        log_output=True,
    )

    if result["status"] != "optimal":
        print(result["message"])
        return

    print("\nBest staff schedule")
    print("-------------------")
    for day in problem["days"]:
        assigned = result["schedule"][day]
        print(f"- {day}: {', '.join(assigned)}")

    print("\nEmployee workloads")
    print("------------------")
    for employee in problem["employees"]:
        shifts = result["workloads"][employee]
        print(f"- {employee}: {shifts:g} shifts")

    print(f"\nTotal assigned shifts: {result['total_required_shifts']:g}")
    print(f"Fairness spread: {result['fairness_spread']:g}")


if __name__ == "__main__":
    main()
