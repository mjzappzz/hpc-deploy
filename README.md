# HPCDeploy

HPCDeploy 是一个面向 HPC 运维的轻量级脚本执行控制台。

当前核心链路：

```text
服务器管理
→ 脚本知识库
→ 选择服务器
→ 选择脚本
→ SSH 上传
→ 远程执行 / 分发
→ 实时日志
→ 资源快照
→ 任务历史
→ 日志下载
→ 结果文件回收
→ 取消任务
→ 删除任务
→ 仪表盘总览
→ 结果文件归档目录查看
```

## 1. 项目简介

HPCDeploy 用于把常见 HPC 运维脚本纳入统一控制面，围绕服务器管理、脚本知识库、SSH 执行、日志查看、资源快照、任务管理、结果回收提供完整可用闭环。

## 2. 当前已实现功能

- 服务器管理（CRUD + SSH 测试 + 信息探测）
- 服务器支持 SSH Key / Password 两种登录方式
- 支持通过密码登录后一键部署公钥，再切换为 SSH Key 登录
- 脚本知识库（四类分类目录，上传/下载/预览/删除）
- test 脚本执行（bash ./script.sh）
- stress 压测执行（带时长参数 + 资源快照）
- mpi 白名单脚本执行（mpi_env_test.sh / OneAPI / OpenMPI）
- Apptainer 容器分发（sif 文件上传，不做 run/exec）
- 实时日志（WebSocket + HTTP 轮询双通道）
- CPU/内存、磁盘、GPU 资源快照（结构化卡片展示）
- WebSocket 实时日志推进（心跳 30s，断线自动切换 HTTP 备用）
- AI 任务失败日志诊断（匹配失败模式，给出原因与建议）
- 任务执行体验优化（中文状态标签、运行耗时、进度条、预计剩余）
- 任务取消（PID → PGID → SIGTERM/SIGKILL + 远端目录清理）
- 任务删除（清理 artifacts / 远端目录 / 日志 / 记录）
- 任务历史筛选、搜索、分页
- 日志下载
- 结果文件回收和下载（.log/.txt/.csv/.xlsx/.json）
- 仪表盘数据化总览（服务器 / 任务 / 归档统计）
- 仪表盘快捷操作（8 个导航按钮）
- 仪表盘结果文件归档目录树查看
- 仪表盘最近任务整行点击跳转任务历史
- 任务显示名格式：客户名 · 模块 · 脚本名 · 日期
- 同服务器防重复提交
- 全局布局与导航视觉优化
- 服务器健康状态增强（阶段 14A，正在收口）
- 批量任务执行（多选服务器，部分成功，离线跳过）
- 任务模板/执行预设（9 个模板一键填充）
- 批量 Apptainer 容器分发

## 3. 当前暂不做

- WebSocket（用 HTTP 轮询替代）
- 多用户权限
- AI 助手
- apptainer run / exec
- 批量执行
- 复杂编排

## 4. 技术栈

| 模块 | 技术 |
|------|------|
| 前端框架 | Vue 3 + Vite |
| 前端 UI | Element Plus |
| 后端框架 | FastAPI |
| ORM | SQLAlchemy |
| 数据库 | SQLite |
| SSH 执行 | Paramiko |
| 部署 | systemd 服务 |

## 5. 目录结构

```
HPCDeploy/
├── backend/
│   ├── app/
│   │   ├── api/         # REST 路由
│   │   ├── core/        # 执行器、回收器
│   │   ├── db/          # 数据库
│   │   ├── models/      # ORM 模型
│   │   └── schemas/     # Pydantic 模型
│   ├── apptainer/       # .sif 文件
│   ├── data/            # SQLite + artifacts
│   ├── keys/            # SSH 私钥和同名 .pub 公钥（不要提交真实密钥）
│   ├── scripts/
│   │   ├── mpi/         # 编译环境
│   │   ├── stress/      # 压测脚本
│   │   └── test/        # 测试脚本
│   ├── main.py
│   └── requirements.txt
├── docs/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── router/
│   │   ├── styles/
│   │   ├── utils/
│   │   └── views/
│   ├── package.json
│   └── vite.config.ts
└── .gitignore
```

## 6. 启动命令

```bash
# 后端
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend && npm install && npm run dev -- --host 0.0.0.0 --port 5173
```

## 7. 构建检查命令

```bash
# 后端编译检查
python3 -m compileall backend/app backend/main.py

# 前端 TypeScript + 构建
cd frontend && npm run build
```

## 8. 安全边界

- 前端不传 command / remote_path / local_path / timeout / PID / kill command
- 后端只执行白名单脚本（文件名白名单 + 目录校验）
- 服务器探测只执行固定安全命令
- 脚本路径必须命中知识库目录，resolve() + startswith() 防逃逸
- artifact 下载防路径逃逸（basename + resolve + startswith）
- 取消任务基于 PID 文件 + PGID 进程组终止，不依赖前端输入
- 删除任务对远端路径做安全格式校验，失败不删数据库
- 同服务器只允许一个未完成任务
- `/api/ssh-keys` 只返回密钥元信息，不返回私钥/公钥内容
- 部署公钥只写远端 `~/.ssh/authorized_keys`
- 不覆盖 `authorized_keys`
- 不修改 `sshd_config`
- 不重启 `sshd`

## 9. 文档索引

- [docs/architecture.md](docs/architecture.md) — 系统架构
- [docs/development-stages.md](docs/development-stages.md) — 阶段开发计划
- [docs/progress.md](docs/progress.md) — 项目进度
- [docs/next-ai-handoff.md](docs/next-ai-handoff.md) — AI 交接文档
- [docs/mvp-acceptance.md](docs/mvp-acceptance.md) — MVP 验收清单
