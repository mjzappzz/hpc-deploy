# HPCDeploy 系统架构说明

> 本文档描述 HPCDeploy 当前实际系统架构，非设计阶段草案。

适用于修改 API、任务调度、SSH/SFTP、数据模型、权限或安全边界前的影响评估。安装、升级和服务排障请阅读 [../deploy/README.md](../deploy/README.md)。

---

## 1. 总体架构

```
浏览器 ── HTTP/WS ──→ Nginx :10086 ──→ 前端静态文件
                           │
                           └── /api/、WebSocket ──→ FastAPI :127.0.0.1:8000 ──→ SQLite
                                                         │
                                                    Paramiko SSH/SFTP
                                                         │
                                                    目标服务器
```

| 组件 | 选型 |
|------|------|
| 浏览器前端 | Vue 3 + Element Plus |
| 后端 API | FastAPI |
| 数据库 | SQLite |
| 远端执行 | Paramiko SSH / SFTP |
| 实时日志 | WebSocket 主通道 + 2s HTTP 并行轮询兜底 |
| 部署 | Nginx 静态前端 + systemd 后端服务 |

### 文件目录

```
backend/data/artifacts/    # 结果文件回收目录
backend/data/gpu_driver_library/ # Linux NVIDIA 驱动库（运行资产）
backend/data/gpu_driver_uploads/ # 临时自定义 NVIDIA 驱动（运行资产）
backend/apptainer/         # .sif 容器文件
backend/scripts/           # 白名单脚本目录
  stress/                  # 压测脚本
  mpi/                     # MPI / 编译环境脚本
backend/keys/              # SSH 私钥和同名 .pub 公钥
```

---

## 2. 后端模块说明

### servers API (`/api/servers`)
- 服务器 CRUD
- 创建服务器后立即执行首次 SSH/环境探测；首次探测失败时保留服务器记录和错误信息
- SSH 测试（`/test`、`/test-ssh-all`）
- 信息探测（`/probe`、`/detect`、`/probe-all`）
- 批量公钥检测（`/public-key/check`）— 按每台服务器自身 `auth_type` 独立认证登录，检测远端 `$HOME/.ssh/authorized_keys` 是否包含当前公钥。SSH 连不上/认证失败 → CHECK_FAILED，文件不存在或不含公钥 → NOT_INSTALLED
- 批量公钥部署（`/public-key/deploy`）— 仅允许首次探测成功且状态为 online 的服务器；按每台服务器自身认证方式登录，创建 `$HOME/.ssh` + `authorized_keys`，公钥已存在不重复追加。单台失败不影响其他
- 单台公钥部署（`/{id}/deploy-public-key`）
- 单台/批量 SSH 测试（`/{id}/test`、`/test-ssh-all`）
- 探测全部（`/probe-all`）支持显式 `server_ids`；服务器管理页可逐台并发复检全部、关注、在线或离线服务器，离线分组默认折叠并按需创建；执行任务页“检测目标服务器”复检第 1 步中展示的全部目标，即所有在线服务器与“我的关注”并集（按服务器 ID 去重，包含离线关注服务器）
- 标签管理（`/tags` 统计、`tag` 参数筛选）；固定单选值为待压测、测试机、压测完成、故障待处理，在线与离线服务器均保留和可维护业务标签。任务执行页按标签分组展示在线服务器，每个分组可独立全选/取消全选，跨分组选择会累积。
- 标签基于 `tags_json TEXT` 列存储，包含在线/离线计数；旧记录读取时兼容空标签并回退为待压测

