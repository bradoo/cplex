# CPLEX 入门与业务优化分享

从经典模型到排班系统，再到跨境电商模拟器

---

## 这套课学什么

1. 数学优化基础：变量、目标、约束
2. 经典模型：背包、运输、仓库选址
3. 排班系统：覆盖、可用性、公平性、技能和软约束
4. 工程化：CSV、情景分析、解释报告、API、测试
5. 跨境电商：仓网、补货、物流路径和经营动作优化

核心主线：

```text
业务问题 -> 决策变量 -> 目标函数 -> 约束条件 -> CPLEX 求解 -> 解释结果
```

---

## CPLEX 适合解决什么问题

CPLEX 是数学优化求解器。

它不是用来预测“会发生什么”，而是用来计算：

```text
在一组限制条件下，怎样做最好？
```

常见目标：

- 成本最低
- 利润最高
- 时间最短
- 资源利用率最高
- 服务缺口最少

---

## 一个优化模型的基本结构

每个 CPLEX 模型基本都包含三部分：

```python
model = Model(name="example")

# 1. Decision variables
x = model.binary_var(name="x")

# 2. Objective
model.maximize(10 * x)

# 3. Constraints
model.add_constraint(x <= 1)
```

先把业务语言翻译成这三部分，代码就自然了。

---

## 第一课：背包问题

问题：

```text
有一批物品，每个物品有价值和重量。
背包容量有限。
应该选哪些物品，让总价值最大？
```

这是一个典型的 0/1 优化问题。

每个物品只有两种状态：

```text
选：1
不选：0
```

---

## 背包问题的数据

当前代码里的数据：

| 物品 | 价值 | 重量 |
|---|---:|---:|
| laptop | 500 | 3 |
| camera | 350 | 2 |
| headphones | 150 | 1 |
| book | 60 | 2 |
| jacket | 220 | 2 |
| water | 220 | 3 |

背包容量：

```text
capacity = 8
```

---

## 背包问题的决策变量

代码：

```python
x = {
    item["name"]: model.binary_var(name=f"pick_{item['name']}")
    for item in items
}
```

含义：

```text
pick_laptop = 1 表示选择 laptop
pick_laptop = 0 表示不选择 laptop
```

`binary_var` 是 0/1 变量。

---

## 背包问题的目标函数

代码：

```python
model.maximize(
    model.sum(item["value"] * x[item["name"]] for item in items)
)
```

含义：

```text
最大化：所有被选中物品的总价值
```

如果某个物品没选，变量是 0，它的价值就不会计入总价值。

---

## 背包问题的约束

代码：

```python
model.add_constraint(
    model.sum(item["weight"] * x[item["name"]] for item in items) <= capacity,
    ctname="capacity_limit",
)
```

含义：

```text
所有被选中物品的总重量 <= 背包容量
```

这是背包问题最核心的约束。

---

## 背包问题的运行结果

当前最优解：

```text
laptop
camera
headphones
jacket
```

结果：

```text
Total value: 1220
Total weight: 8/8
```

CPLEX 找到的是在容量 8 以内，总价值最高的组合。

---

## 第二课：运输问题

问题：

```text
有几个仓库和几个客户。
每个仓库有供应量。
每个客户有需求量。
不同路线运输成本不同。
应该从哪个仓库给哪个客户发多少货，让总成本最低？
```

这类问题常见于物流、库存调拨、产能分配。

---

## 运输问题的数据

仓库供应：

| 仓库 | 供应量 |
|---|---:|
| Shanghai | 80 |
| Beijing | 60 |

客户需求：

| 客户 | 需求量 |
|---|---:|
| Hangzhou | 50 |
| Shenzhen | 70 |
| Chengdu | 20 |

总供应量 = 总需求量 = 140

---

## 运输问题的决策变量

代码：

```python
x = {
    (w, c): model.continuous_var(name=f"ship_{w}_to_{c}", lb=0)
    for w in warehouses
    for c in customers
}
```

含义：

```text
ship_Shanghai_to_Hangzhou = 从上海仓发给杭州客户的数量
```

`continuous_var` 是连续变量，可以取 0、10、37.5 等数值。

---

## 运输问题的目标函数

代码：

```python
model.minimize(
    model.sum(
        shipping_cost[w, c] * x[w, c]
        for w in warehouses
        for c in customers
    )
)
```

含义：

```text
最小化：所有路线的运输数量 × 单位运输成本
```

这次不是最大化价值，而是最小化成本。

---

## 运输问题的供应约束

代码：

