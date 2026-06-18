# HPCDeploy 阶段开发计划

版本：v2.0  
用途：给后续开发按阶段推进使用  
原则：先收敛主线，再逐步扩展；每个阶段只解决当前明确范围内的问题。

---

## 0. 当前主线

HPCDeploy 当前主线已从“复杂通用 params_schema 平台”收敛为：

```text
脚本知识库
↓
任务执行器
↓
任务历史 / 结果回收
```

当前聚焦四类知识库目录：

```text
backend/scripts/mpi
backend/scripts/stress
backend/scripts/test
backend/apptainer
```

当前不再把通用参数平台作为主线目标。参数只保留最少的、与任务执行直接相关的输入。

---

## 1. 开发总原则

开发顺序：

```text
先完成脚本知识库收敛
↓
再简化任务执行页
↓
再补真实远程执行
↓
再做结果回收
↓
最后补实时日志、并发控制和部署强化
```

执行原则：

```text
1. 不做复杂编排
2. 不做 AI 助手能力
3. 不做通用参数 Schema 平台
4. 不做 WebSocket（用 HTTP 轮询替代）
5. 不做 Server Lock（用简单防重复提交替代）
6. 所有新增功能优先服务核心主链路
7. 安全优先：白名单执行、前端不传命令、路径防逃逸
```

---

## 2. 已完成阶段

```text
阶段 1：项目骨架初始化
阶段 2：数据库模型与基础 API
阶段 3：前端基础页面
阶段 4：SSH 连通性测试
阶段 5：服务器信息探测
阶段 6：脚本白名单与脚本管理基础能力
阶段 7A：脚本知识库改造
阶段 7B：任务执行页简化
阶段 8A：任务模型收口与任务创建
阶段 8B：远程目录创建与文件上传
阶段 8C：test 脚本真实执行
阶段 8D：stress 压测脚本执行
阶段 8E：任务执行页交互完善
阶段 9A：stress 结果文件回收
阶段 9B：Apptainer 容器分发
阶段 10A：HTTP 轮询实时日志（替代 WebSocket）
阶段 10B：MPI 脚本轻量执行验证
阶段 10C：任务执行页重构三模式
阶段 10D：部署强化（systemd + PATH 修复）
阶段 11A：同服务器防重复提交
阶段 11B-11E：任务取消完整链路（PID→PGID→kill→清理）
阶段 12A：任务历史删除
阶段 12B：任务历史筛选/搜索/分页优化
```

---

## 3. 实际执行阶段

### 阶段 7A：脚本知识库改造
把原”脚本管理”收敛为固定目录的知识库（mpi/stress/test/apptainer），支持上传/下载/预览/删除，二进制文件只显示元信息。

### 阶段 7B：任务执行页简化
收敛为服务器选择 + 任务类型 + 知识库文件选择，压测时长参数（时/分/秒），命令预览。

### 阶段 8A：任务模型收口与任务创建
`POST /api/tasks/run` 创建任务，task_type/file_path/params 字段，返回 task_id。

### 阶段 8B：远程目录创建与文件上传
SSH 连接 → 创建远端 `~/hpcdeploy/tasks/{type}/{task_id}/` → 上传脚本 → chmod +x → 写 task_logs。

### 阶段 8C：test 脚本真实执行
test 类型 `bash ./script.sh`，实时 stdout/stderr → task_logs，保存 exit_code。

### 阶段 8D：stress 压测脚本执行
stress 类型 `./script.sh duration_seconds`，时长限制 1-3600s，timeout = max(duration+300, 300)，资源快照。

### 阶段 8E：任务执行页交互完善
config/summary/config-readonly 三模式，URL query 恢复任务，新建任务清空状态。

### 阶段 9A：stress 结果文件回收
SFTP 拉取远端文件到 `backend/data/artifacts/{task_id}/`，白名单后缀 .log/.txt/.csv/.xlsx/.json，失败不影响任务状态。

### 阶段 9B：Apptainer 容器分发
上传 `.sif` 到 `$HOME/hpcdeploy/apptainer/`，不做 run/exec，不上传 .sh/.py。

### 阶段 10A：HTTP 轮询实时日志
放弃 WebSocket 方案，采用前端 1s HTTP 轮询替代。

