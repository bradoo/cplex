from cross_border_ecommerce_capacity_expansion_demo import (
    solve_capacity_expansion_network,
)


def run_penalty_sensitivity():
    penalties = [2, 4, 6, 10, 20, 50]
    rows = []
    for penalty in penalties:
        result = solve_capacity_expansion_network(
            demand_multiplier=1.25,
            unfulfilled_penalty=penalty,
            log_output=False,
            print_output=False,
        )
        rows.append({"penalty": penalty, "result": result})
    return rows


def print_summary(rows):
    headers = [
        "Penalty",
        "Unfulfilled",
        "Expansion",
        "Expanded warehouse",
        "Total cost",
    ]
    widths = [9, 12, 10, 28, 10]
    print(format_row(headers, widths))
    print(format_row(["-" * width for width in widths], widths))

    for row in rows:
        result = row["result"]
        expanded = [
            capacity
            for capacity in result["capacity_plan"]
            if capacity["extra_capacity"] > 1e-6
        ]
        expanded_text = ", ".join(
            f"{item['warehouse']} +{item['extra_capacity']:g}"
            for item in expanded
        )
        print(
            format_row(
                [
                    row["penalty"],
                    result["total_unfulfilled"],
                    result["expansion_cost"],
                    expanded_text or "-",
                    round(result["total_cost"]),
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
    print("Cross-border unfulfilled-penalty sensitivity")
    print("============================================")
    rows = run_penalty_sensitivity()
    print_summary(rows)


if __name__ == "__main__":
    main()
