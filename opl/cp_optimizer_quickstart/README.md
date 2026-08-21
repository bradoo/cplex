# CP Optimizer Quickstart

This example shows how OPL switches from the CPLEX engine to CP Optimizer.
It matches the Quick Start topic "Two solving engines".

The key line is:

```opl
using CP;
```

Run with:

```bash
oplrun task_schedule.mod task_schedule.dat
```

Expected result:

```text
Prepare: start=0, end=2
Build: start=2, end=7
Test: start=7, end=10
Makespan: 10
```

Model meaning:

- Each task is an interval decision variable.
- `duration[t]` is the task length.
- `endBeforeStart(a, b)` forces task `a` to finish before task `b` starts.
- The objective minimizes the final completion time, also called makespan.

Use CPLEX for mathematical programming models such as LP and MIP.
Use CP Optimizer for scheduling models with intervals, precedence, and no-overlap logic.
