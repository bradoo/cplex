{string} Warehouses = ...;
{string} Customers = ...;

int p = ...;
float demand[Customers] = ...;
float distance[Warehouses][Customers] = ...;

dvar boolean open[Warehouses];
dvar boolean assign[Warehouses][Customers];

minimize
  sum(w in Warehouses, c in Customers)
    demand[c] * distance[w][c] * assign[w][c];

subject to {
  openExactlyP:
    sum(w in Warehouses) open[w] == p;

  assignEachCustomer:
    forall(c in Customers)
      sum(w in Warehouses) assign[w][c] == 1;

  assignOnlyToOpenWarehouse:
    forall(w in Warehouses, c in Customers)
      assign[w][c] <= open[w];
}

execute {
  writeln("Opened warehouses:");
  for (var w in Warehouses) {
    if (open[w] > 0.5) {
      writeln("- ", w);
    }
  }

  writeln();
  writeln("Customer assignments:");
  for (var c in Customers) {
    for (var w in Warehouses) {
      if (assign[w][c] > 0.5) {
        writeln("- ", c, " -> ", w);
      }
    }
  }
}
