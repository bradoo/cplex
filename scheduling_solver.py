from docplex.mp.model import Model


DEFAULT_EMPLOYEES = ["Alice", "Bob", "Carol", "David"]

DEFAULT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

DEFAULT_REQUIRED_STAFF = {
    "Mon": 2,
    "Tue": 2,
    "Wed": 2,
    "Thu": 2,
    "Fri": 3,
    "Sat": 2,
    "Sun": 1,
}

DEFAULT_AVAILABILITY = {
    "Alice": {"Mon": 1, "Tue": 1, "Wed": 1, "Thu": 1, "Fri": 1, "Sat": 0, "Sun": 0},
    "Bob": {"Mon": 1, "Tue": 0, "Wed": 1, "Thu": 1, "Fri": 1, "Sat": 1, "Sun": 0},
    "Carol": {"Mon": 0, "Tue": 1, "Wed": 1, "Thu": 0, "Fri": 1, "Sat": 1, "Sun": 1},
    "David": {"Mon": 1, "Tue": 1, "Wed": 0, "Thu": 1, "Fri": 1, "Sat": 1, "Sun": 1},
}

DEFAULT_PREFERENCES = {
    "Alice": {"Mon": 1, "Tue": 1, "Wed": 1, "Thu": 1, "Fri": 0, "Sat": 0, "Sun": 0},
    "Bob": {"Mon": 1, "Tue": 0, "Wed": 1, "Thu": 1, "Fri": 0, "Sat": 1, "Sun": 0},
    "Carol": {"Mon": 0, "Tue": 1, "Wed": 0, "Thu": 0, "Fri": 1, "Sat": 1, "Sun": 1},
    "David": {"Mon": 0, "Tue": 1, "Wed": 0, "Thu": 1, "Fri": 1, "Sat": 0, "Sun": 1},
}

DEFAULT_SKILLS = {
    "Alice": ["senior", "support"],
    "Bob": ["support"],
    "Carol": ["senior", "training"],
    "David": ["support", "night"],
}

DEFAULT_SKILL_REQUIREMENTS = {
    day: {"senior": 1}
    for day in DEFAULT_DAYS
}

DEFAULT_SHIFT_COSTS = {
    "Alice": {"Mon": 140, "Tue": 140, "Wed": 140, "Thu": 140, "Fri": 150, "Sat": 0, "Sun": 0},
    "Bob": {"Mon": 100, "Tue": 0, "Wed": 100, "Thu": 100, "Fri": 110, "Sat": 130, "Sun": 0},
    "Carol": {"Mon": 0, "Tue": 135, "Wed": 135, "Thu": 0, "Fri": 145, "Sat": 160, "Sun": 170},
    "David": {"Mon": 95, "Tue": 95, "Wed": 0, "Thu": 95, "Fri": 105, "Sat": 125, "Sun": 135},
}

DEFAULT_MAX_SHIFTS = 5
DEFAULT_MAX_CONSECUTIVE_WORK_DAYS = None


def default_problem():
    return {
        "employees": list(DEFAULT_EMPLOYEES),
        "days": list(DEFAULT_DAYS),
        "required_staff": dict(DEFAULT_REQUIRED_STAFF),
        "availability": {
            employee: dict(days)
            for employee, days in DEFAULT_AVAILABILITY.items()
        },
        "preferences": {
            employee: dict(days)
            for employee, days in DEFAULT_PREFERENCES.items()
        },
        "skills": {
            employee: list(skills)
            for employee, skills in DEFAULT_SKILLS.items()
        },
        "skill_requirements": {
            day: dict(requirements)
            for day, requirements in DEFAULT_SKILL_REQUIREMENTS.items()
        },
        "shift_costs": {
            employee: dict(costs)
            for employee, costs in DEFAULT_SHIFT_COSTS.items()
        },
        "max_shifts_per_employee": DEFAULT_MAX_SHIFTS,
        "max_consecutive_work_days": DEFAULT_MAX_CONSECUTIVE_WORK_DAYS,
    }


