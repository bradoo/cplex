import csv
from pathlib import Path


SCENARIOS = ["baseline", "weekend_peak"]


def read_workload(path):
    workloads = {}
    fairness_spread = None

    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            name = row["employee"]
            value = int(row["workload"])
            if name == "fairness_spread":
                fairness_spread = value
            else:
                workloads[name] = value

    return workloads, fairness_spread


def count_assignments(path):
    with path.open(newline="") as file:
        return sum(1 for _ in csv.DictReader(file))


def build_summary(base_dir):
    rows = []
    for scenario in SCENARIOS:
        workloads, fairness_spread = read_workload(
            base_dir / f"{scenario}_workload_output.csv"
        )
        total_assignments = count_assignments(
            base_dir / f"{scenario}_schedule_output.csv"
        )
        rows.append(
            {
                "scenario": scenario,
                "total_assignments": total_assignments,
                "fairness_spread": fairness_spread,
                "alice_workload": workloads.get("Alice", 0),
                "bob_workload": workloads.get("Bob", 0),
                "carol_workload": workloads.get("Carol", 0),
                "david_workload": workloads.get("David", 0),
            }
        )
    return rows


def write_summary(rows, output_path):
    fieldnames = [
        "scenario",
        "total_assignments",
        "fairness_spread",
        "alice_workload",
        "bob_workload",
        "carol_workload",
        "david_workload",
    ]
    with output_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    base_dir = Path(__file__).resolve().parent
    rows = build_summary(base_dir)
    output_path = base_dir / "scenario_summary.csv"
    write_summary(rows, output_path)

    print("Scenario summary")
    print("----------------")
    for row in rows:
        print(
            f"{row['scenario']}: total={row['total_assignments']}, "
            f"fairness={row['fairness_spread']}"
        )
    print(f"Written: {output_path.name}")


if __name__ == "__main__":
    main()
