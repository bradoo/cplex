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

  mustPickEverything:
    forall(i in Items)
      pick[i] == 1;

  impossibleSmallCapacity:
    capacity <= 1;
}
