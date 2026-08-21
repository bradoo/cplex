from docplex.mp.model import Model


def optimize_bmi_plan(
    height_cm,
    current_weight_kg,
    age,
    sex,
    target_bmi,
    weeks,
    workout_days_per_week,
    max_minutes_per_workout,
    min_daily_intake=None,
    max_daily_intake=2600,
    preferred_intake=2200,
    preferred_workout_minutes=45,
):
    height_m = height_cm / 100
    current_bmi = current_weight_kg / (height_m ** 2)
    target_weight_kg = target_bmi * (height_m ** 2)
    weight_to_lose_kg = current_weight_kg - target_weight_kg

    sex_adjustment = 5 if sex == "male" else -161
    bmr = 10 * current_weight_kg + 6.25 * height_cm - 5 * age + sex_adjustment
    base_daily_burn = bmr * 1.30
    kcal_per_kg = 7700
    kcal_per_workout_minute = 7

    total_days = weeks * 7
    required_daily_deficit = weight_to_lose_kg * kcal_per_kg / total_days

    if min_daily_intake is None:
        min_daily_intake = 1800 if sex == "male" else 1400

    model = Model(name="bmi_calorie_optimizer")

    daily_intake = model.continuous_var(
        name="daily_intake_kcal",
        lb=min_daily_intake,
        ub=max_daily_intake,
    )
    workout_minutes = model.continuous_var(
        name="workout_minutes_per_session",
        lb=0,
        ub=max_minutes_per_workout,
    )
    intake_deviation = model.continuous_var(name="intake_deviation", lb=0)
    workout_deviation = model.continuous_var(name="workout_deviation", lb=0)

    avg_daily_exercise_burn = (
        workout_days_per_week * workout_minutes * kcal_per_workout_minute / 7
    )
    daily_deficit = base_daily_burn + avg_daily_exercise_burn - daily_intake

    if required_daily_deficit >= 0:
        model.add_constraint(daily_deficit >= required_daily_deficit, "target_deficit")
        model.add_constraint(daily_deficit <= 550, "avoid_fast_weight_loss")
    else:
        model.add_constraint(daily_deficit >= required_daily_deficit, "avoid_fast_gain")
        model.add_constraint(daily_deficit <= 150, "small_surplus_or_deficit")

    model.add_constraint(daily_intake - preferred_intake <= intake_deviation)
    model.add_constraint(preferred_intake - daily_intake <= intake_deviation)
    model.add_constraint(workout_minutes - preferred_workout_minutes <= workout_deviation)
    model.add_constraint(preferred_workout_minutes - workout_minutes <= workout_deviation)

    model.minimize(intake_deviation + 8 * workout_deviation)

    solution = model.solve(log_output=False)
    if solution is None:
        return {
            "status": "infeasible",
            "message": "No feasible plan found with the selected limits.",
        }

    intake = daily_intake.solution_value
    minutes = workout_minutes.solution_value
    exercise_burn = avg_daily_exercise_burn.solution_value
    deficit = daily_deficit.solution_value
    expected_loss_kg = deficit * total_days / kcal_per_kg
    expected_weight_kg = current_weight_kg - expected_loss_kg
    expected_bmi = expected_weight_kg / (height_m ** 2)

    return {
        "status": "optimal",
        "height_cm": height_cm,
        "current_weight_kg": round(current_weight_kg, 1),
        "age": age,
        "sex": sex,
        "current_bmi": round(current_bmi, 2),
        "target_bmi": round(target_bmi, 2),
        "target_weight_kg": round(target_weight_kg, 1),
        "weight_to_lose_kg": round(weight_to_lose_kg, 1),
        "weeks": weeks,
        "daily_calorie_intake": round(intake),
        "workout_days_per_week": workout_days_per_week,
        "minutes_per_workout": round(minutes),
        "estimated_exercise_burn_per_workout": round(minutes * kcal_per_workout_minute),
        "average_daily_exercise_burn": round(exercise_burn),
        "average_daily_calorie_deficit": round(deficit),
        "expected_weight_kg": round(expected_weight_kg, 1),
        "expected_bmi": round(expected_bmi, 2),
        "bmr": round(bmr),
        "base_daily_burn": round(base_daily_burn),
        "assumptions": {
            "activity_multiplier": 1.30,
            "kcal_per_kg": kcal_per_kg,
            "kcal_per_workout_minute": kcal_per_workout_minute,
            "min_daily_intake": min_daily_intake,
            "max_daily_intake": max_daily_intake,
        },
        "message": "Learning model only; not medical advice.",
    }


def solve_bmi_plan():
    result = optimize_bmi_plan(
        height_cm=182,
        current_weight_kg=82,
        age=47,
        sex="male",
        target_bmi=23,
        weeks=26,
        workout_days_per_week=4,
        max_minutes_per_workout=60,
    )
    if result["status"] != "optimal":
        print(result["message"])
        return

    print("BMI calorie and exercise optimization")
    print("-------------------------------------")
    print(f"Height: {result['height_cm']} cm")
    print(f"Current weight: {result['current_weight_kg']:.1f} kg")
    print(f"Current BMI: {result['current_bmi']:.2f}")
    print(f"Target BMI: {result['target_bmi']:.2f}")
    print(f"Target weight: {result['target_weight_kg']:.1f} kg")
    print(f"Weight to lose: {result['weight_to_lose_kg']:.1f} kg")
    print(f"Time horizon: {result['weeks']} weeks")
    print()
    print("Optimized weekly plan")
    print("---------------------")
    print(f"Daily calorie intake: {result['daily_calorie_intake']} kcal")
    print(f"Workout days per week: {result['workout_days_per_week']}")
    print(f"Minutes per workout: {result['minutes_per_workout']}")
    print(
        "Estimated exercise burn per workout: "
        f"{result['estimated_exercise_burn_per_workout']} kcal"
    )
    print(f"Average daily exercise burn: {result['average_daily_exercise_burn']} kcal")
    print(f"Average daily calorie deficit: {result['average_daily_calorie_deficit']} kcal")
    print()
    print("Expected result")
    print("---------------")
    print(f"Expected weight after {result['weeks']} weeks: {result['expected_weight_kg']:.1f} kg")
    print(f"Expected BMI after {result['weeks']} weeks: {result['expected_bmi']:.2f}")
    print()
    print("Note: This is a learning model, not medical advice.")


if __name__ == "__main__":
    solve_bmi_plan()
