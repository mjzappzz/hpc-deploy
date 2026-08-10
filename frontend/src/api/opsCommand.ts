import { request } from './request'

export interface OpsCommand {
  id: number
  title: string
  content: string
  created_at: string
  updated_at: string
}

export interface OpsCommandPayload {
  title: string
  content: string
}

export function listOpsCommands() {
  return request.get<OpsCommand[]>('/ops-commands')
}

export function createOpsCommand(payload: OpsCommandPayload) {
  return request.post<OpsCommand>('/ops-commands', payload)
}

export function updateOpsCommand(commandId: number, payload: OpsCommandPayload) {
  return request.put<OpsCommand>(`/ops-commands/${commandId}`, payload)
}

export function deleteOpsCommand(commandId: number) {
  return request.delete(`/ops-commands/${commandId}`)
}
