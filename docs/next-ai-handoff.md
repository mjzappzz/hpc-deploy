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

- 已完成：阶段 1~12B / 13A / 13B / 13C / 13D / **14A / 14B / 15A / 16A / 17A**
- 当前阶段：**14B 收口 + 文档同步**

已完成的里程碑：
- **14A** 服务器健康状态增强（status/last_check_at/last_error/资源摘要）
- **14B** 探测全部性能优化（并发 ThreadPoolExecutor，include_offline 参数，SSH timeout 10→3s，合并探测脚本为单次 exec_command）
- **15A** 脚本参数化增强（stress 参数白名单校验，禁止危险参数键）
- **16A** 脚本任务模板/执行预设（9 个模板，自动填充脚本类型/路径/参数）
- **17A** 批量任务执行（多选服务器，独立 task_id/独立线程，部分成功，并发启动，离线跳过）

## 4. 当前已完成功能

1. 服务器管理
2. SSH 测试
3. SSH Key 登录
4. Password 登录
5. 通过密码登录后一键部署公钥
6. 部署公钥后切换为 SSH Key 登录
7. SSH 私钥/密钥对从 `backend/keys/` 选择
8. `GET /api/ssh-keys` 只返回密钥元信息，不返回私钥/公钥内容
9. 脚本知识库
10. test 脚本执行
11. stress 压测执行
12. stress 结果文件回收下载
13. Apptainer `.sif` 分发
14. `mpi_env_test.sh` 轻量执行
15. `install_oneapi_2022.sh` 白名单执行
16. `install_openmpi_4.1.6_aocc_aocl.sh` 白名单执行
17. 实时日志
18. 日志下载
19. 复制环境变量命令
20. 复制验证命令
21. stderr 日志等级优化为 `STDERR/WARN`
22. 同服务器防重复提交
23. 运行中任务取消
24. 取消后清理远端工作目录
25. 取消后按白名单清理远端临时下载目录
26. 删除终态任务
27. 删除任务时清理 `artifacts / remote_work_dir / task_logs / task`
28. 任务历史筛选 / 搜索 / 分页
29. 任务显示名格式：`客户名 · 模块 · 脚本名 · 日期`
30. 仪表盘数据化
31. 仪表盘快捷操作
32. 仪表盘最近任务点击跳转任务历史
33. 结果文件归档统计
34. 结果文件归档目录树查看
35. 全局布局与导航视觉优化
36. 服务器管理表格 UI 调整
37. 服务器探测与健康状态增强（status/last_check_at/last_error/资源摘要）
38. **14B：探测全部并发优化** — ThreadPoolExecutor 并发，include_offline 跳过离线，SSH timeout 3s，合并探测脚本为单次 exec_command
39. **15A：stress 参数化白名单** — duration_seconds/interval/workers/memory_percent 白名单校验，禁止 command/raw_args/shell
40. **16A：任务模板/预设** — 9 个模板，选择后自动填充脚本类型/路径/参数
41. **17A：批量执行** — 多选服务器，独立 task_id/独立线程（非 BackgroundTasks），部分成功不阻塞，离线服务器跳过

## 5. 最近完成的 UI / 功能调整

- 新增服务器支持 `SSH Key / Password` 两种认证方式
- Password 登录服务器可执行“部署公钥”，成功后自动切换为 `SSH Key`
- 新增服务器表单不再手写私钥路径，改为从 `backend/keys/` 下拉选择
- 部署公钥弹窗文案已改为“SSH 密钥对”，明确只写远端 `~/.ssh/authorized_keys`
- 任务历史与仪表盘最近任务已改为显示业务任务名，而不是只显示 `task_id`
- 服务器管理表格已多轮收口，正在继续处理操作列按钮完整显示与无横向滚动
- 14A 已新增 `last_check_at / last_error`，探测接口已支持 `/api/servers/{id}/probe`

## 6. 当前未提交文件摘要

当前工作区覆盖 14B（probe-all 并发优化）到 17A（批量执行）的全部改动。重点包括：

- **14B 探测全部并发优化**：
  - `backend/app/core/ssh_detector.py` — 合并为单次 exec_command + section 解析 + 3s timeout
  - `backend/app/core/ssh_tester.py` — 同步使用 DEFAULT_DETECT_TIMEOUT=3
  - `backend/app/schemas/detect.py` — 加 skipped/probed/timings/elapsed_seconds 字段
  - `backend/app/api/servers.py` — ThreadPoolExecutor 并发 + include_offline 参数 + 完整 timing 日志
  - `frontend/src/api/server.ts` — 类型同步 + includeOffline 参数
  - `frontend/src/views/Servers.vue` — checkbox + 跳过提示 + loading 修复
  - `frontend/src/components/ServerTable.vue` — loading 逻辑修复（只实际探测的行 loading）

- **16A 任务模板**：
  - `frontend/src/constants/taskTemplates.ts` — 9 个模板定义
  - `frontend/src/views/TaskRunner.vue` — 模板选择器 UI + 自动填充参数

- **17A 批量执行**：
  - `backend/app/api/tasks.py` — batch 端点 + Thread 并发 + 离线跳过
  - `backend/app/schemas/task.py` — BatchTaskCreate 请求/响应 schema
  - `frontend/src/api/task.ts` — batchRunTask API
  - `frontend/src/views/TaskRunner.vue` — 多选服务器 + 批量确认弹窗 + 结果展示

- 文档同步：
  - `README.md`
  - `docs/progress.md`
  - `docs/next-ai-handoff.md`

注意：
- `frontend/tsconfig.tsbuildinfo` 当前有变更，通常不建议提交。
- `backend/keys/` 下真实私钥/公钥不要提交。

## 7. 当前需要继续处理的问题

14B / 16A / 17A 均已完成后端主链路 + 前端 UI。当前状态：

- probe-all 默认跳过 offline 并发执行，默认总耗时 < 1s
- 9 个任务模板可正常填充
- 批量执行多选服务器正常
- 后端 compileall ✅，前端 npm run build ✅
- 文档已收口

待后续阶段推进：
- 18 批量 Apptainer 分发
- 19 远端空间清理策略
- 20 用户权限
- 21 审计日志
- 22 AI 失败日志分析
- 23 WebSocket 实时日志

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
