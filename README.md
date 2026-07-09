# HPCDeploy

HPCDeploy 是一个面向 HPC 运维场景的轻量级自动化控制台，用于管理 Linux 服务器、执行白名单脚本、分发 Apptainer 镜像、查看任务日志、回收结果文件、清理任务产物和审计操作。

## 最近更新

> 2026-07-09

- **煤球精灵系统** — 全局卡片边缘小煤球，IntersectionObserver 驱动，自动出现在视口卡片上。唯一名字 + 6 种性格独立吐槽 + 同卡双煤球对话
- **SSH 测试+探测合并** — 工具栏/表格行/详情抽屉统一为"检测"按钮，SSH 通过后自动探测基本信息
- **OS 信息可视化** — 服务器卡片和表格中 OS 列改用彩色标签（Linux🟢/Windows🔵）
- **离线服务器折叠** — 服务器管理页离线组默认收缩，点击展开
- **任务执行页优化** — 去除右侧滚动条，④ 配置区间距缩小
- **取消文案分层** — 单任务/批次取消弹窗按"标的+结果"结构化展示
- **搜索重置修复** — 点重置后刷新不再回滚到筛选状态
- 完整变更见 `docs/progress.md`

## 版本定位

当前标签定位为 **v1.02 Linux 版**：

- 当前支持对象：Linux / HPC 服务器
- 当前执行方式：基于 SSH 下发脚本到远端服务器，并在远端 Linux 环境执行
- 当前压测能力：GPU、CPU/内存、磁盘压测脚本与报告回收
- 当前部署方式：systemd 开发服务模式

暂未支持但已纳入后续路线：

- Windows Server 远程执行、脚本适配、结果回收
- Docker / Compose 容器化部署
- 更完整的生产部署形态，例如 Nginx 静态托管前端、后端独立服务、数据库外置化

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

- **服务器管理** — SSH 测试、SSH Key / Password 登录、一键部署公钥、缺省密钥自动生成引导、健康探测、探测全部（默认跳过离线）、**标签内联编辑**（表格内点击直接修改）、紧凑表格与表单交互优化，顶部操作按钮按常用顺序收口
- **脚本知识库** — 服务器环境 / 服务器压测 / Apptainer 白名单文件，上传/下载/预览/删除，预览支持复制脚本文本，路径展示绝对路径
- **任务执行** — 单台/批量执行、服务器压测参数化、服务器压测脚本多选/一键全选自动套件、同服务器 GPU→CPU/内存→磁盘串行调度、服务器环境白名单脚本、Apptainer .sif 只上传不分发执行
- **实时日志** — WebSocket 主通道 + HTTP 轮询备用，心跳 30s，断线自动切换
- **实时监控** — CPU/内存、磁盘、GPU 结构化卡片展示，5s 轮询
- **任务管理** — 统一历史任务（单次任务卡 + 批次任务聚合卡）、卡片式展示服务器/模块/远程目录/命令/计划时长/报告状态、批次详情展示完整子任务信息并自动刷新、取消（PID→PGID 进程组终止）、删除（清理 artifacts/远端目录/日志）、任务诊断（规则引擎，16 条规则，覆盖所有状态）、筛选/搜索/分页
- **结果文件** — 回收与下载（.log/.txt/.csv/.xlsx/.json）
- **运行数据管理** — 系统设置集中展示数据库、keys、脚本库、artifacts、备份、Apptainer、本机结果文件大小和路径；支持本机结果文件扫描、按任务/批次展示、删除后软隐藏历史、自动清理
- **Apptainer 分发** — .sif 文件上传、单台/批量分发、不执行 run/exec
- **审计日志** — 关键操作记录可追溯
- **系统设置** — 运行数据与路径、本机结果文件清理、自动清理配置、管理员密码弹窗修改
- **仪表盘** — 服务器/任务/归档统计、快捷操作、最近任务跳转，批次子任务带批次标记并跳转整批历史，结果文件目录树

## 当前阶段状态

当前阶段：**v1.02 Linux 版维护优化已完成，项目进入维护期**。后续以修复缺陷、优化体验为主；Windows 支持和 Docker 化作为后续版本规划，不属于当前 v1.02 范围。

### 已完成（全部 29 个阶段已交付）

服务器管理、SSH 测试、服务器探测、脚本知识库、单任务执行、压测套件、GPU/CPU内存/Disk 独立任务、同服务器压测套件严格串行调度、任务历史统一展示、批次任务聚合卡、失败/取消结果文件入口、报告/下载报告入口、批次报告聚合、CPU/内存长测 timeout 收口、GPU 多卡报告脚本、脚本知识库最新修改时间、压测套件命令预览完整显示、管理员密码确认式高风险操作保护、审计日志延迟管理员确认、SSH 重连 + 批次耗时、WebSocket 多进程广播、服务器管理与任务执行页 UI 优化、运行数据与路径集中展示、本机报告清理融合到系统设置、删除本机结果后历史软隐藏、诊断引擎增强（16 条规则/状态分流/归因分类/风险提示）、诊断入口统一（所有任务状态）、管理员密码弹窗修改。

