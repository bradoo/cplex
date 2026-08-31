# CPLEX 优化平台页面端到端测试报告

- 生成时间：`2026-08-31T14:26:58`
- 平台地址：`http://127.0.0.1:58019`
- 通过率：`100.0%`（16/16）
- 页面功能覆盖率：`100.0%`（26/26）
- 断言数：`15`

## 页面功能覆盖矩阵

| 功能点 | 覆盖状态 | 说明 |
|---|---:|---|
| `AUTH_LOGIN` | 已覆盖 | 用户登录与退出 |
| `FLOW_NAV` | 已覆盖 | 顶部流程导航与页面装载 |
| `UPSTREAM_SOURCE` | 已覆盖 | 上游数据源状态 |
| `UPSTREAM_QUALITY` | 已覆盖 | 数据质量校验 |
| `UPSTREAM_QUARANTINE` | 已覆盖 | 异常数据隔离区 |
| `UPSTREAM_WEATHER` | 已覆盖 | 天气风险因子 |
| `UPSTREAM_SCALE` | 已覆盖 | 规模吞吐概览 |
| `UPSTREAM_ORDERS` | 已覆盖 | 订单明细抽样 |
| `UPSTREAM_EDIT` | 已覆盖 | 上游业务表编辑保存 |
| `CONFIG_PLAYBOOK` | 已覆盖 | 三场景配置导航 |
| `CONFIG_SAVE_AUDIT` | 已覆盖 | 场景配置保存与审计 |
| `INPUT_NAV` | 已覆盖 | 四模型入参导航 |
| `INPUT_HIGHLIGHT` | 已覆盖 | 模型入参变化高亮 |
| `RESULT_RUN_PIPELINE` | 已覆盖 | 求解流水线 |
| `RESULT_COST_VISUAL` | 已覆盖 | 成本结构可视化 |
| `RESULT_EXPLAIN` | 已覆盖 | 经营价值与差异解释 |
| `RESULT_ENTERPRISE` | 已覆盖 | 企业就绪面板 |
| `RESULT_GOVERNANCE` | 已覆盖 | 治理审批 |
| `RESULT_EXECUTION` | 已覆盖 | 执行发布闭环 |
| `RESULT_HISTORY` | 已覆盖 | 运行历史回放与报告 |
| `LINEAGE` | 已覆盖 | 数据血缘可视化与字段映射 |
| `CONSTRAINTS` | 已覆盖 | 约束解释与代码实现 |
| `PERFORMANCE` | 已覆盖 | 压力测试与容量评估 |
| `ROLE_PERMISSIONS` | 已覆盖 | 角色权限隔离 |
| `REPORT_EXPORT` | 已覆盖 | 演示报告导出 |
| `ACCURACY_FLOW` | 已覆盖 | 上游数据到求解结果准确性链路 |

## 用例结果

| 用例 | 名称 | 状态 | 断言 | 耗时 ms | 失败信息 |
|---|---|---:|---:|---:|---|
| E2E01 | 页面导航与订单明细抽样展示 | PASS | 3 | 1630.9 | - |
| E2E02 | 上游业务表页面编辑保存回读 | PASS | 1 | 7201.46 | - |
| E2E03 | 场景配置传递到模型入参并高亮 | PASS | 2 | 7368.0 | - |
| E2E04 | 求解流水线进度与成本结构可视化 | PASS | 1 | 10027.32 | - |
| E2E05 | 审批通过与执行发布闭环 | PASS | 0 | 12570.82 | - |
| E2E06 | 运行历史报告与回放 | PASS | 0 | 5577.64 | - |
| E2E07 | 数据血缘与约束解释页面导航 | PASS | 0 | 422.09 | - |
| E2E08 | 压力测试与容量评估页面 | PASS | 0 | 10143.17 | - |
| E2E09 | 上游数据二级页面覆盖 | PASS | 1 | 1018.84 | - |
| E2E10 | 场景配置保存审计与权限 | PASS | 1 | 1058.12 | - |
| E2E11 | 四模型入参导航与重新生成 | PASS | 1 | 3162.17 | - |
| E2E12 | 结果页面板、三方案对比与报告导出 | PASS | 0 | 6569.8 | - |
| E2E13 | 角色权限隔离页面校验 | PASS | 0 | 319.78 | - |
| E2E14 | 审批驳回路径与发布拦截 | PASS | 0 | 8084.99 | - |
| E2E15 | 血缘多视图与四模型约束覆盖 | PASS | 1 | 544.02 | - |
| E2E16 | 上游到结果四步准确性链路 | PASS | 4 | 11429.97 | - |

