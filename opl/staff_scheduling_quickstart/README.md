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

Output files:

- Output names use `outputPrefix` from the data file.
- `baseline.dat` writes `baseline_schedule_output.csv` and `baseline_workload_output.csv`.
- `weekend_peak.dat` writes `weekend_peak_schedule_output.csv` and `weekend_peak_workload_output.csv`.
- In CPLEX Studio, refresh the project after running if the files do not appear.

Scenario practice:

- `baseline.dat` has the normal weekly demand.
- `weekend_peak.dat` raises weekend demand.
- Create two Run Configurations that use the same model file but different data files:
  - `staff_baseline_run`: `staff_scheduling.mod` + `baseline.dat`
  - `staff_weekend_peak_run`: `staff_scheduling.mod` + `weekend_peak.dat`

This is the core Studio workflow: keep the model stable and switch data
files to compare business scenarios.

Model meaning:

- `work[e][d] = 1` means employee `e` works on day `d`.
- `requiredStaff[d]` is the number of employees needed on day `d`.
- `availability[e][d] = 1` means employee `e` is available on day `d`.
- `maxShiftsPerEmployee` limits each employee's weekly workload.
- The objective minimizes `maxWorkload - minWorkload`.
