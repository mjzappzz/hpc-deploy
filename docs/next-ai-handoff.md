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
脚本知识库 → 选择服务器 → 选择脚本 → SSH 上传 → 执行脚本 → 实时日志 → 资源快照 → 任务历史 → 结果文件回收下载
```

当前不做：
- 复杂 params_schema 平台
- WebSocket / Server Lock / 任务取消
- mpi / apptainer 真实执行
- 多用户权限
- AI 助手

## 当前阶段

阶段 9A（stress 结果文件回收）已完成。

## 最新状态说明

- 后端同服务器防重复提交已生效。
- 现状确认：旧 PENDING 任务会被当作运行中任务，阻塞同服务器新任务提交。
- 本次已通过 SQLite 手动将旧 PENDING 任务改为 FAILED，用于解除阻塞。
- 当前状态：新任务已可正常提交。
- 后续建议：补“卡住任务清理”能力，自动或半自动处理遗留 PENDING；当前先不做。

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

### 后台执行
- 状态流转：PENDING → CONNECTING → PREPARING → UPLOADING → RUNNING → SUCCESS/FAILED
- test：bash ./脚本名（timeout 120s）
- stress：./脚本名 duration_seconds（timeout = max(duration+300, 300)）
- mpi/apptainer：只上传，不执行
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

## 当前不做（仍禁止）

- WebSocket
- Server Lock
- 任务取消
- 结果文件在线预览
- 结果文件压缩打包
- mpi 真实执行
- apptainer 真实执行
- 多用户权限系统
- 自动删除远端结果文件
- AI 助手

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

### 1. MVP 完整验收
- 创建 60 秒 stress 任务
- 等待 SUCCESS
- 确认 backend/data/artifacts/{task_id}/ 有结果文件
- 确认 task_logs 有 artifact 相关 SYSTEM 日志
- 在任务历史页打开结果文件弹窗
- 下载文件确认内容正确

### 2. 稳定性修复（如果有问题）
- 回收部分失败时的 error_message 提示
- 无结果文件时前端提示已完善
- 资源快照监控超时/失败处理
- 增加“卡住任务清理”能力，避免旧 PENDING 阻塞新任务（当前先不做）

### 3. 后续可能的方向（先不做，仅记录）
- mpi 脚本真实执行（需要解决环境依赖）
- apptainer 容器远程执行
- 任务取消（当前完全不做）
- 多用户权限
