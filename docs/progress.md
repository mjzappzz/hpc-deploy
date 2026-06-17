# HPCDeploy 项目进度记录

## 当前阶段

当前进行到：阶段 8B：远程目录创建与文件上传

当前主线已从“复杂 params_schema 平台”收敛为：

```text
脚本知识库
↓
任务执行器
↓
任务历史 / 结果回收
```

当前下一步：

```text
阶段 8B：远程目录创建与文件上传
```

## 已完成阶段

### 阶段 1：项目骨架初始化
- 前端 Vue3 + Vite + Element Plus 已建立
- 后端 FastAPI 已建立
- /api/health 可用
- 前后端开发模式可启动

### 阶段 2：数据库模型与基础 API
- 已实现 servers、scripts、tasks、task_logs 表
- scripts 表包含 params_schema
- tasks 表包含 params
- 已实现基础 CRUD API

### 阶段 3：前端基础页面
- 已实现 Dashboard
- 已实现服务器管理
- 已实现脚本管理
- 已实现任务执行页面占位
- 已实现任务历史页面

### 阶段 4：SSH 连通性测试
- 已实现 POST /api/servers/{server_id}/test
- 前端服务器管理页已有“测试 SSH”按钮
- 能更新 online/offline 状态
- 未做真实测试节点完整成功链路验证

### 阶段 5：服务器信息探测
- 已实现 POST /api/servers/{server_id}/detect
- 已实现服务器 OS / CPU / 内存 / GPU / 磁盘 / 网络信息探测
- 前端已有“探测信息”按钮和详情抽屉
- 服务器管理主表格已做摘要展示和 UI 优化

### 阶段 6：脚本白名单与脚本管理
- scripts 表作为脚本白名单表
- 已实现脚本路径安全校验
- 已实现 params_schema JSON 校验
- 已实现 POST /api/scripts/{script_id}/validate
- 已实现 GET /api/scripts/files 自动扫描 backend/scripts/
- 前端脚本文件可下拉选择，不再手动填写远程路径

## 当前定位调整

阶段 7 不再继续朝“复杂通用参数平台”推进。

新的主线方向：
- 原“脚本管理”收敛为“脚本知识库”
- 任务执行页只保留最少参数输入
- 任务历史后续承担日志与结果回收展示
- 真实远程执行留到阶段 8
- 结果回收留到阶段 9

## 当前保留内容

继续保留：

```text
1. 服务器管理
2. SSH 测试
3. 服务器探测
4. scripts 表和基础 API
5. 脚本路径安全校验
6. 脚本文件扫描
7. 任务历史基础结构
```

## 当前弱化内容

以下内容不再作为当前主线：

```text
1. params_schema
2. validate-params
3. 通用参数 Schema
4. OpenMPI / OneAPI / CUDA 参数模板
```

## 阶段 7A：脚本知识库改造

当前阶段目标：

```text
1. 原“脚本管理”改名为“脚本知识库”
2. 当前固定目录结构：
   - backend/scripts/mpi
   - backend/scripts/stress
   - backend/scripts/test
   - backend/apptainer
3. 目录含义：
   - mpi：编译环境相关脚本，包括基础编译器、OneAPI、OpenMPI、AOCC/AOCL、基础依赖安装脚本
   - stress：压测脚本
   - test：测试脚本
   - apptainer：Apptainer 容器文件，主要是 .sif
4. 支持扫描上述固定目录
5. 支持上传脚本文件
6. 支持下载脚本文件
7. 支持删除脚本文件
8. 支持预览文本脚本内容
9. .sh / .py / .txt / .md 可以预览
10. .sif 等二进制文件只显示文件信息，不预览内容
11. 普通用户界面不显示 params_schema / JSON
```

当前阶段已收敛：

```text
1. 旧目录 compiler / cuda / oneapi 已归并到 mpi 语义
2. 旧目录 containers 已改为 backend/apptainer
3. 前端分类页签调整为：
   - 全部
   - 编译环境
   - 压测脚本
   - Apptainer 容器
   - 测试脚本
4. 预览弹窗需保持底部按钮始终可见
```

阶段 7A 状态：

```text
已完成
```

## 阶段 7B：任务执行页简化

当前阶段目标：

```text
1. 选择目标服务器
2. 选择脚本知识库中的文件
3. 根据脚本类型显示极少参数
4. 压测脚本只填写压测时长：小时 / 分钟 / 秒
5. 压测脚本参数后续转成秒数，例如：
   ./cpu_mem_stress_report.sh 14400
6. 基础编译器脚本无需参数
7. Apptainer 容器后期只复制到远程指定位置，不执行
8. 后续阶段再逐步放开真实执行
```

当前实现边界：

