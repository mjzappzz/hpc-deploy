# HPCDeploy

HPCDeploy 是一个面向 HPC 运维场景的轻量级自动化控制台，用于管理 Linux 服务器、执行白名单脚本、分发 Apptainer 镜像、查看任务日志、回收结果文件、清理任务产物和审计操作。

## 最近更新

> 2026-07-17

- **管理员模式与审计收口** — 顶部可切换普通/管理员模式；管理员会话为 5 分钟 HttpOnly Cookie，刷新页面可恢复剩余时间，手动退出或超时后保持普通模式。管理员模式可直接查看审计日志；普通模式点击该入口会给出权限提示。
- **任务历史删除语义统一** — 管理员删除单任务或整批任务时，删除本机 artifacts、任务日志和历史记录，保留远端目录与审计日志；普通模式保留查看和取消任务能力。
- **任务目标快速复检** — 打开执行任务页时仅后台复检当前在线服务器的 SSH 可达性，并在服务器选择标题旁显示轻量状态，避免全量检测离线主机导致等待。
- **管理员界面分层** — 管理员模式使用金色品牌/侧栏和暖金工作区层次；普通模式保留蓝色导航选中态。

> 2026-07-16

- **服务器首次接入保护** — 新增服务器后立即执行首次 SSH 探测；仅探测成功且在线的服务器可进入公钥检测与部署流程，避免对未验证目标写入 `authorized_keys`。
- **任务恢复与活动态统一** — 后端重启后，脚本任务通过远端 PID 与退出码文件恢复监控，不重复下发命令；侧栏“运行 N”每 5 秒统计 CONNECTING、PREPARING、UPLOADING、RUNNING、CANCELING 全部活动任务，创建任务后即时刷新。
- **历史与压测修复** — 按状态筛选时保留命中批次的完整子任务上下文；CPU/内存压测按设定总内存对每个 VM worker 施压并预分配内存，修复 XLSX 未生成时的最终状态。

> 2026-07-14

- **压测任务可靠性修复** — GPU XLSX 报告采用临时文件原子落盘；回收端下载到 `.part` 后校验 ZIP 完整性再原子入库，避免下载到半写入报告。运行中压测每次健康轮询续租，后端重启后自动重新挂载远端进程。
- **批次与历史任务体验** — 重跑成功以最新尝试作为批次当前结果，原失败记录保留审计；历史任务支持单次/批次筛选、任务/批次 ID 与远端路径复制、运行中预计结束时间；侧栏“运行 N”可直达全部运行任务。
- **压测选择布局** — GPU / CPU 内存 / 磁盘压测脚本使用紧凑固定列，CPU 卡片预留选中标记空间。

> 2026-07-13

- **历史任务运行态提示** — 左侧“历史任务”在存在活动任务时显示绿色呼吸点和运行数量；当前维护版每 5 秒统计 CONNECTING、PREPARING、UPLOADING、RUNNING、CANCELING，页面不可见时暂停
- **审计日志收口** — 默认仅展示删除、清理、远端访问、设置和任务取消等高风险操作，可切换查看完整流水
- **运行数据与路径去重** — 移除与 SQLite 主数据库重复的“任务日志”条目；任务日志仍记录在数据库内

> 2026-07-10

- **压测任务恢复机制** — 三层防护：轮询循环 try-except + 新鲜 SSH 连接替换僵尸连接 + 后端重启后自动 SSH 恢复监控；不再因 SSH 传输层降解或后端重启导致任务卡死在 RUNNING
- **单次任务卡片按钮调整** — 顺序改为"查看任务详情 → 结果文件 → 取消任务"；结果文件按钮常驻显示，无结果时灰色禁用
- 完整变更见 `docs/progress.md`

> 2026-07-09

- **批次详情弹窗重构** — 去除右侧抽屉嵌套，改为左右分栏布局：左侧子任务列表（点击切换高亮），右侧完整信息面板（网格/日志/监控/诊断）
- **实时日志 WebSocket** — 批次详情内子任务支持 WebSocket 实时日志推送，常驻 LogViewer 自动滚动到底部
- **已运行时长不归零** — 独立缓存子任务数据，后端重启后运行时长从原始开始时间继续计
- **批次结束时间修复** — 只有全部子任务结束时才展示结束时间和总耗时
- **取消任务红色原因** — 已取消任务在卡片底部显示红色原因（`canceled by user`）
- **执行顺序修正** — 分子用同服务器任务位置，分母用同服务器任务数，不依赖 `sequence_index`
- **失败子任务重跑** — 批次内失败/取消/报告 FAIL 的压测子任务可追加重跑，同 batch 排队执行；批次报告优先打包最新 OK/PASS 报告
- **历史任务卡片优化** — 历史卡片白底，hover 时显示左侧蓝色亮条和三边窄蓝呼吸边框；批次详情子任务操作收口到左侧列表/右侧标题区
- 完整变更见 `docs/progress.md`

说明：README 只保留当前版本摘要、启动方式和关键边界；详细阶段记录、维护流水和下一步入口以 `docs/progress.md`、`docs/development-stages.md` 为准。

## 版本定位

