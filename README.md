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
- 执行自带的基础环境配置、NVIDIA 驱动、CUDA、MPI 编译环境和 GPU / CPU内存 / 磁盘压测；磁盘压测统一使用 fio，在远端启动前识别实际底层设备，按 HDD、SSD、NVMe 或 RAID 逻辑盘选择安全的默认并发与工作集，并预留文件系统容量余量。性能主测默认负载为 4K 随机混合读写（读 30% / 写 70%）和直连 I/O，报告分别记录读写带宽、IOPS 及 p95/p99 延迟；其后追加逐写落盘的固定工作集 CRC32C 回读校验。多服务器时按每台服务器分别展示并按物理盘默认选择一个压测目录：同盘优先非根目录挂载点，只有根目录时选择根目录；每台只压自己勾选的目录，GPU、CPU/内存等前置阶段完成后，同服务器的已选磁盘并行运行，每盘生成独立子任务与报告；批次 ZIP 保留报告原始文件名（含挂载目录标识）。CPU/内存报告会采集 CPU Busy、I/O Wait、Steal、内存目标达成率和可用温度，并在运行中保留内存安全余量，负载未达到验证阈值或安全余量持续不足时明确判定失败。三类压测均要求 `openpyxl` 可用且生成非空 XLSX；依赖安装或报告生成失败时，TXT/CSV-only 结果不得标记为成功。
- 磁盘报告以用户指定时长完成性能主测；之后追加按时长和介质分档的持久化校验工作集：不超过 3 分钟为 8MiB/worker、3–60 分钟为 32MiB/worker；超过 60 分钟时 HDD 为 32MiB/worker，SSD/NVMe 及未知介质为 256MiB/worker。所有档位均保持逐写落盘和 CRC32C 回读；日志会明确标记“耐久校验中”，两阶段结果分别呈现。内核错误判定只监听任务开始后的新增事件，并只归因到本次测试目录对应的块设备及其父链；监控不可用时明确判定失败，不将未知状态写成通过。
- 查看任务进度、日志、压测报告和失败原因；单次与批次结果先在文件弹窗中确认下载项，批次可逐子任务查看、复制对应远端目录或下载聚合 ZIP。文件完整返回至前端后才触发浏览器保存并自动关闭弹窗，回到当前历史任务列表；请求失败时保留弹窗以便重试。
- 保存任务历史、审计记录和报告；管理员可以清理本机运行数据。
- Windows 压测页面仅管理、预览、下载与复制 `.ps1` / `.bat` / `.cmd` 资料，不会由 HPCDeploy 下发或执行。页面可按整机、GPU、CPU/内存或磁盘生成 PowerShell 命令；每个模块时长独立填写“小时 + 分钟”，整机会同步显示三阶段合计时长，生成命令仍只供复制到 Windows 主机手动运行。Windows 磁盘性能压测按物理盘去重：同一物理盘的多个分区只选一个非系统分区作为测试落点，避免分区并发抢占 I/O 后被分别判定。每块候选盘还会单独校验测试文件大小加 5GB 安全余量；空间不足的盘会记录跳过原因，其余盘及 GPU/CPU 阶段继续执行；全部候选盘不足时仅跳过磁盘阶段。
- Windows CPU/内存压测在启动 y-cruncher 前会核验 x64/x86 `MSVCP140.dll`；低于 `14.51.36247.0` 时，管理员 PowerShell 会从微软官方固定地址下载、验证 Microsoft 签名并静默修复最新 VC++ 2015–2022 Redistributable，安装后复核 DLL 版本。非管理员或复核失败时不启动 y-cruncher，并保留明确日志。
- Windows y-cruncher CPU/内存阶段将准备时间与有效压测时间分开：仅在 CPU 连续达到 80%、内存达到目标策略减 5 个百分点后才开始计入用户设定时长；默认准备超时为 15 分钟，超时明确标记为“准备超时”。EPYC `9Vxx` 自动选择 Zen 5 后端。
- Windows y-cruncher 准备阶段仅按内存每增加 10 个百分点记录一次；有效压测阶段仅在 0%、25%、50%、75%、100% 记录进度。因此默认 12 小时 CPU/内存压测每 3 小时记录一次有效进度，不会按分钟刷屏。
- Windows 压测页面以“常规压测 / 补测命令”双卡展示 GPU、CPU/内存或磁盘补测命令。输入原报告目录后，新报告以原报告为基线，仅替换本次选择模块的结果并重新生成完整 HTML：未补测的 GPU、CPU/内存和磁盘均保留原数据与展示；指定 `D:` 补测时仅以新结果替换 D:，C:/E: 等盘仍显示原结果。报告的整体结论、模块执行状态、项目状态、指标汇总和磁盘阈值均由合并后的有效采样和 DiskSpd 结果统一重评；已保留模块不会再被本次补测的“未启用/未启动”状态覆盖。补测磁盘时，总览和阶段时间保留原测周期并新增补测周期，GPU/CPU 时长从原始采样计算；每个目标盘会采集独立的读取/写入时间序列，趋势区输出 C/D/E 等分盘曲线，补测盘只使用新曲线，未补测盘保留旧曲线；工具清单从原报告补齐。磁盘默认补测全部物理盘，也可指定 `D:` 等盘符。已完成的融合报告可用 `-RebuildReportDir` 离线重建 HTML/ZIP，不会启动任何压测。两张卡的模块、时长和命令区对齐，复制按钮位于各卡右上角。
- 补测未执行 CPU/内存而融合报告已有 CPU 采样时，内存项目会使用已配置的 CPU 后端（如 `ycruncher`），不显示本次补测初始化的 `NotStarted` 临时值。
- 在独立的“常用运维命令”页面维护常用命令：左侧按标题检索，标题前的星标可在当前浏览器置顶常用条目，右侧默认只读；编辑时可选中文字加粗，复制会按可见内容保留换行、空行与缩进，保存、删除等写操作需管理员确认。内容仅作记录和复制，不会下发执行。

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
同时会注册每日 `02:30` 的 SQLite 在线备份任务；常规备份仅保留最近 7 份。
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

