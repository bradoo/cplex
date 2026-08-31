# CPLEX 优化平台准确性测试用例

本文档用于手动验证和自动化测试。当前自动化脚本为 `python/run_platform_accuracy_tests.py`。

- 平台地址：`http://127.0.0.1:5053`
- 上游模式：`PLATFORM_UPSTREAM_SOURCE=starrocks`
- 数据库：`cplex_poc`
- 关键表：`upstream_orders`、`upstream_network_lanes`、`upstream_weather_lane_impacts`
- 运行命令：`PYTHONPATH=python PLATFORM_UPSTREAM_SOURCE=starrocks .venv/bin/python python/run_platform_accuracy_tests.py`
- 覆盖率命令：`cd python && PLATFORM_UPSTREAM_SOURCE=starrocks ../.venv/bin/python -m coverage run --source=. run_platform_accuracy_tests.py`
- 页面端到端测试命令：`PLATFORM_UPSTREAM_SOURCE=starrocks .venv/bin/python python/run_platform_e2e_tests.py`
- 页面端到端测试依赖：首次运行前执行 `cd python && ../.venv/bin/python -m playwright install chromium`

## 测试分层

- `TC01` - `TC24`：模型准确性、API、数据链路、StarRocks 写入、mock 分支和装载脚本覆盖。
- `E2E01` - `E2E08`：使用 Playwright 启动真实 Chromium 浏览器，验证简化后的数据、配置、决策、治理主流程，以及隐藏技术页、快速放行、权限隔离和报告导出。
- 页面端到端报告会输出页面功能覆盖率，覆盖矩阵以关键页面能力为口径，而不是只统计测试用例数量。

## TC01 数据源健康检查

目的：确认平台读取的是 StarRocks 上游数据，不是本地 JSON 样例。

操作：请求 `GET /api/platform/source-status`。

断言：HTTP 200；`status=ok`；`mode=StarRocks`；订单量不少于 100 万；源表列表包含 `cplex_poc.upstream_weather_lane_impacts`；天气表行数大于 0。

通过标准：以上断言全部成立。

## TC02 天气数据接入准确性

目的：确认天气数据来自 StarRocks 天气表，并进入上游数据接口。

操作：请求 `GET /api/platform/upstream-data`。

断言：`data.weather.source=StarRocks.upstream_weather_lane_impacts`；API 天气行数等于 StarRocks 天气表行数；每条天气记录包含仓库、市场、风险、延误、成本系数和原因。

通过标准：API 不回退到 JSON 天气样例，天气行数与 StarRocks 表一致。

## TC03 天气因子进入模型入参

目的：确认天气因子会进入仓网模型的 `lane_costs_and_sla`。

操作：使用 `planner` 角色请求 `POST /api/platform/run`，入参为 `{"playbook":"resilient","overrides":{}}`。

断言：HTTP 200；`model_inputs.lineage.weather_source` 为 StarRocks 天气表；仓网入参存在天气线路；天气影响线路数等于 `network.weather_impacted_lanes` 数量。

通过标准：天气数据同时出现在模型入参和求解结果中。

## TC04 天气成本转换准确性

目的：确认线路成本按天气成本系数正确调整。

操作：运行 `resilient` 场景，遍历受天气影响的 `lane_costs_and_sla`。

断言：对每条天气线路，`last_mile_cost = round(base_last_mile_cost * weather_cost_multiplier, 2)`。

通过标准：所有天气线路成本计算完全匹配。

## TC05 天气时效与 SLA 判断准确性

目的：确认天气延误会进入配送天数，并影响 SLA 可用性。

操作：运行 `resilient` 场景，遍历 `model_inputs.network.lane_costs_and_sla`。

断言：`delivery_days = base_delivery_days + weather_delay_days`；`allowed_by_sla = delivery_days <= markets[market].max_delivery_days`。

通过标准：所有线路的天气时效和 SLA 判断一致。

## TC06 禁用线路不被求解结果使用

目的：确认 CPLEX 不会把订单分配到 SLA 禁用线路。

