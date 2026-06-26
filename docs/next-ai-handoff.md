# HPCDeploy AI Handoff

> **下一个 AI 进入项目后，优先读本文件，再看 `docs/progress.md` 和 `docs/architecture.md`。**

---

## 1. 项目路径

```
~/projects/hpc-deploy
```

本项目由 `Claude Code` 管理，不依赖其他 IDE。

---

## 2. 当前状态摘要

项目已完成到 **阶段 25B（审计日志完善 + 批次视图展开稳定性）**，当前稳定状态：

- **只保留服务器标签，不做分组** — `group_name` 列仍在数据库但不再使用
- **标签保存/展示已修复** — 后端 model_validator 显式解析 `tags_json`，前端 `row.tags` 展示，保存后 `loadTags()` 刷新
- **系统设置只保留 SSH 默认密钥**，远端目录为只读说明
- **任务执行页已优化** — 进度信息从左侧移到右侧实时面板顶部，移除右侧旧 meta 栏
- **实时监控已完成** — CPU/内存/磁盘/GPU 结构化卡片展示，5s 轮询
- **WebSocket 已接入** — 双通道日志推送（WS 主 + HTTP 轮询备），心跳 30s，断线自动切换
- **清理中心已重排** — 远端优先、本地次之
- **Apptainer 只读查看和批量分发已完成**
- **审计日志已完善** — 统一英文 action 命名、中文标签、所有调用点补全 `detail_json` 上下文、过滤密钥/token/命令敏感字段、日志加 `server_id` 和 `target_name`
- **失败诊断已完成**
- **仪表盘已完成**
- **批次视图展开状态已稳定** — 自动刷新不再折叠已展开行，通过 `:expand-row-keys` + `toggleRowExpansion` 保证

---

## 3. 启动命令

```bash
# 后端
cd ~/projects/hpc-deploy/backend
PYTHONPATH=.deps:. .deps/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd ~/projects/hpc-deploy/frontend
npm run dev
```

---

## 4. 构建命令

```bash
# 后端编译检查
cd ~/projects/hpc-deploy
python3 -m compileall backend/app backend/main.py

# 前端 TypeScript + 构建
cd frontend && npm run build
```

---

## 5. 当前重要安全边界

> 以下安全边界是**代码级强制**的，不是仅靠约定。

1. **不允许 raw command** — 所有命令由后端按任务类型固定生成，前端不传 `command` / `remote_path`
2. **不允许任意 shell 执行** — 只执行白名单脚本（文件名白名单 + 目录校验）
3. **不允许 Apptainer run/exec** — 只上传/分发 `.sif`
4. **不清理 $HOME/hpcdeploy/apptainer** — 清理 target 代码级硬编码为 `tasks` / `downloads` / `tmp`
5. **不提交 keys/db/artifacts** — `.gitignore` 已配置，`backend/keys/*`、`*.db`、`backend/data/artifacts/` 被忽略
6. **不 git add .** — 手动指定要添加的文件

---

## 6. 当前关键目录

```
backend/scripts/test/          # 测试脚本
backend/scripts/stress/        # 压测脚本
backend/scripts/mpi/           # MPI / 编译环境脚本
backend/apptainer/             # .sif 容器文件
backend/keys/                  # SSH 私钥和 .pub 公钥（不提交）
backend/data/artifacts/        # 结果文件回收目录（不提交）
backend/data/                   # SQLite 数据库文件（不提交）
```

---

## 7. 当前关键接口

| 端点 | 说明 |
|------|------|
| `GET /api/servers` | 服务器列表（支持 `tag` / `keyword` / `status` 筛选） |
| `GET /api/servers/tags` | 标签统计（含 `online_count` / `offline_count`） |
| `POST /api/servers` | 新增服务器 |
| `PUT /api/servers/{id}` | 编辑服务器 |
| `DELETE /api/servers/{id}` | 删除服务器 |
| `POST /api/servers/probe-all` | 探测全部 |
| `POST /api/servers/{id}/test` | SSH 测试 |
| `POST /api/servers/{id}/probe` | 单台探测 |
| `POST /api/servers/{id}/deploy-public-key` | 部署公钥 |
| `POST /api/tasks` | 创建任务 |
| `POST /api/tasks/batch` | 批量创建任务 |
| `POST /api/tasks/{id}/cancel` | 取消任务 |
| `DELETE /api/tasks/{id}` | 删除任务 |
| `GET /api/tasks/{id}/logs` | 任务日志（支持 `offset` / `limit`） |
| `GET /api/tasks/{id}/logs/download` | 下载日志 |
| `WS /api/tasks/{id}/logs/ws` | WebSocket 实时日志 |
| `GET /api/tasks/{id}/monitor` | CPU/内存/磁盘/GPU 结构化监控 |
| `POST /api/tasks/{id}/diagnosis` | 失败诊断 |
| `GET /api/tasks` | 任务历史（支持 `status` / `task_type` / `keyword` / `server_id` / `limit` / `offset` / `order`） |
| `GET /api/scripts` | 脚本知识库列表 |
| `POST /api/scripts/upload` | 上传脚本 |
| `GET /api/cleanup/local-artifacts/scan` | 本地结果文件目录扫描 |
| `POST /api/cleanup/local-artifacts/delete` | 本地结果文件批量删除 |
| `POST /api/cleanup/remote/scan` | 远端单台扫描 |
| `POST /api/cleanup/remote/delete` | 远端单台清理 |
| `POST /api/cleanup/remote/scan-all` | 全部在线服务器远端扫描 |
| `GET /api/settings` | 系统设置读取 |
| `PUT /api/settings` | 系统设置保存 |
| `GET /api/audit-logs` | 审计日志查询（支持分页/筛选） |

