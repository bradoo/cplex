import csv
import tempfile
import unittest
from pathlib import Path

from scheduling_app import app
from scheduling_scenarios_demo import export_reports, solve_scenario
from scheduling_solver import (
    default_problem,
    solve_staff_scheduling,
    solve_staff_scheduling_soft,
)


class SchedulingSolverTests(unittest.TestCase):
    def test_default_problem_solves_with_no_shortage(self):
        problem = default_problem()
        result = solve_staff_scheduling(
            employees=problem["employees"],
            days=problem["days"],
            required_staff=problem["required_staff"],
            availability=problem["availability"],
            max_shifts_per_employee=problem["max_shifts_per_employee"],
            preferences=problem["preferences"],
        )

        self.assertEqual(result["status"], "optimal")
        self.assertEqual(result["mode"], "hard")
        self.assertEqual(result["total_shortage"], 0)
        self.assertEqual(result["total_required_shifts"], 14)
        self.assertLessEqual(result["fairness_spread"], 1)

    def test_soft_solver_reports_shortage_for_tight_weekend(self):
        problem = default_problem()
        problem["required_staff"].update({"Sat": 4, "Sun": 3})
        problem["max_shifts_per_employee"] = 4

        result = solve_staff_scheduling_soft(
            employees=problem["employees"],
            days=problem["days"],
            required_staff=problem["required_staff"],
            availability=problem["availability"],
            max_shifts_per_employee=problem["max_shifts_per_employee"],
            preferences=problem["preferences"],
        )

        self.assertEqual(result["status"], "optimal")
        self.assertEqual(result["mode"], "soft")
        self.assertGreater(result["total_shortage"], 0)

    def test_max_consecutive_work_days_is_enforced(self):
        problem = default_problem()
        result = solve_staff_scheduling(
            employees=problem["employees"],
            days=problem["days"],
            required_staff=problem["required_staff"],
            availability=problem["availability"],
            max_shifts_per_employee=problem["max_shifts_per_employee"],
            max_consecutive_work_days=2,
            preferences=problem["preferences"],
        )

        self.assertEqual(result["status"], "optimal")
        for employee in problem["employees"]:
            current_run = 0
            longest_run = 0
            for day in problem["days"]:
                if employee in result["schedule"][day]:
                    current_run += 1
                    longest_run = max(longest_run, current_run)
                else:
                    current_run = 0
            self.assertLessEqual(longest_run, 2)

    def test_skill_requirements_are_enforced(self):
        problem = default_problem()
        result = solve_staff_scheduling(
            employees=problem["employees"],
            days=problem["days"],
            required_staff=problem["required_staff"],
            availability=problem["availability"],
            max_shifts_per_employee=problem["max_shifts_per_employee"],
            skills=problem["skills"],
            skill_requirements=problem["skill_requirements"],
            preferences=problem["preferences"],
        )

        self.assertEqual(result["status"], "optimal")
        for day in problem["days"]:
            seniors = [
                employee
                for employee in result["schedule"][day]
                if "senior" in problem["skills"][employee]
            ]
            self.assertGreaterEqual(len(seniors), 1)


class SchedulingApiTests(unittest.TestCase):
    def test_health_and_solve_api(self):
        with app.test_client() as client:
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.get_json()["status"], "ok")

            problem = client.get("/api/problem").get_json()
            response = client.post("/api/solve", json=problem)
            result = response.get_json()

            self.assertEqual(response.status_code, 200)
            self.assertEqual(result["status"], "optimal")
            self.assertEqual(result["total_shortage"], 0)

    def test_solve_api_validates_required_fields(self):
        with app.test_client() as client:
            response = client.post("/api/solve", json={"employees": []})
            result = response.get_json()

            self.assertEqual(response.status_code, 400)
            self.assertEqual(result["status"], "error")
            self.assertIn("Missing required fields", result["message"])


class ScenarioReportTests(unittest.TestCase):
    def test_scenario_reports_are_exported(self):
        rows = [
            solve_scenario("Baseline", {}),
            solve_scenario(
                "Weekend peak",
                {
                    "required_staff": {"Sat": 4, "Sun": 3},
                    "max_shifts_per_employee": 4,
                },
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            export_reports(rows, output_dir)

            summary_path = output_dir / "scenario_summary.csv"
            schedule_path = output_dir / "scenario_schedule.csv"
            json_path = output_dir / "scenario_results.json"

            self.assertTrue(summary_path.exists())
            self.assertTrue(schedule_path.exists())
            self.assertTrue(json_path.exists())

            with summary_path.open(newline="") as file:
                summary_rows = list(csv.DictReader(file))

            self.assertEqual(len(summary_rows), 2)
            self.assertEqual(summary_rows[0]["scenario"], "Baseline")


if __name__ == "__main__":
    unittest.main()
