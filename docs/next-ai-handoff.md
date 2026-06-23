# HPCDeploy AI Handoff

> 下一个 AI 进入项目后，优先读本文件，再看 `docs/progress.md` 和 `docs/architecture.md`。

## 1. 项目一句话定位

HPCDeploy 是一个面向 HPC 运维的轻量级脚本执行控制台，提供服务器接入、白名单脚本执行、日志与结果回收、任务管理和仪表盘总览。

## 2. 技术栈

| 模块 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Element Plus |
| 后端 | FastAPI + SQLAlchemy + Paramiko |
| 数据库 | SQLite |
| 部署 | systemd |

## 3. 当前阶段

- 已完成：阶段 1~24B（完整链路全部完成）
- 当前阶段：**24B 收口 + 文档同步**

已完成的里程碑：
- **14A~17A** 服务器健康 / 探测全部 / 参数化 / 模板 / 批量
- **18A** 应用密码探测处理（SSH 密码过期 / 探测忽略 Password 服务器）
- **19A** SSH 连接健壮性（重试+退避+超时）
- **20A** 任务白名单 UI 检查与提示
- **21A** 批量 Apptainer 分发
- **22A** AI 任务日志诊断（根据日志匹配失败模式）
- **23A** WebSocket 实时日志推送（双通道：WS 主 + HTTP 轮询备）
- **24A** 任务执行体验优化（中文状态标签 / 运行耗时 / 进度条 / 诊断展示）
- **24B** 任务执行页布局优化 + 实时监控 Tab 结构化展示

## 4. 当前已完成功能

1. 服务器管理（CRUD + SSH 测试 + 信息探测）
2. SSH Key / Password 两种登录方式
3. 通过密码登录后一键部署公钥，切换为 SSH Key
4. SSH 私钥/密钥对从 `backend/keys/` 选择
5. `GET /api/ssh-keys` 只返回密钥元信息，不返回私钥/公钥内容
6. 脚本知识库（四类分类目录，上传/下载/预览/删除）
7. test 脚本执行（bash ./script.sh）
8. stress 压测执行（带时长参数 + 资源快照）
9. stress 结果文件回收下载
10. mpi 白名单脚本执行（mpi_env_test.sh / OneAPI / OpenMPI）
11. Apptainer `.sif` 分发（不做 run/exec）
12. 实时日志（WebSocket + HTTP 轮询双通道）
13. 日志下载（task_id.log 格式）
14. 复制环境变量命令 / 复制验证命令
15. stderr 日志等级优化为 `STDERR/WARN`
16. 同服务器防重复提交
17. 运行中任务取消（PID→PGID 进程组终止 + 远端目录清理）
18. 取消后按白名单清理远端临时下载目录
19. 删除终态任务（清理 artifacts / remote_work_dir / task_logs / task）
20. 任务历史筛选 / 搜索 / 分页
21. 任务显示名格式：`客户名 · 模块 · 脚本名 · 日期`
22. 仪表盘数据化总览（服务器/任务/归档统计）
23. 仪表盘快捷操作（8 个导航按钮）
24. 仪表盘最近任务行点击跳转任务历史
25. 结果文件归档目录树查看（el-drawer + el-tree）
26. 全局布局与导航视觉优化（sidebar/topbar/content 对齐）
27. 服务器健康状态增强（status/last_check_at/last_error/资源摘要）
28. 探测全部并发优化（ThreadPoolExecutor + include_offline + 3s timeout + 合并探测脚本）
29. stress 参数化白名单（禁止 command/raw_args/shell/raw_command）
30. 任务模板/预设（9 个模板一键填充脚本类型/路径/参数）
31. 批量执行（多选服务器，独立 task_id/独立线程，部分成功，离线跳过）
32. 应用密码探测处理（SSH 密码过期 / 探测忽略 Password 服务器）
33. SSH 连接健壮性（重试+退避+超时参数化）
34. 任务白名单 UI 检查与提示
35. 批量 Apptainer 分发
36. **AI 任务日志诊断**（根据日志匹配失败模式，给出可能原因与建议）
37. **WebSocket 实时日志**（双通道：WS 主 + HTTP 轮询备，断线自动切换）
38. **进度可视化**（中文状态标签、运行耗时 HH:mm:ss、预计剩余、进度条 el-progress）
39. **诊断结果展示**（失败任务自动显示诊断摘要弹窗）
40. **监控结构化展示**（CPU/内存 4 卡片网格 + 磁盘挂载点表格 + GPU 卡片列表 + 5s 轮询）

## 5. 最近完成的 UI / 功能调整

- **22A AI 诊断**：`POST /api/tasks/{task_id}/diagnose` → 返回结构化诊断（级别/类别/标题/摘要/可能原因/建议/日志证据）
- **23A WebSocket**：`/ws/tasks/{task_id}` 双通道日志推送，前端 `useTaskWebSocket` composable，心跳 30s，HTTP 轮询备用
- **24A 体验优化**：
  - 中文状态标签（等待中/连接中/准备中/上传中/运行中等）
  - 运行耗时 HH:mm:ss 动态显示（now timer 每秒刷新）
  - 压测任务进度条（elapsed / duration * 100）和预计剩余时间
  - 任务历史卡片显示耗时+进度条+错误信息
  - 失败任务诊断摘要弹窗
  - WebSocket 连接状态指示标签（已连接/已断开）