## 证据

### E2E01 页面导航与订单明细抽样展示

```json
{
  "order_status": "抽样 1,000 / 总量 1,000,000",
  "rendered_rows": 1000,
  "first_order": "ORD-0000001\tCanada\tmarketplace\t8\tstandard\t5\t44.44"
}
```

### E2E02 上游业务表页面编辑保存回读

```json
{
  "original_demand": 1801.0,
  "changed_demand": 1802.0,
  "reloaded_demand": 1802.0
}
```

### E2E03 场景配置传递到模型入参并高亮

```json
{
  "changed_rows": 3,
  "input_excerpt": "model_name\tcross_border_ecommerce_network\t实际调用的仓网优化模型\t-\nwarehouses\t4\t候选仓库数量\t-\nmarkets\t5\t目标市场数量\t-\ntotal_demand\t20471\t进入模型的总订单需求\t需求倍率: 1 -> 1.15\ntotal_capacity\t36500\t候选仓库基础总容量\t-\nweather_impacted_lanes\t20\t受天气影响的线路数\t天气风险影响线路成本与时效\nweather_blocked_lanes\t3\t天气延误后不满足 SLA 的线路\t天气延误进入 SLA 可用性判断\nallowed_lanes\t8\t满足 SLA、允许分配的仓库-市场线路\t-\nblocked_lanes\t12\t因配送时效超过 SLA 被禁止的线路\t-"
}
```

### E2E04 求解流水线进度与成本结构可视化

```json
{
  "current": "基准运营方案",
  "total_cost": "319,605.26",
  "cost_cards": 4
}
```

### E2E05 审批通过与执行发布闭环

```json
{
  "approval_status": "当前运行记录：c458edd1，已批准，当前角色：管理员",
  "publish_status": "已发布：EXEC-20260831-c458edd1-9cae25，下游目标 4 个"
}
```

### E2E06 运行历史报告与回放

```json
{
  "history_rows": 20,
  "run_id": "166870a8",
  "audit_status_after_submit": "已提交",
  "replay_status": "已回放运行记录 166870a8，未新增运行记录。"
}
```

### E2E07 数据血缘与约束解释页面导航

```json
{
  "lineage_flows": 4,
  "constraint_models": 4
}
```

### E2E08 压力测试与容量评估页面

```json
{
  "capacity_status": "已完成",
  "throughput_rows": 4
}
```

### E2E09 上游数据二级页面覆盖

```json
{
  "数据源": {
    "status": "StarRocks",
    "rows": 21
  },
  "质量校验": {
    "status": "可运行",
    "rows": 7
  },
  "异常隔离": {
    "status": "需复核",
    "rows": 4
  },
  "天气风险": {
    "status": "20 条影响",
    "rows": 20
  },
  "规模吞吐": {
    "status": "可承载",
    "rows": 4
  }
}
```

### E2E10 场景配置保存审计与权限

```json
{
  "playbook_count": 3,
  "config_status": "已加载：starrocks://127.0.0.1:9030/cplex_poc.platform_playbooks",
  "audit_first_row": "2026/8/31 13:03:19\tpeak\tplatform_ui\tunfulfilled_penalty: 80 -> 75",
  "viewer_save_disabled": true
}
```

### E2E11 四模型入参导航与重新生成