操作：运行 `baseline`、`peak`、`resilient` 三个场景。

断言：任一 `allowed_by_sla=false` 的线路，在 `network.fulfillment_plan` 中订单量必须为 0 或不存在。

通过标准：三个场景均不使用 SLA 禁用线路。

## TC07 仓库容量约束准确性

目的：确认求解结果不会超过仓库容量。

操作：运行 `baseline`、`peak`、`resilient` 三个场景，读取 `network.capacity_plan`。

断言：对每个仓库，`used_capacity <= base_capacity + extra_capacity`；没有 `extra_capacity` 时按 0 处理。

通过标准：所有场景、所有仓库都不超容量。

## TC08 服务水平模型需求平衡

目的：确认服务商分单结果满足各市场需求。

操作：运行 `resilient` 场景，读取 `model_inputs.service_level.markets` 和 `service_mix.allocation`。

断言：对每个市场，`sum(allocation[market].orders) = model_inputs.service_level.markets[market].demand`。

通过标准：所有市场服务分单量与需求一致。

## TC09 天气 A/B 价值验证

目的：确认天气数据不是展示字段，而是会改变优化结果。

操作：保留当前天气表数据运行 `resilient`；再在测试脚本中 mock 为空天气，运行同一场景。

断言：有天气时天气影响线路数大于 0；无天气时天气影响线路数等于 0；成本或缺口至少有一项变化。

通过标准：天气数据对模型结果产生可观测影响。

## TC10 极端天气手动注入验证

目的：验证单条线路天气异常会被模型正确识别、禁用或规避。

操作：暂存原始天气表；将 `Los Angeles 3PL -> US West` 改成 `risk_level=high`、`delay_days=5`、`cost_multiplier=1.5`；运行 `resilient`；测试后恢复原始天气表。

断言：目标线路延误、成本系数和配送天数进入模型入参；如果超过 SLA，求解结果中该线路订单量为 0。

通过标准：极端天气能传导到模型入参，并被求解结果规避。

## TC11 页面与只读 API 路由覆盖

目的：确认主要页面和只读 API 均可访问。

操作：请求 `/`、`/upstream`、`/config`、`/inputs`、`/results`、`/lineage`、`/constraints`、`/performance`，以及健康、概览、配置、质量、隔离、规模、容量、企业就绪、血缘、模型解释、三方案对比和运行历史 API。

断言：所有页面/API 返回 200，favicon 返回 204。

通过标准：主要页面和只读 API 没有 4xx/5xx 错误。

## TC12 权限与输入校验错误覆盖

目的：确认权限隔离和错误输入能被正确拦截。

操作：分别触发只读角色运行模型、未知 playbook、错误平台配置、错误上游数据、计划员审批批准、非法审批动作、发布执行缺少 `run_id`。

断言：对应请求返回 403 或 400。

通过标准：未授权动作和非法输入均被拦截。

## TC13 场景配置保存审计与恢复

目的：确认场景配置可保存、审计可记录、测试后可恢复。

操作：读取当前平台配置；临时修改 `baseline.description`；调用 `PUT /api/platform/data` 保存；查询配置审计；恢复原始配置。

断言：保存成功；审计记录不为空；恢复成功。

通过标准：配置保存、审计和恢复链路完整。

## TC14 运行历史审批发布报告闭环

目的：验证运行批次、批次报告、审批、发布执行和报告导出闭环。

操作：运行 `resilient` 并保存历史；查询运行历史和运行报告；提交审批并批准；发布执行；导出演示报告。

断言：新批次有 `run_id`；历史和报告可查；审批状态进入 `approved` 或 `auto_approved`；发布执行返回 4 个目标系统；导出报告文件存在。

通过标准：运行批次从生成到发布执行全链路通过。

## TC15 校验与异常隔离边界覆盖

目的：确认异常上游数据会被校验和异常隔离区识别。

操作：构造缺失字段、非法市场、负订单量、非法天气引用等异常数据，调用 `validate_upstream_data` 和 `build_data_quarantine`。