### 维护说明

v1.02 Linux 版核心功能已开发完成。后续在 v1.02 标签快照基础上以修复缺陷、优化使用体验为主；Windows 支持、Docker 化和生产部署增强应在后续版本或独立功能分支中推进。

### 权限模型

- **不要强制全站登录** — 普通访客默认可正常使用平台
- **不要复杂 RBAC / 多用户管理**
- **高风险操作需要管理员密码确认**（对话弹窗输入密码，5 分钟 admin_token 缓存）

| 访客可操作 | 需要管理员密码确认 |
|------------|-------------------|
| 新增/编辑服务器、SSH 测试、探测 | 删除服务器、删除任务、删除脚本 |
| 执行任务、执行压测套件 | 清理本地 artifacts、清理远端目录 |
| 查看历史任务、查看日志、下载结果文件 | 查看审计日志、保存系统设置 |
| 查看脚本知识库 | 生成默认 SSH 密钥、修改管理员密码 |

## 启动命令

### 首次部署（远端新机器）

```bash
git clone <repo-url> hpc-deploy
cd hpc-deploy
sudo deploy/scripts/install_hpcdeploy_service.sh
```

安装脚本会自动完成：

- 检测并安装基础依赖：`python3`、`python3-venv`、`python3-pip`、`nodejs`、`npm`
- 识别当前项目路径，不要求固定在 `/home/tjzs/projects/hpc-deploy`
- 使用 `SUDO_USER` 作为 systemd 服务用户
- 创建 `backend/.deps` Python 虚拟环境并安装 `backend/requirements.txt`
- 执行 `frontend` 依赖安装
- 创建 `backend/data`、`backend/keys`、`backend/apptainer`
- 生成并安装 `/etc/systemd/system/hpcdeploy-backend.service`
- 生成并安装 `/etc/systemd/system/hpcdeploy-frontend.service`
- 启动后端 `127.0.0.1:8000` 和前端 `0.0.0.0:5173`

> 当前部署模式是开发模式复刻：后端由 systemd 运行 uvicorn，前端由 systemd 运行 Vite dev server。后续生产化/Docker 化时再切换为容器或 nginx 静态托管。

### 开发模式（热重载）

```bash
# 后端
cd /path/to/hpc-deploy/backend
PYTHONPATH=.deps:. .deps/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd /path/to/hpc-deploy/frontend
npm run dev
```

### 当前 systemd 开发服务

```bash
# 重启后端
sudo systemctl restart hpcdeploy-backend

# 重启前端 Vite dev server
sudo systemctl restart hpcdeploy-frontend

# 更新依赖并重启两个服务
sudo deploy/scripts/redeploy_hpcdeploy.sh

# 查看状态
sudo systemctl status hpcdeploy-backend --no-pager -l
sudo systemctl status hpcdeploy-frontend --no-pager -l
```

> 前端服务运行 `npm run dev -- --host 0.0.0.0 --port 5173`，支持 Vite HMR。访问地址默认为 `http://<server-ip>:5173`。

## 构建验证

```bash
# 后端编译检查
python3 -m compileall backend/app backend/main.py

# 前端 TypeScript + 构建
cd frontend && npm run build
```

## 关键目录与运行数据

### 本地项目关键目录

| 路径 | 用途 | 是否进入 Git |
|------|------|--------------|
| `backend/app/api/` | FastAPI API 路由层，处理服务器、任务、设置、清理、审计等接口 | 是 |
| `backend/app/core/` | 后端核心逻辑，包含 SSH 执行、任务调度、报告回收、诊断、恢复、批次导出 | 是 |
| `backend/app/models/` | SQLAlchemy 数据库模型 | 是 |
| `backend/app/schemas/` | Pydantic 请求/响应结构 | 是 |
| `backend/scripts/mpi/` | 编译环境/安装类白名单脚本库 | 是 |
| `backend/scripts/stress/` | GPU / CPU内存 / Disk 压测脚本库 | 是 |
| `backend/apptainer/` | Apptainer `.sif` 镜像存放目录 | 目录保留，`.sif` 不进 Git |
| `backend/keys/` | SSH 私钥/公钥存放目录 | 目录保留，密钥不进 Git |
| `backend/data/` | SQLite 数据库、任务结果、运行数据 | 不进 Git |
| `backend/data/artifacts/` | 后端从远端回收的报告、日志、CSV、XLSX 等结果文件 | 不进 Git |
| `frontend/src/views/` | 前端页面 | 是 |
| `frontend/src/components/` | 前端复用组件 | 是 |
| `frontend/src/api/` | 前端 API client | 是 |
| `frontend/dist/` | 前端构建产物，由 `npm run build` 生成 | 不进 Git |
| `deploy/` | systemd、nginx、部署脚本 | 是 |

