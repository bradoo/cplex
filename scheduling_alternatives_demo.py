from copy import deepcopy

from scheduling_solver import default_problem, solve_staff_scheduling_soft


ALTERNATIVE_CONFIGS = [
    {
        "name": "Balanced",
        "description": "均衡方案：优先满足覆盖，兼顾公平和少量偏好",
        "preference_weight": 0.01,
        "cost_weight": 0,
        "skill_shortage_penalty": 1200,
    },
    {
        "name": "Preference first",
        "description": "偏好优先：更愿意满足员工偏好",
        "preference_weight": 5,
        "cost_weight": 0,
        "skill_shortage_penalty": 1200,
    },
    {
        "name": "Cost aware",
        "description": "成本优先：在满足规则时压低总排班成本",
        "preference_weight": 0.01,
        "cost_weight": 0.05,
        "skill_shortage_penalty": 1200,
    },
    {
        "name": "Skill relaxed",
        "description": "技能可让步：技能缺口罚分较低，用来观察取舍",
        "preference_weight": 5,
        "cost_weight": 0,
        "skill_shortage_penalty": 1,
    },
]


def generate_schedule_alternatives(problem=None):
    base_problem = deepcopy(problem or default_problem())
    alternatives = []

    for config in ALTERNATIVE_CONFIGS:
        result = solve_staff_scheduling_soft(
            employees=base_problem["employees"],
            days=base_problem["days"],
            required_staff=base_problem["required_staff"],
            availability=base_problem["availability"],
            max_shifts_per_employee=base_problem["max_shifts_per_employee"],
            max_consecutive_work_days=base_problem.get("max_consecutive_work_days"),
            skills=base_problem["skills"],
            skill_requirements=base_problem["skill_requirements"],
            shift_costs=base_problem["shift_costs"],
            preferences=base_problem["preferences"],
            preference_weight=config["preference_weight"],
            cost_weight=config["cost_weight"],
            skill_shortage_penalty=config["skill_shortage_penalty"],
        )
        alternatives.append(
            {
                "name": config["name"],
                "description": config["description"],
                "preference_weight": config["preference_weight"],
                "cost_weight": config["cost_weight"],
                "skill_shortage_penalty": config["skill_shortage_penalty"],
                "result": result,
            }
        )

    return alternatives


def print_alternative_table(alternatives):
    headers = [
        "方案",
        "状态",
        "人数缺口",
        "技能缺口",
        "公平差距",
        "偏好命中",
        "总成本",
    ]
    rows = []

    for alternative in alternatives:
        result = alternative["result"]
        rows.append(
            [
                alternative["name"],
                result["status"],
                str(result.get("total_shortage", "-")),
                str(result.get("total_skill_shortage", "-")),
                str(result.get("fairness_spread", "-")),
                str(result.get("preference_matches", "-")),
                str(result.get("total_cost", "-")),
            ]
        )

    widths = [
        max(len(row[index]) for row in [headers] + rows)
        for index in range(len(headers))
    ]
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def print_schedule_preview(alternatives):
    for alternative in alternatives:
        result = alternative["result"]
        print()
        print(f"{alternative['name']} - {alternative['description']}")
        for day, employees in result["schedule"].items():
            print(f"- {day}: {', '.join(employees) if employees else '无人'}")


def main():
    print("=== CPLEX 候选排班方案对比示例 ===")
    print("同一组业务输入，使用不同目标权重生成多个候选方案，方便经理比较取舍。")
    print()

    alternatives = generate_schedule_alternatives()
    print_alternative_table(alternatives)
    print_schedule_preview(alternatives)


if __name__ == "__main__":
    main()
