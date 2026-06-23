import { request } from './request'

export interface TaskDiagnosisItem {
  level: string
  category: string
  title: string
  summary: string
  possible_causes: string[]
  suggestions: string[]
  matched_patterns: string[]
  evidence: string[]
}

export interface TaskDiagnosisResponse {
  task_id: string
  task_name: string
  status: string
  diagnosis: TaskDiagnosisItem
}

export function getTaskDiagnosis(taskId: string) {
  return request.get<TaskDiagnosisResponse>(`/tasks/${taskId}/diagnosis`)
}
