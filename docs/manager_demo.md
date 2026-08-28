# CPLEX 学习汇报演示脚本

目标：不用 PPT，直接展示可以运行的代码和本地 Web 系统。

这份脚本现在分成两条业务线：

```text
第一条：员工排班优化，展示 CPLEX 如何处理人员、规则、软约束和 API 化。
第二条：跨境电商库存与物流优化，展示 CPLEX 如何处理仓网、补货、物流路径和经营动作。
第三条：优化平台 POC，展示如何把多个模型封装成经理能看懂的一页式决策入口。
```

## 0. 启动优化平台 POC

```bash
cd ~/cplex
source .venv/bin/activate
cd python
python platform_app.py
```

打开：

```text
http://127.0.0.1:5053
```

五层页面：

```text
/upstream  上游数据接入层
/config    场景配置层
/inputs    CPLEX 模型入参层
/results   求解结果层
/lineage   数据血缘与字段映射
```

推荐先讲这一页：

- 上游数据：解释 OMS/WMS/TMS/HR 数据如何接入。
- 场景配置：选择基准、旺季或稳健方案，也可以调整需求倍率、空运能力、缺口罚分或 SLA。
- 模型入参：展示进入 CPLEX 的仓网、补货、服务和排班数据。
- 求解结果：用三方案差异矩阵把 objective value 翻译成综合成本、缺口、行动建议、审批分层和差异来源，保存/回放运行记录，并一键导出演示报告。
- 数据血缘：用按模型分组的可视化泳道图展示上游表、场景参数、转换函数、CPLEX 入参、求解器和结果字段。
- 页面状态：五个页面共享当前方案和临时参数，场景配置页修改后，模型入参和求解结果页会沿用同一组参数。
- 数据层：方案配置来自 `python/data/platform_poc_data.json`，页面右侧可以编辑并保存。
- 上游接入层：业务原始数据来自 `python/data/platform_upstream_data.json`，模拟 OMS、WMS、TMS 和 HR 系统同步，并支持页面编辑保存。
- 模型入参：页面中间的“CPLEX 模型运行入参”展示上游数据经过场景参数加工后的求解器输入，例如仓库容量、市场需求、线路成本、补货需求、员工可用性和技能要求。

一句话：

```text
这两周不是只学会了某一个 CPLEX 模型，而是把排班、仓网、补货、服务水平和 API 化串成了一个优化平台雏形。
```

## 1. 启动排班系统

