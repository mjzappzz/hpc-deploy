import type { ParamsSchema } from '@/api/script'

export interface StressParamConfig {
  duration: number
  stress_type: string
  output_dir: string
  gpu_ids: string
}

export interface DurationParts {
  hours: number
  minutes: number
  seconds: number
}

export const STRESS_TYPE_OPTIONS = [
  { label: 'GPU', value: 'gpu' },
  { label: 'CPU + Memory', value: 'cpu_memory' },
  { label: 'CPU', value: 'cpu' },
  { label: 'Memory', value: 'memory' },
  { label: 'Disk', value: 'disk' },
  { label: 'All', value: 'all' }
] as const

export const DEFAULT_STRESS_CONFIG: StressParamConfig = {
  duration: 0,
  stress_type: 'all',
  output_dir: '~/stress/{datetime}',
  gpu_ids: 'all'
}

interface ParamDefinition {
  type?: string
  label?: string
  options?: unknown[]
  default?: unknown
  required?: boolean
  description?: string
}

export function createStressParamsSchema(config: StressParamConfig): ParamsSchema {
  return {
    duration: {
      type: 'number',
      label: '压测时长',
      default: Number(config.duration),
      required: true,
      description: '压测持续时间，单位秒'
    },
    output_dir: {
      type: 'path',
      label: '输出目录',
      default: config.output_dir,
      required: true,
      description: '默认在用户家目录 stress 目录下按时间创建结果目录'
    },
    stress_type: {
      type: 'select',
      label: '压测类型',
      options: [config.stress_type],
      default: config.stress_type,
      required: true,
      description: '由脚本文件名自动推断'
    },
    gpu_ids: {
      type: 'string',
      label: 'GPU 编号',
      default: config.gpu_ids,
      required: false,
      description: 'all 或 0,1,2,3'
    }
  }
}

export function isStressParamsSchema(schema?: ParamsSchema | null) {
  if (!schema) return false
  return ['duration', 'output_dir', 'stress_type'].every((key) => key in schema)
}

export function stressConfigFromSchema(schema?: ParamsSchema | null): StressParamConfig {
  const source = schema ?? {}
  return {
    duration: numberDefault(source.duration, DEFAULT_STRESS_CONFIG.duration),
    stress_type: stringDefault(source.stress_type, DEFAULT_STRESS_CONFIG.stress_type),
    output_dir: stringDefault(source.output_dir, DEFAULT_STRESS_CONFIG.output_dir),
    gpu_ids: stringDefault(source.gpu_ids, DEFAULT_STRESS_CONFIG.gpu_ids)
  }
}

export function inferStressType(path: string) {
  const name = path.split('/').pop()?.toLowerCase() ?? path.toLowerCase()
  if (name.includes('gpu')) return 'gpu'
  if (name.includes('cpu_mem') || name.includes('cpu-memory')) return 'cpu_memory'
  if (name.includes('cpu')) return 'cpu'
  if (name.includes('mem') || name.includes('memory')) return 'memory'
  if (name.includes('disk') || name.includes('fio')) return 'disk'
  if (name.includes('all')) return 'all'
  return 'all'
}

export function stressTypeLabel(value: string) {
  return STRESS_TYPE_OPTIONS.find((item) => item.value === value)?.label ?? 'All'
}

export function scriptNameFromPath(path: string) {
  const fileName = path.split('/').pop() ?? ''
  return fileName.replace(/\.[^.]+$/, '')
}

export function categoryFromPath(path: string) {
  return path.split('/')[0] || ''
}

export function durationToParts(duration: number): DurationParts {
  const safeDuration = Math.max(0, Math.floor(duration))
  const hours = Math.floor(safeDuration / 3600)
  const minutes = Math.floor((safeDuration % 3600) / 60)
  const seconds = safeDuration % 60
  return { hours, minutes, seconds }
}

export function partsToDuration(parts: DurationParts) {
  return parts.hours * 3600 + parts.minutes * 60 + parts.seconds
}

export function normalizeDurationParts(parts: DurationParts): DurationParts {
  return {
    hours: Math.max(0, Math.floor(Number(parts.hours) || 0)),
    minutes: Math.min(59, Math.max(0, Math.floor(Number(parts.minutes) || 0))),
    seconds: Math.min(59, Math.max(0, Math.floor(Number(parts.seconds) || 0)))
  }
}

export function shouldShowGpuIds(stressType: string) {
  return stressType === 'gpu' || stressType === 'all'
}

function numberDefault(definition: unknown, fallback: number) {
  const value = (definition as ParamDefinition | undefined)?.default
  return typeof value === 'number' ? value : fallback
}

function stringDefault(definition: unknown, fallback: string) {
  const value = (definition as ParamDefinition | undefined)?.default
  return typeof value === 'string' ? value : fallback
}