## NVIDIA 驱动包管理

需要给受管服务器安装 NVIDIA 驱动时，先在“资产库管理 / 脚本库”的 NVIDIA 驱动区域上传 Linux `.run` 安装包，并选择对应分类：`GeForce` 或 `数据中心卡`。这里上传的驱动会保存到本机驱动库，可在后续任务中反复选择使用。

“执行任务”页面中的“上传自定义 `.run`”仅供本次任务临时使用；临时文件会在 7 天后自动清理，不适合用作长期驱动库。驱动包最终会由 HPCDeploy 自动上传到选定的受管服务器执行安装，无需逐台手工传文件。

如需迁移一套保留历史的 HPCDeploy，请一并迁移 `backend/data/gpu_driver_library/`，以保留已上传的长期驱动包；全新部署则在新系统的资产库重新上传即可。

## 日常更新

进入项目目录后执行：

```bash
cd hpc-deploy
sudo ./deploy/scripts/redeploy_hpcdeploy.sh
```

脚本会自动构建并发布新版本。若有正在执行的任务，脚本会拒绝重启，避免中断任务；等任务结束后再更新。

## 前端真实浏览器验证

前端目录提供 Playwright 无头 Chromium 冒烟验证，不依赖系统 Chromium 或图形桌面。首次使用需下载浏览器运行时：

```bash
cd frontend
npx playwright install chromium
npm run test:browser
```

该命令会自动启动 Vite，分别验证桌面与触屏窄视口、减少动画偏好、页面控制台和未捕获异常，并把每次运行的截图和失败追踪保存在被 Git 忽略的 `frontend/test-results/`。若要验证已部署实例而非本地开发服务器：

```bash
cd frontend
PLAYWRIGHT_BASE_URL=http://127.0.0.1:10086 npm run test:browser
```

交互式排查可额外配置 Chrome DevTools MCP；自动化验收以 `npm run test:browser` 为准。

## 后期维护

- 想升级版本：执行上面的“日常更新”。
- 想看服务是否正常：执行下面“页面打不开”中的两条状态命令。
- 数据库每天 `02:30` 自动在线备份并滚动保留 7 份；执行 `systemctl list-timers hpcdeploy-sqlite-backup.timer` 可查看下次时间。备份、迁移和恢复详见 [部署与卸载完整说明](deploy/README.md)。
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