### 阶段 10B：MPI 脚本轻量执行验证
开放 mpi 目录白名单：`mpi_env_test.sh`、`install_oneapi_2022.sh`、`install_openmpi_4.1.6_aocc_aocl.sh`。

### 阶段 10C：任务执行页重构三模式
config（新建）/ summary（执行摘要）/ config-readonly（只读配置快照）模式切换。

### 阶段 10D：部署强化
前后端 systemd 服务化，修复 systemd 下 nvm PATH 问题。

### 阶段 11A：同服务器防重复提交
同一 server_id 同时只允许一个未完成任务（PENDING/CONNECTING/PREPARING/UPLOADING/RUNNING）。

### 阶段 11B-11E：任务取消完整链路
PID 文件（`.hpcdeploy.pid`）→ PGID → 进程组 SIGTERM/SIGKILL，远端工作目录清理，临时目录白名单清理（`/tmp/oneapi_install_2022`、`/tmp/openmpi_aocc_aocl_install`）。

### 阶段 12A：任务历史删除
- `DELETE /api/tasks/{task_id}` — 完整删除（记录 + 日志 + 本地 artifacts + 远端目录）
- `POST /api/tasks/{task_id}/cleanup` — 仅清理文件，保留记录和日志
- 安全校验前置：远端路径格式检查，SSH/安全失败不删数据库
- 前端确认弹窗结构化为"将删除/不会删除"分组排版
- 新增 `TaskDeleteResponse` / `TaskCleanupResponse` Pydantic schema
- 新增 `frontend/src/utils/confirm.ts` 统一确认弹窗工具函数

### 阶段 12B：任务历史筛选/搜索/分页优化
- `GET /api/tasks` 新增 7 个查询参数：status、task_type、server_id、keyword、limit、offset、order
- 返回分页结构 `{items, total, limit, offset}`（代替原数组）
- 参数白名单校验 + 400 响应（非法 status/task_type/order 返回 400 而非 500）
- keyword 使用 SQL ILIKE 参数化查询搜索 task_id、file_path、remote_work_dir、error_message
- limit 默认 50，最大 100；offset 默认 0
- 前端新增筛选区：状态下拉（中文标签）、类型下拉（中文标签）、关键词搜索、重置按钮
- 前端 Element Plus 分页组件，支持 20/50/100 条每页，显示总数和当前范围
- 搜索按钮动态 primary 样式：有筛选条件时变蓝
- 后端适配性：Dashboard 页面同步适配新的分页响应结构


---

# 阶段 1：项目骨架初始化

## 目标

建立前后端基础项目结构，能正常启动。

## 开发内容

### 前端

```text
1. 创建 Vue3 + Vite 项目
2. 安装 Element Plus
3. 安装 Vue Router
4. 安装 Pinia
5. 安装 Axios
6. 建立基础 Layout：左侧菜单 + 顶部栏 + 内容区
```

### 后端

```text
1. 创建 FastAPI 项目
2. 安装 Uvicorn
3. 安装 SQLAlchemy
4. 安装 Pydantic
5. 安装 Paramiko
6. 创建 app/api、app/core、app/models、app/schemas、app/db 目录
```

### 数据库

```text
1. 第一阶段使用 SQLite
2. 建立 database.py
3. 能初始化数据库文件
```

## 验收标准

```text
1. 前端 npm run dev 能启动
2. 后端 uvicorn main:app --reload 能启动
3. 浏览器能访问前端页面
4. /docs 能打开 FastAPI Swagger
5. 数据库能生成 SQLite 文件
```

## 给 AI 的提示词

```text
请先初始化项目骨架，不要实现复杂业务。前端使用 Vue3 + Vite + Element Plus + Pinia + Vue Router + Axios。后端使用 FastAPI + SQLAlchemy + SQLite + Paramiko。只需要让前端和后端能正常启动，并建立清晰目录结构。
```

---

# 阶段 2：数据库模型与基础 API

## 目标

先把核心数据结构建好，能通过 API 管理服务器、脚本、任务记录。

## 开发内容

### 数据库表

必须实现：

```text
1. servers
2. scripts
3. tasks
4. task_logs
```

### servers 表字段

```text
id
name
host
port
username
auth_type
key_path
status
os_info
gpu_info
created_at
updated_at
```

### scripts 表字段

```text
id
name
category
version
file_path
description
enabled
dangerous
params_schema
created_at
updated_at
```

