## MODIFIED Requirements

### Requirement: Historical results preserve task and batch evidence

The system SHALL list and search task and batch history, expose collected artifacts for download, produce batch report archives, and provide evidence-backed task diagnosis. A batch archive SHALL preserve distinct child-report identities. For a failed, canceled, or indeterminate task, diagnosis SHALL distinguish confirmed facts, failure phase, attribution boundary, direct evidence, investigation hints, and next actions. The system MUST NOT present an unverified hypothesis as a confirmed root cause.

#### Scenario: A batch contains multiple disk reports
- **WHEN** the operator downloads the batch report archive
- **THEN** each child report is included under its original distinct filename

#### Scenario: A task completed but its report says FAIL
- **WHEN** task execution reaches a completed state while report parsing finds a failed stress result
- **THEN** history and diagnosis distinguish execution completion from the report-level validation failure

#### Scenario: A task has a directly evidenced failure
- **WHEN** task logs, a structured task event, a platform error, or a report contains a specific failure fact
- **THEN** history presents that fact and its supporting evidence as the primary failure explanation

#### Scenario: A task has insufficient root-cause evidence
- **WHEN** the system can identify the failed phase but cannot directly prove its root cause
- **THEN** history states that the cause requires investigation, presents only evidence-backed hypotheses, and provides targeted next actions

### Requirement: 极限压测以原子任务展示

系统 SHALL 在历史任务中将极限压测展示为一个不可拆分的任务，显示整体状态、GPU 与 CPU/内存结果、同步偏差和失败原因，并提供模块报告下载。整体汇总失败 SHALL NOT 取代可用的 GPU、CPU/内存或编排层直接失败证据。

#### Scenario: 极限压测模块失败
- **WHEN** 极限压测的任一模块或同步校验失败
- **THEN** 历史任务显示整体失败，不将任一模块显示为可独立成功的任务

#### Scenario: 极限压测包含可确认的子模块故障
- **WHEN** GPU、CPU/内存或编排层存在带证据的失败事件
- **THEN** 任务详情分别显示各层状态、直接失败事实和证据，不以通用汇总错误替代该原因
