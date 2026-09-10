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
