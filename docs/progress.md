# HPCDeploy 项目进度记录

## 当前阶段

MVP 已全部完成，进入收尾维护阶段。

当前主线：

```text
脚本知识库 → 选择服务器 → 选择脚本 → SSH 上传 → 远程执行 → 实时日志
→ 资源快照 → 任务历史 → 结果文件回收下载 → 任务取消 → 任务删除
```

当前下一步：

```text
阶段 13：部署与安全增强（Docker / Nginx）
```

## 最新状态补充

### 阶段 12A：任务历史删除功能已完成
- `DELETE /api/tasks/{task_id}` — 删除任务记录、任务日志、本地结果文件、远端工作目录
- `POST /api/tasks/{task_id}/cleanup` — 仅删除本地结果文件和远端工作目录，保留任务记录和日志
- 删除按钮仅对终态任务显示（SUCCESS / FAILED / CANCELED）
- 确认弹窗采用结构化排版，明确列出"将删除/不会删除"内容
- 安全模型：远端工作目录路径格式校验（禁止 `/root`、`/home`、`/tmp` 等顶层目录）
- SSH 失败或安全校验失败时返回错误，不删除数据库记录
- 不删除：服务器配置、脚本知识库文件、已安装到 `/opt`/`/usr` 的软件、Apptainer 容器仓库
- 新增前端工具函数：`frontend/src/utils/confirm.ts` — `buildConfirmContent()` 统一构造确认弹窗 VNode

### 阶段 12B：任务历史筛选/搜索/分页优化已完成
- `GET /api/tasks` 新增查询参数：status、task_type、server_id、keyword、limit、offset、order
- 返回分页结构：`{items, total, limit, offset}`
- 参数白名单校验：非法 status/task_type/order 返回 400，不返回 500
- keyword 使用 ILIKE 参数化查询搜索 task_id、file_path、remote_work_dir、error_message
- limit 默认 50，最大 100；offset 默认 0
- 前端新增筛选区：状态下拉、类型下拉、关键词搜索、重置按钮
- 前端新增分页：Element Plus Pagination 组件，可切换 20/50/100 条每页
- 搜索按钮动态样式：有筛选条件时变蓝 primary
- 后端兼容 Dashboard 页面，适配新的分页响应结构

### 任务取消（Phase 11B-11E）已完成
- PID 文件（`.hpcdeploy.pid`）→ PGID → 进程组 SIGTERM/SIGKILL
- 远端工作目录 `~/hpcdeploy/tasks/{type}/{task_id}/` 被清理
- 临时目录白名单清理：`/tmp/oneapi_install_2022`、`/tmp/openmpi_aocc_aocl_install`
- 任务状态变为 CANCELED，exit_code 为 -15
- 取消失败不改变 CANCELED 状态
- 不删除任务记录和日志，不回滚已安装软件

### MPI 脚本执行已开放
- 白名单：`mpi_env_test.sh`、`install_oneapi_2022.sh`、`install_openmpi_4.1.6_aocc_aocl.sh`
- 执行方式 `bash ./script.sh`
- 支持取消

### 其他已完成
- 日志下载功能（`GET /api/tasks/{id}/logs/download`）
- 时间本地化显示（UTC→浏览器本地时间）
- 前后端 systemd 服务化，修复 nvm PATH 问题
- 前端取消弹窗文案精简

### 已知未修复
- 旧 PENDING 任务会阻塞同服务器新任务提交，需 SQLite 手动清理
- `clipboard.writeText` 在非 HTTPS 下降级
- 回收失败只写 ERROR 日志，不更新 `error_message`

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
→ 任务删除
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

### 阶段 8D：stress 压测脚本短时间执行
- stress 类型执行 ./脚本名 duration_seconds
- duration_seconds 限制 1–3600 秒
- timeout = max(duration_seconds + 300, 300)
- 实时日志 + 资源快照监控（CPU/内存/磁盘/GPU）

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

### 阶段 10A：HTTP 轮询实时日志
- 放弃 WebSocket 方案
- 前端 1s HTTP 轮询 `GET /api/tasks/{id}/logs`
- 实现更简单，避免了 WebSocket 重连/鉴权/心跳等复杂度