---

## 8. 最近刚修复的问题

### 8.1 服务器标签列显示为 `-` 的问题已修复

**根因**：Pydantic 2.10.4 的 `from_attributes=True` 不读取 `@hybrid_property` 定义的 `tags` 字段，导致 API 返回的 `ServerRead` 中 `tags` 始终为默认值 `[]`，前端 `row.tags` 收到空数组 → 显示 `-`。

**修复方案**（`backend/app/schemas/server.py`）：
- 在 `ServerRead` 上增加 `@model_validator(mode="before")`
- 当输入为 SQLAlchemy ORM 实例时，显式将所有列值转为 dict，并从 `tags_json` 解析出 `tags`
- 不再依赖 hybrid_property 做 Pydantic 序列化

**前端同步修复**（`frontend/src/views/Servers.vue`）：
- `saveServer()` 中 `tags` 从条件发送改为始终发送：`tags: form.tags || []`
- 保存后增加 `await loadTags()` 刷新标签下拉列表
- 编辑时回填 `tags: server.tags ?? []`
- 避免用户清空标签时 `tags` 字段被 Axios 忽略（因 `undefined` 被跳过）

### 8.2 分组功能已取消

- 原来同时做了 `group_name` 和 `tags`，用户取消分组只保留标签
- `group_name` 列仍在数据库（ALTER TABLE 已执行），但不再返回和展示
- 前端所有 `listGroups()`、`GroupSummary`、`filterGroup` 已移除

### 8.3 JSON 编码已修复

- `json.dumps(tags_list)` → `json.dumps(tags_list, ensure_ascii=False)` 确保中文标签不转义

### 8.4 标签统计已增强

- `GET /api/servers/tags` 返回含 `online_count` 和 `offline_count`
- 前端 `TagSummary` 接口已更新

### 8.5 批次视图自动刷新展开状态折叠已修复

**根因**：Element Plus el-table 在替换整个 `:data` 数组引用时，内部展开状态丢失。即使 `v-model:expand-row-keys` 正确绑定，组件也不会根据 keys 恢复展开行。

**修复方案**（`frontend/src/views/TaskHistory.vue`）：
- 改为 `:expand-row-keys`（单向绑定），Element Plus 不再写回我们的 ref
- `@expand-change` 中显式更新 `expandedBatchKeys`
- 新增 `batchTableRef` + `restoreExpandedRows()`，数据刷新后通过 `nextTick` + `toggleRowExpansion` 强制恢复
- 仅在 `resetBatchFilters()` 中清空 `expandedBatchKeys`，自动刷新/手动刷新不清理

### 8.6 审计日志已完善

**改动范围**：后端所有审计调用点（tasks.py、servers.py、scripts.py、cleanup.py、settings.py）+ 前端 AuditLog.vue。

**后端改动**：
- 统一英文 action 命名（`server.create`、`task.cancel` 等），中文标签映射在前端
- 所有调用点补全 `detail_json` 上下文（含参数、结果、错误信息等）
- 新增 `server_id` 字段
- SENSITIVE_FIELDS 过滤：`password`、`private_key`、`secret`、`token`、`command`、`raw_shell`、`raw_args`、`env`

**前端改动**：
- AuditLog.vue 新增 `task.stress_suite_create`、`task.diagnose` 标签
- 详情弹窗支持结构化 key-value 表格展示

---

## 9. 下一步建议

**推荐优先做：压测脚本串行批次任务（阶段 26A）**

理由：当前压测脚本一次只能选一个执行一个。需要支持一次选择 GPU、CPU/内存、磁盘三个压测脚本，按 GPU → CPU/内存 → 磁盘顺序自动串行执行，每台服务器独立线程，每个脚本生成独立日志和报告，归入同一个 batch。

**已在 `docs/development-stages.md` 中规划**，需完成：
- 后端：`POST /api/tasks/stress-suite` 端点 + 顺序执行 Worker
- 前端：TaskRunner.vue 多选 stress 卡片 + stress suite 创建流程

**备选方向**：
- **批量任务结果汇总** — 当前批量视图已有展开查看子任务，可考虑独立汇总页面
- **任务模板管理 UI** — 当前 9 个模板在代码中硬编码，未提供管理界面
- **远端空间清理策略** — 任务执行前检查远端磁盘空间，按策略自动清理
- **服务器详情页优化** — 当前详情为 el-drawer 弹窗，可扩展为独立页面

---

## 10. 给下一个 AI 的工作规则

1. **修改前先读 README 和 next-ai-handoff** — 了解当前状态和安全边界
2. **不要重构** — 只做当前阶段明确需要的事
3. **不要删功能** — 原有功能保持不动
4. **每次只做一个阶段** — 不做跨阶段的大改动
5. **高风险操作必须确认** — 涉及 rm/restart/chmod/chown 等需用户确认
6. **修改后必须验证** — 跑 `compileall` 和 `npm run build`
7. **输出建议 git add 文件列表** — 不要直接 `git add .`
8. **先计划后执行** — 给出计划等待用户批准后再动手

---

## 11. 不要提交的文件

`.gitignore` 已配置忽略以下内容，但操作时仍需注意不要手动添加：

- `backend/data/*.db`
- `backend/data/artifacts/`
- `backend/apptainer/*.sif`
- `backend/keys/*`
- `.env`
- `node_modules/`
- `.venv/`
- `.deps/`
- `*.log`
- `dist/`
- `frontend/tsconfig.tsbuildinfo`
