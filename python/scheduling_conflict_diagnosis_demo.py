from copy import deepcopy

from scheduling_diagnostics import diagnose_scheduling_conflicts, format_conflict_report
from scheduling_solver import (
    default_problem,
    solve_staff_scheduling,
    solve_staff_scheduling_soft,
)


def main():
    problem = default_problem()
    problem["required_staff"]["Sun"] = 4
    problem["skill_requirements"]["Sun"] = {"senior": 2, "night": 2}
    problem["max_shifts_per_employee"] = 2

    print("=== CPLEX 排班冲突诊断示例 ===")
    print("本例故意制造一个无解场景：周日需求、技能要求和全周容量都被收紧。")
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

    print(f"硬约束求解状态: {hard_result['status']}")
    if hard_result["status"] == "infeasible":
        print(hard_result["message"])
    print()

    findings = diagnose_scheduling_conflicts(problem)
    print(format_conflict_report(findings))
    print()

    print("=== 软约束兜底 ===")
    print("现在软约束会同时放松人数需求和技能覆盖，并分别报告缺口。")
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

    print(f"软约束求解状态: {soft_result['status']}")
    if soft_result["status"] == "optimal":
        print(f"人数缺口: {soft_result['total_shortage']}")
        print(f"技能缺口: {soft_result['total_skill_shortage']}")
        for key, shortage in soft_result["skill_shortages"].items():
            day, skill = key.split(":")
            print(f"- {day} 的 {skill} 技能缺 {shortage} 人")
    print()

    demand_only_problem = deepcopy(problem)
    demand_only_problem["skill_requirements"]["Sun"] = {"senior": 1}
    demand_only_problem["max_shifts_per_employee"] = 5

    demand_soft_result = solve_staff_scheduling_soft(
        employees=demand_only_problem["employees"],
        days=demand_only_problem["days"],
        required_staff=demand_only_problem["required_staff"],
        availability=demand_only_problem["availability"],
        max_shifts_per_employee=demand_only_problem["max_shifts_per_employee"],
        skills=demand_only_problem["skills"],
        skill_requirements=demand_only_problem["skill_requirements"],
        preferences=demand_only_problem["preferences"],
    )

    print(f"移除技能冲突后的软约束状态: {demand_soft_result['status']}")
    if demand_soft_result["status"] == "optimal":
        print(f"总缺口: {demand_soft_result['total_shortage']}")
        for day, shortage in demand_soft_result["shortages"].items():
            if shortage:
                print(f"- {day}: 缺 {shortage} 人")


if __name__ == "__main__":
    main()
