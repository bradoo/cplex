from scheduling_solver import default_problem, solve_staff_scheduling


def assigned_with_skill(assigned, skills, skill):
    return [
        employee
        for employee in assigned
        if skill in skills.get(employee, [])
    ]


def main():
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
        preferences=problem["preferences"],
        preference_weight=0.01,
    )

    if result["status"] != "optimal":
        print(result["message"])
        return

    print("\nEmployee skills")
    print("---------------")
    for employee in problem["employees"]:
        print(f"- {employee}: {', '.join(problem['skills'][employee])}")

    print("\nSchedule with senior coverage")
    print("-----------------------------")
    for day in problem["days"]:
        assigned = result["schedule"][day]
        senior_required = problem["skill_requirements"][day]["senior"]
        seniors = assigned_with_skill(assigned, problem["skills"], "senior")
        print(
            f"- {day}: {', '.join(assigned)} "
            f"| senior required={senior_required}, assigned={', '.join(seniors)}"
        )

    print(f"\nFairness spread: {result['fairness_spread']}")
    print(f"Preference matches: {result['preference_matches']}")


if __name__ == "__main__":
    main()
