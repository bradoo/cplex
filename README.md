# CPLEX / DOcplex 业务优化项目作品集

这是一个基于 **IBM CPLEX / DOcplex** 的业务优化学习与作品集项目，展示如何把排班、仓网、补货、物流、促销等复杂业务决策，转成变量、目标和约束，并落地为可运行的 Web 模拟器、API 服务、文档讲义和管理层汇报材料。

> 英文版说明见 [docs/README.en.md](docs/README.en.md)

---

## 项目亮点

- 覆盖从基础数学优化到业务系统的完整学习路径。
- 包含员工排班 Web/API 系统，支持软约束、偏好、多目标和结果解释。
- 包含跨境电商库存与物流模拟器，覆盖 35 个仓网、补货、物流和经营优化场景。
- 练习了无解诊断、罚分权重、敏感性分析、候选方案比较、稳健优化和模型版本管理。
- 提供经理汇报 PPT、10 页核心总结、讲课版文档和上午复习笔记。
- 包含自动化测试、API 示例、CSV/JSON 报表和工程化演示。

---

## 快速体验

准备环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
```

优先体验跨境电商模拟器：

```bash
cd python
python cross_border_ecommerce_app.py
```

打开：

```text
http://127.0.0.1:5052
```

推荐演示路径：

```text
1. 旺季缺口分析
2. 旺季临时扩容
3. 跨仓库存调拨
4. 供应商评分体系
5. 订单波次排程
6. 经营看板汇总
```

如果下午要给经理做一页式平台 POC，启动：

```bash
cd python
python platform_app.py
```

打开：

```text
http://127.0.0.1:5053
```

平台 POC 拆成五个流程页：

```text
http://127.0.0.1:5053/upstream  上游数据接入层
http://127.0.0.1:5053/config    场景配置层
http://127.0.0.1:5053/inputs    CPLEX 模型入参层
http://127.0.0.1:5053/results   求解结果层
http://127.0.0.1:5053/lineage   数据血缘与字段映射
http://127.0.0.1:5053/constraints 模型约束解释
```

推荐演示路径：

```text
1. 上游数据：解释 OMS/WMS/TMS/HR 数据如何接入，并做数据质量校验
2. 场景配置：选择基准、旺季或稳健方案
3. 模型入参：展示进入 CPLEX 的仓网、补货、服务和排班数据，并高亮受场景参数影响的入参
4. 求解结果：用决策闭环状态和三方案差异矩阵解释 KPI、行动建议、审批分层和方案差异，保存/回放运行记录，并一键导出演示报告
5. 数据血缘：用按模型分组的可视化泳道图展示来源、场景参数、转换函数、CPLEX 入参、求解器和结果字段
6. 约束解释：用业务语言解释每个模型的变量、目标函数、核心约束和输出字段
```

POC 的方案配置来自 `python/data/platform_poc_data.json`，上游业务数据来自 `python/data/platform_upstream_data.json`。页面会同时展示上游原始数据、场景参数和 CPLEX 模型运行入参；上游数据和场景配置都可以在页面中编辑并保存，便于讲清“业务数据进入优化模型”的链路。
四个页面共享同一份浏览器运行上下文，在场景配置页调整的临时参数会带到模型入参页和求解结果页。

---

## 可运行应用

| 应用 | 启动命令 | 地址 | 说明 |
|---|---|---|---|
| 排班优化系统 | `python scheduling_app.py` | `http://127.0.0.1:5050` | 员工排班优化、软约束兜底、JSON API |
| BMI 优化示例 | `python bmi_app.py` | `http://127.0.0.1:5051` | BMI、热量摄入和运动量优化 |
| 跨境电商模拟器 | `python cross_border_ecommerce_app.py` | `http://127.0.0.1:5052` | 35 个库存、物流和经营优化场景 |
| 优化平台 POC | `python platform_app.py` | `http://127.0.0.1:5053` | 汇总排班、仓网、补货和管理指标的一页式演示台 |

Python 示例默认从 `python/` 目录运行：

```bash
cd python
python knapsack_docplex.py
python scheduling_scenarios_demo.py
```

---

## 核心业务场景

### 基础数学优化

| 脚本 | 主题 | 关键概念 |
|---|---|---|
| `knapsack_docplex.py` | 背包问题 | 0/1 变量、最大化目标、容量约束 |
| `transportation_docplex.py` | 运输问题 | 连续变量、供应/需求约束 |
| `facility_location_docplex.py` | 仓库选址 | 0/1+连续混合、开仓固定成本、关联约束 |
| `bmi_calorie_optimizer_demo.py` | BMI / 热量 / 运动优化 | 连续变量、健康边界、目标体重 |

