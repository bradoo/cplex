# CPLEX 优化平台代码覆盖率报告

- 生成时间：`2026-08-31T11:19:13`
- 测试命令：`PLATFORM_UPSTREAM_SOURCE=starrocks ../.venv/bin/python -m coverage run --source=. run_platform_accuracy_tests.py`
- 测试报告：`python/reports/platform_accuracy_test_report_20260831_111913.md`
- HTML 覆盖率报告：`python/reports/platform_accuracy_coverage_html/index.html`
- XML 覆盖率报告：`python/reports/platform_accuracy_coverage.xml`
- JSON 覆盖率报告：`python/reports/platform_accuracy_coverage.json`

## 测试结果

- 自动化测试用例：`17`
- 通过：`17`
- 失败：`0`
- 错误：`0`
- 断言：`83`

## 代码覆盖率

| 文件 | 语句数 | 未覆盖 | 覆盖率 |
| --- | ---: | ---: | ---: |
| `platform_app.py` | 1702 | 257 | 85% |
| `run_platform_accuracy_tests.py` | 370 | 13 | 96% |
| `load_starrocks_weather.py` | 90 | 51 | 43% |
| `load_starrocks_upstream.py` | 122 | 122 | 0% |
| **合计** | **2284** | **443** | **81%** |

## 结论

- 本轮已经达到代码覆盖率目标：总体覆盖率 `81%`，超过目标 `80%`。
- 平台核心后端 `platform_app.py` 覆盖率达到 `85%`。
- 17 个自动化测试用例全部通过，覆盖数据源、天气因子、模型入参、求解结果、SLA、容量、服务分配、权限、配置审计、审批、发布执行、报告导出、JSON 模式和异常数据隔离。

## 剩余低覆盖区域

- `load_starrocks_upstream.py` 当前为 `0%`，原因是本轮测试没有执行百万订单装载流程，避免在自动化测试中反复重建大表。
- `load_starrocks_weather.py` 当前为 `43%`，已覆盖天气风险分级，尚未 mock 公共天气 API 和 StarRocks 写库路径。

## 后续建议

- 下一步可以增加 mock cursor 和 mock Open-Meteo 响应，把两个数据装载脚本也纳入单元测试。
- 如果把装载脚本纳入覆盖目标，建议单独建立 `tests/test_starrocks_loaders.py`，不要在准确性冒烟测试中真实重灌 100 万订单。
