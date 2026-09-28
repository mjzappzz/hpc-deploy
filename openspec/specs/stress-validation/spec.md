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

### Requirement: openEuler CPU/内存与磁盘压测可完成依赖准备

系统 SHALL 在 openEuler 24.03 LTS SP4 上为 CPU/内存和磁盘压测识别缺失的运行及报告依赖，并使用该系统已配置的软件源准备可用依赖。依赖准备 SHALL 不要求安装面向其他发行版的软件源；依赖不可用时 SHALL 在负载启动前失败，并提供具体的依赖或软件源错误，不将其报告为硬件压测失败。

#### Scenario: 依赖已经齐备
- **WHEN** openEuler 服务器已具备所选 CPU/内存或磁盘压测所需的可执行程序和报告依赖
- **THEN** 任务跳过安装并进入相应的压测阶段

#### Scenario: 缺失依赖但软件源可用
- **WHEN** openEuler 服务器缺少所选压测的依赖，且已配置的软件源提供所需软件包
- **THEN** 系统完成依赖安装与可用性复核，再启动压测并按既有规则生成报告

#### Scenario: 依赖或软件源不可用
- **WHEN** openEuler 服务器无法从已配置的软件源取得所需依赖，或安装后依赖仍不可用
- **THEN** 任务在压测启动前失败，日志指出失败的依赖或软件源，并且不产生压测通过结论

### Requirement: 常规与极限压测相互隔离

系统 SHALL 保持常规 GPU、CPU/内存和磁盘压测的独立报告与串行语义。极限压测 SHALL 作为独立的无磁盘原子验证，不得混入常规套件结果。

#### Scenario: 先后运行两种压测
- **WHEN** 同一服务器先后运行常规压测和极限压测
- **THEN** 系统分别保留常规子报告和极限组合结论
