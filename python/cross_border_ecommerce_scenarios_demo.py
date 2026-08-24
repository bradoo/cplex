from copy import deepcopy

from cross_border_ecommerce_network_demo import (
    default_network_data,
    solve_cross_border_network,
)


def relaxed_sla(markets, extra_days):
    scenario_markets = deepcopy(markets)
    for market in scenario_markets:
        scenario_markets[market]["max_delivery_days"] += extra_days
    return scenario_markets


def peak_demand(markets, multiplier):
    scenario_markets = deepcopy(markets)
    for market in scenario_markets:
        scenario_markets[market]["demand"] = round(
            scenario_markets[market]["demand"] * multiplier
        )
    return scenario_markets


def run_scenarios():
    _, base_markets, _, _ = default_network_data()
    scenarios = [
        ("Strict SLA", deepcopy(base_markets)),
        ("Relaxed SLA +6 days", relaxed_sla(base_markets, 6)),
        ("Peak demand +25%", peak_demand(base_markets, 1.25)),
    ]

    rows = []
    for name, markets in scenarios:
        result = solve_cross_border_network(markets=markets, log_output=False)
        rows.append(
            {
                "scenario": name,
                "markets": markets,
                "result": result,
            }
        )
    return rows


def print_summary(rows):
    headers = [
        "Scenario",
        "Status",
        "Opened warehouses",
        "Fixed",
        "Variable",
        "Total",
    ]
    widths = [20, 10, 58, 10, 10, 10]
    print(format_row(headers, widths))
    print(format_row(["-" * width for width in widths], widths))
    for row in rows:
        result = row["result"]
        opened = ", ".join(result.get("opened_warehouses", []))
        print(
            format_row(
                [
                    row["scenario"],
                    result["status"],
                    opened,
                    round(result.get("fixed_cost", 0)),
                    round(result.get("variable_cost", 0)),
                    round(result.get("total_cost", 0)),
                ],
                widths,
            )
        )


def print_market_assignments(rows):
    for row in rows:
        result = row["result"]
        if result["status"] != "optimal":
            continue

        print()
        print(row["scenario"])
        print("-" * len(row["scenario"]))
        for market, assignments in result["fulfillment_plan"].items():
            parts = [
                f"{assignment['warehouse']} {assignment['orders']:g}"
                for assignment in assignments
            ]
            print(f"{market}: {', '.join(parts)}")


def format_row(values, widths):
    return "  ".join(
        str(value)[:width].ljust(width)
        for value, width in zip(values, widths)
    )


def main():
    rows = run_scenarios()
    print("Cross-border ecommerce scenario comparison")
    print("==========================================")
    print_summary(rows)
    print_market_assignments(rows)


if __name__ == "__main__":
    main()
