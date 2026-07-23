# HPCDeploy 部署与运维手册

用于**首次安装、日常更新和 systemd 服务排障**。SQLite 备份恢复与 Docker / MySQL 演进请阅读 [../docs/deployment.md](../docs/deployment.md)；架构和安全模型请阅读 [../docs/architecture.md](../docs/architecture.md)。

当前部署形态为 Nginx 静态托管前端、systemd 管理后端 uvicorn。生产访问地址为 `http://<server-ip>:10086/`。Vite dev server 仅用于开发人员本地调试，不注册 systemd 服务。

## 前提与边界

- 部署机需为 Linux，执行安装脚本的用户需具备 `sudo` 权限。
- 脚本自动识别 `apt-get`、`dnf` 或 `yum`，并在缺少时安装 `python3`、`python3-venv`、`python3-pip`、`nodejs`、`npm`、`nginx`。
- 前端构建要求 Node.js 18 或更高版本。脚本优先选择部署用户 NVM 中可用的最高版本，再回退到系统 Node.js；没有受支持版本时会在安装或发布前停止，不会覆盖现有静态文件或重启服务。
- 后端仅监听 `127.0.0.1:8000`；Nginx 监听 `0.0.0.0:10086`。如需跨主机访问，请按现场安全策略放行或限制 `10086/tcp`。
- 生产使用前必须通过环境变量设置非默认的 `SECRET_KEY` 与 `HPCDEPLOY_ADMIN_PASSWORD`；详见根目录 [README.md](../README.md#环境变量)。

## 文件说明

- `systemd/hpcdeploy-backend.service`
  - 后端服务示例；实际安装时由脚本按当前路径和用户动态生成
- `nginx/hpcdeploy.conf`
  - Nginx 站点配置，托管 `/var/www/hpcdeploy` 并代理 `/api/` 与 WebSocket
- `scripts/install_hpcdeploy_service.sh`
  - 一次性安装依赖、生成后端 systemd 服务、构建前端并配置 Nginx
- `scripts/redeploy_hpcdeploy.sh`
  - 更新依赖、构建并发布前端、重启后端并重载 Nginx

## 首次安装

```bash
git clone <repo-url> hpc-deploy
cd hpc-deploy
chmod +x deploy/scripts/install_hpcdeploy_service.sh
sudo deploy/scripts/install_hpcdeploy_service.sh
```

安装脚本会自动识别当前项目路径和 `SUDO_USER`，不要求固定在 `/home/tjzs/projects/hpc-deploy`。
脚本会自动安装基础系统依赖、创建后端虚拟环境、安装项目依赖、执行前端生产构建、发布静态文件，并注册后端 systemd 服务与 Nginx。

### WSL 部署的 Windows 网络入口

本节**仅适用于 WSL NAT 环境**。项目运行在 WSL、且需要通过 Windows 宿主机局域网地址访问时，还需在 Windows **管理员 PowerShell** 配置同端口转发和防火墙规则。

如果直接部署在 Linux 物理机或 Linux 虚拟机上，**不需要执行本节的 `netsh portproxy` 命令**；Nginx 会直接监听该 Linux 主机的 `10086/tcp`，只需按现场策略放行 Linux 防火墙和上游网络即可。

WSL NAT 环境执行：

```powershell
$wslIp = (wsl.exe hostname -I).Trim().Split(' ')[0]
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=10086 2>$null
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=10086 connectaddress=$wslIp connectport=10086
if (-not (Get-NetFirewallRule -DisplayName "HPCDeploy Nginx 10086" -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName "HPCDeploy Nginx 10086" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 10086 }
```

WSL 重启后若内网 IP 发生变化，重新执行上述端口转发命令。验证：

```powershell
curl.exe http://127.0.0.1:10086/api/health
curl.exe http://<windows-lan-ip>:10086/api/health
```

## 日常更新

```bash
cd /path/to/hpc-deploy
chmod +x deploy/scripts/redeploy_hpcdeploy.sh
sudo deploy/scripts/redeploy_hpcdeploy.sh
```

更新脚本会解析受支持的 Node.js、更新后端依赖、构建并发布前端、检查 Nginx 配置、重启后端，然后等待 `http://127.0.0.1:8000/api/health` 返回成功；健康检查未通过时脚本失败退出，不会继续重载 Nginx 或报告发布成功。

## 常用命令

```bash
systemctl status hpcdeploy-backend
systemctl status nginx
journalctl -u hpcdeploy-backend -n 200 --no-pager
journalctl -u nginx -n 200 --no-pager
nginx -t
```

## 排障入口

1. 服务未启动：先执行 `systemctl status hpcdeploy-backend nginx --no-pager -l`。
2. 页面无法访问：确认 Nginx 为 active，确认监听 `10086/tcp`，再检查主机防火墙和网络访问策略。
3. API 或任务异常：查看后端日志 `journalctl -u hpcdeploy-backend -n 200 --no-pager`。
4. 更新后异常：重新执行 `sudo deploy/scripts/redeploy_hpcdeploy.sh`；若后端健康检查失败，查看脚本末尾错误及 `journalctl -u hpcdeploy-backend -n 200 --no-pager`，修复后再发布。
5. WSL 内访问正常但 Windows/LAN 地址超时：检查 `netsh interface portproxy show v4tov4`、Windows 防火墙规则及当前 WSL IP。
