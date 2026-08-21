# CPLEX 排班 API

这个小服务把 CPLEX 排班模型包装成 JSON API，方便前端或其他业务系统调用。

## 启动服务

```bash
cd ~/cplex
source .venv/bin/activate
cd python
../.venv/bin/python scheduling_app.py
```

服务地址：

```text
http://127.0.0.1:5050
```

## 健康检查

```bash
curl --noproxy '*' http://127.0.0.1:5050/api/health
```

返回示例：

```json
{
  "service": "cplex-scheduling",
  "status": "ok"
}
```

## 获取默认问题

```bash
curl --noproxy '*' http://127.0.0.1:5050/api/problem
```

返回内容包括：

- `employees`: 员工列表
- `days`: 日期列表
- `required_staff`: 每天需要人数
- `availability`: 员工可用性
- `preferences`: 员工偏好
- `max_shifts_per_employee`: 每人最多班次数

## 求解排班

```bash
curl --noproxy '*' \
  -X POST http://127.0.0.1:5050/api/solve \
  -H 'Content-Type: application/json' \
  --data @problem.json
```

请求体关键字段：

```json
{
  "employees": ["Alice", "Bob", "Carol", "David"],
  "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
  "required_staff": {"Mon": 2, "Tue": 2, "Wed": 2, "Thu": 2, "Fri": 3, "Sat": 2, "Sun": 1},
  "availability": {
    "Alice": {"Mon": 1, "Tue": 1, "Wed": 1, "Thu": 1, "Fri": 1, "Sat": 0, "Sun": 0}
  },
  "max_shifts_per_employee": 5,
  "soft_constraints": false,
  "time_limit": 10,
  "mip_gap": 0,
  "preference_weight": 0.01
}
```

返回内容包括：

- `status`: 求解状态
- `mode`: `hard` 或 `soft`
- `schedule`: 每天安排哪些员工
- `workloads`: 每个员工的总班次数
- `shortages`: 每天缺口
- `fairness_spread`: 公平性差距
- `preference_matches`: 偏好命中数
- `solve_time`: 求解耗时
- `solve_status`: CPLEX 求解状态

## Python 客户端演示

```bash
cd python
../.venv/bin/python scheduling_api_client_demo.py
```

这个脚本会调用：

```text
GET /api/health
GET /api/problem
POST /api/solve
```
