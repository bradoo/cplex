# CPLEX 学习汇报演示脚本

目标：不用 PPT，直接展示可以运行的代码和本地 Web 系统。

## 1. 启动系统

```bash
cd ~/cplex
source .venv/bin/activate
python scheduling_app.py
```

打开：

```text
http://127.0.0.1:5050
```

## 2. 演示默认可行排班

展示点：

- 每天需要人数是输入条件。
- 员工可用性是约束条件。
- 每人最多班次数是工作量约束。
- CPLEX 输出满足全部约束的最优排班。

默认结果：

```text
总班次数: 14
公平性差距: 1
最多工作量: 4
最少工作量: 3
需求缺口: 0
```

## 3. 演示交互修改

现场可以做一个小改动：

- 把某天需要人数从 2 改成 3
- 或把某个员工某天可用性从可用改成不可用
- 点击“重新求解”

讲解点：

```text
业务条件变化后，不需要手工重新排班，模型会重新计算最优方案。
```

## 4. 演示无解诊断

点击：

```text
无解演示
```

这个场景故意提高周末需求，同时降低每人最多班次数。

展示点：

```text
当需求、可用性、最大班次数互相冲突时，硬约束模型会明确返回无可行解。
```

## 5. 演示软约束兜底

在无解场景下点击：

```text
软约束兜底
```

展示点：

- 系统允许需求有缺口，但给缺口很高罚分。
- CPLEX 会优先把缺口降到最少。
- 页面显示每天缺几个人。

讲解话术：

```text
真实业务里，有时候规则太硬会导致完全无解。
软约束的作用不是假装问题解决了，而是给出最小损失方案，并明确告诉业务方缺口在哪里。
```

## 6. 演示求解参数

在页面左侧可以调整：

```text
时间限制秒
MIP Gap
```

也可以点击：

```text
快速
平衡
精确
```

讲解点：

```text
真实生产系统不一定永远追求数学上的完全最优。
有时业务需要在限定时间内拿到足够好的方案。
time limit 控制最多算多久，MIP gap 控制可以接受的最优性误差。
```

命令行演示：

```bash
python scheduling_parameters_demo.py
```

## 7. 演示多目标优化

页面左侧可以调整：

```text
偏好权重
员工偏好矩阵
```

页面右侧会显示：

```text
偏好命中
```

讲解点：

```text
真实排班不只追求公平，还要考虑员工偏好、业务缺口和求解时间。
这里用偏好权重把“尽量排到员工愿意上的日期”加入目标函数。
```

命令行演示：

```bash
python scheduling_multi_objective_demo.py
```

## 8. CPLEX 和 Gurobi 的关系

讲解点：

```text
CPLEX 和 Gurobi 是同一类产品，都是商业级数学优化求解器。
我们现在学的是 CPLEX，但真正沉淀的是建模能力：
变量、目标函数、约束、软约束、MIP Gap、多目标优化。
这些思想换到 Gurobi 也基本一样。
```

简短对比：

| 对比项 | CPLEX | Gurobi |
|---|---|---|
| 公司 | IBM | Gurobi Optimization |
| Python API | docplex / cplex | gurobipy |
| 常见模型 | LP, MIP, QP, QCP, CP | LP, MIP, QP, QCP |
| 排班能力 | MILP + CP Optimizer | 主要用 MILP/MIQP |
| 核心差异 | IBM 生态、OPL、CP Optimizer | API 简洁、MIP 性能口碑强 |

一句话：

```text
CPLEX 和 Gurobi 像两个不同品牌的优化引擎；学会建模后，迁移成本主要是 API 写法。
```

## 9. 演示批量情景分析

命令行演示：

```bash
python scheduling_scenarios_demo.py
```

展示点：

```text
同一个模型可以批量跑多组业务假设：
基准场景、周五高峰、每人最多 4 班、周末高峰、偏好优先。
输出表会对比可行性、缺口、公平性、偏好命中和求解时间。
```

