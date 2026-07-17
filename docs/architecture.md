# HPCDeploy 系统架构说明

> 本文档描述 HPCDeploy 当前实际系统架构，非设计阶段草案。

适用于修改 API、任务调度、SSH/SFTP、数据模型、权限或安全边界前的影响评估。安装、升级和服务排障请阅读 [../deploy/README.md](../deploy/README.md)。

---

## 1. 总体架构

```
浏览器 ── HTTP/WS ──→ FastAPI ──→ SQLite
                         │
                    Paramiko SSH/SFTP
                         │
                    ┌────┴────┐
                    目标服务器
```

| 组件 | 选型 |
|------|------|
| 浏览器前端 | Vue 3 + Element Plus |
| 后端 API | FastAPI |
| 数据库 | SQLite |
| 远端执行 | Paramiko SSH / SFTP |
| 实时日志 | WebSocket + HTTP 轮询双通道 |
| 部署 | systemd 服务 |

### 文件目录

```
backend/data/artifacts/    # 结果文件回收目录
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
- 探测全部（`/probe-all`），默认跳过离线服务器，支持显式指定 server_ids
- 标签管理（`/tags` 统计、`tag` 参数筛选）
- 标签基于 `tags_json TEXT` 列存储，包含在线/离线计数

### tasks API (`/api/tasks`)
- 任务创建、批量创建（`/batch`）
- 压测套件创建（`/stress-suite`），同服务器内按 GPU → CPU/内存 → 磁盘串行推进
- 批次压测子任务重跑（`/{task_id}/retry-in-batch`）：仅支持白名单压测脚本中执行失败、取消、超时或报告 FAIL 的子任务；重跑任务追加到同批次、同服务器队列末尾，并阻止重复排队
- 任务列表 `scope=single|batch`：按是否存在 `batch_id` 筛选单次任务或批次子任务，保持分页总数准确；`active_only=true` 统计 CONNECTING、PREPARING、UPLOADING、RUNNING、CANCELING 全部活动任务；`include_batch_context=true` 在状态筛选时保留命中批次的完整子任务
- 状态查询、取消；管理员删除本机任务记录（`POST /api/tasks/{task_id}/local-artifacts/cleanup`）和整批记录（`POST /api/tasks/batches/{batch_id}/local-artifacts/cleanup`）
- 删除仅允许终态任务：清理本地 artifacts、任务日志和数据库任务记录，**不删除远端目录**，审计日志保留
- 日志查询、日志下载、WebSocket 实时日志（`/logs/ws`）
- 失败诊断（`/{task_id}/diagnosis`）
- 结构化监控（`/{task_id}/monitor` — CPU/内存/磁盘/GPU 5s 轮询）
- 历史任务统一展示：普通任务按单次任务卡展示；同一 `batch_id` 在前端聚合为批次卡，首页展示批次概览，批次详情弹窗展示完整子任务信息
- 历史任务卡片统一展示模块、文件、远程目录、命令、计划时长、开始/结束/耗时、报告状态和失败原因
- 重跑链以最新一次尝试计算批次当前状态；旧尝试仅作为历史审计记录保留
- 结果文件入口先展示 artifact/result 文件列表，再由用户选择具体文件下载
- 批次报告下载：单服务器批次生成 `服务器名称_压测报告_日期.zip`，多服务器批次生成 `batch_id.zip` 并按服务器目录拆分
- 任务历史查询默认过滤 `hidden_from_history=1` 的软隐藏记录；keyword 支持匹配任务 ID、批次 ID、脚本名、服务器名称与主机地址

### scripts API (`/api/scripts`)
- 脚本知识库文件列表、上传、预览、下载、删除
- 按类型筛选（mpi/stress/apptainer）

### cleanup API (`/api/cleanup`)
- 本地结果文件目录扫描与删除已整合到系统设置页面，旧清理中心页面和 `/cleanup` 前端路由已删除
- 本地结果文件按真实任务记录聚合：普通任务返回任务名称、任务 ID、任务类型；批次任务按 `batch_id` 聚合并返回所有子任务名称、task_id、目录、文件数和大小
- 本地结果删除后默认只软隐藏历史记录：设置 `tasks.hidden_from_history=1`、`hidden_reason`、`hidden_at`，保留数据库记录
- 本地结果按任务完成时间（无结束时间时开始/创建时间）排序；未匹配数据库任务的遗留目录才使用文件 mtime
- 本地报告自动清理状态查询（`GET /api/cleanup/auto-cleanup/status`），配置保存走 settings API
- Apptainer 镜像目录只读查看
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

### task runner
- 基于 `setsid --wait` 启动进程组
- PID 写入 `.hpcdeploy.pid` 文件；脚本任务结束时写入 `.hpcdeploy.exit_code`
- SSH executor 封装 Paramiko 连接、重试、超时
- stress 后台执行使用完全 detach 的 `setsid bash -lc ... < /dev/null`，远端启动成功只代表任务进入 `RUNNING`
- stress-suite 调度按 `server_id` 加锁，只有前序子任务进入终态后才启动下一子任务
- 后端重启后，RUNNING 脚本任务通过远端 PID 与退出码文件恢复监控，不重新下发远端命令；stress 恢复 SSH 连接临时失败时，先重试 3 次，仍失败则保留 `RUNNING` 并在 60 秒后继续恢复，不将控制面连接错误误判为远端任务失败；已恢复的活动压测子任务结束后，套件调度继续后续任务

### ssh detector
- 执行固定的安全探测命令
- 解析 OS/CPU/内存/磁盘/GPU 信息
- 不依赖前端输入

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
| `tags_json` | TEXT DEFAULT '[]' | 标签 JSON 数组 |
| `last_check_at` | DATETIME | 最后探测时间 |
| `last_error` | TEXT | 最后错误 |

说明：只保留标签，不做分组。`group_name` 列仍存在于数据库但不再使用。

### tasks 表关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | VARCHAR(64) | 任务唯一 ID；本地 artifacts 一级目录名 |
| `batch_id` | VARCHAR(64) | 批次 ID；同一批次下多个子任务共享 |
| `task_type` | VARCHAR(50) | 任务类型：script / stress / apptainer |
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

### 参数白名单
- stress 参数只允许数字
- 禁止 `command` / `raw_args` / `shell` / `raw_command` 参数键

### 路径白名单
- 远端清理只允许 `tasks` / `downloads` / `tmp`
- 不清理 `$HOME/hpcdeploy/apptainer`
- 删除任务时远端路径必须匹配 `hpcdeploy/tasks/{type}/{timestamp}` 格式

### 禁止 raw command
- 前端不传 `command`、`remote_path`
- 所有命令由后端按任务类型固定生成

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
| 执行任务/压测套件 | `POST /api/tasks` |
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

### 认证流程

```
用户开启管理员模式
  → POST /auth/admin/verify 输入管理员密码、选择 5 / 15 / 30 / 60 分钟或本标签页持续
    → 后端签发绑定 `tab_id` 的 JWT，并写入 HttpOnly、SameSite=Lax Cookie
  → 前端显示倒计时；刷新时 GET /auth/admin/status 恢复未过期会话
  → 高风险 API 由 require_admin_token() 验证 JWT 签名 + scope=admin，并要求 `X-Admin-Tab-Id` 与 JWT 内 `tab_id` 一致
  → 手动退出 POST /auth/admin/logout 清除 Cookie；超时或关闭标签页后切回普通模式
  → 通过后执行操作，审计日志 actor="admin"
