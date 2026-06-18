import { h } from 'vue'
import type { VNode } from 'vue'

export interface ConfirmContentOptions {
  intro: string
  doTitle: string
  doItems: string[]
  dontTitle: string
  dontItems: string[]
}

export function buildConfirmContent(options: ConfirmContentOptions): VNode {
  const { intro, doTitle, doItems, dontTitle, dontItems } = options
  return h('div', { style: 'font-size: 14px; line-height: 1.8;' }, [
    h('p', { style: 'margin: 0 0 14px;' }, intro),
    h('div', { style: 'margin-bottom: 10px;' }, [
      h('p', { style: 'margin: 0 0 4px; font-weight: 600; color: var(--el-color-primary, #409eff);' }, doTitle),
      h('ul', { style: 'margin: 0; padding-left: 20px;' }, doItems.map((item) =>
        h('li', { style: 'margin-bottom: 2px;' }, item),
      )),
    ]),
    h('div', { style: 'margin-bottom: 10px;' }, [
      h('p', { style: 'margin: 0 0 4px; font-weight: 600; color: var(--el-color-warning, #e6a23c);' }, dontTitle),
      h('ul', { style: 'margin: 0; padding-left: 20px;' }, dontItems.map((item) =>
        h('li', { style: 'margin-bottom: 2px;' }, item),
      )),
    ]),
    h('p', { style: 'margin: 0; color: var(--el-text-color-secondary, #909399);' }, '是否继续？'),
  ])
}
