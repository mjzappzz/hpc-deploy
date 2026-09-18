## Why

线上观察显示煤球主体对比度偏弱，状态效果会残留，纸条与气泡存在重叠风险，多个动画层也可能同时争用 `transform`。需要一次聚焦的可视性和状态收敛修复，让煤球更像清晰可辨的宠物，同时保持低干扰与低资源。

## What Changes

- 提高煤球主体与眼睛/脚的可辨识度，收敛毛边模糊和阴影。
- 为监控拟态状态增加自动过期和危险 UI 立即清理。
- 建立主动作互斥，点击、信号、果冻和终态动画不叠加。
- 将页面道具和状态纸条改为稳定的 CSS/内联视觉，避免 emoji 字体差异和遮挡。
- 为煤球及气泡补充 CJK 字体 fallback，并覆盖减少动效与移动端尺寸。

## Capabilities

### New Capabilities

<!-- 无新增独立能力。 -->

### Modified Capabilities

- `operator-companion`: 修正煤球可见性、状态生命周期、动画互斥、道具呈现与字体兼容契约。

## Impact

- 影响 `frontend/src/components/AppCritters.vue`、`frontend/src/utils/companionContext.ts` 及相关源码/浏览器测试。
- 同步更新 `docs/fun-principles.md`、`docs/progress.md`。
- 不新增后端 API、轮询、WebSocket、第三方依赖或持久化数据。
