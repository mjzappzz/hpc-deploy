## MODIFIED Requirements

### Requirement: Stress outcomes require valid reports and safe execution inputs

The system SHALL enforce supported duration and parameter bounds, retain filesystem safety margin for disk tests, collect task evidence, and distinguish platform execution success from a report-level PASS or FAIL. A missing or invalid required XLSX report SHALL not be reported as a successful stress validation. Controlled stress execution SHALL emit or persist evidence of its current phase and terminal outcome so the platform can report an evidence-backed failure explanation.

#### Scenario: A stress script exits without producing a valid report
- **WHEN** remote execution completes but required report generation or collection fails
- **THEN** the task is finalized as failed or report-failed with diagnostic evidence instead of a validation pass

#### Scenario: Disk testing would consume protected capacity
- **WHEN** the selected filesystem cannot satisfy the required safety margin and minimum workload
- **THEN** the disk stage refuses to start and reports the capacity constraint

#### Scenario: A controlled stress stage fails
- **WHEN** a controlled GPU, CPU/memory, disk, or extreme-stress stage exits unsuccessfully
- **THEN** its collected evidence identifies the failed phase and terminal outcome, and includes a specific failure fact when one is available
