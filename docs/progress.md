# HPCDeploy 项目进度记录

## 当前完成度

HPCDeploy 已形成完整闭环，端到端链路全部打通：

```
服务器管理（含标签筛选/健康探测/一键部署公钥）
→ 脚本/模板选择
→ 多服务器任务执行
→ 实时日志 + 实时监控
→ 结果文件回收与下载
→ 失败诊断
→ 审计日志
→ 清理中心
```

---

## 已完成重点功能

### 服务器管理
- CRUD、SSH 测试、SSH Key / Password 登录
- 一键部署公钥（Password → SSH Key 切换）
- 服务器健康探测、探测全部（默认跳过离线，3s timeout）
- **标签管理**：标签添加/编辑/删除、标签列展示、标签筛选、标签统计（含在线/离线计数）

### 任务执行
- test / stress / mpi / install 白名单脚本执行
- stress 参数化（时长参数 + 白名单校验）
- 任务模板/执行预设（9 个模板一键填充）
- 批量任务执行（多选服务器，独立线程，离线跳过）
- 任务取消（PID→PGID→SIGTERM/SIGKILL + 远端目录清理）
- 任务删除（清理 artifacts / 远端目录 / 日志 / 记录）
- 任务历史筛选/搜索/分页
- 任务失败诊断（GPU/CUDA/SSH/磁盘/路径错误识别）
- 进度可视化：中文状态标签、运行耗时 HH:mm:ss、进度条、预计剩余

### 实时日志
- WebSocket 主通道（心跳 30s、断线自动 HTTP 轮询备用）
- HTTP 轮询备用通道
- 日志下载（task_id.log 格式）

### 实时监控
- CPU/内存结构化卡片网格（CPU 使用率 / Load Average / 内存）
- 磁盘挂载点 el-table 展示（总容量/已用/可用/使用率进度条）
- GPU 卡片列表展示（利用率/显存/温度）
- 5s 轮询，子系统隔离

### Apptainer
- .sif 文件上传（不执行 run/exec）
- 单台+批量多线程分发（SFTP）
- Apptainer 镜像目录只读查看

### 清理中心
- 本地结果文件按 task 目录聚合查看与批量删除
- Apptainer 镜像目录只读查看
- 远端单台/全部在线服务器临时目录扫描与清理
- 清理 target 白名单：只允许 tasks / downloads / tmp

### 系统设置
- SSH 默认私钥设置
- 远端目录只读说明
- 生成默认 SSH 密钥

### 审计日志
- 关键操作记录：任务创建/删除/取消/诊断、压测套件创建、清理、设置保存、服务器增删改/探测/SSH 测试/公钥部署
- 分页查询、按操作类型/对象类型/状态/关键词筛选
- **统一英文 action 命名 + 前端中文标签映射**
- **所有调用点补全 `detail_json` 结构化上下文**
- **敏感字段自动过滤**（password/private_key/token/command/raw_shell/raw_args/env）
- **新增 `server_id` 字段**
- 不记录密钥内容

### 仪表盘
- 服务器总数/在线/离线统计
- 任务运行/等待/取消/成功/失败/已取消统计
- 结果文件归档目录数量和占用空间
- 8 个快捷操作按钮
- 最近任务行点击跳转任务历史
- 结果文件目录树查看

### 管理员密码确认式高风险操作保护（Phase 26 — 当前阶段）
- 移除用户账号体系（User 模型、login/logout/me 端点、登录页）
- 替换为管理员密码确认弹窗（ElMessageBox.prompt）
- 5 分钟 admin_token 缓存（内存，不存 localStorage）
- 高风险接口通过 `X-Admin-Token` header 保护
- 管理员密码通过 `HPCDEPLOY_ADMIN_PASSWORD` 环境变量配置
- 侧边栏菜单 admin 标签标记

---

## 最近完成事项

1. **管理员密码确认式高风险操作保护** — 移除账号登录体系，高风险操作（删除/清理/审计日志/设置保存/SSH 密钥生成）通过密码确认弹窗保护。
2. **取消分组，只保留标签** — 所有 `group_name` 相关功能已移除
3. **修复编辑服务器标签不显示** — 根因：Pydantic from_attributes 不读取 hybrid_property，修复：ServerRead 增加 model_validator 显式解析 tags_json
4. **标签全链路打通** — 标签列展示、标签筛选、任务执行页标签筛选、清理中心标签筛选、标签统计含在线/离线计数
5. **任务执行页进度右移** — 进度信息移到右侧实时面板顶部
6. **实时监控结构化展示** — CPU/内存/磁盘/GPU 5s 轮询卡片展示
7. **SSH 执行器重连机制** — `SSHExecutor.reconnect()` 自动重连，`_execute_stress_async` 轮询中 SSH 闪断自动重连一次再试
8. **批次视图总耗时列** — 后端计算 `duration_seconds`，前端展示 `1h 23m 45s` 格式
9. **取消/超时远端文件不删除** — 确认 `TaskCancelRequest.delete_remote_files` 默认 `False`，超时/失败流程无自动远程目录清理
7. **清理中心布局优化** — 远端优先、本地次之的重排
8. **WebSocket 实时日志** — 双通道日志推送，心跳 30s，断线自动 HTTP 轮询
9. **审计日志全面完善** — 统一英文 action 命名、全调用点 detail_json 上下文、敏感字段过滤、新增 server_id
10. **批次视图展开状态修复** — 自动刷新不再折叠已展开行，通过 `:expand-row-keys` + `toggleRowExpansion` 恢复

---

## 当前暂未做

- WebSocket 多进程广播
- 自动定时清理
- 外部 AI API / AI 小助手
- 调度器集群集成（Slurm 等）
- 可配置远端任务根目录

---

## 下一步优先级

1. **WebSocket 多进程广播** — 当前 WS 连接仅在单进程生效，多 uvicorn worker 时日志推送会丢失
2. **自动定时清理** — 远端任务目录自动清理策略
3. **外部 AI API / AI 小助手** — 接入 AI 辅助诊断

---

## 明天继续的明确入口

1. 先读 `README.md`、`docs/architecture.md`、`docs/development-stages.md`、`docs/progress.md`
2. 当前阶段已经完成的是：管理员密码确认式高风险操作保护
3. 下一阶段：WebSocket 多进程广播
4. 不要做强制全站登录、复杂 RBAC、多用户管理
5. 修改后必须跑 `compileall` + `npm run build`
6. 前端不传 raw command / raw_args / remote_path / remote_work_dir
7. 高风险操作的所有 API 已经通过 `require_admin_token()` 依赖保护

---

## Next Session Prompt

```
继续 HPCDeploy 项目。
请先读取 README.md、docs/progress.md、docs/development-stages.md、docs/architecture.md。
当前下一阶段是：WebSocket 多进程广播。
不要做强制全站登录。
不要做复杂 RBAC。
不要做多用户管理。
普通访客默认可正常使用平台。
只有删除、清理、审计日志、系统设置保存、生成 SSH 密钥等高风险操作需要管理员密码确认。
前端不要传 raw command / raw_args / remote_path / remote_work_dir。
不要 git add .
不要 git commit，除非我明确要求。
```