```python
for w, supply in warehouses.items():
    model.add_constraint(
        model.sum(x[w, c] for c in customers) <= supply,
        ctname=f"supply_{w}",
    )
```

含义：

```text
每个仓库发出去的总量 <= 这个仓库的供应量
```

仓库不能发出超过自己库存的货。

---

## 运输问题的需求约束

代码：

```python
for c, demand in customers.items():
    model.add_constraint(
        model.sum(x[w, c] for w in warehouses) == demand,
        ctname=f"demand_{c}",
    )
```

含义：

```text
每个客户收到的总量 = 这个客户的需求量
```

这里用 `==`，说明客户需求必须被完全满足。

---

## 运输问题的运行结果

当前最优解：

```text
Shanghai -> Hangzhou: 50, cost 100
Shanghai -> Shenzhen: 30, cost 180
Beijing -> Shenzhen: 40, cost 160
Beijing -> Chengdu: 20, cost 60
```

总成本：

```text
Total cost: 500
```

---

## `1e-6` 是什么

代码里有：

```python
if amount > 1e-6:
```

`1e-6` 等于：

```text
0.000001
```

用途：

```text
把非常小的浮点误差当作 0，不打印出来
```

---

## 第三课：仓库选址问题

问题：

```text
有多个候选仓库。
开仓库需要固定成本。
仓库有容量。
客户有需求。
不同仓库到客户的运输成本不同。
应该开哪些仓库，并如何发货，让总成本最低？
```

这是一个混合整数规划问题，简称 MILP。

---

## 仓库选址问题为什么更真实

它同时包含两类决策：

```text
1. 是否开某个仓库：0/1 变量
2. 从仓库给客户发多少货：连续变量
```

现实项目里经常是这种组合：

- 开不开门店
- 是否购买设备
- 是否启用路线
- 每条路线分配多少量
- 每个节点承担多少需求

---

## 仓库选址的数据

候选仓库：

| 仓库 | 容量 | 固定成本 |
|---|---:|---:|
| Shanghai | 100 | 420 |
| Beijing | 90 | 380 |
| Wuhan | 80 | 300 |

客户需求：

| 客户 | 需求量 |
|---|---:|
| Hangzhou | 50 |
| Shenzhen | 70 |
| Chengdu | 40 |

---

## 仓库选址的 0/1 变量

代码：

```python
open_facility = {
    f: model.binary_var(name=f"open_{f}")
    for f in facilities
}
```

含义：

```text
open_Beijing = 1 表示开北京仓
open_Beijing = 0 表示不开北京仓
```

这是选址决策。

---

## 仓库选址的连续变量

代码：

```python
ship = {
    (f, c): model.continuous_var(name=f"ship_{f}_to_{c}", lb=0)
    for f in facilities
    for c in customers
}
```

含义：

```text
ship_Beijing_to_Chengdu = 北京仓发给成都客户的数量
```

这是配送决策。

---

## 仓库选址的目标函数

代码：

```python
model.minimize(fixed_cost_total + shipping_cost_total)
```

含义：

```text
最小化：开仓固定成本 + 运输成本
```

这让 CPLEX 在“少开仓”和“运输便宜”之间自动权衡。

---

## 仓库选址的关键约束

代码：

```python
model.sum(ship[f, c] for c in customers) <= data["capacity"] * open_facility[f]
```

这叫 linking constraint。

含义：

```text
如果仓库不开，open_facility[f] = 0
右边就是 0
所以这个仓库不能发货
```

如果仓库开了，发货量最多不能超过容量。

---

## 仓库选址的运行结果

当前最优解：

```text
Open Beijing
Open Wuhan
```

发货方案：

```text
Beijing -> Hangzhou: 40
Beijing -> Chengdu: 40
Wuhan -> Hangzhou: 10
Wuhan -> Shenzhen: 70
```

总成本：

```text
Total fixed cost: 680
Total shipping cost: 570
Total cost: 1250
```

---

## 第四课：排班问题

问题：

```text
一周每天需要一定人数上班。
每个员工有自己的可上班日期。
每个员工最多只能上一些班次。
应该如何安排，让每天人数够用，同时尽量公平？
```

这类问题常见于：

- 客服排班
- 医院护士排班
- 仓库工人排班
- 门店值班

---

## 排班问题的数据

员工：

```text
Alice, Bob, Carol, David
```

日期：

```text
Mon, Tue, Wed, Thu, Fri, Sat, Sun
```

每天需要人数：

