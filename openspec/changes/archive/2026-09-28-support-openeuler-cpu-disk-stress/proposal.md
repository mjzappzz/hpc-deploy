## Why

批次 `batch-20260928-101125-eaf071` 在 openEuler 24.03 (LTS-SP4) 上执行 CPU/内存及磁盘压测时，依赖检查进入 `Unsupported OS` 分支，任务未启动。现有脚本仅以 `/etc/redhat-release` 或 `/etc/debian_version` 选择安装路径，未覆盖该系统。

## What Changes

- 使 CPU/内存与磁盘压测脚本识别 openEuler，并在缺少依赖时使用经验证的发行版软件源和包安装路径。
- 保留现有依赖已齐备时的跳过逻辑；缺包、软件源不可用或报告依赖不可用时输出具体错误，不把依赖失败判为硬件压测失败。
- 为 openEuler 的发行版识别、依赖准备和失败分支增加回归验证。
- 本变更不包含 GPU 压测：本次目标服务器探测为“无 NVIDIA GPU”，GPU 子任务因缺少 `nvidia-smi` 失败，与 openEuler 识别问题不同。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `stress-validation`：明确 openEuler 上 CPU/内存和磁盘压测的依赖准备与错误归因要求。

## Impact

- 脚本：`backend/scripts/stress/cpu_mem_stress_report.sh`、`backend/scripts/stress/disk_stress_report.sh`。
- 测试：相关压测脚本与依赖安装测试；需核对 openEuler 24.03 的包名、可用软件源及 `stress-ng`、`fio`、`sysstat`、`python3-openpyxl` 的获取方式。
- 文档：按项目规则同步 `README.md` 或 `docs/architecture.md`，并更新 `docs/progress.md`，记录脚本版本、行为及兼容边界。
- 无 API 或数据库契约变更；适配后的依赖安装会在受管服务器上运行，实施验证前需单独确认远端包安装范围。
