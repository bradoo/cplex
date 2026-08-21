from scheduling_solver import (
    default_problem,
    solve_staff_scheduling_soft,
    solve_staff_scheduling_two_stage,
)


def build_problem():
    problem = default_problem()
    problem["days"] = ["Sun"]
    problem["required_staff"] = {"Sun": 1}
    problem["availability"] = {
        employee: {"Sun": int(employee in ["Carol", "David"])}
        for employee in problem["employees"]
    }
    problem["skill_requirements"] = {"Sun": {"night": 1}}
    problem["preferences"] = {
        employee: {"Sun": int(employee == "Carol")}
        for employee in problem["employees"]
    }
    problem["max_shifts_per_employee"] = 1
    return problem


def print_result(title, result):
    print(title)
    print(f"排班: {', '.join(result['schedule']['Sun'])}")
    print(f"人数缺口: {result['total_shortage']}")
    print(f"技能缺口: {result['total_skill_shortage']}")
    print(f"偏好命中: {result['preference_matches']}")
    print()


def main():
    problem = build_problem()

    print("=== CPLEX 分阶段优化示例 ===")
    print("场景：周日只需要 1 人；Carol 更想上班；David 有 night 技能。")
    print("目标：先保证业务底线，也就是缺口最少；再考虑偏好。")
    print()

    weighted_result = solve_staff_scheduling_soft(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        skills=problem["skills"],
        skill_requirements=problem["skill_requirements"],
        preferences=problem["preferences"],
        preference_weight=10,
        skill_shortage_penalty=1,
    )

    two_stage_result = solve_staff_scheduling_two_stage(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        skills=problem["skills"],
        skill_requirements=problem["skill_requirements"],
        preferences=problem["preferences"],
        preference_weight=10,
        skill_shortage_penalty=1,
    )

    print_result("单目标低技能罚分", weighted_result)
    print_result("分阶段优化", two_stage_result)

    print("第一阶段最少技能缺口:", two_stage_result["stage_one"]["total_skill_shortage"])
    print("第二阶段在这个缺口上限内继续优化偏好。")


if __name__ == "__main__":
    main()
