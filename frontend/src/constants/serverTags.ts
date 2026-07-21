export const SERVER_TAG_OPTIONS = [
  { name: '待压测', type: 'warning' },
  { name: '测试机', type: 'primary' },
  { name: '压测完成', type: 'success' },
  { name: '故障待处理', type: 'danger' },
] as const

export type ServerTagName = typeof SERVER_TAG_OPTIONS[number]['name']
export type ServerTagType = typeof SERVER_TAG_OPTIONS[number]['type']

export function serverTagType(tag: string): ServerTagType | 'info' {
  return SERVER_TAG_OPTIONS.find((item) => item.name === tag)?.type ?? 'info'
}
