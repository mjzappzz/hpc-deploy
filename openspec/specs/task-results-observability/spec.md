## Purpose

Define how operators observe execution and retrieve its evidence so live progress, durable history, diagnostics, artifacts, and dashboard summaries remain consistent for single tasks and batches.

## Requirements

### Requirement: Live task evidence is available during execution

The system SHALL publish task logs through a WebSocket channel and provide HTTP retrieval as a fallback. It SHALL expose task progress and monitor data without allowing overlapping monitor work to exhaust the controller.

#### Scenario: The live log WebSocket is unavailable
- **WHEN** a browser cannot maintain its task-log WebSocket connection
- **THEN** it can retrieve current logs through the HTTP fallback without changing task execution state

#### Scenario: A monitor request overlaps an active sample
- **WHEN** a second monitor request arrives for the same task while sampling is active
- **THEN** the system rejects or defers the overlap without opening an unnecessary competing remote connection

### Requirement: Historical results preserve task and batch evidence

The system SHALL list and search task and batch history, expose collected artifacts for download, produce batch report archives, and provide rule-based task diagnosis. A batch archive SHALL preserve distinct child-report identities.

#### Scenario: A batch contains multiple disk reports
- **WHEN** the operator downloads the batch report archive
- **THEN** each child report is included under its original distinct filename

#### Scenario: A task completed but its report says FAIL
- **WHEN** task execution reaches a completed state while report parsing finds a failed stress result
- **THEN** history and diagnosis distinguish execution completion from the report-level validation failure

### Requirement: 极限压测以原子任务展示

系统 SHALL 在历史任务中将极限压测展示为一个不可拆分的任务，显示整体状态、GPU 与 CPU/内存结果、同步偏差和失败原因，并提供模块报告下载。

#### Scenario: 极限压测模块失败
- **WHEN** 极限压测的任一模块或同步校验失败
- **THEN** 历史任务显示整体失败，不将任一模块显示为可独立成功的任务

### Requirement: 历史压测提供同机同类基线比较

系统 SHALL 为完成的可比较压测保留关键结论指标，并在查看新结果时比较同一服务器、同一压测类别的最近有效历史基线。系统 SHALL 以证据可得为前提提示性能、温度、错误或结果状态的明显退化，不将不同服务器或不同压测类别混为基线。

#### Scenario: 新压测相对基线明显退化
- **WHEN** 某服务器完成的压测关键指标相对最近可比成功基线超过已定义阈值
- **THEN** 历史任务显示退化提示、比较指标、基线任务标识和证据可用性

#### Scenario: 没有可比基线
- **WHEN** 某服务器尚无同类有效历史结果
- **THEN** 系统显示本次结果可作为首个基线，不生成退化结论

### Requirement: 极限压测预检和处置证据可查看

系统 SHALL 在极限压测历史中显示提交前预检结果、自动准备记录、资源冲突拒绝原因（如有）以及取消或异常时的远端处置证据。

#### Scenario: 查看异常结束的极限压测
- **WHEN** 操作员打开因连接丢失、温度保护或取消而结束的极限压测
- **THEN** 系统显示触发原因、最后远端状态、停止/清理结果和待人工确认项