讲解话术：

```text
优化系统不只是给一个答案，更适合回答“如果条件变化会怎样”。
这类 what-if 分析可以帮助经理在不同业务方案之间做选择。
```

## 10. 演示结果导出

运行：

```bash
python scheduling_scenarios_demo.py
```

会生成：

```text
reports/scenario_summary.csv
reports/scenario_schedule.csv
reports/scenario_results.json
```

讲解点：

```text
优化系统最终通常要把结果交给业务方或下游系统。
CSV 适合给人看，JSON 适合系统集成。
这一步把“模型求解”变成了可以落地流转的业务报表。
```

## 11. 演示结果解释

运行：

```bash
python scheduling_explain_demo.py
```

会生成：

```text
reports/baseline_explanation.md
```

讲解点：

```text
业务方不只想知道排班结果，还会问“为什么这样排”。
解释报告会说明每天需求、实际安排、缺口、员工可用性、偏好命中和工作量。
这能帮助业务方信任优化结果。
```

## 12. 演示 API 化部署

启动服务：

```bash
python scheduling_app.py
```

健康检查：

```bash
curl --noproxy '*' http://127.0.0.1:5050/api/health
```

Python 客户端演示：

```bash
python scheduling_api_client_demo.py
```

讲解点：

```text
排班模型不只可以通过网页使用，也可以作为 JSON API 给其他系统调用。
这一步把 CPLEX 求解器包装成了一个可集成的小服务。
```

API 文档：

```text
scheduling_api.md
```

## 13. 演示自动化测试

运行：

```bash
python run_tests.py
```

讲解点：

```text
优化模型也需要回归测试。
测试可以验证默认求解、软约束兜底、API 请求校验和报表导出是否正常。
这样后续继续改模型时，不容易悄悄破坏已有行为。
```

## 14. 演示性能基准测试

运行：

```bash
python scheduling_benchmark_demo.py
```

会生成：

```text
reports/benchmark_results.csv
```

讲解点：

```text
自动化测试回答“结果对不对”，性能基准测试回答“规模变大后快不快”。
这个脚本会生成 small、medium、large、xlarge 四个规模的排班问题，
对比员工数、天数、0/1 变量数量、求解时间和结果质量。
```

## 15. 演示业务规则扩展

运行：

```bash
python scheduling_consecutive_demo.py
```

讲解点：

```text
真实排班经常会增加新的劳动规则，比如不能连续上太多天。
这个示例用滑动窗口约束实现“最多连续上 N 天”，
说明优化模型可以随着业务规则逐步扩展。
```

## 16. 可以打开的代码

核心求解器：

```text
scheduling_solver.py
```

Web 后端：

```text
scheduling_app.py
```

Web 页面：

```text
templates/scheduling_app.html
```

CSV 数据驱动版本：

```text
scheduling_from_csv.py
data/employees.csv
data/demand.csv
data/availability.csv
```

现场命令：

```bash
python scheduling_from_csv.py
python scheduling_from_csv.py --employees data/employees_limited.csv --demand data/demand_hard.csv
```

求解参数演示：

```text
scheduling_parameters_demo.py
```

多目标优化演示：

```text
scheduling_multi_objective_demo.py
```

批量情景分析演示：

```text
scheduling_scenarios_demo.py
```

结果解释演示：

```text
scheduling_explain_demo.py
reports/baseline_explanation.md
```

API 化部署演示：

```text
scheduling_app.py
scheduling_api.md
scheduling_api_client_demo.py
```

自动化测试：

```text
run_tests.py
tests/test_scheduling.py
```

性能基准测试：

```text
scheduling_benchmark_demo.py
reports/benchmark_results.csv
```

业务规则扩展：

```text
scheduling_consecutive_demo.py
scheduling_solver.py
```

前面几节基础模型：

```text
knapsack_docplex.py
transportation_docplex.py
facility_location_docplex.py
scheduling_docplex.py
```
