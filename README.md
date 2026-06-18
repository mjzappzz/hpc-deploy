# HPCDeploy

HPCDeploy 是一个面向 HPC 运维的轻量级脚本执行控制台。

当前主链路：

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

## 1. 项目简介

HPCDeploy 用于把常见 HPC 运维脚本纳入统一控制面，围绕服务器管理、脚本知识库、SSH 执行、日志查看、资源快照和结果文件回收提供最小可用闭环。

## 2. 当前已实现功能

- 服务器管理
- SSH 测试
- 服务器信息探测
- 脚本知识库
- test 脚本执行
- stress 压测执行
- mpi 脚本执行（mpi_env_test.sh / OneAPI / OpenMPI）
- 实时日志 HTTP 轮询
- CPU/内存、磁盘 IO、GPU 资源快照
- 任务取消（PID 文件 → PGID 进程组终止 + 远端目录清理）
- 任务历史
- stress 结果文件回收和下载
- 任务日志下载
- 日志时间本地化显示
- 任务删除（删除任务记录、日志、本地结果文件、远端工作目录）
- 任务历史筛选与分页（按状态/类型筛选、关键词搜索、分页加载）

## 3. 当前未实现 / 暂不做

- WebSocket
- Server Lock
- apptainer run/exec（当前只做上传分发）
- 多用户权限
- AI 助手

## 4. 技术栈

- 前端：Vue 3 + Vite + Element Plus
- 后端：FastAPI + SQLAlchemy + Paramiko
- 数据库：SQLite
- 实时日志：HTTP 轮询
- 远程执行：SSH / SFTP

## 5. 项目目录结构

```text
HPCDeploy/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   └── schemas/
│   ├── apptainer/
│   ├── data/
│   ├── keys/
│   ├── scripts/
│   │   ├── mpi/
│   │   ├── stress/
│   │   └── test/
│   ├── main.py
│   └── requirements.txt
├── docs/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── router/
│   │   ├── stores/
│   │   ├── styles/
│   │   ├── utils/
│   │   └── views/
│   ├── package.json
│   └── vite.config.ts
└── .gitignore
```

## 6. 后端启动方式

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

默认数据库配置在 `backend/.env`：

```env
APP_NAME=HPCDeploy
APP_ENV=development
DATABASE_URL=sqlite:///./data/hpc_control_panel.db
```

## 7. 前端启动方式

```bash
cd frontend
npm install
npm run dev
```

默认 Vite 监听 `0.0.0.0`。

## 8. 基础使用流程

1. 在服务器管理页面录入目标服务器信息和 SSH key 路径。
2. 执行 SSH 测试，确认在线状态。
3. 执行服务器探测，获取 OS / CPU / 内存 / 磁盘 / GPU 信息。
4. 在脚本知识库中维护脚本文件。
5. 在任务执行页选择服务器、任务类型（test / stress / mpi / apptainer）和知识库文件。
6. 发起执行，系统自动 SSH 连接、上传脚本、执行/分发。
7. 通过 HTTP 轮询查看实时日志，并按需获取资源快照。
8. RUNNING 任务可取消（终止远端进程 + 清理远端目录）。
9. 在任务历史查看状态、日志和 stress 回收结果。
10. 从 `artifacts` 下载回收文件，或下载任务日志。
11. 对已完成终态任务（SUCCESS / FAILED / CANCELED）可删除全部相关记录。

## 9. 脚本知识库目录说明

- `backend/scripts/mpi`
  用于存放编译环境、OneAPI、OpenMPI 等相关脚本。
- `backend/scripts/stress`
  用于存放 CPU / 内存 / 磁盘 / GPU 压测脚本。
- `backend/scripts/test`
  用于存放测试脚本，例如 `hello.sh`。
- `backend/apptainer`
  用于存放 Apptainer 容器文件（`.sif`），当前只做上传分发，不做 run/exec。

## 10. 结果文件保存目录

stress 任务回收结果默认保存到：

```text
backend/data/artifacts/{task_id}/
```

允许回收并下载的结果文件以平台白名单为准，当前任务历史页会展示本地保存目录和下载入口。

## 11. 安全边界

- 前端不能传 `command`
- 前端不能传 `remote_path`
- 前端不能传 `timeout`
- 只执行知识库文件
- artifact 下载防路径逃逸
- 取消任务基于 PID 文件 + PGID 进程组终止，不依赖前端提供的 PID/命令/路径

补充说明：

- 任务执行命令由后端按任务类型固定生成，不接受前端任意命令。
- 脚本路径必须命中知识库目录并通过路径校验。
- artifact 下载接口对文件名做 `basename` 校验，并限制在 `backend/data/artifacts/{task_id}/` 目录内解析。
- 取消通过 `setsid --wait` 写入的 `.hpcdeploy.pid` 文件定位进程组，先 SIGTERM 再 SIGKILL。
- 删除任务接口对远端工作目录做安全校验（路径格式限制 + 禁止系统顶层目录），校验失败返回 400 且不删除数据库记录。

## 12. 开发文档索引

- [docs/architecture.md](docs/architecture.md) — 系统架构说明
- [docs/development-stages.md](docs/development-stages.md) — 阶段开发计划
- [docs/progress.md](docs/progress.md) — 项目进度与接手说明
- [docs/mvp-acceptance.md](docs/mvp-acceptance.md) — MVP 验收清单