### 阶段 10B：MPI 脚本轻量执行验证
- 开放 mpi 目录白名单：`mpi_env_test.sh`、`install_oneapi_2022.sh`、`install_openmpi_4.1.6_aocc_aocl.sh`
- 执行方式：`bash ./script.sh`
- 严格文件名白名单校验，非白名单文件拒绝执行

### 阶段 10C：任务执行页重构三模式
- config（新建任务）、summary（执行摘要）、config-readonly（只读配置快照）模式切换
- URL query 恢复任务状态
- 新建任务清空状态

### 阶段 10D：部署强化
- 后端 systemd 服务化：`hpcdeploy-backend.service`
- 前端 systemd 服务化：`hpcdeploy-frontend.service`
- 修复 systemd 下 nvm PATH 找不到 node 的问题

### 阶段 11A：同服务器防重复提交
- 同一 `server_id` 同时只允许一个未完成任务
- 未完成状态：PENDING / CONNECTING / PREPARING / UPLOADING / RUNNING / CANCELING
- 已完成状态：SUCCESS / FAILED / CANCELED

### 阶段 11B-11E：任务取消完整链路
- `setsid --wait bash -lc 'printf "%s" $$ > .hpcdeploy.pid; exec <command>'` — session 隔离
- PID → PGID 定位进程组 → SIGTERM → 等待 → SIGKILL
- 远端工作目录清理 `~/hpcdeploy/tasks/{type}/{task_id}/`
- 临时目录白名单清理（`/tmp/oneapi_install_2022`、`/tmp/openmpi_aocc_aocl_install`）
- SCRIPT_TEMP_DIR_MAP 代码级硬编码白名单
- 前端取消弹窗文案简化
- 时间本地化显示（`formatDateTime`）
- 日志下载功能

### 阶段 12A：任务历史删除功能
- `DELETE /api/tasks/{task_id}` — 删除任务记录、任务日志、本地结果文件、远端工作目录
- `POST /api/tasks/{task_id}/cleanup` — 仅删除本地文件和远端目录，保留任务记录和日志
- 删除按钮仅对终态任务显示（SUCCESS / FAILED / CANCELED）
- 安全模型：远端路径格式校验（禁止 `/root`、`/home`、`/tmp` 等顶层目录），SSH/安全失败不删除数据库记录
- 新增 `TaskDeleteResponse` / `TaskCleanupResponse` schema
- 前端确认弹窗结构化为"将删除/不会删除"排版（`frontend/src/utils/confirm.ts`）
- 不删除：服务器配置、脚本知识库文件、已安装到 `/opt`/`/usr` 的软件、Apptainer 容器仓库

### 阶段 12B：任务历史筛选/搜索/分页优化
- `GET /api/tasks` 支持 7 个查询参数：status、task_type、server_id、keyword、limit、offset、order
- 返回分页结构 `{items, total, limit, offset}`，不再直接返回数组
- 参数白名单校验 + 400 响应（非法参数不返回 500）
- keyword ILIKE 搜索 task_id、file_path、remote_work_dir、error_message
- 前端新增状态下拉、类型下拉、关键词搜索、重置按钮
- 前端 Element Plus 分页组件，支持 20/50/100 条每页
- 搜索按钮有筛选条件时显示蓝色 primary
- Dashboard 同步适配新的分页返回结构

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
  ├─ mpi: bash ./脚本名（白名单3个脚本）
  └─ apptainer: 上传 .sif 到 $HOME/hpcdeploy/apptainer/
  ↓
实时日志轮询（1s interval） + 资源快照（手动刷新）
  ↓
任务历史 + 日志下载
  ├─ SUCCESS / FAILED / TIMEOUT / CANCELED
  ├─ RUNNING 支持继续查看、取消
  └─ 日志下载
  ↓
结果文件回收（仅 stress）
  └─ SFTP 下载到 backend/data/artifacts/{task_id}/
      └─ .log / .txt / .csv / .xlsx / .json
  ↓
