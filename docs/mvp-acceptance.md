# HPCDeploy MVP 验收清单

> 本文档用于 HPCDeploy MVP 功能验收。核心主链路：脚本知识库 → 选择服务器 → 选择脚本 → SSH 上传 → 执行脚本 → 实时日志 → 资源快照 → 任务历史 → 结果文件回收下载。

---

## 1. 先决条件

- [ ] 后端可启动（`cd backend && python main.py`）
- [ ] 前端可启动（`cd frontend && npm run dev`）
- [ ] 数据库已初始化（`backend/data/hpc_control_panel.db` 存在）
- [ ] 测试脚本存在（`backend/scripts/test/hello.sh`）
- [ ] 压测脚本存在（`backend/scripts/stress/cpu_mem_stress_report.sh`）
- [ ] 远端服务器已添加本机 SSH 公钥

---

## 2. 服务器管理

- [ ] 新增服务器成功后出现在列表中，状态为 `unknown`
- [ ] SSH 测试成功后状态变为 `online`（失败后变为 `offline`）
- [ ] 探测信息能显示 OS/CPU/内存/GPU/磁盘/网络
- [ ] 编辑服务器后列表同步更新
- [ ] 删除服务器后列表消失

**验证命令：** `curl -s http://localhost:8000/api/servers | python3 -m json.tool`

---

## 3. 脚本知识库

- [ ] 5 个分类页签显示正确：全部 / 编译环境(mpi) / 压测脚本(stress) / Apptainer 容器(apptainer) / 测试脚本(test)
- [ ] 各分类页签能正确过滤文件
- [ ] 上传 `.sh` 文件到指定分类后文件出现在列表中
- [ ] 预览文本文件内容正常
- [ ] 下载脚本文件正常
- [ ] 删除脚本文件后列表更新
- [ ] `.sif` 文件只显示文件信息，不尝试预览内容
- [ ] 上传非 `.sh`/`.py`/`.sif` 文件被拒绝

**验证命令：** `curl -s http://localhost:8000/api/scripts/files | python3 -m json.tool`

---

## 4. test/hello.sh 执行

- [ ] 选择服务器后显示服务器名 + 主机名 + 状态标签
- [ ] 选择"测试脚本"类型后文件列表正确过滤
- [ ] 选择 hello.sh 后命令预览显示 `bash ./hello.sh`
- [ ] 校验参数通过后弹出"参数校验通过"
- [ ] 点击"开始执行"后切换到摘要模式，右侧日志开始滚动
- [ ] 等待 5-10 秒后状态变为 SUCCESS，退出码为 0
- [ ] 日志中包含 SYSTEM 级别的连接/上传/执行日志和 INFO 级别的 stdout

---

## 5. stress 60 秒执行

- [ ] 点击"新建任务"能清空状态回到 config 模式
- [ ] 选择"压测脚本"类型后文件列表正确过滤，参数区出现"压测时长"
- [ ] 设置 0 小时 / 1 分钟 / 0 秒，总秒数显示为 60
- [ ] 执行后切换到实时面板，日志持续滚动
- [ ] CPU/内存资源快照能刷新显示 top + free + ps 输出
- [ ] 磁盘 IO 资源快照能刷新显示 iostat + df 输出
- [ ] GPU 资源快照能刷新显示 nvidia-smi 输出（或无 GPU 提示）
- [ ] 等待 60 秒后状态变为 SUCCESS，退出码为 0
- [ ] RUNNING 状态下"开始执行"按钮灰色禁用（不允许重复提交）

---

## 6. mpi/apptainer 阶段边界

- [ ] mpi 脚本已开放执行，包括 `mpi_env_test.sh`、`install_oneapi_2022.sh`、`install_openmpi_4.1.6_aocc_aocl.sh`
- [ ] apptainer 任务选择 `.sif` 文件后上传到 `$HOME/hpcdeploy/apptainer/`
- [ ] apptainer 日志包含 `apptainer distribution completed, file was uploaded but not executed`
- [ ] apptainer 不做 run/exec，不上传 .sh/.py 文件

---

## 7. 任务历史

- [ ] 任务列表按创建时间降序排列
- [ ] 查看日志弹窗显示 TaskLog 列表（SYSTEM/INFO/ERROR）
- [ ] RUNNING 任务显示"继续查看"按钮，点击后跳转到 task-runner 并恢复轮询
- [ ] SUCCESS/FAILED 任务没有"继续查看"按钮
- [ ] stress 已完成任务显示"结果文件"按钮
- [ ] 结果文件弹窗显示文件列表 + 本地保存目录 + 下载按钮
- [ ] 下载文件正常
- [ ] 空结果文件时显示"暂无结果文件，可能脚本未生成报告或回收失败，请查看任务日志。"
- [ ] 完成任务日志中包含 SYSTEM 日志：`collecting artifacts from ...` → `artifact downloaded: ...` → `artifact collection completed`

