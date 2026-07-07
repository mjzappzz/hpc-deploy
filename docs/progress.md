# HPCDeploy 项目进度记录

## 当前完成度

HPCDeploy 已形成完整闭环，端到端链路全部打通：

```
服务器管理（含标签筛选/健康探测/一键部署公钥）
→ 脚本/模板选择
→ 多服务器任务执行
→ 实时日志 + 实时监控
→ 结果文件回收与下载
→ 失败诊断
→ 审计日志
→ 系统设置（运行数据/本机清理）
```

---

## 已完成重点功能

### 服务器管理
- CRUD、SSH 测试、SSH Key / Password 登录
- 一键部署公钥（Password → SSH Key 切换）
- 服务器健康探测、探测全部（默认跳过离线，3s timeout）
- **标签管理**：标签添加/编辑/删除、标签列展示、标签筛选、标签统计（含在线/离线计数）

### 任务执行
- test / stress / mpi / install 白名单脚本执行
- stress 参数化（时长参数 + 白名单校验）
- 任务模板/执行预设（9 个模板一键填充）
- 批量任务执行（多选服务器，独立线程，离线跳过）
- 任务取消（PID→PGID→SIGTERM/SIGKILL + 远端目录清理）
- 任务删除（清理 artifacts / 远端目录 / 日志 / 记录）
- 任务历史筛选/搜索/分页
- 任务失败诊断（GPU/CUDA/SSH/磁盘/路径错误识别）
- 进度可视化：中文状态标签、运行耗时 HH:mm:ss、进度条、预计剩余

### 实时日志
- WebSocket 主通道（心跳 30s、断线自动 HTTP 轮询备用）
- HTTP 轮询备用通道
- 日志下载（task_id.log 格式）

### 实时监控
- CPU/内存结构化卡片网格（CPU 使用率 / Load Average / 内存）
- 磁盘挂载点 el-table 展示（总容量/已用/可用/使用率进度条）
- GPU 卡片列表展示（利用率/显存/温度）
- 5s 轮询，子系统隔离

### Apptainer
- .sif 文件上传（不执行 run/exec）
- 单台+批量多线程分发（SFTP）
- Apptainer 镜像目录只读查看

### 运行数据与本机清理
- 系统设置集中展示数据库、任务日志、SSH keys、脚本库、artifacts、SQLite 备份、Apptainer 镜像和远端目录约定
- 展示本机关键路径大小、文件数、是否存在和关注标签
- 本机结果文件按 task 目录聚合查看与批量删除，自动显示元数据（服务器名称/任务类型/脚本名/日期标签）
- 本机结果按目录 mtime 降序排列（最新在前）
- 自动清理本地报告面板融合到系统设置：开关/保留天数/执行时间配置、最近一次执行结果展示
- 自动清理按目录 mtime 判断是否过期，跳过运行中任务，删除前路径防逃逸校验
- 远端目录清理功能保留后端能力和旧路由兼容，但不再作为默认侧边栏入口

### 系统设置
- 运行数据与路径总览
- 本机结果文件扫描、删除、自动清理
- 管理员密码弹窗修改
- 默认 SSH 密钥生成迁移到服务器管理“部署公钥”流程

### 审计日志
- 关键操作记录：任务创建/删除/取消/诊断、压测套件创建、清理、设置保存、服务器增删改/探测/SSH 测试/公钥部署
- 分页查询、按操作类型/对象类型/状态/关键词筛选
- **统一英文 action 命名 + 前端中文标签映射**
- **所有调用点补全 `detail_json` 结构化上下文**
- **敏感字段自动过滤**（password/private_key/token/command/raw_shell/raw_args/env）
- **新增 `server_id` 字段**
- 不记录密钥内容

### 仪表盘
- 服务器总数/在线/离线统计
- 任务运行/等待/取消/成功/失败/已取消统计
- 结果文件归档目录数量和占用空间
- 8 个快捷操作按钮
- 最近任务行点击跳转任务历史
- 结果文件目录树查看

### 任务诊断增强（规则引擎，无外部 AI）
- 诊断引擎重写：新增 5 条元数据预检查规则（用户取消、回收失败、报告未收尾、超时无报告、stress 卡住）
- 状态分流：SUCCESS/RUNNING/PENDING 不进入错误模式匹配，分别返回对应结论
- 新增归因分类（`attribution`）：平台问题/脚本问题/远端环境/用户取消/任务超时/回收失败
- 新增结论（`conclusion`）：一句话结论，SUCCESS+报告 FAIL 时标注"平台任务成功但报告压测为 FAIL"
- 新增风险提示（`risk_tips`）：每条规则附带可执行的风险警告
- 诊断入口统一：所有任务（SUCCESS/RUNNING/PENDING/FAILED/CANCELED）均可点击诊断
- 修复 SUCCESS 任务误判为"未知失败类型"：预检查函数增加 `**kwargs` 兼容参数传递
- 诊断弹窗标签按任务状态显示颜色（SUCCESS→绿色、FAILED→红色、RUNNING→蓝色、PENDING→灰色）
- 诊断弹窗位置上移（top 6vh），内容过长时内部滚动

