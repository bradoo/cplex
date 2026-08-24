from docplex.mp.model import Model


def default_replenishment_data():
    weeks = ["W1", "W2", "W3", "W4"]
    lanes = {
        "air": {"lead_time_weeks": 1, "unit_cost": 5.5, "weekly_capacity": 900},
        "ocean": {"lead_time_weeks": 3, "unit_cost": 1.8, "weekly_capacity": 1600},
    }
    demand = {
        "W1": 900,
        "W2": 1100,
        "W3": 1300,
        "W4": 1500,
    }

    initial_inventory = 1200
    target_ending_inventory = 800
    holding_cost = 0.35
    stockout_penalty = 18

    return {
        "weeks": weeks,
        "lanes": lanes,
        "demand": demand,
        "initial_inventory": initial_inventory,
        "target_ending_inventory": target_ending_inventory,
        "holding_cost": holding_cost,
        "stockout_penalty": stockout_penalty,
    }


def solve_replenishment_plan(data=None, log_output=True):
    data = data or default_replenishment_data()
    weeks = data["weeks"]
    lanes = data["lanes"]
    demand = data["demand"]
    initial_inventory = data["initial_inventory"]
    target_ending_inventory = data["target_ending_inventory"]
    holding_cost = data["holding_cost"]
    stockout_penalty = data["stockout_penalty"]

    model = Model(name="cross_border_ecommerce_replenishment")

    order = {
        (lane, week): model.continuous_var(name=f"order_{lane}_{week}", lb=0)
        for lane in lanes
        for week in weeks
    }
    ending_inventory = {
        week: model.continuous_var(name=f"ending_inventory_{week}", lb=0)
        for week in weeks
    }
    stockout = {
        week: model.continuous_var(name=f"stockout_{week}", lb=0)
        for week in weeks
    }

    def arrivals(target_week_index):
        arrived = []
        for lane, lane_data in lanes.items():
            source_week_index = target_week_index - lane_data["lead_time_weeks"]
            if source_week_index >= 0:
                arrived.append(order[lane, weeks[source_week_index]])
        return model.sum(arrived) if arrived else 0

    for week_index, week in enumerate(weeks):
        starting_inventory = (
            initial_inventory
            if week_index == 0
            else ending_inventory[weeks[week_index - 1]]
        )
        model.add_constraint(
            ending_inventory[week]
            == starting_inventory + arrivals(week_index) - demand[week] + stockout[week],
            ctname=f"inventory_balance_{week}",
        )

    for lane, lane_data in lanes.items():
        for week in weeks:
            model.add_constraint(
                order[lane, week] <= lane_data["weekly_capacity"],
                ctname=f"capacity_{lane}_{week}",
            )

    model.add_constraint(
        ending_inventory["W4"] >= target_ending_inventory,
        ctname="target_ending_inventory",
    )

    transport_cost = model.sum(
        lanes[lane]["unit_cost"] * order[lane, week]
        for lane in lanes
        for week in weeks
    )
    inventory_cost = model.sum(
        holding_cost * ending_inventory[week]
        for week in weeks
    )
    stockout_cost = model.sum(
        stockout_penalty * stockout[week]
        for week in weeks
    )

    model.minimize(transport_cost + inventory_cost + stockout_cost)

    solution = model.solve(log_output=log_output)
    if solution is None:
        return {
            "status": "infeasible",
            "message": "No feasible replenishment plan found.",
        }

    orders = {
        (lane, week): order[lane, week].solution_value
        for lane in lanes
        for week in weeks
    }
    inventory_projection = {
        week: {
            "demand": demand[week],
            "ending_inventory": ending_inventory[week].solution_value,
            "stockout": stockout[week].solution_value,
        }
        for week in weeks
    }

    return {
        "status": "optimal",
        "orders": orders,
        "inventory_projection": inventory_projection,
        "transport_cost": transport_cost.solution_value,
        "holding_cost": inventory_cost.solution_value,
        "stockout_penalty": stockout_cost.solution_value,
        "total_cost": solution.objective_value,
        "total_stockout": sum(
            stockout[week].solution_value
            for week in weeks
        ),
    }


def print_replenishment_result(result, data):
    if result["status"] != "optimal":
        print(result["message"])
        return

    weeks = data["weeks"]
    lanes = data["lanes"]

    print("Cross-border replenishment plan")
    print("===============================")
    print()
    print("Orders placed")
    print("-------------")
    for week in weeks:
        for lane in lanes:
            amount = result["orders"][lane, week]
            if amount > 1e-6:
                print(f"{week} {lane}: {amount:g} units")

    print()
    print("Inventory projection")
    print("--------------------")
    for week in weeks:
        projection = result["inventory_projection"][week]
        print(
            f"{week}: demand={projection['demand']}, "
            f"ending_inventory={projection['ending_inventory']:g}, "
            f"stockout={projection['stockout']:g}"
        )

    print()
    print(f"Transport cost: {result['transport_cost']:g}")
    print(f"Holding cost: {result['holding_cost']:g}")
    print(f"Stockout penalty: {result['stockout_penalty']:g}")
    print(f"Total cost: {result['total_cost']:g}")


def main():
    data = default_replenishment_data()
    result = solve_replenishment_plan(data=data, log_output=True)
    print_replenishment_result(result, data)


if __name__ == "__main__":
    main()
