from scheduling_solver import default_problem, solve_staff_scheduling_soft


def build_tradeoff_problem():
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


def solve_with_skill_penalty(skill_penalty):
    problem = build_tradeoff_problem()
    return solve_staff_scheduling_soft(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        skills=problem["skills"],
        skill_requirements=problem["skill_requirements"],
        preferences=problem["preferences"],
        preference_weight=10,
        skill_shortage_penalty=skill_penalty,
    )


def print_result(label, result):
    print(label)
    print(f"排班: {', '.join(result['schedule']['Sun'])}")
    print(f"偏好命中: {result['preference_matches']}")
    print(f"技能缺口: {result['total_skill_shortage']}")
    if result["skill_shortages"]:
        for key, shortage in result["skill_shortages"].items():
            day, skill = key.split(":")
            print(f"- {day} 的 {skill} 技能缺 {shortage} 人")
    print(f"目标函数值: {result['objective_value']}")
    print()


def main():
    print("=== CPLEX 罚分权重示例 ===")
    print("同一个场景：周日只需要 1 人，Carol 更想上班，David 有 night 技能。")
    print("低技能罚分会偏向员工偏好；高技能罚分会优先满足技能覆盖。")
    print()

    low_penalty_result = solve_with_skill_penalty(skill_penalty=1)
    high_penalty_result = solve_with_skill_penalty(skill_penalty=1200)

    print_result("低技能罚分 skill_shortage_penalty=1", low_penalty_result)
    print_result("高技能罚分 skill_shortage_penalty=1200", high_penalty_result)


if __name__ == "__main__":
    main()
