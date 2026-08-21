{string} Employees = ...;
{string} Days = ...;

int requiredStaff[Days] = ...;
int availability[Employees][Days] = ...;
int assignmentCost[Employees][Days] = ...;
int maxShiftsPerEmployee = ...;
int fairnessWeight = ...;
int costWeight = ...;

dvar boolean work[Employees][Days];
dvar int+ maxWorkload;
dvar int+ minWorkload;

dexpr int totalCost =
  sum(e in Employees, d in Days) assignmentCost[e][d] * work[e][d];

dexpr int fairnessSpread = maxWorkload - minWorkload;

minimize
  fairnessWeight * fairnessSpread + costWeight * totalCost;

subject to {
  coverDemand:
    forall(d in Days)
      sum(e in Employees) work[e][d] == requiredStaff[d];

  respectAvailability:
    forall(e in Employees, d in Days)
      work[e][d] <= availability[e][d];

  maxShifts:
    forall(e in Employees)
      sum(d in Days) work[e][d] <= maxShiftsPerEmployee;

  workloadUpper:
    forall(e in Employees)
      sum(d in Days) work[e][d] <= maxWorkload;

  workloadLower:
    forall(e in Employees)
      sum(d in Days) work[e][d] >= minWorkload;
}

execute {
  writeln("Schedule:");
  for (var d in Days) {
    write(d, ": ");
    var first = 1;
    for (var e in Employees) {
      if (work[e][d] > 0.5) {
        if (!first) {
          write(", ");
        }
        write(e);
        first = 0;
      }
    }
    writeln();
  }

  writeln();
  writeln("Workloads:");
  for (var e in Employees) {
    var total = 0;
    for (var d in Days) {
      if (work[e][d] > 0.5) {
        total += 1;
      }
    }
    writeln(e, ": ", total);
  }

  writeln();
  writeln("Fairness spread: ", fairnessSpread);
  writeln("Total assignment cost: ", totalCost);
  writeln("Weighted objective: ", fairnessWeight * fairnessSpread + costWeight * totalCost);
}