| 日期 | 需要人数 |
|---|---:|
| Mon | 2 |
| Tue | 2 |
| Wed | 2 |
| Thu | 2 |
| Fri | 3 |
| Sat | 2 |
| Sun | 1 |

---

## 排班问题的决策变量

代码：

```python
work = {
    (e, d): model.binary_var(name=f"work_{e}_{d}")
    for e in employees
    for d in days
}
```

含义：

```text
work_Alice_Mon = 1 表示 Alice 周一上班
work_Alice_Mon = 0 表示 Alice 周一不上班
```

这是一个典型的 0/1 变量。

---

## 排班问题的覆盖约束

代码：

```python
for d in days:
    model.add_constraint(
        model.sum(work[e, d] for e in employees) >= required_staff[d],
        ctname=f"cover_{d}",
    )
```

含义：

```text
每天安排的人数 >= 当天需要的人数
```

这种约束叫 coverage constraint。

---

## 排班问题的可用性约束

代码：

```python
work[e, d] <= availability[e, d]
```

含义：

```text
如果员工当天不可用，availability[e, d] = 0
那么 work[e, d] 也只能是 0
```

这保证不会把员工排到他不能上班的日期。

---

## 排班问题的工作量约束

代码：

```python
model.sum(work[e, d] for d in days) <= max_shifts_per_employee
```

含义：

```text
每个员工一周最多上 max_shifts_per_employee 个班
```

当前代码里：

```text
max_shifts_per_employee = 5
```

---

## 排班问题的公平性目标

代码里定义了两个辅助变量：

```python
max_workload = model.integer_var(name="max_workload", lb=0)
min_workload = model.integer_var(name="min_workload", lb=0)
```

目标函数：

```python
model.minimize(max_workload - min_workload)
```

含义：

```text
让最忙的人和最闲的人之间的班次数差距尽量小
```

---

## 为什么要固定总班次数

代码：

```python
model.add_constraint(
    model.sum(work[e, d] for e in employees for d in days) == total_required_shifts,
    ctname="total_required_shifts",
)
```

因为覆盖约束用的是 `>=`。

如果不固定总班次数，模型可能为了公平而多排不必要的班。

这个约束告诉 CPLEX：

```text
只排刚好满足需求的班次数
```

---

## 排班问题的运行结果

当前最优解：

```text
Mon: Alice, Bob
Tue: Alice, David
Wed: Bob, Carol
Thu: Alice, David
Fri: Alice, Bob, Carol
Sat: Bob, Carol
Sun: David
```

员工工作量：

```text
Alice: 4 shifts
Bob: 4 shifts
Carol: 3 shifts
David: 3 shifts
```

公平性差距：

```text
Fairness spread: 1
```

---

## 从四个例子扩展到业务系统

| 课程 | 问题类型 | 变量类型 | 目标 |
|---|---|---|---|
| 背包问题 | 选择组合 | 0/1 变量 | 总价值最大 |
| 运输问题 | 数量分配 | 连续变量 | 总成本最低 |
| 仓库选址 | 选择 + 分配 | 0/1 + 连续变量 | 总成本最低 |
| 排班问题 | 人员安排 | 0/1 变量 + 辅助整数变量 | 尽量公平 |

这四个例子是基础积木。

后面所有复杂业务场景，都是这些积木的组合：

```text
选择谁 / 开不开 / 用不用：0/1 变量
发多少 / 买多少 / 分多少：连续或整数变量
成本、利润、风险、服务水平：目标函数
容量、预算、SLA、技能、现金流：约束条件
```

学习 CPLEX 的关键不是背 API。

真正关键的是：

```text
把业务问题翻译成变量、目标和约束
```

---

## 软约束：现实业务经常不完美

硬约束模型可能会无解。

例如排班：

```text
周末需要 5 个人
但可用员工只有 3 个
```

这时不能只告诉业务方“无解”，更有价值的是：

```text
最少缺几个人？
缺口在哪几天？
如果要补齐，需要增加多少资源？
```

软约束做法：

```text
允许缺口变量存在，但给缺口很高罚分。
```

这样 CPLEX 会给出最小损失方案。

---

## 多目标与分阶段优化

真实业务通常不是单目标。

排班可能同时关心：

```text
缺口最少
公平性更好
员工偏好命中更多
关键技能覆盖
成本更低
```

跨境电商也一样：

```text
成本、SLA、碳排、风险、库存、现金流、客户体验
```

常见建模方式：

- 加权多目标：把多个目标放进一个评分函数
- 罚分权重：不同违反行为设置不同代价
- 分阶段优化：先保证最重要目标，再优化次要目标

