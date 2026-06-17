# HPCDeploy 项目进度记录

## 当前阶段

当前进行到：阶段 9A：stress 结果文件回收（已完成）

当前主线：

```text
脚本知识库
↓
任务执行器
↓
SSH 上传
↓
stress / test 真实执行
↓
实时日志 + 资源快照
↓
任务历史
↓
结果文件回收下载
```

当前下一步：

```text
MVP 验收与稳定性修复
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

## 当前完整主链路

```text
脚本知识库
  ↓ 上传/管理脚本文件
任务执行准备（服务器 + 任务类型 + 知识库文件）
  ↓ POST /api/tasks/run
SSH 连接（CONNECTING → PREPARING → UPLOADING）
  ↓
脚本远程执行（RUNNING）
  ├─ test: bash ./脚本名
  └─ stress: ./脚本名 duration_seconds
  ↓
实时日志轮询（1s interval） + 资源快照（手动刷新）
  ↓
任务历史（SUCCESS / FAILED）
  ↓
结果文件回收（仅 stress）
  └─ SFTP 下载到 backend/data/artifacts/{task_id}/
      └─ .log / .txt / .csv / .xlsx / .json
```

## 严格禁止

禁止实现：
- WebSocket
- Server Lock
- 任务取消
- mpi / apptainer 真实执行
- 多用户权限
- AI 助手
- 复杂编排

## 当前保留内容

继续保留：
- 服务器管理
- SSH 测试
- 服务器探测
- 脚本知识库
- 任务执行
- 任务历史
- 结果文件回收

## 下一步建议

1. MVP 验收：确认 stress 60 秒任务从创建到回收完整通过
2. 稳定性修复：
   - 回收部分失败时 error_message 提示
   - 无结果文件时的前端提示完善
   - 资源快照监控超时处理
3. 文档补全：API 文档、架构图
4. 不急着加新功能，先跑通完整验收
