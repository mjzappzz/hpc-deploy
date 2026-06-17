# HPCDeploy 阶段开发计划

版本：v2.0  
用途：给后续开发按阶段推进使用  
原则：先收敛主线，再逐步扩展；每个阶段只解决当前明确范围内的问题。

---

## 0. 当前主线

HPCDeploy 当前主线已从“复杂通用 params_schema 平台”收敛为：

```text
脚本知识库
↓
任务执行器
↓
任务历史 / 结果回收
```

当前聚焦四类知识库目录：

```text
backend/scripts/mpi
backend/scripts/stress
backend/scripts/test
backend/apptainer
```

当前不再把通用参数平台作为主线目标。参数只保留最少的、与任务执行直接相关的输入。

---

## 1. 开发总原则

开发顺序：

```text
先完成脚本知识库收敛
↓
再简化任务执行页
↓
再补真实远程执行
↓
再做结果回收
↓
最后补实时日志、并发控制和部署强化
```

执行原则：

```text
1. 当前阶段不做复杂编排
2. 当前阶段不做 AI 助手能力
3. 当前阶段不做通用参数 Schema 平台
4. 当前阶段不做远程上传和真实执行
5. 当前阶段不做 WebSocket
6. 当前阶段不做 Server Lock / Timeout
7. 所有新增功能优先服务三大主线模块
```

---

## 2. 已完成阶段

```text
阶段 1：项目骨架初始化
阶段 2：数据库模型与基础 API
阶段 3：前端基础页面
阶段 4：SSH 连通性测试
阶段 5：服务器信息探测
阶段 6：脚本白名单与脚本管理基础能力
```

---

## 3. 新阶段划分

### 阶段 7A：脚本知识库改造

目标：把原“脚本管理”收敛为“脚本知识库”。

范围：

```text
1. 原“脚本管理”改名为“脚本知识库”
2. 固定目录结构：
   - backend/scripts/mpi
   - backend/scripts/stress
   - backend/scripts/test
   - backend/apptainer
3. 目录含义：
   - mpi：编译环境相关脚本，包括基础编译器、OneAPI、OpenMPI、AOCC/AOCL、基础依赖安装脚本
   - 压测脚本
   - test：测试脚本，例如 hello.sh
   - apptainer：Apptainer 容器文件，主要是 .sif
4. 支持扫描上述固定目录
5. 支持上传脚本文件
6. 支持下载脚本文件
7. 支持删除脚本文件
8. 支持预览文本脚本内容
9. .sh / .py / .txt / .md 等文本文件可以预览
10. .sif 等二进制文件只显示文件信息，不预览内容
11. 普通用户界面不显示 params_schema / JSON
```

明确不做：

```text
1. 不实现远程上传
2. 不实现远程执行
3. 不实现任务调度
```

验收重点：

```text
1. 分类清晰
2. 文件操作闭环清晰
3. 文本 / 二进制文件行为区分明确
4. 预览弹窗代码区单独滚动、底部按钮固定可见
5. 用户界面不再暴露复杂 JSON
```

### 阶段 7B：任务执行页简化

目标：把任务执行页收敛为“任务创建前参数确认页”。

范围：

```text
1. 选择目标服务器
2. 选择脚本知识库中的文件
3. 根据脚本类型显示极少参数
4. 压测脚本只填写压测时长：小时 / 分钟 / 秒
5. 压测脚本执行参数后续转成秒数，例如：
   ./cpu_mem_stress_report.sh 14400
6. 基础编译器脚本无需参数
7. Apptainer 容器后期只复制到远程指定位置，不执行
8. 执行按钮仍然禁用，真实执行留到阶段 8
```

明确不做：

```text
1. 不做真实执行
2. 不做远程上传
3. 不创建真实任务
4. 不做 WebSocket
```

验收重点：

```text
1. 参数展示逻辑足够简单
2. 压测时长能稳定转为秒数
3. 不再依赖复杂 params_schema 驱动页面
```

### 阶段 8：真实远程执行

目标：开始补最小可用的单任务远程执行链路。

范围：

