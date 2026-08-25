from docplex.mp.model import Model


def solve_marketplace_allocation_case():
    skus = {
        "Phone Case": {"inventory": 5200, "unit_cost": 4.2},
        "Desk Lamp": {"inventory": 1500, "unit_cost": 19.0},
        "Earbuds": {"inventory": 1100, "unit_cost": 21.0},
    }

    channels = {
        "Amazon": {
            "commission_rate": 0.15,
            "fulfillment_cost": {"Phone Case": 3.0, "Desk Lamp": 6.2, "Earbuds": 4.8},
            "min_service_share": 0.35,
            "capacity": 4100,
        },
        "Shopify": {
            "commission_rate": 0.04,
            "fulfillment_cost": {"Phone Case": 4.1, "Desk Lamp": 7.0, "Earbuds": 5.2},
            "min_service_share": 0.20,
            "capacity": 3200,
        },
        "TikTok_Shop": {
            "commission_rate": 0.09,
            "fulfillment_cost": {"Phone Case": 3.7, "Desk Lamp": 6.6, "Earbuds": 5.0},
            "min_service_share": 0.15,
            "capacity": 2800,
        },
        "Wholesale": {
            "commission_rate": 0.00,
            "fulfillment_cost": {"Phone Case": 2.4, "Desk Lamp": 5.1, "Earbuds": 3.9},
            "min_service_share": 0.00,
            "capacity": 2400,
        },
    }

    demand = {
        ("Phone Case", "Amazon"): {"orders": 2600, "price": 14},
        ("Phone Case", "Shopify"): {"orders": 1600, "price": 15},
        ("Phone Case", "TikTok_Shop"): {"orders": 2200, "price": 13},
        ("Phone Case", "Wholesale"): {"orders": 1800, "price": 10},
        ("Desk Lamp", "Amazon"): {"orders": 850, "price": 42},
        ("Desk Lamp", "Shopify"): {"orders": 620, "price": 46},
        ("Desk Lamp", "TikTok_Shop"): {"orders": 700, "price": 40},
        ("Desk Lamp", "Wholesale"): {"orders": 500, "price": 32},
        ("Earbuds", "Amazon"): {"orders": 760, "price": 58},
        ("Earbuds", "Shopify"): {"orders": 520, "price": 62},
        ("Earbuds", "TikTok_Shop"): {"orders": 680, "price": 55},
        ("Earbuds", "Wholesale"): {"orders": 420, "price": 44},
    }

    lost_order_penalty = {
        "Amazon": 5.0,
        "Shopify": 4.0,
        "TikTok_Shop": 3.2,
        "Wholesale": 1.0,
    }

    model = Model(name="cross_border_marketplace_allocation")

    allocate = {
        (sku, channel): model.continuous_var(name=f"allocate_{sku}_{channel}", lb=0)
        for sku in skus
        for channel in channels
    }
    lost = {
        (sku, channel): model.continuous_var(name=f"lost_{sku}_{channel}", lb=0)
        for sku in skus
        for channel in channels
    }

    net_margin = model.sum(
        (
            demand[sku, channel]["price"] * (1 - channels[channel]["commission_rate"])
            - skus[sku]["unit_cost"]
            - channels[channel]["fulfillment_cost"][sku]
        )
        * allocate[sku, channel]
        for sku in skus
        for channel in channels
    )
    lost_penalty = model.sum(
        lost_order_penalty[channel] * lost[sku, channel]
        for sku in skus
        for channel in channels
    )

    model.maximize(net_margin - lost_penalty)

    for sku, data in skus.items():
        model.add_constraint(
            model.sum(allocate[sku, channel] for channel in channels) <= data["inventory"],
            ctname=f"inventory_{sku}",
        )

    for channel, data in channels.items():
        model.add_constraint(
            model.sum(allocate[sku, channel] for sku in skus) <= data["capacity"],
            ctname=f"channel_capacity_{channel}",
        )
        total_channel_demand = sum(demand[sku, channel]["orders"] for sku in skus)
        model.add_constraint(
            model.sum(allocate[sku, channel] for sku in skus)
            >= data["min_service_share"] * total_channel_demand,
            ctname=f"minimum_channel_service_{channel}",
        )

    for sku in skus:
        for channel in channels:
            model.add_constraint(
                allocate[sku, channel] + lost[sku, channel] == demand[sku, channel]["orders"],
                ctname=f"demand_balance_{sku}_{channel}",
            )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    allocation = []
    channel_totals = {}
    sku_totals = {}
    for channel in channels:
        channel_totals[channel] = sum(allocate[sku, channel].solution_value for sku in skus)
    for sku in skus:
        sku_totals[sku] = sum(allocate[sku, channel].solution_value for channel in channels)
        for channel in channels:
            amount = allocate[sku, channel].solution_value
            lost_amount = lost[sku, channel].solution_value
            if amount > 1e-6 or lost_amount > 1e-6:
                unit_net = (
                    demand[sku, channel]["price"] * (1 - channels[channel]["commission_rate"])
                    - skus[sku]["unit_cost"]
                    - channels[channel]["fulfillment_cost"][sku]
                )
                allocation.append(
                    {
                        "sku": sku,
                        "channel": channel,
                        "allocated": amount,
                        "lost": lost_amount,
                        "unit_net_margin": unit_net,
                    }
                )

    return {
        "status": "optimal",
        "allocation": allocation,
        "channel_totals": channel_totals,
        "sku_totals": sku_totals,
        "net_margin": net_margin.solution_value,
        "lost_penalty": lost_penalty.solution_value,
        "objective_value": solution.objective_value,
    }


def print_result(result):
    print("Cross-border marketplace inventory allocation")
    print("=============================================")
    print()
    print("Channel totals")
    print("--------------")
    for channel, amount in result["channel_totals"].items():
        print(f"- {channel}: {amount:.0f} units")
    print()
    print("SKU totals")
    print("----------")
    for sku, amount in result["sku_totals"].items():
        print(f"- {sku}: {amount:.0f} units")
    print()
    print("Allocation detail")
    print("-----------------")
    for row in result["allocation"]:
        print(
            f"{row['sku']:10} -> {row['channel']:11} "
            f"allocated={row['allocated']:6.0f}, lost={row['lost']:6.0f}, "
            f"unit_net_margin={row['unit_net_margin']:5.2f}"
        )
    print()
    print(f"Net margin: {result['net_margin']:.0f}")
    print(f"Lost order penalty: {result['lost_penalty']:.0f}")
    print(f"Objective value: {result['objective_value']:.0f}")


def main():
    print_result(solve_marketplace_allocation_case())


if __name__ == "__main__":
    main()
