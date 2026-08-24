from docplex.mp.model import Model


def solve_returns_network():
    skus = {
        "Phone Case": {"resale_value": 5.5, "scrap_value": 0.4},
        "Bluetooth Earbuds": {"resale_value": 22.0, "scrap_value": 2.0},
        "Coffee Grinder": {"resale_value": 34.0, "scrap_value": 4.0},
    }

    return_regions = {
        "US": {"refurb_capacity": 1300},
        "EU": {"refurb_capacity": 900},
    }

    returned_units = {
        ("Phone Case", "US"): 900,
        ("Phone Case", "EU"): 620,
        ("Bluetooth Earbuds", "US"): 430,
        ("Bluetooth Earbuds", "EU"): 360,
        ("Coffee Grinder", "US"): 260,
        ("Coffee Grinder", "EU"): 220,
    }

    refurb_cost = {
        ("Phone Case", "US"): 1.0,
        ("Phone Case", "EU"): 1.1,
        ("Bluetooth Earbuds", "US"): 4.2,
        ("Bluetooth Earbuds", "EU"): 4.5,
        ("Coffee Grinder", "US"): 7.8,
        ("Coffee Grinder", "EU"): 8.2,
    }

    transfer_cost = {
        ("US", "EU"): 3.8,
        ("EU", "US"): 4.1,
    }

    model = Model(name="cross_border_returns_network")

    refurb_local = {
        (sku, region): model.continuous_var(
            name=f"refurb_local_{sku}_{region}",
            lb=0,
        )
        for sku in skus
        for region in return_regions
    }
    transfer_refurb = {
        (sku, source, target): model.continuous_var(
            name=f"transfer_refurb_{sku}_{source}_to_{target}",
            lb=0,
        )
        for sku in skus
        for source in return_regions
        for target in return_regions
        if source != target
    }
    scrap = {
        (sku, region): model.continuous_var(name=f"scrap_{sku}_{region}", lb=0)
        for sku in skus
        for region in return_regions
    }

    local_value = model.sum(
        (skus[sku]["resale_value"] - refurb_cost[sku, region])
        * refurb_local[sku, region]
        for sku in skus
        for region in return_regions
    )
    transfer_value = model.sum(
        (
            skus[sku]["resale_value"]
            - refurb_cost[sku, target]
            - transfer_cost[source, target]
        )
        * transfer_refurb[sku, source, target]
        for sku, source, target in transfer_refurb
    )
    scrap_value = model.sum(
        skus[sku]["scrap_value"] * scrap[sku, region]
        for sku in skus
        for region in return_regions
    )

    model.maximize(local_value + transfer_value + scrap_value)

    for sku in skus:
        for region in return_regions:
            outbound_transfers = model.sum(
                transfer_refurb[sku, region, target]
                for target in return_regions
                if target != region
            )
            model.add_constraint(
                refurb_local[sku, region] + outbound_transfers + scrap[sku, region]
                == returned_units[sku, region],
                ctname=f"returns_balance_{sku}_{region}",
            )

    for region, data in return_regions.items():
        inbound_transfers = model.sum(
            transfer_refurb[sku, source, region]
            for sku in skus
            for source in return_regions
            if source != region
        )
        model.add_constraint(
            model.sum(refurb_local[sku, region] for sku in skus)
            + inbound_transfers
            <= data["refurb_capacity"],
            ctname=f"refurb_capacity_{region}",
        )

    solution = model.solve(log_output=True)
    if solution is None:
        print("No feasible returns plan found.")
        return

    print("Cross-border returns and reverse logistics")
    print("==========================================")
    print()
    print("Return handling plan")
    print("--------------------")
    for sku in skus:
        print(sku)
        for region in return_regions:
            local_amount = refurb_local[sku, region].solution_value
            scrap_amount = scrap[sku, region].solution_value
            if local_amount > 1e-6:
                print(f"  refurb in {region}: {local_amount:g}")
            for target in return_regions:
                if target == region:
                    continue
                transfer_amount = transfer_refurb[sku, region, target].solution_value
                if transfer_amount > 1e-6:
                    print(f"  transfer {region} -> {target}: {transfer_amount:g}")
            if scrap_amount > 1e-6:
                print(f"  scrap in {region}: {scrap_amount:g}")

    print()
    print("Refurb capacity usage")
    print("---------------------")
    for region, data in return_regions.items():
        used = sum(
            refurb_local[sku, region].solution_value
            for sku in skus
        ) + sum(
            transfer_refurb[sku, source, region].solution_value
            for sku in skus
            for source in return_regions
            if source != region
        )
        print(f"{region}: {used:g} / {data['refurb_capacity']}")

    print()
    print(f"Net recovery value: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_returns_network()
