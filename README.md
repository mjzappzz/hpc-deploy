# HPCDeploy

> 面向 Linux / HPC 运维场景的轻量级自动化控制台：统一管理服务器、受控脚本、压测任务、运行日志、结果文件与审计操作。

HPCDeploy 通过 SSH 在远端执行白名单脚本，提供批量任务调度、实时日志与资源监控，以及 GPU、CPU/内存、磁盘压测报告的回收与追踪。

## 快速了解

| 项目 | 当前状态 |
|---|---|
| 产品定位 | 持续演进的 Linux / HPC 自动化运维控制台 |
| 被管对象 | Linux / HPC 服务器 |
| 执行方式 | SSH 下发并执行受控脚本 |
| 压测能力 | GPU、CPU/内存、磁盘压测与报告回收 |
| 当前部署 | Nginx 静态托管前端 + systemd 管理后端 uvicorn |
| 数据存储 | SQLite |
| Windows 边界 | 提供 Windows 压测脚本上传、预览、复制与下载；不支持 Windows Server 远程管理或自动执行 |
| 暂不支持 | Windows Server 远程执行、Docker / Compose 容器化 |

## 核心能力

| 能力域 | 提供内容 |
|---|---|
| 服务器接入 | SSH 探测、密码/密钥认证、公钥部署、标签管理与在线状态复检；任务执行页可按标签分组全选在线服务器 |
| 自动化执行 | 白名单脚本库、单台/批量任务、同服务器压测套件严格串行调度；兼容远端 shell 启动输出并在 SFTP 不可用时自动回退到 SSH 流式传输 |
| GPU 软件部署 | Linux NVIDIA `.run` 驱动库（GeForce 默认 `580.159.04`、Data Center（RTX Enterprise）默认 `580.173.02`）与 CUDA Toolkit 11.8、12.0–12.6、12.8、12.9、13.0 自动安装 |
| 压测与结果 | GPU、CPU/内存、磁盘压测；回收 `.log`、`.txt`、`.csv`、`.xlsx`、`.json` |
| 可观测与恢复 | WebSocket 实时日志、CPU/内存/磁盘/GPU 监控、任务诊断与后端重启后恢复监控 |
| 资产与治理 | 任务历史与失败重跑、管理员模式、审计与自动清理 |
| Windows 脚本库 | Windows 压测脚本上传、预览、复制、下载及 8 组 PowerShell 命令预设（不执行）；当前内置脚本为 v96 |

## 快速启动

### 前提

- 部署机：Linux，具备 `sudo` 权限及网络访问所需的软件源。
- 前端构建：Node.js 18 或更高版本；部署脚本会优先使用部署用户 NVM 中可用的最高版本。
- 被管服务器：SSH 可达，使用有效的密码或私钥认证；GPU 压测目标需具备可用的 NVIDIA 驱动与 `nvidia-smi`。
- 网络：安装后 Nginx 监听 `0.0.0.0:10086`，后端监听 `127.0.0.1:8000`。

### 首次部署

```bash
git clone <repo-url> hpc-deploy
cd hpc-deploy
sudo deploy/scripts/install_hpcdeploy_service.sh
```

安装完成后访问：`http://<server-ip>:10086/`

安装脚本会安装基础依赖和 Nginx、创建后端虚拟环境、构建前端、发布静态文件、初始化运行目录，并注册和启动后端 systemd 服务；后端健康检查通过后才会继续启动 Nginx 并报告部署成功。部署详情与日常更新见 [deploy/README.md](deploy/README.md)。

首次安装会要求设置管理员密码，并在后台自动生成 JWT 签名密钥。两者写入仅 root 可读的 `/etc/hpcdeploy/hpcdeploy.env`；日常使用只需记住管理员密码，JWT 密钥由系统管理。忘记管理员密码时，在部署服务器执行：

```bash
sudo /path/to/hpc-deploy/deploy/scripts/reset_admin_password.sh
```

## 使用流程

