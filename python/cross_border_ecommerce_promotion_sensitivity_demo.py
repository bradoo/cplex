from cross_border_ecommerce_promotion_planning_demo import solve_promotion_plan


def run_promotion_budget_sensitivity():
    budgets = [0, 2200, 3600, 5000, 6200, 9000]
    rows = []
    for budget in budgets:
        result = solve_promotion_plan(
            promo_budget=budget,
            max_promoted_skus=2,
            log_output=False,
            print_output=False,
        )
        promoted = [
            row["sku"]
            for row in result["skus"]
            if row["promoted"]
        ]
        rows.append(
            {
                "budget": budget,
                "promoted": promoted,
                "fulfilled": result["total_fulfilled_orders"],
                "promo_spend": result["promotion_spend"],
                "net_contribution": result["net_contribution"],
            }
        )
    return rows


def print_summary(rows):
    headers = ["Budget", "Spend", "Promoted SKUs", "Fulfilled", "Net contribution"]
    widths = [8, 8, 38, 10, 16]
    print("Cross-border promotion budget sensitivity")
    print("=========================================")
    print(format_row(headers, widths))
    print(format_row(["-" * width for width in widths], widths))
    for row in rows:
        print(
            format_row(
                [
                    row["budget"],
                    round(row["promo_spend"]),
                    ", ".join(row["promoted"]) or "-",
                    round(row["fulfilled"]),
                    round(row["net_contribution"]),
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
    print_summary(run_promotion_budget_sensitivity())


if __name__ == "__main__":
    main()
