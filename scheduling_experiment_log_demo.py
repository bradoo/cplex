import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scheduling_scenarios_demo import solve_scenario


EXPERIMENTS = [
    (
        "baseline_v1",
        {
            "description": "Base model with fairness, preferences, skills, and default costs.",
            "changes": {},
        },
    ),
    (
        "cost_aware_v1",
        {
            "description": "Increase cost weight to reduce schedule cost.",
            "changes": {"cost_weight": 0.01},
        },
    ),
    (
        "fatigue_rule_v1",
        {
            "description": "Limit employees to at most two consecutive work days.",
            "changes": {"max_consecutive_work_days": 2},
        },
    ),
    (
        "weekend_peak_v1",
        {
            "description": "Weekend demand spike with soft fallback.",
            "changes": {
                "required_staff": {"Sat": 4, "Sun": 3},
                "max_shifts_per_employee": 4,
            },
        },
    ),
]


def experiment_record(experiment_id, description, scenario_row):
    result = scenario_row["result"]
    problem = scenario_row["problem"]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experiment_id": experiment_id,
        "description": description,
        "model_config": {
            "max_shifts_per_employee": problem["max_shifts_per_employee"],
            "max_consecutive_work_days": problem.get("max_consecutive_work_days"),
            "preference_weight": problem.get("preference_weight", 0.01),
            "cost_weight": problem.get("cost_weight", 0),
            "time_limit": problem.get("time_limit", 10),
            "mip_gap": problem.get("mip_gap", 0),
        },
        "metrics": {
            "status": result["status"],
            "mode": result.get("mode"),
            "total_required_shifts": result.get("total_required_shifts"),
            "total_shortage": result.get("total_shortage"),
            "fairness_spread": result.get("fairness_spread"),
            "preference_matches": result.get("preference_matches"),
            "total_cost": result.get("total_cost"),
            "solve_time": result.get("solve_time"),
            "solve_status": result.get("solve_status"),
        },
    }


def append_jsonl(records, path):
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_summary_csv(records, path):
    path.parent.mkdir(exist_ok=True)
    fieldnames = [
        "timestamp",
        "experiment_id",
        "status",
        "mode",
        "total_shortage",
        "fairness_spread",
        "preference_matches",
        "total_cost",
        "solve_time",
        "cost_weight",
        "max_consecutive_work_days",
    ]
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            metrics = record["metrics"]
            config = record["model_config"]
            writer.writerow(
                {
                    "timestamp": record["timestamp"],
                    "experiment_id": record["experiment_id"],
                    "status": metrics["status"],
                    "mode": metrics["mode"],
                    "total_shortage": metrics["total_shortage"],
                    "fairness_spread": metrics["fairness_spread"],
                    "preference_matches": metrics["preference_matches"],
                    "total_cost": metrics["total_cost"],
                    "solve_time": metrics["solve_time"],
                    "cost_weight": config["cost_weight"],
                    "max_consecutive_work_days": config["max_consecutive_work_days"],
                }
            )


def print_summary(records):
    print("\nExperiment run")
    print("==============")
    for record in records:
        metrics = record["metrics"]
        print(
            f"{record['experiment_id']}: "
            f"status={metrics['status']}, "
            f"mode={metrics['mode']}, "
            f"shortage={metrics['total_shortage']}, "
            f"fairness={metrics['fairness_spread']}, "
            f"pref={metrics['preference_matches']}, "
            f"cost={metrics['total_cost']}, "
            f"time={metrics['solve_time']}"
        )


def main():
    records = []
    for experiment_id, spec in EXPERIMENTS:
        scenario_row = solve_scenario(experiment_id, spec["changes"])
        records.append(
            experiment_record(
                experiment_id,
                spec["description"],
                scenario_row,
            )
        )

    append_jsonl(records, Path("reports") / "experiments.jsonl")
    write_summary_csv(records, Path("reports") / "experiments_summary.csv")
    print_summary(records)
    print("\nExperiment records written to:")
    print("reports/experiments.jsonl")
    print("reports/experiments_summary.csv")


if __name__ == "__main__":
    main()