### tasks API (`/api/tasks`)
- 任务创建、批量创建（`/batch`）
- GPU 驱动安装（`/gpu-driver/rocky9`、`/gpu-driver/batch`）：接口路径为兼容保留名称；任务展示为“自动识别系统”，并按目标服务器 OS 自动选择 Rocky 9 或 Ubuntu 安装脚本，支持 GeForce / Data Center（RTX Enterprise）驱动库与临时 `.run` 上传
- CUDA Toolkit 安装（`/cuda-toolkit`、`/cuda-toolkit/batch`）：支持 11.8、12.0–12.6、12.8、12.9、13.0，安装前校验 `nvidia-smi`，仅安装 Toolkit，不安装或覆盖驱动
- 压测套件创建（`/stress-suite`）：同服务器内 GPU → CPU/内存保持串行；选择多个磁盘时，前置阶段结束后各挂载点并行推进
- 批次子任务重跑（`/{task_id}/retry-in-batch`）：支持压测套件和基础环境受控脚本套件的失败步骤；新尝试替代原失败步骤参与后续调度，已成功前序步骤不会重跑
- 单项压测与压测套件的单个脚本时长范围为 1 分钟–72 小时（后端秒级边界仍为 10–259200 秒）；当前任务页以小时/分钟输入并在 72 小时边界前置限制和提示
- 磁盘压测脚本 `v2026.08.19.1` 支持已挂载路径的随机写稳定性测试。每次远端启动时会沿块设备父链解析实际底层盘，并以 `ROTA`、`TRAN`、`MODEL` 和 NVMe 设备名自动定档：机械盘为 `2 worker × 1G`，SSD 为 `4 × 2G`，NVMe 为 `8 × 2G`；RAID 控制器逻辑盘（例如 MegaRAID `MRxxxx`）标识为 `RAID`，不把控制器的 `ROTA=1` 误作底层机械盘。无法可靠识别的设备保守使用机械盘档。父链查询使用 `lsblk` 原始行格式，避免树形前缀污染设备名。压测随机写固定使用 `direct,sync`，绕过页缓存并等待写入落盘，避免 NVMe 的缓存压力被误判为物理磁盘通过。启动前按文件系统总容量的 10% 与 20GiB 中较大值保留安全余量；自动档在必要时先减少 worker、再将单 worker 工作集降至 1G，最低档仍会侵占余量才拒绝启动。用户显式传入 `WORKERS` 时保持手动覆盖语义并使用每 worker 20G，不自动降档。TXT/XLSX 报告记录自动档位、旋转属性、传输链路、安全余量、总工作集及 I/O 路径；XLSX 文件名保留时间戳并追加 `root` 或挂载目录标识。任务页默认全选每台目标服务器可压测的根分区与数据盘挂载点，过滤 `/boot`/EFI；每台服务器只会为自己勾选的挂载点创建 `磁盘压测 · <目录>` 子任务，同服务器磁盘任务共享 GPU/CPU 等前置阶段并行执行，不同服务器批次也并行。批次 ZIP 保留每份 XLSX 的原始文件名并导出每个已选挂载点的报告。
- 并行创建的压测子任务在远端工作目录中追加各自 `task_id`，避免同秒创建时共享脚本、PID、日志或报告文件。
- 任务执行器会保留预分配的远端目录，仅将 `~/` 展开为远端 HOME；不会在连接后重新生成目录覆盖并行隔离标识。
- CPU/内存压测脚本 `v2026.08.19.1` 保持 `stress-ng` 全 CPU worker 与内存校验方式，CSV、TXT 和可选 XLSX 报告新增基于 `/proc/stat` 的 CPU Busy、I/O Wait、Steal，以及内存压力目标达成率。CPU Busy 平均低于 80% 或内存目标最高达成率低于 75% 时判定 FAIL，阈值允许通过环境变量覆盖；CPU Busy 平均和最高值默认排除最初 15 秒预热阶段（按采样间隔向上取整），并只统计 `stress-ng` 仍在运行的完整采样窗口，避免短时任务把压力启动爬升或结束后的收尾空闲采样计入判定；CSV 记录 `stress_active`，TXT/XLSX 报告记录实际有效压力采样数。内存目标仍以启动时可用内存的 85% 为上限；安全余量取“物理内存 10%”与“物理内存 25%（最高 4 GiB）”的较大值，目标缓冲取物理内存 2% 并限制在 128–512 MiB，从而兼容小内存测试机和大内存服务器。运行中可用内存连续 3 个采样周期跌破安全余量时终止 `stress-ng` 并判定 FAIL，不做自动减载或重启 VM worker。CPU 温度优先读取 Intel `Package id`、AMD `Tctl/Tdie`，`sensors -j` 不可用时回退 Linux `hwmon`；温度当前只记录、不参与 PASS/FAIL，也尚未进入任务实时监控接口。脚本以 `dmesg --follow-new` 监听本次新增内核日志，并在结束时按开始时间二次核验 `journalctl -k`；`UE`/`UECC`、可纠正 ECC MCE、OOM、热节流和一般 MCE/硬件事件分别判定与说明。TXT、XLSX 和 Shell 输出均显示实际事件分类；XLSX 的事件明细 Sheet 按分类命名（如 `CorrectedECC`、`UncorrectableECC`、`OutOfMemory`），原始 `cpu_mem_error_*.log` 文件名保持兼容。`openpyxl` 改为可选依赖，缺失时跳过 XLSX，但 TXT/CSV 和最终判定正常生成。
- 受控环境套件创建（`/managed-suite`）：基础环境配置按关闭锁屏/休眠 → 锁定当前系统版本，GPU 驱动安装按 NVIDIA 驱动 → CUDA Toolkit 严格串行；多台服务器各自创建独立批次，前序失败时后序不启动，后端重启后恢复套件 worker
- 多服务器单动作入口按服务器创建互相独立的单次任务：普通脚本/单项压测/Apptainer（`/batch`）、GPU 驱动（`/gpu-driver/batch`）和 CUDA Toolkit（`/cuda-toolkit/batch`）均返回完整 `task_ids`，每条任务的 `batch_id` 为空；只有同一服务器包含多个有序步骤的受控环境套件和压测套件才创建批次，并按服务器分配独立 `batch_id`
- Intel oneAPI 2022 安装脚本 v1.1.0 在执行安装器前分别检查 MKL 与编译器/Intel MPI 命令；目标组件已完整安装时跳过对应离线包下载和安装，最终严格验证 `icc`、`icx`、`ifort`、`mpiicc`、`mpiifort`、`mpirun` 及 `MKLROOT`，重复执行不再因 Intel 安装器返回“already installed”而误报失败
- AOCC/AOCL + OpenMPI 安装脚本 v1.1.0 分别检测 AOCC 编译器、AOCL 库和 OpenMPI wrapper；已完整安装的组件跳过下载、包安装或编译，最终严格验证 `clang`、`clang++`、`flang`、`mpicc`、`mpicxx`、`mpif90`、`mpirun`、AOCL 库及 `mpicc --showme`
- Linux 当前版本锁定脚本 v1.7.5 接受 x86_64 Rocky 9.x 与 Ubuntu 22.04/24.04。Rocky 读取执行前 `VERSION_ID` 与 `uname -r`，要求当前运行内核存在对应 `kernel-core` RPM，并收集当前内核对应的已安装 `kernel`、`kernel-core`、`kernel-modules*`、`kernel-devel` 及已安装的 `kernel-headers`；随后预检并固定当前小版本仓库，通过 DNF versionlock 锁定 release/repo/GPG 与内核包。每个 Rocky 候选源的隔离 DNF 预检由 coreutils `timeout` 限制为 90 秒，超时后发送 TERM、10 秒后强制结束并切换下一源；所有候选失败时仍处于预检阶段，不修改系统配置。Ubuntu 在读取 hold、更新软件包索引和写入 hold 前，均通过 `fuser` 检查 apt/dpkg 锁。仅当持锁进程命令为 `unattended-upgrade` 且 cgroup 归属 `apt-daily-upgrade.service` 时，脚本才将它识别为可恢复的自动更新，因此服务主进程已退出并显示 failed 的遗留子进程也能被正确处理；每 5 秒比较下载缓存增量与进程 CPU 时间，连续两个采样的平均下载速率低于 512KiB/s 且没有 CPU 配置进展时（约 10 秒），先异步停止该服务，再仅向该服务 cgroup 的自动更新进程发送 `SIGTERM`，等待锁释放后执行 `dpkg --configure -a` 恢复包管理一致性，再继续版本锁定；不会使用 `SIGKILL`。人工 apt/dpkg、cloud-init 或未识别的锁始终只等待，最长 900 秒，绝不删除锁文件或终止进程。随后将 `Prompt` 设置为 `never`，收集当前运行内核对应的 image/modules/headers 包以及已安装的 generic、HWE、virtual、lowlatency、OEM 内核元包，再通过 `apt-mark hold` 锁定并逐项验证；包状态识别接受 `dpkg` 的普通已安装（`ii`）和已 hold 且已安装（`hi`），仍拒绝残留配置或未安装状态。Ubuntu 备份原发行版升级配置与原 hold 清单，保留既有 hold，失败时只撤销本次新增 hold 并恢复配置。Rocky 备份全部 `.repo`、`releasever` 与 `versionlock.list`，失败时完整恢复并校验。脚本不自动补装、升级或切换内核，也不执行跨版本升级、降级或全量更新；内核安全更新需在维护窗口手动解锁、升级并重新验证驱动。
- 资产库对所有文本脚本解析内容版本（支持 `SCRIPT_VERSION=...`、`ScriptVersion: ...` 等形式），API 通过 `content_version` 返回，管理表格统一展示“版本”列；未声明版本的文件显示 `-`。
- 任务执行恢复：普通脚本和 CUDA Toolkit 与压测、NVIDIA 驱动一致，远端进程使用 `nohup + setsid` 脱离 SSH，任务目录保存 `.hpcdeploy.pid`、`task.log` 和 `.hpcdeploy.exit_code`。后端启动时扫描 RUNNING 任务，通过 SSH 重新附着监控、补录日志并按远端退出码收尾；CONNECTING/PREPARING/UPLOADING 阶段任务由启动恢复器重新排队。已在远端启动的压测任务会保留 `PREPARING` 状态直到负载启动标记出现，重启恢复器按 PID 重新附着而不重复下发。
- 重启恢复中的普通脚本与 CUDA Toolkit 遇到 SSH 连接或 channel 临时不可用时保持 RUNNING，并以 60 秒间隔重新附着；NVIDIA 驱动已有同类延迟重试，压测执行多次即时重连后再延迟重试。控制面连接失败不再直接覆盖远端任务真实退出状态。
- 批次压测子任务重跑（`/{task_id}/retry-in-batch`）：仅支持白名单压测脚本中执行失败、取消、超时或报告 FAIL 的子任务；重跑任务追加到同批次、同服务器队列末尾，并阻止重复排队
- 任务列表 `scope=single|batch`：按是否存在 `batch_id` 筛选单次任务或批次子任务，保持分页总数准确；`active_only=true` 统计 CONNECTING、PREPARING、UPLOADING、WAITING_REBOOT、RUNNING、CANCELING 全部活动任务；`active_only=true&include_batch_context=true` 返回活动任务所属批次的完整子任务，供运行入口渲染完整批次卡；状态筛选也支持 `include_batch_context=true`
- 状态查询、取消；管理员删除本机任务记录（`POST /api/tasks/{task_id}/local-artifacts/cleanup`）和整批记录（`POST /api/tasks/batches/{batch_id}/local-artifacts/cleanup`）
- 删除仅允许终态任务：清理本地 artifacts、任务日志和数据库任务记录，**不删除远端目录**，审计日志保留
- 日志查询、日志下载、WebSocket 实时日志（`/api/tasks/{task_id}/logs/ws`）
- 失败诊断（`/{task_id}/diagnosis`）
- 结构化监控（`/{task_id}/monitor` — CPU/内存/磁盘/GPU 5s 轮询）
- 历史任务统一展示：普通任务按单次任务卡展示；同一 `batch_id` 在前端聚合为批次卡，首页展示批次概览，批次详情弹窗展示完整子任务信息。批次有成功和失败时，全部子任务结束后才显示橙色 `PARTIAL SUCCESS` / “部分成功”及成功、失败计数；仍有子任务运行时只显示运行状态。单次与批次详情的实时日志连接状态固定置于任务标题旁，WebSocket 建连、已连接和 HTTP 轮询兜底仅更新既有标签内容与颜色，避免状态切换导致标题行重排。
- 仪表盘“运行中任务”使用独立任务 ID 列，并与历史任务共用任务类型标签规则；返回所有 PENDING、CONNECTING、PREPARING、UPLOADING、WAITING_REBOOT、RUNNING、CANCELING 状态任务，不设数量上限。页面可见时每 5 秒静默刷新，切回前台立即补刷；右上角标签以 5 秒蓝色填充进度表示下一轮刷新。拖选表格文本不触发行跳转
- 仪表盘在“运行中任务”下展示“近期已完成任务”：`/api/dashboard/summary` 返回最近 10 条 `SUCCESS` 或 `FAILED` 任务，按 `end_time` 倒序（同一结束时间按数据库记录 ID 倒序）；取消任务不混入该列表，继续仅在任务结果统计中单列。两张任务表均可跳转对应单次或批次历史记录
- 仪表盘服务器概览的离线计数使用红色告警样式；在线、总数等既有统计口径不变
- 历史任务卡片统一展示模块、文件、远程目录、命令、计划时长、开始/结束/耗时、报告状态和失败原因
- 重跑链以最新一次尝试计算批次当前状态；旧尝试仅作为历史审计记录保留
- 结果文件入口先展示 artifact/result 文件列表，再由用户选择具体文件下载
- 批次报告下载：单服务器批次生成 `服务器名称_压测报告_日期.zip`，多服务器批次生成 `batch_id.zip` 并按服务器目录拆分
- 批次结果文件弹窗与单任务结果卡保持一致：每个子任务展示可换行、可复制的远端目录；聚合下载以主操作“下载批次报告（ZIP）”呈现
- 任务历史查询默认过滤 `hidden_from_history=1` 的软隐藏记录；keyword 支持匹配任务 ID、批次 ID、脚本名、服务器名称与主机地址
- 驱动与 CUDA 批量任务按服务器独立执行；混合 Rocky 9 / Ubuntu 目标允许并行，各任务记录实际识别到的 OS profile

