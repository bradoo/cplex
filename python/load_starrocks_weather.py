import argparse
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen

import pymysql


MARKET_COORDINATES = {
    "US West": {"latitude": 34.0522, "longitude": -118.2437, "label": "Los Angeles"},
    "US East": {"latitude": 40.7128, "longitude": -74.0060, "label": "New York"},
    "Canada": {"latitude": 43.6532, "longitude": -79.3832, "label": "Toronto"},
    "UK": {"latitude": 51.5072, "longitude": -0.1276, "label": "London"},
    "EU": {"latitude": 52.3676, "longitude": 4.9041, "label": "Amsterdam"},
}


def connect(args):
    return pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def ensure_weather_table(cursor, replication_num):
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS upstream_weather_lane_impacts (
          warehouse VARCHAR(64) NOT NULL,
          market VARCHAR(64) NOT NULL,
          risk_level VARCHAR(32) NOT NULL,
          delay_days INT NOT NULL,
          cost_multiplier DOUBLE NOT NULL,
          reason VARCHAR(512) NOT NULL,
          snapshot_time VARCHAR(64) NOT NULL
        )
        DUPLICATE KEY(warehouse, market)
        DISTRIBUTED BY HASH(warehouse, market) BUCKETS 8
        PROPERTIES ("replication_num" = "{replication_num}")
        """
    )


def fetch_market_weather(market, coordinates, forecast_days, timeout):
    query = urlencode(
        {
            "latitude": coordinates["latitude"],
            "longitude": coordinates["longitude"],
            "daily": ",".join(
                [
                    "precipitation_sum",
                    "rain_sum",
                    "snowfall_sum",
                    "wind_speed_10m_max",
                    "temperature_2m_max",
                ]
            ),
            "forecast_days": forecast_days,
            "timezone": "auto",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{query}"
    with urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    daily = payload.get("daily", {})
    return {
        "market": market,
        "location": coordinates["label"],
        "max_precipitation": max([float(value or 0) for value in daily.get("precipitation_sum", [])] or [0]),
        "max_rain": max([float(value or 0) for value in daily.get("rain_sum", [])] or [0]),
        "max_snowfall": max([float(value or 0) for value in daily.get("snowfall_sum", [])] or [0]),
        "max_wind": max([float(value or 0) for value in daily.get("wind_speed_10m_max", [])] or [0]),
        "max_temperature": max([float(value or 0) for value in daily.get("temperature_2m_max", [])] or [0]),
    }


def classify_weather_risk(weather):
    score = 0
    reasons = []
    if weather["max_precipitation"] >= 25:
        score += 2
        reasons.append(f"降水 {weather['max_precipitation']:.1f}mm")
    elif weather["max_precipitation"] >= 10:
        score += 1
        reasons.append(f"降水 {weather['max_precipitation']:.1f}mm")
    if weather["max_snowfall"] >= 5:
        score += 2
        reasons.append(f"降雪 {weather['max_snowfall']:.1f}cm")
    elif weather["max_snowfall"] > 0:
        score += 1
        reasons.append(f"降雪 {weather['max_snowfall']:.1f}cm")
    if weather["max_wind"] >= 55:
        score += 2
        reasons.append(f"大风 {weather['max_wind']:.1f}km/h")
    elif weather["max_wind"] >= 35:
        score += 1
        reasons.append(f"大风 {weather['max_wind']:.1f}km/h")
    if weather["max_temperature"] >= 38:
        score += 1
        reasons.append(f"高温 {weather['max_temperature']:.1f}C")

    if score >= 3:
        return "high", 2, 1.18, "；".join(reasons) or "公共天气预报显示高风险"
    if score >= 1:
        return "medium", 1, 1.08, "；".join(reasons) or "公共天气预报显示中风险"
    return "low", 0, 1.02, "公共天气预报未见显著异常，保留轻微运行缓冲"


def load_network_lanes(cursor):
    cursor.execute("SELECT warehouse, market FROM upstream_network_lanes ORDER BY warehouse, market")
    return list(cursor.fetchall())


def build_weather_rows(args, cursor):
    lanes = load_network_lanes(cursor)
    forecasts = {
        market: fetch_market_weather(market, coordinates, args.forecast_days, args.timeout)
        for market, coordinates in MARKET_COORDINATES.items()
    }
    snapshot_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for lane in lanes:
        weather = forecasts.get(lane["market"])
        if not weather:
            continue
        risk_level, delay_days, cost_multiplier, reason = classify_weather_risk(weather)
        rows.append(
            (
                lane["warehouse"],
                lane["market"],
                risk_level,
                delay_days,
                cost_multiplier,
                f"{weather['location']} 未来 {args.forecast_days} 天天气：{reason}",
                snapshot_time,
            )
        )
    return rows, forecasts, snapshot_time


def load_weather(args):
    started_at = time.perf_counter()
    with connect(args) as connection:
        with connection.cursor() as cursor:
            ensure_weather_table(cursor, args.replication_num)
            rows, forecasts, snapshot_time = build_weather_rows(args, cursor)
            if args.truncate:
                cursor.execute("TRUNCATE TABLE upstream_weather_lane_impacts")
            if rows:
                cursor.executemany(
                    """
                    INSERT INTO upstream_weather_lane_impacts
                    (warehouse, market, risk_level, delay_days, cost_multiplier, reason, snapshot_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
    return {
        "database": args.database,
        "table": "upstream_weather_lane_impacts",
        "inserted_rows": len(rows),
        "snapshot_time": snapshot_time,
        "forecast_days": args.forecast_days,
        "market_forecasts": forecasts,
        "timings_seconds": {"total": round(time.perf_counter() - started_at, 3)},
    }


def main():
    parser = argparse.ArgumentParser(description="Load public weather forecast impacts into local StarRocks.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--database", default="cplex_poc")
    parser.add_argument("--forecast-days", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--replication-num", default="1")
    parser.add_argument("--no-truncate", action="store_false", dest="truncate")
    parser.set_defaults(truncate=True)
    args = parser.parse_args()
    print(json.dumps(load_weather(args), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
