import { request } from './request'

export interface ServerStats {
  total: number
  online: number
  offline: number
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
  params?: Record<string, unknown> | null
  duration_seconds?: number | null
  final_status?: string | null
}

export interface ArtifactStats {
  local_artifacts_count: number
  local_artifacts_size_bytes: number
}

export interface DashboardSummary {
  servers: ServerStats
  tasks: TaskStats
  recent_tasks: RecentTaskItem[]
  artifacts: ArtifactStats
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