**验证 API 命令：**

```bash
curl -s http://localhost:8000/api/tasks | python3 -m json.tool
curl -s http://localhost:8000/api/tasks/{task_id}/logs | python3 -m json.tool
curl -s http://localhost:8000/api/tasks/{task_id}/artifacts | python3 -m json.tool
```

---

## 8. 远程服务器验证

- [ ] 远端目录路径无 `/root/~/` 前缀（`_resolve_remote_work_dir` 使用 SSH 检测到的 `$HOME` 绝对路径）
- [ ] 文件上传位置正确，权限为 `-rwxr-xr-x`
- [ ] 远端结果文件存在（`.log` / `.csv` / `.txt` / `.xlsx`）
- [ ] 本地结果文件与远端文件一致

**验证命令：**

```bash
ssh root@<server> "ls -la ~/hpcdeploy/tasks/stress/$(ls -t ~/hpcdeploy/tasks/stress/ | head -1)/"
ls -la backend/data/artifacts/{task_id}/
```

---

## 9. 安全边界

- [ ] 前端 `createTask` payload 只有 `server_id`、`task_type`、`file_path`、`duration_seconds?`，没有 `command` / `remote_path` / `timeout`
- [ ] 知识库脚本路径无法逃逸到 `backend/scripts/` 或 `backend/apptainer/` 之外
- [ ] 结果文件下载通过 `basename` + `resolve()` + `startswith()` 三重检查，路径逃逸返回 400
- [ ] 远端文件名通过 `_safe_basename()` 校验，禁止 `..`、`/`、`.` 开头
- [ ] 回收失败只写 ERROR 日志，不覆盖 `status` / `exit_code` / `error_message`
- [ ] 只允许回收 `.log` / `.txt` / `.csv` / `.xlsx` / `.json` 后缀

**验证 API 命令：**

```bash
# 路径逃逸测试
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/tasks/{task_id}/artifacts/..%2F..%2Fetc%2Fpasswd/download"
# 预期：400

# 不存在文件
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/tasks/{task_id}/artifacts/nonexist.txt/download"
# 预期：404
```

---

## 10. API 接口

- [ ] `GET /api/health` 返回 `{"status":"ok","service":"hpcdeploy-backend"}`
- [ ] `GET /api/tasks` 返回 JSON 数组
- [ ] `GET /api/tasks/{id}/logs` 返回 TaskLog 数组，第一条 level="SYSTEM"
- [ ] `GET /api/tasks/{id}/artifacts` 返回 `{artifact_dir, files[]}`
- [ ] `GET /api/tasks/{id}/artifacts/{name}/download` 能正常下载文件
- [ ] 不存在的文件返回 404
- [ ] 路径逃逸尝试返回 400

---

## 11. 日志下载

- [ ] 任务历史页面每个任务都有"下载日志"按钮
- [ ] 下载文件名格式为 `{task_id}.log`
- [ ] 下载内容包含任务所有日志（SYSTEM/INFO/ERROR），格式 `[YYYY-MM-DD HH:mm:ss] [LEVEL] message`
- [ ] 下载不依赖任务状态（已结束、运行中的任务均可下载）

**验证命令：**

```bash
curl -s -o /tmp/test.log -w "%{http_code}" "http://localhost:8000/api/tasks/{task_id}/logs/download"
# 预期：200
head -5 /tmp/test.log
```

---

## 12. 任务取消

- [ ] RUNNING / PENDING / CONNECTING / PREPARING / UPLOADING 状态的任务显示"取消任务"按钮
- [ ] 取消弹窗提示清晰，确认后执行
- [ ] 取消后远端进程通过 `.hpcdeploy.pid` 定位 PGID 并终止
- [ ] 先 SIGTERM 等待，超时后 SIGKILL
- [ ] 远端工作目录 `~/hpcdeploy/tasks/{type}/{task_id}/` 被清理
- [ ] 脚本对应的临时下载目录（`/tmp/oneapi_install_2022`、`/tmp/openmpi_aocc_aocl_install`）被清理
- [ ] 任务状态变为 CANCELED，exit_code 为 -15
- [ ] 任务记录和日志不删除
- [ ] 已安装到 `/opt`、`/usr` 的软件不回滚
- [ ] CANCELING 状态下按钮灰色禁用

**验证 API 命令：**

```bash
curl -s -X POST "http://localhost:8000/api/tasks/{task_id}/cancel"
# 预期：{"status": "CANCELED", ...}
```

---

## 13. 时间显示

- [ ] 所有时间字段（创建时间、开始时间、结束时间）显示为浏览器本地时间
- [ ] 格式为 `YYYY/MM/DD HH:mm:ss`
- [ ] 后端存储为 UTC，前端自动转换

---

## 14. 服务部署

