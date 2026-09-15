## Purpose

Define reliable remote execution of approved operational work so a controller can create, monitor, cancel, retry, recover, and group work across managed Linux/HPC servers without losing task identity or remote-work-directory ownership.

## Requirements

### Requirement: Approved work is represented by durable tasks

The system SHALL create single and batch tasks only for eligible managed servers and approved task inputs. Each task SHALL retain a unique task ID, server association, execution parameters, remote work directory, lifecycle state, logs, and terminal outcome.

#### Scenario: A task is submitted to an archived server
- **WHEN** a create request includes an archived server
- **THEN** task creation is rejected and no remote command is issued

#### Scenario: A batch is submitted to several eligible servers
- **WHEN** approved work is created for multiple servers
- **THEN** the system creates independently identifiable task records while retaining their batch relationship for monitoring and later retrieval

### Requirement: Task lifecycle remains recoverable and controllable

The system SHALL expose task and batch status, cancellation, permitted retries, log retrieval, and restart recovery. A backend restart SHALL resume monitoring of remote work that is still active rather than submitting it again.

#### Scenario: The backend restarts while remote work is running
- **WHEN** startup recovery finds a RUNNING task with a live remote process or pending completion evidence
- **THEN** the controller resumes monitoring that task and does not duplicate its remote execution

#### Scenario: An operator retries a failed task
- **WHEN** a retryable failed or canceled task is retried
- **THEN** a new task attempt is created with the supported original execution settings and the prior attempt remains historical evidence

### Requirement: 原子极限任务按整体处理

系统 SHALL 将极限压测的取消、重试和后端恢复作为单一远端任务处理，不得单独重新下发或恢复其 GPU、CPU/内存模块。

#### Scenario: 后端恢复极限压测
- **WHEN** 后端重启时发现仍在运行的极限压测
- **THEN** 系统恢复对已有远端任务的监控，不重复启动组合负载

### Requirement: 资源冲突被拒绝且保留可追溯原因

系统 SHALL 在创建资源竞争型任务时判断同一服务器的活动任务。被资源互斥规则拒绝的请求 SHALL 不产生远端命令，并向操作员返回冲突任务标识、冲突资源类别和可重试条件。

#### Scenario: 创建任务遇到活动资源冲突
- **WHEN** 请求会与同一服务器的活动任务竞争 GPU、CPU 或内存资源
- **THEN** 系统不创建可执行远端工作，返回冲突任务及其状态，并在审计记录中保留拒绝原因

### Requirement: 未确认远端状态不得伪装为正常终态

系统 SHALL 在任务停止、恢复或监控期间无法确认远端进程状态时，保留最后一次确认的证据和明确的未确认原因；任务结果 SHALL 区分已确认停止与远端状态未确认。

#### Scenario: 取消后的远端状态未确认
- **WHEN** 任务取消操作无法连接远端并验证进程清理结果
- **THEN** 系统向操作员显示远端状态未确认及建议处置，而不将任务描述为已完成清理
