# CPLEX 优化平台准确性自动化测试报告

- 生成时间：`2026-08-31T11:36:09`
- 测试依据：`/Users/bradwoo/cplex/docs/platform_accuracy_test_cases.md`
- 平台地址：`http://127.0.0.1:5053`
- 上游模式：`starrocks`
- StarRocks 数据库：`cplex_poc`

## 总览

- 测试用例覆盖率：`100.0%`（24/24）
- 通过率：`100.0%`
- 通过：`24`
- 失败：`0`
- 错误：`0`
- 断言总数：`118`

## 明细

| 用例 | 名称 | 状态 | 断言 | 耗时 ms | 关键证据 |
| --- | --- | --- | ---: | ---: | --- |
| TC01 | 数据源健康检查 | PASS | 6 | 246.26 | {"http_status": 200, "mode": "StarRocks", "summary": {"order_lines": 1000000, "sample_rows": 1000, "source_tables": 21}, "weather_table": {"name": "cplex_poc.upstream_weather_lane_impacts", "role": "天气线路风险", "rows": 20}} |
| TC02 | 天气数据接入准确性 | PASS | 4 | 179.12 | {"http_status": 200, "weather_source": "StarRocks.upstream_weather_lane_impacts", "api_weather_rows": 20, "table_weather_rows": 20} |
| TC03 | 天气因子进入模型入参 | PASS | 4 | 1635.26 | {"http_status": 200, "weather_source": "StarRocks.upstream_weather_lane_impacts", "weather_inputs": 20, "weather_results": 20} |
| TC04 | 天气成本转换准确性 | PASS | 2 | 1337.02 | {"checked_lanes": 20} |
| TC05 | 天气时效与 SLA 判断准确性 | PASS | 1 | 0.02 | {"checked_lanes": 20, "weather_blocked_lanes": 3} |
| TC06 | 禁用线路不被求解结果使用 | PASS | 1 | 1229.34 | {"checked_playbooks": ["baseline", "peak", "resilient"]} |
| TC07 | 仓库容量约束准确性 | PASS | 1 | 0.02 | {"checked_playbooks": ["baseline", "peak", "resilient"]} |
| TC08 | 服务水平模型需求平衡 | PASS | 1 | 0.01 | {"checked_markets": 4} |
| TC09 | 天气 A/B 价值验证 | PASS | 3 | 1413.93 | {"cost_delta": 2875.0, "with_weather_lanes": 20, "without_weather_lanes": 0} |
| TC10 | 极端天气手动注入验证 | PASS | 5 | 1329.58 | {"used_orders": 0, "target_lane": {"lane": "Los Angeles 3PL->US West", "delay": 5, "cost_multiplier": 1.5, "allowed_by_sla": false}} |
| TC11 | 页面与只读 API 路由覆盖 | PASS | 22 | 20218.82 | {} |
| TC12 | 权限与输入校验错误覆盖 | PASS | 7 | 184.75 | {} |
| TC13 | 场景配置保存审计与恢复 | PASS | 4 | 1556.8 | {} |
| TC14 | 运行历史审批发布报告闭环 | PASS | 10 | 3677.89 | {} |
| TC15 | 校验与异常隔离边界覆盖 | PASS | 4 | 114.81 | {} |
| TC16 | JSON 模式分支覆盖 | PASS | 5 | 192.26 | {} |
| TC17 | 天气装载脚本纯函数覆盖 | PASS | 3 | 6.11 | {} |
| TC18 | 天气装载脚本 mock 覆盖 | PASS | 4 | 0.07 | {} |
| TC19 | StarRocks 上游装载脚本 mock 覆盖 | PASS | 5 | 1.4 | {} |
| TC20 | StarRocks 上游基础表保存回读 | PASS | 3 | 2642.72 | {} |
| TC21 | 装载脚本建表与天气写库 mock 覆盖 | PASS | 4 | 0.52 | {} |
| TC22 | 数据校验错误矩阵覆盖 | PASS | 12 | 172.2 | {} |
| TC23 | 上游订单装载流程 mock 覆盖 | PASS | 4 | 0.32 | {} |
| TC24 | CLI main 与连接参数 mock 覆盖 | PASS | 3 | 1.5 | {} |

## 覆盖说明

- 24/24 个测试用例全部自动化执行，测试用例覆盖率为 100.0%。
- 本报告统计业务测试用例覆盖率和断言结果；代码行覆盖率由 `coverage.py` 单独生成。
