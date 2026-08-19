# CPLEX 学习笔记

这个目录保存了一组 CPLEX / DOcplex 入门示例，用来学习数学优化建模、排班系统和可运行的汇报 Demo。

英文版已保留在：

```bash
README.en.md
```

## 课件

复习和分享用的课件在：

```bash
cplex_intro_slides.md
```

## 环境准备

创建并激活虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行背包问题示例

```bash
python knapsack_docplex.py
```

## 背包模型含义

- 决策变量：`pick_item = 1` 表示选择该物品，`0` 表示不选择。
- 目标函数：最大化总价值。
- 约束条件：总重量不能超过背包容量。

## 运行运输问题示例

```bash
python transportation_docplex.py
```

## 运输模型含义

- 决策变量：`ship_warehouse_to_customer` 表示从某仓库发给某客户的数量。
- 目标函数：最小化总运输成本。
- 供应约束：每个仓库发出的数量不能超过可用供应量。
- 需求约束：每个客户必须收到指定需求量。

## 运行仓库选址示例

```bash
python facility_location_docplex.py
```

## 仓库选址模型含义

- 0/1 决策变量：`open_facility = 1` 表示开启该仓库。
- 连续决策变量：`ship_facility_to_customer` 表示从仓库发给客户的数量。
- 目标函数：最小化开仓固定成本和运输成本。
- 需求约束：每个客户必须收到指定需求量。
- 关联约束：仓库只有开启后才能发货。

## 运行基础排班示例

```bash
python scheduling_docplex.py
```

## 从 CSV 读取排班数据

```bash
python scheduling_from_csv.py
```

运行一个更紧张的需求场景；硬约束无解时会自动切换到软约束兜底：

```bash
python scheduling_from_csv.py --employees data/employees_limited.csv --demand data/demand_hard.csv
```

## 运行求解参数示例

```bash
python scheduling_parameters_demo.py
```

这个示例展示 `time_limit` 和 `mip_gap` 如何影响 CPLEX 求解。

## 运行多目标排班示例

```bash
python scheduling_multi_objective_demo.py
```

这个示例展示如何在公平性之外加入员工偏好。

## 运行批量情景分析示例

```bash
python scheduling_scenarios_demo.py
```

这个示例会一次性比较多个需求和人员配置场景。

它还会导出报表：

```text
reports/scenario_summary.csv
reports/scenario_schedule.csv
reports/scenario_results.json
```

## 查看静态排班展示页

用浏览器打开：

```bash
scheduling_solution.html
```

## 运行交互式排班模拟器

```bash
python scheduling_app.py
```

然后打开：

```text
http://127.0.0.1:5050
```

经理汇报脚本在：

```bash
manager_demo.md
```

## 排班模型学到的内容

- 0/1 决策变量：`work_employee_day = 1` 表示某员工在某天上班。
- 覆盖约束：每天必须有足够员工。
- 可用性约束：员工只能在可用日期上班。
- 工作量约束：每个员工有最大班次数。
- 公平性目标：最忙员工和最闲员工的班次数差距尽量小。
- CSV 数据读取：从业务表格读取员工、需求和可用性数据。
- 求解参数：设置时间限制和 MIP Gap，更接近生产系统。
- 多目标建模：在公平性之外平衡员工偏好命中。
- 情景分析：批量运行多个业务场景，对比可行性、缺口、公平性和偏好命中。
- 结果导出：将场景汇总和详细排班写入 CSV/JSON。

## CPLEX vs Gurobi

CPLEX 和 Gurobi 是同一类商业数学优化求解器。

| 对比项 | CPLEX | Gurobi |
|---|---|---|
| 公司 | IBM | Gurobi Optimization |
| 主要定位 | IBM Optimization Studio 生态中的数学优化求解器 | 专注优化 API 和求解器本体 |
| 常见模型类型 | LP、MILP/MIP、QP、QCP，也可通过 CP Optimizer 做 CP | LP、MILP/MIP、QP、QCP 等数学规划模型 |
| Python 写法 | `docplex` 或底层 `cplex` API | `gurobipy` API |
| 排班场景 | 可用 MILP，也可用 CP Optimizer 处理复杂排程 | 通常用 MILP/MIQP 方式建模 |
| 学习迁移 | 变量、目标、约束、软约束、MIP Gap 都能迁移到 Gurobi | 同样的建模思想也能迁移回 CPLEX |

关键结论：CPLEX 和 Gurobi 的差别主要在 API、授权、生态和性能细节；真正重要的是建模能力。
