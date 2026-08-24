from docplex.mp.model import Model


def solve_channel_allocation():
    markets = {
        "US": {"demand": 6200, "min_fast_share": 0.78},
        "EU": {"demand": 5200, "min_fast_share": 0.72},
        "UK": {"demand": 2600, "min_fast_share": 0.65},
    }

    channels = {
        "marketplace_fba": {
            "capacity": 5200,
            "referral_fee_rate": 0.15,
            "fulfillment_cost": {"US": 5.4, "EU": 6.0, "UK": 6.2},
            "delivery_days": {"US": 2, "EU": 2, "UK": 3},
        },
        "brand_3pl": {
            "capacity": 6200,
            "referral_fee_rate": 0.04,
            "fulfillment_cost": {"US": 6.1, "EU": 6.4, "UK": 6.8},
            "delivery_days": {"US": 3, "EU": 3, "UK": 4},
        },
        "direct_cross_border": {
            "capacity": 9000,
            "referral_fee_rate": 0.02,
            "fulfillment_cost": {"US": 5.0, "EU": 5.4, "UK": 5.3},
            "delivery_days": {"US": 9, "EU": 9, "UK": 8},
        },
    }

    average_order_value = {
        "US": 38,
        "EU": 36,
        "UK": 34,
    }
    product_cost = {
        "US": 16,
        "EU": 15,
        "UK": 14,
    }

    model = Model(name="cross_border_channel_allocation")

    orders = {
        (channel, market): model.continuous_var(
            name=f"orders_{channel}_{market}",
            lb=0,
        )
        for channel in channels
        for market in markets
    }

    contribution = model.sum(
        (
            average_order_value[market]
            - product_cost[market]
            - channels[channel]["fulfillment_cost"][market]
            - channels[channel]["referral_fee_rate"] * average_order_value[market]
        )
        * orders[channel, market]
        for channel in channels
        for market in markets
    )

    model.maximize(contribution)

    for market, data in markets.items():
        model.add_constraint(
            model.sum(orders[channel, market] for channel in channels)
            == data["demand"],
            ctname=f"demand_{market}",
        )
        model.add_constraint(
            model.sum(
                orders[channel, market]
                for channel in channels
                if channels[channel]["delivery_days"][market] <= 4
            )
            >= data["min_fast_share"] * data["demand"],
            ctname=f"fast_share_{market}",
        )

    for channel, data in channels.items():
        model.add_constraint(
            model.sum(orders[channel, market] for market in markets)
            <= data["capacity"],
            ctname=f"capacity_{channel}",
        )

    solution = model.solve(log_output=True)
    if solution is None:
        print("No feasible channel allocation found.")
        return

    print("Cross-border channel allocation")
    print("===============================")
    print()
    print("Channel usage")
    print("-------------")
    for channel in channels:
        volume = sum(orders[channel, market].solution_value for market in markets)
        if volume > 1e-6:
            print(f"{channel}: {volume:g} orders")

    print()
    print("Market allocation")
    print("-----------------")
    for market, data in markets.items():
        fast_orders = 0
        print(f"{market}: demand={data['demand']}")
        for channel in channels:
            amount = orders[channel, market].solution_value
            if amount > 1e-6:
                days = channels[channel]["delivery_days"][market]
                if days <= 4:
                    fast_orders += amount
                contribution_per_order = (
                    average_order_value[market]
                    - product_cost[market]
                    - channels[channel]["fulfillment_cost"][market]
                    - channels[channel]["referral_fee_rate"] * average_order_value[market]
                )
                print(
                    f"  {channel}: {amount:g} orders, "
                    f"contribution={contribution_per_order:g}, days={days}"
                )
        print(f"  fast_share={fast_orders / data['demand']:.1%}")

    print()
    print(f"Total contribution: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_channel_allocation()
