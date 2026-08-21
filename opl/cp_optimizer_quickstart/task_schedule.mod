using CP;

{string} Tasks = ...;
int duration[Tasks] = ...;

tuple Precedence {
  string before;
  string after;
}

{Precedence} precedences = ...;

dvar interval task[t in Tasks] size duration[t];

minimize
  max(t in Tasks) endOf(task[t]);

subject to {
  respectPrecedence:
    forall(p in precedences)
      endBeforeStart(task[p.before], task[p.after]);
}

execute {
  writeln("CP Optimizer task schedule:");
  var makespan = 0;
  for (var t in Tasks) {
    writeln(t, ": start=", task[t].start, ", end=", task[t].end);
    if (task[t].end > makespan) {
      makespan = task[t].end;
    }
  }
  writeln("Makespan: ", makespan);
}
