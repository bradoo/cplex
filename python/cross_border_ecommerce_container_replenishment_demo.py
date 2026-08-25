from docplex.mp.model import Model


def solve_container_replenishment_case():
    weeks = [1, 2, 3, 4, 5, 6]
    demand = {1: 1800, 2: 2100, 3: 2600, 4: 3200, 5: 2800, 6: 2400}
    initial_inventory = 2600
    target_ending_inventory = 900
    warehouse_capacity = 6800
    stockout_penalty = 16
    holding_cost = 0.18

    modes = {
        "air": {
            "lead_time": 1,
            "unit_cost": 7.8,
            "fixed_cost": 0,
            "batch_size": 1,
            "max_batches_per_week": 1800,
        },
        "lcl": {
            "lead_time": 2,
            "unit_cost": 4.3,
            "fixed_cost": 650,
            "batch_size": 500,
            "max_batches_per_week": 5,
        },
        "fcl": {
            "lead_time": 4,
            "unit_cost": 2.4,
            "fixed_cost": 3800,
            "batch_size": 2500,
            "max_batches_per_week": 2,
        },
    }

    order_weeks = weeks
    model = Model(name="cross_border_container_replenishment")

    batches = {
        (mode, week): model.integer_var(name=f"batches_{mode}_{week}", lb=0)
        for mode in modes
        for week in order_weeks
    }
    use_mode_week = {
        (mode, week): model.binary_var(name=f"use_{mode}_{week}")
        for mode in modes
        for week in order_weeks
        if modes[mode]["fixed_cost"] > 0
    }
    inventory = {
        week: model.continuous_var(name=f"inventory_{week}", lb=0)
        for week in weeks
    }
    stockout = {
        week: model.continuous_var(name=f"stockout_{week}", lb=0)
        for week in weeks
    }

    order_cost = model.sum(
        (
            modes[mode]["unit_cost"] * modes[mode]["batch_size"]
            + modes[mode]["fixed_cost"]
        )
        * batches[mode, week]
        for mode in modes
        for week in order_weeks
    )
    inventory_cost = model.sum(holding_cost * inventory[week] for week in weeks)
    shortage_cost = model.sum(stockout_penalty * stockout[week] for week in weeks)

    model.minimize(order_cost + inventory_cost + shortage_cost)

    for index, week in enumerate(weeks):
        previous_inventory = initial_inventory if index == 0 else inventory[weeks[index - 1]]
        arrivals = model.sum(
            modes[mode]["batch_size"] * batches[mode, order_week]
            for mode in modes
            for order_week in order_weeks
            if order_week + modes[mode]["lead_time"] == week
        )
        model.add_constraint(
            previous_inventory + arrivals + stockout[week] == demand[week] + inventory[week],
            ctname=f"inventory_balance_week_{week}",
        )
        model.add_constraint(inventory[week] <= warehouse_capacity, ctname=f"warehouse_capacity_week_{week}")

    model.add_constraint(
        inventory[weeks[-1]] >= target_ending_inventory,
        ctname="target_ending_inventory",
    )

    for mode, data in modes.items():
        for week in order_weeks:
            model.add_constraint(
                batches[mode, week] <= data["max_batches_per_week"],
                ctname=f"max_batches_{mode}_{week}",
            )
            if data["fixed_cost"] > 0:
                model.add_constraint(
                    batches[mode, week] <= data["max_batches_per_week"] * use_mode_week[mode, week],
                    ctname=f"use_if_ordered_{mode}_{week}",
                )

    solution = model.solve(log_output=False)
    if solution is None:
        return {"status": "infeasible"}

    orders = []
    for week in order_weeks:
        for mode in modes:
            count = batches[mode, week].solution_value
            if count > 1e-6:
                units = count * modes[mode]["batch_size"]
                arrival_week = week + modes[mode]["lead_time"]
                orders.append(
                    {
                        "order_week": week,
                        "arrival_week": arrival_week if arrival_week in weeks else "after_horizon",
                        "mode": mode,
                        "batches": count,
                        "units": units,
                    }
                )

    projection = []
    for week in weeks:
        projection.append(
            {
                "week": week,
                "demand": demand[week],
                "ending_inventory": inventory[week].solution_value,
                "stockout": stockout[week].solution_value,
            }
        )

    return {
        "status": "optimal",
        "orders": orders,
        "projection": projection,
        "order_cost": order_cost.solution_value,
        "holding_cost": inventory_cost.solution_value,
        "stockout_cost": shortage_cost.solution_value,
        "total_cost": solution.objective_value,
    }


def print_result(result):
    print("Cross-border container replenishment")
    print("====================================")
    print()
    print("Orders")
    print("------")
    for row in result["orders"]:
        print(
            f"week {row['order_week']} {row['mode']:3} "
            f"batches={row['batches']:.0f}, units={row['units']:.0f}, "
            f"arrives={row['arrival_week']}"
        )
    print()
    print("Inventory projection")
    print("--------------------")
    for row in result["projection"]:
        print(
            f"week {row['week']}: demand={row['demand']:.0f}, "
            f"ending={row['ending_inventory']:.0f}, stockout={row['stockout']:.0f}"
        )
    print()
    print(f"Order cost: {result['order_cost']:.0f}")
    print(f"Holding cost: {result['holding_cost']:.0f}")
    print(f"Stockout cost: {result['stockout_cost']:.0f}")
    print(f"Total cost: {result['total_cost']:.0f}")


def main():
    print_result(solve_container_replenishment_case())


if __name__ == "__main__":
    main()
