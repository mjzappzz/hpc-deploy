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
