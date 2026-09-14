## ADDED Requirements

### Requirement: 常规与极限压测相互隔离

系统 SHALL 保持常规 GPU、CPU/内存和磁盘压测的独立报告与串行语义。极限压测 SHALL 作为独立的无磁盘原子验证，不得混入常规套件结果。

#### Scenario: 先后运行两种压测
- **WHEN** 同一服务器先后运行常规压测和极限压测
- **THEN** 系统分别保留常规子报告和极限组合结论
