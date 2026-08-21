{string} Employees = ...;
{string} Days = ...;

int requiredStaff[Days] = ...;
int availability[Employees][Days] = ...;
int maxShiftsPerEmployee = ...;
string outputPrefix = ...;

dvar boolean work[Employees][Days];
dvar int+ maxWorkload;
dvar int+ minWorkload;

minimize
  maxWorkload - minWorkload;

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
  writeln("Fairness spread: ", maxWorkload - minWorkload);

  var scheduleFile = new IloOplOutputFile(outputPrefix + "_schedule_output.csv");
  scheduleFile.writeln("day,employee,work");
  for (var d in Days) {
    for (var e in Employees) {
      if (work[e][d] > 0.5) {
        scheduleFile.writeln(d, ",", e, ",1");
      }
    }
  }
  scheduleFile.close();

  var summaryFile = new IloOplOutputFile(outputPrefix + "_workload_output.csv");
  summaryFile.writeln("employee,workload");
  for (var e in Employees) {
    var workload = 0;
    for (var d in Days) {
      if (work[e][d] > 0.5) {
        workload += 1;
      }
    }
    summaryFile.writeln(e, ",", workload);
  }
  summaryFile.writeln("fairness_spread,", maxWorkload - minWorkload);
  summaryFile.close();
}
