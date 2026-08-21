#!/usr/bin/env bash
set -euo pipefail

OPLRUN="${OPLRUN:-/Users/bradwoo/Applications/CPLEX_Studio_Community222/opl/bin/arm64_osx/oplrun}"

cd "$(dirname "$0")"
mkdir -p logs

for data_file in baseline.dat weekend_peak.dat; do
  scenario="${data_file%.dat}"
  echo "Running ${scenario}"
  "${OPLRUN}" staff_scheduling.mod "${data_file}" > "logs/${scenario}.log"
  echo "  log: logs/${scenario}.log"
  echo "  schedule: ${scenario}_schedule_output.csv"
  echo "  matrix: ${scenario}_schedule_matrix.csv"
  echo "  workload: ${scenario}_workload_output.csv"
done

python3 summarize_scenarios.py
