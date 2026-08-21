# Staff Scheduling Cost Lesson

This lesson extends the quickstart staff scheduling model with assignment
costs. It shows a common business pattern: keep hard constraints strict, then
use the objective function to choose the best feasible schedule.

Recommended CPLEX Studio names:

- Project name: `staff_scheduling_cost`
- Run configuration name: `staff_cost_run`
- Model file: `staff_scheduling_cost.mod`
- Data file: `staff_scheduling_cost.dat`

Run steps:

1. File -> New -> OPL Project.
2. Create or import `staff_scheduling_cost.mod` and `staff_scheduling_cost.dat`.
3. Create a Run Configuration.
4. Add the model file and data file.
5. Click Run.

What changed from the quickstart:

- `assignmentCost[e][d]` gives the business cost of assigning employee `e` to
  day `d`.
- `fairnessWeight` controls how much the model cares about balanced workload.
- `costWeight` controls how much the model cares about low assignment cost.
- The objective minimizes both workload spread and total assignment cost.

Business interpretation:

- A high cost can represent overtime, preference mismatch, commute difficulty,
  or a less desirable shift.
- A low cost can represent a preferred or cheaper assignment.
- If the schedule becomes too expensive, increase `costWeight`.
- If the schedule becomes unfair, increase `fairnessWeight`.