1. 在“服务器管理”新增目标服务器并完成 SSH 探测。可分别复检全部、在线或离线服务器；离线服务器默认折叠，需按需展开后检测。
2. 在“资产库管理”统一上传 Linux NVIDIA 驱动和受控脚本；脚本按基础环境配置、MPI 编译环境配置和 Linux 服务器压测分类展示。低频的“Windows 压测（试验）”位于左侧“资产库管理”上方，仅用于脚本上传、复制或下载。
3. 在“执行任务”按“环境部署 / 稳定性验证”选择任务类型；环境部署包含基础环境配置、GPU 驱动安装和 MPI 编译环境配置，稳定性验证用于 Linux 服务器压测。基础环境与 GPU 软件支持多选并按固定顺序串行执行。

> Apptainer 镜像上传和任务创建入口当前暂不开放；后端兼容接口和历史任务数据保留，历史任务仍可查看。本机资料库当前不保留 `.sif` 镜像。
4. 在“历史任务”直接查看单次及批次子任务状态和详情说明；压测任务可下载结果文件，CUDA 安装任务可复制环境变量与验证命令，管理员可执行任务清理和审计查询。
5. 仪表盘“最近任务”以独立任务 ID 列区分批次子任务，并显示与历史任务一致的单次/批次及任务类型标签；离线服务器计数使用告警色；单击行进入任务历史，拖选文本不会触发跳转。

## 目录

