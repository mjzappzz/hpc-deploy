export type EnvironmentBusinessCategory = 'base_system' | 'compiler_mpi'

const BASE_SYSTEM_SCRIPTS = new Set([
  'lock_linux_release.sh',
  'disable_linux_lock_sleep.sh',
])

export function environmentBusinessCategory(fileName: string): EnvironmentBusinessCategory {
  return BASE_SYSTEM_SCRIPTS.has(fileName) ? 'base_system' : 'compiler_mpi'
}