```text
1. 创建任务记录
2. 在远程服务器创建固定工作目录
3. 默认目录：~/hpcdeploy/tasks/{task_id}
4. 上传脚本到远程目录
5. chmod +x
6. 按脚本类型生成固定命令
7. 执行脚本
8. 保存 stdout / stderr
9. 更新任务状态
10. 仍然不做复杂编排
```

### 阶段 9：任务结果回收

目标：把远程执行产物回收到平台本地，并纳入任务历史。

范围：

```text
1. 任务完成后从远程目录回收结果文件
2. 压测报告包从远程拉回平台本地
3. 本地保存到 backend/data/artifacts/{task_id}/
4. 任务历史页提供下载按钮
5. 支持查看日志和结果文件
```

### 阶段 10：实时日志与体验增强

目标：在主链路稳定后补用户体验。

范围：

```text
1. WebSocket 实时日志
2. 更好的任务状态展示
3. 任务取消
4. Timeout
5. Server Lock
```

### 阶段 11：部署与安全增强

目标：补部署与运行安全。

范围：

```text
1. Docker Compose
2. Nginx
3. SSH key 权限检查
4. 访问控制
5. 日志保留策略
```

---

## 4. 当前阶段禁止项

当前在阶段 7A / 7B 期间，明确禁止：

```text
1. 不做远程 SSH 上传
2. 不做真实脚本执行
3. 不创建真实任务
4. 不做 WebSocket
5. 不做 Server Lock
6. 不做 Timeout
7. 不做 AI 助手
8. 不做复杂编排
```

---

## 5. 当前开发验证重点

阶段 7A 验证重点：

```text
1. 脚本知识库分类正确
2. 上传 / 下载 / 删除闭环正常
3. 文本脚本可预览
4. 二进制文件只显示元信息
5. UI 不出现 params_schema / JSON
```

阶段 7B 验证重点：

```text
1. 能正确选择服务器和脚本
2. 压测时长录入正确
3. 秒数换算逻辑正确
4. 非压测脚本不出现无意义参数表单
5. 执行按钮保持禁用
```

---

## 6. 当前阶段结束后的进入条件

只有以下条件满足后，才进入阶段 8：

```text
1. 脚本知识库功能稳定
2. 任务执行页参数逻辑稳定
3. 任务类型边界清晰
4. 文档已同步更新
```

echo "[INFO] test script started"
echo "[INFO] hostname: $(hostname)"
echo "[INFO] user: $(whoami)"
echo "[INFO] date: $(date)"

for i in {1..10}; do
  echo "[INFO] running step $i"
  sleep 1
done

echo "[OK] test script finished"
```

验证目标：

```text
1. 前端能选择测试服务器
2. 前端能选择 hello.sh 测试脚本
3. 后端能上传脚本到 /tmp/hpc-control-panel/{task_id}/
4. 远程服务器能执行脚本
5. 前端能实时看到日志逐行输出
6. 任务最终状态为 SUCCESS
7. task_logs 表中能查到日志
```

---

## 脚本参数验证

再用参数测试脚本验证 params_schema 和 params。

测试脚本：

```bash
#!/usr/bin/env bash
set -euo pipefail

INSTALL_PREFIX=""
DURATION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      INSTALL_PREFIX="$2"
      shift 2
      ;;
    --duration)
      DURATION="$2"
      shift 2
      ;;
    *)
      echo "[ERROR] unknown argument: $1"
      exit 1
      ;;
  esac
done

