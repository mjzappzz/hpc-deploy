import assert from 'node:assert/strict'
import test from 'node:test'

import { opsCommandRichTextToPlainText } from './richText.ts'

test('copies ops command rich text with line breaks, blank lines, indentation, and decoded shell characters', () => {
  const richText = "cat &gt;/tmp/test.sh &lt;&lt;&#x27;EOF&#x27;<div>#!/usr/bin/env bash</div><div>  echo &quot;hello&quot;</div><div><br></div><div>echo done &amp;&amp; true</div><div>EOF</div>"

  assert.equal(
    opsCommandRichTextToPlainText(richText),
    "cat >/tmp/test.sh <<'EOF'\n#!/usr/bin/env bash\n  echo \"hello\"\n\necho done && true\nEOF",
  )
})

test('keeps existing plain-text line breaks unchanged', () => {
  assert.equal(
    opsCommandRichTextToPlainText('first command\n\nsecond command'),
    'first command\n\nsecond command',
  )
})

test('removes presentation-only bold tags without changing their text', () => {
  assert.equal(
    opsCommandRichTextToPlainText('<p><strong>sudo</strong> systemctl restart ssh</p>'),
    'sudo systemctl restart ssh',
  )
})
