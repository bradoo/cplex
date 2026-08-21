{string} Items = ...;
int capacity = ...;
int weight[Items] = ...;
int value[Items] = ...;

dvar boolean pick[Items];

maximize
  sum(i in Items) value[i] * pick[i];

subject to {
  capacityLimit:
    sum(i in Items) weight[i] * pick[i] <= capacity;
}

execute {
  writeln("Selected items:");
  for (var i in Items) {
    if (pick[i] > 0.5) {
      writeln("- ", i);
    }
  }
}
