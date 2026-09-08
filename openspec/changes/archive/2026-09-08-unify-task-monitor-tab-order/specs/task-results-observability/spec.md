## MODIFIED Requirements

### Requirement: Live task evidence is available during execution

系统 SHALL 通过 WebSocket 发布任务日志，并提供 HTTP 查询作为回退方式。系统 SHALL 提供任务进度和监控数据，且不得因重叠的监控工作耗尽控制端资源。对于运行中的 stress 任务，任务执行页、单任务历史详情和批次子任务详情 SHALL 按“执行日志、GPU、CPU 与内存、磁盘”展示监控标签。

#### Scenario: The live log WebSocket is unavailable
- **WHEN** 浏览器无法维持任务日志的 WebSocket 连接
- **THEN** 可以通过 HTTP 回退方式获取当前日志，且不改变任务执行状态

#### Scenario: A monitor request overlaps an active sample
- **WHEN** 同一任务的第二个监控请求在采样进行期间到达
- **THEN** 系统拒绝或延后该重叠请求，且不建立不必要的竞争性远端连接

#### Scenario: Operator views a running stress task from any task surface
- **WHEN** 运维人员在任务执行页、单任务历史详情或批次子任务详情查看运行中的 stress 任务
- **THEN** 监控标签均按执行日志、GPU、CPU 与内存、磁盘的顺序显示
