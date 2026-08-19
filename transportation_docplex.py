from docplex.mp.model import Model


def solve_transportation():
    warehouses = {
        "Shanghai": 80,
        "Beijing": 60,
    }

    customers = {
        "Hangzhou": 50,
        "Shenzhen": 70,
        "Chengdu": 20,
    }

    shipping_cost = {
        ("Shanghai", "Hangzhou"): 2,
        ("Shanghai", "Shenzhen"): 6,
        ("Shanghai", "Chengdu"): 7,
        ("Beijing", "Hangzhou"): 5,
        ("Beijing", "Shenzhen"): 4,
        ("Beijing", "Chengdu"): 3,
    }

    model = Model(name="transportation")

    # Decision variable:
    # x[w, c] means how many units to ship from warehouse w to customer c.
    x = {
        (w, c): model.continuous_var(name=f"ship_{w}_to_{c}", lb=0)
        for w in warehouses
        for c in customers
    }

    # Objective: minimize total shipping cost.
    model.minimize(
        model.sum(
            shipping_cost[w, c] * x[w, c]
            for w in warehouses
            for c in customers
        )
    )

    # Supply constraints: each warehouse cannot ship more than its supply.
    for w, supply in warehouses.items():
        model.add_constraint(
            model.sum(x[w, c] for c in customers) <= supply,
            ctname=f"supply_{w}",
        )

    # Demand constraints: each customer must receive exactly its demand.
    for c, demand in customers.items():
        model.add_constraint(
            model.sum(x[w, c] for w in warehouses) == demand,
            ctname=f"demand_{c}",
        )

    solution = model.solve(log_output=True)

    if solution is None:
        print("No solution found.")
        return

    print("\nBest shipping plan")
    print("------------------")
    for w in warehouses:
        for c in customers:
            amount = x[w, c].solution_value
            if amount > 1e-6:
                route_cost = shipping_cost[w, c] * amount
                print(
                    f"- {w} -> {c}: amount={amount:g}, "
                    f"unit_cost={shipping_cost[w, c]}, cost={route_cost:g}"
                )

    print(f"\nTotal cost: {solution.objective_value:g}")


if __name__ == "__main__":
    solve_transportation()