def solve_staff_scheduling(
    employees,
    days,
    required_staff,
    availability,
    max_shifts_per_employee,
    max_consecutive_work_days=None,
    skills=None,
    skill_requirements=None,
    shift_costs=None,
    cost_weight=0,
    preferences=None,
    preference_weight=0.01,
    time_limit=None,
    mip_gap=None,
    log_output=False,
):
    model = Model(name="staff_scheduling")
    apply_solve_parameters(model, time_limit, mip_gap)

    work = {
        (employee, day): model.binary_var(name=f"work_{employee}_{day}")
        for employee in employees
        for day in days
    }

    max_workload = model.integer_var(name="max_workload", lb=0)
    min_workload = model.integer_var(name="min_workload", lb=0)
    total_required_shifts = sum(required_staff[day] for day in days)
    preference_score = model.sum(
        preference_value(preferences, employee, day) * work[employee, day]
        for employee in employees
        for day in days
    )
    total_cost = model.sum(
        shift_cost(shift_costs, employee, day) * work[employee, day]
        for employee in employees
        for day in days
    )

    model.minimize(
        max_workload
        - min_workload
        + cost_weight * total_cost
        - preference_weight * preference_score
    )

    for day in days:
        model.add_constraint(
            model.sum(work[employee, day] for employee in employees)
            >= required_staff[day],
            ctname=f"cover_{day}",
        )

    for employee in employees:
        for day in days:
            model.add_constraint(
                work[employee, day] <= availability[employee][day],
                ctname=f"availability_{employee}_{day}",
            )

    for employee in employees:
        workload = model.sum(work[employee, day] for day in days)
        model.add_constraint(
            workload <= max_shifts_per_employee,
            ctname=f"max_shifts_{employee}",
        )
        model.add_constraint(workload <= max_workload, ctname=f"max_workload_{employee}")
        model.add_constraint(workload >= min_workload, ctname=f"min_workload_{employee}")

    add_max_consecutive_work_constraints(
        model,
        work,
        employees,
        days,
        max_consecutive_work_days,
    )

    add_skill_coverage_constraints(
        model,
        work,
        employees,
        days,
        skills,
        skill_requirements,
    )

    model.add_constraint(
        model.sum(work[employee, day] for employee in employees for day in days)
        == total_required_shifts,
        ctname="total_required_shifts",
    )

    solution = model.solve(log_output=log_output)

    if solution is None:
        return {
            "status": "infeasible",
            "message": "No feasible schedule found. Try lowering demand, increasing availability, or raising max shifts.",
        }

    schedule = {}
    for day in days:
        schedule[day] = [
            employee
            for employee in employees
            if work[employee, day].solution_value > 0.5
        ]

    workloads = {
        employee: int(round(sum(work[employee, day].solution_value for day in days)))
        for employee in employees
    }
    preference_matches = count_preference_matches(schedule, preferences)
    schedule_cost = calculate_schedule_cost(schedule, shift_costs)

    return {
        "status": "optimal",
        "mode": "hard",
        "schedule": schedule,
        "workloads": workloads,
        "shortages": {day: 0 for day in days},
        "total_shortage": 0,
        "total_required_shifts": total_required_shifts,
        "fairness_spread": max(workloads.values()) - min(workloads.values()) if workloads else 0,
        "preference_matches": preference_matches,
        "total_cost": schedule_cost,
        "max_workload": max(workloads.values()) if workloads else 0,
        "min_workload": min(workloads.values()) if workloads else 0,
        **solve_details(model),
    }


