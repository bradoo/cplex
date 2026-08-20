from flask import Flask, jsonify, render_template, request

from scheduling_solver import (
    default_problem,
    solve_staff_scheduling,
    solve_staff_scheduling_soft,
)


app = Flask(__name__)


@app.get("/")
def index():
    return render_template("scheduling_app.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "cplex-scheduling"})


@app.get("/api/problem")
def get_problem():
    return jsonify(default_problem())


@app.get("/api/infeasible-demo")
def get_infeasible_demo():
    problem = default_problem()
    problem["required_staff"]["Fri"] = 4
    problem["required_staff"]["Sat"] = 4
    problem["required_staff"]["Sun"] = 3
    problem["max_shifts_per_employee"] = 3
    return jsonify(problem)


@app.post("/api/solve")
def solve():
    data = request.get_json(force=True)
    validation_error = validate_problem(data)
    if validation_error:
        return jsonify({"status": "error", "message": validation_error}), 400

    solver_args = {
        "employees": data["employees"],
        "days": data["days"],
        "required_staff": data["required_staff"],
        "availability": data["availability"],
        "max_shifts_per_employee": int(data["max_shifts_per_employee"]),
        "max_consecutive_work_days": optional_int(data.get("max_consecutive_work_days")),
        "preferences": data.get("preferences"),
        "preference_weight": float(data.get("preference_weight") or 0.01),
        "time_limit": float(data.get("time_limit") or 0),
        "mip_gap": float(data.get("mip_gap") or 0),
        "log_output": False,
    }
    if data.get("soft_constraints"):
        result = solve_staff_scheduling_soft(**solver_args)
    else:
        result = solve_staff_scheduling(**solver_args)
    return jsonify(result)


def optional_int(value):
    if value in (None, "", 0, "0"):
        return None
    return int(value)


def validate_problem(data):
    required_keys = [
        "employees",
        "days",
        "required_staff",
        "availability",
        "max_shifts_per_employee",
    ]
    missing = [key for key in required_keys if key not in data]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"

    employees = data["employees"]
    days = data["days"]
    if not employees:
        return "employees must not be empty"
    if not days:
        return "days must not be empty"

    for day in days:
        if day not in data["required_staff"]:
            return f"required_staff is missing day: {day}"

    for employee in employees:
        if employee not in data["availability"]:
            return f"availability is missing employee: {employee}"
        for day in days:
            if day not in data["availability"][employee]:
                return f"availability is missing {employee} / {day}"

    preferences = data.get("preferences")
    if preferences:
        for employee in employees:
            if employee not in preferences:
                return f"preferences is missing employee: {employee}"
            for day in days:
                if day not in preferences[employee]:
                    return f"preferences is missing {employee} / {day}"

    return None


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
