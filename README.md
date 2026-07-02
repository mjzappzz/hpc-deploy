# HPCDeploy

HPCDeploy 是一个面向 HPC 运维场景的轻量级自动化控制台，用于管理服务器、执行白名单脚本、分发 Apptainer 镜像、查看任务日志、回收结果文件、清理任务产物和审计操作。

## 技术栈

| 模块 | 技术 |
|------|------|
| 前端框架 | Vue 3 + Vite |
| 前端 UI | Element Plus |
| 前端路由 | Vue Router |
| 后端框架 | FastAPI |
| ORM | SQLAlchemy |
| 数据库 | SQLite |
| SSH 执行 | Paramiko |
| 实时日志 | WebSocket + HTTP 双通道 |

## 核心功能

- **服务器管理** — SSH 测试、SSH Key / Password 登录、一键部署公钥、默认 SSH 私钥设置、健康探测、探测全部（默认跳过离线）、标签管理、紧凑表格与表单交互优化
- **脚本知识库** — test / stress / mpi / install 白名单脚本，上传/下载/预览/删除
- **任务执行** — 单台/批量执行、stress 参数化、压测脚本多选自动套件、同服务器 GPU→CPU/内存→磁盘串行调度、MPI 白名单脚本、Apptainer .sif 只上传不分发执行
- **实时日志** — WebSocket 主通道 + HTTP 轮询备用，心跳 30s，断线自动切换
- **实时监控** — CPU/内存、磁盘、GPU 结构化卡片展示，5s 轮询
- **任务管理** — 取消（PID→PGID 进程组终止）、删除（清理 artifacts/远端目录/日志）、任务诊断（规则引擎，16 条规则，覆盖所有状态）、筛选/搜索/分页
- **结果文件** — 回收与下载（.log/.txt/.csv/.xlsx/.json）
- **清理中心** — 本地结果文件按 task 目录聚合、手动清理、自动清理本地旧报告、远端临时目录扫描与清理、Apptainer 镜像目录只读查看
- **Apptainer 分发** — .sif 文件上传、单台/批量分发、不执行 run/exec
- **审计日志** — 关键操作记录可追溯
- **系统设置** — SSH 默认私钥设置、远端目录只读说明、自动清理配置、管理员密码修改
- **仪表盘** — 服务器/任务/归档统计、快捷操作、最近任务跳转、结果文件目录树

## 当前阶段状态

当前阶段：**所有规划阶段已完成，项目进入维护期**。后续以修复缺陷、优化体验为主。

### 已完成（全部 29 个阶段已交付）

服务器管理、SSH 测试、服务器探测、脚本知识库、单任务执行、压测套件、GPU/CPU内存/Disk 独立任务、同服务器压测套件严格串行调度、批次视图、批次展开稳定、任务历史体验优化、失败/取消结果文件入口、报告/下载报告入口、批次报告聚合、CPU/内存长测 timeout 收口、GPU 多卡报告脚本、系统设置 SSH 密钥管理、脚本知识库最新修改时间、压测套件命令预览完整显示、管理员密码确认式高风险操作保护、审计日志延迟管理员确认、SSH 重连 + 批次耗时、WebSocket 多进程广播、服务器管理与任务执行页 UI 优化、本地报告自动清理、诊断引擎增强（16 条规则/状态分流/归因分类/风险提示）、诊断入口统一（所有任务状态）、管理员密码修改。

### 维护说明

所有核心功能已开发完成，不再规划大型新功能。后续以修复缺陷、优化使用体验为主，不引入新的功能阶段。

### 权限模型

- **不要强制全站登录** — 普通访客默认可正常使用平台
- **不要复杂 RBAC / 多用户管理**
- **高风险操作需要管理员密码确认**（对话弹窗输入密码，5 分钟 admin_token 缓存）

| 访客可操作 | 需要管理员密码确认 |
|------------|-------------------|
| 新增/编辑服务器、SSH 测试、探测 | 删除服务器、删除任务、删除脚本 |
| 执行任务、执行压测套件 | 清理本地 artifacts、清理远端目录 |
| 查看任务历史、查看日志、下载报告 | 查看审计日志、保存系统设置 |
| 查看脚本知识库 | 生成默认 SSH 密钥、修改管理员密码 |

## 启动命令

### 开发模式（热重载）

```bash
# 后端
cd ~/projects/hpc-deploy/backend
PYTHONPATH=.deps:. .deps/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd ~/projects/hpc-deploy/frontend
npm run dev
```

### 生产模式（systemd 服务）

```bash
# 重启后端（修改 Python 代码后必须重启）
sudo systemctl restart hpcdeploy-backend

# 重启前端（修改 Vue/前端代码后必须重启）
sudo systemctl restart hpcdeploy-frontend

# 查看状态
sudo systemctl status hpcdeploy-backend --no-pager -l
sudo systemctl status hpcdeploy-frontend --no-pager -l
```

> 修改代码后，必须通过 `systemctl restart` 重启对应服务才能生效。开发模式下可用 `--reload` 热重载避免手动重启。

## 构建验证

```bash
# 后端编译检查
python3 -m compileall backend/app backend/main.py

# 前端 TypeScript + 构建
cd frontend && npm run build
```

## 安全边界

- 前端不传 `command` / `raw shell` / `remote_path` / `raw_args`
- 前端不传 `remote_work_dir` — 远端工作目录由后端 `UUID` 生成，不绕过 `task_runner`
- 后端只执行白名单脚本（文件名白名单 + 目录校验）
- Apptainer 只上传/分发 `.sif`，不执行 `run` / `exec`
- SSH 私钥只保存文件名，不保存内容；API 不返回私钥/公钥内容
- 远端清理只允许 `tasks` / `downloads` / `tmp`，不清理 `$HOME/hpcdeploy/apptainer`
- 自动清理只作用于 `backend/data/artifacts` 本地任务结果目录，不清理远端目录、Apptainer 镜像、数据库、keys、scripts
- 路径防逃逸（`resolve()` + `startswith()`）
- 取消任务基于 PID 文件 + PGID 进程组终止，不依赖前端输入
- 部署公钥只写远端 `$HOME/.ssh/authorized_keys`，不覆盖、不修改 `sshd_config`、不重启 `sshd`
- 部署公钥按每台服务器自身 `auth_type` 独立认证登录，不固定同一私钥
- 密钥路径统一解析为 `KEYS_DIR` 下绝对路径，防止相对路径/CWD 问题
- 管理员密码通过 `HPCDEPLOY_ADMIN_PASSWORD` 环境变量设置，不返回前端、不打印日志
- 高风险接口通过 `X-Admin-Token` 5 分钟短期 JWT 保护

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 系统架构与技术设计（含权限模型） |
| [docs/development-stages.md](docs/development-stages.md) | 阶段开发计划与完成记录 |
| [docs/progress.md](docs/progress.md) | 项目当前进度与入口指引 |