### tasks 表字段

```text
id
task_id
server_id
script_id
status
params
start_time
end_time
exit_code
error_message
created_at
updated_at
```

### task_logs 表字段

```text
id
task_id
level
message
created_at
```

### API

实现：

```text
GET    /api/servers
POST   /api/servers
GET    /api/servers/{server_id}
PUT    /api/servers/{server_id}
DELETE /api/servers/{server_id}

GET    /api/scripts
POST   /api/scripts
GET    /api/scripts/{script_id}
PUT    /api/scripts/{script_id}
DELETE /api/scripts/{script_id}

GET    /api/tasks
GET    /api/tasks/{task_id}
GET    /api/tasks/{task_id}/logs
```

## 验收标准

```text
1. 能新增服务器
2. 能查看服务器列表
3. 能新增脚本元信息
4. scripts 表支持 params_schema 字段
5. tasks 表支持 params 字段
6. Swagger 上能测试所有基础 API
```

## 给 AI 的提示词

```text
请实现数据库模型和基础 CRUD API。重点是 servers、scripts、tasks、task_logs 四张表。scripts 表必须有 params_schema 字段，tasks 表必须有 params 字段。暂时不要实现 SSH 执行，只做数据结构和 API。
```

---

# 阶段 3：前端基础页面

## 目标

先做能操作的基础页面，不追求最终 UI 效果。

## 开发内容

### 页面

实现以下页面：

```text
1. Dashboard.vue
2. Servers.vue
3. Scripts.vue
4. TaskRunner.vue
5. TaskHistory.vue
```

### 组件

实现以下组件：

```text
1. ServerTable.vue
2. ScriptTable.vue
3. TaskCard.vue
4. StatusTag.vue
5. LogViewer.vue
```

### 功能

```text
1. 服务器列表展示
2. 新增服务器表单
3. 脚本列表展示
4. 新增脚本元信息
5. 任务历史展示
```

## 验收标准

```text
1. 能在前端新增服务器
2. 能看到服务器列表
3. 能在前端新增脚本元信息
4. 能看到脚本列表
5. 页面之间路由正常
```

## 给 AI 的提示词

```text
请实现前端基础页面，先不要追求复杂视觉效果。需要有左侧菜单、顶部栏、服务器管理、脚本管理、任务执行、任务历史页面。所有 API 请求封装到 src/api，不要在 Vue 页面里直接写 axios 地址。
```

---

# 阶段 4：SSH 连通性测试

## 目标

先实现最基础的远程服务器连接能力。

## 开发内容

### 后端

实现：

```text
POST /api/servers/{server_id}/test
```

逻辑：

```text
1. 根据 server_id 查询服务器
2. 使用 Paramiko SSH Key 登录
3. 执行 hostname
4. 执行 uname -a
5. 返回成功 / 失败
6. 更新 servers.status
```

### 前端

服务器管理页面增加按钮：

```text
测试 SSH
```

点击后显示：

```text
成功 / 失败
耗时
错误信息
```

## 验收标准

```text
1. 能通过页面点击测试 SSH
2. SSH 成功时服务器状态变为 online
3. SSH 失败时服务器状态变为 offline
4. 能显示失败原因
```

## 给 AI 的提示词

```text
请实现 SSH 连通性测试功能。后端使用 Paramiko，根据服务器表里的 host、port、username、key_path 登录目标服务器，执行 hostname 和 uname -a。前端服务器管理页面增加“测试 SSH”按钮，并显示测试结果。
```

---

# 阶段 5：服务器信息探测

## 目标

获取目标服务器基础环境信息，为后续安装任务做准备。

## 开发内容

### 后端 API

实现：

```text
POST /api/servers/{server_id}/detect
```

执行命令：

```bash
hostname
cat /etc/os-release
uname -r
lscpu | head
free -h
df -h
nvidia-smi || true
which nvcc || true
nvcc --version || true
which mpirun || true
mpirun --version || true
gcc --version || true
cmake --version || true
```

### 保存结果

更新：

```text
servers.os_info
servers.gpu_info
servers.status
```

### 前端

服务器管理页面增加：

```text
探测信息
刷新信息
服务器详情面板
```

## 验收标准

```text
1. 能探测 OS 信息
2. 能探测 GPU 信息
3. 能探测 CUDA / OpenMPI / GCC 状态
4. 前端能显示探测结果
```

