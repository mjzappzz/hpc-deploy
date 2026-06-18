# HPCDeploy 下一位 AI 接手说明

请先阅读：

1. docs/architecture.md
2. docs/development-stages.md
3. docs/progress.md
4. docs/next-ai-handoff.md

## 当前项目定位

HPCDeploy 是一个面向 HPC 运维的脚本执行控制台。

核心链路：

```
脚本知识库 → 选择服务器 → 选择脚本 → SSH 上传 → 远程执行 → 实时日志 → 资源快照 → 任务历史 → 结果文件回收下载
```

当前不做：
- WebSocket
- 任务取消
- 复杂 Server Lock
- mpi 真实安装脚本执行
- apptainer run / exec
- AI 助手
- 多用户权限
- 复杂 params_schema
- 前端传 command
- 前端传 remote_path
- 前端传 timeout

## 当前阶段

MVP 收口已完成，下一阶段进入阶段 10B：mpi / 编译环境脚本轻量执行验证。

## 最新状态说明

- 后端同服务器防重复提交已生效。
- 现状确认：旧 PENDING 任务会被当作运行中任务，阻塞同服务器新任务提交。
- 本次已通过 SQLite 手动将旧 PENDING 任务改为 FAILED，用于解除阻塞。
- 当前状态：新任务已可正常提交。
- 后续建议：补“卡住任务清理”能力，自动或半自动处理遗留 PENDING；当前先不做。
- Apptainer 容器分发已完成。
- 后端知识库目录：`backend/apptainer/`
- 前端任务类型：`Apptainer 容器`
- 远端固定目录：`$HOME/hpcdeploy/apptainer/`
- 当前只做上传分发：SSH 连接、创建远端目录、上传 `.sif` 文件，不 `chmod`，不执行 `apptainer run / exec`
- 任务日志固定会出现：`apptainer distribution completed, file was uploaded but not executed`
- `.sif` 文件不建议提交到 Git，应通过知识库上传或本地放置。

## 已完成功能

### 脚本知识库
- 4 个固定目录：mpi / stress / test / apptainer
- 支持上传、下载、预览（文本文件）、删除
- 按类型过滤展示

### 服务器管理
- CRUD + SSH 测试 + 硬件探测（OS/CPU/内存/GPU/磁盘/网络）

### 任务执行（task-runner）
- 左侧配置面板：服务器选择、任务类型、知识库文件、执行参数、命令预览、校验/执行按钮
- 右侧实时面板：执行日志（HTTP 1s 轮询）、资源快照（手动刷新）
- 三种模式切换：config（新建）、summary（执行摘要）、config-readonly（只读配置快照）
- stress 参数：小时/分钟/秒 → 总秒数
- Apptainer 参数区固定显示：`~/hpcdeploy/apptainer/`
- Apptainer 命令预览固定显示：复制容器到远程目录

### 后台执行
- 状态流转：PENDING → CONNECTING → PREPARING → UPLOADING → RUNNING → SUCCESS/FAILED
- test：bash ./脚本名（timeout 120s）
- stress：./脚本名 duration_seconds（timeout = max(duration+300, 300)）
- apptainer：上传 `.sif` 到 `$HOME/hpcdeploy/apptainer/`，不执行
- mpi：当前仍不真实执行
- 所有 SYSTEM/INFO/ERROR 日志写入 task_logs 表
- 同服务器防重复提交已生效：同一服务器存在运行中任务时拒绝新提交
- 已知现象：历史遗留 PENDING 任务同样会触发拦截，需要人工清理或后续补清理能力

### 资源快照
- POST /api/tasks/{task_id}/monitor
- 白名单 type：top / free / ps / cpu_mem / iostat / df / disk / nvidia-smi / gpu

### 任务历史
- 任务列表（降序）
- 查看日志弹窗
- 继续查看（跳转到 task-runner + 恢复任务）
- 结果文件弹窗（仅 stress 已完成任务）

### 结果文件回收（阶段 9A）
- 新增模块：backend/app/core/artifact_collector.py
- 回收时机：stress 执行结束后，executor 关闭前
- SFTP 列出远端文件 → 过滤允许后缀 → 下载到本地
- 允许回收：.log / .txt / .csv / .xlsx / .json
- 禁止回收：.sh / .py / .sif / 隐藏文件 / 目录 / 软链接
- 本地目录：backend/data/artifacts/{task_id}/
- 失败不影响任务状态（不覆盖 exit_code，不把 SUCCESS 改成 FAILED）
- 安全性：远端文件名 basename 检查 + 本地路径 resolve() 防逃逸

