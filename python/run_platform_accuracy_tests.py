import json
import os
import sys
import time
import traceback
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


os.environ.setdefault("PLATFORM_UPSTREAM_SOURCE", "starrocks")

import platform_app  # noqa: E402


REPORTS_DIR = Path(__file__).resolve().parent / "reports"
TEST_DOC = Path(__file__).resolve().parent.parent / "docs" / "platform_accuracy_test_cases.md"
EPS = 1e-5


@dataclass
class TestResult:
    case_id: str
    name: str
    status: str = "PASS"
    assertions: int = 0
    failures: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    elapsed_ms: float = 0


class PlatformAccuracyRunner:
    def __init__(self):
        self.client = platform_app.app.test_client()
        self.results = []
        self.cached_runs = {}

    def assert_true(self, result, condition, message):
        result.assertions += 1
        if not condition:
            result.status = "FAIL"
            result.failures.append(message)

    def run_case(self, case_id, name, func):
        result = TestResult(case_id=case_id, name=name)
        started = time.perf_counter()
        try:
            func(result)
        except Exception as error:
            result.status = "ERROR"
            result.failures.append(f"{type(error).__name__}: {error}")
            result.evidence["traceback"] = traceback.format_exc(limit=8)
        result.elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self.results.append(result)

    def get_json(self, path):
        response = self.client.get(path)
        return response.status_code, response.get_json()

    def post_json(self, path, payload, role="planner"):
        response = self.client.post(path, json=payload, headers={"X-Platform-Role": role})
        return response.status_code, response.get_json()

    def starrocks_count(self, table):
        with platform_app.starrocks_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) AS row_count FROM `{table}`")
                return int(cursor.fetchone()["row_count"])

    def starrocks_weather_rows(self):
        with platform_app.starrocks_connection() as connection:
            with connection.cursor() as cursor:
                platform_app.ensure_starrocks_weather_table(cursor)
                cursor.execute(
                    """
                    SELECT warehouse, market, risk_level, delay_days, cost_multiplier, reason, snapshot_time
                    FROM upstream_weather_lane_impacts
                    ORDER BY warehouse, market, risk_level, delay_days, cost_multiplier, reason
                    """
                )
                return list(cursor.fetchall())

    def replace_weather_rows(self, rows):
        with platform_app.starrocks_connection() as connection:
            with connection.cursor() as cursor:
                platform_app.ensure_starrocks_weather_table(cursor)
                cursor.execute("TRUNCATE TABLE upstream_weather_lane_impacts")
                if rows:
                    cursor.executemany(
                        """
                        INSERT INTO upstream_weather_lane_impacts
                        (warehouse, market, risk_level, delay_days, cost_multiplier, reason, snapshot_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            (
                                row["warehouse"],
                                row["market"],
                                row["risk_level"],
                                int(row["delay_days"]),
                                float(row["cost_multiplier"]),
                                row["reason"],
                                row.get("snapshot_time", ""),
                            )
                            for row in rows
                        ],
                    )
            connection.commit()

    def cached_run(self, playbook):
        if playbook not in self.cached_runs:
            self.cached_runs[playbook] = platform_app.run_case(playbook, {})
        return self.cached_runs[playbook]

    def tc01_source_health(self, result):
        status_code, payload = self.get_json("/api/platform/source-status")
        weather_tables = [row for row in payload.get("tables", []) if row.get("name") == "cplex_poc.upstream_weather_lane_impacts"]
        result.evidence = {
            "http_status": status_code,
            "mode": payload.get("mode"),
            "summary": payload.get("summary"),
            "weather_table": weather_tables[0] if weather_tables else None,
        }
        self.assert_true(result, status_code == 200, "source-status HTTP 状态码不是 200")
        self.assert_true(result, payload.get("status") == "ok", "source-status 不是 ok")
        self.assert_true(result, payload.get("mode") == "StarRocks", "平台没有运行在 StarRocks 模式")
        self.assert_true(result, payload.get("summary", {}).get("order_lines", 0) >= 1_000_000, "订单量不足 100 万")
        self.assert_true(result, bool(weather_tables), "source-status 未列出天气风险表")
        self.assert_true(result, weather_tables and weather_tables[0].get("rows", 0) > 0, "天气风险表没有数据")

    def tc02_weather_upstream(self, result):
        status_code, payload = self.get_json("/api/platform/upstream-data")
        weather = payload.get("data", {}).get("weather", {})
        table_count = self.starrocks_count("upstream_weather_lane_impacts")
        impacts = weather.get("lane_impacts", [])
        required = {"warehouse", "market", "risk_level", "delay_days", "cost_multiplier", "reason"}
        result.evidence = {
            "http_status": status_code,
            "weather_source": weather.get("source"),
            "api_weather_rows": len(impacts),
            "table_weather_rows": table_count,
            "sample": impacts[:2],
        }
        self.assert_true(result, status_code == 200, "upstream-data HTTP 状态码不是 200")
        self.assert_true(result, weather.get("source") == "StarRocks.upstream_weather_lane_impacts", "天气来源不是 StarRocks 天气表")
        self.assert_true(result, len(impacts) == table_count, "API 天气行数与 StarRocks 表行数不一致")
        self.assert_true(result, all(required.issubset(item) for item in impacts), "天气记录缺少必要字段")

    def tc03_weather_in_model_inputs(self, result):
        status_code, payload = self.post_json("/api/platform/run", {"playbook": "resilient", "overrides": {}})
        weather_inputs = [
            row
            for row in payload.get("model_inputs", {}).get("network", {}).get("lane_costs_and_sla", [])
            if row.get("weather_risk_level") not in ("none", "", None)
        ]
        weather_results = payload.get("network", {}).get("weather_impacted_lanes", [])
        result.evidence = {
            "http_status": status_code,
            "weather_source": payload.get("model_inputs", {}).get("lineage", {}).get("weather_source"),
            "weather_inputs": len(weather_inputs),
            "weather_results": len(weather_results),
        }
        self.assert_true(result, status_code == 200, "run HTTP 状态码不是 200")
        self.assert_true(result, payload.get("model_inputs", {}).get("lineage", {}).get("weather_source") == "StarRocks.upstream_weather_lane_impacts", "模型入参天气来源错误")
        self.assert_true(result, len(weather_inputs) > 0, "模型入参中没有天气线路")
        self.assert_true(result, len(weather_inputs) == len(weather_results), "模型入参与结果天气线路数不一致")

    def tc04_weather_cost_transform(self, result):
        payload = self.cached_run("resilient")
        weather_inputs = [
            row
            for row in payload["model_inputs"]["network"]["lane_costs_and_sla"]
            if row.get("weather_risk_level") not in ("none", "", None)
        ]
        mismatches = []
        for lane in weather_inputs:
            expected = round(lane["base_last_mile_cost"] * lane["weather_cost_multiplier"], 2)
            if abs(lane["last_mile_cost"] - expected) > 1e-9:
                mismatches.append({"lane": f"{lane['warehouse']}->{lane['market']}", "actual": lane["last_mile_cost"], "expected": expected})
        result.evidence = {"checked_lanes": len(weather_inputs), "mismatches": mismatches[:5]}
        self.assert_true(result, len(weather_inputs) > 0, "没有可检查的天气线路")
        self.assert_true(result, not mismatches, "存在天气成本转换错误")

    def tc05_weather_sla_transform(self, result):
        payload = self.cached_run("resilient")
        network_input = payload["model_inputs"]["network"]
        mismatches = []
        for lane in network_input["lane_costs_and_sla"]:
            expected_days = lane["base_delivery_days"] + lane["weather_delay_days"]
            expected_allowed = expected_days <= network_input["markets"][lane["market"]]["max_delivery_days"]
            if lane["delivery_days"] != expected_days or lane["allowed_by_sla"] != expected_allowed:
                mismatches.append(
                    {
                        "lane": f"{lane['warehouse']}->{lane['market']}",
                        "actual_days": lane["delivery_days"],
                        "expected_days": expected_days,
                        "actual_allowed": lane["allowed_by_sla"],
                        "expected_allowed": expected_allowed,
                    }
                )
        result.evidence = {
            "checked_lanes": len(network_input["lane_costs_and_sla"]),
            "weather_blocked_lanes": len([row for row in network_input["lane_costs_and_sla"] if row["weather_delay_days"] > 0 and not row["allowed_by_sla"]]),
            "mismatches": mismatches[:5],
        }
        self.assert_true(result, not mismatches, "存在天气时效或 SLA 判断错误")

    def tc06_blocked_lanes_not_used(self, result):
        violations = []
        for playbook in ("baseline", "peak", "resilient"):
            payload = self.cached_run(playbook)
            lanes = {
                (row["warehouse"], row["market"]): row
                for row in payload["model_inputs"]["network"]["lane_costs_and_sla"]
            }
            for market, rows in payload["network"].get("fulfillment_plan", {}).items():
                for row in rows:
                    lane = lanes[(row["warehouse"], market)]
                    if not lane["allowed_by_sla"] and float(row.get("orders") or 0) > EPS:
                        violations.append({"playbook": playbook, "lane": f"{row['warehouse']}->{market}", "orders": row["orders"]})
        result.evidence = {"checked_playbooks": ["baseline", "peak", "resilient"], "violations": violations[:5]}
        self.assert_true(result, not violations, "SLA 禁用线路仍被使用")

    def tc07_capacity_constraints(self, result):
        violations = []
        for playbook in ("baseline", "peak", "resilient"):
            payload = self.cached_run(playbook)
            for row in payload["network"].get("capacity_plan", []):
                limit = float(row.get("base_capacity") or 0) + float(row.get("extra_capacity") or 0)
                if float(row.get("used_capacity") or 0) - limit > EPS:
                    violations.append({"playbook": playbook, "warehouse": row["warehouse"], "used": row["used_capacity"], "limit": limit})
        result.evidence = {"checked_playbooks": ["baseline", "peak", "resilient"], "violations": violations[:5]}
        self.assert_true(result, not violations, "存在仓库容量超限")

    def tc08_service_demand_balance(self, result):
        payload = self.cached_run("resilient")
        service_input = payload["model_inputs"]["service_level"]
        allocation = payload["service_mix"].get("allocation", {})
        mismatches = []
        for market, data in service_input["markets"].items():
            allocated = sum(float(row.get("orders") or 0) for row in allocation.get(market, []))
            if abs(allocated - float(data["demand"])) > EPS:
                mismatches.append({"market": market, "allocated": allocated, "demand": data["demand"]})
        result.evidence = {"checked_markets": len(service_input["markets"]), "mismatches": mismatches[:5]}
        self.assert_true(result, not mismatches, "服务水平模型市场需求不平衡")

    def tc09_weather_ab_value(self, result):
        with_weather = self.cached_run("resilient")
        original_loader = platform_app.load_starrocks_weather
        try:
            platform_app.load_starrocks_weather = lambda cursor, fallback_weather=None: {
                "snapshot_time": "",
                "source": "validation.no_weather",
                "lane_impacts": [],
            }
            without_weather = platform_app.run_case("resilient", {})
        finally:
            platform_app.load_starrocks_weather = original_loader
        cost_delta = float(with_weather["summary"]["total_cost"]) - float(without_weather["summary"]["total_cost"])
        shortage_delta = float(with_weather["summary"]["total_shortage"]) - float(without_weather["summary"]["total_shortage"])
        result.evidence = {
            "with_weather_cost": with_weather["summary"]["total_cost"],
            "without_weather_cost": without_weather["summary"]["total_cost"],
            "cost_delta": cost_delta,
            "with_weather_lanes": len(with_weather["network"].get("weather_impacted_lanes", [])),
            "without_weather_lanes": len(without_weather["network"].get("weather_impacted_lanes", [])),
            "shortage_delta": shortage_delta,
        }
        self.assert_true(result, len(with_weather["network"].get("weather_impacted_lanes", [])) > 0, "有天气场景没有天气影响线路")
        self.assert_true(result, len(without_weather["network"].get("weather_impacted_lanes", [])) == 0, "无天气场景仍有天气影响线路")
        self.assert_true(result, abs(cost_delta) > EPS or abs(shortage_delta) > EPS, "天气 A/B 未造成关键 KPI 变化")

    def tc10_extreme_weather_injection(self, result):
        original_rows = self.starrocks_weather_rows()
        target_found = False
        modified_rows = []
        for row in original_rows:
            row = dict(row)
            if row["warehouse"] == "Los Angeles 3PL" and row["market"] == "US West":
                target_found = True
                row.update(
                    {
                        "risk_level": "high",
                        "delay_days": 5,
                        "cost_multiplier": 1.5,
                        "reason": "自动化测试：极端天气导致 US West 末端配送中断",
                    }
                )
            modified_rows.append(row)
        try:
            self.replace_weather_rows(modified_rows)
            self.cached_runs.clear()
            payload = platform_app.run_case("resilient", {})
            target_lane = next(
                row
                for row in payload["model_inputs"]["network"]["lane_costs_and_sla"]
                if row["warehouse"] == "Los Angeles 3PL" and row["market"] == "US West"
            )
            used_orders = sum(
                float(row.get("orders") or 0)
                for row in payload["network"].get("fulfillment_plan", {}).get("US West", [])
                if row.get("warehouse") == "Los Angeles 3PL"
            )
            result.evidence = {
                "target_found": target_found,
                "target_lane": target_lane,
                "used_orders": used_orders,
            }
            self.assert_true(result, target_found, "原始天气表中没有目标线路")
            self.assert_true(result, target_lane["weather_delay_days"] == 5, "极端天气延误天数没有进入模型入参")
            self.assert_true(result, abs(target_lane["weather_cost_multiplier"] - 1.5) < 1e-9, "极端天气成本系数没有进入模型入参")
            self.assert_true(result, target_lane["delivery_days"] == target_lane["base_delivery_days"] + 5, "极端天气配送天数计算错误")
            if not target_lane["allowed_by_sla"]:
                self.assert_true(result, used_orders <= EPS, "极端天气导致 SLA 禁用后线路仍被使用")
            else:
                self.assert_true(result, True, "目标线路未超过 SLA，无需断言禁用")
        finally:
            self.replace_weather_rows(original_rows)
            self.cached_runs.clear()

    def tc11_page_and_readonly_api_routes(self, result):
        pages = ["/", "/upstream", "/config", "/inputs", "/results", "/lineage", "/constraints", "/performance"]
        apis = [
            "/api/health",
            "/favicon.ico",
            "/api/platform/overview",
            "/api/platform/data",
            "/api/platform/config-audit",
            "/api/platform/data-quality",
            "/api/platform/data-quarantine",
            "/api/platform/scale-snapshot",
            "/api/platform/capacity-assessment",
            "/api/platform/enterprise-readiness",
            "/api/platform/lineage",
            "/api/platform/model-explanations",
            "/api/platform/compare",
            "/api/platform/run-history",
        ]
        statuses = {}
        for path in pages + apis:
            response = self.client.get(path)
            statuses[path] = response.status_code
            self.assert_true(result, response.status_code in {200, 204}, f"{path} 返回 {response.status_code}")
        result.evidence = {"checked_routes": len(statuses), "statuses": statuses}

    def tc12_permissions_and_validation_errors(self, result):
        checks = []
        response = self.client.post("/api/platform/run", json={"playbook": "baseline"})
        checks.append(("viewer_run_forbidden", response.status_code))
        self.assert_true(result, response.status_code == 403, "只读角色运行模型应被拒绝")

        response = self.client.post(
            "/api/platform/run",
            json={"playbook": "missing"},
            headers={"X-Platform-Role": "planner"},
        )
        checks.append(("unknown_playbook", response.status_code))
        self.assert_true(result, response.status_code == 400, "未知方案应返回 400")

        response = self.client.put(
            "/api/platform/data",
            json={"data": {"bad": "shape"}},
            headers={"X-Platform-Role": "planner"},
        )
        checks.append(("invalid_platform_data", response.status_code))
        self.assert_true(result, response.status_code == 400, "错误平台配置应返回 400")

        response = self.client.put(
            "/api/platform/upstream-data",
            json={"data": {"bad": "shape"}},
            headers={"X-Platform-Role": "data_admin"},
        )
        checks.append(("invalid_upstream_data", response.status_code))
        self.assert_true(result, response.status_code == 400, "错误上游数据应返回 400")

        response = self.client.post(
            "/api/platform/approval",
            json={"run_id": "missing", "action": "approve"},
            headers={"X-Platform-Role": "planner"},
        )
        checks.append(("planner_approve_forbidden", response.status_code))
        self.assert_true(result, response.status_code == 403, "计划员审批应被拒绝")

        response = self.client.post(
            "/api/platform/approval",
            json={"run_id": "missing", "action": "bad"},
            headers={"X-Platform-Role": "admin"},
        )
        checks.append(("bad_approval_action", response.status_code))
        self.assert_true(result, response.status_code == 400, "错误审批动作应返回 400")

        response = self.client.post(
            "/api/platform/publish-execution",
            json={},
            headers={"X-Platform-Role": "admin"},
        )
        checks.append(("missing_publish_run_id", response.status_code))
        self.assert_true(result, response.status_code == 400, "缺少 run_id 发布应返回 400")
        result.evidence = {"checks": checks}

    def tc13_config_save_audit_and_restore(self, result):
        original = platform_app.load_platform_data()
        modified = deepcopy(original)
        modified["playbooks"]["baseline"]["description"] = "自动化覆盖测试临时描述"
        response = self.client.put(
            "/api/platform/data",
            json={"data": modified},
            headers={"X-Platform-Role": "planner"},
        )
        self.assert_true(result, response.status_code == 200, "保存平台配置失败")
        audit_status, audit_payload = self.get_json("/api/platform/config-audit?limit=5")
        self.assert_true(result, audit_status == 200, "配置审计查询失败")
        self.assert_true(result, len(audit_payload.get("rows", [])) > 0, "配置审计没有记录")
        restore = self.client.put(
            "/api/platform/data",
            json={"data": original},
            headers={"X-Platform-Role": "planner"},
        )
        self.assert_true(result, restore.status_code == 200, "恢复平台配置失败")
        result.evidence = {"audit_rows": len(audit_payload.get("rows", [])), "data_source": audit_payload.get("data_source")}

    def tc14_history_report_approval_publish_export(self, result):
        run_response = self.client.post(
            "/api/platform/run",
            json={"playbook": "resilient", "overrides": {}, "save_history": True},
            headers={"X-Platform-Role": "planner"},
        )
        payload = run_response.get_json()
        run_id = payload.get("run_record", {}).get("run_id", "")
        self.assert_true(result, run_response.status_code == 200 and bool(run_id), "保存运行历史失败")

        history_status, history = self.get_json("/api/platform/run-history?limit=5")
        self.assert_true(result, history_status == 200 and any(row.get("run_id") == run_id for row in history.get("rows", [])), "运行历史未找到新批次")

        report_status, report = self.get_json(f"/api/platform/run-report/{run_id}")
        self.assert_true(result, report_status == 200 and report.get("report", {}).get("run_id") == run_id, "运行批次报告查询失败")

        submit = self.client.post(
            "/api/platform/approval",
            json={"run_id": run_id, "action": "submit", "actor": "auto.planner", "comment": "coverage submit"},
            headers={"X-Platform-Role": "planner"},
        )
        self.assert_true(result, submit.status_code == 200, "提交审批失败")
        approve = self.client.post(
            "/api/platform/approval",
            json={"run_id": run_id, "action": "approve", "actor": "auto.cio", "comment": "coverage approve"},
            headers={"X-Platform-Role": "approver"},
        )
        self.assert_true(result, approve.status_code == 200, "批准审批失败")
        approved_report_status, approved_report = self.get_json(f"/api/platform/run-report/{run_id}")
        approved_status = approved_report.get("report", {}).get("approval", {}).get("status") if approved_report else ""
        self.assert_true(result, approved_report_status == 200 and approved_status in {"approved", "auto_approved"}, "审批状态未进入可发布状态")

        publish = self.client.post(
            "/api/platform/publish-execution",
            json={"run_id": run_id, "actor": "auto.admin"},
            headers={"X-Platform-Role": "admin"},
        )
        publish_payload = publish.get_json() or {}
        self.assert_true(result, publish.status_code == 200, "发布执行包失败")
        self.assert_true(result, len(publish_payload.get("release", {}).get("targets", [])) == 4, "发布目标不是 4 个系统")

        export = self.client.post(
            "/api/platform/export-report",
            json={"playbook": "resilient", "overrides": {}},
            headers={"X-Platform-Role": "planner"},
        )
        export_payload = export.get_json()
        export_path = Path(export_payload.get("report", {}).get("path", ""))
        if not export_path.is_absolute():
            export_path = Path(__file__).resolve().parent.parent / export_path
        self.assert_true(result, export.status_code == 200, "导出演示报告失败")
        self.assert_true(result, export_path.exists(), "导出报告文件不存在")
        result.evidence = {
            "run_id": run_id,
            "approved_status": approved_status,
            "publish_status": publish.status_code,
            "publish_body": publish_payload if publish.status_code != 200 else {"status": publish_payload.get("status")},
            "publish_targets": len(publish_payload.get("release", {}).get("targets", [])),
            "export_path": str(export_path),
        }

    def tc15_validation_and_quarantine_edges(self, result):
        valid = platform_app.load_upstream_data()
        bad = deepcopy(valid)
        bad["orders"] = [
            {"order_id": "", "market": "UNKNOWN", "channel": "", "units": -1, "priority": "", "requested_delivery_days": 0, "demand_share_bp": -5}
        ]
        bad["weather"] = {
            "lane_impacts": [
                {"warehouse": "NO_WAREHOUSE", "market": "US West", "risk_level": "high", "delay_days": 1, "cost_multiplier": 1.2, "reason": "bad"}
            ]
        }
        validation = platform_app.validate_upstream_data(bad)
        quarantine = platform_app.build_data_quarantine(bad)
        self.assert_true(result, validation is not None, "异常上游数据未触发校验错误")
        self.assert_true(result, quarantine["summary"]["total_issues"] > 0, "异常隔离区没有识别问题")
        self.assert_true(result, platform_app.validate_number(float("nan"), "x") is not None, "NaN 未被拦截")
        self.assert_true(result, platform_app.validate_platform_data({"playbooks": {}, "assets": [], "capabilities": []}) is not None, "空 playbooks 未被拦截")
        result.evidence = {"validation_error": validation, "quarantine_summary": quarantine["summary"]}

    def tc16_json_mode_branches(self, result):
        original = platform_app.starrocks_upstream_enabled
        try:
            platform_app.starrocks_upstream_enabled = lambda: False
            data = platform_app.load_upstream_data()
            source = platform_app.upstream_data_source_label(data)
            platform_source = platform_app.platform_data_source_label()
            status = platform_app.build_upstream_source_status()
            scale = platform_app.build_platform_scale_snapshot()
            capacity = platform_app.build_capacity_assessment()
            self.assert_true(result, source.endswith("python/data/platform_upstream_data.json"), "JSON 上游来源标签错误")
            self.assert_true(result, platform_source.endswith("python/data/platform_poc_data.json"), "JSON 平台来源标签错误")
            self.assert_true(result, status["mode"] == "JSON", "JSON 模式源状态错误")
            self.assert_true(result, scale["status"] == "ok", "JSON 模式规模快照失败")
            self.assert_true(result, capacity["status"] == "ok", "JSON 模式容量评估失败")
        finally:
            platform_app.starrocks_upstream_enabled = original
        result.evidence = {"source": source, "status_mode": status["mode"], "scale_status": scale["status"], "capacity_status": capacity["status"]}

    def tc17_weather_loader_pure_functions(self, result):
        import load_starrocks_weather

        low = {"max_precipitation": 0, "max_snowfall": 0, "max_wind": 10, "max_temperature": 20}
        medium = {"max_precipitation": 12, "max_snowfall": 0, "max_wind": 10, "max_temperature": 20}
        high = {"max_precipitation": 30, "max_snowfall": 0, "max_wind": 60, "max_temperature": 39}
        self.assert_true(result, load_starrocks_weather.classify_weather_risk(low)[:3] == ("low", 0, 1.02), "低风险天气分级错误")
        self.assert_true(result, load_starrocks_weather.classify_weather_risk(medium)[:3] == ("medium", 1, 1.08), "中风险天气分级错误")
        self.assert_true(result, load_starrocks_weather.classify_weather_risk(high)[:3] == ("high", 2, 1.18), "高风险天气分级错误")
        result.evidence = {"markets": sorted(load_starrocks_weather.MARKET_COORDINATES)}

    def run(self):
        self.run_case("TC01", "数据源健康检查", self.tc01_source_health)
        self.run_case("TC02", "天气数据接入准确性", self.tc02_weather_upstream)
        self.run_case("TC03", "天气因子进入模型入参", self.tc03_weather_in_model_inputs)
        self.run_case("TC04", "天气成本转换准确性", self.tc04_weather_cost_transform)
        self.run_case("TC05", "天气时效与 SLA 判断准确性", self.tc05_weather_sla_transform)
        self.run_case("TC06", "禁用线路不被求解结果使用", self.tc06_blocked_lanes_not_used)
        self.run_case("TC07", "仓库容量约束准确性", self.tc07_capacity_constraints)
        self.run_case("TC08", "服务水平模型需求平衡", self.tc08_service_demand_balance)
        self.run_case("TC09", "天气 A/B 价值验证", self.tc09_weather_ab_value)
        self.run_case("TC10", "极端天气手动注入验证", self.tc10_extreme_weather_injection)
        self.run_case("TC11", "页面与只读 API 路由覆盖", self.tc11_page_and_readonly_api_routes)
        self.run_case("TC12", "权限与输入校验错误覆盖", self.tc12_permissions_and_validation_errors)
        self.run_case("TC13", "场景配置保存审计与恢复", self.tc13_config_save_audit_and_restore)
        self.run_case("TC14", "运行历史审批发布报告闭环", self.tc14_history_report_approval_publish_export)
        self.run_case("TC15", "校验与异常隔离边界覆盖", self.tc15_validation_and_quarantine_edges)
        self.run_case("TC16", "JSON 模式分支覆盖", self.tc16_json_mode_branches)
        self.run_case("TC17", "天气装载脚本纯函数覆盖", self.tc17_weather_loader_pure_functions)
        return self.results


def write_reports(results):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    total = len(results)
    passed = len([result for result in results if result.status == "PASS"])
    failed = len([result for result in results if result.status == "FAIL"])
    errors = len([result for result in results if result.status == "ERROR"])
    assertions = sum(result.assertions for result in results)
    covered_case_ids = [result.case_id for result in results]
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_document": str(TEST_DOC),
        "environment": {
            "platform_source": os.environ.get("PLATFORM_UPSTREAM_SOURCE"),
            "starrocks_database": platform_app.starrocks_config()["database"],
            "platform_url": "http://127.0.0.1:5053",
        },
        "summary": {
            "total_cases": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "assertions": assertions,
            "test_case_coverage": f"{passed + failed + errors}/{total}",
            "test_case_coverage_percent": round((passed + failed + errors) / total * 100, 2) if total else 0,
            "pass_rate_percent": round(passed / total * 100, 2) if total else 0,
        },
        "covered_case_ids": covered_case_ids,
        "results": [
            {
                "case_id": result.case_id,
                "name": result.name,
                "status": result.status,
                "assertions": result.assertions,
                "elapsed_ms": result.elapsed_ms,
                "failures": result.failures,
                "evidence": result.evidence,
            }
            for result in results
        ],
    }
    json_path = REPORTS_DIR / f"platform_accuracy_test_report_{timestamp}.json"
    md_path = REPORTS_DIR / f"platform_accuracy_test_report_{timestamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown_report(payload), encoding="utf-8")
    return json_path, md_path, payload


def render_markdown_report(payload):
    lines = [
        "# CPLEX 优化平台准确性自动化测试报告",
        "",
        f"- 生成时间：`{payload['generated_at']}`",
        f"- 测试依据：`{payload['source_document']}`",
        f"- 平台地址：`{payload['environment']['platform_url']}`",
        f"- 上游模式：`{payload['environment']['platform_source']}`",
        f"- StarRocks 数据库：`{payload['environment']['starrocks_database']}`",
        "",
        "## 总览",
        "",
        f"- 测试用例覆盖率：`{payload['summary']['test_case_coverage_percent']}%`（{payload['summary']['test_case_coverage']}）",
        f"- 通过率：`{payload['summary']['pass_rate_percent']}%`",
        f"- 通过：`{payload['summary']['passed']}`",
        f"- 失败：`{payload['summary']['failed']}`",
        f"- 错误：`{payload['summary']['errors']}`",
        f"- 断言总数：`{payload['summary']['assertions']}`",
        "",
        "## 明细",
        "",
        "| 用例 | 名称 | 状态 | 断言 | 耗时 ms | 关键证据 |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for result in payload["results"]:
        evidence = compact_evidence(result["evidence"])
        lines.append(
            f"| {result['case_id']} | {result['name']} | {result['status']} | {result['assertions']} | {result['elapsed_ms']} | {evidence} |"
        )
        if result["failures"]:
            lines.append(f"| {result['case_id']} | 失败原因 |  |  |  | {'; '.join(result['failures'])} |")
    lines.extend(
        [
            "",
            "## 覆盖说明",
            "",
            "- TC01-TC17 全部自动化执行，测试用例覆盖率为 100%。",
            "- 本报告统计业务测试用例覆盖率和断言结果；代码行覆盖率由 `coverage.py` 单独生成。",
        ]
    )
    return "\n".join(lines) + "\n"


def compact_evidence(evidence):
    interesting_keys = [
        "http_status",
        "mode",
        "summary",
        "weather_source",
        "api_weather_rows",
        "table_weather_rows",
        "weather_inputs",
        "weather_results",
        "checked_lanes",
        "weather_blocked_lanes",
        "checked_playbooks",
        "checked_markets",
        "cost_delta",
        "with_weather_lanes",
        "without_weather_lanes",
        "used_orders",
    ]
    compact = {key: evidence[key] for key in interesting_keys if key in evidence}
    if "weather_table" in evidence:
        compact["weather_table"] = evidence["weather_table"]
    if "target_lane" in evidence:
        lane = evidence["target_lane"]
        compact["target_lane"] = {
            "lane": f"{lane['warehouse']}->{lane['market']}",
            "delay": lane["weather_delay_days"],
            "cost_multiplier": lane["weather_cost_multiplier"],
            "allowed_by_sla": lane["allowed_by_sla"],
        }
    return json.dumps(compact, ensure_ascii=False, default=str)


def main():
    runner = PlatformAccuracyRunner()
    results = runner.run()
    json_path, md_path, payload = write_reports(results)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"json_report={json_path}")
    print(f"markdown_report={md_path}")
    return 0 if all(result.status == "PASS" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
