import json
import os
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from socket import socket

from playwright.sync_api import expect, sync_playwright


DEFAULT_BASE_URL = os.environ.get("PLATFORM_E2E_BASE_URL", "http://127.0.0.1:5053")
BASE_URL = DEFAULT_BASE_URL
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
SCREENSHOT_DIR = REPORTS_DIR / "platform_e2e_screenshots"
SERVER_ENV = {
    "PLATFORM_UPSTREAM_SOURCE": os.environ.get("PLATFORM_UPSTREAM_SOURCE", "starrocks"),
    "STARROCKS_HOST": os.environ.get("STARROCKS_HOST", "127.0.0.1"),
    "STARROCKS_PORT": os.environ.get("STARROCKS_PORT", "9030"),
    "STARROCKS_USER": os.environ.get("STARROCKS_USER", "root"),
    "STARROCKS_DATABASE": os.environ.get("STARROCKS_DATABASE", "cplex_poc"),
}
FEATURE_REGISTRY = {
    "FLOW_NAV": "顶部流程导航与页面装载",
    "UPSTREAM_SOURCE": "上游数据源状态",
    "UPSTREAM_QUALITY": "数据质量校验",
    "UPSTREAM_QUARANTINE": "异常数据隔离区",
    "UPSTREAM_WEATHER": "天气风险因子",
    "UPSTREAM_SCALE": "规模吞吐概览",
    "UPSTREAM_ORDERS": "订单明细抽样",
    "UPSTREAM_EDIT": "上游业务表编辑保存",
    "CONFIG_PLAYBOOK": "三场景配置导航",
    "CONFIG_SAVE_AUDIT": "场景配置保存与审计",
    "INPUT_NAV": "四模型入参导航",
    "INPUT_HIGHLIGHT": "模型入参变化高亮",
    "RESULT_RUN_PIPELINE": "求解流水线",
    "RESULT_COST_VISUAL": "成本结构可视化",
    "RESULT_EXPLAIN": "经营价值与差异解释",
    "RESULT_ENTERPRISE": "企业就绪面板",
    "RESULT_GOVERNANCE": "治理审批",
    "RESULT_EXECUTION": "执行发布闭环",
    "RESULT_HISTORY": "运行历史回放与报告",
    "LINEAGE": "数据血缘可视化与字段映射",
    "CONSTRAINTS": "约束解释与代码实现",
    "PERFORMANCE": "压力测试与容量评估",
    "ROLE_PERMISSIONS": "角色权限隔离",
    "REPORT_EXPORT": "演示报告导出",
}


@dataclass
class E2EResult:
    case_id: str
    name: str
    status: str = "PASS"
    assertions: int = 0
    failures: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    features: list = field(default_factory=list)
    elapsed_ms: float = 0


