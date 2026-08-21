# CPLEX Learning Notes

This folder contains small CPLEX / DOcplex examples.

## Slides

The review/share deck is here:

```bash
cplex_intro_slides.md
```

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
```

## Run the knapsack example

```bash
cd python
python knapsack_docplex.py
```

## What the knapsack model means

- Decision variable: `pick_item = 1` means choose this item, `0` means skip it.
- Objective: maximize total value.
- Constraint: total weight must be less than or equal to the bag capacity.

## Run the transportation example

```bash
python transportation_docplex.py
```

## What the transportation model means

- Decision variable: `ship_warehouse_to_customer` means how many units to ship.
- Objective: minimize total shipping cost.
- Supply constraints: each warehouse cannot ship more than its available supply.
- Demand constraints: each customer must receive exactly its required demand.

## Run the facility location example

```bash
python facility_location_docplex.py
```

## What the facility location model means

- Binary decision variable: `open_facility = 1` means open this warehouse.
- Continuous decision variable: `ship_facility_to_customer` means how many units to ship.
- Objective: minimize fixed warehouse costs plus shipping costs.
- Demand constraints: each customer must receive exactly its required demand.
- Linking constraints: a warehouse can ship only if it is open.

## Run the staff scheduling example

```bash
python scheduling_docplex.py
```

## Run staff scheduling from CSV data

```bash
python scheduling_from_csv.py
```

Run a tighter demand scenario that falls back to soft constraints:

```bash
python scheduling_from_csv.py --employees data/employees_limited.csv --demand data/demand_hard.csv
```

## Run the solve-parameter demo

```bash
python scheduling_parameters_demo.py
```

This shows how `time_limit` and `mip_gap` affect CPLEX solving.

## Run the multi-objective scheduling demo

```bash
python scheduling_multi_objective_demo.py
```

This shows how employee preferences can be added alongside fairness.

## Run the what-if scenario demo

```bash
python scheduling_scenarios_demo.py
```

This compares multiple demand and staffing scenarios in one run.

It also exports reports:

```text
reports/scenario_summary.csv
reports/scenario_schedule.csv
reports/scenario_results.json
```

## View the staff scheduling web page

Open this file in a browser:

```bash
scheduling_solution.html
```

## Run the interactive staff scheduling app

```bash
python scheduling_app.py
```

Then open:

```text
http://127.0.0.1:5050
```

The manager demo script is here:

```bash
manager_demo.md
```

## What the staff scheduling model means

- Binary decision variable: `work_employee_day = 1` means this employee works that day.
- Coverage constraints: each day must have enough employees.
- Availability constraints: employees can work only when they are available.
- Workload constraints: each employee has a maximum number of shifts.
- Fairness objective: minimize the difference between the busiest and least busy employee.
- CSV data loading: read employees, demand, and availability from business tables.
- Solve parameters: set time limits and MIP gap targets for production-style solving.
- Multi-objective modeling: balance fairness with employee preference matching.
- What-if analysis: batch-run business scenarios and compare feasibility, shortage, fairness, and preference matches.
- Report export: write scenario summaries and detailed schedules to CSV/JSON.

## CPLEX vs Gurobi

CPLEX and Gurobi are similar commercial mathematical optimization solvers.

| Topic | CPLEX | Gurobi |
|---|---|---|
| Company | IBM | Gurobi Optimization |
| Main role | Mathematical optimization solver inside IBM Optimization Studio | Mathematical optimization solver focused on optimization APIs |
| Common model types | LP, MILP/MIP, QP, QCP, CP via CP Optimizer | LP, MILP/MIP, QP, QCP and related mathematical programming models |
| Python style | `docplex` or lower-level `cplex` API | `gurobipy` API |
| Scheduling angle | MILP models, plus CP Optimizer for complex scheduling | Usually MILP/MIQP style scheduling models |
| Learning transfer | Variables, objectives, constraints, soft constraints, MIP gap all transfer | Same modeling ideas transfer back to CPLEX |

The key lesson: CPLEX and Gurobi differ mostly in API, licensing, ecosystem, and performance details. The modeling skill is shared.
