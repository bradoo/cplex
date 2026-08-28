import argparse
import json
import tempfile
import time
from pathlib import Path

from platform_app import (
    build_data_quality_metrics,
    build_network_model_input,
    build_replenishment_model_input,
    build_service_level_model_input,
    build_staffing_model_input,
    load_upstream_data,
    validate_upstream_data,
)


MARKETS = ["Canada", "US East", "US West", "UK", "Germany"]
CHANNELS = ["marketplace", "direct_site", "social_shop", "retail_partner"]
PRIORITIES = ["standard", "expedited", "standard", "standard", "priority"]


def build_orders(sample_orders, target):
    orders = []
    sample_count = len(sample_orders)
    for index in range(1, target + 1):
        sample = sample_orders[(index - 1) % sample_count] if sample_count else {}
        orders.append(
            {
                "order_id": f"ORD-{index:07d}",
                "market": MARKETS[(index - 1) % len(MARKETS)],
                "channel": CHANNELS[((index - 1) // len(MARKETS)) % len(CHANNELS)],
                "units": int(sample.get("units", ((index * 7) % 48) + 2)),
                "priority": PRIORITIES[((index - 1) // 17) % len(PRIORITIES)],
                "requested_delivery_days": int(sample.get("requested_delivery_days", 3 + (index % 4))),
                "demand_share_bp": round(float(sample.get("demand_share_bp", ((index * 37) % 10000) / 100)), 2),
            }
        )
    return orders


def benchmark(target):
    source_data = load_upstream_data()
    sample_orders = source_data.get("orders", [])

    generated_at = time.perf_counter()
    source_data["orders"] = build_orders(sample_orders, target)
    if isinstance(source_data.get("metadata"), dict):
        source_data["metadata"]["order_line_count"] = target
        source_data["metadata"]["volume_profile"] = f"{target:,} order-line throughput benchmark"

    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".json", delete=False) as file:
        json.dump(source_data, file, ensure_ascii=False, separators=(",", ":"))
        temp_path = Path(file.name)

    written_at = time.perf_counter()
    loaded_data = json.loads(temp_path.read_text(encoding="utf-8"))
    loaded_at = time.perf_counter()
    validation_error = validate_upstream_data(loaded_data)
    validated_at = time.perf_counter()
    metrics = build_data_quality_metrics(loaded_data)
    metrics_ready_at = time.perf_counter()
    config = {
        "demand_multiplier": 1,
        "sla_extra_days": 0,
        "air_capacity": 900,
        "ocean_lead_time": 3,
        "unfulfilled_penalty": 50,
        "network_mode": "strict",
        "staff_peak": False,
        "soft_staffing": False,
    }
    model_inputs = {
        "network": build_network_model_input(config, loaded_data["network"]),
        "replenishment": build_replenishment_model_input(config, loaded_data["replenishment"]),
        "service_level": build_service_level_model_input(loaded_data["service_level"]),
        "staffing": build_staffing_model_input(config),
    }
    model_inputs_ready_at = time.perf_counter()

    result = {
        "target_order_lines": target,
        "temp_file": str(temp_path),
        "temp_file_mb": round(temp_path.stat().st_size / 1024 / 1024, 2),
        "validation_error": validation_error,
        "metrics_order_lines": metrics["order_lines"],
        "model_input_blocks": len(model_inputs),
        "timings_seconds": {
            "generate_and_write": round(written_at - generated_at, 3),
            "load_json": round(loaded_at - written_at, 3),
            "validate": round(validated_at - loaded_at, 3),
            "metrics": round(metrics_ready_at - validated_at, 3),
            "build_model_inputs": round(model_inputs_ready_at - metrics_ready_at, 3),
            "total_after_write": round(model_inputs_ready_at - written_at, 3),
        },
    }
    temp_path.unlink(missing_ok=True)
    return result


def main():
    parser = argparse.ArgumentParser(description="Benchmark upstream order-line volume without committing a huge JSON file.")
    parser.add_argument("--orders", type=int, default=1_000_000)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.orders), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
