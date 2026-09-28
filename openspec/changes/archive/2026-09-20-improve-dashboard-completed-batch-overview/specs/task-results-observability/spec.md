## MODIFIED Requirements

### Requirement: Historical results preserve task and batch evidence

The system SHALL list and search task and batch history, expose collected artifacts for download, produce batch report archives, and provide evidence-backed task diagnosis. A batch archive SHALL preserve distinct child-report identities. For a failed, canceled, or indeterminate task, diagnosis SHALL distinguish confirmed facts, failure phase, attribution boundary, direct evidence, investigation hints, and next actions. The system MUST NOT present an unverified hypothesis as a confirmed root cause. Dashboard 的近期完成任务 SHALL 将带有相同 `batch_id` 的子任务聚合为一个批次展示条目，同时保留单次任务的独立条目；批次摘要 SHALL 反映完整批次，而不是受子任务列表截断影响的部分数据。

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

#### Scenario: Dashboard shows a completed batch
- **WHEN** the Dashboard loads recent completed work containing multiple completed child tasks with the same `batch_id`
- **THEN** it displays one batch row with the batch ID, task type, server count, child-task count, overall status, success/failure summary, completion time, and an entry to the existing batch detail view

#### Scenario: Dashboard mixes batches and single tasks
- **WHEN** recent completed work contains both batched and single tasks
- **THEN** the Dashboard displays each batch as one row and each single task as one row, and the display limit counts these aggregated rows rather than child tasks

#### Scenario: Dashboard batch summary includes report-level failure
- **WHEN** a child task execution is complete but its report-level validation result is failed
- **THEN** the batch overall status and failure summary include that report-level failure using the same final-status semantics as task history