### 数据库

当前使用 **SQLite**。

默认数据库文件：

```text
backend/data/hpc_control_panel.db
```

配置来源：

```text
backend/app/core/config.py
DATABASE_URL=sqlite:///./data/hpc_control_panel.db
```

数据库里保存：

- 服务器列表、SSH 登录方式、服务器状态、探测结果
- 任务、批次、任务日志、任务状态
- 系统设置、默认 SSH key 文件名
- 审计日志
- 报告 summary cache

数据库文件不进入 Git，原因：

- 属于运行状态，不是源码
- 可能包含服务器地址、账号、密码/配置痕迹、任务历史
- 不适合随代码仓库同步

新机器拉代码后，如果不拷贝数据库，后端首次启动会自动创建空库和表结构。

完整迁移已有环境时，需要额外拷贝：

```bash
backend/data/hpc_control_panel.db
backend/data/artifacts/
backend/keys/
backend/apptainer/*.sif
```

### SSH 密钥

SSH 密钥目录：

```text
backend/keys/
```

规则：

- Git 只保留 `backend/keys/.gitkeep`
- 实际密钥文件如 `id_ed25519`、`id_ed25519.pub` 不进入 Git
- 系统只保存默认密钥文件名，不保存密钥内容；默认密钥生成入口在服务器管理的“部署公钥”流程中
- API 不返回私钥/公钥内容

### 脚本与镜像

脚本库：

```text
backend/scripts/mpi/
backend/scripts/stress/
```

这些脚本属于代码/白名单资产，会进入 Git。

Apptainer 镜像目录：

```text
backend/apptainer/
```

`.sif` 镜像不进入 Git，原因是镜像通常较大，且属于运行资产，不适合作为源码提交。

### 任务执行时会推送到远端服务器的内容

HPCDeploy 不会把整个项目目录推到目标 HPC 服务器。

任务执行时只上传“当前任务选择的单个库文件”：

- 编译环境/普通脚本：上传选中的 `backend/scripts/mpi/*`
- 压测任务：上传选中的 `backend/scripts/stress/*`
- Apptainer 分发：上传选中的 `backend/apptainer/*.sif`

远端目录：

```text
$HOME/hpcdeploy/tasks/<task_type>/<脚本名_时间>/
$HOME/hpcdeploy/apptainer/
```

压测任务在远端目录内生成：

- `task.log`
- `.hpcdeploy.pid`
- `*report*.xlsx`
- `*report*.txt`
- 相关 `.csv` / `.log` / `.json`

后端任务结束后，会把允许的结果文件回收到：

```text
backend/data/artifacts/
```

### 不进入 Git 的关键文件

由 `.gitignore` 控制，主要包括：

```text
backend/.deps/
frontend/node_modules/
frontend/dist/
frontend/tsconfig.tsbuildinfo
.env
.env.local
*.db
*.sqlite
*.sqlite3
backend/data/artifacts/
backend/keys/*
backend/apptainer/*.sif
*.log
```

这些文件不推送的原因：

- 依赖目录和构建产物可重新生成
- 数据库、artifacts、日志是运行数据
- SSH keys、`.env` 是敏感信息
- `.sif` 是大体积运行资产

### 环境变量

后端支持的主要环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_NAME` | `HPCDeploy` | 应用名称 |
| `APP_ENV` | `development` | 运行环境 |
| `DATABASE_URL` | `sqlite:///./data/hpc_control_panel.db` | 数据库连接，后端工作目录下解析为 `backend/data/hpc_control_panel.db` |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | JWT 签名密钥，生产环境必须修改 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | 登录/管理 token 过期时间 |
| `HPCDEPLOY_ADMIN_PASSWORD` | `admin123` | 管理员密码环境变量 fallback |

当前 systemd 服务显式设置：

```text
PYTHONPATH=/home/tjzs/projects/hpc-deploy/backend/.deps:/home/tjzs/projects/hpc-deploy/backend
```

配置文件：

```text
deploy/systemd/hpcdeploy-backend.service
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
| [docs/deployment.md](docs/deployment.md) | 当前 systemd 部署、SQLite 备份恢复、后续 Docker/MySQL 路线 |
| [docs/development-stages.md](docs/development-stages.md) | 阶段开发计划与完成记录 |
| [docs/progress.md](docs/progress.md) | 项目当前进度与入口指引 |