### scripts API (`/api/scripts`)
- 脚本知识库文件列表、上传、预览、下载、删除
- 常用运维命令位于资产库管理下的独立页面，数据保存在 SQLite `ops_commands` 表；左侧选择标题，标题前的星标沿用服务器关注交互，将当前浏览器关注的命令置顶，无需管理员确认且不写入服务端。右侧默认按安全富文本展示正文，点击编辑后才进入编辑态，支持选中文字加粗、新增、保存、复制和删除。正文仅允许段落、换行及加粗标签，服务端在写入与读取时均清理其他 HTML，审计不记录命令正文；该模块不关联文件上传、脚本白名单或远程任务执行。
- 前端当前按类型筛选 mpi/stress/windows；apptainer 资产保留但不开放管理入口
- Windows 分类仅接受 `.ps1`、`.bat`、`.cmd`，单文件不超过 2 MiB；只供 Windows 压测页面预览、复制和下载，不可创建 Linux 任务。当前 `v97_windows_stress.ps1` 在管理员 PowerShell、PawnIO 未安装且 `AutoConfirmPawIoInstall=true` 时，会从 PawnIO 官方 GitHub Release 下载 Authenticode 有效签名的安装器并以 `-install -silent` 安装；仅接受退出码 0 或 3010，且会轮询复核安装状态。非管理员、签名校验失败或超时只记录告警并降级采集。报告的核心指标和 CPU/GPU 分项指标均展示 CPU 最高、平均温度，以及 GPU 最高、平均最高温度和最大、平均总功耗；CPU 温度在所有 CPU 类型统一按 ≤95°C 通过、>95°C 且 <100°C 关注、≥100°C 不合格评定。GPU 优先按驱动的 `power.limit`、`GPU Slowdown Temp` 动态评定，热降频点不可用时按现有 GPU 温度阈值评定。CPU 优先使用 LHM PPT/Power Limit 百分比反推平台上限，未读取到时可回退到本地精确型号的官方 TDP；达到基准显示通过，低于基准显示 `-`。客户报告的参考标准面板只展示已成功读取的动态限制值。
- Linux NVIDIA 驱动库由 tasks API 独立管理，避免 `.run` 文件进入通用 Linux 脚本执行链路
- 前端“资产库管理”将 Linux NVIDIA 驱动库置于独立卡片，普通脚本知识库只展示 mpi/stress；统一上传入口先选择目标模块，再应用对应扩展名约束。Windows 与暂时下线的 Apptainer 资料不进入该页面的“全部”列表

