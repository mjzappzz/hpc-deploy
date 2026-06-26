# HPCDeploy 系统架构说明

> 本文档描述 HPCDeploy 当前实际系统架构，非设计阶段草案。

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
  test/                    # 测试脚本
  stress/                  # 压测脚本
  mpi/                     # MPI / 编译环境脚本
backend/keys/              # SSH 私钥和同名 .pub 公钥
```

---

## 2. 后端模块说明

### servers API (`/api/servers`)
- 服务器 CRUD
- SSH 测试（`/test`）
- 信息探测（`/probe`、`/detect`）
- 一键部署公钥（`/deploy-public-key`）
- 探测全部（`/probe-all`），默认跳过离线服务器
- 标签管理（`/tags` 统计、`tag` 参数筛选）
- 标签基于 `tags_json TEXT` 列存储，包含在线/离线计数

### tasks API (`/api/tasks`)
- 任务创建、批量创建（`/batch`）
- 状态查询、取消、删除
- 日志查询、日志下载、WebSocket 实时日志（`/logs/ws`）
- 失败诊断（`/{task_id}/diagnosis`）
- 结构化监控（`/{task_id}/monitor` — CPU/内存/磁盘/GPU 5s 轮询）

### scripts API (`/api/scripts`)
- 脚本知识库文件列表、上传、预览、下载、删除
- 按类型筛选（test/stress/mpi/apptainer）

### cleanup API (`/api/cleanup`)
- 本地结果文件目录扫描与删除（按 task 目录聚合）
- Apptainer 镜像目录只读查看
- 远端单台/全部在线服务器临时目录扫描与清理
- 清理 target 白名单：只允许 `tasks` / `downloads` / `tmp`

### settings API (`/api/settings`)
- 系统设置读写
- 当前：SSH 默认私钥名称、远端目录只读说明

### audit API (`/api/audit-logs`)
- 审计日志查询与分页（支持 action / target_type / status / keyword 筛选）
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
- PID 写入 `.hpcdeploy.pid` 文件
- SSH executor 封装 Paramiko 连接、重试、超时

### ssh detector
- 执行固定的安全探测命令
- 解析 OS/CPU/内存/磁盘/GPU 信息
- 不依赖前端输入

### diagnosis rules
- 根据任务日志匹配失败模式
- GPU/CUDA 错误、SSH 连接错误、磁盘空间不足、远端路径错误
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
- 脚本必须命中 `backend/scripts/test/`、`backend/scripts/stress/`、`backend/scripts/mpi/`
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

### Apptainer 不执行
- 不执行 `apptainer run` / `apptainer exec`
- 只上传/分发 `.sif` 文件

### 清理中心 target 白名单
- 远端清理 target 代码级硬编码：`tasks` / `downloads` / `tmp`
- 不清理系统目录（`/root`、`/home`、`/tmp`、`/opt`、`/usr`、`/etc`）

### 敏感信息过滤
- `GET /api/ssh-keys` 不返回私钥/公钥内容
- 审计日志不记录密钥内容
- 诊断 evidence 不泄露敏感字段

---

## 6. 任务状态机

```
PENDING → CONNECTING → PREPARING → UPLOADING → RUNNING → SUCCESS
                                                             → FAILED
           任意状态 ──────────────────────────────────────→ CANCELED
```

终态：SUCCESS、FAILED、CANCELED。仅终态允许删除。

---

## 7. WebSocket 实时日志（Phase 23A）

- 端点：`/ws/tasks/{task_id}`
- 心跳间隔 30s，超时 60s 清理
- 消息格式：`{ "type": "log|status|done", "data": {...} }`
- 前端 `useTaskWebSocket` composable 管理生命周期
- HTTP 轮询作为备用通道，WS 断线自动切换

---

## 8. 结构化监控（Phase 24B）

- 端点：`GET /api/tasks/{task_id}/monitor`
- 返回独立数据：CPU/内存、磁盘、GPU
- 子系统隔离（单个 section 失败不影响其他）
- SSH 连接失败 → 全部 section `available=false`
- 5s 轮询，仅 activeTaskId + monitor tab 激活时拉取

---

## 9. 前端布局架构

| 元素 | 定位 | 样式 |
|------|------|------|
| `.app-sidebar` | `fixed; left: 0; top: 0; bottom: 0` | `width: 236px; z-index: 30` |
| `.app-main-area` | `margin-left: 236px` | `height: 100vh; overflow-y: auto` |
| `.app-topbar` | `position: sticky; top: 0` | `height: 56px; z-index: 20` |
| `.app-content` | 在 main-area 内 flex: 1 | `padding: 20px 24px` |

---

## 10. 服务部署

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
