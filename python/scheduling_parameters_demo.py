from scheduling_solver import default_problem, solve_staff_scheduling


def run_case(name, time_limit, mip_gap):
    problem = default_problem()
    result = solve_staff_scheduling(
        employees=problem["employees"],
        days=problem["days"],
        required_staff=problem["required_staff"],
        availability=problem["availability"],
        max_shifts_per_employee=problem["max_shifts_per_employee"],
        time_limit=time_limit,
        mip_gap=mip_gap,
    )

    print(f"\n{name}")
    print("-" * len(name))
    print(f"Status: {result['status']}")
    print(f"CPLEX solve status: {result['solve_status']}")
    print(f"Time limit: {time_limit} seconds")
    print(f"Requested MIP gap: {mip_gap}")
    print(f"Reported MIP gap: {result['reported_mip_gap']}")
    print(f"Solve time: {result['solve_time']} seconds")
    print(f"Fairness spread: {result['fairness_spread']}")


def main():
    run_case("Fast setting", time_limit=0.5, mip_gap=0.2)
    run_case("Balanced setting", time_limit=5, mip_gap=0.05)
    run_case("Exact setting", time_limit=30, mip_gap=0)


if __name__ == "__main__":
    main()