### cleanup API (`/api/cleanup`)
- 本地结果文件目录扫描与删除已整合到系统设置页面，旧清理中心页面和 `/cleanup` 前端路由已删除
- 系统设置的运行路径列表隐藏软下线的本机及远端 Apptainer 目录，后端路径契约仍保留用于兼容历史任务
- 本地结果文件按真实任务记录聚合：普通任务返回任务名称、任务 ID、任务类型；批次任务按 `batch_id` 聚合并返回所有子任务名称、task_id、目录、文件数和大小
- 批次结果按“子任务 → 子任务文件”返回；数据库中属于该批次但没有 artifacts 目录的取消、未启动或未回收子任务也会进入 `child_tasks`，文件列表为空
- 本地结果和数据库任务日志支持同一任务 ID 搜索：匹配单次任务 ID、批次 ID和批次子任务 ID；批次 ID会映射全部子任务日志
- 数据库任务日志按任务汇总时关联任务、批次与服务器，返回单次/批次标识、批次 ID、子任务 ID及服务器名称；无法关联的历史记录显式标记为未关联
- 本地结果删除后默认只软隐藏历史记录：设置 `tasks.hidden_from_history=1`、`hidden_reason`、`hidden_at`，保留数据库记录
- 本地结果按任务完成时间（无结束时间时开始/创建时间）排序；未匹配数据库任务的遗留目录才使用文件 mtime
- 本地报告自动清理状态查询（`GET /api/cleanup/auto-cleanup/status`），配置保存走 settings API
- Apptainer 镜像目录扫描接口保留用于历史兼容，前端当前不展示
- 远端单台/全部在线服务器临时目录扫描与清理，自动匹配数据库任务记录，返回显示元数据（display_title、server_name、batch_id 等）
- 远端任务目录按 mtime 降序排列
- 远端整体目录清理（`POST /api/cleanup/remote/delete`），只允许 `tasks` / `downloads` / `tmp` 三个 target
- 远端单个任务目录删除（`POST /api/cleanup/remote/task-dir/delete`），使用 HMAC-SHA256 签名的 `delete_key` 代替原始路径防篡改

### settings API (`/api/settings`)
- 系统设置读写
- 当前：SSH 默认私钥名称、远端目录只读说明、结果文件与数据库任务日志共用的自动清理开关/保留天数/执行时间
- 修改管理员密码（`POST /api/settings/change-password`），需要 admin_token + 当前密码验证
- `admin_password` 在 `FORBIDDEN_KEYS` 中，不能通过 PUT /settings 读写
- GET /settings 返回 `admin_password_configured: bool`，不返回密码明文

### audit API (`/api/audit-logs`)
- **需 `require_admin_token()` 保护**（需要管理员密码确认）
- 审计日志查询与分页（支持 action / target_type / status / keyword 筛选）
- 审计记录操作人、目标服务器、来源 IP、状态、说明与脱敏后的详情；浏览器请求仅信任本机 Nginx 转发且格式合法的 `X-Real-IP`，其他请求记录直连对端 IP，后台自动任务无来源 IP
- 支持 `risk_only=true`：仅返回删除、清理、远端访问、公钥部署、设置修改和任务取消等高风险操作；接口默认保留完整流水，前端默认启用该筛选
- 统一英文 action 命名（`server.create`、`task.cancel` 等），前端中文标签映射
- 记录任务创建/删除/取消/诊断、压测套件创建、清理、设置保存、服务器增删改/探测/SSH 测试/公钥部署等操作
- 所有调用点包含 `detail_json` 结构化上下文（参数、结果、错误信息）
- 敏感字段自动过滤：password、private_key、secret、token、command、raw_shell、raw_args、env
- 包含 `server_id`、`target_name`、`target_type` 字段

### apptainer 分发逻辑
- 单台分发：SFTP 上传 .sif 到 `$HOME/hpcdeploy/apptainer/`
- 批量分发：多线程并发 SFTP
- 只上传，不执行 `run` / `exec`

### GPU 驱动与 CUDA runner
- `gpu_driver_runner.py` 管理驱动库、临时上传驱动和安装任务。驱动文件名限制为 `NVIDIA-Linux-x86_64-*.run`，类型为 GeForce / Data Center（RTX Enterprise）；临时文件默认保留 7 天，引用中的文件不会清理。
- 驱动安装根据探测 OS 选择 Rocky 9 或 Ubuntu 自动化脚本。若已存在可用 `nvidia-smi`，默认跳过；勾选强制安装时才覆盖执行。强制路径从 `.run` 安装包探测并固定 NVIDIA 推荐的 `open` 或 `proprietary` 内核模块类型，并使用 `--allow-installation-with-running-driver`，避免非交互任务因模块类型和运行中驱动确认而默认中止。强制替换运行中驱动时，安装成功后任务进入 `WAITING_REBOOT`，自动重启、重连并以 `nvidia-smi` 实际版本收尾，避免旧内核模块与新用户态库短暂不匹配而误报失败。需要时自动完成 Nouveau 禁用、重启与恢复执行；Ubuntu `.run` 安装器显式使用 `--no-questions --accept-license --ui=none`，避免无终端 SSH 环境因交互 UI 初始化失败。
- `cuda_toolkit_runner.py` 使用 NVIDIA 官方软件源安装指定 Toolkit；写入 `/etc/profile.d/cuda-<version>.sh` 并维护 `/usr/local/cuda` 软链接。成功后仅以 `nvcc --version` 验证，并在任务日志输出可复制的环境变量。

### task runner
- 基于 `setsid --wait` 启动进程组
- PID 写入 `.hpcdeploy.pid` 文件；脚本任务结束时写入 `.hpcdeploy.exit_code`
- SSH executor 封装 Paramiko 连接、重试、超时；`connect()` 只建立 SSH 会话，文件上传和结果回收通过 `get_sftp()` 按需创建并复用 SFTP 会话
- stress 后台执行使用完全 detach 的 `setsid bash -lc ... < /dev/null`，远端启动成功只代表任务进入 `RUNNING`
- stress-suite 调度按 `server_id` 加锁，只有前序子任务进入终态后才启动下一子任务
- 后端重启后，RUNNING 脚本任务通过远端 PID 与退出码文件恢复监控，不重新下发远端命令；stress 恢复 SSH 连接临时失败时，先重试 3 次，仍失败则保留 `RUNNING` 并在 60 秒后继续恢复，不将控制面连接错误误判为远端任务失败；已恢复的活动压测子任务结束后，套件调度继续后续任务

### ssh detector
- 执行固定的安全探测命令
- 解析 OS/CPU/内存/磁盘/GPU 信息；CPU 同时提取型号、Socket 数、总物理核心与逻辑线程。前端优先显示“颗数 · 物理核 · 线程”；旧记录缺少拓扑字段时保留原摘要并将旧 `CPU(s)` 明确展示为线程，不推断物理核。
- 不依赖前端输入
- 服务器离线或重启后沿用最后一次**完整成功**的硬件清单。SSH 已恢复但 NVIDIA PCI 硬件存在、`nvidia-smi` 尚未就绪时，探测器以 2 秒间隔最多重试 3 次；仍未恢复则仅更新在线状态，不覆盖既有硬件信息，也不更新 `last_check_at`。只有 OS/CPU/内存/磁盘/GPU 全部完成当前轮探测时，才原子写入最新清单与“最后探测时间”。

