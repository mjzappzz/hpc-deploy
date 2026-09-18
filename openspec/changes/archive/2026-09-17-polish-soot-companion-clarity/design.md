## Context

当前煤球集中在 `AppCritters.vue`，使用 CSS 多 class 动画、上下文事件和危险 UI `MutationObserver`。线上截图显示主体对比度、状态清理和多文字层需要收敛。

## Goals / Non-Goals

**Goals:** 提升主体辨识度；集中管理主动作 token 与过期 timer；让纸条、气泡、道具和字体在不同浏览器稳定呈现；保留现有低资源和安全边界。

**Non-Goals:** 不引入物理引擎或动画库，不改变业务状态来源，不新增后端接口，不重做煤球位置和整体人格文案。

## Decisions

1. 使用单一 `activeAction`/token 作为主动作入口，所有旧动作先取消再启动；CSS 只保留一个主 animation。
2. 上下文事件设置 `signalExpiresAt`，8 秒无更新即清零；危险 UI 清理所有视觉层。
3. 纸条和气泡共享文字层仲裁器，气泡优先；道具改用 CSS/内联 SVG，避免 emoji 字体差异。
4. 主体使用更深渐变、较低毛边 opacity/blur 和明确阴影；字体使用 `PingFang SC`、`Microsoft YaHei`、`Noto Sans CJK SC` fallback。

## Risks / Trade-offs

- [状态过期过短] -> 仅影响趣味表现，不影响真实业务数据；8 秒后可由新事件重新触发。
- [动作取消过快] -> 保留点击动作优先级和 token 重播，确保每次用户点击仍有反馈。
- [字体 fallback 差异] -> 使用稳定系统字体栈并在 Chromium 与移动尺寸下回归。

## Migration Plan

先在本地完成源码/浏览器回归和生产构建，再使用现有前端原子发布脚本；发布失败时回指上一 release，不重启后端。
