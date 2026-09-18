## Why

当前煤球悬停时主要触发一次回应，鼠标快速移入移出缺少连续、可感知的宠物反馈。增加果冻式 squash-and-stretch 动作，让煤球每次进入都能产生轻快的“Duang”反应，同时保持文案、业务事件和危险 UI 的现有边界。

## What Changes

- 将每次鼠标进入煤球的反馈改为可重复播放的果冻物理动作：压扁、拉伸、过冲后回弹。
- 悬停/聚焦动作与说话气泡解耦；悬停只表达宠物反应，点击/触屏轻触继续负责互动吐槽。
- 快速鼠标进出时允许每次进入重新触发动作，不受自动独白或手动说话冷却影响；减少动效时不播放形变。
- 保持固定右下安全位、单实例、无新增依赖和失败/告警静默规则。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `operator-companion`: 增加可重复的悬停果冻动作，并明确悬停动作与手动文案冷却的交互边界。

## Impact

- 影响 `frontend/src/components/AppCritters.vue` 及其源码/浏览器回归测试；必要时同步 `docs/fun-principles.md` 与 `docs/progress.md`。
- 不影响后端 API、任务执行、权限、数据库、Nginx 或部署依赖。