```json
{
  "仓网选址与履约": "model_name\tcross_border_ecommerce_network\t实际调用的仓网优化模型\t-\nwarehouses\t4\t候选仓库数量\t-\nmarkets\t5\t目标市场数量\t-\ntotal_demand\t17801\t进入模型的总订单需求\t-\ntotal_capacity\t36500\t候选仓库基础总容量\t-\nweather_impacted_lanes\t20\t受天气影响的线路数\t天气风险影响线路成本与时效\nweather_blocked_lanes\t3\t天气延误后不满足 SLA 的线路\t天气延误进入 SLA 可用性判断\nallowed_lanes\t8\t满足 SLA、允许分配的仓库",
  "补货计划": "model_name\tcross_border_ecommerce_replenishment\t实际调用的补货优化模型\t-\nweeks\tW1, W2, W3, W4\t计划周期\t-\nlanes\tair, ocean\t可选补货运输方式\t-\ntotal_demand\t4900\t四周预测需求\t-\ninitial_inventory\t1200\t期初可用库存\t-\ntarget_ending_inventory\t800\t期末目标库存\t-\nair.weekly_capacity\t900\t空运每周可用运力\t-\nocean.lead_time_weeks\t3\t海运提前期\t-\nstockout_penalty\t50",
  "服务水平组合": "model_name\tcross_border_ecommerce_service_level\t实际调用的服务水平组合模型\t-\nmarkets\t4\t需要满足平均时效的市场数量\t-\nservices\tcross_border_economy, cross_border_express, local_standard\t可选配送服务\t-\ntotal_demand\t16000\t服务组合模型订单需求\t-\ntotal_service_capacity\t23500\t服务商总处理能力\t-",
  "人员排班": "model_name\tstaff_scheduling\t实际调用的排班模型\t-\nemployees\tAlice, Bob, Carol, David\t可排班员工集合\t-\ndays\tMon, Tue, Wed, Thu, Fri, Sat, Sun\t排班周期\t-\ntotal_required_staff\t14\t总人班需求\t-\nmax_shifts_per_employee\t5\t每人最多班次数\t-\nsoft_constraints\tfalse\t是否允许缺口并用罚分兜底\t-"
}
```

### E2E12 结果页面板、三方案对比与报告导出

```json
{
  "compare_rows": 10,
  "export_status": "已导出：python/reports/platform_report_20260831_142637_baseline.md",
  "enterprise_excerpt": "\n        \n          演示可上线\n          无上线阻塞项\n          评分 100\n        \n        \n          \n            领域状态证据负责人下一步\n          \n          \n            \n              \n                数据接入\n                达标\n                StarRocks / 订单 1,000,000 行 / 源表 21 张\n                数据平台\n                保持 OMS"
}
```

### E2E13 角色权限隔离页面校验

```json
{
  "viewer_run_disabled": true,
  "viewer_export_disabled": true,
  "viewer_publish_disabled": true,
  "viewer_upstream_save_disabled": true,
  "data_admin_upstream_save_enabled": true
}
```

### E2E14 审批驳回路径与发布拦截

```json
{
  "run_id": "417662e0",
  "approval_status": "当前运行记录：417662e0，已驳回，当前角色：管理员",
  "publish_disabled_after_reject": true
}
```

### E2E15 血缘多视图与四模型约束覆盖

```json
{
  "可视化流程": 4,
  "节点总览": 5,
  "转换规则": 6,
  "字段映射": 10,
  "constraint_1": "仓网选址与履约模型",
  "constraint_2": "跨境补货模型",
  "constraint_3": "服务水平组合模型",
  "constraint_4": "门店/仓内排班模型"
}
```

### E2E16 上游到结果四步准确性链路

```json
{
  "step_1_upstream": {
    "market_demands": [
      1801.0,
      3600.0,
      2400.0,
      4800.0,
      5200.0
    ],
    "upstream_total_demand": 17801.0,
    "weather_lane_count": 20
  },
  "step_2_config": {
    "playbook": "baseline",
    "demand_multiplier": 1.12,
    "air_capacity": 980,
    "unfulfilled_penalty": 80,
    "sla_extra_days": 1
  },
  "step_3_model_inputs": {
    "expected_total_demand": 19937,
    "actual_total_demand": 19937.0,
    "actual_weather_lanes": 20.0
  },
  "step_4_result": {
    "total_cost": 331775.66,
    "cost_parts": [
      163589.52,
      37088.0,
      1765.0,
      129333.14
    ],
    "cost_parts_sum": 331775.66
  }
}
```