```

### 管理员密码
- 通过环境变量 `HPCDEPLOY_ADMIN_PASSWORD` 设置，默认值 `admin123`
- 可通过系统设置页面修改密码，修改后保存到 `system_settings` 表 `admin_password` 键
- 密码验证优先级：DB 存储密码 → 环境变量 `HPCDEPLOY_ADMIN_PASSWORD`
- 删除 DB 配置后自动回退到环境变量密码，不会锁死
- 密码不返回前端、不打印日志；GET /settings 只返回 `admin_password_configured: bool`

### 文件说明
| 文件 | 说明 |
|------|------|
| `backend/app/core/auth.py` | `verify_admin_password()`、`create_admin_token()`（可选时长/标签页绑定 JWT）、`require_admin_token()` 依赖 |
| `backend/app/api/auth.py` | 管理员验证、会话状态与退出端点 |
| `frontend/src/composables/useAdminConfirm.ts` | 管理员模式、倒计时、会话恢复与退出 |

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

### 压测运行续租与报告回收

- 远端脚本先写入临时 XLSX，再原子替换最终文件名；采集端下载到本地 `.part`，完成 ZIP 完整性校验后再原子入库。
- 运行中的压测任务每次 SSH 健康轮询都会更新 heartbeat/lease；后端重启后通过 SSH 检查远端 PID，并恢复对应监控线程。

---

## 8. WebSocket 实时日志（Phase 23A）

- 端点：`/ws/tasks/{task_id}`
- 心跳间隔 30s，超时 60s 清理
- 消息格式：`{ "type": "log|status|done", "data": {...} }`
- 前端 `useTaskWebSocket` composable 管理生命周期
- HTTP 轮询作为备用通道，WS 断线自动切换
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

侧边栏“历史任务”每 5 秒轻量查询一次活动任务总数（CONNECTING、PREPARING、UPLOADING、RUNNING、CANCELING）；存在活动任务时显示绿色状态点和数量，页面不可见时暂停轮询。创建任务后立即刷新，点击“运行 N”会跳转历史任务并应用 `RUNNING` 状态筛选。

---

## 11. 服务部署

```bash
# 开发模式 — 后端
cd ~/projects/hpc-deploy/backend
PYTHONPATH=.deps:. .deps/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 开发模式 — 前端
cd ~/projects/hpc-deploy/frontend
npm run dev

# 生产模式（systemd）
# hpcdeploy-backend.service → uvicorn
# hpcdeploy-frontend.service → npm run dev
```
