## Purpose

Define Linux GPU, CPU/memory, and disk stress validation so operators obtain safe, attributable, and report-backed evidence of server stability rather than treating process completion as a hardware pass result.

## Requirements

### Requirement: Stress suites preserve dependency and disk-isolation semantics

The system SHALL create GPU and CPU/memory stages serially per server and SHALL create each selected disk mount as a distinct child task after its required predecessor. Disk selections SHALL remain scoped to their owning server.

#### Scenario: A suite selects two disk paths on one server
- **WHEN** the GPU and CPU/memory prerequisites have completed successfully
- **THEN** the system runs distinct disk child tasks for the two paths and preserves a unique remote work directory and report identity for each

#### Scenario: A multi-server suite has different disk selections
- **WHEN** each server submits its own selected mount paths
- **THEN** no server receives a disk path selected solely for another server

### Requirement: Stress outcomes require valid reports and safe execution inputs

The system SHALL enforce supported duration and parameter bounds, retain filesystem safety margin for disk tests, collect task evidence, and distinguish platform execution success from a report-level PASS or FAIL. A missing or invalid required XLSX report SHALL not be reported as a successful stress validation.

#### Scenario: A stress script exits without producing a valid report
- **WHEN** remote execution completes but required report generation or collection fails
- **THEN** the task is finalized as failed or report-failed with diagnostic evidence instead of a validation pass

#### Scenario: Disk testing would consume protected capacity
- **WHEN** the selected filesystem cannot satisfy the required safety margin and minimum workload
- **THEN** the disk stage refuses to start and reports the capacity constraint
