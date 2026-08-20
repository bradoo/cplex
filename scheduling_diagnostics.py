def diagnose_scheduling_conflicts(problem):
    employees = problem["employees"]
    days = problem["days"]
    required_staff = problem["required_staff"]
    availability = problem["availability"]
    max_shifts = problem["max_shifts_per_employee"]
    skills = problem.get("skills", {})
    skill_requirements = problem.get("skill_requirements", {})

    findings = []
    findings.extend(
        diagnose_total_capacity(employees, days, required_staff, max_shifts)
    )
    findings.extend(
        diagnose_daily_availability(employees, days, required_staff, availability)
    )
    findings.extend(
        diagnose_skill_coverage(
            employees,
            days,
            availability,
            skills,
            skill_requirements,
        )
    )

    return findings


def diagnose_total_capacity(employees, days, required_staff, max_shifts):
    total_required = sum(required_staff[day] for day in days)
    total_capacity = len(employees) * max_shifts

    if total_capacity >= total_required:
        return []

    return [
        {
            "type": "total_capacity",
            "severity": "error",
            "message": (
                f"全周需要 {total_required} 个班次，但员工总容量只有 "
                f"{total_capacity} 个班次。"
            ),
            "required": total_required,
            "available": total_capacity,
            "gap": total_required - total_capacity,
        }
    ]


def diagnose_daily_availability(employees, days, required_staff, availability):
    findings = []

    for day in days:
        available_employees = [
            employee
            for employee in employees
            if availability.get(employee, {}).get(day, 0)
        ]
        required = required_staff[day]

        if len(available_employees) < required:
            findings.append(
                {
                    "type": "daily_availability",
                    "severity": "error",
                    "day": day,
                    "message": (
                        f"{day} 需要 {required} 人，但只有 "
                        f"{len(available_employees)} 人可上班。"
                    ),
                    "required": required,
                    "available": len(available_employees),
                    "gap": required - len(available_employees),
                    "employees": available_employees,
                }
            )

    return findings


def diagnose_skill_coverage(
    employees,
    days,
    availability,
    skills,
    skill_requirements,
):
    findings = []

    for day in days:
        for skill, required in skill_requirements.get(day, {}).items():
            qualified_available = [
                employee
                for employee in employees
                if availability.get(employee, {}).get(day, 0)
                and skill in skills.get(employee, [])
            ]

            if len(qualified_available) < required:
                findings.append(
                    {
                        "type": "skill_coverage",
                        "severity": "error",
                        "day": day,
                        "skill": skill,
                        "message": (
                            f"{day} 需要 {required} 名 {skill} 技能员工，"
                            f"但当天只有 {len(qualified_available)} 名可用。"
                        ),
                        "required": required,
                        "available": len(qualified_available),
                        "gap": required - len(qualified_available),
                        "employees": qualified_available,
                    }
                )

    return findings


def format_conflict_report(findings):
    if not findings:
        return "没有发现明显的输入数据冲突；可能需要进一步查看更复杂的组合约束。"

    lines = ["冲突诊断结果："]
    for index, finding in enumerate(findings, start=1):
        lines.append(f"{index}. [{finding['type']}] {finding['message']}")

    return "\n".join(lines)
