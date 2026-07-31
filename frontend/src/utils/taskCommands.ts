type CommandCopyTask = {
  status?: string | null
  task_type?: string | null
  file_name?: string | null
  file_path?: string | null
}

const COMMAND_BLOCK_SCRIPT_FILES = new Set([
  'install_oneapi_2022.sh',
  'install_openmpi_4.1.6_aocc_aocl.sh',
])

export function shouldShowTaskCommandCopyButtons(task: CommandCopyTask): boolean {
  if (task.status?.toUpperCase() !== 'SUCCESS') return false
  if (task.task_type === 'cuda_toolkit') return true

  const fileName = (task.file_name || task.file_path || '').split('/').pop() || ''
  return COMMAND_BLOCK_SCRIPT_FILES.has(fileName)
}

export function extractEnvironmentCommands(messages: string[]): string {
  const startIndex = messages.findIndex(message => message.includes('如需仅当前终端临时加载，请执行：'))
  if (startIndex === -1) return ''

  const lines: string[] = []
  for (let index = startIndex + 1; index < messages.length; index += 1) {
    const message = messages[index]
    if (message.includes('如需验证环境，请执行：')) break

    for (const line of message.split('\n')) {
      const trimmed = line.trim()
      if (
        (trimmed.startsWith('source ') || trimmed.startsWith('export '))
        && trimmed !== 'source ~/.bashrc'
      ) {
        lines.push(trimmed)
      }
    }
  }
  return lines.join('\n')
}

export function extractVerifyCommands(messages: string[]): string {
  const startIndex = messages.findIndex(message => message.includes('如需验证环境，请执行：'))
  if (startIndex === -1) return ''

  const blockLines: string[] = []
  for (let index = startIndex + 1; index < messages.length; index += 1) {
    const message = messages[index]
    if (message.includes('如需删除安装包')) break

    for (const line of message.split('\n')) {
      const trimmed = line.trim()
      if (trimmed) blockLines.push(trimmed)
    }
  }

  const whichLines = blockLines.filter(line => line.startsWith('which '))
  if (whichLines.length === 0) return blockLines.join('\n')

  const hasMklRootCheck = blockLines.some(line => /^echo\s+["']?\$MKLROOT["']?$/.test(line))
  return [...whichLines, ...(hasMklRootCheck ? ['echo "$MKLROOT"'] : [])].join('\n')
}
