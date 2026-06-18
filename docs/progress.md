# HPCDeploy 项目进度记录

## 当前阶段

当前进行到：MVP 收口完成，下一阶段为阶段 10B：mpi / 编译环境脚本轻量执行验证

当前主线：

```text
脚本知识库
↓
任务执行器
↓
SSH 上传
↓
远程执行
↓
实时日志 + 资源快照
↓
任务历史
↓
结果文件回收下载
```

当前下一步：

```text
阶段 10B：mpi / 编译环境脚本轻量执行验证
```

## 最新状态补充

- 后端同服务器防重复提交已生效。
- 已发现旧 PENDING 任务会阻塞同服务器新任务提交。
- 已通过 SQLite 手动将旧 PENDING 任务标记为 FAILED。
- 当前已恢复为可正常提交新任务。
- 后续建议增加“卡住任务清理”能力，但当前先不做。
- Apptainer 容器分发已完成。
- 后端知识库目录：`backend/apptainer/`
- 前端任务类型：`Apptainer 容器`
- 远端固定目录：`$HOME/hpcdeploy/apptainer/`
- 当前只做上传分发：SSH 连接、创建远端目录、上传 `.sif` 文件，不 `chmod`，不执行 `apptainer run / exec`
- 任务日志会显示：`apptainer distribution completed, file was uploaded but not executed`
- `.sif` 文件不建议提交到 Git，应通过知识库上传或本地放置

## 当前项目定位

HPCDeploy 是一个面向 HPC 运维的轻量级脚本执行控制台。

核心链路：

```text
脚本知识库
→ 选择服务器
→ 选择脚本
→ SSH 上传
→ 远程执行
→ 实时日志
→ 资源快照
→ 任务历史
→ 结果文件回收下载
```

## 已完成阶段

### 阶段 1：项目骨架初始化
- 前端 Vue3 + Vite + Element Plus 已建立
- 后端 FastAPI 已建立
- /api/health 可用
- 前后端开发模式可启动

### 阶段 2：数据库模型与基础 API
- 已实现 servers、scripts、tasks、task_logs 表
- scripts 表包含 params_schema
- tasks 表包含 params
- 已实现基础 CRUD API

### 阶段 3：前端基础页面
- 已实现 Dashboard
- 已实现服务器管理
- 已实现脚本管理
- 已实现任务执行页面占位
- 已实现任务历史页面

### 阶段 4：SSH 连通性测试
- 已实现 POST /api/servers/{server_id}/test
- 前端服务器管理页已有"测试 SSH"按钮
- 能更新 online/offline 状态

### 阶段 5：服务器信息探测
- 已实现 POST /api/servers/{server_id}/detect
- 已实现服务器 OS / CPU / 内存 / GPU / 磁盘 / 网络信息探测
- 前端已有"探测信息"按钮和详情抽屉
- 服务器管理主表格已做摘要展示和 UI 优化

### 阶段 6：脚本白名单与脚本管理
- scripts 表作为脚本白名单表
- 已实现脚本路径安全校验
- 已实现 params_schema JSON 校验
- 已实现 POST /api/scripts/{script_id}/validate
- 已实现 GET /api/scripts/files 自动扫描 backend/scripts/
- 前端脚本文件可下拉选择，不再手动填写远程路径

### 阶段 7A：脚本知识库改造
- 完成目录结构重构为 mpi / stress / test / apptainer
- 前端分类页签：全部 / 编译环境 / 压测脚本 / Apptainer 容器 / 测试脚本
- 支持上传、下载、预览、删除
- 普通用户界面不显示 params_schema

### 阶段 7B：任务执行页简化
- 服务器选择 + 任务类型选择 + 知识库文件选择
- 按类型过滤知识库文件
- 压测时长参数（小时/分钟/秒）
- 命令预览
- 远程工作目录模板

### 阶段 8A：任务模型收口与任务创建
- POST /api/tasks/run 创建任务
- tasks 表已有 task_type / file_path / params 等完整字段
- 返回 task_id，前端跳转任务历史

### 阶段 8B：远程目录创建与文件上传
- SSH 连接目标服务器
- 创建远程工作目录
- 上传知识库文件
- 对 .sh / .py 执行 chmod +x
- 写入 task_logs，任务状态：CONNECTING → PREPARING → UPLOADING → SUCCESS/FAILED

### 阶段 8C：test 脚本真实执行
- test 类型执行 bash ./脚本名
- 实时 stdout/stderr → task_logs（INFO/ERROR 级别）
- 保存 exit_code、end_time
- stress/mpi/apptainer 仍只上传不执行

### 阶段 8D：stress 压测脚本短时间执行
- stress 类型执行 ./脚本名 duration_seconds
- duration_seconds 限制 1–3600 秒
- timeout = max(duration_seconds + 300, 300)
- 实时日志 + 资源快照监控（CPU/内存/磁盘/GPU）
- mpi/apptainer 仍只上传不执行

