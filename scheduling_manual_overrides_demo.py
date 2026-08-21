from scheduling_solver import default_problem, solve_staff_scheduling


def solve(problem, locked_assignments=None, blocked_assignments=None):
    return solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        skills=problem["skills"],
        skill_requirements=problem["skill_requirements"],
        preferences=problem["preferences"],
        locked_assignments=locked_assignments,
        blocked_assignments=blocked_assignments,
    )


def print_day(title, result, day):
    print(title)
    print(f"{day}: {', '.join(result['schedule'][day])}")
    print(f"工作量: {result['workloads']}")
    print()


def main():
    problem = default_problem()

    print("=== CPLEX 人工干预 / 锁定班次示例 ===")
    print("场景：经理手工指定 David 周一必须上班，同时 Bob 周三不能上班。")
    print("模型会在这些人工规则固定后，重新优化剩余排班。")
    print()

    baseline = solve(problem)
    overridden = solve(
        problem,
        locked_assignments={"Mon": ["David"]},
        blocked_assignments={"Wed": ["Bob"]},
    )

    print_day("默认排班", baseline, "Mon")
    print_day("加入人工规则后的周一", overridden, "Mon")
    print_day("加入人工规则后的周三", overridden, "Wed")

    print("人工规则检查:")
    print("- David 是否在周一上班:", "David" in overridden["schedule"]["Mon"])
    print("- Bob 是否没有在周三上班:", "Bob" not in overridden["schedule"]["Wed"])


if __name__ == "__main__":
    main()
