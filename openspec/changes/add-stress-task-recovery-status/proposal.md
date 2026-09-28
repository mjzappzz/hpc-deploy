## Why

长时压测的远端工作负载与平台 SSH 控制通道相互独立。控制通道不可用时，现有状态机仍可能将远端仍在执行的任务标记为 `FAILED`，使批次调度停止等待、前端误报失败，并可能诱发重复下发风险。

## What Changes

- 新增非终态任务状态 `RECOVERING`，表示远端压测已启动但 SSH 控制通道不可用，平台正在重新连接并确认远端状态。
- 为 stress 任务定义 `RUNNING -> RECOVERING -> RUNNING` 的自动恢复路径；仅在已确认远端退出失败、检测到重启或操作员明确放弃时进入 `FAILED`。
- 使批次调度、资源冲突检查、启动恢复、自动清理和任务取消将 `RECOVERING` 视为活动任务，等待其恢复或终态，禁止将其当作调度失败。
- 在 REST/WebSocket 响应和前端展示中提供“恢复中：SSH 失联，正在重新连接”的状态、最后成功心跳、失联时间、重连次数与最近错误。
- 对历史上由控制面失联误标为失败、但恢复时确认远端 PID 存活的任务提供受审计的自动回正路径。

## Capabilities

### New Capabilities

- `stress-task-recovery-state`: 为已启动的 stress 任务提供可观察、可恢复且不误判失败的 SSH 控制面失联状态机。

### Modified Capabilities

- 无。

## Impact

- 后端：`backend/app/core/task_runner.py`、`backend/app/api/tasks.py`、任务恢复与清理逻辑、任务 schema/序列化及相关测试。
- 前端：任务历史、状态标签、进度展示、运行中筛选与 WebSocket 状态消费。
- API：任务 `status` 新增 `RECOVERING` 枚举值；响应新增恢复诊断字段，现有消费者必须把该状态当作活动状态处理。
- 数据：SQLite `tasks.params` 保存恢复元数据；无需新增表或数据库迁移。
