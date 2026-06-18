# HPCDeploy Deployment

推荐部署方式：

- 后端：`systemd` 运行 `uvicorn`
- 前端：`npm run build` 后发布到 `/var/www/hpcdeploy`
- Web：`nginx` 提供静态文件并反代 `/api`

## 文件说明

- `systemd/hpcdeploy-backend.service`
  - 后端服务定义
- `nginx/hpcdeploy.conf`
  - Nginx 站点配置
- `scripts/install_hpcdeploy_service.sh`
  - 一次性安装 `systemd` 和 `nginx` 配置
- `scripts/redeploy_hpcdeploy.sh`
  - 前端重建发布、后端重启、Nginx reload

## 首次安装

```bash
cd /home/tjzs/projects/hpc-deploy
chmod +x deploy/scripts/install_hpcdeploy_service.sh
sudo deploy/scripts/install_hpcdeploy_service.sh
```

首次安装前还需要先发布前端静态文件：

```bash
cd /home/tjzs/projects/hpc-deploy/frontend
npm run build
sudo rsync -av --delete dist/ /var/www/hpcdeploy/
```

## 日常更新

```bash
cd /home/tjzs/projects/hpc-deploy
chmod +x deploy/scripts/redeploy_hpcdeploy.sh
sudo deploy/scripts/redeploy_hpcdeploy.sh
```

## 常用命令

```bash
systemctl status hpcdeploy-backend
journalctl -u hpcdeploy-backend -n 200 --no-pager
nginx -t
systemctl reload nginx
```
