# HPCDeploy 部署与运维手册

用于**首次安装、日常更新和 systemd 服务排障**。SQLite 备份恢复与 Docker / MySQL 演进请阅读 [../docs/deployment.md](../docs/deployment.md)；架构和安全模型请阅读 [../docs/architecture.md](../docs/architecture.md)。

当前部署形态为 Nginx 静态托管前端、systemd 管理后端 uvicorn。生产访问地址为 `http://<server-ip>:10086/`。Vite dev server 仅用于开发人员本地调试，不注册 systemd 服务。

## 前提与边界

- 部署机需为 Linux，执行安装脚本的用户需具备 `sudo` 权限。
- 脚本自动识别 `apt-get`、`dnf` 或 `yum`，并在缺少时安装 `python3`、`python3-venv`、`python3-pip`、`nodejs`、`npm`、`nginx`。
- 前端构建要求 Node.js 18 或更高版本。脚本优先选择部署用户 NVM 中可用的最高版本，再回退到系统 Node.js；没有受支持版本时会在安装或发布前停止，不会覆盖现有静态文件或重启服务。
- 后端仅监听 `127.0.0.1:8000`；Nginx 监听 `0.0.0.0:10086`。如需跨主机访问，请按现场安全策略放行或限制 `10086/tcp`。
- 首次安装自动创建 `/etc/hpcdeploy/hpcdeploy.env`：交互设置管理员密码并随机生成内部 JWT 密钥；生产模式缺少安全值时后端拒绝启动。

## 文件说明

- `systemd/hpcdeploy-backend.service`
  - 后端服务示例；实际安装时由脚本按当前路径和用户动态生成
- `nginx/hpcdeploy.conf`
  - Nginx 站点配置，托管 `/var/www/hpcdeploy` 并代理 `/api/` 与 WebSocket
- `scripts/install_hpcdeploy_service.sh`
  - v1.1.0；初始化或保留生产安全配置、安装依赖、生成后端 systemd 服务、构建前端并配置 Nginx
- `scripts/reset_admin_password.sh`
  - v1.0.0；仅限 root 在本机重置管理员密码、备份 SQLite、清除数据库密码覆盖并使旧管理员会话失效
- `scripts/redeploy_hpcdeploy.sh`
  - v1.1.0；更新依赖、构建并发布前端、重启后端并重载 Nginx；发布开始及重启前检测活动任务，存在活动任务时拒绝重启，避免切断远端 SSH 执行通道

## 首次安装

```bash
git clone <repo-url> hpc-deploy
cd hpc-deploy
chmod +x deploy/scripts/install_hpcdeploy_service.sh
sudo deploy/scripts/install_hpcdeploy_service.sh
```

安装脚本会自动识别当前项目路径和 `SUDO_USER`，不要求固定在 `/home/tjzs/projects/hpc-deploy`。
脚本会自动安装基础系统依赖、创建后端虚拟环境、安装项目依赖、执行前端生产构建、发布静态文件，并注册后端 systemd 服务与 Nginx。

首次安装会交互要求输入两次管理员密码，密码至少 6 位，具体内容由部署人员自行决定。JWT 密钥由脚本自动生成，不显示且无需记忆。安全配置保存到：

```text
/etc/hpcdeploy/hpcdeploy.env
owner: root:root
mode:  0600
```

重复执行安装脚本时保留已有安全配置，不覆盖管理员密码或 JWT 密钥。无终端的自动化安装可预先传入 `HPCDEPLOY_ADMIN_PASSWORD`；若未传入，脚本生成随机管理员密码并在安装结束时仅显示一次。

### 忘记管理员密码

在部署服务器执行：

```bash
sudo /path/to/hpc-deploy/deploy/scripts/reset_admin_password.sh
```

脚本要求输入两次新密码，并执行以下操作：

1. 在线备份 SQLite 到 `backend/data/backups/pre_admin_reset_<时间>.db`。
2. 删除 `system_settings.admin_password` 的网页修改覆盖值，使新环境密码立即生效。
3. 更新 `/etc/hpcdeploy/hpcdeploy.env`，同时轮换 JWT 密钥，使已有管理员会话失效。
4. 重启后端并检查 `/api/health`。

任务、服务器、SSH 密钥、历史记录和报告不受影响。管理员密码重置不提供网页找回入口，因为恢复权限以部署服务器的 root/sudo 权限为准。

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

发布开始及后端重启前会查询活动任务。存在 `CONNECTING`、`PREPARING`、`UPLOADING`、`RUNNING` 或 `CANCELING` 任务时，脚本拒绝重启并输出任务 ID；等待任务结束或取消后再执行发布。后端本身不可访问时允许继续发布，用于故障恢复。

从旧版本首次升级到“生产安全配置”版本时，需要重新执行一次安装脚本，而不是只执行更新脚本：

```bash
sudo deploy/scripts/install_hpcdeploy_service.sh
```

它会创建 `/etc/hpcdeploy/hpcdeploy.env` 并更新 systemd 的 `EnvironmentFile`；以后继续使用 `redeploy_hpcdeploy.sh` 即可。若安全配置已经存在，安装脚本会保留原值。

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
