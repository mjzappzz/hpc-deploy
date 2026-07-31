import assert from 'node:assert/strict'
import test from 'node:test'

import { groupRuntimePaths } from './runtimePaths.ts'

test('groups runtime paths by operational function and preserves configured order', () => {
  const paths = [
    { key: 'remote_tasks' },
    { key: 'artifacts' },
    { key: 'mpi_scripts' },
    { key: 'database' },
    { key: 'apptainer' },
    { key: 'remote_apptainer' },
    { key: 'ssh_keys' },
    { key: 'sqlite_backups' },
  ]

  assert.deepEqual(
    groupRuntimePaths(paths).map(group => ({
      key: group.key,
      rows: group.rows.map(row => row.key),
    })),
    [
      { key: 'core', rows: ['database', 'ssh_keys'] },
      { key: 'assets', rows: ['mpi_scripts'] },
      { key: 'results', rows: ['artifacts', 'sqlite_backups'] },
      { key: 'remote', rows: ['remote_tasks'] },
    ],
  )
})
