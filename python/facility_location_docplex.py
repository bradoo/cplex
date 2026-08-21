from docplex.mp.model import Model


def solve_facility_location():
    facilities = {
        "Shanghai": {"capacity": 100, "fixed_cost": 420},
        "Beijing": {"capacity": 90, "fixed_cost": 380},
        "Wuhan": {"capacity": 80, "fixed_cost": 300},
    }

    customers = {
        "Hangzhou": 50,
        "Shenzhen": 70,
        "Chengdu": 40,
    }

    shipping_cost = {
        ("Shanghai", "Hangzhou"): 2,
        ("Shanghai", "Shenzhen"): 6,
        ("Shanghai", "Chengdu"): 7,
        ("Beijing", "Hangzhou"): 5,
        ("Beijing", "Shenzhen"): 4,
        ("Beijing", "Chengdu"): 3,
        ("Wuhan", "Hangzhou"): 4,
        ("Wuhan", "Shenzhen"): 3,
        ("Wuhan", "Chengdu"): 4,
    }

    model = Model(name="facility_location")

    # open_facility[f] = 1 means we open facility f, 0 means we do not.
    open_facility = {
        f: model.binary_var(name=f"open_{f}")
        for f in facilities
    }

    # ship[f, c] means how many units facility f ships to customer c.
    ship = {
        (f, c): model.continuous_var(name=f"ship_{f}_to_{c}", lb=0)
        for f in facilities
        for c in customers
    }

    fixed_cost_total = model.sum(
        facilities[f]["fixed_cost"] * open_facility[f]
        for f in facilities
    )

    shipping_cost_total = model.sum(
        shipping_cost[f, c] * ship[f, c]
        for f in facilities
        for c in customers
    )

    # Objective: minimize warehouse fixed costs plus shipping costs.
    model.minimize(fixed_cost_total + shipping_cost_total)

    # Demand constraints: each customer must receive exactly its demand.
    for c, demand in customers.items():
        model.add_constraint(
            model.sum(ship[f, c] for f in facilities) == demand,
            ctname=f"demand_{c}",
        )

    # Linking constraints:
    # If facility f is closed, open_facility[f] = 0, so it cannot ship anything.
    # If it is open, total shipments can be at most its capacity.
    for f, data in facilities.items():
        model.add_constraint(
            model.sum(ship[f, c] for c in customers)
            <= data["capacity"] * open_facility[f],
            ctname=f"capacity_if_open_{f}",
        )

    solution = model.solve(log_output=True)

    if solution is None:
        print("No solution found.")
        return

    print("\nBest facility location plan")
    print("---------------------------")
    for f in facilities:
        if open_facility[f].solution_value > 0.5:
            print(f"- Open {f}")

    print("\nShipping plan")
    print("-------------")
    for f in facilities:
        for c in customers:
            amount = ship[f, c].solution_value
            if amount > 1e-6:
                route_cost = shipping_cost[f, c] * amount
                print(
                    f"- {f} -> {c}: amount={amount:g}, "
                    f"unit_cost={shipping_cost[f, c]}, cost={route_cost:g}"
                )

    print(f"\nTotal fixed cost: {fixed_cost_total.solution_value:g}")
    print(f"Total shipping cost: {shipping_cost_total.solution_value:g}")
    print(f"Total cost: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_facility_location()
