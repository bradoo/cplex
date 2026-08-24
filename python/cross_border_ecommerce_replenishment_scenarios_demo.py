from copy import deepcopy

from cross_border_ecommerce_replenishment_demo import (
    default_replenishment_data,
    solve_replenishment_plan,
)


def run_scenarios():
    base = default_replenishment_data()

    air_capacity_boost = deepcopy(base)
    air_capacity_boost["lanes"]["air"]["weekly_capacity"] = 1200

    higher_stockout_penalty = deepcopy(base)
    higher_stockout_penalty["stockout_penalty"] = 35

    faster_ocean = deepcopy(base)
    faster_ocean["lanes"]["ocean"]["lead_time_weeks"] = 2

    scenarios = [
        ("Base plan", base),
        ("Air capacity +300", air_capacity_boost),
        ("Higher stockout penalty", higher_stockout_penalty),
        ("Ocean lead time -1 week", faster_ocean),
    ]

    rows = []
    for name, data in scenarios:
        result = solve_replenishment_plan(data=data, log_output=False)
        rows.append({"scenario": name, "data": data, "result": result})
    return rows


def print_summary(rows):
    headers = [
        "Scenario",
        "Status",
        "Stockout",
        "Transport",
        "Holding",
        "Penalty",
        "Total",
    ]
    widths = [24, 10, 9, 10, 9, 9, 9]
    print(format_row(headers, widths))
    print(format_row(["-" * width for width in widths], widths))
    for row in rows:
        result = row["result"]
        print(
            format_row(
                [
                    row["scenario"],
                    result["status"],
                    result.get("total_stockout", 0),
                    round(result.get("transport_cost", 0)),
                    round(result.get("holding_cost", 0)),
                    round(result.get("stockout_penalty", 0)),
                    round(result.get("total_cost", 0)),
                ],
                widths,
            )
        )


def print_order_plans(rows):
    for row in rows:
        result = row["result"]
        if result["status"] != "optimal":
            continue

        print()
        print(row["scenario"])
        print("-" * len(row["scenario"]))
        for week in row["data"]["weeks"]:
            parts = []
            for lane in row["data"]["lanes"]:
                amount = result["orders"][lane, week]
                if amount > 1e-6:
                    parts.append(f"{lane} {amount:g}")
            if parts:
                print(f"{week}: {', '.join(parts)}")


def format_row(values, widths):
    return "  ".join(
        str(value)[:width].ljust(width)
        for value, width in zip(values, widths)
    )


def main():
    rows = run_scenarios()
    print("Cross-border replenishment scenario comparison")
    print("==============================================")
    print_summary(rows)
    print_order_plans(rows)


if __name__ == "__main__":
    main()