### diagnosis rules（规则引擎，无外部 AI）
- 16 条诊断规则，按优先级排序：5 条元数据预检查 + 11 条日志模式匹配
- 元数据预检查（优先匹配）：
  - 用户取消（`exit_code == -15` / `status == CANCELED`）
  - Artifact 回收失败（`error_message` 含 "artifact recovery failed"）
  - 报告已生成但状态未收尾（artifacts 有报告 + 任务仍 RUNNING）
  - 超时无报告（日志匹配超时模式 + artifacts 无报告）
  - Stress 卡在 stress-ng 阶段（日志含 stress-ng 标记 + 未终态）
- 状态分流：SUCCESS / RUNNING / PENDING 不进入错误模式匹配，分别返回对应结论
- 每个诊断结果包含：归因（`attribution`）、结论（`conclusion`）、风险提示（`risk_tips`）
- 诊断端点 `GET /tasks/{task_id}/diagnosis` 接受全量任务元数据（exit_code、artifacts 存在性、params、报告结果等）
- 报告内容解析：自动读取本地 txt 报告判断 PASS/FAIL，SUCCESS+FAIL 时标注"平台任务已成功完成，但报告内压测结果为 FAIL"
- evidence 不泄露敏感字段

---

## 3. 数据模型

### 核心表

| 表 | 说明 |
|----|------|
| `servers` | 服务器配置与健康状态 |
| `tasks` | 任务记录 |
| `task_logs` | 任务日志行 |
| `scripts` | 脚本知识库元信息 |
| `audit_logs` | 审计日志 |
| `system_settings` | 系统设置键值对 |

### servers 表关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | VARCHAR(100) | 服务器名称 |
| `host` | VARCHAR(100) | 主机地址 |
| `port` | INTEGER | SSH 端口 |
| `username` | VARCHAR(100) | SSH 用户名 |
| `auth_type` | VARCHAR(20) | key / password |
| `key_path` | VARCHAR(255) | 本地私钥路径 |
| `password` | VARCHAR(255) | 密码（仅 password 模式） |
| `status` | VARCHAR(20) | online / offline / unknown |
| `tags_json` | TEXT DEFAULT '[]' | 单元素标签 JSON 数组；固定业务标签 |
| `last_check_at` | DATETIME | 最后探测时间 |
| `last_error` | TEXT | 最后错误 |
| `cpu_sockets` | INTEGER | CPU 颗数；仅完整 CPU 拓扑探测后写入 |
| `cpu_physical_cores` | INTEGER | 总物理核心数；不等同于逻辑线程数 |
| `cpu_logical_threads` | INTEGER | 操作系统可调度的逻辑线程数（`lscpu` 的 `CPU(s)`） |

说明：只保留标签，不做分组。`group_name` 列仍存在于数据库但不再使用。

### tasks 表关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | VARCHAR(64) | 任务唯一 ID；本地 artifacts 一级目录名 |
| `batch_id` | VARCHAR(64) | 批次 ID；同一批次下多个子任务共享 |
| `task_type` | VARCHAR(50) | 任务类型：script / stress / apptainer / gpu_driver / cuda_toolkit |
| `file_name` | VARCHAR(255) | 执行脚本文件名 |
| `status` | VARCHAR(30) | PENDING / RUNNING / SUCCESS / FAILED / CANCELED 等 |
| `sequence_index` | INTEGER | 压测套件子任务顺序 |
| `depends_on_task_id` | VARCHAR(64) | 串行任务依赖的前序任务 ID |
| `hidden_from_history` | BOOLEAN | 本机结果文件删除后的历史软隐藏标记 |
| `hidden_reason` | VARCHAR(100) | 软隐藏原因 |
| `hidden_at` | DATETIME | 软隐藏时间 |

---

## 4. 远端目录约定

### 固定目录结构

```
$HOME/hpcdeploy/
├── tasks/{type}/{task_id}/    # 任务工作目录
├── apptainer/                 # Apptainer .sif 文件（仅分发）
├── downloads/                 # 临时下载目录
└── tmp/                       # 临时目录（清理 target）
```

说明：远端任务目录暂不开放自定义，避免影响任务执行、取消、删除、清理、结果回收的路径安全校验。

---

## 5. 安全设计

### 白名单脚本
- 脚本必须命中 `backend/scripts/`（当前内置 `stress/`、`mpi/`）；Apptainer 文件必须位于 `backend/apptainer/`
- 文件名通过 `_safe_basename()` 校验（禁止 `..`、禁止 `/`）
- 路径通过 `resolve()` + `startswith()` 防逃逸
- `backend/scripts/windows/` 仅为 Windows 压测资料库，任务执行器拒绝该分类，避免 PowerShell/批处理文件进入 Linux SSH 执行链路
- 驱动库仅允许 `NVIDIA-Linux-x86_64-*.run`，并按 GeForce / Data Center（RTX Enterprise）固定分类；驱动文件必须位于专用运行目录，不能作为通用脚本执行

### 参数白名单
- stress 参数只允许数字
- 禁止 `command` / `raw_args` / `shell` / `raw_command` 参数键

### 路径白名单
- 远端清理只允许 `tasks` / `downloads` / `tmp`
- 不清理 `$HOME/hpcdeploy/apptainer`
- 删除任务时远端路径必须匹配 `hpcdeploy/tasks/{type}/{task_id}` 格式

### 禁止 raw command
- 前端不传 `command`、`remote_path`
- 所有命令由后端按任务类型固定生成
- CUDA 安装源与 Toolkit 包名由后端按 Rocky 9 / Ubuntu 22.04 / Ubuntu 24.04 和版本白名单生成；前端不能传入下载地址或 shell 参数

### 公钥检测/部署安全
- 前端只传 `private_key_path`，不传远端路径、不传原始 shell 命令
- 远端路径固定为 `$HOME/.ssh/authorized_keys`，后端硬编码，不接收前端参数
- 公钥内容从本地 `.pub` 文件读取，不接收前端传入的 key 内容
- 每台服务器按自身 `auth_type` 独立认证（key 用 `key_path`，password 用 `password`），不固定同一私钥
- 新增服务器必须先完成首次探测且状态为 online，才允许部署公钥
- `key_path` 通过 `_resolve_server_key_path()` 统一解析为 `KEYS_DIR` 下的绝对路径，防止相对路径/前缀问题

### Apptainer 不执行
- 不执行 `apptainer run` / `apptainer exec`
- 只上传/分发 `.sif` 文件

### 清理中心 target 白名单
- 远端清理 target 代码级硬编码：`tasks` / `downloads` / `tmp`
- 不清理系统目录（`/root`、`/home`、`/tmp`、`/opt`、`/usr`、`/etc`）
- 远端单个任务目录删除使用 HMAC-SHA256 签名 `delete_key`：后端对 `{"server_id": <id>, "path": "<path>"}` JSON 序列化 → base64url 编码 → `secret_key` HMAC 签名 → `body.sig` 格式传递给前端；删除时前端回传 key，后端验签后解析路径，防止路径篡改

