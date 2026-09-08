## MODIFIED Requirements

### Requirement: High-risk operations require scoped administrator authorization

系统 SHALL 在授予管理员权限前于服务端验证管理员密码，并对受保护的设置、资产、清理、归档和审计操作要求有效且绑定浏览器标签页的管理员令牌。系统 SHALL NOT 提供临时、开发或环境开关控制的无密码管理员授权路径。设置接口 SHALL NOT 返回密码值。

#### Scenario: A protected request has no valid administrator authority
- **WHEN** 调用方在没有有效作用域令牌的情况下访问受保护端点
- **THEN** 端点拒绝该请求，且不发生受保护的变更

#### Scenario: An administrator changes the password
- **WHEN** 当前密码已验证且新密码满足策略
- **THEN** 系统更新凭据，且任何设置响应均不暴露其明文

#### Scenario: A caller attempts passwordless temporary administrator authorization
- **WHEN** 调用方尝试使用旧的临时管理员授权入口或任何未提供管理员密码的授权路径
- **THEN** 系统不签发管理员会话，且调用方不能获得受保护操作权限
