## Why

压测监控标签在任务执行页、普通历史详情和批次详情中使用了不一致的顺序；批次详情将 GPU 放在 CPU 与磁盘之后，增加了 GPU 压测观察的查找成本。统一排序可让运维人员在各入口形成稳定的操作预期。

## What Changes

- 将运行中 stress 任务的监控标签统一为“执行日志、GPU、CPU 与内存、磁盘”。
- 对齐任务执行页、普通历史任务详情和批次详情的标签顺序与中文标签表达。
- 保持现有可见性条件、默认选中标签、监控请求和终态隐藏行为不变。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `task-results-observability`: 统一单任务与批次任务的运行中监控标签顺序，确保 GPU 监控优先于 CPU 和磁盘监控。

## Impact

- 影响 `frontend/src/views/TaskHistory.vue` 与 `frontend/src/views/TaskRunner.vue` 的展示顺序。
- 不涉及后端 API、任务执行、监控采集、数据库、依赖或部署配置。
