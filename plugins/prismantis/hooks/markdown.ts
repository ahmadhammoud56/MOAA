export type Inline =
  | { kind: 'text'; text: string }
  | { kind: 'strong'; children: Inline[] }
  | { kind: 'emphasis'; children: Inline[] }
  | { kind: 'strike'; children: Inline[] }
  | { kind: 'code'; text: string }
  | { kind: 'link'; text: string; href: string }
  | { kind: 'number'; text: string }
  | { kind: 'path'; text: string }
  | { kind: 'dim'; text: string }

export type Block = { raw: string } & (
  | { kind: 'heading'; level: number; inline: Inline[] }
  | { kind: 'paragraph'; inline: Inline[] }
  | { kind: 'list'; ordered: boolean; items: { marker: string; depth: number; task?: boolean; inline: Inline[] }[] }
  | { kind: 'code'; lang: string; lines: string[] }
  | { kind: 'quote'; inline: Inline[] }
  | { kind: 'alert'; level: AlertLevel; inline: Inline[] }
  | { kind: 'rule' }
  | { kind: 'table'; header: Inline[][]; align: ('left' | 'right' | 'center')[]; rows: Inline[][][] }
)

type Draft = Block extends infer B ? (B extends unknown ? Omit<B, 'raw'> : never) : never

export type AlertLevel = 'note' | 'tip' | 'important' | 'warning' | 'caution'
const ALERT = /^\[!(note|tip|important|warning|caution)\]\s*(.*)$/i

export type Highlight = { numbers: boolean; paths: boolean }