```text
1. 任务执行页只做：
   - 服务器选择
   - 任务类型选择
   - 知识库文件选择
   - 按类型过滤知识库文件
   - 参数输入
   - 按类型显示远程工作目录模板
   - 命令预览
2. 当前页面已经进入任务创建与执行阶段
3. 执行能力按任务类型分阶段放开
4. 不做 WebSocket
5. 不做 Server Lock
6. 不做 Timeout
7. 不做结果回收
```

当前页面行为：

```text
1. 任务类型选项：
   - 编译环境 → mpi
   - 压测脚本 → stress
   - Apptainer 容器 → apptainer
   - 测试脚本 → test
2. 远程工作目录模板：
   - 编译环境：~/hpcdeploy/tasks/mpi/{datetime}
   - 压测脚本：~/hpcdeploy/tasks/stress/{datetime}
   - 测试脚本：~/hpcdeploy/tasks/test/{datetime}
   - Apptainer 容器：~/hpcdeploy/apptainer/
3. 当前只有 test 类型会真实执行，其他类型仍只上传不执行
```

阶段 7B 状态：

```text
已完成
```

## 阶段 8A：任务模型收口与任务创建

当前阶段目标：

```text
1. 前端点击“开始执行”
2. POST /api/tasks/run
3. 后端校验 server_id / task_type / file_path / duration_seconds
4. 创建 tasks 记录
5. 状态为 PENDING
6. 返回 task_id
7. 前端跳转到任务历史
8. 任务历史能看到该任务
```

当前实现边界：

```text
1. 创建 tasks 记录并返回 task_id
2. 只定义任务模型和任务历史展示
3. 真实 SSH 上传与执行在后续阶段实现
4. 不做 WebSocket
5. 不做 Server Lock
6. 不做 Timeout
7. 不做结果回收
```

阶段 8A 状态：

```text
已完成
```

## 阶段 8B：远程目录创建与文件上传

当前阶段目标：

```text
1. 创建任务后启动后台 8B 流程
2. SSH 连接目标服务器
3. 创建远程工作目录
4. 上传知识库文件
5. 对 .sh / .py 执行 chmod +x
6. 写入 task_logs
7. 任务状态更新为 SUCCESS 或 FAILED
```

当前实现边界：

```text
1. 完成 SSH 连接、远程 HOME 识别、目录创建、上传、chmod
2. 任务历史可以看到 CONNECTING / PREPARING / UPLOADING / SUCCESS / FAILED
3. 不执行业务脚本
4. 不做 WebSocket
5. 不做 Server Lock
6. 不做 Timeout
7. 不做结果回收
```

阶段 8B 状态：

```text
已完成
```

## 阶段 8C：真实执行 test 脚本并保存日志

当前阶段目标：

```text
1. 在 8B 上传成功后，仅对 test 类型进入执行阶段
2. 执行命令固定为：bash ./脚本名
3. 执行目录固定为 remote_work_dir
4. 保存 stdout / stderr 到 task_logs
5. 保存 exit_code、end_time、SUCCESS / FAILED
6. stress / mpi / apptainer 继续只上传不执行
```

当前实现边界：

```text
1. 仅开放 test 类型真实执行
2. stress 仍只上传，不执行
3. mpi 仍只上传，不执行
4. apptainer 仍只复制到远程目录，不执行
5. 不做 WebSocket
6. 不做 Server Lock
7. 不做 Timeout
8. 不做结果回收
```

阶段 8C 状态：

```text
已完成
```

## 阶段 8D：放开 stress 压测脚本短时间执行

当前阶段目标：

```text
1. 在 8B 上传成功后，允许 stress 类型进入执行阶段
2. 执行命令固定为：./脚本名 duration_seconds
3. duration_seconds 仅允许使用后端校验后的任务参数
4. 第一版限制最大 3600 秒
5. 保存 stdout / stderr / exit_code 到 task_logs 和 tasks
6. mpi / apptainer 继续只上传不执行
```

当前实现边界：

```text
1. 仅开放 stress 短时执行和 test 执行
2. stress 最长 3600 秒
3. mpi 仍只上传，不执行
4. apptainer 仍只复制到远程目录，不执行
5. 不做 WebSocket
6. 不做 Server Lock
7. 不做 Timeout
8. 不做结果回收
```

阶段 8D 状态：

```text
已完成
```

## 严格禁止

禁止实现：
- WebSocket
- Server Lock
- Timeout
- mpi / apptainer 真实执行
- AI 助手
- 复杂编排

## 下次继续重点

下一步优先做：

```text
继续收口阶段 8，补充 stress 执行后的错误展示与日志验证，再决定是否进入阶段 9 结果回收
```

后续开发必须遵守：

```text
1. 继续按阶段边界推进
2. 先收好 test / stress 执行链路，再逐步放开 mpi
3. 结果回收先做最小可用，不提前引入 WebSocket / Server Lock / Timeout
```
