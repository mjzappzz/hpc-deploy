## Purpose

Define the managed-server inventory and connectivity capability so operators can safely register Linux/HPC hosts, establish their access posture, and maintain trustworthy hardware and availability information.

## Requirements

### Requirement: Server records preserve a unique management target

The system SHALL create, read, update, archive, restore, and delete server records containing the SSH endpoint, authentication mode, and operator-facing inventory metadata. A live server host SHALL not be registered twice, and archive state SHALL be changed only through the dedicated archive operations.

#### Scenario: An operator attempts to add a duplicate host
- **WHEN** a create request uses a host already present in the active inventory
- **THEN** the request is rejected with the existing server identity and no duplicate record is written

#### Scenario: An operator archives a server
- **WHEN** an administrator archives a managed server
- **THEN** the server is frozen for operational use and its displayed connectivity state becomes unknown until it is restored

### Requirement: Connectivity and hardware state are evidence-based

The system SHALL test SSH connectivity, probe hardware, expose tag summaries, and support public-key inspection and deployment using each server's configured authentication method. A failed or partial probe SHALL not replace the last complete hardware inventory.

#### Scenario: GPU probing is incomplete after a server reconnects
- **WHEN** OS, CPU, memory, or disk probing cannot complete together with the GPU portion
- **THEN** the system records the current connectivity outcome but preserves the last complete hardware inventory

#### Scenario: Public key deployment targets multiple servers
- **WHEN** an operator deploys the managed public key to eligible servers
- **THEN** each target is authenticated independently, already-present keys are not duplicated, and one failure does not prevent other targets from being processed

### Requirement: SSH 主机身份须经确认并持续校验

系统 SHALL 在首次密码或密钥连接受管服务器时获取并向操作员展示 SSH 主机指纹；仅在操作员确认后保存为该服务器的受信身份。后续探测、公钥部署和任务连接 SHALL 校验当前指纹与已确认指纹一致；不一致时 SHALL 阻断会产生远端操作的请求，并说明身份变更。

#### Scenario: 首次连接服务器
- **WHEN** 操作员以有效认证信息首次连接尚无受信 SSH 指纹的服务器
- **THEN** 系统展示当前指纹并在操作员确认前不执行探测以外的远端变更或任务下发

#### Scenario: 已登记服务器的指纹发生变化
- **WHEN** 系统连接到与已保存指纹不一致的 SSH 服务
- **THEN** 系统拒绝公钥部署和任务执行，记录身份变化，并要求操作员显式确认更新后才能恢复远端操作

### Requirement: 密码接入兼容且可在密钥验证后清除

系统 SHALL 保持密码认证用于首次接入、探测和公钥部署。平台公钥部署后，系统 SHALL 支持验证密钥认证；验证成功后，操作员 SHALL 能选择仅清除该服务器在平台保存的密码，而不修改远端账户密码或已部署公钥。

#### Scenario: 密码接入后切换密钥认证
- **WHEN** 操作员通过密码认证完成公钥部署且密钥连接验证成功
- **THEN** 系统提示可切换为密钥认证并可选清除平台留存密码

#### Scenario: 清除留存密码
- **WHEN** 操作员对已验证密钥认证的服务器确认清除密码
- **THEN** 系统删除该服务器保存的密码，保留服务器记录、远端公钥和密钥认证配置