### 阶段 8E：任务执行页交互完善
- 左侧配置面板（文件信息、执行参数、命令预览、校验/执行按钮）
- 右侧实时面板（执行日志、资源快照）
- 任务摘要展开/收起
- 任务历史页"继续查看"跳转
- URL query 恢复任务
- 新建任务清空状态

### 阶段 9A：stress 结果文件回收
- 新增 artifact_collector.py：通过 SFTP 列出远端文件，过滤允许后缀（.log/.txt/.csv/.xlsx/.json），下载到本地
- 本地保存目录：backend/data/artifacts/{task_id}/
- 回收时机：stress 任务执行结束后（SUCCESS/FAILED），在 executor 关闭前调用
- 不修改任务状态：回收失败不把 SUCCESS 改成 FAILED，不覆盖 exit_code
- 安全性：远端文件名 basename 检查，本地路径防逃逸（resolve() + prefix 检查）
- 新增 API：
  - GET /api/tasks/{task_id}/artifacts → 返回 {artifact_dir, files[{name, size, type, local_relative_path, download_url}]}
  - GET /api/tasks/{task_id}/artifacts/{filename}/download → FileResponse
- 前端：TaskHistory 弹窗显示文件列表 + 本地保存目录 + 下载按钮
- 空状态提示："可能脚本未生成报告或回收失败，请查看任务日志"

### 阶段 9A 补充：同服务器重复提交保护验证
- 后端已增加同服务器运行中任务拦截，防止重复提交。
- 已确认历史遗留的旧 PENDING 任务会被视为运行中任务，从而阻塞新任务。
- 本次已通过 SQLite 手动修正旧 PENDING 任务状态为 FAILED，解除阻塞。
- 修正后已确认当前可以正常提交新任务。
- 后续可补“卡住任务清理”能力，但本阶段先不新增功能。

### 阶段 9B：Apptainer 容器分发
- Apptainer 容器分发已完成。
- 后端知识库目录固定为：`backend/apptainer/`
- 前端任务类型已提供：`Apptainer 容器`
- 远端固定目录为：`$HOME/hpcdeploy/apptainer/`
- 当前行为仅包含：
  - SSH 连接
  - 创建远端目录
  - 上传 `.sif` 文件
  - 不执行 `chmod`
  - 不执行 `apptainer run / exec`
- 任务完成日志固定包含：`apptainer distribution completed, file was uploaded but not executed`
- `.sif` 文件不建议提交到 Git，应通过知识库上传或本地放置。

## 当前完整主链路

```text
脚本知识库
  ↓ 上传/管理脚本文件
任务执行准备（服务器 + 任务类型 + 知识库文件）
  ↓ POST /api/tasks/run
SSH 连接（CONNECTING → PREPARING → UPLOADING）
  ↓
远端执行 / 分发
  ├─ test: bash ./脚本名
  ├─ stress: ./脚本名 duration_seconds
  └─ apptainer: 上传 .sif 到 $HOME/hpcdeploy/apptainer/
  ↓
实时日志轮询（1s interval） + 资源快照（手动刷新）
  ↓
任务历史（SUCCESS / FAILED）
  ↓
结果文件回收（仅 stress）
  └─ SFTP 下载到 backend/data/artifacts/{task_id}/
      └─ .log / .txt / .csv / .xlsx / .json
```

## 当前已完成

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
   - `stress` 脚本可以执行：`./cpu_mem_stress_report.sh 60`
   - 支持时/分/秒输入，后端换算 `duration_seconds`
   - `timeout_seconds = max(duration_seconds + 300, 300)`
   - 实时日志通过 HTTP 轮询，不使用 WebSocket

5. 资源快照
   - 支持 CPU/内存
   - 支持磁盘 IO
   - 支持 GPU
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
   - 远端结果文件回收到：`backend/data/artifacts/{task_id}/`
   - 支持回收：`.log`、`.txt`、`.csv`、`.xlsx`、`.json`
   - 不回收：`.sh`、`.py`、`.sif`、隐藏文件、目录、软链接
   - 前端可以下载结果文件

8. Apptainer 分发
   - 知识库目录：`backend/apptainer/`
   - 远端目录：`$HOME/hpcdeploy/apptainer/`
   - 当前只做：
     - SSH 连接
     - 创建远端目录
     - 上传 `.sif`
   - 不 `chmod`
   - 不执行 `apptainer run / exec`
   - 日志应包含：`apptainer distribution completed, file was uploaded but not executed`

9. 同服务器防重复提交
   - 同一 `server_id` 同时只允许一个未完成任务
   - 未完成状态：
     - `PENDING`
     - `CONNECTING`
     - `PREPARING`
     - `UPLOADING`
     - `RUNNING`
   - 已完成状态：
     - `SUCCESS`
     - `FAILED`
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

## 下一步建议

下一阶段：阶段 10B，mpi / 编译环境脚本轻量执行验证。

注意：只允许执行 `backend/scripts/mpi/mpi_env_test.sh`，不要执行真实安装脚本。