- **24B 布局+监控**：
  - 左侧”执行进度”组移除，进度信息右移到实时面板顶部
  - 右侧面板 meta 栏（name|id|status|time）替换为进度状态栏（任务名+阶段+耗时+剩余+进度条）
  - CPU/内存 → 4 卡片网格（CPU 使用率/Load Average/内存总容量/内存使用）
  - 磁盘 → el-table 展示挂载点信息（总容量/已用/可用/使用率进度条）
  - GPU → 卡片列表（名称/利用率/显存/温度），无 GPU 显示空状态
  - 所有监控数据 5s 轮询 GET 接口，不接收前端参数
  - 修复 el-tabs 白色背景横条

## 6. 当前未提交文件摘要

当前工作区覆盖从 14B 到 24B 的全部改动。重点包括：

- **18A~21A**：密码探测 / SSH 健壮性 / 白名单检查 / 批量 Apptainer
- **22A AI 诊断**：
  - `backend/app/core/diagnosis.py` — 失败模式规则引擎
  - `backend/app/schemas/diagnosis.py` — 诊断 schema
  - `backend/app/api/diagnosis.py` — 诊断 API 端点
  - `frontend/src/api/diagnosis.ts` — 前端 API
  - `frontend/src/views/TaskRunner.vue` — 诊断弹窗

- **23A WebSocket**：
  - `backend/app/core/ws_manager.py` — 连接管理器（心跳 30s + 清理）
  - `backend/app/api/tasks.py` — `/ws/{task_id}` 端点
  - `frontend/src/composables/useTaskWebSocket.ts` — composable（断线自动 HTTP 备用）
  - `frontend/src/views/TaskRunner.vue` — WS 集成

- **24A 体验优化**：
  - `frontend/src/composables/useTaskProgress.ts` — 进度计算工具函数
  - `frontend/src/views/TaskRunner.vue` — 状态标签/计时器/进度条/诊断集成
  - `frontend/src/components/TaskCard.vue` — 卡片进度条/耗时显示
  - `frontend/src/components/StatusTag.vue` — 中文状态标签

- **24B 布局+监控**：
  - `backend/app/schemas/task.py` — MonitorCpuMemory/MonitorDisk/MonitorGpu/TaskMonitorResponseStructured
  - `backend/app/api/tasks.py` — `_exec_monitor_cmd/_parse_cpu_memory/_parse_disk/_parse_gpu` + `GET /{task_id}/monitor`
  - `frontend/src/api/task.ts` — `getTaskMonitor()` API + 类型定义
  - `frontend/src/views/TaskRunner.vue` — 进度状态栏 + 结构化监控 Tab + 5s 轮询

- 文档同步：
  - `README.md`
  - `docs/architecture.md`
  - `docs/progress.md`
  - `docs/development-stages.md`
  - `docs/mvp-acceptance.md`
  - `docs/next-ai-handoff.md`

注意：
- `frontend/tsconfig.tsbuildinfo` 当前有变更，通常不建议提交。
- `backend/keys/` 下真实私钥/公钥不要提交。

## 7. 当前需要继续处理的问题

阶段 1~24B 的完整主链路全部完成。后端 compileall ✅，前端 npm run build ✅。

待后续阶段推进：
- 25 远端空间清理策略
- 26 用户权限
- 27 审计日志

## 8. 下一步建议

- 按后续阶段方向依次推进
- 如果进入新阶段，先跑 `python3 -m compileall backend/app backend/main.py && cd frontend && npm run build`
- 新阶段开始前确认后端使用 `uvicorn main:app --reload` 启动，避免进程缓存旧代码

## 9. 禁止事项

1. 不要修改任务执行逻辑
2. 不要修改取消任务逻辑
3. 不要修改删除任务逻辑
4. 不要修改真实安装脚本
5. 不要修改 mpi 白名单
6. 不要执行真实安装任务
7. 不要删除数据库
8. 不要删除 artifacts
9. 不要让前端传 command / remote_path / local_path / PID
10. 不要返回私钥内容
11. 不要返回公钥内容
12. 不要执行任意远程命令
13. 不要执行 `apptainer run / exec`
14. 不要修改 `sshd_config`
15. 不要重启 `sshd`
16. 不要执行远端 `systemctl / reboot / shutdown`

## 10. Git 提交注意事项

- 不要 `git add .`
- 不要提交：
  - `backend/data/*.db`
  - `backend/data/artifacts/`
  - `backend/apptainer/*.sif`
  - `backend/keys/*`
  - `.env`
  - `node_modules/`
  - `.venv/`
  - `.deps/`
  - `*.log`
  - `dist/`
- 如需保留 `backend/keys/` 空目录，可后续补：
  - `.gitignore` 中忽略 `backend/keys/*`
  - 仅提交 `backend/keys/.gitkeep`