### 管理员密码修改
- 系统设置新增"管理员密码"卡片，支持修改密码
- 密码保存到 `system_settings` 表，验证优先 DB 后回退环境变量
- `admin_password` 加入 `FORBIDDEN_KEYS`，不能通过 PUT /settings 读写
- 修改密码写入审计日志，需要 admin_token + 当前密码双验证

### 管理员密码确认式高风险操作保护（Phase 26）
- 移除用户账号体系（User 模型、login/logout/me 端点、登录页）
- 替换为管理员密码确认弹窗（ElMessageBox.prompt）
- 5 分钟 admin_token 缓存（内存，不存 localStorage）
- 高风险接口通过 `X-Admin-Token` header 保护
- 管理员密码通过 `HPCDEPLOY_ADMIN_PASSWORD` 环境变量配置
- 侧边栏菜单 admin 标签标记

### WebSocket 多进程广播（Phase 28 — 已完成）
- WebSocket 连接所在 worker 每秒 tail 数据库 `task_logs`
- 状态变化从数据库补发 `status`，终态补发 `done`
- 同进程内仍保留 `ws_manager` 即时广播
- 不引入 Redis / Celery，不改变前端协议和 HTTP 轮询备用链路

### 稳定性与交互优化（Phase 28B — 已完成）
- stress-suite 同服务器串行锁，严格按 GPU → CPU/内存 → 磁盘推进
- 后台启动成功仅表示任务进入 RUNNING，suite 调度只在任务终态后推进
- stress 远端启动后立即写 RUNNING / started_at，避免远端已跑但页面仍 PENDING
- 失败、取消、超时任务只要 artifacts 已回收即可显示结果文件入口
- 审计日志进入页面不再自动弹管理员确认，点击“查看审计日志”后再确认
- 管理菜单移动到底部区域，服务器管理和任务执行页做表格/卡片/日志弹窗交互优化
- GPU 压测报告脚本支持多卡元数据、每卡统计和 XLSX 报告

### 本地报告自动清理（Phase 29 — 已完成）
- 自动清理范围只限 `backend/data/artifacts` 下的本地任务结果目录
- 默认关闭，默认保留 30 天，默认每日 03:00 执行
- 清理中心新增“自动清理本地报告”开关、保留天数、执行时间和最近一次结果展示
- 自动清理按目录 mtime 判断是否超过保留天数，删除前确认路径仍在 artifacts 根目录下
- RUNNING / PENDING / CONNECTING / PREPARING / UPLOADING 任务对应的本地 artifact 目录会跳过
- 每次自动清理写入 `actor=system`、`action=auto_cleanup_local_artifacts` 审计日志
- 不自动清理远端服务器目录、downloads/tmp、Apptainer 镜像、数据库、keys、scripts

---

## 最近完成事项