### 员工排班优化

| 能力 | 对应内容 |
|---|---|
| 基础排班 | 覆盖需求、员工可用性、最大班次 |
| 软约束兜底 | 硬约束无解时输出最小缺口方案 |
| 多目标优化 | 公平性、员工偏好、成本和技能覆盖 |
| 工程化 | Flask 页面、REST API、CSV 输入、报表导出 |
| 质量保障 | 自动化测试、性能基准、实验记录 |

### 跨境电商优化模拟器

| 场景组 | 覆盖内容 |
|---|---|
| 仓网与履约 | 严格 SLA、旺季缺口、临时扩容、库存前置、新市场进入、天气风险、利润优先分配 |
| 补货与库存 | 补货情景、供应商采购、供应商评分、现金流、整柜拼箱空运、跨仓调拨、安全库存、稳健库存 |
| 物流路径与服务 | Landed Cost、关税、百分比 SLA、SLA 敏感性、绿色物流、多目标、韧性、包装、渠道分配 |
| 经营动作 | 退货、再销售、多平台库存、广告库存、客服排班、订单波次、促销、清仓、罚分敏感性、看板 |

---

## 技术栈

| 类别 | 技术 |
|---|---|
| 优化建模 | IBM CPLEX、DOcplex、MILP/MIP、CP Optimizer / OPL 示例 |
| 后端服务 | Python、Flask、JSON API |
| 前端展示 | HTML、CSS、JavaScript、可视化图表 |
| 数据与报表 | CSV、JSON、JSONL、Markdown、PowerPoint |
| 工程质量 | 自动化测试、实验记录、性能基准、Git 版本管理 |

---

## 文档与汇报材料

| 文档 | 用途 |
|---|---|
| [docs/cplex_learning_manager_share.pptx](docs/cplex_learning_manager_share.pptx) | 给经理分享学习成果的 10 页 PPT |
| [docs/cplex_core_learning_10_slides.md](docs/cplex_core_learning_10_slides.md) | CPLEX 核心学习内容 10 页 Markdown 版 |
| [docs/cplex_intro_slides.md](docs/cplex_intro_slides.md) | 入门到业务优化的完整分享课件 |
| [docs/manager_demo.md](docs/manager_demo.md) | 面向经理的现场演示脚本 |
| [docs/cplex_morning_review.md](docs/cplex_morning_review.md) | CPLEX 项目落地方法论复习笔记 |
| [docs/cplex_afternoon_review.md](docs/cplex_afternoon_review.md) | CPLEX 业务上线、平台化和作品集复习笔记 |
| [docs/cross_border_ecommerce_simulator.md](docs/cross_border_ecommerce_simulator.md) | 跨境电商模拟器说明，按页面实际菜单同步 35 个场景 |
| [docs/cross_border_ecommerce_lessons.md](docs/cross_border_ecommerce_lessons.md) | 跨境电商 35 个场景讲课版讲义 |
| [docs/scheduling_api.md](docs/scheduling_api.md) | 排班 REST API 接口文档 |
| [docs/README.en.md](docs/README.en.md) | 英文版项目说明 |

---

## 仓库结构

```text
cplex/
├── README.md
├── docs/
│   ├── cplex_learning_manager_share.pptx
│   ├── cplex_core_learning_10_slides.md
│   ├── cplex_intro_slides.md
│   ├── cplex_morning_review.md
│   ├── cplex_afternoon_review.md
│   ├── cross_border_ecommerce_simulator.md
│   ├── cross_border_ecommerce_lessons.md
│   ├── manager_demo.md
│   └── scheduling_api.md
├── opl/
│   ├── pmedian_quickstart/
│   ├── staff_scheduling_quickstart/
│   ├── staff_scheduling_cost/
│   ├── staff_scheduling_soft_constraints/
│   ├── cp_optimizer_quickstart/
│   └── debugging_quickstart/
└── python/
    ├── requirements.txt
    ├── run_tests.py
    ├── scheduling_solver.py
    ├── scheduling_app.py
    ├── platform_app.py
    ├── cross_border_ecommerce_app.py
    ├── cross_border_ecommerce_*_demo.py
    ├── scheduling_*_demo.py
    ├── data/
    │   ├── platform_poc_data.json
    │   ├── platform_upstream_data.json
    ├── reports/
    ├── templates/
    └── tests/
```

---

## 学习路线

**第一阶段 · 数学优化基础**