echo "[INFO] prefix=${INSTALL_PREFIX}"
echo "[INFO] duration=${DURATION}"
echo "[OK] params test finished"
```

前端填写：

```text
安装路径：/opt/test
压测时长：60
```

验证目标：

```text
1. 前端根据 params_schema 生成表单
2. 后端能校验 params
3. 后端能把 params 转成安全参数
4. 远程日志能看到 prefix=/opt/test
5. 远程日志能看到 duration=60
6. 非法参数会被拒绝
```

---

## 真实脚本验证顺序

等 hello.sh 和参数测试脚本都通过后，再接入真实脚本。

推荐顺序：

```text
1. 服务器探测脚本
2. 基础编译器 / 编译工具安装脚本
3. 短时间 Stress 压测脚本
4. OpenMPI 编译安装脚本
5. OneAPI 安装脚本
6. CUDA Toolkit 安装脚本
7. GPU Driver 安装脚本
```

GPU Driver 最后验证，因为它可能涉及：

```text
1. 内核模块
2. nouveau 禁用
3. DKMS
4. 重启
5. 驱动版本冲突
6. 图形界面影响
```

---

## Docker 部署验证放到最后

只有当以下功能在开发模式下全部通过后，再进行 Docker 验证：

```text
1. 前端页面正常
2. 后端 API 正常
3. 数据库读写正常
4. SSH 测试正常
5. 脚本上传正常
6. 脚本执行正常
7. 参数传递正常
8. WebSocket 实时日志正常
9. 任务状态正常
10. 任务历史正常
```

Docker 验证目标不是调业务逻辑，而是验证部署环境：

```text
1. frontend 容器能启动
2. backend 容器能启动
3. 数据库容器能启动
4. Nginx 能访问前端
5. Nginx 能反代 /api
6. Nginx 能反代 /ws
7. 后端容器能读取 SSH 私钥
8. 后端容器能访问目标服务器 22 端口
9. 数据库数据能持久化
```

---

## Docker Compose 验证命令

```bash
docker compose up -d
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

验证 API：

```bash
curl http://localhost/api/health
curl http://localhost/api/servers
```

如果后端单独暴露 8000：

```bash
curl http://localhost:8000/docs
```

---

## Docker 阶段常见问题

```text
1. 容器内找不到 SSH 私钥
2. SSH 私钥权限不是 600
3. 容器无法访问目标服务器网络
4. Nginx 没有正确代理 WebSocket
5. 前端 API 地址仍然指向 localhost:8000
6. SQLite 数据库没有挂载 volume，容器重启数据丢失
7. scripts 目录没有挂载或路径错误
```

---

## 最终推荐结论

推荐方式：

```text
开发阶段：本地开发模式验证
最终阶段：Docker Compose 部署验证
```

不推荐方式：

```text
一开始所有东西都放 Docker 里边开发边调
```

原因：

```text
Docker 适合交付部署，不适合早期频繁排错。
```

本项目最稳验证路线：

```text
前端开发模式跑通
↓
后端开发模式跑通
↓
SQLite 开发模式跑通
↓
SSH 测试服务器跑通
↓
hello.sh 无害脚本跑通
↓
参数脚本跑通
↓
真实低风险脚本跑通
↓
真实高风险脚本跑通
↓
Docker Compose 部署验证
```


---

# 阶段 1：项目骨架初始化

## 目标

建立前后端基础项目结构，能正常启动。

## 开发内容

### 前端

```text
1. 创建 Vue3 + Vite 项目
2. 安装 Element Plus
3. 安装 Vue Router
4. 安装 Pinia
5. 安装 Axios
6. 建立基础 Layout：左侧菜单 + 顶部栏 + 内容区
```

### 后端

```text
1. 创建 FastAPI 项目
2. 安装 Uvicorn
3. 安装 SQLAlchemy
4. 安装 Pydantic
5. 安装 Paramiko
6. 创建 app/api、app/core、app/models、app/schemas、app/db 目录
```

### 数据库

```text
1. 第一阶段使用 SQLite
2. 建立 database.py
3. 能初始化数据库文件
```

## 验收标准

```text
1. 前端 npm run dev 能启动
2. 后端 uvicorn main:app --reload 能启动
3. 浏览器能访问前端页面
4. /docs 能打开 FastAPI Swagger
5. 数据库能生成 SQLite 文件
```

## 给 AI 的提示词

```text
请先初始化项目骨架，不要实现复杂业务。前端使用 Vue3 + Vite + Element Plus + Pinia + Vue Router + Axios。后端使用 FastAPI + SQLAlchemy + SQLite + Paramiko。只需要让前端和后端能正常启动，并建立清晰目录结构。
```

---

# 阶段 2：数据库模型与基础 API

## 目标

先把核心数据结构建好，能通过 API 管理服务器、脚本、任务记录。

## 开发内容

### 数据库表

必须实现：

```text
1. servers
2. scripts
3. tasks
4. task_logs
```

### servers 表字段

