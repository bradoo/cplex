from cross_border_ecommerce_capacity_expansion_demo import (
    solve_capacity_expansion_network,
)
from cross_border_ecommerce_network_demo import solve_cross_border_network
from cross_border_ecommerce_replenishment_demo import (
    default_replenishment_data,
    solve_replenishment_plan,
)
from cross_border_ecommerce_service_level_demo import solve_service_level_mix
from cross_border_ecommerce_soft_capacity_demo import solve_soft_capacity_network


def build_dashboard_rows():
    strict_network = solve_cross_border_network(log_output=False)
    soft_capacity = solve_soft_capacity_network(
        demand_multiplier=1.25,
        unfulfilled_penalty=50,
        log_output=False,
        print_output=False,
    )
    capacity_expansion = solve_capacity_expansion_network(
        demand_multiplier=1.25,
        unfulfilled_penalty=50,
        log_output=False,
        print_output=False,
    )
    replenishment = solve_replenishment_plan(
        data=default_replenishment_data(),
        log_output=False,
    )
    service_mix = solve_service_level_mix(log_output=False, print_output=False)

    return [
        {
            "area": "Warehouse network",
            "scenario": "Strict SLA",
            "primary_metric": "total_cost",
            "value": strict_network["total_cost"],
            "risk": f"unfulfilled={strict_network.get('total_unfulfilled', 0)}",
            "decision": ", ".join(strict_network["opened_warehouses"]),
        },
        {
            "area": "Warehouse network",
            "scenario": "Peak demand without expansion",
            "primary_metric": "weighted_cost",
            "value": soft_capacity["total_cost"],
            "risk": f"unfulfilled={soft_capacity['total_unfulfilled']}",
            "decision": "Report shortage by market",
        },
        {
            "area": "Warehouse network",
            "scenario": "Peak demand with expansion",
            "primary_metric": "weighted_cost",
            "value": capacity_expansion["total_cost"],
            "risk": f"unfulfilled={capacity_expansion['total_unfulfilled']}",
            "decision": expansion_decision(capacity_expansion),
        },
        {
            "area": "Replenishment",
            "scenario": "Base 4-week plan",
            "primary_metric": "total_cost",
            "value": replenishment["total_cost"],
            "risk": f"stockout={replenishment['total_stockout']}",
            "decision": order_summary(replenishment),
        },
        {
            "area": "Service level",
            "scenario": "Average SLA mix",
            "primary_metric": "total_cost",
            "value": service_mix["total_cost"],
            "risk": "avg SLA satisfied",
            "decision": service_summary(service_mix),
        },
    ]


def expansion_decision(result):
    expanded = [
        row
        for row in result["capacity_plan"]
        if row.get("extra_capacity", 0) > 1e-6
    ]
    if not expanded:
        return "No temporary expansion"
    return ", ".join(
        f"{row['warehouse']} +{row['extra_capacity']:g}"
        for row in expanded
    )


def order_summary(result):
    totals = {}
    for (lane, _week), amount in result["orders"].items():
        totals[lane] = totals.get(lane, 0) + amount
    return ", ".join(f"{lane} {amount:g}" for lane, amount in totals.items() if amount)


def service_summary(result):
    return ", ".join(
        f"{row['service']} {row['orders']:g}"
        for row in result["used_services"]
    )


def print_dashboard(rows):
    headers = ["Area", "Scenario", "Metric", "Value", "Risk", "Decision"]
    widths = [18, 30, 14, 10, 18, 72]
    print("Cross-border ecommerce optimization dashboard")
    print("=============================================")
    print(format_row(headers, widths))
    print(format_row(["-" * width for width in widths], widths))
    for row in rows:
        print(
            format_row(
                [
                    row["area"],
                    row["scenario"],
                    row["primary_metric"],
                    round(row["value"], 2),
                    row["risk"],
                    row["decision"],
                ],
                widths,
            )
        )


def format_row(values, widths):
    return "  ".join(
        str(value)[:width].ljust(width)
        for value, width in zip(values, widths)
    )


def main():
    print_dashboard(build_dashboard_rows())


if __name__ == "__main__":
    main()
