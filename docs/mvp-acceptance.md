# HPCDeploy MVP 验收清单

> 本文档用于 HPCDeploy MVP 功能验收。按模块逐一验收。

---

## 1. 服务器管理验收

- [ ] 新增服务器后出现在列表中，状态为 `unknown`
- [ ] SSH 测试成功后状态变为 `online`
- [ ] SSH 测试失败后状态变为 `offline`
- [ ] 支持 `SSH Key / Password` 两种认证方式
- [ ] SSH 私钥从 `backend/keys/` 下拉选择，不手写路径
- [ ] `Password` 登录服务器支持一键部署公钥
- [ ] 部署公钥成功后自动切换为 `SSH Key`
- [ ] 探测信息能显示 OS/CPU/内存/GPU/磁盘摘要
- [ ] 编辑服务器后列表同步更新
- [ ] 删除服务器后列表消失
- [ ] **标签保存后列表正确显示**
- [ ] **标签列最多显示 3 个标签，超过显示 +N**
- [ ] **标签筛选按选中标签准确过滤**
- [ ] **编辑服务器时已有标签正确回填**

## 2. 任务执行验收

- [ ] test 白名单脚本执行成功
- [ ] stress 白名单脚本执行成功（含时长参数）
- [ ] mpi 白名单脚本执行成功
- [ ] install 白名单脚本执行成功
- [ ] 批量执行多台服务器，独立 task_id
- [ ] 批量执行中离线服务器被正确跳过
- [ ] 取消任务：PID→PGID→SIGTERM→SIGKILL，远端目录清理
- [ ] 删除任务：清理 artifacts / 远端目录 / 日志 / 记录
- [ ] 日志实时滚动显示
- [ ] 日志下载文件名格式 `{task_id}.log`
- [ ] 结果文件回收与下载

## 3. Apptainer 验收

- [ ] .sif 文件选择
- [ ] 单台分发（SFTP 上传到 `$HOME/hpcdeploy/apptainer/`）
- [ ] 批量分发（多线程并发）
- [ ] `overwrite=true` 时覆盖已存在文件
- [ ] `overwrite=false` 时跳过已存在文件
- [ ] **不执行 `apptainer run` / `apptainer exec`**
- [ ] 不上传 `.sh` / `.py` 文件

## 4. 清理中心验收

- [ ] 本地结果文件按 task 目录聚合展示
- [ ] 本地结果文件支持批量删除
- [ ] Apptainer 镜像目录只读查看（不可删除）
- [ ] 远端临时目录按在线服务器扫描
- [ ] 远端清理 target 白名单：只允许 `tasks` / `downloads` / `tmp`
- [ ] **不清理 `$HOME/hpcdeploy/apptainer`**
- [ ] 不清理系统目录（`/root`、`/home`、`/tmp`、`/opt`、`/usr`、`/etc`）

## 5. 审计日志验收

- [ ] 任务创建有记录
- [ ] 任务删除有记录
- [ ] 清理操作有记录
- [ ] 设置保存有记录
- [ ] 服务器更新有记录
- [ ] **不记录密钥内容**

## 6. 诊断验收

- [ ] GPU/CUDA 错误识别
- [ ] SSH 连接错误识别
- [ ] 磁盘空间不足识别
- [ ] 远端路径错误识别
- [ ] evidence 不泄露敏感字段

## 7. 安全验收

- [ ] `command` 参数被后端拒绝
- [ ] `raw shell` 参数被后端拒绝
- [ ] `remote_path` 参数被后端拒绝
- [ ] 路径穿越（`../`）被后端拒绝
- [ ] **非法标签（含特殊字符、超长、超量）被拒绝返回 400**
- [ ] 非 `.sif` 文件上传被拒绝
- [ ] `/api/ssh-keys` 不返回私钥/公钥内容
- [ ] 部署公钥只写远端 `~/.ssh/authorized_keys`
- [ ] 不覆盖 `authorized_keys`
- [ ] 不修改 `sshd_config`
- [ ] 不重启 `sshd`

## 8. 仪表盘验收

- [ ] 显示服务器总数/在线/离线
- [ ] 显示任务按状态分类统计
- [ ] 显示结果文件归档目录数量和占用空间
- [ ] 8 个快捷操作按钮导航正确
- [ ] 最近任务行点击跳转任务历史
- [ ] 结果文件目录树正确展示

## 9. 非阻塞问题记录

### 9.1 clipboard.writeText 在非 HTTPS 环境降级
TaskHistory.vue 中 `copyArtifactDir` 使用 `navigator.clipboard.writeText()`，需要安全上下文。开发环境（localhost）没问题，生产需要 HTTPS。

### 9.2 旧 PENDING 任务需要人工清理
同服务器防重复提交把旧 PENDING 也视为未完成任务，可通过 SQLite 手动修正为 FAILED。

### 9.3 回收失败未更新 error_message
artifact_collector.py 回收失败只写 ERROR 日志，没有更新 task.error_message。

## MVP 验收通过标准

- [ ] 所有"安全验收"项通过
- [ ] 各模块核心功能验收项通过
- [ ] 后端 `compileall` 通过
- [ ] 前端 `npm run build` 通过
