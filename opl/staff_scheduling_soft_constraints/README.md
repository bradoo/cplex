# Staff Scheduling Soft Constraints Lesson

This lesson turns daily demand coverage from a hard constraint into a soft
constraint. The model can still return a schedule when demand is too high, and
it reports the staffing shortage explicitly.

Recommended CPLEX Studio names:

- Project name: `staff_scheduling_soft_constraints`
- Run configuration name: `staff_soft_run`
- Model file: `staff_scheduling_soft_constraints.mod`
- Data file: `staff_scheduling_soft_constraints.dat`

Run steps:

1. File -> New -> OPL Project.
2. Create or import `staff_scheduling_soft_constraints.mod` and
   `staff_scheduling_soft_constraints.dat`.
3. Create a Run Configuration.
4. Add the model file and data file.
5. Click Run.

What changed from the cost lesson:

- `shortage[d]` is a nonnegative decision variable.
- The coverage rule becomes `assigned staff + shortage = required staff`.
- `shortagePenalty` makes uncovered demand expensive in the objective.
- Cost and fairness still matter, but the model first tries to avoid shortage.

Business interpretation:

- Hard constraints mean "never violate this rule."
- Soft constraints mean "avoid violating this rule, and measure the violation
  when reality makes it unavoidable."
- Use a high `shortagePenalty` when uncovered demand is much worse than cost or
  fairness tradeoffs.