断言：校验返回错误；异常隔离区 `total_issues` 大于 0；`NaN` 和空 playbooks 被拦截。

通过标准：异常数据不会静默进入模型层。

## TC16 JSON 模式分支覆盖

目的：确认非 StarRocks 模式仍能读取本地 JSON 样例并构建规模/容量评估。

操作：在测试中 mock `starrocks_upstream_enabled=False`，调用 JSON 模式相关函数。

断言：上游来源和平台配置来源指向本地 JSON；源状态 `mode=JSON`；规模快照和容量评估返回 `ok`。

通过标准：JSON fallback 分支可用。

## TC17 天气装载脚本纯函数覆盖

目的：验证天气风险分级函数。

操作：构造低、中、高风险天气指标，调用 `classify_weather_risk`。

断言：低风险返回 `low, 0, 1.02`；中风险返回 `medium, 1, 1.08`；高风险返回 `high, 2, 1.18`。

通过标准：天气分级规则符合预期。

## TC18 天气装载脚本 mock 覆盖

目的：验证天气装载脚本能按市场预报生成线路级天气风险行。

操作：mock 市场坐标和 `fetch_market_weather`；fake cursor 返回有效线路和无效市场线路；调用 `build_weather_rows`。

断言：只为有效市场生成天气线路；EU 降水 mock 能转换为中风险；forecast 缓存包含目标市场；快照时间不为空。

通过标准：天气脚本能从市场预报生成线路级入库数据。

## TC19 StarRocks 上游装载脚本 mock 覆盖

目的：验证上游维表和平台配置装载逻辑。

操作：使用 fake cursor 和小样本数据调用 `load_dimension_tables`、`load_platform_tables`、`batched`。

断言：天气线路、网络线路、playbook 统计正确；批处理切片正确；fake cursor 收到天气表写入。

通过标准：维表装载和批处理逻辑正确。

## TC20 StarRocks 上游基础表保存回读

目的：验证平台保存上游基础表后可从 StarRocks 回读。

操作：读取当前上游数据；调用 `save_starrocks_upstream_data` 保存；重新读取上游数据。

断言：保存后天气表行数等于当前天气影响行数；回读天气来源仍为 StarRocks 天气表；网络线路数量不变。

通过标准：上游基础表写入和回读一致。

## TC21 装载脚本建表与天气写库 mock 覆盖

目的：覆盖建表 SQL、天气 API 解析和天气写库主流程。

操作：mock `load_starrocks_upstream.connect` 调用 `create_schema`；mock `load_starrocks_weather.connect` 和 `urlopen` 调用 `load_weather`；调用 `fetch_market_weather` 解析 mock Open-Meteo 响应。

断言：建表 SQL 数量达到预期；mock 天气装载插入 2 行；fake cursor 收到 2 行天气写入；mock 天气响应解析出最大降水。

通过标准：建表、API 解析、天气写库主流程可被自动化验证。

## TC22 数据校验错误矩阵覆盖

目的：覆盖更多上游数据和平台配置错误分支。

操作：构造缺失 network、缺失仓库容量、非法 SLA、非法扩容引用、缺失线路、缺失补货周、缺失服务商市场成本、非法天气成本系数等错误数据。

断言：每组异常数据都触发校验错误；非对象平台配置和空 playbook id 触发错误；`weather_risk_score` 和 `markdown_cell` 返回预期结果。

通过标准：主要校验错误分支都能被覆盖。

## TC23 上游订单装载流程 mock 覆盖

目的：覆盖 `load_starrocks_upstream.load_orders` 的主流程，但不真实重灌百万订单。

操作：mock 数据文件、`connect`、`create_schema` 和 `build_orders`，使用小样本订单执行 `load_orders`。

断言：返回的 `loaded_order_lines` 等于 mock 计数；`target_order_lines` 等于请求订单数；市场聚合结果符合 mock 数据；订单表 truncate 被执行。

通过标准：订单装载主流程在 mock 环境下可验证。

## TC24 CLI main 与连接参数 mock 覆盖

目的：覆盖两个装载脚本的 CLI 参数解析和连接参数传递。

