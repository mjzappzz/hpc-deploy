import { request } from './request'

export interface TaskDiagnosisItem {
  level: string
  category: string
  attribution: string
  title: string
  conclusion: string
  summary: string
  possible_causes: string[]
  suggestions: string[]
  risk_tips: string[]
  matched_patterns: string[]
  evidence: string[]
}

export interface TaskDiagnosisResponse {
  task_id: string
  task_name: string
  status: string
  execution_status: string
  report_status: string
  final_status: string
  diagnosis: TaskDiagnosisItem
}

export function getTaskDiagnosis(taskId: string) {
  return request.get<TaskDiagnosisResponse>(`/tasks/${taskId}/diagnosis`)
}
