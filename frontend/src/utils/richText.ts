const HTML_ENTITY_PATTERN = /&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi

const NAMED_ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
}

function decodeHtmlEntities(value: string): string {
  return value.replace(HTML_ENTITY_PATTERN, (_, entity: string) => {
    const normalized = entity.toLowerCase()
    if (normalized.startsWith('#x')) {
      return String.fromCodePoint(Number.parseInt(normalized.slice(2), 16))
    }
    if (normalized.startsWith('#')) {
      return String.fromCodePoint(Number.parseInt(normalized.slice(1), 10))
    }
    return NAMED_ENTITIES[normalized] ?? `&${entity};`
  })
}

/** Convert the limited rich text supported by Ops Commands into copyable plain text. */
export function opsCommandRichTextToPlainText(value: string): string {
  let output = ''
  const tokens = value.split(/(<\/?(?:div|p|strong|b)\s*>|<br\s*\/?>)/gi)

  for (const token of tokens) {
    if (/^<br\s*\/?>$/i.test(token)) {
      output += '\n'
    } else if (/^<(?:div|p)\s*>$/i.test(token)) {
      if (output && !output.endsWith('\n')) output += '\n'
    } else if (/^<\/(?:div|p)>$/i.test(token)) {
      if (!output.endsWith('\n')) output += '\n'
    } else if (!/^<\/?(?:div|p|strong|b)\s*>$/i.test(token)) {
      output += decodeHtmlEntities(token)
    }
  }

  return output.replace(/\r\n?/g, '\n').replace(/\n+$/, '')
}
