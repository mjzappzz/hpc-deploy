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

### Requirement: 常规与极限压测相互隔离

系统 SHALL 保持常规 GPU、CPU/内存和磁盘压测的独立报告与串行语义。极限压测 SHALL 作为独立的无磁盘原子验证，不得混入常规套件结果。

#### Scenario: 先后运行两种压测
- **WHEN** 同一服务器先后运行常规压测和极限压测
- **THEN** 系统分别保留常规子报告和极限组合结论