```text
id
name
host
port
username
auth_type
key_path
status
os_info
gpu_info
created_at
updated_at
```

### scripts 表字段

```text
id
name
category
version
file_path
description
enabled
dangerous
params_schema
created_at
updated_at
```

### tasks 表字段

```text
id
task_id
server_id
script_id
status
params
start_time
end_time
exit_code
error_message
created_at
updated_at
```

### task_logs 表字段

```text
id
task_id
level
message
created_at
```

### API

实现：

```text
GET    /api/servers
POST   /api/servers
GET    /api/servers/{server_id}
PUT    /api/servers/{server_id}
DELETE /api/servers/{server_id}

GET    /api/scripts
POST   /api/scripts
GET    /api/scripts/{script_id}
PUT    /api/scripts/{script_id}
DELETE /api/scripts/{script_id}

GET    /api/tasks
GET    /api/tasks/{task_id}
GET    /api/tasks/{task_id}/logs
```

## 验收标准

```text
1. 能新增服务器
2. 能查看服务器列表
3. 能新增脚本元信息
4. scripts 表支持 params_schema 字段
5. tasks 表支持 params 字段
6. Swagger 上能测试所有基础 API
```

## 给 AI 的提示词

```text
请实现数据库模型和基础 CRUD API。重点是 servers、scripts、tasks、task_logs 四张表。scripts 表必须有 params_schema 字段，tasks 表必须有 params 字段。暂时不要实现 SSH 执行，只做数据结构和 API。
```

---

# 阶段 3：前端基础页面

## 目标

先做能操作的基础页面，不追求最终 UI 效果。

## 开发内容

### 页面

实现以下页面：

```text
1. Dashboard.vue
2. Servers.vue
3. Scripts.vue
4. TaskRunner.vue
5. TaskHistory.vue
```

### 组件

实现以下组件：

```text
1. ServerTable.vue
2. ScriptTable.vue
3. TaskCard.vue
4. StatusTag.vue
5. LogViewer.vue
```

### 功能

```text
1. 服务器列表展示
2. 新增服务器表单
3. 脚本列表展示
4. 新增脚本元信息
5. 任务历史展示
```

## 验收标准

```text
1. 能在前端新增服务器
2. 能看到服务器列表
3. 能在前端新增脚本元信息
4. 能看到脚本列表
5. 页面之间路由正常
```

## 给 AI 的提示词

```text
请实现前端基础页面，先不要追求复杂视觉效果。需要有左侧菜单、顶部栏、服务器管理、脚本管理、任务执行、任务历史页面。所有 API 请求封装到 src/api，不要在 Vue 页面里直接写 axios 地址。
```

---

# 阶段 4：SSH 连通性测试

## 目标

先实现最基础的远程服务器连接能力。

## 开发内容

### 后端

实现：

```text
POST /api/servers/{server_id}/test
```

逻辑：

```text
1. 根据 server_id 查询服务器
2. 使用 Paramiko SSH Key 登录
3. 执行 hostname
4. 执行 uname -a
5. 返回成功 / 失败
6. 更新 servers.status
```

### 前端

服务器管理页面增加按钮：

```text
测试 SSH
```

点击后显示：

```text
成功 / 失败
耗时
错误信息
```

## 验收标准

```text
1. 能通过页面点击测试 SSH
2. SSH 成功时服务器状态变为 online
3. SSH 失败时服务器状态变为 offline
4. 能显示失败原因
```

## 给 AI 的提示词

```text
请实现 SSH 连通性测试功能。后端使用 Paramiko，根据服务器表里的 host、port、username、key_path 登录目标服务器，执行 hostname 和 uname -a。前端服务器管理页面增加“测试 SSH”按钮，并显示测试结果。
```

---

# 阶段 5：服务器信息探测

## 目标

获取目标服务器基础环境信息，为后续安装任务做准备。

## 开发内容

### 后端 API

实现：

```text
POST /api/servers/{server_id}/detect
```

执行命令：

```bash
hostname
cat /etc/os-release
uname -r
lscpu | head
free -h
df -h
nvidia-smi || true
which nvcc || true
nvcc --version || true
which mpirun || true
mpirun --version || true
gcc --version || true
cmake --version || true
```

