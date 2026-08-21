# CPLEX / DOcplex 学习笔记

这个仓库是一组 **CPLEX / DOcplex** 入门到进阶的可运行示例，围绕「数学优化建模」和「员工排班系统」两条主线，配套课件、汇报脚本、REST API 和自动化测试，适合自学和团队分享。

> 英文版说明见 [docs/README.en.md](docs/README.en.md)

---

## 目录

- [环境准备](#环境准备)
- [仓库结构](#仓库结构)
- [学习路线](#学习路线)
- [文档与课件](#文档与课件)
- [示例速查表](#示例速查表)
- [自动化测试](#自动化测试)
- [CPLEX vs Gurobi](#cplex-vs-gurobi)

---

## 环境准备

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
```

> Python 示例默认从 `python/` 目录运行（`data/` 与 `reports/` 使用相对路径）。

---

## 仓库结构

```text
cplex/
├── README.md                     # 本文件：入口与索引
│
├── docs/                         # 文档与课件
│   ├── README.en.md              # 英文版说明
│   ├── cplex_intro_slides.md     # 分享用课件
│   ├── manager_demo.md           # 经理汇报脚本
│   └── scheduling_api.md         # 排班 REST API 文档
│
├── opl/                          # CPLEX Studio / OPL 示例
└── python/                       # Python / DOcplex 示例与相关文件
    ├── requirements.txt          # 依赖：docplex / cplex / flask
    ├── run_tests.py              # 一键运行全部测试
    ├── scheduling_solver.py      # 核心排班求解器
    ├── scheduling_app.py         # Flask 交互式排班服务 + API
    ├── data/                     # 示例业务数据
    ├── reports/                  # 示例输出
    ├── templates/                # Flask 页面模板
    └── tests/                    # 回归测试
```

经典优化示例与排班示例都在 `python/` 目录，命名统一以 `*_docplex.py` / `scheduling_*_demo.py` 区分，详见下方[示例速查表](#示例速查表)。

---

## 学习路线

建议按下面顺序循序渐进：

**第一阶段 · 数学优化基础**（理解「变量 / 目标 / 约束」三要素）

1. `knapsack_docplex.py` — 背包问题（0/1 变量 + 最大化价值）
2. `transportation_docplex.py` — 运输问题（连续变量 + 供需平衡）
3. `facility_location_docplex.py` — 仓库选址（0/1 + 连续混合，关联约束）

**第二阶段 · 排班建模入门**

4. `scheduling_docplex.py` — 最基础排班模型
5. `scheduling_from_csv.py` — 从 CSV 读业务数据；硬约束无解自动切软约束
6. `scheduling_parameters_demo.py` — 求解参数（`time_limit` / `mip_gap`）

**CPLEX Studio / OPL 入门**

- `opl/pmedian_quickstart/` — 官方 Quick Start 风格的 P-Median 仓库分配模型
- `opl/staff_scheduling_quickstart/` — CPLEX Studio 里的最小排班模型
- `opl/staff_scheduling_quickstart/baseline.dat` 与 `weekend_peak.dat` — 同一模型切换不同数据场景
- 建议在 Studio 中全部使用英文项目名、英文文件名、英文 Run Configuration 名

**第三阶段 · 多目标与业务规则**

7. `scheduling_multi_objective_demo.py` — 公平性 + 员工偏好
8. `scheduling_consecutive_demo.py` — 最多连续上班 N 天
9. `scheduling_skills_demo.py` — 技能覆盖（如每天至少 1 名 senior）
10. `scheduling_cost_demo.py` — 加入排班成本优化

**第四阶段 · 软约束、诊断与取舍**

11. `scheduling_conflict_diagnosis_demo.py` — 无解时定位冲突来源
12. `scheduling_soft_constraints_demo.py` — 人数缺口 + 技能缺口量化
13. `scheduling_penalty_weights_demo.py` — 罚分权重如何改变模型取舍
14. `scheduling_two_stage_demo.py` — 两阶段求解：先保覆盖、再优化偏好
15. `scheduling_manual_overrides_demo.py` — 人工干预：锁定上班 / 禁止上班

**第五阶段 · 工程化（情景 / 解释 / 实验 / 基准 / API）**

16. `scheduling_alternatives_demo.py` — 生成多个候选排班方案并对比指标
17. `scheduling_scenarios_demo.py` — 批量情景分析 + 报表导出
18. `scheduling_explain_demo.py` — 自动解释排班结果
19. `scheduling_experiment_log_demo.py` — 记录每次实验配置与指标
20. `scheduling_benchmark_demo.py` — 不同规模的性能基准
21. `scheduling_app.py` + `scheduling_api_client_demo.py` — REST API 化部署

---

## 文档与课件

| 文档 | 用途 |
|---|---|
| [docs/cplex_intro_slides.md](docs/cplex_intro_slides.md) | 复习与分享用课件 |
| [docs/manager_demo.md](docs/manager_demo.md) | 面向经理的汇报脚本 |
| [docs/scheduling_api.md](docs/scheduling_api.md) | 排班 REST API 接口文档 |
| [docs/README.en.md](docs/README.en.md) | 英文版说明 |

---

## 示例速查表

### 经典数学优化

| 脚本 | 主题 | 关键概念 |
|---|---|---|
| `knapsack_docplex.py` | 背包问题 | 0/1 变量、最大化目标、容量约束 |
| `transportation_docplex.py` | 运输问题 | 连续变量、供应/需求约束 |
| `facility_location_docplex.py` | 仓库选址 | 0/1+连续混合、开仓固定成本、关联约束 |

### 排班系统（核心：`scheduling_solver.py`）

| 脚本 | 主题 | 产出 |
|---|---|---|
| `scheduling_docplex.py` | 基础排班 | — |
| `scheduling_from_csv.py` | 读 CSV / 软约束兜底 | — |
| `scheduling_parameters_demo.py` | 求解参数 | — |
| `scheduling_multi_objective_demo.py` | 公平性 + 偏好 | — |
| `scheduling_consecutive_demo.py` | 连续上班限制 | — |
| `scheduling_skills_demo.py` | 技能覆盖约束 | — |
| `scheduling_cost_demo.py` | 成本优化 | — |
| `scheduling_conflict_diagnosis_demo.py` | 冲突诊断 | — |
| `scheduling_soft_constraints_demo.py` | 软约束进阶 | — |
| `scheduling_penalty_weights_demo.py` | 罚分权重取舍 | — |
| `scheduling_two_stage_demo.py` | 两阶段求解（先覆盖后偏好） | — |
| `scheduling_manual_overrides_demo.py` | 人工干预（锁定 / 禁止班次） | — |
| `scheduling_alternatives_demo.py` | 候选方案对比 | — |
| `scheduling_scenarios_demo.py` | 批量情景分析 | `reports/scenario_*.{csv,json}` |
| `scheduling_explain_demo.py` | 结果自动解释 | `reports/baseline_explanation.md` |
| `scheduling_experiment_log_demo.py` | 实验记录 | `reports/experiments.jsonl` / `_summary.csv` |
| `scheduling_benchmark_demo.py` | 性能基准 | `reports/benchmark_results.csv` |

### 部署与展示

| 脚本 / 文件 | 说明 |
|---|---|
| `scheduling_app.py` | Flask 服务，`http://127.0.0.1:5050`，含交互模拟器与 JSON API |
| `scheduling_api_client_demo.py` | 调用 `/api/health`、`/api/problem`、`/api/solve` 的 Python 客户端 |
| `scheduling_solution.html` | 静态排班展示页（浏览器直接打开） |

运行任意脚本：

```bash
cd python
python <脚本名>.py
# 例如
python knapsack_docplex.py
python scheduling_scenarios_demo.py
```

一个更紧张的需求场景（硬约束无解会自动切换软约束兜底）：

```bash
cd python
python scheduling_from_csv.py --employees data/employees_limited.csv --demand data/demand_hard.csv
```

---

## 自动化测试

```bash
cd python
python run_tests.py
```

覆盖范围：

- 默认排班求解
- 软约束缺口场景
- API 健康检查与求解接口
- API 请求校验
- 情景分析报表导出

---

## 排班模型学到的内容

- **0/1 决策变量**：`work_employee_day = 1` 表示某员工某天上班
- **覆盖约束**：每天必须有足够员工
- **可用性约束**：员工只能在可用日期上班
- **工作量约束**：每人有最大班次数
- **公平性目标**：最忙与最闲员工的班次差距尽量小
- **CSV 数据读取**：从业务表格读取员工、需求、可用性
- **求解参数**：`time_limit` 与 `mip_gap`，更贴近生产
- **多目标建模**：公平性之外平衡员工偏好
- **情景分析**：批量运行多个业务场景并对比
- **结果导出 / 解释**：写入 CSV/JSON，并自动说明排班理由
- **API 化部署**：通过 JSON API 提供求解能力
- **自动化测试**：回归测试防止后续改动破坏模型/API/报表
- **性能基准**：对比不同规模下的变量数、求解时间与质量
- **规则扩展**：最多连续上班天数等真实约束
- **技能覆盖 / 成本优化 / 软约束 / 罚分权重**：更贴近真实业务的取舍
- **人工干预**：支持经理锁定或禁止某些班次，再由模型重排剩余安排
- **候选方案对比**：同一问题生成多套排班，比较缺口、公平性、偏好和成本

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
