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

### 管理员密码确认式高风险操作保护（Phase 26）
- 移除用户账号体系（User 模型、login/logout/me 端点、登录页）
- 替换为管理员密码确认弹窗（ElMessageBox.prompt）
- 5 分钟 admin_token 缓存（内存，不存 localStorage）
- 高风险接口通过 `X-Admin-Token` header 保护
- 管理员密码通过 `HPCDEPLOY_ADMIN_PASSWORD` 环境变量配置
- 侧边栏菜单 admin 标签标记

### WebSocket 多进程广播（Phase 28 — 已完成）
- WebSocket 连接所在 worker 每秒 tail 数据库 `task_logs`
- 状态变化从数据库补发 `status`，终态补发 `done`
- 同进程内仍保留 `ws_manager` 即时广播
- 不引入 Redis / Celery，不改变前端协议和 HTTP 轮询备用链路

### 稳定性与交互优化（Phase 28B — 已完成）
- stress-suite 同服务器串行锁，严格按 GPU → CPU/内存 → 磁盘推进
- 后台启动成功仅表示任务进入 RUNNING，suite 调度只在任务终态后推进
- stress 远端启动后立即写 RUNNING / started_at，避免远端已跑但页面仍 PENDING
- 失败、取消、超时任务只要 artifacts 已回收即可显示结果文件入口
- 审计日志进入页面不再自动弹管理员确认，点击“查看审计日志”后再确认
- 管理菜单移动到底部区域，服务器管理和任务执行页做表格/卡片/日志弹窗交互优化
- GPU 压测报告脚本支持多卡元数据、每卡统计和 XLSX 报告

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
10. **WebSocket 多进程广播** — WS endpoint 主动 tail 数据库日志和任务状态，多 uvicorn worker 下可补发日志与终态
11. **清理中心布局优化** — 远端优先、本地次之的重排
12. **WebSocket 实时日志** — 双通道日志推送，心跳 30s，断线自动 HTTP 轮询
13. **审计日志全面完善** — 统一英文 action 命名、全调用点 detail_json 上下文、敏感字段过滤、新增 server_id
14. **批次视图展开状态修复** — 自动刷新不再折叠已展开行，通过 `:expand-row-keys` + `toggleRowExpansion` 恢复
15. **stress-suite 串行调度修复** — 同服务器加锁，后续子任务只在前序任务终态后启动，后台启动成功不再被误判为完成
16. **任务结果入口修复** — 失败/取消任务 artifacts 可见时显示结果文件，结果弹窗显示远端服务器目录
17. **任务历史跳转定位修复** — 压测套件弹窗“查看批次详情”跳转批次视图、自动搜索并展开 batch
18. **任务执行页压测脚本选择优化** — 压测脚本统一多选，选 1 个走单任务，选 2/3 个自动按 GPU→CPU/内存→磁盘创建套件
19. **服务器管理 UI 优化** — 部署公钥外置、表格列宽重分配、标签选择后自动收起、新增服务器默认密码认证
20. **日志查看体验优化** — 下载日志并入查看日志弹窗，去除日志工具栏白色间隙
21. **侧边栏与审计日志体验优化** — 审计日志/系统设置/清理中心下移到底部管理区，审计日志延迟管理员确认
22. **GPU 多卡报告脚本更新** — GPU 压测脚本按卡统计利用率、温度、功耗、显存，输出 TXT/XLSX 报告

---

## 当前暂未做

- 自动定时清理
- 外部 AI API / AI 小助手
- 调度器集群集成（Slurm 等）
- 可配置远端任务根目录

---

## 下一步优先级

1. **自动定时清理** — 远端任务目录自动清理策略
2. **外部 AI API / AI 小助手** — 接入 AI 辅助诊断

---

## 明天继续的明确入口

1. 先读 `README.md`、`docs/architecture.md`、`docs/development-stages.md`、`docs/progress.md`
2. 当前阶段已经完成的是：WebSocket 多进程广播 + 稳定性与交互优化
3. 下一阶段：自动定时清理
4. 不要做强制全站登录、复杂 RBAC、多用户管理
5. 修改后必须跑 `compileall` + `npm run build`
6. 前端不传 raw command / raw_args / remote_path / remote_work_dir
7. 高风险操作的所有 API 已经通过 `require_admin_token()` 依赖保护

---

## Next Session Prompt

```
继续 HPCDeploy 项目。
请先读取 README.md、docs/progress.md、docs/development-stages.md、docs/architecture.md。
当前下一阶段是：自动定时清理。
不要做强制全站登录。
不要做复杂 RBAC。
不要做多用户管理。
普通访客默认可正常使用平台。
只有删除、清理、审计日志、系统设置保存、生成 SSH 密钥等高风险操作需要管理员密码确认。
前端不要传 raw command / raw_args / remote_path / remote_work_dir。
不要 git add .
不要 git commit，除非我明确要求。
```