1. **管理员密码确认式高风险操作保护** — 移除账号登录体系，高风险操作（删除/清理/审计日志/设置保存/SSH 密钥生成）通过密码确认弹窗保护。
2. **取消分组，只保留标签** — 所有 `group_name` 相关功能已移除
3. **修复编辑服务器标签不显示** — 根因：Pydantic from_attributes 不读取 hybrid_property，修复：ServerRead 增加 model_validator 显式解析 tags_json
4. **标签全链路打通** — 标签列展示、标签筛选、任务执行页标签筛选、清理中心标签筛选、标签统计含在线/离线计数
5. **任务执行页进度右移** — 进度信息移到右侧实时面板顶部
6. **实时监控结构化展示** — CPU/内存/磁盘/GPU 5s 轮询卡片展示
7. **SSH 执行器重连机制** — `SSHExecutor.reconnect()` 自动重连，`_execute_stress_async` 轮询中 SSH 闪断自动重连一次再试
8. **批次视图总耗时列** — 后端计算 `duration_seconds`，前端展示 `1h 23m 45s` 格式
9. **取消/超时远端文件不删除** — 确认 `TaskCancelRequest.delete_remote_files` 默认 `False`，超时/失败流程无自动远程目录清理
10. **WebSocket 多进程广播** — WS endpoint 主动 tail 数据库日志和任务状态，多 uvicorn worker 下可补发日志与终态
11. **清理中心布局优化** — 远端优先、本地次之的重排
12. **WebSocket 实时日志** — 双通道日志推送，心跳 30s，断线自动 HTTP 轮询
13. **审计日志全面完善** — 统一英文 action 命名、全调用点 detail_json 上下文、敏感字段过滤、新增 server_id
14. **批次视图展开状态修复** — 自动刷新不再折叠已展开行，通过 `:expand-row-keys` + `toggleRowExpansion` 恢复
15. **stress-suite 串行调度修复** — 同服务器加锁，后续子任务只在前序任务终态后启动，后台启动成功不再被误判为完成
16. **任务结果入口修复** — 失败/取消任务 artifacts 可见时显示结果文件，结果弹窗显示远端服务器目录
17. **任务历史跳转定位修复** — 压测套件弹窗“查看批次详情”跳转批次视图、自动搜索并展开 batch
18. **任务执行页压测脚本选择优化** — 压测脚本统一多选，选 1 个走单任务，选 2/3 个自动按 GPU→CPU/内存→磁盘创建套件
19. **服务器管理 UI 优化** — 部署公钥外置、表格列宽重分配、标签选择后自动收起、新增服务器默认密码认证
20. **日志查看体验优化** — 下载日志并入查看日志弹窗，去除日志工具栏白色间隙
21. **侧边栏与审计日志体验优化** — 审计日志/系统设置下移到底部管理区，审计日志延迟管理员确认
22. **GPU 多卡报告脚本更新** — GPU 压测脚本按卡统计利用率、温度、功耗、显存，输出 TXT/XLSX 报告
23. **诊断引擎增强（16 条规则）** — 新增 5 条元数据预检查、状态分流、归因/结论/风险提示字段
24. **SUCCESS 任务诊断修复** — 修复 `**kwargs` 缺失导致预检查全崩溃、SUCCESS 任务误判为未知失败
25. **诊断入口统一** — 所有状态任务（SUCCESS/RUNNING/PENDING）均可诊断，不再限制 FAILED
26. **诊断弹窗优化** — 状态标签颜色按任务状态显示、弹窗位置上移、内容过长可滚动
27. **管理员密码修改** — 系统设置新增修改密码功能，DB 存储 + 环境变量回退

28. **公钥检测逻辑修复** — 区分检测失败/未安装：远端没有 authorized_keys 显示"未安装"而非"检测失败"；SSH 连不上/密钥文件不存在才显示"检测失败"。使用 `exec_capture` + `|| true` 替代 `exec_simple`，避免远端命令非零退出码抛异常。远端路径统一用 `$HOME` 替代 `~` 避免 tilde 展开问题。
29. **公钥部署兼容 key/password 双认证** — 每台服务器按自身 `auth_type` 和 `key_path`/`password` 独立认证登录，不再固定用 `id_ed25519` 私钥或只支持 password 登录。单台失败不影响其他服务器。
30. **密钥路径统一解析** — 新增 `_resolve_server_key_path()` 统一处理 `/backend/keys/xxx` 前缀和相对路径，解析为绝对路径，避免 systemd 下 CWD 不同导致密钥找不到。
31. **部署公钥弹窗优化** — 打开弹窗不再自动 SSH 检测全部服务器。直接读取服务器已有 `auth_type` 判断：`auth_type=key` 显示"已安装"，`auth_type=password` 显示"未安装"。"检测全部"按钮保留供手动验证。
32. **异常兜底保护** — 批量检查/部署线程新增 `except Exception` 捕获未知异常，防止单线程崩溃导致结果丢失。
33. **部署与运行数据文档化** — 新增 `docs/deployment.md`、SQLite 备份/恢复脚本，明确 systemd 开发部署、Docker+SQLite、Docker+MySQL 路线。
34. **系统设置重组** — 清理中心本机结果文件功能融合到系统设置，运行数据与路径展示关键本机目录大小/文件数，管理员密码改为左上角弹窗入口。
35. **部署公钥流程补强** — 默认 SSH 密钥生成迁移到服务器管理部署公钥流程；无可部署密钥时弹窗生成 `id_ed25519`。

---

## 近期维护记录

### 2026-07-07 — 任务历史统一展示 + 本机结果清理联动隐藏

**任务历史统一展示**
- 移除“单次任务视图 / 批次任务视图”切换入口，任务历史统一展示普通任务与批次任务
- 普通任务继续使用任务卡；同一 `batch_id` 的任务在前端聚合为一个批次卡
- 批次卡内按子任务拆分展示 GPU / CPU内存 / 磁盘等状态、耗时、退出码、详情和报告入口
- 批次卡不再显示整体统计与整体状态，避免和子任务状态重复
- `PARTIAL_FAILED` 前端显示为“部分完成”，状态标签使用 warning 色
- 任务历史 keyword 搜索支持 `batch_id` 和 `file_name`，修复从任务执行页跳转批次历史为空的问题