### 本地报告自动清理（Phase 29）
- 后端启动入口 `start_auto_cleanup_scheduler()`（`backend/app/core/auto_cleanup.py`），`main.py` startup event 中调用
- 轻量 asyncio `asyncio.create_task()` 循环，每隔约 1 分钟检查一次
- 每次检查流程：读配置 → 判断是否启用 → 判断是否到达设定时间 → 尝试获取文件锁（`fcntl.LOCK_EX|LOCK_NB`，文件 `.auto_cleanup.lock`） → 判断当天是否已执行过
- 实际清理函数 `run_local_artifacts_auto_cleanup()`：
  - 只扫描 `backend/data/artifacts` 一级任务结果目录
  - 按任务 `end_time` 判断是否超过保留天数，无结束时间时使用 `created_at`；未匹配任务的遗留目录使用目录 mtime
  - 删除前通过 `resolve()` + `relative_to(ARTIFACTS_DIR)` 确认路径仍在 artifacts 根目录内
  - RUNNING / PENDING / CONNECTING / PREPARING / UPLOADING 任务对应目录跳过
  - 同步删除过期终态任务的 `task_logs`；运行中任务及其日志跳过
  - 每个目录操作写入一条 `actor=system`、`action=auto_cleanup_local_artifacts` 审计日志，最后汇总写入一条
  - 执行结果保存到 `system_settings` 表（`auto_cleanup_last_run_at` / `last_deleted_dirs` / ...），前端通过 settings API 或 auto-cleanup/status 端点读取
- 默认关闭，默认保留 30 天，默认每日 03:00 执行
- 不自动清理任务记录、远端服务器目录、downloads/tmp、Apptainer 镜像、keys、scripts

### 时间约定
- SQLite 中任务、日志时间以 UTC 无时区值存储；前端和任务日志下载统一转换为 `Asia/Shanghai`（北京时间）展示
- 本机/远端扫描接口的文件 mtime 统一以 UTC 返回，避免前端重复加时区

### 敏感信息过滤
- `GET /api/ssh-keys` 不返回私钥/公钥内容
- 审计日志不记录密钥内容
- 诊断 evidence 不泄露敏感字段

---

## 6. 权限模型（Phase 26）

### 设计原则
- 不强制全站登录 — 普通访客默认可正常使用平台
- 不做复杂 RBAC / 多用户管理
- 高风险操作需要管理员密码确认

### 访客允许操作
| 操作 | 端点 |
|------|------|
| 新增/编辑服务器 | `POST/PUT /api/servers` |
| SSH 测试、探测 | `POST /api/servers/{id}/test`、`POST /api/servers/{id}/probe` |
| 执行任务/批量任务/压测套件/受控环境套件 | `POST /api/tasks/run`、`POST /api/tasks/batch`、`POST /api/tasks/stress-suite`、`POST /api/tasks/managed-suite` |
| 查看任务历史/日志/报告 | `GET /api/tasks/**` |
| 查看脚本知识库 | `GET /api/scripts/**` |

所有访客操作审计日志 `actor="visitor"`。

### 管理员模式下的高风险操作
| 操作 | 端点 | 依赖 |
|------|------|------|
| 删除服务器 | `DELETE /api/servers/{id}` | `require_admin_token()` |
| 删除本机任务/批次历史 | `POST /api/tasks/{task_id}/local-artifacts/cleanup`、`POST /api/tasks/batches/{batch_id}/local-artifacts/cleanup` | `require_admin_token()` |
| 删除脚本 | `DELETE /api/scripts/files` | `require_admin_token()` |
| 上传/修改脚本 | `POST/PUT /api/scripts/**` | `require_admin_token()` |
| 清理本地 artifacts | `POST /api/cleanup/local-artifacts/delete` | `require_admin_token()` |
| 清理远端目录 | `POST /api/cleanup/remote/delete` | `require_admin_token()` |
| 查看审计日志 | `GET /api/audit-logs` | `require_admin_token()` |
| 保存系统设置 | `PUT /api/settings` | `require_admin_token()` |

任务记录与本机 artifacts 的清理以单任务或整批为原子范围：任务同时关联批次、执行日志和报告摘要时，不应仅按空目录删除单条子任务，以免保留不完整的批次历史。

所有前端高风险入口（删除服务器、脚本、驱动、任务/批次记录和本机结果、保存自动清理设置、查看审计日志）均先调用统一的 `requireAdminConfirm()`：普通用户点击即弹出右上角同一管理员登录弹窗；管理员会话有效时直接进入后续确认或操作。
弹窗中的隐藏头像三击入口仅在显式启用时可用：后端签发绑定当前 `tab_id`、30 秒有效且只能成功消费一次的 `scope=admin_once` JWT，并写入独立的 HttpOnly `admin_once_token` Cookie；它只能用于紧接着的当前高风险请求，不暴露给前端 JavaScript、不激活管理员主题/倒计时，也不开放后续操作。

### 认证流程

```
用户开启管理员模式
  → POST /auth/admin/verify 输入管理员密码、选择 5 / 15 / 30 / 60 分钟或本标签页持续
    → 后端签发绑定 `tab_id` 的 JWT，并写入 HttpOnly、SameSite=Lax Cookie
  → 前端显示倒计时；刷新时 GET /auth/admin/status 恢复未过期会话
  → 高风险 API 由 require_admin_token() 验证 JWT 签名 + scope=admin，并要求 `X-Admin-Tab-Id` 与 JWT 内 `tab_id` 一致
  → 手动退出 POST /auth/admin/logout 清除 Cookie；超时或关闭标签页后切回普通模式
  → 通过后执行操作，审计日志 actor="admin"

普通模式下在高风险操作弹窗三击头像（仅显式启用时）
  → POST /auth/admin/temporary-session 签发 30 秒、绑定 tab_id 的 scope=admin_once JWT，写入独立 HttpOnly Cookie
  → 紧接着的一个高风险 API 自动携带 Cookie，后端原子标记 jti 已消费
  → 当前操作继续，前端保持普通模式；后续高风险操作必须重新授权
```

### 管理员密码
- 生产安装通过 `/etc/hpcdeploy/hpcdeploy.env` 设置 `HPCDEPLOY_ADMIN_PASSWORD`；首次安装交互设置，开发模式才保留 `admin123` fallback
- JWT `SECRET_KEY` 由安装脚本随机生成并保存在同一 root-only 文件，属于系统内部密钥，用户无需查看或记忆
- 管理员 JWT 保存在 `HttpOnly`、`SameSite=Lax` Cookie 中；Cookie 的 `Secure` 属性按 nginx 转发的实际请求协议设置，HTTP 内网部署可正常回传，HTTPS 部署自动启用 `Secure`
- 可通过系统设置页面修改密码，修改后保存到 `system_settings` 表 `admin_password` 键
- 密码验证优先级：DB 存储密码 → 环境变量 `HPCDEPLOY_ADMIN_PASSWORD`
- 删除 DB 配置后自动回退到环境变量密码，不会锁死
- 密码不返回前端、不打印日志；GET /settings 只返回 `admin_password_configured: bool`
- 忘记密码时由部署服务器 root 执行 `deploy/scripts/reset_admin_password.sh`；脚本先备份 SQLite，再清除 DB 覆盖、更新环境密码并轮换 JWT 密钥，使现有管理员会话失效
- `APP_ENV=production` 时只强制 JWT 密钥为至少 32 位的非默认值；管理员密码内容由部署人员自行决定

