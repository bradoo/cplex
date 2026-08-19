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
    solver_args = {
        "employees": data["employees"],
        "days": data["days"],
        "required_staff": data["required_staff"],
        "availability": data["availability"],
        "max_shifts_per_employee": int(data["max_shifts_per_employee"]),
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