#### 结果文件 API

GET /api/tasks/{task_id}/artifacts
返回：
```json
{
  "artifact_dir": "backend/data/artifacts/task-20260617-145709-30d363/",
  "files": [
    {
      "name": "cpu_mem_report_...xlsx",
      "size": 17711,
      "type": "xlsx",
      "local_relative_path": "backend/data/artifacts/.../xxx.xlsx",
      "download_url": "/api/tasks/.../artifacts/xxx.xlsx/download"
    }
  ]
}
```

GET /api/tasks/{task_id}/artifacts/{filename}/download
→ FileResponse (application/octet-stream)

## 当前已完成摘要

1. 服务器管理
   - 新增服务器
   - SSH 测试
   - 服务器信息探测

2. 脚本知识库
   - 后端目录：
     - `backend/scripts/mpi`
     - `backend/scripts/stress`
     - `backend/scripts/test`
     - `backend/apptainer`
   - 支持扫描、上传、下载、删除、预览
   - `.sh` / `.py` / `.txt` / `.md` 可预览
   - `.sif` 不预览，只显示文件信息和下载

3. test 脚本执行
   - `test/hello.sh` 可以上传、`chmod`、执行
   - `stdout/stderr` 写入 `task_logs`
   - `exit_code=0` 时任务 `SUCCESS`

4. stress 压测执行
   - `stress` 脚本支持真实执行
   - 支持时/分/秒输入，后端换算 `duration_seconds`
   - `timeout_seconds = max(duration_seconds + 300, 300)`
   - 实时日志通过 HTTP 轮询，不使用 WebSocket

5. 资源快照
   - 支持 CPU/内存、磁盘 IO、GPU
   - 通过白名单监控命令实现
   - 不允许前端传 `command`
   - 快照失败不影响任务状态

6. 任务历史
   - 查看任务状态
   - 查看日志
   - `RUNNING` 等未完成任务支持“继续查看”
   - `SUCCESS / FAILED` 不显示“继续查看”，只显示“查看日志”
   - `stress` 完成任务支持“结果文件”

7. stress 结果文件回收
   - 远端结果文件回收到 `backend/data/artifacts/{task_id}/`
   - 支持回收：`.log`、`.txt`、`.csv`、`.xlsx`、`.json`
   - 不回收：`.sh`、`.py`、`.sif`、隐藏文件、目录、软链接
   - 前端可以下载结果文件

8. Apptainer 分发
   - 知识库目录：`backend/apptainer/`
   - 远端目录：`$HOME/hpcdeploy/apptainer/`
   - 当前只做 SSH 连接、创建远端目录、上传 `.sif`
   - 不 `chmod`
   - 不执行 `apptainer run / exec`
   - 日志应包含：`apptainer distribution completed, file was uploaded but not executed`

9. 同服务器防重复提交
   - 同一 `server_id` 同时只允许一个未完成任务
   - 未完成状态：`PENDING`、`CONNECTING`、`PREPARING`、`UPLOADING`、`RUNNING`
   - 已完成状态：`SUCCESS`、`FAILED`
   - 如果有旧 `PENDING` 卡住，可用 SQLite 清理。

## 当前仍不做

- WebSocket
- 任务取消
- 复杂 Server Lock
- mpi 真实安装脚本执行
- apptainer run / exec
- AI 助手
- 多用户权限
- 复杂 params_schema
- 前端传 command
- 前端传 remote_path
- 前端传 timeout

## 关键文件清单

### 后端
- backend/app/api/tasks.py — 任务 API（含 artifacts 端点）
- backend/app/core/task_runner.py — 执行编排
- backend/app/core/artifact_collector.py — 结果文件回收
- backend/app/core/ssh_executor.py — SSH/SFTP
- backend/app/core/script_library.py — 脚本库管理
- backend/app/schemas/task.py — Pydantic 模型
- backend/app/db/database.py — 数据库引擎 + 迁移

### 前端
- frontend/src/views/TaskRunner.vue — 任务执行页
- frontend/src/views/TaskHistory.vue — 任务历史 + 结果文件弹窗
- frontend/src/components/TaskCard.vue — 任务卡片组件
- frontend/src/api/task.ts — 任务 API 调用
- frontend/src/components/LogViewer.vue — 日志展示组件

## 下一步建议

- 下一阶段：阶段 10B，mpi / 编译环境脚本轻量执行验证。
- 只允许执行 `backend/scripts/mpi/mpi_env_test.sh`。
- 不要执行真实 OneAPI / OpenMPI / AOCC / AOCL 安装脚本。
