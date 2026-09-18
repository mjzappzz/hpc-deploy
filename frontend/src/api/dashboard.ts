import { request } from './request'

export interface ServerStats {
  total: number
  online: number
  offline: number
  unknown?: number
  archived?: number
}

export interface TaskStats {
  total: number
  running: number
  success: number
  failed: number
  canceled: number
  pending: number
  canceling: number
}

export interface RecentTaskItem {
  task_id: string
  batch_id?: string | null
  server_name: string | null
  server_host: string | null
  task_type: string | null
  file_name: string | null
  file_path: string | null
  status: string | null
  created_at: string | null
  start_time: string | null
  end_time: string | null
  command_preview?: string | null
  sequence_index?: number | null
  params?: Record<string, unknown> | null
  duration_seconds?: number | null
  final_status?: string | null
  /** Number of active children represented by this dashboard row. */
  active_task_count?: number
}

export interface RecentCompletedBatchItem {
  batch_id: string
  task_type: string | null
  file_name?: string | null
  file_path?: string | null
  params?: Record<string, unknown> | null
  total: number
  success: number
  failed: number
  canceled: number
  status: string
  server_count: number
  servers: string[]
  created_at: string | null
  end_time: string | null
  duration_seconds: number | null
}

export interface ArtifactStats {
  local_artifacts_count: number
  local_artifacts_size_bytes: number
}

export interface StoragePathStats {
  key: string
  label: string
  path: string
  size_bytes: number
  file_count?: number
  status: string
  error?: string | null
}

export interface StorageBreakdownItem {
  key: string
  label: string
  path?: string | null
  size_bytes: number
  file_count?: number
  status: string
  error?: string | null
  percentage?: number | null
}

export interface StorageStats {
  total_bytes: number
  free_bytes: number
  used_bytes: number
  artifacts_bytes: number
  database_bytes: number
  cleanup_status: string
  capacity_status: string
  usage_percent?: number | null
  project_total_bytes?: number | null
  project_total_file_count?: number | null
  project_status?: 'available' | 'partial' | 'unknown'
  device?: string | null
  mountpoint?: string | null
  inspected_paths?: StoragePathStats[]
  breakdown?: StorageBreakdownItem[]
}

export interface DashboardSummary {
  servers: ServerStats
  tasks: TaskStats
  recent_tasks: RecentTaskItem[]
  recent_completed_tasks: RecentTaskItem[]
  recent_completed_batches?: RecentCompletedBatchItem[]
  artifacts: ArtifactStats
  storage: StorageStats
}

export interface ArtifactTreeNode {
  name: string
  relative_path: string
  type: string
  size_bytes: number
  children: ArtifactTreeNode[]
}

export interface ArtifactTreeResponse {
  root: string
  total_size_bytes: number
  total_dirs: number
  truncated: boolean
  warnings: string[]
  items: ArtifactTreeNode[]
}

/** GET /api/dashboard/summary */
export function getDashboardSummary() {
  return request.get<DashboardSummary>('/dashboard/summary')
}

/** GET /api/dashboard/artifacts/tree */
export function getArtifactsTree(maxDepth = 2) {
  return request.get<ArtifactTreeResponse>('/dashboard/artifacts/tree', {
    params: { max_depth: maxDepth },
  })
}