- [ ] 后端 systemd 服务已配置，`systemctl status hpcdeploy-backend` 为 active
- [ ] 前端 systemd 服务已配置，`systemctl status hpcdeploy-frontend` 为 active

---

## 15. 任务删除（Phase 12A）

- [ ] SUCCESS / FAILED / CANCELED 状态任务显示"删除任务"按钮
- [ ] PENDING / CONNECTING / PREPARING / UPLOADING / RUNNING / CANCELING 状态不显示删除按钮
- [ ] 未完成任务（RUNNING 等）显示"取消任务"而非"删除任务"
- [ ] 删除确认弹窗采用结构化排版：明确列出"将删除"和"不会删除"两组内容
- [ ] 点击确认后任务从历史列表中消失
- [ ] 删除后重新查询后端确认任务记录已被清除
- [ ] 远端工作目录 `~/hpcdeploy/tasks/{type}/{timestamp}/` 已被清理
- [ ] 本地 artifacts 目录 `backend/data/artifacts/{task_id}/` 已被清理
- [ ] 任务日志（task_logs 表）已被删除
- [ ] 服务器配置、脚本知识库文件、已安装到 `/opt`/`/usr` 的软件不受影响
- [ ] 其他任务记录不受影响

**验证 API 命令：**

```bash
# 删除任务
curl -s -X DELETE "http://localhost:8000/api/tasks/{task_id}"
# 预期：{"task_id": "...", "deleted": true, ...}

# 确认删除后查询不存在
curl -s "http://localhost:8000/api/tasks/{task_id}"
# 预期：404
```

---

## 16. 任务历史筛选/搜索/分页（Phase 12B）

- [ ] 进入任务历史页，默认显示最近 50 条任务
- [ ] 页面底部显示分页组件，显示总数和当前页码
- [ ] 状态筛选下拉：选择"成功"后只显示 SUCCESS 任务，选择"已取消"后只显示 CANCELED
- [ ] 类型筛选下拉：选择"压测脚本"后只显示 stress 任务，选择"编译环境"后只显示 mpi
- [ ] 输入关键词搜索，能匹配 task_id、文件路径、远端目录、错误信息
- [ ] 点击重置按钮后，筛选条件清空，恢复默认列表
- [ ] 分页切换正常，上一页/下一页/页码跳转均可用
- [ ] 每页条数切换（20/50/100）后重新加载
- [ ] 搜索按钮在无筛选条件时为普通按钮，有筛选条件时变蓝 primary
- [ ] 非法参数（无效状态/类型/排序）后端返回 400 不是 500
- [ ] 查看日志、下载日志、结果文件、删除任务、取消任务均不受影响

**验证 API 命令：**

```bash
# 默认分页
curl -s "http://localhost:8000/api/tasks?limit=2&offset=0"
# 预期：{"items":[...],"total":N,"limit":2,"offset":0}

# 状态筛选
curl -s "http://localhost:8000/api/tasks?status=SUCCESS&limit=5"
# 预期：只返回 SUCCESS 状态任务

# 关键词搜索
curl -s "http://localhost:8000/api/tasks?keyword=openmpi&limit=5"
# 预期：返回匹配 openmpi 的任务

# 非法参数返回 400
curl -s -w "%{http_code}" "http://localhost:8000/api/tasks?status=INVALID"
# 预期：400
```

---

## 17. 非阻塞问题记录

以下 3 个问题不影响 MVP 功能完整性，建议记录但不立即修复：

### 17.1 clipboard.writeText 在非 HTTPS 环境降级

`TaskHistory.vue` 中 `copyArtifactDir` 使用 `navigator.clipboard.writeText()`，该 API 需要安全上下文（HTTPS 或 localhost）。开发模式（localhost）下没问题，生产环境需要 HTTPS。影响极小——复制按钮只是便利功能，失败时用户可手动选中路径复制。

### 17.2 旧 PENDING 任务需要人工清理

后端已实现同服务器防重复提交。当前保留风险是历史遗留 `PENDING` 任务会被视为未完成任务，从而阻塞新提交。出现这种情况时，可通过 SQLite 手动将旧 `PENDING` 修正为 `FAILED`。

### 17.3 回收失败未更新 error_message

`artifact_collector.py` 中回收失败只写 ERROR 日志到 `task_logs`，没有更新 `task.error_message`。按需求描述"可以在任务上记录 artifact_error"，当前省略了，不影响核心验收（任务状态和退出码仍然正确）。

---

## 18. 当前 MVP 验收通过标准

- test/hello.sh 能执行成功
- stress 60 秒能执行成功
- mpi_env_test.sh 能执行成功
- 实时日志正常
- stress 结果文件能回收并下载
- RUNNING 任务能取消
- 知识库路径和 artifact 下载路径不能逃逸
- 日志下载功能正常
- 时间显示为本地时间
