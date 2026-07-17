# HPCDeploy 部署与运维手册

用于**首次安装、日常更新和 systemd 服务排障**。SQLite 备份恢复与 Docker / MySQL 演进请阅读 [../docs/deployment.md](../docs/deployment.md)；架构和安全模型请阅读 [../docs/architecture.md](../docs/architecture.md)。

当前部署形态为 systemd 开发服务复刻：后端运行 `uvicorn`，前端运行 Vite dev server，访问地址为 `http://<server-ip>:5173`。这不是 Nginx 静态托管或容器化生产部署。

## 前提与边界

- 部署机需为 Linux，执行安装脚本的用户需具备 `sudo` 权限。
- 脚本自动识别 `apt-get`、`dnf` 或 `yum`，并在缺少时安装 `python3`、`python3-venv`、`python3-pip`、`nodejs`、`npm`。
- 后端仅监听 `127.0.0.1:8000`；前端监听 `0.0.0.0:5173`。如需跨主机访问，请按现场安全策略放行或限制 `5173/tcp`。
- 生产使用前必须通过环境变量设置非默认的 `SECRET_KEY` 与 `HPCDEPLOY_ADMIN_PASSWORD`；详见根目录 [README.md](../README.md#环境变量)。

## 文件说明

- `systemd/hpcdeploy-backend.service`
  - 后端服务示例；实际安装时由脚本按当前路径和用户动态生成
- `systemd/hpcdeploy-frontend.service`
  - 前端 Vite dev server 服务示例；实际安装时由脚本按当前路径和用户动态生成
- `nginx/hpcdeploy.conf`
  - Nginx 站点配置，保留给后续生产静态托管使用；当前默认安装脚本不启用
- `scripts/install_hpcdeploy_service.sh`
  - 一次性安装依赖、生成后端/前端 `systemd` 服务
- `scripts/redeploy_hpcdeploy.sh`
  - 更新依赖并重启后端/前端服务

## 首次安装

```bash
git clone <repo-url> hpc-deploy
cd hpc-deploy
chmod +x deploy/scripts/install_hpcdeploy_service.sh
sudo deploy/scripts/install_hpcdeploy_service.sh
```

安装脚本会自动识别当前项目路径和 `SUDO_USER`，不要求固定在 `/home/tjzs/projects/hpc-deploy`。
脚本会自动安装基础系统依赖、创建后端虚拟环境、安装项目依赖，并注册两个 systemd 服务。

## 日常更新

```bash
cd /path/to/hpc-deploy
chmod +x deploy/scripts/redeploy_hpcdeploy.sh
sudo deploy/scripts/redeploy_hpcdeploy.sh
```

## 常用命令

```bash
systemctl status hpcdeploy-backend
systemctl status hpcdeploy-frontend
journalctl -u hpcdeploy-backend -n 200 --no-pager
journalctl -u hpcdeploy-frontend -n 200 --no-pager
```

## 排障入口

1. 服务未启动：先执行 `systemctl status hpcdeploy-backend hpcdeploy-frontend --no-pager -l`。
2. 页面无法访问：确认前端服务为 active，确认监听 `5173/tcp`，再检查主机防火墙和网络访问策略。
3. API 或任务异常：查看后端日志 `journalctl -u hpcdeploy-backend -n 200 --no-pager`。
4. 更新后异常：重新执行 `sudo deploy/scripts/redeploy_hpcdeploy.sh`；该脚本会更新依赖并重启两个服务。
