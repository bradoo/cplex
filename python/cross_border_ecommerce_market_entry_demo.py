from docplex.mp.model import Model


def solve_market_entry_case():
    markets = {
        "Canada": {"demand": 1800, "min_fast_share": 0.65},
        "Australia": {"demand": 1500, "min_fast_share": 0.55},
        "Singapore": {"demand": 900, "min_fast_share": 0.70},
    }

    channels = {
        "cross_border_direct": {
            "fixed_cost": 2500,
            "capacity": 4500,
            "unit_margin": {"Canada": 17, "Australia": 18, "Singapore": 16},
            "fulfillment_cost": {"Canada": 7.2, "Australia": 8.1, "Singapore": 6.7},
            "fast": {"Canada": 0, "Australia": 0, "Singapore": 0},
        },
        "regional_hub": {
            "fixed_cost": 14500,
            "capacity": 2800,
            "unit_margin": {"Canada": 17, "Australia": 18, "Singapore": 16},
            "fulfillment_cost": {"Canada": 6.1, "Australia": 6.4, "Singapore": 5.5},
            "fast": {"Canada": 1, "Australia": 1, "Singapore": 1},
        },
        "local_3pl": {
            "fixed_cost": 24000,
            "capacity": 2200,
            "unit_margin": {"Canada": 17, "Australia": 18, "Singapore": 16},
            "fulfillment_cost": {"Canada": 4.9, "Australia": 5.3, "Singapore": 4.7},
            "fast": {"Canada": 1, "Australia": 1, "Singapore": 1},
        },
    }

    model = Model(name="cross_border_market_entry")

    use_channel = {
        channel: model.binary_var(name=f"use_{channel}")
        for channel in channels
    }
    orders = {
        (channel, market): model.continuous_var(name=f"orders_{channel}_{market}", lb=0)
        for channel in channels
        for market in markets
    }

    gross_margin = model.sum(
        channels[channel]["unit_margin"][market] * orders[channel, market]
        for channel in channels
        for market in markets
    )
    fulfillment_cost = model.sum(
        channels[channel]["fulfillment_cost"][market] * orders[channel, market]
        for channel in channels
        for market in markets
    )
    fixed_cost = model.sum(
        channels[channel]["fixed_cost"] * use_channel[channel]
        for channel in channels
    )

    model.maximize(gross_margin - fulfillment_cost - fixed_cost)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(orders[channel, market] for channel in channels) == data["demand"],
            ctname=f"demand_{market}",
        )
        model.add_constraint(
            model.sum(
                channels[channel]["fast"][market] * orders[channel, market]
                for channel in channels
            )
            >= data["min_fast_share"] * data["demand"],
            ctname=f"fast_share_{market}",
        )

    for channel, data in channels.items():
        model.add_constraint(
            model.sum(orders[channel, market] for market in markets)
            <= data["capacity"] * use_channel[channel],
            ctname=f"capacity_if_used_{channel}",
        )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    allocation = []
    channel_totals = {}
    for channel in channels:
        total = sum(orders[channel, market].solution_value for market in markets)
        if total > 1e-6:
            channel_totals[channel] = total
    for market in markets:
        for channel in channels:
            amount = orders[channel, market].solution_value
            if amount > 1e-6:
                allocation.append(
                    {
                        "market": market,
                        "channel": channel,
                        "orders": amount,
                        "unit_margin": channels[channel]["unit_margin"][market],
                        "fulfillment_cost": channels[channel]["fulfillment_cost"][market],
                        "fast": bool(channels[channel]["fast"][market]),
                    }
                )

    return {
        "status": "optimal",
        "allocation": allocation,
        "channel_totals": channel_totals,
        "gross_margin": gross_margin.solution_value,
        "fulfillment_cost": fulfillment_cost.solution_value,
        "fixed_cost": fixed_cost.solution_value,
        "net_contribution": solution.objective_value,
    }


def print_result(result):
    print("Cross-border market entry")
    print("=========================")
    print()
    print("Channel totals")
    print("--------------")
    for channel, amount in result["channel_totals"].items():
        print(f"- {channel}: {amount:.0f} orders")

    print()
    print("Market allocation")
    print("-----------------")
    for row in result["allocation"]:
        fast = "fast" if row["fast"] else "slow"
        print(
            f"{row['market']:10} -> {row['channel']:20} "
            f"{row['orders']:6.0f} orders, "
            f"margin={row['unit_margin']:4.1f}, "
            f"fulfillment_cost={row['fulfillment_cost']:4.1f}, "
            f"{fast}"
        )

    print()
    print(f"Gross margin: {result['gross_margin']:.0f}")
    print(f"Fulfillment cost: {result['fulfillment_cost']:.0f}")
    print(f"Fixed market-entry cost: {result['fixed_cost']:.0f}")
    print(f"Net contribution: {result['net_contribution']:.0f}")


def main():
    print_result(solve_market_entry_case())


if __name__ == "__main__":
    main()