```bash
cd ~/cplex
source .venv/bin/activate
cd python
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

## 16. 演示技能覆盖约束

运行：

```bash
python scheduling_skills_demo.py
```

讲解点：

```text
真实排班里，不是所有员工都能覆盖所有岗位。
这个示例给员工配置技能，并要求每天至少有 1 名 senior。
模型会在满足总人数的同时，保证关键技能覆盖。
```

## 17. 演示成本优化

运行：

```bash
python scheduling_cost_demo.py
```

讲解点：

```text
真实排班不只要满足人数和技能，还要考虑成本。
这个示例给每个员工每天设置不同成本，
模型会在公平性、偏好和技能覆盖之外，尽量降低总排班成本。
```

## 18. 演示模型版本和实验记录

运行：

```bash
python scheduling_experiment_log_demo.py
```

会生成：

```text
reports/experiments.jsonl
reports/experiments_summary.csv
```

讲解点：

```text
随着模型规则越来越多，需要记录每次实验用了哪些参数、哪些约束和得到什么结果。
JSONL 适合追加保存历史实验，CSV 适合快速对比。
这能帮助我们回溯“为什么当时选择这个模型版本”。
```

## 19. 演示冲突诊断

运行：

```bash
python scheduling_conflict_diagnosis_demo.py
```

讲解点：

```text
当硬约束模型无解时，业务方最关心的不是“无解”两个字，
而是哪条条件互相打架。
这个示例会检查总班次容量、每天可用人数、每天技能覆盖，
把可能的问题翻译成可读的诊断报告。
```

## 20. 演示软约束进阶

运行：

```bash
python scheduling_soft_constraints_demo.py
```

讲解点：

```text
上一版软约束只允许“人数不足”有缺口。
这一版进一步允许“技能覆盖不足”也有缺口，并给缺口设置高罚分。
这样模型会尽量满足技能要求，实在满足不了时明确报告缺哪个技能、缺几个人。
```

## 21. 演示罚分权重

运行：

```bash
python scheduling_penalty_weights_demo.py
```

讲解点：

```text
软约束不是简单地“都可以违反”，而是要给不同违反设置不同代价。
如果技能缺口罚分很低，模型可能为了满足员工偏好牺牲技能覆盖。
如果技能缺口罚分很高，模型会优先安排具备关键技能的人。
```

## 22. 演示分阶段优化

运行：

```bash
python scheduling_two_stage_demo.py
```

讲解点：

```text
生产排班里有些目标有明显优先级：先尽量不缺人、不缺关键技能，
然后才考虑公平性、偏好和成本。
分阶段优化会先求出最小缺口，再把这个缺口固定住做第二次优化。
这样比单纯靠罚分权重更稳定，也更容易向业务解释。
```

## 23. 演示人工干预

运行：

```bash
python scheduling_manual_overrides_demo.py
```

讲解点：

```text
真实排班不是一次求解后就结束，经理经常需要手工锁定某些安排。
比如某员工周一必须上班，或者某员工周二临时不能上班。
这些人工规则可以变成模型约束，系统会在保留人工决定的前提下重新优化。
```

## 24. 演示候选方案对比

运行：

```bash
python scheduling_alternatives_demo.py
```

讲解点：

```text
优化系统不一定只给一个答案。
我们可以用同一组业务输入生成多套候选排班，
让经理比较人数缺口、技能缺口、公平性、偏好命中和成本，
再选择最适合当前管理目标的方案。
```

## 25. 可以打开的代码

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

## 26. 启动跨境电商模拟器

启动服务：

```bash
cd ~/cplex
source .venv/bin/activate
cd python
python cross_border_ecommerce_app.py
```

打开：

```text
http://127.0.0.1:5052
```

讲解开场：

```text
前面的排班案例说明了 CPLEX 如何做人员资源优化。
这个跨境电商模拟器则把同样的建模方法扩展到仓库、库存、物流和经营决策。
页面左侧有 35 个场景，按仓网与履约、补货与库存、物流路径与服务、经营动作分组。
```

配套文档：

```text
docs/cross_border_ecommerce_simulator.md
docs/cross_border_ecommerce_lessons.md
```

## 27. 演示跨境电商仓网与履约

建议依次点击：

```text
严格 SLA
旺季缺口分析
旺季临时扩容
天气风险建仓选址
```

讲解点：

```text
仓网问题的核心不是“开哪个仓看起来近”，而是把固定成本、履约成本、容量、SLA 和风险放在一起算。
严格 SLA 会推动模型选择更靠近客户的仓；
旺季缺口分析会指出哪里缺产能；
临时扩容会比较扩容成本和丢单损失；
天气风险选址会把极端天气转成风险成本和风险约束。
```

一句话：

```text
仓网优化是在成本、速度、容量和风险之间找一个可执行的履约网络。
```

## 28. 演示跨境电商补货与库存

建议依次点击：

```text
补货情景分析
多供应商采购分配
供应商评分体系
采购现金流约束
整柜拼箱空运补货
跨仓库存调拨
```

讲解点：

```text
库存优化不是单纯多备货。
模型会同时考虑运输提前期、缺货罚分、仓库容量、供应商可靠性、起订量、现金预算和跨仓调拨成本。
```

可以重点展示：

```text
空运适合救急，整柜适合提前规划，拼箱负责在速度和成本之间过渡。
供应商选择不是只看报价，还要看风险、交期、可靠性、售后和响应能力。
现金流约束会解释为什么有需求也不一定能马上采购。
```

一句话：

```text
补货优化的重点不是把库存堆高，而是在缺货、现金、仓容和运输成本之间找平衡。
```

## 29. 演示跨境电商物流路径与服务

建议依次点击：

```text
Landed Cost 路径选择
关税政策敏感性
百分比 SLA 路径选择
SLA 敏感性分析
多目标权衡
物流韧性预案
包装箱型与运费优化
```

讲解点：

```text
物流路径不能只看单票运费。
DDU、DDP、保税仓、直邮、本地仓会受到税费、清关成本、时效、容量、风险和碳排影响。
SLA 敏感性可以告诉业务方“快一天”到底多花多少钱。
韧性预案可以比较平时省钱和故障时缺货之间的取舍。
包装优化说明箱型和包材也会影响体积重、破损率和总成本。
```

一句话：

```text
物流优化看的是 landed cost 和服务承诺，不是单独比较哪条线路运费最低。
```

## 30. 演示跨境电商经营动作

建议依次点击：

```text
多平台库存分配
广告库存联动
订单波次排程
客服售后排班
促销预算计划
促销预算敏感性
清仓折扣优化
退货分级再销售
经营看板汇总
```

讲解点：

```text
经营动作也可以建成优化模型。
库存不足时，模型会决定 Amazon、独立站、TikTok Shop 和批发渠道谁优先拿货。
广告库存联动会避免广告把需求打到无法履约的 SKU 上。
订单波次排程会把拣货、打包、截单时间和加班成本放在一起算。
促销和清仓不是越猛越好，而是要看库存、毛利、履约能力和预算边际收益。
退货分级再销售会把不同成色商品分到最合适的回收路径。
```

一句话：

```text
优化模型不只适合供应链后台，也能支持促销、广告、客服、清仓和退货这些经营决策。
```

## 31. 跨境电商模拟器的汇报收尾

可以这样总结：

```text
这个模拟器不是预测销量，而是在给定销量、库存、仓容、运费、时效和经营约束后，
计算怎样开仓、分仓、补货、选择物流服务和安排经营动作，能让总成本或损失最小，或者让净贡献最大。
```

也可以把所有场景统一解释成：

```text
变量 = 模型可以决定什么
目标 = 模型想让什么最好
限制 = 模型必须遵守什么规则
结果 = 业务上应该怎么解释
```

现场可以打开：

```text
docs/cross_border_ecommerce_simulator.md
```

用于查页面实际场景、API 参数和演示顺序。

如果要按课程方式讲解，则打开：

```text
docs/cross_border_ecommerce_lessons.md
```

这份文档把 35 个场景都整理成“解决什么问题、核心变量、目标函数、关键限制、业务判断句”的格式。

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

技能覆盖约束：

```text
scheduling_skills_demo.py
scheduling_solver.py
```

成本优化：

```text
scheduling_cost_demo.py
scheduling_solver.py
```

实验记录：

```text
scheduling_experiment_log_demo.py
reports/experiments.jsonl
reports/experiments_summary.csv
```

冲突诊断：

```text
scheduling_conflict_diagnosis_demo.py
scheduling_diagnostics.py
```

软约束进阶：

```text
scheduling_soft_constraints_demo.py
scheduling_solver.py
```

罚分权重：

```text
scheduling_penalty_weights_demo.py
scheduling_solver.py
```

分阶段优化：

```text
scheduling_two_stage_demo.py
scheduling_solver.py
```

前面几节基础模型：

```text
knapsack_docplex.py
transportation_docplex.py
facility_location_docplex.py
scheduling_docplex.py
```
