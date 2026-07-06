# HPCDeploy Deployment

推荐部署方式：

- 后端：`systemd` 运行 `uvicorn`
- 前端：`systemd` 运行 Vite dev server
- 当前模式：开发模式复刻，访问 `http://<server-ip>:5173`
- 后续生产化：建议切换为 Docker 或 nginx 静态托管

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