### 文件说明
| 文件 | 说明 |
|------|------|
| `backend/app/core/auth.py` | `verify_admin_password()`、`create_admin_token()`（可选时长/标签页绑定 JWT）、`create_one_time_admin_token()`（单次授权）、`require_admin_token()` 依赖 |
| `backend/app/api/auth.py` | 管理员验证、会话状态与退出端点 |
| `frontend/src/composables/useAdminConfirm.ts` | 管理员模式、倒计时、会话恢复与退出 |
| `deploy/scripts/reset_admin_password.sh` | root-only 管理员密码恢复、SQLite 备份和会话失效 |
| `deploy/scripts/redeploy_hpcdeploy.sh` | 生产更新；重启前阻止活动任务期间发布，避免前台 SSH 通道被后端重启切断 |

---

## 7. 任务状态机

```
PENDING → CONNECTING → PREPARING → UPLOADING → RUNNING → SUCCESS
                                                             → FAILED
           任意状态 ──────────────────────────────────────→ CANCELED
```

终态：SUCCESS、FAILED、CANCELED。仅终态允许删除。

### 压测任务最终状态

压测任务的展示状态由 `backend/app/core/task_state_resolver.py` 统一计算，优先级为：报告 `FAIL` → `FAILED`，报告 `PASS` → `SUCCESS`，执行状态 `FAILED` → `FAILED`，其余为 `UNKNOWN`。该规则用于任务卡、批次详情、诊断与批次汇总；不改变数据库中的原始执行状态。

GPU 压测 TXT/XLSX 报告分别记录 `nvidia-smi --query-gpu=driver_version` 检出的 NVIDIA 驱动版本和 `nvcc --version` 检出的 CUDA Toolkit 版本，不使用 `nvidia-smi` 顶部 CUDA Version（驱动最高兼容版本）替代实际安装版本。

`gpu_stress_report.sh`（v2026.08.19.1）为 gpu-burn 实际加载的 `compare.fatbin` 维护服务器级、按本机匹配的编译缓存：只取 `nvidia-smi` 检出的物理 GPU `compute_cap`，并要求当前 CUDA Toolkit 支持每一种架构。首次或缓存不匹配时，在 `/opt/software/gpu-burn` 用 `make COMPUTE= NVCCFLAGS='-gencode=arch=compute_XX,code=sm_XX …'` 禁用 Makefile 的单一 PTX 默认值并重编译；每次启动均以 `cuobjdump --list-elf` 验证 fatbin 确有本机所需 SM。缓存状态同时记录源码指纹、CUDA Toolkit 版本和目标 SM，任一变化或校验失败都会清理旧二进制、fatbin、对象文件后重建；匹配时直接复用。构建锁避免同一服务器并发任务同时清理或编译。每张卡仍以独立 `CUDA_VISIBLE_DEVICES` 实例并发运行，因此 RTX 4090（SM89）与 RTX 5090（SM120）等混合服务器均会参与同一次压测。gpu-burn 的 CR 高频进度在管道中实时拆分，只保留每 10% 的进度样本、错误和每卡汇总，不再写入或回读多 GB 原始日志；任一设备编译或运行失败会使最终报告为 FAIL。

为避免 gpu-burn 多卡实例把部分设备初始化失败掩盖为整体运行，GPU 压测以每张 GPU 一个受限 `CUDA_VISIBLE_DEVICES` 实例执行；同一算力仅复用已编译的原生 SM 二进制，不复用运行进程。每卡日志和退出码写入汇总日志，报告及任务诊断据此定位具体受影响设备。诊断摘要会读取回收的 `stress_gpu*.log`；出现 `no kernel image is available for execution on the device` 时，明确归因为“GPU 内核镜像无法加载”，而不是笼统的报告 FAIL。

GPU 压测默认使用服务器已验证可用的 `/opt/software/gpu-burn` 源码；仅当任一每卡日志明确出现 `no kernel image is available for execution on the device` 时，立即终止本轮全部 gpu-burn 进程（含子进程），再从固定共享地址 `http://171.221.252.54:8573/chfs/shared/%E5%85%B6%E4%BB%96%E5%B8%B8%E7%94%A8%E8%BD%AF%E4%BB%B6%EF%BC%88%E5%90%AB%E5%8E%8B%E6%B5%8B%E8%84%9A%E6%9C%AC%E7%AD%89%EF%BC%89/Stress%E5%8E%8B%E6%B5%8B%E7%9B%B8%E5%85%B3%E8%84%9A%E6%9C%AC/gpu-burn-master.zip` 以 `wget` 的 GET 请求下载、检查 ZIP 路径安全、解压并原子替换源码后重新编译并重试一次。该 CHFS 地址对 HEAD 请求可返回 404，不能据此判定文件不可下载；应以实际 GET 下载结果为准。下载或新版重试失败会保留准确日志并终止，不把网络或工具升级失败伪装为硬件压测结论。

若 `/opt/software/gpu-burn/Makefile` 在压测启动前不存在，脚本将其视为受控依赖缺失：仅此时从用户指定的共享 ZIP 下载、检查归档路径安全、解压并原子替换本地源码目录，然后继续本机匹配 fat binary 构建；已有可用源码时不会下载。恢复下载失败会显示“gpu-burn 源码缺失”，不会误报为硬件压测异常。

任务列表、单任务详情和批次子任务共用缓存摘要中的 `failure_reason`。结构化诊断发现旧版 GPU 脚本已输出 `Start gpu-burn`、却因缺少 `[STAGE] stress_start` 被 300 秒启动超时终止时，归因为平台阶段协议不一致，并将中文诊断结论写入该字段；原始 `Task.error_message` 保留用于日志和审计。

任务卡的“详情说明”使用缓存诊断中的 `outcome_title`，只展示基于已验证日志/报告证据的短结论；任务详情继续展示完整 `failure_reason`。若压测报告为 FAIL 但无更具体证据，卡片保守显示“GPU 压测报告未通过”，不会将“任务执行成功”误作压测通过；证据、原始错误和处理建议仍只在详情/诊断中展开。

失败原因遵循“先取证，再归因”：只有命中回收日志、报告、退出码或状态机中的明确证据时，才在详情展示具体根因；例如 Bash `unbound variable` 会自动提取变量名并明确归因为脚本实现错误。已生成且明确的 GPU、CPU/内存、磁盘报告以其 `Reason:` / `判定原因:` 为首要证据，卡片显示第一句准确结论、详情保留完整原因；CPU/内存报告若命中可纠正 ECC MCE（CE/CECC），则明确显示“可纠正 ECC 内存错误”，不再泛化为内核异常。未生成报告、报告原因缺失或准备阶段失败时，平台继续依据任务阶段、退出码、任务/回收日志、SSH 状态与硬件探测运行规则归因，例如 root 权限、准备超时、SSH 认证、服务器重启、报告回收、GPU 内核镜像和脚本变量错误。两类证据均不足时，才显示“未能从已回收日志确认具体根因，请查看任务日志与结果文件”；“疑似重启”等推测不作为失败原因写入详情，仍可在诊断建议中提示核查方向。