class PlatformE2ERunner:
    def __init__(self, headed=False):
        self.headed = headed
        self.results = []
        self.browser = None
        self.context = None
        self.page = None
        self.console_errors = []
        self.failed_responses = []

    def assert_true(self, result, condition, message):
        result.assertions += 1
        if not condition:
            result.status = "FAIL"
            result.failures.append(message)

    def run_case(self, case_id, name, func, features=None):
        result = E2EResult(case_id=case_id, name=name, features=features or [])
        started = time.perf_counter()
        try:
            self.console_errors.clear()
            self.failed_responses.clear()
            func(result)
            if self.console_errors:
                result.evidence["console_errors"] = list(self.console_errors)
            if self.failed_responses:
                result.evidence["failed_responses"] = list(self.failed_responses)
                result.status = "FAIL"
                result.failures.append("页面运行过程中出现 4xx/5xx API 响应")
        except Exception as error:
            result.status = "ERROR"
            result.failures.append(f"{type(error).__name__}: {error}")
            result.evidence["traceback"] = traceback.format_exc(limit=8)
            result.evidence["screenshot"] = self.capture_failure(case_id)
        result.elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self.results.append(result)

    def capture_failure(self, case_id):
        if not self.page:
            return ""
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOT_DIR / f"{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        try:
            self.page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return ""

    def start_browser(self, playwright):
        self.browser = playwright.chromium.launch(headless=not self.headed, args=["--no-proxy-server"])
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 1100},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        self.context.set_default_timeout(20_000)
        self.page = self.context.new_page()
        self.page.on("console", self.on_console)
        self.page.on("response", self.on_response)

    def close_browser(self):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()

    def on_console(self, message):
        if message.type == "error":
            text = message.text
            allowed = ["favicon.ico"]
            if not any(item in text for item in allowed):
                self.console_errors.append(text[:500])

    def on_response(self, response):
        if response.status >= 400 and "/api/platform/" in response.url:
            self.failed_responses.append({"status": response.status, "url": response.url})

    def goto(self, path):
        self.page.goto(f"{BASE_URL}{path}", wait_until="networkidle")

    def set_role(self, role):
        self.page.locator("#roleSelect").select_option(role)
        expect(self.page.locator("#roleSelect")).to_have_value(role)

    def wait_loaded(self):
        expect(self.page.locator("body")).to_be_visible()
        self.page.wait_for_load_state("networkidle")

    def e2e01_navigation_and_order_sample(self, result):
        self.goto("/upstream")
        self.wait_loaded()
        self.page.get_by_role("button", name="订单明细").click()
        expect(self.page.locator("#orderSampleRows tr").first).to_be_visible()
        status = self.page.locator("#orderSampleStatus").inner_text()
        first_order = self.page.locator("#orderSampleRows tr").first.inner_text()
        self.assert_true(result, "抽样" in status, "订单抽样状态没有显示")
        self.assert_true(result, len(first_order.strip()) > 0, "订单明细表没有渲染首行")
        self.page.get_by_role("button", name="显示全部抽样").click()
        row_count = self.page.locator("#orderSampleRows tr").count()
        result.evidence = {"order_status": status, "rendered_rows": row_count, "first_order": first_order}
        self.assert_true(result, row_count > 0, "点击显示全部抽样后仍没有订单行")

    def e2e09_upstream_source_quality_quarantine_weather_scale(self, result):
        self.goto("/upstream")
        checks = [
            ("数据源", "#sourceStatus", "#sourceTableRows tr"),
            ("质量校验", "#qualityStatus", "#qualityChecks .row"),
            ("异常隔离", "#quarantineStatus", "#quarantineMetrics .metric"),
            ("天气风险", "#weatherStatus", "#weatherRows tr"),
            ("规模吞吐", "#scaleStatus", "#scaleModelRows tr"),
        ]
        evidence = {}
        for button_name, status_selector, content_selector in checks:
            self.page.get_by_role("button", name=button_name).click()
            expect(self.page.locator(status_selector)).not_to_contain_text("加载中", timeout=20_000)
            expect(self.page.locator(content_selector).first).to_be_visible(timeout=20_000)
            evidence[button_name] = {
                "status": self.page.locator(status_selector).inner_text(),
                "rows": self.page.locator(content_selector).count(),
            }
        result.evidence = evidence
        self.assert_true(result, all(item["rows"] > 0 for item in evidence.values()), "上游二级页面存在空内容")

    def e2e02_upstream_edit_save_roundtrip(self, result):
        self.goto("/upstream")
        self.set_role("data_admin")
        self.page.get_by_role("button", name="业务表编辑").click()
        market_input = self.page.locator('[data-upstream="market"][data-field="demand"]').first
        expect(market_input).to_be_visible()
        original = float(market_input.input_value())
        changed = original + 1
        market_input.fill(str(changed))
        self.page.locator("#saveUpstream").click()
        expect(self.page.locator("#upstreamStatus")).not_to_contain_text("保存中", timeout=30_000)
        self.page.reload(wait_until="networkidle")
        self.page.get_by_role("button", name="业务表编辑").click()
        reloaded = float(self.page.locator('[data-upstream="market"][data-field="demand"]').first.input_value())
        self.assert_true(result, reloaded == changed, "保存后刷新页面没有读到修改后的上游需求")
        self.page.locator('[data-upstream="market"][data-field="demand"]').first.fill(str(original))
        self.page.locator("#saveUpstream").click()
        expect(self.page.locator("#upstreamStatus")).not_to_contain_text("保存中", timeout=30_000)
        result.evidence = {"original_demand": original, "changed_demand": changed, "reloaded_demand": reloaded}

    def e2e03_config_to_model_inputs_highlight(self, result):
        self.goto("/config")
        self.set_role("planner")
        self.page.locator("#demand").fill("1.15")
        self.page.locator("#air").fill("980")
        self.page.locator("#runFromConfig").click()
        expect(self.page.locator("#current")).not_to_have_text("求解中", timeout=45_000)
        self.goto("/inputs")
        expect(self.page.locator("#inputRows tr").first).to_be_visible()
        changed_rows = self.page.locator("#inputRows tr.changed-input").count()
        body_text = self.page.locator("#inputRows").inner_text()
        result.evidence = {"changed_rows": changed_rows, "input_excerpt": body_text[:500]}
        self.assert_true(result, changed_rows > 0, "模型入参页没有显示变化高亮")
        self.assert_true(result, "需求倍率" in body_text or "空运容量" in body_text, "模型入参没有显示场景参数变化来源")

    def e2e10_config_playbooks_save_audit_and_permissions(self, result):
        self.goto("/config")
        self.set_role("viewer")
        expect(self.page.locator("#saveConfig")).to_be_disabled()
        self.set_role("planner")
        playbook_buttons = self.page.locator("#playbooks button")
        expect(playbook_buttons.first).to_be_visible(timeout=20_000)
        playbook_count = playbook_buttons.count()
        playbook_buttons.nth(1).click()
        self.page.locator("#penalty").fill("75")
        self.page.locator("#saveConfig").click()
        expect(self.page.locator("#configStatus")).not_to_contain_text("保存中", timeout=30_000)
        expect(self.page.locator("#configAuditRows tr").first).to_be_visible(timeout=20_000)
        result.evidence = {
            "playbook_count": playbook_count,
            "config_status": self.page.locator("#configStatus").inner_text(),
            "audit_first_row": self.page.locator("#configAuditRows tr").first.inner_text(),
            "viewer_save_disabled": True,
        }
        self.assert_true(result, playbook_count >= 3, "场景配置少于三种方案")

    def e2e11_model_input_tabs_and_regeneration(self, result):
        self.goto("/inputs")
        self.set_role("planner")
        self.page.locator("#runFromInputs").click()
        expect(self.page.locator("#inputPlaybook")).not_to_have_text("生成中", timeout=60_000)
        evidence = {}
        for key, name in [
            ("network", "仓网选址与履约"),
            ("replenishment", "补货计划"),
            ("service_level", "服务水平组合"),
            ("staffing", "人员排班"),
        ]:
            self.page.locator(f'[data-model-input="{key}"]').click()
            expect(self.page.locator("#inputRows tr").first).to_be_visible(timeout=20_000)
            evidence[name] = self.page.locator("#inputRows").inner_text()[:300]
        result.evidence = evidence
        self.assert_true(result, len(evidence) == 4, "四个模型入参导航没有全部覆盖")

    def e2e04_results_pipeline_and_visuals(self, result):
        self.goto("/results")
        self.set_role("planner")
        self.page.get_by_role("button", name="运行概览").click()
        self.page.locator("#run").click()
        expect(self.page.locator('[data-run-step="solve"]')).to_contain_text("进行中", timeout=20_000)
        expect(self.page.locator("#runSteps")).to_contain_text("完成", timeout=60_000)
        expect(self.page.locator("#totalCost")).not_to_have_text("0", timeout=20_000)
        self.page.get_by_role("button", name="模型分析").click()
        expect(self.page.locator(".cost-card").first).to_be_visible()
        self.page.get_by_role("button", name="经营价值").click()
        expect(self.page.locator("#differencePanel")).to_be_visible()
        result.evidence = {
            "current": self.page.locator("#current").inner_text(),
            "total_cost": self.page.locator("#totalCost").inner_text(),
            "cost_cards": self.page.locator(".cost-card").count(),
        }
        self.assert_true(result, self.page.locator(".cost-card").count() >= 4, "成本结构卡片不足")

    def e2e05_approval_and_publish_flow(self, result):
        self.goto("/results")
        self.set_role("admin")
        self.page.get_by_role("button", name="运行概览").click()
        self.page.locator("#run").click()
        expect(self.page.locator("#runSteps")).to_contain_text("完成", timeout=60_000)
        self.page.get_by_role("button", name="治理审批").click()
        self.page.locator("#submitApproval").click()
        expect(self.page.locator("#approvalStatus")).to_contain_text("待审批", timeout=20_000)
        self.page.locator("#approveRun").click()
        expect(self.page.locator("#approvalStatus")).to_contain_text("已批准", timeout=20_000)
        self.page.get_by_role("button", name="执行闭环").click()
        expect(self.page.locator("#publishExecution")).to_be_enabled(timeout=20_000)
        self.page.locator("#publishExecution").click()
        expect(self.page.locator("#publishStatus")).to_contain_text("已发布", timeout=20_000)
        result.evidence = {
            "approval_status": self.page.locator("#approvalStatus").inner_text(),
            "publish_status": self.page.locator("#publishStatus").inner_text(),
        }

    def e2e12_results_subviews_compare_enterprise_export(self, result):
        self.goto("/results")
        self.set_role("planner")
        self.page.get_by_role("button", name="运行概览").click()
        self.page.locator("#run").click()
        expect(self.page.locator("#runSteps")).to_contain_text("完成", timeout=60_000)
        self.page.locator("#compare").click()
        self.page.get_by_role("button", name="企业就绪").click()
        expect(self.page.locator("#enterpriseReadinessPanel")).to_be_visible(timeout=20_000)
        self.page.get_by_role("button", name="经营价值").click()
        expect(self.page.locator("#businessValuePanel")).to_be_visible(timeout=20_000)
        expect(self.page.locator("#tradeoffPanel")).to_be_visible(timeout=20_000)
        self.page.get_by_role("button", name="模型分析").click()
        expect(self.page.locator("#compareRows tr").first).to_be_visible(timeout=20_000)
        self.page.get_by_role("button", name="运行概览").click()
        self.page.locator("#exportReport").click()
        expect(self.page.locator("#exportStatus")).to_contain_text("已导出", timeout=30_000)
        result.evidence = {
            "compare_rows": self.page.locator("#compareRows tr").count(),
            "export_status": self.page.locator("#exportStatus").inner_text(),
            "enterprise_excerpt": self.page.locator("#enterpriseReadinessPanel").inner_text()[:300],
        }

    def e2e13_role_permission_gates(self, result):
        self.goto("/results")
        self.set_role("viewer")
        for selector in ["#run", "#exportReport", "#publishExecution"]:
            expect(self.page.locator(selector)).to_be_disabled()
        self.goto("/upstream")
        self.set_role("viewer")
        self.page.get_by_role("button", name="业务表编辑").click()
        expect(self.page.locator("#saveUpstream")).to_be_disabled()
        self.set_role("data_admin")
        expect(self.page.locator("#saveUpstream")).to_be_enabled()
        result.evidence = {
            "viewer_run_disabled": True,
            "viewer_export_disabled": True,
            "viewer_publish_disabled": True,
            "viewer_upstream_save_disabled": True,
            "data_admin_upstream_save_enabled": True,
        }

    def e2e14_approval_reject_path(self, result):
        self.goto("/results")
        self.set_role("admin")
        self.page.get_by_role("button", name="运行概览").click()
        self.page.locator("#run").click()
        expect(self.page.locator("#runSteps")).to_contain_text("完成", timeout=60_000)
        self.page.get_by_role("button", name="治理审批").click()
        self.page.locator("#submitApproval").click()
        expect(self.page.locator("#approvalStatus")).to_contain_text("待审批", timeout=20_000)
        self.page.locator("#rejectRun").click()
        expect(self.page.locator("#approvalStatus")).to_contain_text("已驳回", timeout=20_000)
        self.page.get_by_role("button", name="执行闭环").click()
        expect(self.page.locator("#publishExecution")).to_be_disabled(timeout=20_000)
        result.evidence = {
            "approval_status": self.page.locator("#approvalStatus").inner_text(),
            "publish_disabled_after_reject": True,
        }

    def e2e06_history_replay_and_report(self, result):
        self.goto("/results")
        self.set_role("planner")
        self.page.get_by_role("button", name="模型分析").click()
        expect(self.page.locator("#historyRows tr").first).to_be_visible(timeout=30_000)
        self.page.locator("[data-report-run]").first.click()
        expect(self.page.locator("#auditReportPanel")).to_contain_text("版本证据链", timeout=20_000)
        self.page.locator("[data-replay-run]").first.click()
        expect(self.page.locator("#exportStatus")).to_contain_text("已回放运行记录", timeout=60_000)
        result.evidence = {
            "history_rows": self.page.locator("#historyRows tr").count(),
            "replay_status": self.page.locator("#exportStatus").inner_text(),
        }

    def e2e07_lineage_and_constraints_navigation(self, result):
        self.goto("/lineage")
        expect(self.page.locator("#lineageDiagram .lineage-flow").first).to_be_visible(timeout=20_000)
        self.page.get_by_role("button", name="字段映射").click()
        expect(self.page.locator("#lineageFieldRows tr").first).to_be_visible()
        self.goto("/constraints")
        expect(self.page.locator("#constraintModelNav button").first).to_be_visible(timeout=20_000)
        self.page.locator('[data-constraint-model="replenishment"]').click()
        expect(self.page.locator(".code-block").first).to_contain_text("Python", timeout=10_000)
        expect(self.page.locator(".code-block").nth(1)).to_contain_text("OPL", timeout=10_000)
        result.evidence = {
            "lineage_flows": self.page.locator("#lineageDiagram .lineage-flow").count(),
            "constraint_models": self.page.locator("#constraintModelNav button").count(),
        }

    def e2e15_lineage_all_views_and_all_constraints(self, result):
        self.goto("/lineage")
        evidence = {}
        for key, name, selector in [
            ("flow", "可视化流程", "#lineageDiagram .lineage-flow"),
            ("nodes", "节点总览", "#lineageNodeRows .row"),
            ("transforms", "转换规则", "#lineageTransformRows tr"),
            ("fields", "字段映射", "#lineageFieldRows tr"),
        ]:
            self.page.locator(f'[data-lineage-view-button="{key}"]').click()
            expect(self.page.locator(selector).first).to_be_visible(timeout=20_000)
            evidence[name] = self.page.locator(selector).count()
        self.goto("/constraints")
        expect(self.page.locator("#constraintModelNav button").first).to_be_visible(timeout=20_000)
        model_count = self.page.locator("#constraintModelNav button").count()
        for index in range(model_count):
            button = self.page.locator("#constraintModelNav button").nth(index)
            model_name = button.inner_text()
            button.click()
            expect(self.page.locator(".code-block").first).to_contain_text("Python", timeout=10_000)
            expect(self.page.locator(".code-block").nth(1)).to_contain_text("OPL", timeout=10_000)
            evidence[f"constraint_{index + 1}"] = model_name
        result.evidence = evidence
        self.assert_true(result, model_count >= 4, "约束解释没有覆盖四个模型")

    def e2e08_capacity_assessment_page(self, result):
        self.goto("/performance")
        expect(self.page.locator("#capacityStatus")).to_contain_text("已完成", timeout=45_000)
        expect(self.page.locator("#capacitySummary")).to_contain_text("上游订单量")
        expect(self.page.locator("#throughputChart .throughput-row").first).to_be_visible()
        result.evidence = {
            "capacity_status": self.page.locator("#capacityStatus").inner_text(),
            "throughput_rows": self.page.locator("#throughputChart .throughput-row").count(),
        }

    def run_all(self):
        self.run_case("E2E01", "页面导航与订单明细抽样展示", self.e2e01_navigation_and_order_sample, ["FLOW_NAV", "UPSTREAM_ORDERS"])
        self.run_case("E2E02", "上游业务表页面编辑保存回读", self.e2e02_upstream_edit_save_roundtrip, ["UPSTREAM_EDIT"])
        self.run_case("E2E03", "场景配置传递到模型入参并高亮", self.e2e03_config_to_model_inputs_highlight, ["CONFIG_PLAYBOOK", "INPUT_HIGHLIGHT"])
        self.run_case("E2E04", "求解流水线进度与成本结构可视化", self.e2e04_results_pipeline_and_visuals, ["RESULT_RUN_PIPELINE", "RESULT_COST_VISUAL", "RESULT_EXPLAIN"])
        self.run_case("E2E05", "审批通过与执行发布闭环", self.e2e05_approval_and_publish_flow, ["RESULT_GOVERNANCE", "RESULT_EXECUTION"])
        self.run_case("E2E06", "运行历史报告与回放", self.e2e06_history_replay_and_report, ["RESULT_HISTORY"])
        self.run_case("E2E07", "数据血缘与约束解释页面导航", self.e2e07_lineage_and_constraints_navigation, ["LINEAGE", "CONSTRAINTS"])
        self.run_case("E2E08", "压力测试与容量评估页面", self.e2e08_capacity_assessment_page, ["PERFORMANCE"])
        self.run_case("E2E09", "上游数据二级页面覆盖", self.e2e09_upstream_source_quality_quarantine_weather_scale, ["UPSTREAM_SOURCE", "UPSTREAM_QUALITY", "UPSTREAM_QUARANTINE", "UPSTREAM_WEATHER", "UPSTREAM_SCALE"])
        self.run_case("E2E10", "场景配置保存审计与权限", self.e2e10_config_playbooks_save_audit_and_permissions, ["CONFIG_PLAYBOOK", "CONFIG_SAVE_AUDIT", "ROLE_PERMISSIONS"])
        self.run_case("E2E11", "四模型入参导航与重新生成", self.e2e11_model_input_tabs_and_regeneration, ["INPUT_NAV", "INPUT_HIGHLIGHT", "RESULT_RUN_PIPELINE"])
        self.run_case("E2E12", "结果页面板、三方案对比与报告导出", self.e2e12_results_subviews_compare_enterprise_export, ["RESULT_ENTERPRISE", "RESULT_EXPLAIN", "REPORT_EXPORT", "RESULT_COST_VISUAL"])
        self.run_case("E2E13", "角色权限隔离页面校验", self.e2e13_role_permission_gates, ["ROLE_PERMISSIONS"])
        self.run_case("E2E14", "审批驳回路径与发布拦截", self.e2e14_approval_reject_path, ["RESULT_GOVERNANCE", "RESULT_EXECUTION", "ROLE_PERMISSIONS"])
        self.run_case("E2E15", "血缘多视图与四模型约束覆盖", self.e2e15_lineage_all_views_and_all_constraints, ["LINEAGE", "CONSTRAINTS"])
        return self.results