### 保存结果

更新：

```text
servers.os_info
servers.gpu_info
servers.status
```

### 前端

服务器管理页面增加：

```text
探测信息
刷新信息
服务器详情面板
```

## 验收标准

```text
1. 能探测 OS 信息
2. 能探测 GPU 信息
3. 能探测 CUDA / OpenMPI / GCC 状态
4. 前端能显示探测结果
```

## 给 AI 的提示词

```text
请实现服务器信息探测功能。通过 SSH 执行 hostname、os-release、uname、lscpu、free、df、nvidia-smi、nvcc、mpirun、gcc、cmake 等命令。命令失败不能导致整个探测失败，使用 || true。前端显示探测结果。
```

---

# 阶段 6：脚本白名单与脚本上传

## 目标

实现安全脚本执行的前置能力：只允许执行白名单脚本，并上传到远程服务器临时目录。

## 开发内容

### 后端规则

```text
1. 前端只能传 script_id
2. 后端根据 script_id 查询 scripts 表
3. 只有 enabled=true 的脚本允许执行
4. 后端读取本地 file_path
5. 使用 SFTP 上传到目标服务器
6. 远程目录：/tmp/hpc-control-panel/{task_id}/
```

### 禁止

```text
1. 禁止前端传 command
2. 禁止前端传脚本路径
3. 禁止后端执行用户输入的任意命令
```

## 验收标准

```text
1. 能根据 script_id 找到本地脚本
2. 能通过 SFTP 上传脚本到远程服务器
3. 远程服务器能看到 /tmp/hpc-control-panel/{task_id}/script.sh
4. 非白名单脚本不能执行
```

## 给 AI 的提示词

```text
请实现脚本白名单和 SFTP 上传能力。前端只能传 script_id，后端根据 scripts 表查询 file_path，确认 enabled=true 后，把脚本上传到目标服务器 /tmp/hpc-control-panel/{task_id}/script.sh。禁止执行任意 command。
```

---

# 阶段 7：脚本参数机制

## 目标

支持安装路径、版本、压测时长、GPU 编号等参数。

## 开发内容

### 后端

实现：

```text
1. scripts.params_schema 定义参数模板
2. tasks.params 保存实际执行参数
3. 后端根据 params_schema 校验 params
4. 只允许传 schema 里声明过的参数
5. 校验类型：string / number / select / boolean / path
6. 生成安全命令行参数
```

### 前端

TaskRunner 页面：

```text
1. 选择脚本后读取 params_schema
2. 自动生成表单
3. 填写参数
4. 提交 params
```

### 示例参数

OpenMPI：

```json
{
  "version": "4.1.6",
  "install_prefix": "/opt/openmpi-4.1.6-gcc11",
  "compiler": "gcc",
  "make_jobs": 32
}
```

Stress：

```json
{
  "duration": 3600,
  "gpu_ids": "0,1,2,3",
  "output_dir": "/tmp/stress-report"
}
```

## 验收标准

```text
1. scripts 表能保存 params_schema
2. 前端能根据 params_schema 生成表单
3. 后端能校验 params
4. tasks 表能保存本次 params
5. 非法参数会被拒绝
```

## 给 AI 的提示词

```text
请实现脚本参数机制。scripts.params_schema 使用 JSON 定义参数模板，tasks.params 保存执行参数。前端根据 params_schema 动态生成参数表单。后端必须校验参数，只允许 schema 中声明的参数，禁止命令注入。支持 string、number、select、boolean、path 类型。
```

---

# 阶段 8：任务执行与状态机

## 目标

真正执行远程脚本，并保存任务状态。

## 开发内容

### API

实现：

```text
POST /api/tasks/run
POST /api/tasks/{task_id}/cancel
```

### 状态机

必须支持：

```text
PENDING
RUNNING
SUCCESS
FAILED
CANCELLED
TIMEOUT
```

### 执行流程

```text
1. 创建 task_id
2. 保存任务 PENDING
3. 校验服务器
4. 校验脚本
5. 校验参数
6. 上传脚本
7. 更新 RUNNING
8. SSH 执行脚本
9. 读取 exit_code
10. 更新 SUCCESS / FAILED / TIMEOUT
```

