## Why

仪表盘已从 `/api/dashboard/summary` 获取控制器存储统计，但前端未将返回的 `storage` 写入页面状态，导致初始的 `0 B` 与 `unknown` 被显示为真实数据。由于未知状态也被当作非正常容量状态，操作员会收到错误的“控制器空间偏低”告警，无法据此判断是否需要清理或扩容。

## What Changes

- 将仪表盘接口返回的控制器存储统计同步到页面状态，展示实际可用空间、产物占用、SQLite 占用与最近清理结果。
- 始终显示已获得的控制器容量统计；仅在容量状态明确为 `warning` 或 `blocked` 时显示对应容量告警。
- 容量状态为 `unknown` 或存储统计暂不可用时，显示“容量统计暂不可用”，不将默认数值伪装为统计结果或低空间告警。
- 保持现有 `10 GiB` 告警阈值、`5 GiB` 极限压测阻断阈值及后端 API 契约不变。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `runtime-data-lifecycle`: 控制器容量状态在仪表盘上必须忠实展示；未知状态不得触发低空间告警。

## Impact

- 影响 `frontend/src/views/Dashboard.vue` 的仪表盘状态同步和告警呈现。
- 为该页面补充回归测试，覆盖实际存储数据回填与 `unknown` 状态不告警。
- 不修改后端统计逻辑、容量阈值、任务提交阻断条件、部署配置或外部 API。
