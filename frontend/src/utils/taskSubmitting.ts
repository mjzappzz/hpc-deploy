export function beginTaskSubmitting(submitting: Record<string, boolean>, taskId: string): boolean {
  if (submitting[taskId]) return false
  submitting[taskId] = true
  return true
}

export function endTaskSubmitting(submitting: Record<string, boolean>, taskId: string): void {
  delete submitting[taskId]
}