**本机结果文件与历史联动**
- 清理中心页面与 `/cleanup` 前端路由已删除，本机结果文件清理整合到系统设置
- 系统设置本机结果文件表格显示任务名称、任务 ID、任务类型（单次/批次/遗留）、子任务数量
- 本机 artifacts 扫描按 `batch_id` 聚合批次结果，展开批次可查看所有子任务名称、task_id、目录、文件数和大小
- 删除本机结果文件后不物理删除任务记录，只设置 `tasks.hidden_from_history=1`、`hidden_reason`、`hidden_at`
- 任务历史和批次接口默认过滤 `hidden_from_history=1`，保留数据库记录但不再展示

**功能收口**
- 移除“重新执行/重跑”模块：前端按钮、API client、后端 `/tasks/{task_id}/rerun` 端点和响应 schema 均已删除
- 服务器详情快捷入口从“打开清理中心”改为“打开系统设置”

### 2026-07-06 — 状态体系统一 + 仪表盘进度条 + 服务器标签内联编辑

**最终状态统一（final_status）**
- 新增 `backend/app/core/task_state_resolver.py` — `resolve_final_status()` 单源真理
- 优先级：report FAIL > report PASS > execution FAILED > UNKNOWN
- 诊断弹窗顶部改为 final_status 展示（压测失败/压测通过/执行失败）
- TaskCard、批次展开、抽屉详情、诊断弹窗统一使用 final_status
- `_compute_batch_status` 考虑报告状态（SUCCESS+FAIL 报告 → 批次 FAILED）
- batch detail API 返回 `final_status`

**仪表盘进度条**
- 最近任务表新增进度列（el-progress），实时显示运行耗时 + 预计剩余
- 移除快捷操作卡片
- 使用 tick 计数器 + `currentNow()` 保证进度条每秒刷新
- 后端 `RecentTaskItem` 新增 `params`、`command_preview`、`duration_seconds`、`final_status`

**服务器标签内联编辑**
- 标签列改为点击直接出现输入框，回车/失焦保存
- 去掉编辑对话框中的标签字段
- 标签使用 `el-tag` 蓝色芯片展示，点击任意位置编辑
- 多个标签用逗号/空格分隔

**任务执行页服务器卡片**
- 标签从 meta 行移到 title 行，紧跟在服务器名称后

---

## 当前暂未做

- 调度器集群集成（Slurm 等）
- 可配置远端任务根目录

---

## 下一步优先级

项目已进入维护期，所有阶段开发完成。后续以修复缺陷、优化体验为主。

---

## 明天继续的明确入口

1. 先读 `README.md`、`docs/architecture.md`、`docs/development-stages.md`、`docs/progress.md`
2. 所有 29 个阶段已全部完成，项目进入维护期
3. 后续以修复缺陷、优化体验为主，不再新增大型功能
4. 不要做强制全站登录、复杂 RBAC、多用户管理
5. 修改后必须跑 `compileall` + `npm run build`
6. 前端不传 raw command / raw_args / remote_path / remote_work_dir
7. 高风险操作的所有 API 已经通过 `require_admin_token()` 依赖保护
8. 新增 `backend/app/core/task_state_resolver.py` — 统一 final_status 规则，report 状态优先
9. 任务历史默认过滤 `hidden_from_history=1`；系统设置删除本机结果文件会软隐藏历史任务
10. 清理中心页面已删除，本机结果文件清理入口在系统设置
11. 重跑/重新执行模块已删除；如需再次执行，回到任务执行页新建任务

---

## Next Session Prompt

```
继续 HPCDeploy 项目。
所有规划阶段已完成，项目进入维护期。
请先读取 README.md、docs/progress.md、docs/development-stages.md、docs/architecture.md。
不要做强制全站登录。
不要做复杂 RBAC。
不要做多用户管理。
普通访客默认可正常使用平台。
只有删除、清理、审计日志、系统设置保存、生成 SSH 密钥等高风险操作需要管理员密码确认。
前端不要传 raw command / raw_args / remote_path / remote_work_dir。
不要 git add .
不要 git commit，除非我明确要求。
最终状态规则：report FAIL > report PASS > execution FAILED > UNKNOWN，
实现在 backend/app/core/task_state_resolver.py。
任务历史统一展示单次和批次任务；清理中心页面已删除，本机结果文件在系统设置。
删除本机结果文件只软隐藏历史任务，不物理删除任务记录，字段为 hidden_from_history。
重跑/重新执行模块已删除。
```