---

## 工程化：从 demo 到可用系统

我们不只写了单个求解脚本，还逐步加入：

- CSV 数据输入
- 情景分析
- 结果导出 CSV / JSON
- 自动解释报告
- 实验日志
- 性能基准
- REST API
- Web 交互页面
- 自动化测试

这一步很重要：

```text
优化模型只有能被业务使用、复查、解释和集成，才真正有生产价值。
```

---

## 跨境电商模拟器

最新业务主线是跨境电商库存与物流模拟器：

```bash
cd ~/cplex/python
../.venv/bin/python cross_border_ecommerce_app.py
```

打开：

```text
http://127.0.0.1:5052
```

页面包含 35 个场景，分成四组：

- 仓网与履约
- 补货与库存
- 物流路径与服务
- 经营动作

---

## 跨境电商场景怎么理解

这些场景看起来很多，但底层结构一样。

例子：

```text
仓网选址：开哪些仓、哪些市场由哪个仓履约
补货计划：空运、海运、整柜、拼箱怎么组合
供应商选择：采购价、起订量、交期、可靠性如何取舍
促销计划：哪些 SKU 值得投预算
订单波次：订单排到哪个出库波次，是否需要加班
```

统一解释方式：

```text
变量 = 模型能决定什么
目标 = 成本最低、利润最高、风险最小或净贡献最大
约束 = 预算、容量、SLA、库存、现金流、产能等限制
```

---

## CPLEX vs Gurobi

CPLEX 和 Gurobi 是同一类产品。

它们都是商业级数学优化求解器，都可以用来解决：

- 线性规划 LP
- 混合整数规划 MIP / MILP
- 二次规划 QP
- 选址、运输、排班、生产计划等优化问题

---

## CPLEX 和 Gurobi 的区别

| 对比项 | CPLEX | Gurobi |
|---|---|---|
| 公司 | IBM | Gurobi Optimization |
| Python API | `docplex` / `cplex` | `gurobipy` |
| 产品生态 | IBM Optimization Studio、OPL、CP Optimizer | 专注优化求解器和 API |
| 排班场景 | MILP，也可用 CP Optimizer 做复杂排程 | 通常用 MILP/MIQP 建模 |
| 学习迁移 | 建模思想可迁移到 Gurobi | 建模思想可迁移到 CPLEX |

关键判断：

```text
差别主要在 API、授权、生态和性能细节；
变量、目标函数、约束这些建模思想是共通的。
```

---

## 运行方式

进入目录：

```bash
cd ~/cplex
```

激活虚拟环境：

```bash
source .venv/bin/activate
```

运行四个例子：

```bash
python knapsack_docplex.py
python transportation_docplex.py
python facility_location_docplex.py
python scheduling_docplex.py
```

启动排班 Web 系统：

```bash
python scheduling_app.py
```

打开：

```text
http://127.0.0.1:5050
```

启动跨境电商模拟器：

```bash
python cross_border_ecommerce_app.py
```

打开：

```text
http://127.0.0.1:5052
```

---

## 复习练习

背包问题：

- 把容量从 8 改成 6，观察选择结果
- 给 book 提高价值，看它什么时候会被选中
- 增加一个新物品

运输问题：

- 调整某条路线成本
- 增加一个仓库
- 把某个客户需求调大，观察是否仍可行

仓库选址问题：

- 提高 Wuhan 的固定成本
- 降低 Shanghai 到 Shenzhen 的运输成本
- 给模型加一个“最多只能开 2 个仓库”的约束

排班问题：

- 把某天需要人数调高，观察是否仍可行
- 把某个员工周末可用性改成 0
- 把每人最多班次数从 5 改成 4
- 加一个约束：员工不能连续上超过 3 天

---

## 已经形成的文档体系

复习与分享可以看：

```text
docs/cplex_core_learning_10_slides.md
```

排班演示脚本：

```text
docs/manager_demo.md
```

跨境电商模拟器说明：

```text
docs/cross_border_ecommerce_simulator.md
```

跨境电商 35 个场景讲义：

```text
docs/cross_border_ecommerce_lessons.md
```

---

## 最后总结

CPLEX 学习真正沉淀的是一种决策建模能力：

```text
把复杂业务拆成变量、目标和约束；
把经验判断变成可计算规则；
把冲突和取舍变成可解释结果；
把单次求解扩展成系统能力。
```

一句话：

```text
CPLEX 的价值不是替人拍脑袋，
而是让业务决策在约束清楚、目标清楚、取舍清楚的基础上变得可计算。
```
