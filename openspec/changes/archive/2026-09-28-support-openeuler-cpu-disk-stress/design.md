## Context

见 `proposal.md`。两个脚本在依赖齐备时直接继续；缺依赖时，仅凭 `/etc/redhat-release` 或 `/etc/debian_version` 选安装分支。前者会先检查或安装 EPEL，后者走 APT。openEuler 官方文档提供 DNF 软件包管理方式，但不保证目标机已配置的软件源包含每一个压测依赖。

## Goals / Non-Goals

**Goals:**

- 在 openEuler 24.03 LTS SP4 上通过明确的发行版识别进入独立依赖准备路径。
- 复用现有缺包检测、DNF 重试与安装后复核能力；不改变 RHEL 系及 Debian 系现有路径。
- 在依赖不可取得时保留具体安装错误与阶段证据，阻止压测和成功报告。

**Non-Goals:**

- 不为目标服务器新增、更换或启用软件源，不自动安装 EPEL，不修改系统仓库配置。
- 不扩展 GPU 脚本或在无 NVIDIA GPU 的主机上运行 GPU 压测。
- 不改变 API、数据库、批次调度和压测判定阈值。

## Decisions

1. **用 `/etc/os-release` 的 `ID` 精确识别 openEuler。** 将标识规范化后匹配 `openeuler`，并在现有 RHEL/Debian 分支之前处理。仅靠 DNF 存在与否会把其他 RPM 发行版误纳入；依赖 `/etc/redhat-release` 已在本次目标机失效。现有发行版分支保持原有判断和行为。
2. **使用目标机已配置的 DNF 软件源。** 根据缺失的命令或 Python 模块安装对应包，再复核 `stress-ng`、`fio`、`iostat` 与 `openpyxl` 等实际能力。openEuler 分支不调用 `ensure_epel_repo`，也不尝试 CentOS 8 仓库修复。只读检查确认目标机的 DNF 缓存列出 `stress-ng`、`python3-openpyxl`（openEuler `EPOL`）、`fio`（`everything`）和 `sysstat`（`OS`）；这些包当前均未安装。`EPOL` 是该机已配置的软件源，不等同于脚本针对其他发行版安装的 `epel-release`。实际安装仍需验证仓库可达；若失败则返回明确依赖错误，不静默引入其他发行版的 RPM 或未经确认的下载源。选择此方式是为了保持目标机的软件源信任边界。
3. **保留已齐备依赖的快速路径。** 只有确实缺失依赖时才调用包管理器；安装后仍以命令或模块可用性判断，不以 DNF 退出码单独宣布成功。openEuler 的 Python 报告依赖优先由已配置的 RPM 源提供；若不可用，明确失败，不默认向系统 Python 执行全局 pip 安装。
4. **验证覆盖两类阶段和原有分支。** 用受控的 OS 标识、包管理器和依赖探针测试 CPU/内存及磁盘脚本，覆盖依赖齐备、安装成功、缺包/仓库失败；原有 RHEL、Debian 路径做回归。真实 openEuler 环境只在获得远端安装和压测授权后验证。

## Risks / Trade-offs

- [目标机软件源不含所需包] → 在实施前只读核对可用包；缺包时保留明确失败，不自动添加第三方源。
- [脚本以 root 身份运行，DNF 会修改受管服务器] → 先验证本地逻辑；远端安装与压测另行确认范围。
- [发行版分支调整影响既有平台] → 仅匹配 `ID=openeuler`，并回归现有 RHEL/Debian 分支。
- [包安装成功但 XLSX 无法生成] → 安装后复核 `openpyxl` 导入与现有非空 XLSX 成功条件。

## Migration Plan

不需要数据库迁移。完成脚本、测试和文档后，按项目发布流程另行确认部署；发布前不会更改线上脚本。回退时恢复旧版脚本即可，但旧版仍不支持 openEuler 缺依赖场景。首次远端验证先核对软件源，再经授权运行短时 CPU/内存与磁盘压测。
