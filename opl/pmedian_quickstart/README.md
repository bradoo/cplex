# P-Median OPL Quickstart

This folder contains a minimal OPL example for the CPLEX Optimization
Studio Quick Start.

Run it in CPLEX Studio:

1. File -> New -> OPL Project.
2. Set the project name to `pmedian_quickstart`.
3. Create or import `pmedian.mod` and `pmedian.dat`.
4. Create a Run Configuration with those two files.
5. Click the green Run button.

Model meaning:

- `open[w] = 1` means warehouse `w` is opened.
- `assign[w][c] = 1` means customer `c` is served by warehouse `w`.
- `p = 2` means exactly two warehouses can be opened.
- The objective minimizes total demand-weighted distance.
