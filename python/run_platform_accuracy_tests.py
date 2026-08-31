import json
import os
import sys
import time
import traceback
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch


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

    def tc18_weather_loader_with_mocks(self, result):
        import load_starrocks_weather

        class FakeCursor:
            def __init__(self):
                self.executed = []
                self.inserted = []

            def execute(self, sql, params=None):
                self.executed.append(sql)

            def fetchall(self):
                return [
                    {"warehouse": "Los Angeles 3PL", "market": "US West"},
                    {"warehouse": "Rotterdam EU Hub", "market": "EU"},
                    {"warehouse": "Ghost Warehouse", "market": "Unknown"},
                ]

            def executemany(self, sql, rows):
                self.executed.append(sql)
                self.inserted.extend(rows)

        cursor = FakeCursor()
        args = type("Args", (), {"forecast_days": 3, "timeout": 5})()
        original_coordinates = load_starrocks_weather.MARKET_COORDINATES
        original_fetch = load_starrocks_weather.fetch_market_weather
        try:
            load_starrocks_weather.MARKET_COORDINATES = {
                "US West": {"latitude": 1, "longitude": 2, "label": "Los Angeles"},
                "EU": {"latitude": 3, "longitude": 4, "label": "Amsterdam"},
            }
            load_starrocks_weather.fetch_market_weather = lambda market, coordinates, forecast_days, timeout: {
                "market": market,
                "location": coordinates["label"],
                "max_precipitation": 30 if market == "EU" else 0,
                "max_rain": 30 if market == "EU" else 0,
                "max_snowfall": 0,
                "max_wind": 10,
                "max_temperature": 20,
            }
            rows, forecasts, snapshot = load_starrocks_weather.build_weather_rows(args, cursor)
        finally:
            load_starrocks_weather.MARKET_COORDINATES = original_coordinates
            load_starrocks_weather.fetch_market_weather = original_fetch
        self.assert_true(result, len(rows) == 2, "天气脚本没有按有效市场生成线路行")
        self.assert_true(result, any(row[1] == "EU" and row[2] == "medium" for row in rows), "EU 天气风险没有按 mock 降水转换")
        self.assert_true(result, "US West" in forecasts and "EU" in forecasts, "天气 forecast 缓存缺少市场")
        self.assert_true(result, bool(snapshot), "天气快照时间为空")
        result.evidence = {"generated_rows": len(rows), "forecast_markets": sorted(forecasts)}

    def tc19_upstream_loader_with_mocks(self, result):
        import load_starrocks_upstream

        class FakeCursor:
            def __init__(self):
                self.commands = []
                self.inserted = {}

            def execute(self, sql, params=None):
                self.commands.append(sql)

            def executemany(self, sql, rows):
                table = sql.split("INSERT INTO ", 1)[1].split()[0]
                self.inserted.setdefault(table, 0)
                self.inserted[table] += len(list(rows))

        cursor = FakeCursor()
        source_data = {
            "network": {
                "warehouses": {"W1": {"capacity": 10, "fixed_cost": 1, "handling_cost": 0.5}},
                "markets": {"M1": {"demand": 5, "max_delivery_days": 3}},
                "lanes": [{"warehouse": "W1", "market": "M1", "last_mile_cost": 2, "delivery_days": 2}],
                "expansion_options": {"W1": {"max_extra_capacity": 3, "unit_cost": 4}},
            },
            "weather": {
                "snapshot_time": "2026-08-31T00:00:00+00:00",
                "lane_impacts": [{"warehouse": "W1", "market": "M1", "risk_level": "low", "delay_days": 0, "cost_multiplier": 1.02, "reason": "test"}],
            },
            "replenishment": {
                "weeks": ["W1"],
                "demand": {"W1": 8},
                "lanes": {"air": {"lead_time_weeks": 1, "unit_cost": 3, "weekly_capacity": 9}},
                "initial_inventory": 1,
                "target_ending_inventory": 1,
                "holding_cost": 0.1,
                "stockout_penalty": 10,
            },
            "service_level": {
                "markets": {"M1": {"demand": 5, "max_avg_delivery_days": 3}},
                "services": {"S1": {"capacity": 10, "fixed_cost": 1, "unit_cost_by_market": {"M1": 2}, "delivery_days_by_market": {"M1": 2}}},
            },
        }
        platform_data = {
            "playbooks": {
                "baseline": {
                    "name": "基准",
                    "description": "test",
                    "demand_multiplier": 1,
                    "sla_extra_days": 0,
                    "air_capacity": 1,
                    "ocean_lead_time": 2,
                    "unfulfilled_penalty": 10,
                    "network_mode": "strict",
                    "staff_peak": False,
                    "soft_staffing": False,
                }
            },
            "assets": [{"name": "A", "area": "B"}],
            "capabilities": ["C"],
        }
        dimension_counts = load_starrocks_upstream.load_dimension_tables(cursor, source_data)
        platform_counts = load_starrocks_upstream.load_platform_tables(cursor, platform_data)
        batches = list(load_starrocks_upstream.batched([1, 2, 3, 4, 5], 2))
        self.assert_true(result, dimension_counts["weather_lane_impacts"] == 1, "维表装载未统计天气行")
        self.assert_true(result, dimension_counts["network_lanes"] == 1, "维表装载未统计线路")
        self.assert_true(result, platform_counts["playbooks"] == 1, "平台配置装载未统计 playbook")
        self.assert_true(result, batches == [[1, 2], [3, 4], [5]], "批处理切片错误")
        self.assert_true(result, cursor.inserted.get("upstream_weather_lane_impacts", 0) == 1, "天气行没有写入 fake cursor")
        result.evidence = {"dimension_counts": dimension_counts, "platform_counts": platform_counts, "inserted": cursor.inserted}

    def tc20_starrocks_upstream_save_roundtrip(self, result):
        data = platform_app.load_upstream_data()
        before_weather = self.starrocks_count("upstream_weather_lane_impacts")
        platform_app.save_starrocks_upstream_data(data)
        after_weather = self.starrocks_count("upstream_weather_lane_impacts")
        reloaded = platform_app.load_upstream_data()
        self.assert_true(result, after_weather == len(data.get("weather", {}).get("lane_impacts", [])), "保存后天气表行数不一致")
        self.assert_true(result, reloaded.get("weather", {}).get("source") == "StarRocks.upstream_weather_lane_impacts", "保存后天气来源错误")
        self.assert_true(result, len(reloaded.get("network", {}).get("lanes", [])) == len(data["network"]["lanes"]), "保存后网络线路数量变化")
        result.evidence = {"before_weather": before_weather, "after_weather": after_weather, "network_lanes": len(reloaded["network"]["lanes"])}

    def tc21_loader_schema_and_weather_load_mocks(self, result):
        import load_starrocks_upstream
        import load_starrocks_weather

        class FakeCursor:
            def __init__(self):
                self.commands = []
                self.inserted = []
                self.rows = [
                    {"warehouse": "W1", "market": "US West"},
                    {"warehouse": "W1", "market": "EU"},
                ]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                self.commands.append(sql)

            def executemany(self, sql, rows):
                self.commands.append(sql)
                self.inserted.extend(list(rows))

            def fetchall(self):
                return self.rows

        class FakeConnection:
            def __init__(self, cursor):
                self.cursor_obj = cursor
                self.committed = False

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def cursor(self):
                return self.cursor_obj

            def commit(self):
                self.committed = True

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "daily": {
                            "precipitation_sum": [0, 12],
                            "rain_sum": [0, 12],
                            "snowfall_sum": [0, 0],
                            "wind_speed_10m_max": [10, 20],
                            "temperature_2m_max": [21, 23],
                        }
                    }
                ).encode("utf-8")

        schema_cursor = FakeCursor()
        schema_args = type("Args", (), {"database": "db", "table": "orders", "buckets": 2, "replication_num": "1"})()
        original_upstream_connect = load_starrocks_upstream.connect
        original_weather_connect = load_starrocks_weather.connect
        original_urlopen = load_starrocks_weather.urlopen
        try:
            load_starrocks_upstream.connect = lambda args, database=None: FakeConnection(schema_cursor)
            load_starrocks_upstream.create_schema(schema_args)

            weather_cursor = FakeCursor()
            load_starrocks_weather.connect = lambda args: FakeConnection(weather_cursor)
            load_starrocks_weather.urlopen = lambda url, timeout: FakeResponse()
            weather_args = type(
                "Args",
                (),
                {
                    "host": "x",
                    "port": 1,
                    "user": "u",
                    "password": "",
                    "database": "db",
                    "forecast_days": 2,
                    "timeout": 1,
                    "replication_num": "1",
                    "truncate": True,
                },
            )()
            loaded = load_starrocks_weather.load_weather(weather_args)
            fetched = load_starrocks_weather.fetch_market_weather("US West", {"latitude": 1, "longitude": 2, "label": "X"}, 2, 1)
        finally:
            load_starrocks_upstream.connect = original_upstream_connect
            load_starrocks_weather.connect = original_weather_connect
            load_starrocks_weather.urlopen = original_urlopen
        self.assert_true(result, len(schema_cursor.commands) >= 10, "上游装载建表 SQL 覆盖不足")
        self.assert_true(result, loaded["inserted_rows"] == 2, "mock 天气装载行数错误")
        self.assert_true(result, len(weather_cursor.inserted) == 2, "mock 天气写库没有执行")
        self.assert_true(result, fetched["max_precipitation"] == 12, "mock Open-Meteo 解析错误")
        result.evidence = {"schema_commands": len(schema_cursor.commands), "weather_loaded": loaded["inserted_rows"]}

    def tc22_validation_error_matrix(self, result):
        data = platform_app.load_upstream_data()
        mutations = []

        bad = deepcopy(data)
        bad.pop("network")
        mutations.append(("missing_network", bad))

        bad = deepcopy(data)
        bad["network"]["warehouses"]["Los Angeles 3PL"].pop("capacity")
        mutations.append(("missing_warehouse_capacity", bad))

        bad = deepcopy(data)
        bad["network"]["markets"]["US West"]["max_delivery_days"] = 0
        mutations.append(("bad_market_sla", bad))

        bad = deepcopy(data)
        bad["network"]["expansion_options"]["NO_WAREHOUSE"] = {"max_extra_capacity": 1, "unit_cost": 1}
        mutations.append(("bad_expansion_ref", bad))

        bad = deepcopy(data)
        bad["network"]["lanes"] = bad["network"]["lanes"][:-1]
        mutations.append(("missing_lane_pair", bad))

        bad = deepcopy(data)
        bad["replenishment"]["weeks"].append("W999")
        mutations.append(("missing_replenishment_week", bad))

        bad = deepcopy(data)
        bad["service_level"]["services"]["local_standard"]["unit_cost_by_market"].pop("US West", None)
        mutations.append(("missing_service_market_cost", bad))

        bad = deepcopy(data)
        bad["weather"]["lane_impacts"][0]["cost_multiplier"] = 0
        mutations.append(("bad_weather_multiplier", bad))

        errors = {name: platform_app.validate_upstream_data(payload) for name, payload in mutations}
        for name, error in errors.items():
            self.assert_true(result, bool(error), f"{name} 未触发校验错误")
        self.assert_true(result, platform_app.validate_platform_data(None) is not None, "非对象平台配置未报错")
        self.assert_true(result, platform_app.validate_platform_data({"playbooks": {"": {}}, "assets": [], "capabilities": []}) is not None, "空 playbook id 未报错")
        self.assert_true(result, platform_app.weather_risk_score("high") == 3 and platform_app.weather_risk_score("x") == 0, "天气风险分值错误")
        self.assert_true(result, platform_app.markdown_cell("a|b") == "a\\|b", "Markdown 单元格转义错误")
        result.evidence = {"validated_errors": errors}

    def tc23_upstream_load_orders_mock_flow(self, result):
        import load_starrocks_upstream

        class FakePath:
            def __init__(self, payload):
                self.payload = payload

            def read_text(self, encoding="utf-8"):
                return json.dumps(self.payload, ensure_ascii=False)

        class FakeCursor:
            def __init__(self):
                self.commands = []
                self.inserts = []
                self.last_select = ""

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                self.commands.append(sql)
                self.last_select = sql

            def executemany(self, sql, rows):
                self.commands.append(sql)
                self.inserts.extend(list(rows))

            def fetchone(self):
                return {"order_line_count": 3}

            def fetchall(self):
                if "GROUP BY market" in self.last_select:
                    return [{"market": "M1", "order_lines": 3, "units": 6}]
                return []

        class FakeConnection:
            def __init__(self, cursor):
                self.cursor_obj = cursor

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def cursor(self):
                return self.cursor_obj

        source_data = {
            "orders": [{"order_id": "seed"}],
            "network": {
                "warehouses": {"W1": {"capacity": 10, "fixed_cost": 1, "handling_cost": 0.5}},
                "markets": {"M1": {"demand": 5, "max_delivery_days": 3}},
                "lanes": [{"warehouse": "W1", "market": "M1", "last_mile_cost": 2, "delivery_days": 2}],
                "expansion_options": {"W1": {"max_extra_capacity": 3, "unit_cost": 4}},
            },
            "weather": {"snapshot_time": "t", "lane_impacts": []},
            "replenishment": {
                "weeks": ["W1"],
                "demand": {"W1": 8},
                "lanes": {"air": {"lead_time_weeks": 1, "unit_cost": 3, "weekly_capacity": 9}},
                "initial_inventory": 1,
                "target_ending_inventory": 1,
                "holding_cost": 0.1,
                "stockout_penalty": 10,
            },
            "service_level": {
                "markets": {"M1": {"demand": 5, "max_avg_delivery_days": 3}},
                "services": {"S1": {"capacity": 10, "fixed_cost": 1, "unit_cost_by_market": {"M1": 2}, "delivery_days_by_market": {"M1": 2}}},
            },
        }
        platform_data = {
            "playbooks": {
                "baseline": {
                    "name": "基准",
                    "description": "test",
                    "demand_multiplier": 1,
                    "sla_extra_days": 0,
                    "air_capacity": 1,
                    "ocean_lead_time": 2,
                    "unfulfilled_penalty": 10,
                    "network_mode": "strict",
                    "staff_peak": False,
                    "soft_staffing": False,
                }
            },
            "assets": [],
            "capabilities": [],
        }
        cursor = FakeCursor()
        args = type(
            "Args",
            (),
            {
                "database": "db",
                "table": "orders",
                "orders": 3,
                "batch_size": 2,
                "buckets": 2,
                "replication_num": "1",
                "truncate": True,
                "skip_orders": False,
                "progress": 2,
            },
        )()
        original_data_path = load_starrocks_upstream.DATA_PATH
        original_platform_path = load_starrocks_upstream.PLATFORM_DATA_PATH
        original_connect = load_starrocks_upstream.connect
        original_create_schema = load_starrocks_upstream.create_schema
        original_build_orders = load_starrocks_upstream.build_orders
        try:
            load_starrocks_upstream.DATA_PATH = FakePath(source_data)
            load_starrocks_upstream.PLATFORM_DATA_PATH = FakePath(platform_data)
            load_starrocks_upstream.connect = lambda args, database=None: FakeConnection(cursor)
            load_starrocks_upstream.create_schema = lambda args: cursor.execute("CREATE_SCHEMA")
            load_starrocks_upstream.build_orders = lambda seeds, total: [
                {"order_id": f"O{i}", "market": "M1", "channel": "web", "units": i, "priority": "normal", "requested_delivery_days": 3, "demand_share_bp": 100}
                for i in range(1, total + 1)
            ]
            with redirect_stdout(StringIO()):
                loaded = load_starrocks_upstream.load_orders(args)
        finally:
            load_starrocks_upstream.DATA_PATH = original_data_path
            load_starrocks_upstream.PLATFORM_DATA_PATH = original_platform_path
            load_starrocks_upstream.connect = original_connect
            load_starrocks_upstream.create_schema = original_create_schema
            load_starrocks_upstream.build_orders = original_build_orders
        self.assert_true(result, loaded["loaded_order_lines"] == 3, "mock 订单装载计数错误")
        self.assert_true(result, loaded["target_order_lines"] == 3, "目标订单量错误")
        self.assert_true(result, loaded["market_rows"][0]["units"] == 6, "市场聚合结果错误")
        self.assert_true(result, any("TRUNCATE TABLE `orders`" in sql for sql in cursor.commands), "订单表 truncate 未执行")
        result.evidence = {"loaded_order_lines": loaded["loaded_order_lines"], "commands": len(cursor.commands), "insert_batches": len(cursor.inserts)}

    def tc24_cli_main_and_connect_mocks(self, result):
        import load_starrocks_upstream
        import load_starrocks_weather

        calls = {}
        with redirect_stdout(StringIO()):
            with patch.object(sys, "argv", ["load_starrocks_weather.py", "--forecast-days", "2", "--no-truncate"]):
                with patch.object(load_starrocks_weather, "load_weather", lambda args: calls.setdefault("weather", {"forecast_days": args.forecast_days, "truncate": args.truncate})):
                    load_starrocks_weather.main()
            with patch.object(sys, "argv", ["load_starrocks_upstream.py", "--orders", "7", "--skip-orders"]):
                with patch.object(load_starrocks_upstream, "load_orders", lambda args: calls.setdefault("upstream", {"orders": args.orders, "skip_orders": args.skip_orders})):
                    load_starrocks_upstream.main()
        with patch.object(load_starrocks_weather.pymysql, "connect", lambda **kwargs: kwargs):
            weather_conn = load_starrocks_weather.connect(type("Args", (), {"host": "h", "port": 1, "user": "u", "password": "p", "database": "d"})())
        with patch.object(load_starrocks_upstream.pymysql, "connect", lambda **kwargs: kwargs):
            upstream_conn = load_starrocks_upstream.connect(type("Args", (), {"host": "h", "port": 2, "user": "u", "password": "p"})(), "d2")
        self.assert_true(result, calls["weather"] == {"forecast_days": 2, "truncate": False}, "天气 CLI 参数解析错误")
        self.assert_true(result, calls["upstream"] == {"orders": 7, "skip_orders": True}, "上游 CLI 参数解析错误")
        self.assert_true(result, weather_conn["database"] == "d" and upstream_conn["database"] == "d2", "connect 参数传递错误")
        result.evidence = calls

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
        self.run_case("TC18", "天气装载脚本 mock 覆盖", self.tc18_weather_loader_with_mocks)
        self.run_case("TC19", "StarRocks 上游装载脚本 mock 覆盖", self.tc19_upstream_loader_with_mocks)
        self.run_case("TC20", "StarRocks 上游基础表保存回读", self.tc20_starrocks_upstream_save_roundtrip)
        self.run_case("TC21", "装载脚本建表与天气写库 mock 覆盖", self.tc21_loader_schema_and_weather_load_mocks)
        self.run_case("TC22", "数据校验错误矩阵覆盖", self.tc22_validation_error_matrix)
        self.run_case("TC23", "上游订单装载流程 mock 覆盖", self.tc23_upstream_load_orders_mock_flow)
        self.run_case("TC24", "CLI main 与连接参数 mock 覆盖", self.tc24_cli_main_and_connect_mocks)
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
            f"- {payload['summary']['test_case_coverage']} 个测试用例全部自动化执行，测试用例覆盖率为 {payload['summary']['test_case_coverage_percent']}%。",
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
