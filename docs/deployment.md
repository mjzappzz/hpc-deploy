# HPCDeploy Deployment Notes

本文档用于**运行数据运维与部署演进决策**：SQLite 适用边界、备份恢复、Docker / MySQL 路线。首次安装、日常更新和 systemd 排障请阅读 [../deploy/README.md](../deploy/README.md)。

## 当前模式：Nginx + systemd

本节只说明当前形态及其适用范围；安装命令以 [部署与运维手册](../deploy/README.md) 为准。

当前默认部署结构：

```text
hpcdeploy-backend.service
  -> uvicorn
  -> 127.0.0.1:8000

nginx.service
  -> /var/www/hpcdeploy
  -> /api/ 代理到 127.0.0.1:8000
  -> 0.0.0.0:10086
```

首次部署：

```bash
git clone <repo-url> hpc-deploy
cd hpc-deploy
sudo deploy/scripts/install_hpcdeploy_service.sh
```

日常更新：

```bash
sudo deploy/scripts/redeploy_hpcdeploy.sh
```

访问地址：

```text
http://<server-ip>:10086/
```

WSL NAT 部署需要由 Windows 宿主机将 `0.0.0.0:10086` 转发到当前 WSL IP 的 `10086/tcp`，并放行 Windows 入站防火墙；具体命令见 [部署与运维手册](../deploy/README.md#wsl-部署的-windows-网络入口)。WSL IP变化后需更新该转发规则。直接部署在 Linux 物理机或 Linux 虚拟机时不存在 Windows 转发层，不执行该步骤，只需放行 Linux 主机及上游网络的 `10086/tcp`。

## 当前数据库：SQLite

当前使用 SQLite 文件数据库：

```text
backend/data/hpc_control_panel.db
```

该文件不进入 Git。新机器首次启动后端时会自动创建空库和表结构。

适用场景：

- 单机部署
- 单 backend 实例
- 少量运维人员使用
- 中低频任务写入
- 开发模式或轻量生产

暂不适合：

- 多 backend 实例同时写入
- 高并发写入
- 多节点共享数据库
- 长期大规模任务日志写入

## SQLite 备份

在线备份：

```bash
scripts/backup_sqlite.sh
```

默认备份到：

```text
backend/data/backups/
```

指定备份目录：

```bash
scripts/backup_sqlite.sh /backup/hpcdeploy
```

脚本使用 Python 标准库 `sqlite3.Connection.backup()`，可以在服务运行时备份。

## SQLite 恢复

恢复前建议停止服务。恢复脚本会在 systemd 可用时自动尝试停止并重启：

```bash
sudo scripts/restore_sqlite.sh backend/data/backups/<backup-file>.db --force
```

恢复脚本会先对当前数据库做安全备份：

```text
backend/data/backups/pre_restore_<timestamp>.db
```

未加 `--force` 时只展示将执行的操作，不覆盖数据库。

## 后续 Docker 路线

建议分两步走。

### 阶段 1：Docker + SQLite volume

以下为后续容器化路线，不代表当前 systemd + Nginx 服务名称：

容器：

```text
hpcdeploy-backend
hpcdeploy-frontend
```

数据挂载：

```text
./backend/data:/app/backend/data
./backend/keys:/app/backend/keys
./backend/apptainer:/app/backend/apptainer
```

优点：

- 改造小
- 保留当前 SQLite 逻辑
- 适合单机部署
- 迁移风险低

限制：

- backend 仍建议单实例
- 数据库备份仍需文件级备份

### 阶段 2：Docker + MySQL

容器：

```text
hpcdeploy-backend
hpcdeploy-frontend
hpcdeploy-mysql
```

适合：

- 多人长期使用
- 数据量持续增长
- 需要集中备份和数据库管理
- 后续希望支持 backend 多实例

切换 MySQL 前建议先引入 Alembic，管理数据库 schema migration。

## MySQL 切换预期工作

后续切换 MySQL 大致需要：

1. 增加 MySQL driver，例如 `pymysql`
2. 调整 `DATABASE_URL`
3. 引入 Alembic 管理表结构迁移
4. 检查 SQLAlchemy 模型在 MySQL 下的字段兼容性
5. 编写 SQLite 到 MySQL 的数据迁移脚本
6. 更新 Docker Compose 和备份恢复流程

当前阶段不建议立即切换 MySQL。先稳定 systemd + SQLite，再做 Docker + SQLite，最后再考虑 MySQL。