当前标签定位为 **v1.02 Linux 维护版**：

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

- **服务器管理** — SSH 测试、SSH Key / Password 登录、新增服务器自动首次探测、仅在线且已探测服务器可部署公钥、缺省密钥自动生成引导、探测全部（默认跳过离线）、**标签内联编辑**（表格内点击直接修改）、紧凑表格与表单交互优化，顶部操作按钮按常用顺序收口
- **脚本知识库** — 服务器环境 / 服务器压测 / Apptainer 白名单文件，上传/下载/预览/删除，预览支持复制脚本文本，路径展示绝对路径
- **任务执行** — 单台/批量执行、服务器压测参数化、服务器压测脚本多选/一键全选自动套件、同服务器 GPU→CPU/内存→磁盘串行调度、服务器环境白名单脚本、Apptainer .sif 只上传不分发执行
- **实时日志** — WebSocket 主通道 + HTTP 轮询备用，心跳 30s，断线自动切换
- **实时监控** — CPU/内存、磁盘、GPU 结构化卡片展示，5s 轮询
- **任务管理** — 统一历史任务（单次任务卡 + 批次任务聚合卡）、卡片式展示服务器/远端用户/模块/远程目录/命令/计划时长/报告状态；压测任务展示使用统一最终状态（报告 FAIL > 报告 PASS > 执行 FAILED > UNKNOWN）；批次内失败/取消/超时或报告 FAIL 的压测子任务可追加重跑；支持取消（PID→PGID 进程组终止）、管理员删除本机 artifacts/日志/历史记录（保留远端目录与审计）、任务诊断（规则引擎，16 条规则，覆盖所有状态）、筛选/搜索/分页；按状态筛选时完整保留命中批次上下文
- **结果文件** — 回收与下载（.log/.txt/.csv/.xlsx/.json）
- **运行数据管理** — 系统设置集中展示数据库、keys、脚本库、artifacts、备份、Apptainer、本机结果文件大小和路径；支持本机结果文件扫描、按任务/批次展示、自动清理
- **Apptainer 分发** — .sif 文件上传、单台/批量分发、不执行 run/exec
- **审计日志** — 关键操作记录可追溯，默认聚焦高风险操作，可切换查看完整流水
- **系统设置** — 运行数据与路径、本机结果文件清理、自动清理配置、管理员密码弹窗修改
- **仪表盘** — 服务器/任务/归档统计、快捷操作、最近任务跳转，批次子任务带批次标记并跳转整批历史，结果文件目录树

## 当前阶段状态

当前阶段：**v1.02 Linux 维护版，项目进入维护期**。后续以修复缺陷、优化体验为主；Windows 支持和 Docker 化作为后续版本规划，不属于当前 v1.02 范围。

### 已完成（全部 29 个阶段已交付）

服务器管理、SSH 测试、服务器探测、脚本知识库、单任务执行、压测套件、GPU/CPU内存/Disk 独立任务、同服务器压测套件严格串行调度、任务历史统一展示、批次任务聚合卡、失败/取消结果文件入口、报告/下载报告入口、批次报告聚合、CPU/内存长测 timeout 收口、GPU 多卡报告脚本、脚本知识库最新修改时间、压测套件命令预览完整显示、管理员密码确认式高风险操作保护、审计日志延迟管理员确认、SSH 重连 + 批次耗时、WebSocket 多进程广播、服务器管理与任务执行页 UI 优化、运行数据与路径集中展示、本机报告清理融合到系统设置、删除本机结果后历史软隐藏、诊断引擎增强（16 条规则/状态分流/归因分类/风险提示）、诊断入口统一（所有任务状态）、管理员密码弹窗修改。

### 维护说明

v1.02 Linux 维护版核心功能已开发完成。后续在 v1.02 标签快照基础上以修复缺陷、优化使用体验为主；Windows 支持、Docker 化和生产部署增强应在后续版本或独立功能分支中推进。

### 权限模型

- **普通模式默认可用** — 可新增/编辑服务器、SSH 检测、部署公钥、提交任务、取消任务、查看历史/日志/结果；上传脚本保留一次管理员密码确认。
- **管理员模式处理高风险操作** — 删除服务器/脚本/任务/批次任务、系统设置写入与本机结果清理。管理员模式有效期 5 分钟，显示倒计时。
- **会话恢复** — 管理员 JWT 存在 HttpOnly Cookie 中；刷新页面可恢复未过期的管理员模式，手动退出或超时会清除该状态。
- **审计日志** — 普通模式不能进入；管理员模式进入后直接加载，无需再次输入密码。

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
- 高风险接口通过 5 分钟短期 JWT 保护；浏览器以 HttpOnly Cookie 传递，兼容 `X-Admin-Token` 请求头

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 系统架构与技术设计（含权限模型） |
| [docs/deployment.md](docs/deployment.md) | 当前 systemd 部署、SQLite 备份恢复、后续 Docker/MySQL 路线 |
| [docs/development-stages.md](docs/development-stages.md) | 阶段开发计划与完成记录 |
| [docs/progress.md](docs/progress.md) | 项目当前进度与入口指引 |
