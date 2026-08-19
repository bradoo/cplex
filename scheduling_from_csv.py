import csv
import argparse
from pathlib import Path

from scheduling_solver import solve_staff_scheduling, solve_staff_scheduling_soft


DATA_DIR = Path(__file__).parent / "data"


def read_employees(path):
    employees = []
    max_shifts = None

    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            employees.append(row["employee"])
            row_max_shifts = int(row["max_shifts"])
            if max_shifts is None:
                max_shifts = row_max_shifts
            elif max_shifts != row_max_shifts:
                raise ValueError("This lesson expects the same max_shifts for every employee.")

    return employees, max_shifts


def read_demand(path):
    days = []
    required_staff = {}

    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            day = row["day"]
            days.append(day)
            required_staff[day] = int(row["required_staff"])

    return days, required_staff


def read_availability(path, employees, days):
    availability = {employee: {} for employee in employees}

    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            employee = row["employee"]
            if employee not in availability:
                raise ValueError(f"Unknown employee in availability.csv: {employee}")
            for day in days:
                availability[employee][day] = int(row[day])

    missing = [
        employee
        for employee in employees
        if set(availability[employee]) != set(days)
    ]
    if missing:
        raise ValueError(f"Missing availability rows for: {', '.join(missing)}")

    return availability


def print_result(result, days, employees):
    if result["status"] != "optimal":
        print(result["message"])
        return

    print("\nSchedule loaded from CSV data")
    print("-----------------------------")
    for day in days:
        assigned = result["schedule"][day]
        shortage = result["shortages"][day]
        suffix = f" (shortage: {shortage})" if shortage else ""
        print(f"- {day}: {', '.join(assigned)}{suffix}")

    print("\nEmployee workloads")
    print("------------------")
    for employee in employees:
        print(f"- {employee}: {result['workloads'][employee]} shifts")

    print(f"\nMode: {result['mode']}")
    print(f"Total required shifts: {result['total_required_shifts']}")
    print(f"Total shortage: {result['total_shortage']}")
    print(f"Fairness spread: {result['fairness_spread']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Solve staff scheduling from CSV files.")
    parser.add_argument("--employees", default=DATA_DIR / "employees.csv", type=Path)
    parser.add_argument("--demand", default=DATA_DIR / "demand.csv", type=Path)
    parser.add_argument("--availability", default=DATA_DIR / "availability.csv", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()

    employees, max_shifts = read_employees(args.employees)
    days, required_staff = read_demand(args.demand)
    availability = read_availability(args.availability, employees, days)

    result = solve_staff_scheduling(
        employees=employees,
        days=days,
        required_staff=required_staff,
        availability=availability,
        max_shifts_per_employee=max_shifts,
    )

    if result["status"] == "infeasible":
        print("Hard constraints are infeasible. Trying soft constraints...\n")
        result = solve_staff_scheduling_soft(
            employees=employees,
            days=days,
            required_staff=required_staff,
            availability=availability,
            max_shifts_per_employee=max_shifts,
        )

    print_result(result, days, employees)


if __name__ == "__main__":
    main()
