export const COMPANION_CONTEXT_EVENT = 'hpcdeploy:companion-context'

export type CompanionSignal = 'gpu' | 'queue' | 'network' | 'disk' | 'unknown'

export interface CompanionContextDetail {
  signal?: CompanionSignal
  intensity?: 'low' | 'medium' | 'high'
  status?: string
  source?: string
}

export function dispatchCompanionContext(detail: CompanionContextDetail): void {
  window.dispatchEvent(new CustomEvent<CompanionContextDetail>(COMPANION_CONTEXT_EVENT, { detail }))
}
