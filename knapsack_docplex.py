from docplex.mp.model import Model


def solve_knapsack():
    # Each item has a value and a weight. We choose a subset without exceeding capacity.
    items = [
        {"name": "laptop", "value": 500, "weight": 3},
        {"name": "camera", "value": 350, "weight": 2},
        {"name": "headphones", "value": 150, "weight": 1},
        {"name": "book", "value": 60, "weight": 2},
        {"name": "jacket", "value": 220, "weight": 2},
        {"name": "water", "value": 220, "weight": 3},
    ]
    capacity = 8

    model = Model(name="knapsack")

    # Decision variable:
    # x[i] = 1 means we put item i into the bag, x[i] = 0 means we leave it out.
    x = {
        item["name"]: model.binary_var(name=f"pick_{item['name']}")
        for item in items
    }

    # Objective: maximize total value.
    model.maximize(
        model.sum(item["value"] * x[item["name"]] for item in items)
    )

    # Constraint: total weight cannot exceed the bag capacity.
    model.add_constraint(
        model.sum(item["weight"] * x[item["name"]] for item in items) <= capacity,
        ctname="capacity_limit",
    )

    solution = model.solve(log_output=True)

    if solution is None:
        print("No solution found.")
        return

    chosen_items = [
        item
        for item in items
        if x[item["name"]].solution_value > 0.5
    ]

    total_value = sum(item["value"] for item in chosen_items)
    total_weight = sum(item["weight"] for item in chosen_items)

    print("\nBest packing plan")
    print("-----------------")
    for item in chosen_items:
        print(f"- {item['name']}: value={item['value']}, weight={item['weight']}")

    print(f"\nTotal value: {total_value}")
    print(f"Total weight: {total_weight}/{capacity}")


if __name__ == "__main__":
    solve_knapsack()