const MAX_INLINE = 4000
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/
const FENCE = /^\s*(`{3,}|~{3,})\s*([\w+-]*)/

const splitRow = (line: string): string[] => {
  const trimmed = line.trim().replace(/^\|/, '').replace(/(?<!\\)\|$/, '')
  const cells: string[] = []
  let cell = ''
  for (let i = 0; i < trimmed.length; i++) {
    const ch = trimmed[i]
    if (ch === '\\' && trimmed[i + 1] === '|') {
      cell += '|'
      i++
    } else if (ch === '|') {
      cells.push(cell.trim())
      cell = ''
    } else {
      cell += ch
    }
  }
  cells.push(cell.trim())
  return cells
}

const INLINE = /(`+)(?!`)(.+?)(?<!`)\1(?!`)|\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+?)\*\*|__([^_]+?)__|~~([^~]+?)~~|(?<![\w*])\*([^*\s][^*]*?)\*(?!\w)|(?<![\w_])_([^_\s][^_]*?)_(?!\w)|(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/g
const NUMBER = /(?<![\w.#/-])(v?\d+(?:[.,:]\d+)*(?:%|ms|s|m|h|d|Gi|Mi|GB|MB|KB|x)?)(?![\w/])/g
const PATH = /(?<![\w/.:])((?:~|\.{1,2})?\/[\w.@+-]+(?:\/[\w.@+-]*)*)/g

const decorate = (text: string, hl: Highlight): Inline[] => {
  if (!hl.numbers && !hl.paths) return [{ kind: 'text', text }]
  const marks: { start: number; end: number; kind: 'number' | 'path' }[] = []
  if (hl.paths) for (const m of text.matchAll(PATH)) marks.push({ start: m.index, end: m.index + m[0].length, kind: 'path' })
  if (hl.numbers) {
    for (const m of text.matchAll(NUMBER)) {
      const start = m.index
      if (!marks.some(p => start < p.end && start + m[0].length > p.start)) {
        marks.push({ start, end: start + m[0].length, kind: 'number' })
      }
    }
  }
  marks.sort((a, b) => a.start - b.start)
  const out: Inline[] = []
  let at = 0
  for (const m of marks) {
    if (m.start > at) out.push({ kind: 'text', text: text.slice(at, m.start) })
    out.push({ kind: m.kind, text: text.slice(m.start, m.end) })
    at = m.end
  }
  if (at < text.length) out.push({ kind: 'text', text: text.slice(at) })
  return out
}

export const parseInline = (text: string, hl: Highlight): Inline[] => {
  if (text.length > MAX_INLINE) return [{ kind: 'text', text }]
  const out: Inline[] = []
  let at = 0
  for (const m of text.matchAll(INLINE)) {
    if (m.index > at) out.push(...decorate(text.slice(at, m.index), hl))
    if (m[2] !== undefined) out.push({ kind: 'code', text: m[2] })
    else if (m[3] !== undefined) out.push({ kind: 'link', text: m[3], href: m[4] ?? "" })
    else if (m[5] !== undefined || m[6] !== undefined) out.push({ kind: 'strong', children: parseInline(m[5] ?? m[6] ?? "", hl) })
    else if (m[7] !== undefined) out.push({ kind: 'strike', children: parseInline(m[7], hl) })
    else if (m[8] !== undefined || m[9] !== undefined) out.push({ kind: 'emphasis', children: parseInline(m[8] ?? m[9] ?? "", hl) })
    else if (m[10] !== undefined) out.push({ kind: 'link', text: m[10], href: m[10] })
    at = m.index + m[0].length
  }
  if (at < text.length) out.push(...decorate(text.slice(at), hl))
  return out
}

export const inlineText = (inline: Inline[]): string =>
  inline.map(n => ('children' in n ? inlineText(n.children) : n.text)).join('')

export const parse = (source: string, hl: Highlight): Block[] => {
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  const at = (n: number) => lines[n] ?? ''
  const blocks: Block[] = []
  const add = (block: Draft, from: number, to: number) => blocks.push({ ...block, raw: lines.slice(from, to).join('\n') } as Block)
  let paraStart = 0
  let para: string[] = []

  const flush = (end: number) => {
    if (para.length) add({ kind: 'paragraph', inline: parseInline(para.join(' '), hl) }, paraStart, end)
    para = []
  }

  for (let i = 0; i < lines.length; i++) {
    const line = at(i)
    const fence = FENCE.exec(line)
    if (fence) {
      flush(i)
      const start = i
      const run = fence[1] ?? '```'
      const closer = new RegExp(`^\\s*\\${run[0]}{${run.length},}\\s*$`)
      const body: string[] = []
      i++
      while (i < lines.length && !closer.test(at(i))) body.push(at(i++))
      add({ kind: 'code', lang: fence[2] ?? '', lines: body }, start, i + 1)
      continue
    }
    if (line.trim() === '') {
      flush(i)
      continue
    }
    const heading = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line)
    if (heading) {
      flush(i)
      add({ kind: 'heading', level: (heading[1] ?? '#').length, inline: parseInline(heading[2] ?? '', hl) }, i, i + 1)
      continue
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
      flush(i)
      add({ kind: 'rule' }, i, i + 1)
      continue
    }
    if (line.includes('|') && i + 1 < lines.length && TABLE_SEP.test(at(i + 1))) {
      flush(i)
      const start = i
      const header = splitRow(line)
      const align = splitRow(at(i + 1)).map(c =>
        c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : 'left',
      )
      i += 2
      const rows: Inline[][][] = []
      while (i < lines.length && at(i).includes('|') && at(i).trim() !== '') {
        const cells = splitRow(at(i++))
        rows.push(header.map((_, c) => parseInline(cells[c] ?? '', hl)))
      }
      add({ kind: 'table', header: header.map(c => parseInline(c, { numbers: false, paths: false })), align, rows }, start, i)
      i--
      continue
    }
    if (/^\s*>/.test(line)) {
      flush(i)
      const start = i
      const body: string[] = []
      while (i < lines.length && /^\s*>/.test(at(i))) body.push(at(i++).replace(/^\s*>\s?/, ''))
      const alert = ALERT.exec(body[0] ?? '')
      if (alert) add({ kind: 'alert', level: alert[1]!.toLowerCase() as AlertLevel, inline: parseInline([alert[2]!, ...body.slice(1)].join(' ').trim(), hl) }, start, i)
      else add({ kind: 'quote', inline: parseInline(body.join(' '), hl) }, start, i)
      i--
      continue
    }
    const item = LIST_ITEM.exec(line)
    if (item) {
      flush(i)
      const start = i
      const ordered = /\d/.test(item[2] ?? '')
      const items: { marker: string; depth: number; task?: boolean; inline: Inline[] }[] = []
      const contentIndent: number[] = []
      while (i < lines.length) {
        const it = LIST_ITEM.exec(at(i))
        if (it) {
          contentIndent.push((it[1] ?? '').replace(/\t/g, '  ').length + (it[2] ?? '').length + 1)
          const task = /^\[([ xX])\]\s+(.*)$/.exec(it[3] ?? '')
          items.push({ marker: it[2] ?? '-', depth: Math.floor((it[1] ?? '').replace(/\t/g, '  ').length / 2), ...(task ? { task: task[1] !== ' ' } : {}), inline: parseInline(task ? task[2]! : it[3] ?? '', hl) })
        } else if (/^\s{2,}\S/.test(at(i)) && items.length) {
          const indent = (at(i).match(/^\s*/)?.[0] ?? '').replace(/\t/g, '  ').length
          let owner = items.length - 1
          while (owner > 0 && contentIndent[owner]! > indent) owner--
          const target = items[owner]!
          target.inline = [...target.inline, { kind: 'text', text: ' ' }, ...parseInline(at(i).trim(), hl)]
        } else {
          break
        }
        i++
      }
      add({ kind: 'list', ordered, items }, start, i)
      i--
      continue
    }
    if (!para.length) paraStart = i
    para.push(line.trim())
  }
  flush(lines.length)
  return blocks
}
