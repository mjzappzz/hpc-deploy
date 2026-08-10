# HPCDeploy

HPCDeploy 是一个 Linux / HPC 服务器运维控制台：管理服务器、执行环境配置或压测任务、查看日志与报告。

<p align="center">
  <img src="frontend/public/assets/hpcdeploy-mascot.png" width="360" alt="HPCDeploy：抱着服务器、精神状态略微超频的运维人" />
</p>

<p align="center"><sub>压测开始后，运维人的精神状态。</sub></p>

## 你只需要知道这几件事

- 安装后在浏览器打开：`http://<部署机-IP>:10086/`
- 第一次安装时设置管理员密码；后续只需要记住这个密码。
- 受管服务器需要能通过 SSH 访问；在“服务器管理”中添加即可。
- 所有任务都在目标服务器执行；清理本系统不会删除任何受管服务器上的文件。

## 它能做什么

- 管理 Linux / HPC 服务器：添加、检测 SSH、部署公钥、打标签、关注常用服务器。
- 执行自带的基础环境配置、NVIDIA 驱动、CUDA、MPI 编译环境和 GPU / CPU内存 / 磁盘压测；CPU/内存报告会在目标主机提供可读传感器时采集 CPU 温度，Intel 优先使用 Package id、AMD 优先使用 Tctl/Tdie，无可用传感器时会明确标注。
- 查看任务进度、日志、压测报告和失败原因；批次结果可逐子任务查看、复制对应远端目录或下载聚合 ZIP。
- 保存任务历史、审计记录和报告；管理员可以清理本机运行数据。
- 在“资产库管理 → 常用运维命令”维护常用命令：左侧按标题检索，右侧默认只读；编辑时可选中文字加粗，保存、删除等写操作需管理员确认。内容仅作记录和复制，不会下发执行。

## 克隆后目录里有什么

```text
hpc-deploy/
├── deploy/          安装、更新、清理脚本
├── backend/         后端程序和自带 Linux / Windows 脚本
├── frontend/        网页界面源码
└── docs/            完整部署、架构和维护说明
```

安装后系统会自动创建数据库、任务报告、运行日志和 SSH 密钥目录。它们保存在本机，不会提交到 Git。

## 一键安装

在一台 Linux 机器上执行。你需要有 `sudo` 权限和网络软件源访问权限。

```bash
git clone https://github.com/mjzappzz/hpc-deploy.git hpc-deploy && \
  cd hpc-deploy && \
  sudo ./deploy/scripts/install_hpcdeploy_service.sh
```

安装脚本会自动安装 Python、Node.js、Nginx 等所需依赖，构建前端并启动服务。
上述命令仅在克隆成功后才会继续执行；若网络中断，请先确认 `hpc-deploy` 目录不存在或内容可丢弃，再重新执行整条命令。

安装时按提示输入两次管理员密码。看到“`HPCDeploy 服务安装完成`”后，在浏览器打开：

```text
http://<部署机-IP>:10086/
```

例如部署机 IP 是 `192.168.1.10`，访问地址就是 `http://192.168.1.10:10086/`。

如果提示找不到 `git`，先安装它：

```bash
# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y git

# Rocky / RHEL
sudo dnf install -y git
```

## 安装完成后怎么用

1. 打开“服务器管理” → “新增服务器”。
2. 填写服务器名称、IP、SSH 用户和密码或私钥，保存后检测连接。
3. 在“执行任务”选择在线服务器、任务类型和脚本，然后提交。
4. 到“历史任务”查看进度、日志、结果和失败原因。

小提示：服务器名称前的 `☆` 可以加入“我的关注”。关注会保存在当前浏览器中；离线收藏可以查看，但不能被选为任务目标。

## 日常更新

进入项目目录后执行：

```bash
cd hpc-deploy
sudo ./deploy/scripts/redeploy_hpcdeploy.sh
```

脚本会自动构建并发布新版本。若有正在执行的任务，脚本会拒绝重启，避免中断任务；等任务结束后再更新。

## 后期维护

- 想升级版本：执行上面的“日常更新”。
- 想看服务是否正常：执行下面“页面打不开”中的两条状态命令。
- 想备份或迁移数据库、报告和密钥：查看 [部署与卸载完整说明](deploy/README.md)。
- 想了解某个脚本、网络、权限或安全细节：到 [docs/](docs/) 中查看对应说明。

## 一键清理 / 卸载

进入项目目录后，先预览清理范围。这一步**不会删除任何内容**：

```bash
cd hpc-deploy
sudo ./deploy/scripts/uninstall_hpcdeploy.sh
```

确认输出的范围无误后，执行默认清理：

```bash
sudo ./deploy/scripts/uninstall_hpcdeploy.sh --force
```

默认清理会删除：

- HPCDeploy 后端服务
- HPCDeploy 的 Nginx 站点配置
- 已发布的前端页面

默认会保留：

- 本项目源代码（`hpc-deploy` 目录）
- 数据库、任务报告和运行记录
- SSH 私钥
- 管理员密码等生产配置
- 所有受管服务器上的远端文件

如果你明确要同时删除运行数据或密钥，请阅读 [完整卸载说明](deploy/README.md#卸载) 后再执行；这些操作不可恢复。

## 常见问题

### 页面打不开

在部署机执行：

```bash
sudo systemctl status hpcdeploy-backend --no-pager -l
sudo systemctl status nginx --no-pager -l
```

两项都应显示 `active (running)`。然后确认浏览器访问的是 `http://<部署机-IP>:10086/`，并检查部署机防火墙是否放行 `10086/tcp`。

### 忘记管理员密码

在项目目录执行：

```bash
sudo ./deploy/scripts/reset_admin_password.sh
```

按提示设置新密码即可；服务器、任务和报告不会丢失。

### 更新后有问题

重新执行日常更新命令；仍失败时查看后端日志：

```bash
sudo journalctl -u hpcdeploy-backend -n 200 --no-pager
```

## 想了解更多

- [部署与卸载完整说明](deploy/README.md)
- [部署架构与网络说明](docs/deployment.md)
- [系统架构与安全边界](docs/architecture.md)
- [项目进度记录](docs/progress.md)
