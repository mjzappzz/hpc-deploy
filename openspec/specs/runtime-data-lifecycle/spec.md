## Purpose

Define retention, cleanup, backup, and restore behavior for controller-owned runtime data so operators can control local and remote footprint while preserving task traceability and protecting recoverable system state.

## Requirements

### Requirement: Artifact and log retention preserve traceability

The system SHALL scan controller artifacts and database task logs with task and batch context, support configured automatic retention, and soft-hide history when local task artifacts are removed rather than silently deleting task records.

#### Scenario: Local artifacts for a completed task are deleted
- **WHEN** an authorized operator removes the task's local result files
- **THEN** the files are removed, the task record is retained, and history records that its artifacts were removed

#### Scenario: Automatic retention runs
- **WHEN** automatic cleanup is enabled and its scheduled time arrives
- **THEN** the system applies the configured retention period and records the run outcome for settings visibility

### Requirement: Remote cleanup is path-constrained and attributable

The system SHALL inspect and clean only supported remote runtime locations, associate discovered task directories with known task metadata where possible, and require a tamper-resistant deletion reference for an individual remote task directory.

#### Scenario: An operator requests removal of a remote task directory
- **WHEN** the request supplies a server and valid deletion reference returned by a prior scan
- **THEN** the system deletes only that authorized task directory and returns the outcome

#### Scenario: A caller attempts an unsupported remote cleanup target
- **WHEN** a remote cleanup request names a path or target outside the supported runtime locations
- **THEN** the request is rejected before any remote deletion command is issued

### Requirement: SQLite backup and restore preserve recoverability

The system SHALL support verified SQLite backup rotation and guarded restoration so a valid replacement is not applied without an operator's explicit force action and a pre-restore safety snapshot.

#### Scenario: A restore is requested without force
- **WHEN** an operator invokes the restore workflow without its explicit force flag
- **THEN** the workflow reports the planned target and does not overwrite the active database

### Requirement: 控制器运行数据容量和清理状态可见且可告警

系统 SHALL 显示控制器数据分区可用空间、任务产物占用、SQLite 备份占用、自动清理启用状态和最近一次清理结果。当可用空间或占用达到已配置阈值时，系统 SHALL 在仪表盘和任务提交前给出明确告警；空间不足以安全保存任务证据时 SHALL 阻断新建高产物任务。

#### Scenario: 控制器存储空间低于告警阈值
- **WHEN** 控制器运行数据所在分区的可用空间低于配置的告警阈值
- **THEN** 系统显示容量告警和当前占用构成，同时不影响已运行任务

#### Scenario: 空间不足以创建极限压测
- **WHEN** 控制器可用空间低于极限压测所需的最小安全空间
- **THEN** 系统拒绝创建该任务并说明需清理或扩容后再试
