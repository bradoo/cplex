import csv
import tempfile
import unittest
from pathlib import Path

from scheduling_app import app
from scheduling_diagnostics import diagnose_scheduling_conflicts
from scheduling_scenarios_demo import export_reports, solve_scenario
from scheduling_solver import (
    default_problem,
    solve_staff_scheduling,
    solve_staff_scheduling_soft,
    solve_staff_scheduling_two_stage,
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

    def test_soft_solver_reports_skill_shortage(self):
        problem = default_problem()
        problem["skill_requirements"]["Sun"] = {"night": 2}

        result = solve_staff_scheduling_soft(
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
        self.assertEqual(result["total_skill_shortage"], 1)
        self.assertEqual(result["skill_shortages"]["Sun:night"], 1)

    def test_soft_solver_does_not_overstaff_when_preferences_are_high(self):
        problem = default_problem()
        problem["days"] = ["Sun"]
        problem["required_staff"] = {"Sun": 1}
        problem["availability"] = {
            employee: {"Sun": int(employee in ["Carol", "David"])}
            for employee in problem["employees"]
        }
        problem["skill_requirements"] = {"Sun": {"night": 1}}
        problem["preferences"] = {
            employee: {"Sun": int(employee == "Carol")}
            for employee in problem["employees"]
        }

        result = solve_staff_scheduling_soft(
            employees=problem["employees"],
            days=problem["days"],
            required_staff=problem["required_staff"],
            availability=problem["availability"],
            max_shifts_per_employee=1,
            skills=problem["skills"],
            skill_requirements=problem["skill_requirements"],
            preferences=problem["preferences"],
            preference_weight=10,
            skill_shortage_penalty=1,
        )

        self.assertEqual(len(result["schedule"]["Sun"]), 1)
        self.assertEqual(result["schedule"]["Sun"], ["Carol"])
        self.assertEqual(result["total_skill_shortage"], 1)

    def test_two_stage_solver_prioritizes_shortages_before_preferences(self):
        problem = default_problem()
        problem["days"] = ["Sun"]
        problem["required_staff"] = {"Sun": 1}
        problem["availability"] = {
            employee: {"Sun": int(employee in ["Carol", "David"])}
            for employee in problem["employees"]
        }
        problem["skill_requirements"] = {"Sun": {"night": 1}}
        problem["preferences"] = {
            employee: {"Sun": int(employee == "Carol")}
            for employee in problem["employees"]
        }

        result = solve_staff_scheduling_two_stage(
            employees=problem["employees"],
            days=problem["days"],
            required_staff=problem["required_staff"],
            availability=problem["availability"],
            max_shifts_per_employee=1,
            skills=problem["skills"],
            skill_requirements=problem["skill_requirements"],
            preferences=problem["preferences"],
            preference_weight=10,
            skill_shortage_penalty=1,
        )

        self.assertEqual(result["status"], "optimal")
        self.assertEqual(result["mode"], "two_stage")
        self.assertEqual(result["total_skill_shortage"], 0)
        self.assertEqual(result["schedule"]["Sun"], ["David"])

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

    def test_cost_objective_returns_total_cost(self):
        problem = default_problem()
        result = solve_staff_scheduling(
            employees=problem["employees"],
            days=problem["days"],
            required_staff=problem["required_staff"],
            availability=problem["availability"],
            max_shifts_per_employee=problem["max_shifts_per_employee"],
            skills=problem["skills"],
            skill_requirements=problem["skill_requirements"],
            shift_costs=problem["shift_costs"],
            cost_weight=0.01,
            preferences=problem["preferences"],
        )

        self.assertEqual(result["status"], "optimal")
        self.assertGreater(result["total_cost"], 0)


class SchedulingDiagnosticsTests(unittest.TestCase):
    def test_diagnosis_reports_total_capacity_shortage(self):
        problem = default_problem()
        problem["max_shifts_per_employee"] = 2

        findings = diagnose_scheduling_conflicts(problem)
        finding_types = {finding["type"] for finding in findings}

        self.assertIn("total_capacity", finding_types)

    def test_diagnosis_reports_daily_availability_shortage(self):
        problem = default_problem()
        problem["required_staff"]["Sun"] = 4

        findings = diagnose_scheduling_conflicts(problem)
        daily_findings = [
            finding
            for finding in findings
            if finding["type"] == "daily_availability"
        ]

        self.assertEqual(daily_findings[0]["day"], "Sun")
        self.assertEqual(daily_findings[0]["gap"], 2)

    def test_diagnosis_reports_skill_coverage_shortage(self):
        problem = default_problem()
        problem["skill_requirements"]["Sun"] = {"night": 2}

        findings = diagnose_scheduling_conflicts(problem)
        skill_findings = [
            finding
            for finding in findings
            if finding["type"] == "skill_coverage"
        ]

        self.assertEqual(skill_findings[0]["day"], "Sun")
        self.assertEqual(skill_findings[0]["skill"], "night")


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