操作：mock `sys.argv` 和装载函数，调用 `load_starrocks_weather.main()` 与 `load_starrocks_upstream.main()`；mock `pymysql.connect` 调用两个脚本的 `connect`。

断言：天气 CLI 正确解析 `--forecast-days` 和 `--no-truncate`；上游 CLI 正确解析 `--orders` 和 `--skip-orders`；`connect` 正确传递 database、host、port、user、password。

通过标准：CLI 和连接配置逻辑可被自动化验证。

## E2E01 简化主导航与技术页隐藏

目的：确认平台主流程已收敛为 `数据 / 配置 / 决策 / 治理`，并且 `入参 / 血缘 / 约束` 不再作为常规入口暴露。

操作：管理员登录后访问 `/upstream`；检查顶部导航；直接访问 `/inputs`、`/lineage`、`/constraints`。

断言：顶部主导航只有 4 个入口；技术页导航链接不存在；直接访问隐藏技术页会重定向到当前角色可用页面。

通过标准：普通演示路径不会看到或误入技术细节页。

## E2E02 数据工作台三入口与业务数据保存

目的：确认数据页已收敛为 `数据概览 / 质量状态 / 业务数据`，且数据管理员仍可维护上游业务数据。

操作：数据管理员访问 `/upstream`；检查三个二级入口；查看数据概览与质量状态；进入“业务数据”临时修改市场需求、保存、刷新回读并恢复原值。

断言：数据页只有 3 个二级入口；源指标和质量检查可见；业务数据保存后可回读。

通过标准：数据页简洁，同时不牺牲维护能力。

## E2E03 配置运行进入决策总览

目的：确认计划员可以配置场景并直接进入新版决策总览，而不再依赖模型入参页。

操作：计划员访问 `/config`；修改需求倍率和空运容量；点击“保存临时参数并运行”；进入 `/results`。

断言：至少有 3 个场景模板；求解完成；决策页只有 `决策总览 / 审批放行` 两个页签；综合成本、管理层摘要和经营影响可见。

通过标准：用户从配置到决策页即可完成核心判断。

## E2E04 审批放行页快速放行

目的：确认 `快速放行` 在审批页仍然可见，并能完成当前角色允许的审批/发布动作。

操作：管理员访问 `/results`；运行当前方案；切换“审批放行”；点击“快速放行”。

断言：快速放行按钮在审批页可见；审批状态进入已批准；发布状态不显示失败。

通过标准：审批页可以高效完成放行，不需要切回其他页签。

## E2E05 报告导出与运行审计

目的：确认新版决策页仍保留报告导出和运行批次审计能力。

操作：计划员访问 `/results`；运行当前方案；点击“导出报告”；进入“审批放行”；打开运行记录报告。

断言：导出状态显示已导出；运行历史有记录；审计报告显示版本证据链；查看审计报告后快速放行按钮仍可见。

通过标准：页面简化后仍可追溯、可汇报。

## E2E06 简化角色权限隔离

目的：确认简化页面后的角色权限仍然生效。

操作：分别使用 viewer、approver、data_admin 访问结果、配置、上游页面。

断言：viewer 不能运行、导出或快速放行；viewer 访问配置页会被重定向；approver 访问上游页会被重定向到结果页；data_admin 可保存业务数据。

通过标准：页面变少后，角色边界仍清晰。

## E2E07 治理容量评估

目的：确认治理页仍能展示容量和压力测试结果。

操作：viewer 访问 `/performance`。

断言：容量评估状态显示已完成；容量摘要包含上游订单量；吞吐曲线至少一行。

通过标准：治理页可以支撑平台容量沟通。

## E2E08 主流程无控制台错误

目的：防止简化页面后出现隐藏面板、历史记录或快速放行引发的前端异常。

操作：管理员访问 `/results`；运行当前方案；切换“审批放行”；点击“快速放行”；监听浏览器 console error 和 page error。

断言：主流程无 console error；审批状态不显示失败。

通过标准：新版主流程前端运行干净。
