import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('uses a star alone to indicate starred commands', async () => {
  const source = await readFile(new URL('./OpsCommands.vue', import.meta.url), 'utf8')

  assert.match(source, /<StarFilled v-if="starredCommandIds\.includes\(command\.id\)" \/>/)
  assert.doesNotMatch(source, /\.ops-command-item\.is-starred/)
  assert.match(source, /:class="\{\s+'is-active': selectedId === command\.id,\s+\}"/)
  assert.doesNotMatch(source, /warning-light-[89]/)
})

test('shows the first sorted command when no command detail is selected', async () => {
  const source = await readFile(new URL('./OpsCommands.vue', import.meta.url), 'utf8')

  assert.match(source, /if \(selectedId\.value === undefined\) \{\s+const firstCommand = filteredCommands\.value\[0\]\s+if \(firstCommand\) selectCommand\(firstCommand\)/)
})
