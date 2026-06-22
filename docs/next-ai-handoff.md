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

- 已完成：阶段 13A / 13B / 13C / 13D
- 当前阶段：**14A 服务器健康状态增强**

14A 当前目标：
- `online / offline / unknown` 状态
- `last_check_at`
- `last_error`
- OS / CPU / 内存 / GPU / 磁盘摘要
- 服务器管理页展示
- 仪表盘服务器统计联动

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
37. 服务器探测与健康状态增强已开始并已完成后端主链路

## 5. 最近完成的 UI / 功能调整

- 新增服务器支持 `SSH Key / Password` 两种认证方式
- Password 登录服务器可执行“部署公钥”，成功后自动切换为 `SSH Key`
- 新增服务器表单不再手写私钥路径，改为从 `backend/keys/` 下拉选择
- 部署公钥弹窗文案已改为“SSH 密钥对”，明确只写远端 `~/.ssh/authorized_keys`
- 任务历史与仪表盘最近任务已改为显示业务任务名，而不是只显示 `task_id`
- 服务器管理表格已多轮收口，正在继续处理操作列按钮完整显示与无横向滚动
- 14A 已新增 `last_check_at / last_error`，探测接口已支持 `/api/servers/{id}/probe`

## 6. 当前未提交文件摘要

当前工作区有后端、前端和文档改动，且存在新增未跟踪文件。重点包括：

- 后端健康探测与统计：
  - `backend/app/models/server.py`
  - `backend/app/db/database.py`
  - `backend/app/schemas/server.py`
  - `backend/app/schemas/detect.py`
  - `backend/app/api/servers.py`
  - `backend/app/api/dashboard.py`
  - `backend/app/schemas/dashboard.py`
  - `backend/app/api/ssh_keys.py`
  - `backend/app/schemas/ssh_key.py`
- 前端服务器管理 / 仪表盘 / 任务显示名：
  - `frontend/src/views/Servers.vue`
  - `frontend/src/components/ServerTable.vue`
  - `frontend/src/components/StatusTag.vue`
  - `frontend/src/views/Dashboard.vue`
  - `frontend/src/api/server.ts`
  - `frontend/src/api/dashboard.ts`
  - `frontend/src/utils/taskDisplay.ts`
  - `frontend/src/styles/global.css`
- 文档同步：
  - `README.md`
  - `docs/architecture.md`
  - `docs/development-stages.md`
  - `docs/mvp-acceptance.md`
  - `docs/progress.md`
  - `docs/next-ai-handoff.md`

注意：
- `frontend/tsconfig.tsbuildinfo` 当前有变更，通常不建议提交。
- `backend/keys/` 下真实私钥/公钥不要提交。

## 7. 当前需要继续处理的问题

优先完成 14A 服务器健康状态增强的收口：

1. 确认服务器探测字段是否完整
2. 确认服务器列表 UI 不出现横向滚动条
3. 确认操作列按钮完整显示
4. 确认探测失败时 `status=offline`、`last_error` 有值
5. 确认仪表盘 `online/offline` 统计联动
6. 跑 `compileall / npm build`
7. 再提交 14A

## 8. 下一步建议

- 先完成 14A 收口，不进入 14B
- 如果操作列仍然贴边，继续只改 `frontend/src/components/ServerTable.vue` 和 `frontend/src/styles/global.css`
- 如果健康探测 UI 还有显示问题，只改 `frontend/src/views/Servers.vue` / `Dashboard.vue`
- 后端探测安全边界不要再放宽

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
