# CPLEX 优化平台准确性测试用例

本文档用于手动验证和后续自动化测试。默认测试环境为当前 StarRocks 版本平台：

- 平台地址：`http://127.0.0.1:5053`
- 上游模式：`PLATFORM_UPSTREAM_SOURCE=starrocks`
- 数据库：`cplex_poc`
- 关键表：`upstream_orders`、`upstream_network_lanes`、`upstream_weather_lane_impacts`

## TC01 数据源健康检查

目的：确认平台读取的是 StarRocks 上游数据，不是本地 JSON 样例。

前置条件：
- 当前服务已启动。
- StarRocks 可连接。

操作：
- 请求 `GET /api/platform/source-status`。

断言：
- HTTP 状态码为 `200`。
- `status` 为 `ok`。
- `mode` 为 `StarRocks`。
- `summary.order_lines` 大于等于 `1000000`。
- `tables` 中包含 `cplex_poc.upstream_weather_lane_impacts`。
- 天气表行数大于 `0`。

通过标准：
- 以上断言全部成立。

## TC02 天气数据接入准确性

目的：确认天气数据来自 StarRocks 天气表，并进入上游数据接口。

操作：
- 请求 `GET /api/platform/upstream-data`。

断言：
- HTTP 状态码为 `200`。
- `data.weather.source` 等于 `StarRocks.upstream_weather_lane_impacts`。
- `data.weather.lane_impacts` 数量等于 StarRocks 表 `upstream_weather_lane_impacts` 行数。
- 每条天气记录包含 `warehouse`、`market`、`risk_level`、`delay_days`、`cost_multiplier`、`reason`。

通过标准：
- 页面/API 不再回退到 JSON 天气样例，天气行数与 StarRocks 表一致。

## TC03 天气因子进入模型入参

目的：确认天气因子会进入仓网模型的 `lane_costs_and_sla`。

操作：
- 使用 `planner` 角色请求 `POST /api/platform/run`，入参为：

```json
{"playbook":"resilient","overrides":{}}
```

断言：
- HTTP 状态码为 `200`。
- `model_inputs.lineage.weather_source` 等于 `StarRocks.upstream_weather_lane_impacts`。
- `model_inputs.network.lane_costs_and_sla` 中存在 `weather_risk_level` 不是 `none` 的记录。
- 天气影响线路数等于 `network.weather_impacted_lanes` 数量。

通过标准：
- 天气数据同时出现在模型入参和求解结果中。

## TC04 天气成本转换准确性

目的：确认线路成本按天气成本系数正确调整。

操作：
- 请求 `POST /api/platform/run`，场景为 `resilient`。
- 遍历 `model_inputs.network.lane_costs_and_sla` 中受天气影响的线路。

断言：
- 对每条天气线路：
  - `last_mile_cost = round(base_last_mile_cost * weather_cost_multiplier, 2)`。

通过标准：
- 所有天气线路成本计算都完全匹配。

## TC05 天气时效与 SLA 判断准确性

目的：确认天气延误会进入配送天数，并影响 SLA 可用性。

操作：
- 请求 `POST /api/platform/run`，场景为 `resilient`。
- 遍历 `model_inputs.network.lane_costs_and_sla`。

断言：
- 对每条线路：
  - `delivery_days = base_delivery_days + weather_delay_days`。
  - `allowed_by_sla = delivery_days <= markets[market].max_delivery_days`。

通过标准：
- 所有线路的天气时效和 SLA 判断都一致。

## TC06 禁用线路不被求解结果使用

目的：确认 CPLEX 不会把订单分配到 SLA 禁用线路。

操作：
- 请求 `POST /api/platform/run`，分别测试 `baseline`、`peak`、`resilient`。
- 读取 `model_inputs.network.lane_costs_and_sla` 中 `allowed_by_sla=false` 的线路。
- 读取 `network.fulfillment_plan`。

断言：
- 任一 `allowed_by_sla=false` 的线路，在 `fulfillment_plan` 中订单量必须为 `0` 或不存在。

通过标准：
- 三个场景均不使用 SLA 禁用线路。

## TC07 仓库容量约束准确性

目的：确认求解结果不会超过仓库容量。

操作：
- 请求 `POST /api/platform/run`，分别测试 `baseline`、`peak`、`resilient`。
- 读取 `network.capacity_plan`。

断言：
- 对每个仓库：
  - `used_capacity <= base_capacity + extra_capacity`。
  - 如果没有 `extra_capacity` 字段，则按 `0` 处理。

通过标准：
- 所有场景、所有仓库都不超容量。

## TC08 服务水平模型需求平衡

目的：确认服务商分单结果满足各市场需求。

操作：
- 请求 `POST /api/platform/run`，场景为 `resilient`。
- 读取 `model_inputs.service_level.markets`。
- 读取 `service_mix.allocation`。

断言：
- 对每个市场：
  - `sum(allocation[market].orders) = model_inputs.service_level.markets[market].demand`。

通过标准：
- 所有市场服务分单量与需求一致。

## TC09 天气 A/B 价值验证

目的：确认天气数据不是展示字段，而是会改变优化结果。

操作：
- 保留当前天气表数据，运行 `resilient`，记录 `summary.total_cost`、`summary.total_shortage`、`network.weather_impacted_lanes`。
- 临时将 `upstream_weather_lane_impacts` 清空或在测试脚本中 mock 为空天气，再运行同一场景。

断言：
- 有天气时 `network.weather_impacted_lanes` 大于 `0`。
- 无天气时 `network.weather_impacted_lanes` 等于 `0`。
- 有天气与无天气的 `summary.total_cost` 至少有一项关键 KPI 发生变化。

通过标准：
- 天气数据对模型结果产生可观测影响。

## TC10 极端天气手动注入验证

目的：验证单条线路天气异常会被模型正确识别、禁用或规避。

前置条件：
- 记录原始 `Los Angeles 3PL -> US West` 天气数据，便于恢复。

操作：
- 在上游数据页面的“业务表编辑 -> 天气风险表”中修改：
  - `warehouse = Los Angeles 3PL`
  - `market = US West`
  - `risk_level = high`
  - `delay_days = 5`
  - `cost_multiplier = 1.5`
  - `reason = 自动化测试：极端天气导致 US West 末端配送中断`
- 点击保存。
- 运行 `baseline` 或 `resilient`。

断言：
- 模型入参中该线路：
  - `weather_delay_days = 5`
  - `weather_cost_multiplier = 1.5`
  - `delivery_days = base_delivery_days + 5`
  - 如果超过 `US West.max_delivery_days`，则 `allowed_by_sla = false`。
- 求解结果中该线路没有被使用，或订单量为 `0`。

通过标准：
- 极端天气能传导到模型入参，并被求解结果规避。

测试后恢复：
- 将该线路恢复为测试前记录的值，或重新执行 `python/load_starrocks_weather.py --forecast-days 3` 刷新公共天气数据。