## 验收标准

```text
1. 能通过 API 创建任务
2. 任务状态从 PENDING 到 RUNNING
3. 成功脚本最终变成 SUCCESS
4. 失败脚本最终变成 FAILED
5. 任务记录里能看到 exit_code 和 error_message
```

## 给 AI 的提示词

```text
请实现任务执行和状态机。POST /api/tasks/run 创建任务，后台通过 SSH 执行远程脚本。任务状态必须包含 PENDING、RUNNING、SUCCESS、FAILED、CANCELLED、TIMEOUT。执行完成后保存 exit_code、error_message、start_time、end_time。
```

---

# 阶段 9：实时日志 WebSocket

## 目标

前端能实时看到远程脚本输出。

## 开发内容

### 后端

实现：

```text
/ws/tasks/{task_id}/logs
```

日志来源：

```text
1. SSH stdout
2. SSH stderr
3. 后端状态变更
```

日志处理：

```text
1. 写入 task_logs 表
2. 推送给 WebSocket 客户端
3. 前端断开后不影响任务继续执行
```

### 前端

LogViewer.vue：

```text
1. 连接 WebSocket
2. 实时追加日志
3. 支持自动滚动
4. 支持清空显示
5. 支持按 level 显示颜色
```

## 验收标准

```text
1. 执行任务时前端能看到实时日志
2. stdout 和 stderr 都能显示
3. 日志能保存到 task_logs
4. 刷新页面后能通过历史日志查看
```

## 给 AI 的提示词

```text
请实现 WebSocket 实时日志。后端在执行 SSH 脚本时实时读取 stdout/stderr，写入 task_logs 表，同时推送到 /ws/tasks/{task_id}/logs。前端 LogViewer 组件实时显示日志并自动滚动。
```

---

# 阶段 10：Server Lock 与超时机制

## 目标

防止同一服务器同时执行多个高风险任务，避免安装冲突。

## 开发内容

### Server Lock

规则：

```text
1. 同一服务器默认同时只能运行一个任务
2. 不同服务器可以并行运行
3. GPU Driver / CUDA / OneAPI / OpenMPI / Stress 默认都需要 lock
4. 任务结束后释放 lock
5. 任务失败或超时也必须释放 lock
```

### Timeout

默认超时建议：

```text
普通检测任务：5 分钟
基础编译器安装：60 分钟
OpenMPI 编译安装：120 分钟
OneAPI 安装：120 分钟
GPU Driver / CUDA 安装：120 分钟
Stress 压测：用户参数 duration + 额外缓冲时间
```

## 验收标准

```text
1. 同一服务器运行任务时，不能再启动第二个任务
2. 不同服务器可以同时执行
3. 超时任务会变成 TIMEOUT
4. 超时后 server lock 会释放
```

## 给 AI 的提示词

```text
请实现 Server Lock 和 Timeout。默认同一台服务器同一时间只能运行一个任务。任务结束、失败、取消、超时都必须释放 lock。不同服务器可以并行。任务超时后状态改为 TIMEOUT。
```

---

# 阶段 11：第一阶段脚本模板接入

## 目标

把你自己的脚本接入系统，先接入少量稳定脚本。

## 第一批建议脚本

```text
1. compiler/install_base_tools.sh
2. mpi/install_openmpi_4_1_6.sh
3. oneapi/install_oneapi_2024.sh
4. cuda/install_gpu_driver.sh
5. cuda/install_cuda_12_8.sh
6. stress/gpu_burn.sh
7. stress/cpu_stress.sh
8. stress/memory_stress.sh
9. stress/disk_stress.sh
```

## 每个脚本必须具备

```text
1. set -euo pipefail
2. [INFO] [OK] [WARN] [ERROR] 日志格式
3. 参数解析
4. 基础幂等判断
5. 安装后验证
6. 明确 exit code
```

## 验收标准

```text
1. 每类至少一个脚本能通过平台执行
2. 参数能传入脚本
3. 日志能实时显示
4. 执行结果能保存
5. 失败时能看到原因
```

## 给 AI 的提示词

