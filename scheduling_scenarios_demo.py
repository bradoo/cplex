from copy import deepcopy
import csv
import json
from pathlib import Path

from scheduling_solver import (
    default_problem,
    solve_staff_scheduling,
    solve_staff_scheduling_soft,
)


def solve_scenario(name, changes, use_soft_fallback=True):
    problem = default_problem()
    apply_changes(problem, changes)

    result = solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        preferences=problem["preferences"],
        preference_weight=problem.get("preference_weight", 0.01),
        time_limit=problem.get("time_limit", 10),
        mip_gap=problem.get("mip_gap", 0),
    )

    if result["status"] == "infeasible" and use_soft_fallback:
        result = solve_staff_scheduling_soft(
            employees=problem["employees"],
            days=problem["days"],
            required_staff=problem["required_staff"],
            availability=problem["availability"],
            max_shifts_per_employee=problem["max_shifts_per_employee"],
            preferences=problem["preferences"],
            preference_weight=problem.get("preference_weight", 0.01),
            time_limit=problem.get("time_limit", 10),
            mip_gap=problem.get("mip_gap", 0),
        )

    return {
        "name": name,
        "result": result,
        "problem": problem,
    }


def apply_changes(problem, changes):
    if "required_staff" in changes:
        problem["required_staff"].update(changes["required_staff"])

    if "max_shifts_per_employee" in changes:
        problem["max_shifts_per_employee"] = changes["max_shifts_per_employee"]

    if "availability" in changes:
        for employee, days in changes["availability"].items():
            problem["availability"][employee].update(days)

    if "preferences" in changes:
        for employee, days in changes["preferences"].items():
            problem["preferences"][employee].update(days)

    for key in ("preference_weight", "time_limit", "mip_gap"):
        if key in changes:
            problem[key] = changes[key]


def print_summary(rows):
    headers = [
        "Scenario",
        "Mode",
        "Status",
        "Required",
        "Shortage",
        "Fairness",
        "Pref",
        "Time",
    ]
    widths = [18, 8, 11, 8, 8, 8, 6, 7]
    print(format_row(headers, widths))
    print(format_row(["-" * width for width in widths], widths))

    for row in rows:
        result = row["result"]
        print(
            format_row(
                [
                    row["name"],
                    result.get("mode", "-"),
                    result["status"],
                    result.get("total_required_shifts", "-"),
                    result.get("total_shortage", "-"),
                    result.get("fairness_spread", "-"),
                    result.get("preference_matches", "-"),
                    result.get("solve_time", "-"),
                ],
                widths,
            )
        )


def format_row(values, widths):
    return "  ".join(
        str(value)[:width].ljust(width)
        for value, width in zip(values, widths)
    )


def print_details(row):
    result = row["result"]
    problem = row["problem"]
    print(f"\n{row['name']}")
    print("-" * len(row["name"]))
    if result["status"] != "optimal":
        print(result["message"])
        return

    for day in problem["days"]:
        assigned = ", ".join(result["schedule"][day])
        shortage = result["shortages"][day]
        shortage_text = f" | shortage {shortage}" if shortage else ""
        print(f"{day}: {assigned}{shortage_text}")


def export_reports(rows, output_dir):
    output_dir.mkdir(exist_ok=True)
    write_summary_csv(rows, output_dir / "scenario_summary.csv")
    write_schedule_csv(rows, output_dir / "scenario_schedule.csv")
    write_results_json(rows, output_dir / "scenario_results.json")


def write_summary_csv(rows, path):
    fieldnames = [
        "scenario",
        "mode",
        "status",
        "total_required_shifts",
        "total_shortage",
        "fairness_spread",
        "preference_matches",
        "solve_time",
        "solve_status",
    ]

    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            result = row["result"]
            writer.writerow(
                {
                    "scenario": row["name"],
                    "mode": result.get("mode", ""),
                    "status": result["status"],
                    "total_required_shifts": result.get("total_required_shifts", ""),
                    "total_shortage": result.get("total_shortage", ""),
                    "fairness_spread": result.get("fairness_spread", ""),
                    "preference_matches": result.get("preference_matches", ""),
                    "solve_time": result.get("solve_time", ""),
                    "solve_status": result.get("solve_status", ""),
                }
            )


def write_schedule_csv(rows, path):
    fieldnames = [
        "scenario",
        "day",
        "required_staff",
        "assigned_employees",
        "assigned_count",
        "shortage",
    ]

    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            result = row["result"]
            problem = row["problem"]
            if result["status"] != "optimal":
                continue
            for day in problem["days"]:
                assigned = result["schedule"][day]
                writer.writerow(
                    {
                        "scenario": row["name"],
                        "day": day,
                        "required_staff": problem["required_staff"][day],
                        "assigned_employees": ";".join(assigned),
                        "assigned_count": len(assigned),
                        "shortage": result["shortages"][day],
                    }
                )


def write_results_json(rows, path):
    payload = []
    for row in rows:
        payload.append(
            {
                "scenario": row["name"],
                "problem": {
                    "days": row["problem"]["days"],
                    "required_staff": row["problem"]["required_staff"],
                    "max_shifts_per_employee": row["problem"]["max_shifts_per_employee"],
                },
                "result": row["result"],
            }
        )

    with path.open("w") as file:
        json.dump(payload, file, indent=2)


def main():
    scenarios = [
        ("Baseline", {}),
        ("Friday peak", {"required_staff": {"Fri": 4}}),
        ("Max 4 shifts", {"max_shifts_per_employee": 4}),
        (
            "Weekend peak",
            {
                "required_staff": {"Sat": 4, "Sun": 3},
                "max_shifts_per_employee": 4,
            },
        ),
        ("Preference focus", {"preference_weight": 0.5}),
    ]

    rows = [
        solve_scenario(name, deepcopy(changes))
        for name, changes in scenarios
    ]

    print("\nScenario comparison")
    print("===================")
    print_summary(rows)

    print("\nDetailed schedules")
    print("==================")
    for row in rows:
        print_details(row)

    export_reports(rows, Path("reports"))
    print("\nReports written")
    print("===============")
    print("reports/scenario_summary.csv")
    print("reports/scenario_schedule.csv")
    print("reports/scenario_results.json")


if __name__ == "__main__":
    main()
