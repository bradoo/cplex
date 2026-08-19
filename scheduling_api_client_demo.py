import json
import urllib.request


BASE_URL = "http://127.0.0.1:5050"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get_json(path):
    with OPENER.open(f"{BASE_URL}{path}") as response:
        return json.load(response)


def post_json(path, payload):
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with OPENER.open(request) as response:
        return json.load(response)


def main():
    health = get_json("/api/health")
    print("Health:", health)

    problem = get_json("/api/problem")
    problem["time_limit"] = 10
    problem["mip_gap"] = 0
    problem["preference_weight"] = 0.01
    problem["soft_constraints"] = False

    result = post_json("/api/solve", problem)

    print("\nAPI solve result")
    print("----------------")
    print("Status:", result["status"])
    print("Mode:", result["mode"])
    print("Total required shifts:", result["total_required_shifts"])
    print("Total shortage:", result["total_shortage"])
    print("Fairness spread:", result["fairness_spread"])
    print("Preference matches:", result["preference_matches"])
    print("Solve time:", result["solve_time"])

    print("\nSchedule")
    print("--------")
    for day in problem["days"]:
        print(f"{day}: {', '.join(result['schedule'][day])}")


if __name__ == "__main__":
    main()
