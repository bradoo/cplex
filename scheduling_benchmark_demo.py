import csv
from pathlib import Path

from scheduling_solver import solve_staff_scheduling


def build_problem(employee_count, day_count):
    employees = [f"Emp{index + 1:02d}" for index in range(employee_count)]
    days = [f"Day{index + 1:02d}" for index in range(day_count)]
    required_staff = {
        day: max(1, employee_count // 3 + (index % 2))
        for index, day in enumerate(days)
    }
    max_shifts = max(2, (sum(required_staff.values()) + employee_count - 1) // employee_count + 2)

    availability = {}
    preferences = {}
    for employee_index, employee in enumerate(employees):
        availability[employee] = {}
        preferences[employee] = {}
        for day_index, day in enumerate(days):
            availability[employee][day] = 0 if (employee_index + day_index) % 7 == 0 else 1
            preferences[employee][day] = 1 if (employee_index + 2 * day_index) % 4 == 0 else 0

    return {
        "employees": employees,
        "days": days,
        "required_staff": required_staff,
        "availability": availability,
        "preferences": preferences,
        "max_shifts_per_employee": max_shifts,
    }


def run_benchmark_case(name, employee_count, day_count):
    problem = build_problem(employee_count, day_count)
    result = solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        preferences=problem["preferences"],
        preference_weight=0.01,
        time_limit=10,
        mip_gap=0.01,
    )

    return {
        "case": name,
        "employees": employee_count,
        "days": day_count,
        "binary_variables": employee_count * day_count,
        "required_shifts": result.get("total_required_shifts", ""),
        "status": result["status"],
        "solve_status": result.get("solve_status", ""),
        "solve_time": result.get("solve_time", ""),
        "fairness_spread": result.get("fairness_spread", ""),
        "preference_matches": result.get("preference_matches", ""),
        "reported_mip_gap": result.get("reported_mip_gap", ""),
    }


def print_results(rows):
    headers = [
        "Case",
        "Emp",
        "Days",
        "Vars",
        "Req",
        "Status",
        "Time",
        "Fair",
        "Pref",
        "Gap",
    ]
    widths = [12, 5, 5, 6, 5, 10, 7, 5, 5, 8]
    print(format_row(headers, widths))
    print(format_row(["-" * width for width in widths], widths))
    for row in rows:
        print(
            format_row(
                [
                    row["case"],
                    row["employees"],
                    row["days"],
                    row["binary_variables"],
                    row["required_shifts"],
                    row["status"],
                    row["solve_time"],
                    row["fairness_spread"],
                    row["preference_matches"],
                    row["reported_mip_gap"],
                ],
                widths,
            )
        )


def format_row(values, widths):
    return "  ".join(
        str(value)[:width].ljust(width)
        for value, width in zip(values, widths)
    )


def export_csv(rows, path):
    path.parent.mkdir(exist_ok=True)
    fieldnames = [
        "case",
        "employees",
        "days",
        "binary_variables",
        "required_shifts",
        "status",
        "solve_status",
        "solve_time",
        "fairness_spread",
        "preference_matches",
        "reported_mip_gap",
    ]
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    cases = [
        ("small", 4, 7),
        ("medium", 8, 14),
        ("large", 12, 21),
        ("xlarge", 16, 28),
    ]
    rows = [
        run_benchmark_case(name, employee_count, day_count)
        for name, employee_count, day_count in cases
    ]

    print("\nScheduling benchmark")
    print("====================")
    print_results(rows)

    output_path = Path("reports") / "benchmark_results.csv"
    export_csv(rows, output_path)
    print(f"\nBenchmark report written to {output_path}")


if __name__ == "__main__":
    main()
