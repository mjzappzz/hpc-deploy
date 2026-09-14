# 极限压测 Specification

## Purpose

定义 GPU 与 CPU/内存组合负载的极限压测，使 HPCDeploy 能提供独立于常规压测的原子稳定性验证结论。

## Requirements

### Requirement: 极限压测是独立的无磁盘任务

系统 SHALL 将极限压测作为每台服务器的单一任务，固定包含 GPU 与 CPU/内存，不包含磁盘；常规压测的脚本选择和串行执行 SHALL 保持不变。

#### Scenario: 创建极限压测
- **WHEN** 操作员选择极限压测并提交任务
- **THEN** 系统创建一个 GPU 与 CPU/内存组合任务，且不创建磁盘任务

### Requirement: 极限压测同步且受安全边界保护

系统 SHALL 自动准备所需依赖，并在两个模块均 ready 后同步启动实际负载；启动偏差 SHALL 不超过 2 秒。CPU/内存模块 SHALL 保留至少 15% 物理内存；任一模块失败、超时或被取消时，系统 SHALL 停止整个组合任务。

#### Scenario: 模块发生异常
- **WHEN** GPU 或 CPU/内存模块在准备或运行中失败、超时或触发安全线
- **THEN** 系统停止另一模块并将极限任务标记为失败或取消

### Requirement: 极限压测提供原子结论和模块证据

仅当 GPU、CPU/内存和同步校验均通过时，极限压测整体 SHALL 为 PASS。系统 SHALL 保留总结果、两个模块的报告和原始日志供下载。

#### Scenario: 查看完成的极限压测
- **WHEN** 操作员打开已完成的极限压测
- **THEN** 系统显示整体结果、模块结果和同步偏差，并提供相关证据下载