```text
请接入第一批脚本模板：基础编译器、OpenMPI、OneAPI、GPU Driver、CUDA、GPU Burn、CPU Stress、Memory Stress、Disk Stress。每个脚本必须支持参数、统一日志前缀、基础幂等判断和安装后验证。
```

---

# 阶段 12：前端体验优化

## 目标

在功能跑通后，再优化页面风格和交互体验。

## 优化内容

```text
1. 仪表盘统计卡片
2. 暗色主题
3. 服务器管理详情面板
4. 任务卡片样式
5. 日志颜色
6. 任务进度显示
7. 状态标签
8. 高风险确认弹窗
9. 最近任务面板
```

## 不要在前期做的事

```text
1. 不要一开始追求炫酷 UI
2. 不要为了卡片样式影响主流程开发
3. 不要大量做动画
4. 不要过早复杂化权限系统
```

## 验收标准

```text
1. 页面清晰
2. 操作路径短
3. 关键状态明显
4. 日志易读
5. 高风险任务有确认
```

## 给 AI 的提示词

```text
请在不改变后端接口和数据库结构的前提下，优化前端页面体验。重点优化仪表盘、服务器管理、任务执行、实时日志、任务历史。保持组件化，不要把所有逻辑写在一个 Vue 文件里。
```

---

# 阶段 13：部署与交付

## 目标

把系统部署成可实际使用的版本。

注意：Docker / Nginx 部署验证放在最后进行。前端、后端、数据库、SSH、脚本执行、WebSocket 日志这些主功能必须先在开发模式下验证通过，再进入 Docker Compose 验证。

## 开发环境

```text
frontend: npm run dev
backend: uvicorn main:app --reload
database: SQLite
```

## 生产环境建议

```text
1. 前端 npm run build
2. Nginx 托管前端静态文件
3. FastAPI 使用 Uvicorn/Gunicorn 运行
4. SQLite 可继续用，后续切 MySQL
5. SSH 私钥放在后端服务器本地
6. 配置文件使用 .env
```

## 必须检查

```text
1. SSH key 权限 chmod 600
2. 后端不能暴露私钥
3. Nginx 反代 API 和 WebSocket
4. 日志目录有写权限
5. scripts 目录路径正确
6. 数据库可写
```

## 验收标准

```text
1. 能通过浏览器访问系统
2. 能添加真实服务器
3. 能测试 SSH
4. 能执行真实脚本
5. 能看到实时日志
6. 能查看任务历史
```

## 给 AI 的提示词

```text
请整理部署配置。前端 build 后由 Nginx 提供静态文件，后端 FastAPI 使用 Uvicorn 运行。Nginx 需要反代 /api 和 /ws。使用 .env 管理配置。SSH 私钥只能保存在后端服务器本地，权限必须为 600。
```

---

# 推荐执行顺序总结

```text
阶段 1：项目骨架初始化
阶段 2：数据库模型与基础 API
阶段 3：前端基础页面
阶段 4：SSH 连通性测试
阶段 5：服务器信息探测
阶段 6：脚本白名单与脚本上传
阶段 7：脚本参数机制
阶段 8：任务执行与状态机
阶段 9：实时日志 WebSocket
阶段 10：Server Lock 与超时机制
阶段 11：第一阶段脚本模板接入
阶段 12：前端体验优化
阶段 13：部署与交付
```

---

# 每阶段交付要求

每个阶段完成后，AI 必须输出：

```text
1. 本阶段完成了什么
2. 修改了哪些文件
3. 如何运行
4. 如何测试
5. 当前已知问题
6. 下一阶段建议
```

---

# 每阶段禁止事项

```text
1. 禁止跳阶段一次性做完全部功能
2. 禁止前端直接执行 SSH
3. 禁止后端执行前端传入的任意命令
4. 禁止绕过 scripts 白名单
5. 禁止把 SSH 私钥返回给前端
6. 禁止没有日志的后台任务
7. 禁止任务没有状态
8. 禁止同一服务器无控制地并发安装
```

---

# 最终一句话

本项目开发必须按下面原则推进：

```text
先跑通主链路，再优化 UI，再扩展功能。
```

主链路是：

```text
服务器 → 脚本 → 参数 → SSH执行 → 实时日志 → 任务记录
```
