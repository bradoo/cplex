from pathlib import Path

from scheduling_solver import default_problem, preference_value, solve_staff_scheduling


def build_explanation(problem, result):
    lines = [
        "# 排班结果解释",
        "",
        "## 总体结论",
        "",
        f"- 求解状态：{result['solve_status']}",
        f"- 总需求班次数：{result['total_required_shifts']}",
        f"- 需求缺口：{result['total_shortage']}",
        f"- 公平性差距：{result['fairness_spread']}",
        f"- 偏好命中：{result['preference_matches']}",
        f"- 求解耗时：{result['solve_time']} 秒",
        "",
        "## 每天为什么这样排",
        "",
    ]

    for day in problem["days"]:
        assigned = result["schedule"][day]
        required = problem["required_staff"][day]
        shortage = result["shortages"][day]
        lines.append(f"### {day}")
        lines.append("")
        lines.append(f"- 当天需求：{required} 人")
        lines.append(f"- 实际安排：{len(assigned)} 人")
        lines.append(f"- 需求缺口：{shortage} 人")
        for employee in assigned:
            preference_text = (
                "命中员工偏好"
                if preference_value(problem["preferences"], employee, day)
                else "未命中偏好，但满足可用性和整体公平性"
            )
            lines.append(
                f"- {employee} 被安排：当天可用，{preference_text}，"
                f"当前总工作量为 {result['workloads'][employee]} 班"
            )
        lines.append("")

    lines.extend(
        [
            "## 员工工作量解释",
            "",
        ]
    )

    for employee in problem["employees"]:
        workload = result["workloads"][employee]
        lines.append(
            f"- {employee}: {workload} 班，"
            f"不超过上限 {problem['max_shifts_per_employee']} 班"
        )

    lines.extend(
        [
            "",
            "## 模型如何权衡",
            "",
            "- 第一层：必须满足每天需求、员工可用性、每人最大班次数等硬约束。",
            "- 第二层：在可行方案中，让员工工作量尽量公平。",
            "- 第三层：在公平性相近时，尽量提高员工偏好命中数。",
            "",
        ]
    )

    return "\n".join(lines)


def main():
    problem = default_problem()
    result = solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        preferences=problem["preferences"],
        preference_weight=0.01,
        time_limit=10,
        mip_gap=0,
    )

    if result["status"] != "optimal":
        print(result["message"])
        return

    explanation = build_explanation(problem, result)
    print(explanation)

    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "baseline_explanation.md"
    output_path.write_text(explanation)
    print(f"\nExplanation written to {output_path}")


if __name__ == "__main__":
    main()
