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