1. `knapsack_docplex.py`：背包问题，理解 0/1 决策。
2. `transportation_docplex.py`：运输问题，理解连续变量和供需平衡。
3. `facility_location_docplex.py`：仓库选址，理解固定成本和关联约束。
4. `bmi_calorie_optimizer_demo.py`：用连续变量表达健康目标。

**第二阶段 · 排班建模**

5. `scheduling_docplex.py`：最基础排班模型。
6. `scheduling_from_csv.py`：从 CSV 读取业务数据，硬约束无解时切换软约束。
7. `scheduling_parameters_demo.py`：求解参数 `time_limit` 和 `mip_gap`。
8. `scheduling_multi_objective_demo.py`：公平性和员工偏好。
9. `scheduling_skills_demo.py`：技能覆盖。
10. `scheduling_cost_demo.py`：成本优化。

**第三阶段 · 软约束、诊断和工程化**

11. `scheduling_conflict_diagnosis_demo.py`：无解诊断。
12. `scheduling_soft_constraints_demo.py`：人数和技能缺口软约束。
13. `scheduling_penalty_weights_demo.py`：罚分权重取舍。
14. `scheduling_two_stage_demo.py`：两阶段求解。
15. `scheduling_manual_overrides_demo.py`：人工干预。
16. `scheduling_alternatives_demo.py`：候选方案对比。
17. `scheduling_scenarios_demo.py`：批量情景分析。
18. `scheduling_explain_demo.py`：自动解释结果。
19. `scheduling_experiment_log_demo.py`：实验记录。
20. `scheduling_benchmark_demo.py`：性能基准。
21. `scheduling_app.py`：REST API 和 Web 页面。

**第四阶段 · CPLEX Studio / OPL**

- `opl/pmedian_quickstart/`：P-Median 仓库分配模型。
- `opl/staff_scheduling_quickstart/`：CPLEX Studio 最小排班模型。
- `opl/staff_scheduling_cost/`：排班成本目标。
- `opl/staff_scheduling_soft_constraints/`：软约束建模。
- `opl/cp_optimizer_quickstart/`：使用 `using CP;` 切换到 CP Optimizer。
- `opl/debugging_quickstart/`：语法错误、数据错误和无解错误排查。

**第五阶段 · 跨境电商业务优化**

22. `cross_border_ecommerce_app.py`：跨境电商模拟器。
23. 仓网与履约：SLA、扩容、天气风险、新市场进入。
24. 补货与库存：供应商、现金流、调拨、安全库存、稳健库存。
25. 物流路径与服务：DDU/DDP、Landed Cost、关税、碳排、韧性。
26. 经营动作：退货、广告、促销、清仓、客服、订单波次和经营看板。

---

## 自动化测试

```bash
cd python
python run_tests.py
```

覆盖范围：

- 默认排班求解。
- 软约束缺口场景。
- API 健康检查与求解接口。
- API 请求校验。
- 情景分析报表导出。

---

## 能力总结

通过这个项目，系统练习了：

- 把业务问题抽象成变量、目标和约束。
- 用 CPLEX / DOcplex 构建 LP、MIP/MILP 和排班优化模型。
- 处理无解、软约束、罚分权重、多目标和敏感性分析。
- 将模型包装成 API 和 Web 模拟器。
- 用图表、指标、行动清单和解释理由呈现优化结果。
- 从 ROI、试点、审批、人工干预和复盘角度思考优化项目落地。

一句话总结：

```text
CPLEX 的价值不是替人拍脑袋，而是让业务决策在约束清楚、目标清楚、取舍清楚的基础上变得可计算。
```

---

## CPLEX vs Gurobi

CPLEX 和 Gurobi 是同一类商业数学优化求解器。

| 对比项 | CPLEX | Gurobi |
|---|---|---|
| 公司 | IBM | Gurobi Optimization |
| 主要定位 | IBM Optimization Studio 生态中的求解器 | 专注优化 API 和求解器本体 |
| 常见模型 | LP、MILP/MIP、QP、QCP，也可用 CP Optimizer 做 CP | LP、MILP/MIP、QP、QCP 等 |
| Python 写法 | `docplex` 或底层 `cplex` API | `gurobipy` API |
| 排班场景 | 可用 MILP，也可用 CP Optimizer 处理复杂排程 | 通常用 MILP/MIQP 建模 |
| 学习迁移 | 变量、目标、约束、软约束、MIP Gap 都能迁移到 Gurobi | 同样的建模思想也能迁移回 CPLEX |

关键结论：CPLEX 和 Gurobi 的差别主要在 API、授权、生态和性能细节；真正重要的是**建模能力**。
