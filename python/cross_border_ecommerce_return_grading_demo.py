from docplex.mp.model import Model


def solve_return_grading_case():
    return_units = {
        ("A_grade", "Earbuds"): 360,
        ("B_grade", "Earbuds"): 520,
        ("C_grade", "Earbuds"): 300,
        ("A_grade", "Coffee Grinder"): 180,
        ("B_grade", "Coffee Grinder"): 280,
        ("C_grade", "Coffee Grinder"): 160,
        ("A_grade", "Yoga Mat"): 420,
        ("B_grade", "Yoga Mat"): 500,
        ("C_grade", "Yoga Mat"): 340,
    }

    channels = {
        "refurb_full_price": {"capacity": 900, "handling_cost": 6.2},
        "outlet": {"capacity": 1000, "handling_cost": 3.4},
        "wholesale_liquidation": {"capacity": 1300, "handling_cost": 1.2},
        "recycle_scrap": {"capacity": 2000, "handling_cost": 0.4},
    }

    recovery_value = {
        ("A_grade", "Earbuds"): {
            "refurb_full_price": 34,
            "outlet": 26,
            "wholesale_liquidation": 14,
            "recycle_scrap": 2,
        },
        ("B_grade", "Earbuds"): {
            "refurb_full_price": 24,
            "outlet": 22,
            "wholesale_liquidation": 13,
            "recycle_scrap": 2,
        },
        ("C_grade", "Earbuds"): {
            "refurb_full_price": 0,
            "outlet": 11,
            "wholesale_liquidation": 8,
            "recycle_scrap": 2,
        },
        ("A_grade", "Coffee Grinder"): {
            "refurb_full_price": 52,
            "outlet": 39,
            "wholesale_liquidation": 21,
            "recycle_scrap": 5,
        },
        ("B_grade", "Coffee Grinder"): {
            "refurb_full_price": 36,
            "outlet": 31,
            "wholesale_liquidation": 19,
            "recycle_scrap": 5,
        },
        ("C_grade", "Coffee Grinder"): {
            "refurb_full_price": 0,
            "outlet": 16,
            "wholesale_liquidation": 12,
            "recycle_scrap": 5,
        },
        ("A_grade", "Yoga Mat"): {
            "refurb_full_price": 19,
            "outlet": 15,
            "wholesale_liquidation": 8,
            "recycle_scrap": 1,
        },
        ("B_grade", "Yoga Mat"): {
            "refurb_full_price": 13,
            "outlet": 12,
            "wholesale_liquidation": 7,
            "recycle_scrap": 1,
        },
        ("C_grade", "Yoga Mat"): {
            "refurb_full_price": 0,
            "outlet": 6,
            "wholesale_liquidation": 4,
            "recycle_scrap": 1,
        },
    }

    model = Model(name="cross_border_return_grading")

    assign = {
        (grade, sku, channel): model.continuous_var(
            name=f"assign_{grade}_{sku}_{channel}", lb=0
        )
        for grade, sku in return_units
        for channel in channels
    }

    net_recovery = model.sum(
        (
            recovery_value[grade, sku][channel]
            - channels[channel]["handling_cost"]
        )
        * assign[grade, sku, channel]
        for grade, sku in return_units
        for channel in channels
    )

    model.maximize(net_recovery)

    for grade, sku in return_units:
        model.add_constraint(
            model.sum(assign[grade, sku, channel] for channel in channels)
            == return_units[grade, sku],
            ctname=f"return_balance_{grade}_{sku}",
        )
        if grade == "C_grade":
            model.add_constraint(
                assign[grade, sku, "refurb_full_price"] == 0,
                ctname=f"no_full_price_for_c_grade_{sku}",
            )

    for channel, data in channels.items():
        model.add_constraint(
            model.sum(assign[grade, sku, channel] for grade, sku in return_units)
            <= data["capacity"],
            ctname=f"channel_capacity_{channel}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    allocation = []
    channel_totals = {}
    for channel in channels:
        total = sum(assign[grade, sku, channel].solution_value for grade, sku in return_units)
        if total > 1e-6:
            channel_totals[channel] = total
    for grade, sku in return_units:
        for channel in channels:
            amount = assign[grade, sku, channel].solution_value
            if amount > 1e-6:
                allocation.append(
                    {
                        "grade": grade,
                        "sku": sku,
                        "channel": channel,
                        "units": amount,
                        "net_value": recovery_value[grade, sku][channel]
                        - channels[channel]["handling_cost"],
                    }
                )

    return {
        "status": "optimal",
        "allocation": allocation,
        "channel_totals": channel_totals,
        "net_recovery_value": solution.objective_value,
    }


def print_result(result):
    print("Cross-border return grading")
    print("===========================")
    print()
    print("Channel totals")
    print("--------------")
    for channel, amount in result["channel_totals"].items():
        print(f"- {channel}: {amount:.0f} units")

    print()
    print("Grading allocation")
    print("------------------")
    for row in result["allocation"]:
        print(
            f"{row['grade']:7} {row['sku']:14} -> {row['channel']:22} "
            f"{row['units']:6.0f} units, net_value={row['net_value']:5.1f}"
        )

    print()
    print(f"Net recovery value: {result['net_recovery_value']:.0f}")


def main():
    print_result(solve_return_grading_case())


if __name__ == "__main__":
    main()