def solve_staff_scheduling_soft(
    employees,
    days,
    required_staff,
    availability,
    max_shifts_per_employee,
    max_consecutive_work_days=None,
    skills=None,
    skill_requirements=None,
    shift_costs=None,
    cost_weight=0,
    preferences=None,
    preference_weight=0.01,
    shortage_penalty=1000,
    time_limit=None,
    mip_gap=None,
    log_output=False,
):
    model = Model(name="staff_scheduling_soft")
    apply_solve_parameters(model, time_limit, mip_gap)

    work = {
        (employee, day): model.binary_var(name=f"work_{employee}_{day}")
        for employee in employees
        for day in days
    }
    shortage = {
        day: model.integer_var(name=f"shortage_{day}", lb=0)
        for day in days
    }
    max_workload = model.integer_var(name="max_workload", lb=0)
    min_workload = model.integer_var(name="min_workload", lb=0)
    total_required_shifts = sum(required_staff[day] for day in days)

    total_shortage = model.sum(shortage[day] for day in days)
    preference_score = model.sum(
        preference_value(preferences, employee, day) * work[employee, day]
        for employee in employees
        for day in days
    )
    total_cost = model.sum(
        shift_cost(shift_costs, employee, day) * work[employee, day]
        for employee in employees
        for day in days
    )
    model.minimize(
        shortage_penalty * total_shortage
        + max_workload
        - min_workload
        + cost_weight * total_cost
        - preference_weight * preference_score
    )

    for day in days:
        model.add_constraint(
            model.sum(work[employee, day] for employee in employees) + shortage[day]
            >= required_staff[day],
            ctname=f"cover_with_shortage_{day}",
        )

    for employee in employees:
        for day in days:
            model.add_constraint(
                work[employee, day] <= availability[employee][day],
                ctname=f"availability_{employee}_{day}",
            )

    for employee in employees:
        workload = model.sum(work[employee, day] for day in days)
        model.add_constraint(
            workload <= max_shifts_per_employee,
            ctname=f"max_shifts_{employee}",
        )
        model.add_constraint(workload <= max_workload, ctname=f"max_workload_{employee}")
        model.add_constraint(workload >= min_workload, ctname=f"min_workload_{employee}")

    add_max_consecutive_work_constraints(
        model,
        work,
        employees,
        days,
        max_consecutive_work_days,
    )

    add_skill_coverage_constraints(
        model,
        work,
        employees,
        days,
        skills,
        skill_requirements,
    )

    solution = model.solve(log_output=log_output)

    if solution is None:
        return {
            "status": "infeasible",
            "mode": "soft",
            "message": "No schedule found even with soft demand constraints.",
        }

    schedule = {}
    for day in days:
        schedule[day] = [
            employee
            for employee in employees
            if work[employee, day].solution_value > 0.5
        ]

    workloads = {
        employee: int(round(sum(work[employee, day].solution_value for day in days)))
        for employee in employees
    }
    shortages = {
        day: int(round(shortage[day].solution_value))
        for day in days
    }
    preference_matches = count_preference_matches(schedule, preferences)
    schedule_cost = calculate_schedule_cost(schedule, shift_costs)

    return {
        "status": "optimal",
        "mode": "soft",
        "schedule": schedule,
        "workloads": workloads,
        "shortages": shortages,
        "total_shortage": sum(shortages.values()),
        "total_required_shifts": total_required_shifts,
        "fairness_spread": max(workloads.values()) - min(workloads.values()) if workloads else 0,
        "preference_matches": preference_matches,
        "total_cost": schedule_cost,
        "max_workload": max(workloads.values()) if workloads else 0,
        "min_workload": min(workloads.values()) if workloads else 0,
        "objective_value": solution.objective_value,
        **solve_details(model),
    }


def apply_solve_parameters(model, time_limit, mip_gap):
    if time_limit is not None and time_limit > 0:
        model.parameters.timelimit = float(time_limit)
    if mip_gap is not None and mip_gap >= 0:
        model.parameters.mip.tolerances.mipgap = float(mip_gap)


def add_max_consecutive_work_constraints(
    model,
    work,
    employees,
    days,
    max_consecutive_work_days,
):
    if not max_consecutive_work_days:
        return

    window_size = max_consecutive_work_days + 1
    if window_size > len(days):
        return

    for employee in employees:
        for start in range(len(days) - window_size + 1):
            window_days = days[start : start + window_size]
            model.add_constraint(
                model.sum(work[employee, day] for day in window_days)
                <= max_consecutive_work_days,
                ctname=f"max_consecutive_{employee}_{start}",
            )


def add_skill_coverage_constraints(
    model,
    work,
    employees,
    days,
    skills,
    skill_requirements,
):
    if not skills or not skill_requirements:
        return

    for day in days:
        day_requirements = skill_requirements.get(day, {})
        for skill, required_count in day_requirements.items():
            qualified_employees = [
                employee
                for employee in employees
                if skill in skills.get(employee, [])
            ]
            model.add_constraint(
                model.sum(work[employee, day] for employee in qualified_employees)
                >= required_count,
                ctname=f"skill_{skill}_{day}",
            )


def solve_details(model):
    details = model.solve_details
    return {
        "solve_status": str(details.status),
        "solve_time": round(float(details.time or 0), 4),
        "reported_mip_gap": rounded_or_none(
            getattr(details, "mip_relative_gap", None)
        ),
    }


def rounded_or_none(value):
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def preference_value(preferences, employee, day):
    if not preferences:
        return 0
    return int(preferences.get(employee, {}).get(day, 0))


def count_preference_matches(schedule, preferences):
    if not preferences:
        return 0
    return sum(
        preference_value(preferences, employee, day)
        for day, employees in schedule.items()
        for employee in employees
    )


def shift_cost(shift_costs, employee, day):
    if not shift_costs:
        return 0
    return float(shift_costs.get(employee, {}).get(day, 0))


def calculate_schedule_cost(schedule, shift_costs):
    return round(
        sum(
            shift_cost(shift_costs, employee, day)
            for day, employees in schedule.items()
            for employee in employees
        ),
        2,
    )