def wait_for_server(base_url, timeout=45):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with opener.open(f"{base_url}/api/health", timeout=2) as response:
                body = response.read(200).decode("utf-8", errors="ignore")
                if response.status == 200 and "cplex-optimization-platform-poc" in body:
                    return True
        except (urllib.error.URLError, TimeoutError, ValueError):
            time.sleep(1)
    return False


def free_port():
    with closing(socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server_if_needed():
    global BASE_URL
    force_server = os.environ.get("PLATFORM_E2E_FORCE_SERVER") == "1"
    if not force_server and wait_for_server(BASE_URL, timeout=2):
        return None
    if "PLATFORM_E2E_BASE_URL" in os.environ and not force_server:
        raise RuntimeError(f"指定的平台地址不可用：{BASE_URL}")
    port = free_port()
    BASE_URL = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(SERVER_ENV)
    env.update({"NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
    process = subprocess.Popen(
        [sys.executable, "-c", f"import platform_app; platform_app.app.run(host='127.0.0.1', port={port}, debug=False, use_reloader=False)"],
        cwd=Path(__file__).resolve().parent,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if not wait_for_server(BASE_URL, timeout=60):
        output = ""
        process.terminate()
        if process.stdout:
            try:
                output = process.communicate(timeout=3)[0][:2000]
            except Exception:
                output = ""
        raise RuntimeError(f"平台服务未能在 60 秒内启动。{output}")
    return process


def write_reports(results):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    total = len(results)
    passed = len([item for item in results if item.status == "PASS"])
    failed = len([item for item in results if item.status == "FAIL"])
    errors = len([item for item in results if item.status == "ERROR"])
    passed_features = sorted({feature for item in results if item.status == "PASS" for feature in item.features})
    feature_total = len(FEATURE_REGISTRY)
    feature_coverage = round(len(passed_features) / feature_total * 100, 2) if feature_total else 0
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": BASE_URL,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": round(passed / total * 100, 2) if total else 0,
            "assertions": sum(item.assertions for item in results),
            "feature_coverage": f"{len(passed_features)}/{feature_total}",
            "feature_coverage_percent": feature_coverage,
        },
        "feature_registry": FEATURE_REGISTRY,
        "covered_features": passed_features,
        "uncovered_features": sorted(set(FEATURE_REGISTRY) - set(passed_features)),
        "results": [item.__dict__ for item in results],
    }
    json_path = REPORTS_DIR / f"platform_e2e_test_report_{timestamp}.json"
    md_path = REPORTS_DIR / f"platform_e2e_test_report_{timestamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# CPLEX 优化平台页面端到端测试报告",
        "",
        f"- 生成时间：`{payload['generated_at']}`",
        f"- 平台地址：`{BASE_URL}`",
        f"- 通过率：`{payload['summary']['pass_rate']}%`（{passed}/{total}）",
        f"- 页面功能覆盖率：`{feature_coverage}%`（{len(passed_features)}/{feature_total}）",
        f"- 断言数：`{payload['summary']['assertions']}`",
        "",
        "## 页面功能覆盖矩阵",
        "",
        "| 功能点 | 覆盖状态 | 说明 |",
        "|---|---:|---|",
    ]
    for key, description in FEATURE_REGISTRY.items():
        lines.append(f"| `{key}` | {'已覆盖' if key in passed_features else '未覆盖'} | {description} |")
    lines.extend([
        "",
        "## 用例结果",
        "",
        "| 用例 | 名称 | 状态 | 断言 | 耗时 ms | 失败信息 |",
        "|---|---|---:|---:|---:|---|",
    ])
    for item in results:
        failures = "<br>".join(item.failures) if item.failures else "-"
        lines.append(f"| {item.case_id} | {item.name} | {item.status} | {item.assertions} | {item.elapsed_ms} | {failures} |")
    lines.extend(["", "## 证据", ""])
    for item in results:
        lines.append(f"### {item.case_id} {item.name}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(item.evidence, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return payload, json_path, md_path


def main():
    headed = "--headed" in sys.argv
    server = start_server_if_needed()
    try:
        with sync_playwright() as playwright:
            runner = PlatformE2ERunner(headed=headed)
            runner.start_browser(playwright)
            try:
                results = runner.run_all()
            finally:
                runner.close_browser()
        payload, json_path, md_path = write_reports(results)
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {md_path}")
        return 0 if payload["summary"]["failed"] == 0 and payload["summary"]["errors"] == 0 else 1
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