## 给 AI 的提示词

```text
请实现服务器信息探测功能。通过 SSH 执行 hostname、os-release、uname、lscpu、free、df、nvidia-smi、nvcc、mpirun、gcc、cmake 等命令。命令失败不能导致整个探测失败，使用 || true。前端显示探测结果。
```

---

# 阶段 6：脚本白名单与脚本上传

## 目标

实现安全脚本执行的前置能力：只允许执行白名单脚本，并上传到远程服务器临时目录。

## 开发内容

### 后端规则

```text
1. 前端只能传 script_id
2. 后端根据 script_id 查询 scripts 表
3. 只有 enabled=true 的脚本允许执行
4. 后端读取本地 file_path
5. 使用 SFTP 上传到目标服务器
6. 远程目录：/tmp/hpc-control-panel/{task_id}/
```

### 禁止

```text
1. 禁止前端传 command
2. 禁止前端传脚本路径
3. 禁止后端执行用户输入的任意命令
```

## 验收标准

```text
1. 能根据 script_id 找到本地脚本
2. 能通过 SFTP 上传脚本到远程服务器
3. 远程服务器能看到 /tmp/hpc-control-panel/{task_id}/script.sh
4. 非白名单脚本不能执行
```

## 给 AI 的提示词

```text
请实现脚本白名单和 SFTP 上传能力。前端只能传 script_id，后端根据 scripts 表查询 file_path，确认 enabled=true 后，把脚本上传到目标服务器 /tmp/hpc-control-panel/{task_id}/script.sh。禁止执行任意 command。
```

---

---

# 下一阶段建议

以下阶段在主线收敛后按需推进：

### 阶段 13：部署与安全增强
- Docker Compose 容器化部署
- Nginx 反代配置（前端静态 + API）
- SSH key 权限自动检查
- 访问控制、日志保留策略

### 阶段 14：前端体验优化
- 仪表盘统计卡片
- 暗色主题
- 任务进度显示
- 状态标签完善

### 后续扩展方向（明确当前不做）
- Apptainer run/exec 执行
- 多用户权限系统
- WebSocket 实时日志
- 复杂 Server Lock
- AI 助手
- 批量编排 / Ansible 集成
- Slurm 作业提交
- 科学计算软件安装模板

---

# 推荐执行顺序总结

回顾实际已完成阶段：

```text
阶段 1：项目骨架初始化
阶段 2：数据库模型与基础 API
阶段 3：前端基础页面
阶段 4：SSH 连通性测试
阶段 5：服务器信息探测
阶段 6：脚本白名单与脚本管理基础能力
阶段 7A：脚本知识库改造
阶段 7B：任务执行页简化
阶段 8A：任务模型收口与任务创建
阶段 8B：远程目录创建与文件上传
阶段 8C：test 脚本真实执行
阶段 8D：stress 压测脚本执行
阶段 8E：任务执行页交互完善
阶段 9A：stress 结果文件回收
阶段 9B：Apptainer 容器分发
阶段 10A：HTTP 轮询实时日志
阶段 10B：MPI 脚本轻量执行验证
阶段 10C：任务执行页重构三模式
阶段 10D：部署强化（systemd）
阶段 11A：同服务器防重复提交
阶段 11B-11E：任务取消完整链路
阶段 12A：任务历史删除
阶段 12B：任务历史筛选/搜索/分页优化
```

---

# 每阶段交付要求

每个阶段完成后，AI 必须输出：

```text
1. 本阶段完成了什么
2. 修改了哪些文件
3. 如何运行
4. 如何测试
5. 当前已知问题
6. 下一阶段建议
```

---

# 每阶段禁止事项

```text
1. 禁止跳阶段一次性做完全部功能
2. 禁止前端直接执行 SSH
3. 禁止后端执行前端传入的任意命令
4. 禁止绕过 scripts 白名单
5. 禁止把 SSH 私钥返回给前端
6. 禁止没有日志的后台任务
7. 禁止任务没有状态
8. 禁止同一服务器无控制地并发安装
```

---

# 最终一句话

本项目开发必须按下面原则推进：

```text
先跑通主链路，再优化 UI，再扩展功能。
```

主链路是：

```text
服务器 → 脚本 → 参数 → SSH执行 → 实时日志 → 任务记录
```