前端任务展示通过 `frontend/src/utils/taskPresentation.ts` 接受单任务与批次详情的结构兼容输入，统一计算功能分类、模块名称、GPU 精度、受控套件动作、批次步骤名称和最终状态；仪表盘、服务器详情与历史任务均传入完整任务对象，`script` 只有缺少文件上下文时才回退显示为“服务器环境”，避免把 MPI 编译环境误标为基础环境。`taskError.ts` 统一选择 `outcome_message`、`failure_reason`、`error_message` 并将已识别英文错误格式化为中文；单次详情、批次详情和列表共用这一规则，原始文本保留在日志与结果文件中。后端仅在确认整个安装任务未产生安装动作时返回成功跳过说明：单组件或依赖步骤跳过不计入，oneAPI 与 AOCC/AOCL/OpenMPI 等组合安装必须全部目标组件均已存在。单次和批次组件只保留布局及各入口已有的兜底文案。

### 压测运行续租与报告回收

- 远端脚本先写入临时 XLSX，再原子替换最终文件名；采集端下载到本地 `.part`，完成 ZIP 完整性校验后再原子入库。
- 运行中的压测任务每次 SSH 健康轮询都会更新 heartbeat/lease；后端重启后通过 SSH 检查远端 PID，并恢复对应监控线程。
- GPU、CPU/内存和磁盘压测脚本依次输出 `[STAGE] dependency_check_start`、`[STAGE] dependency_check_done`、`[STAGE] stress_start`。后端在 `stress_start` 前保持 `PREPARING`，准备期上限为 30 分钟；收到标记才切换 `RUNNING`、重置任务开始时间。用户压测时长加报告回收宽限仅用于标记“预计完成已延后”：远端 PID 和 SSH 健康时持续监控，不因该阈值失败；PID 异常退出、服务器重启、SSH 恢复失败或准备期无启动标记才判失败。依赖安装、下载或编译不再侵占用户设定的压测时长。
- 三类 Linux 压测脚本在 RPM 系发行版上只请求实际缺失的软件包；DNF/YUM 下载默认以 `51200 B/s` 为最低速率、30 秒为网络超时、单次包下载重试 2 次，外层安装最多尝试 3 次并在第二次起刷新元数据。默认值可分别通过 `HPCDEPLOY_DNF_MINRATE`、`HPCDEPLOY_DNF_TIMEOUT`、`HPCDEPLOY_DNF_RETRIES`、`HPCDEPLOY_DNF_INSTALL_ATTEMPTS` 覆盖。安装最终失败时脚本在准备阶段立即退出并保留明确错误，不使用外层 `timeout` 强杀可能已进入 RPM 事务的包管理器；Debian/Ubuntu 的 APT 行为保持不变。
- 压测套件以服务器为批次边界：每台服务器使用独立 `batch_id`，同服务器的 GPU、CPU/内存前置任务串行；多个磁盘子任务共享最后一个前置任务并行运行，不同服务器批次也并行。批次取消、重试和结果文件只作用于对应服务器；一次多服务器请求通过响应中的 `batch_ids`/`batches` 关联，不合并为历史页中的单个批次。

---

## 8. WebSocket 实时日志（Phase 23A）

- 端点：`/api/tasks/{task_id}/logs/ws`
- 浏览器连接成功后每 30s 发送一次文本 `ping`；连接关闭时清理前端心跳定时器
- 消息为扁平 JSON：日志使用 `{ "type": "log", "task_id", "level", "line", "created_at" }`，状态和终态分别使用 `{ "type": "status|done", "task_id", "status" }`
- 前端 `useTaskWebSocket` composable 管理生命周期
- HTTP 每 2s 始终并行拉取任务和完整日志，用于状态刷新、去重和补齐漏收消息；当前 WebSocket 断开后不主动重连
- 多 uvicorn worker 场景下，WebSocket 连接所在 worker 每秒 tail 数据库 `task_logs` 和任务状态；同进程 `ws_manager` 即时广播仍保留

---

## 9. 结构化监控（Phase 24B）

- 端点：`GET /api/tasks/{task_id}/monitor`
- 返回独立数据：CPU/内存、磁盘、GPU
- GPU 数据直接取自 `nvidia-smi --query-gpu`：索引、名称、利用率、显存、温度、风扇转速、实时/上限功耗、性能状态与 PCIe Bus-ID；字段以可选方式扩展，兼容不支持部分指标的驱动或设备
- 子系统隔离（单个 section 失败不影响其他）
- SSH 连接失败 → 全部 section `available=false`
- 5s 轮询，仅 activeTaskId + monitor tab 激活时拉取

---

## 10. 前端布局架构

| 元素 | 定位 | 样式 |
|------|------|------|
| `.app-sidebar` | `fixed; left: 0; top: 0; bottom: 0` | `width: 236px; z-index: 30` |
| `.app-main-area` | `margin-left: 236px` | `height: 100vh; overflow-y: auto` |
| `.app-topbar` | `position: sticky; top: 0` | `height: 56px; z-index: 20` |
| `.app-content` | 在 main-area 内 flex: 1 | `padding: 20px 24px` |

侧边栏“历史任务”每 5 秒轻量查询一次活动任务总数（CONNECTING、PREPARING、UPLOADING、WAITING_REBOOT、RUNNING、CANCELING），作为跨页面与异常恢复兜底；历史任务成功刷新、路由切换、任务创建及页面重新可见时会立即同步计数。刷新请求采用 trailing queue，并发期间到达的多个刷新信号合并为一次后续请求，不丢失任务终态同步。页面不可见时暂停轮询。所有任务创建成功分支以及点击“运行 N”均进入历史任务的运行筛选；运行筛选使用 `active_only` 并保留完整批次上下文，首次查询处于全 PENDING 窗口时等待一次自动刷新后再决定是否退出筛选。单次任务显示单次卡，批次任务在普通历史和运行筛选中均显示完整批次卡。

任务取消交互统一为异步提交反馈：确认后立即关闭确认弹窗，发起取消的单任务卡片或批次详情按钮按任务 ID 独立显示“取消中…”，后端刷新为 `CANCELING` 后显示“正在取消”，进入终态后取消按钮消失。批次级取消沿用批次卡片/表格按钮的独立 loading 状态；取消接口仍负责远端进程终止、结果回收和状态落库。

---

## 11. 服务部署

```bash
# 开发模式 — 后端
cd ~/projects/hpc-deploy/backend
PYTHONPATH=.deps:. .deps/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 开发模式 — 前端
cd ~/projects/hpc-deploy/frontend
npm run dev

# 生产模式
# hpcdeploy-backend.service → uvicorn
# nginx.service → frontend/dist 静态文件 + /api/ 反向代理
```
