export type OsIconName = 'ubuntu' | 'rocky' | 'debian' | 'centos' | 'rhel' | 'linux'

export function getOsIconName(value: string | null | undefined): OsIconName {
  const text = value?.toLowerCase() ?? ''
  if (text.includes('ubuntu')) return 'ubuntu'
  if (text.includes('rocky')) return 'rocky'
  if (text.includes('debian')) return 'debian'
  if (text.includes('centos')) return 'centos'
  if (text.includes('red hat') || text.includes('rhel')) return 'rhel'
  return 'linux'
}

export function getOsIconPath(value: string | null | undefined): string {
  return `/assets/os/${getOsIconName(value)}.svg`
}

export function getOsDisplayName(value: string | null | undefined, compact = false): string {
  const text = value?.trim() || '-'
  if (!compact || text === '-') return text

  const patterns: Array<[RegExp, string]> = [
    [/Ubuntu\s+(\d+(?:\.\d+)?)/i, 'Ubuntu'],
    [/Rocky(?: Linux)?\s+(\d+(?:\.\d+)?)/i, 'Rocky'],
    [/Debian(?: GNU\/Linux)?\s+(\d+(?:\.\d+)?)/i, 'Debian'],
    [/CentOS(?: Linux)?\s+(\d+(?:\.\d+)?)/i, 'CentOS'],
    [/(?:Red Hat Enterprise Linux|RHEL)\s+(\d+(?:\.\d+)?)/i, 'RHEL'],
  ]
  for (const [pattern, name] of patterns) {
    const match = text.match(pattern)
    if (match) return `${name} ${match[1]}`
  }
  return text
}