- [技术栈](#技术栈)
- [权限模型](#权限模型)
- [开发与运维命令](#开发与运维命令)
- [构建验证](#构建验证)
- [关键目录与运行数据](#关键目录与运行数据)
- [安全边界](#安全边界)
- [文档导航](#文档导航)

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
| 实时日志 | WebSocket 主通道 + 2s HTTP 并行轮询兜底 |

## 权限模型

- **普通模式默认可用** — 可新增/编辑服务器、SSH 检测、部署公钥、提交任务、取消任务、查看历史/日志/结果；上传脚本保留一次管理员密码确认。
- **管理员模式处理高风险操作** — 删除服务器/脚本/任务/批次任务、系统设置写入与本机结果清理。管理员模式可选 5 / 15 / 30 / 60 分钟或本标签页持续。
- **会话恢复** — 管理员 JWT 存在 HttpOnly Cookie 中并绑定当前标签页；刷新页面可恢复有效会话，手动退出、超时或关闭标签页后会清除管理员权限。
- **确认交互** — 切换管理员模式时，密码输入框可按 Enter 确认；输入法组合输入期间不会误提交。
- **审计日志** — 左侧入口仅在管理员模式显示；普通模式直接访问审计路由会返回仪表盘，后端接口继续校验管理员令牌。

## 开发与运维命令

### 开发模式（热重载）

```bash
# 后端
cd /path/to/hpc-deploy/backend
PYTHONPATH=.deps:. .deps/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd /path/to/hpc-deploy/frontend
npm run dev
```

### 当前生产服务

```bash
# 重启后端
sudo systemctl restart hpcdeploy-backend

# 检查并重载 Nginx
sudo nginx -t && sudo systemctl reload nginx

# 更新依赖、构建前端并重载服务
sudo deploy/scripts/redeploy_hpcdeploy.sh

# 预览卸载范围（默认不执行）
sudo deploy/scripts/uninstall_hpcdeploy.sh

# 查看状态
sudo systemctl status hpcdeploy-backend --no-pager -l
sudo systemctl status nginx --no-pager -l
```

卸载默认只移除本机 systemd 后端服务、HPCDeploy Nginx 站点配置及 `/var/www/hpcdeploy` 已发布前端，保留源码、SQLite、报告、SSH 密钥和生产环境配置。删除运行数据或密钥须显式追加 `--purge-runtime-data`、`--purge-secrets` 与 `--force`；不会删除任何受管服务器远端目录。详见 [deploy/README.md](deploy/README.md)。

> Nginx 从 `/var/www/hpcdeploy` 提供前端静态文件，并将 `/api/`（含 WebSocket）代理到后端。生产访问地址为 `http://<server-ip>:10086/`；Vite 仅用于开发人员本地调试，不注册 systemd 服务。

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
| `backend/scripts/windows/` | Windows 压测资料脚本库（`.ps1` / `.bat` / `.cmd`），仅供复制/下载 | 是 |
| `backend/apptainer/` | Apptainer `.sif` 镜像存放目录 | 目录保留，`.sif` 不进 Git |
| `backend/keys/` | SSH 私钥/公钥存放目录 | 目录保留，密钥不进 Git |
| `backend/data/` | SQLite 数据库、任务结果、运行数据 | 不进 Git |
| `backend/data/artifacts/` | 后端从远端回收的报告、日志、CSV、XLSX 等结果文件 | 不进 Git |
| `backend/data/gpu_driver_library/` | Linux NVIDIA 驱动库，按 GeForce / Data Center（RTX Enterprise）分类保存 `.run` 文件 | 不进 Git |
| `backend/data/gpu_driver_uploads/` | 任务页临时上传的自定义 NVIDIA 驱动，默认保留 7 天 | 不进 Git |
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
backend/data/gpu_driver_library/
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
- Apptainer 分发：后端保留历史兼容能力，前端当前不开放创建入口
- GPU 驱动安装：上传选择的驱动库 `.run` 文件，或临时上传的自定义 `.run` 文件
- CUDA 安装：不上传本机安装包；目标服务器从 NVIDIA 官方软件源安装选定 Toolkit 版本

远端目录：

```text
$HOME/hpcdeploy/tasks/<task_type>/<task_id>/
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
| `SECRET_KEY` | 开发模式有内置值 | JWT 签名密钥；生产安装时自动随机生成，用户无需记忆 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | 登录/管理 token 过期时间 |
| `HPCDEPLOY_ADMIN_PASSWORD` | 开发模式为 `admin123` | 生产安装时交互设置；非交互安装自动生成并仅显示一次 |

当前 systemd 服务显式设置：

```text
EnvironmentFile=/etc/hpcdeploy/hpcdeploy.env
PYTHONPATH=/home/tjzs/projects/hpc-deploy/backend/.deps:/home/tjzs/projects/hpc-deploy/backend
```

生产安全配置文件由安装脚本维护，权限为 `root:root 0600`。项目内的 `backend/.env.example` 仅用于开发或手工启动参考，不包含真实凭据。生产模式强制 JWT 密钥使用至少 32 位的非默认值；管理员密码内容由部署人员自行决定。

配置文件：

```text
deploy/systemd/hpcdeploy-backend.service
```

## 安全边界

- 前端不传 `command` / `raw shell` / `remote_path` / `raw_args`
- 前端不传 `remote_work_dir` — 远端工作目录由后端 `UUID` 生成，不绕过 `task_runner`
- 后端只执行白名单脚本（文件名白名单 + 目录校验）
- Apptainer 历史兼容能力只上传/分发 `.sif`，不执行 `run` / `exec`；前端当前不开放入口
- Windows 压测页只管理与展示 `.ps1` / `.bat` / `.cmd`；不允许进入 Linux SSH 任务执行链路
- 当前内置 Windows 压测脚本为 `v96_windows_stress.ps1`，兼容 Windows PowerShell 5.1。v96 保留 v95 按实际负载进程判定模块“已测试”的逻辑，并修复 DiskSpd 重定向输出尚未刷新时读取到空 `ExitCode` 被误记为失败的问题：仅已验证的非零退出码记为错误，空或不可用退出码仅作为诊断信息，仍以有效 DiskSpd 输出进行性能判定；原有阈值与硬件评估逻辑不变。
- NVIDIA 驱动任务仅接受安全文件名的 `.run` 文件；驱动类型必须为 GeForce 或 Data Center（RTX Enterprise）。临时上传驱动默认 7 天后清理，运行中被引用的文件不清理
- CUDA 任务仅安装 Toolkit，不安装或覆盖 NVIDIA 驱动；任务先通过 `nvidia-smi` 校验驱动可用，再按目标系统安装对应版本
- Linux 当前版本锁定脚本 v1.6.1 支持 x86_64 Rocky 9.x 与 Ubuntu 22.04/24.04。Rocky 读取执行前的 `VERSION_ID` 与 `uname -r`，预检固定版本仓库后锁定当前小版本、当前运行内核对应的已安装 RPM 及已安装的 `kernel-headers`；每个候选仓库预检最多运行 90 秒，超时终止 DNF 并自动切换下一源，全部失败时不修改系统配置。Ubuntu 禁止发行版升级，并通过 `apt-mark hold` 锁定当前运行内核对应的 image/modules/headers 包及已安装的 generic、HWE、virtual、lowlatency、OEM 内核元包；已安装且已 hold 的 `dpkg` 状态（`hi`）与普通已安装状态（`ii`）均可重复识别，保留原有 hold，失败时只撤销本次新增 hold。两类系统均不自动安装、升级或切换内核，也不执行全量更新；内核安全更新需在维护窗口手动解锁、升级并重新验证驱动。Rocky 旧小版本可能来自 Vault，不再获得安全更新；EPEL 9 按主版本滚动，不随 Rocky 小版本冻结。
- Linux 压测脚本使用统一启动阶段标记供后端区分准备与真实负载：依赖安装、下载或编译期间显示“准备中”，收到 `stress_start` 后才进入“运行中”并开始计算用户设定的压测时长；准备期上限为 30 分钟。运行超过“压测时长 + 报告回收宽限”只记录延后提示，远端 PID 与 SSH 健康时持续监控，不会误判为超时失败；GPU、磁盘脚本版本为 `2026.07.30`，CPU/内存脚本版本为 `2026.07.29`。该机制不改变压测参数、负载、报告格式或判定阈值。
- 多服务器执行单个普通脚本、MPI 环境脚本、单项压测、Apptainer 分发、GPU 驱动或 CUDA Toolkit 时，每台服务器创建一条独立单次任务，任务之间不共享批次；提交后历史页按本次 `task_ids` 精确展示。只有同一服务器包含多个有序步骤的基础环境、GPU 软件和压测套件才创建批次。
- 多服务器压测套件按服务器创建独立批次：每台服务器内部顺序执行所选压测，不同服务器批次并行；历史、取消、重试和结果文件均按服务器区分。
- 远端执行任务采用脱离 SSH 会话的后台进程，并在任务目录持久化 PID、日志和退出码。后端意外重启后会重新接管普通脚本、压测、NVIDIA 驱动和 CUDA Toolkit 的运行状态；Apptainer 上传等未进入远端执行阶段的任务会重新排队。
- SSH 私钥只保存文件名，不保存内容；API 不返回私钥/公钥内容
- 远端清理只允许 `tasks` / `downloads` / `tmp`，不清理 `$HOME/hpcdeploy/apptainer`
- 自动清理以任务结束时间（无结束时间时创建时间）判断保留期，同步清理 `backend/data/artifacts/<task_id>/` 与同任务 `task_logs`；不清理任务记录、远端目录、Apptainer 镜像、keys、scripts
- 路径防逃逸（`resolve()` + `startswith()`）
- 取消任务基于 PID 文件 + PGID 进程组终止，不依赖前端输入
- 部署公钥只写远端 `$HOME/.ssh/authorized_keys`，不覆盖、不修改 `sshd_config`、不重启 `sshd`
- 部署公钥按每台服务器自身 `auth_type` 独立认证登录，不固定同一私钥
- 密钥路径统一解析为 `KEYS_DIR` 下绝对路径，防止相对路径/CWD 问题
- 管理员密码通过 `/etc/hpcdeploy/hpcdeploy.env` 中的 `HPCDEPLOY_ADMIN_PASSWORD` 设置，不返回前端、不打印日志；忘记后由服务器 root 执行 `deploy/scripts/reset_admin_password.sh` 重置
- 高风险接口通过可选时长或本标签页持续的 JWT 保护；浏览器以 HttpOnly Cookie 和标签页标识共同校验，关闭标签页后不能复用管理员权限

## 文档导航

按当前任务选择对应文档，避免在维护记录中查找操作步骤：

| 如果你要…… | 阅读文档 | 内容 |
|---|---|---|
| 首次安装、日常更新或排查 systemd 服务 | [deploy/README.md](deploy/README.md) | 可执行安装、更新、状态与日志命令 |
| 备份/恢复 SQLite，评估 Docker 或 MySQL 路线 | [docs/deployment.md](docs/deployment.md) | 数据运维与部署演进，不重复安装步骤 |
| 修改 API、SSH、任务调度、数据模型或安全策略 | [docs/architecture.md](docs/architecture.md) | 当前架构、接口职责、状态机与安全模型 |
| 了解当前已交付能力、维护记录与下一步入口 | [docs/progress.md](docs/progress.md) | 维护流水，不作为当前行为的唯一依据 |
| 查询历史阶段范围与不可突破的约束 | [docs/development-stages.md](docs/development-stages.md) | 阶段交付归档 |
| 修改煤球、趣味文案或相关前端交互 | [docs/fun-principles.md](docs/fun-principles.md) | 趣味性设计约束与实现位置 |