任务删除（仅终态 SUCCESS / FAILED / CANCELED）
  ├─ DELETE /api/tasks/{task_id} → 删除记录 + 日志 + 本地文件 + 远端目录
  └─ POST /api/tasks/{task_id}/cleanup → 仅删文件，保留记录
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
   - 未完成状态：PENDING / CONNECTING / PREPARING / UPLOADING / RUNNING / CANCELING
   - 已完成状态：SUCCESS / FAILED / CANCELED
   - 如果有旧 `PENDING` 卡住，可用 SQLite 清理。

10. mpi 脚本执行
    - 白名单三个脚本：`mpi_env_test.sh`、`install_oneapi_2022.sh`、`install_openmpi_4.1.6_aocc_aocl.sh`
    - 执行 `bash ./script.sh`
    - 支持取消（PID→PGID→kill）

11. 任务取消
    - `setsid --wait` session 隔离，PID 写入 `.hpcdeploy.pid`
    - PID → PGID → SIGTERM → 等待 → SIGKILL
    - 清理远端工作目录
    - 清理临时目录白名单
    - 状态变为 CANCELED，exit_code 为 -15
    - 不删除记录和日志，不回滚已安装软件

12. 日志下载
    - `GET /api/tasks/{id}/logs/download` → text/plain
    - 前端每张任务卡片都有"下载日志"按钮

13. 时间本地化显示
    - 后端 UTC 存储，前端 `formatDateTime()` 转换本地时间
    - 格式：`YYYY/MM/DD HH:mm:ss`

14. 任务删除
    - `DELETE /api/tasks/{task_id}` — 删除任务记录、日志、本地文件、远端目录
    - `POST /api/tasks/{task_id}/cleanup` — 仅删文件，保留记录和日志
    - 仅终态任务显示删除按钮（SUCCESS / FAILED / CANCELED）
    - 安全校验：远端路径格式限制，失败不删除数据库记录
    - 不删除：服务器配置、脚本库、已安装软件、Apptainer 仓库

15. 任务历史筛选与分页
    - GET /api/tasks 支持 7 个查询参数：status、task_type、server_id、keyword、limit、offset、order
    - 返回分页结构：{items, total, limit, offset}
    - 参数白名单校验，非法值返回 400
    - keyword 搜索 task_id、file_path、remote_work_dir、error_message
    - 前端筛选区：状态下拉、类型下拉、关键词搜索、重置按钮
    - 前端 Element Plus 分页，20/50/100 条每页
    - 搜索按钮动态蓝色 primary 样式

## 当前仍不做

- WebSocket（用 HTTP 轮询替代）
- 复杂 Server Lock（用简单防重复提交替代）
- apptainer run / exec（当前只做上传分发）
- AI 助手
- 多用户权限
- 复杂 params_schema
- 前端传 command / remote_path / timeout

## 关键文件清单

### 后端
- `backend/app/api/tasks.py` — 任务 API（含 artifacts、cancel、log download 端点）
- `backend/app/core/task_runner.py` — 执行编排（test/stress/mpi/apptainer）
- `backend/app/core/artifact_collector.py` — 结果文件回收
- `backend/app/core/ssh_executor.py` — SSH/SFTP 执行器
- `backend/app/core/script_library.py` — 脚本库管理
- `backend/app/schemas/task.py` — Pydantic 模型
- `backend/app/db/database.py` — 数据库引擎 + 迁移

### 前端
- `frontend/src/views/TaskRunner.vue` — 任务执行页
- `frontend/src/views/TaskHistory.vue` — 任务历史 + 结果文件弹窗
- `frontend/src/components/TaskCard.vue` — 任务卡片组件
- `frontend/src/components/LogViewer.vue` — 日志展示组件
- `frontend/src/api/task.ts` — 任务 API 调用（含日志下载）
- `frontend/src/utils/time.ts` — 时间格式化工具
- `frontend/src/utils/confirm.ts` — 确认弹窗结构化排版工具函数

## 下一步建议

下一阶段：阶段 13，部署与安全增强。
- Docker Compose 容器化部署
- Nginx 反代配置（前端静态 + API）
- SSH key 权限自动检查
- 日志保留策略
