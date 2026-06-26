# HPCDeploy

HPCDeploy 是一个面向 HPC 运维场景的轻量级自动化控制台，用于管理服务器、执行白名单脚本、分发 Apptainer 镜像、查看任务日志、回收结果文件、清理任务产物和审计操作。

## 技术栈

| 模块 | 技术 |
|------|------|
| 前端框架 | Vue 3 + Vite |
| 前端 UI | Element Plus |
| 前端路由 | Vue Router |
| 后端框架 | FastAPI |
| ORM | SQLAlchemy |
| 数据库 | SQLite |
| SSH 执行 | Paramiko |
| 实时日志 | WebSocket + HTTP 双通道 |

## 核心功能

- **服务器管理** — SSH 测试、SSH Key / Password 登录、一键部署公钥、默认 SSH 私钥设置、健康探测、探测全部（默认跳过离线）、标签管理
- **脚本知识库** — test / stress / mpi / install 白名单脚本，上传/下载/预览/删除
- **任务执行** — 单台/批量执行、stress 参数化、MPI 白名单脚本、Apptainer .sif 只上传不分发执行
- **实时日志** — WebSocket 主通道 + HTTP 轮询备用，心跳 30s，断线自动切换
- **实时监控** — CPU/内存、磁盘、GPU 结构化卡片展示，5s 轮询
- **任务管理** — 取消（PID→PGID 进程组终止）、删除（清理 artifacts/远端目录/日志）、失败诊断、筛选/搜索/分页
- **结果文件** — 回收与下载（.log/.txt/.csv/.xlsx/.json）
- **清理中心** — 本地结果文件按 task 目录聚合、远端临时目录扫描与清理、Apptainer 镜像目录只读查看
- **Apptainer 分发** — .sif 文件上传、单台/批量分发、不执行 run/exec
- **审计日志** — 关键操作记录可追溯
- **系统设置** — SSH 默认私钥设置、远端目录只读说明
- **仪表盘** — 服务器/任务/归档统计、快捷操作、最近任务跳转、结果文件目录树

## 启动命令

### 开发模式（热重载）

```bash
# 后端
cd ~/projects/hpc-deploy/backend
PYTHONPATH=.deps:. .deps/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd ~/projects/hpc-deploy/frontend
npm run dev
```

### 生产模式（systemd 服务）

```bash
# 重启后端（修改 Python 代码后必须重启）
sudo systemctl restart hpcdeploy-backend

# 重启前端（修改 Vue/前端代码后必须重启）
sudo systemctl restart hpcdeploy-frontend

# 查看状态
sudo systemctl status hpcdeploy-backend --no-pager -l
sudo systemctl status hpcdeploy-frontend --no-pager -l
```

> 修改代码后，必须通过 `systemctl restart` 重启对应服务才能生效。开发模式下可用 `--reload` 热重载避免手动重启。

## 构建验证

```bash
# 后端编译检查
python3 -m compileall backend/app backend/main.py

# 前端 TypeScript + 构建
cd frontend && npm run build
```

## 安全边界

- 前端不传 `command` / `raw shell` / `remote_path`
- 后端只执行白名单脚本（文件名白名单 + 目录校验）
- Apptainer 只上传/分发 `.sif`，不执行 `run` / `exec`
- SSH 私钥只保存文件名，不保存内容；API 不返回私钥/公钥内容
- 远端清理只允许 `tasks` / `downloads` / `tmp`，不清理 `$HOME/hpcdeploy/apptainer`
- 路径防逃逸（`resolve()` + `startswith()`）
- 取消任务基于 PID 文件 + PGID 进程组终止，不依赖前端输入
- 部署公钥只写远端 `~/.ssh/authorized_keys`，不覆盖、不修改 `sshd_config`、不重启 `sshd`

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 系统架构与技术设计 |
| [docs/development-stages.md](docs/development-stages.md) | 阶段开发计划与完成记录 |
| [docs/progress.md](docs/progress.md) | 项目当前进度与完成度 |
| [docs/mvp-acceptance.md](docs/mvp-acceptance.md) | MVP 验收清单 |
| [docs/next-ai-handoff.md](docs/next-ai-handoff.md) | AI 交接文档（下一位 AI 先读） |
