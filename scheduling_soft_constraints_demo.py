from scheduling_solver import (
    default_problem,
    solve_staff_scheduling,
    solve_staff_scheduling_soft,
)


def main():
    problem = default_problem()
    problem["skill_requirements"]["Sun"] = {"senior": 1, "night": 2}

    print("=== CPLEX 软约束进阶示例 ===")
    print("本例把技能覆盖也做成软约束：不再只回答无解，而是报告技能缺口。")
    print()

    hard_result = solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        skills=problem["skills"],
        skill_requirements=problem["skill_requirements"],
        preferences=problem["preferences"],
    )

    print(f"硬约束状态: {hard_result['status']}")
    if hard_result["status"] == "infeasible":
        print("硬模型要求所有技能覆盖必须完全满足，因此找不到可行解。")
    print()

    soft_result = solve_staff_scheduling_soft(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        skills=problem["skills"],
        skill_requirements=problem["skill_requirements"],
        preferences=problem["preferences"],
    )

    print(f"软约束状态: {soft_result['status']}")
    print(f"人数缺口: {soft_result['total_shortage']}")
    print(f"技能缺口: {soft_result['total_skill_shortage']}")
    for key, shortage in soft_result["skill_shortages"].items():
        day, skill = key.split(":")
        print(f"- {day} 的 {skill} 技能缺 {shortage} 人")
    print()

    print("周日排班结果:")
    print(", ".join(soft_result["schedule"]["Sun"]))


if __name__ == "__main__":
    main()
