from flask import Flask, jsonify, render_template, request

from bmi_calorie_optimizer_demo import optimize_bmi_plan


app = Flask(__name__)


@app.get("/")
def index():
    return render_template("bmi_app.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "cplex-bmi-optimizer"})


@app.post("/api/optimize")
def optimize():
    data = request.get_json(force=True)
    validation_error = validate_request(data)
    if validation_error:
        return jsonify({"status": "error", "message": validation_error}), 400

    result = optimize_bmi_plan(
        height_cm=float(data["height_cm"]),
        current_weight_kg=float(data["current_weight_kg"]),
        age=int(data["age"]),
        sex=data["sex"],
        target_bmi=float(data["target_bmi"]),
        weeks=int(data["weeks"]),
        workout_days_per_week=int(data["workout_days_per_week"]),
        max_minutes_per_workout=float(data["max_minutes_per_workout"]),
        preferred_intake=float(data.get("preferred_intake") or 2200),
        preferred_workout_minutes=float(data.get("preferred_workout_minutes") or 45),
    )
    return jsonify(result)


def validate_request(data):
    required = [
        "height_cm",
        "current_weight_kg",
        "age",
        "sex",
        "target_bmi",
        "weeks",
        "workout_days_per_week",
        "max_minutes_per_workout",
    ]
    missing = [key for key in required if key not in data]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"

    numeric_ranges = {
        "height_cm": (100, 230),
        "current_weight_kg": (35, 220),
        "age": (18, 90),
        "target_bmi": (18.5, 30),
        "weeks": (4, 104),
        "workout_days_per_week": (0, 7),
        "max_minutes_per_workout": (0, 180),
    }
    for key, (lower, upper) in numeric_ranges.items():
        try:
            value = float(data[key])
        except (TypeError, ValueError):
            return f"{key} must be numeric"
        if value < lower or value > upper:
            return f"{key} must be between {lower} and {upper}"

    if data["sex"] not in {"male", "female"}:
        return "sex must be male or female"

    return None


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5051, debug=True)
