# Staff Scheduling OPL Quickstart

This folder contains a minimal staff scheduling model for CPLEX Studio.
Keep file names, project names, and run configuration names in English.

Recommended CPLEX Studio names:

- Project name: `staff_scheduling_quickstart`
- Run configuration name: `staff_scheduling_run`
- Model file: `staff_scheduling.mod`
- Data file: `staff_scheduling.dat`

Run steps:

1. File -> New -> OPL Project.
2. Create or import `staff_scheduling.mod` and `staff_scheduling.dat`.
3. Create a Run Configuration.
4. Add the model file and data file.
5. Click Run.

Model meaning:

- `work[e][d] = 1` means employee `e` works on day `d`.
- `requiredStaff[d]` is the number of employees needed on day `d`.
- `availability[e][d] = 1` means employee `e` is available on day `d`.
- `maxShiftsPerEmployee` limits each employee's weekly workload.
- The objective minimizes `maxWorkload - minWorkload`.
