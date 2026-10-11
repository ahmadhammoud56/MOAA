import type { ElementTable, RenderElement } from 'claude-code'

import type { Block, Inline } from './markdown'
import { inlineText } from './markdown'
import { commentTail, commentVisual, flow, hasRtl } from './rtl'
import type { Style, Theme } from './theme'
import type { PrismToken } from './vendor/prism.js'
import { languages, tokenize } from './vendor/prism.js'

const WIDE = /[\u1100-\u115F\u2E80-\uA4CF\uAC00-\uD7A3\uF900-\uFAFF\uFE30-\uFE4F\uFF00-\uFF60\uFFE0-\uFFE6]|\p{Extended_Pictographic}/u
const segmenter = typeof Intl !== 'undefined' && 'Segmenter' in Intl ? new Intl.Segmenter() : undefined

const graphemes = (s: string): string[] => (segmenter ? [...segmenter.segment(s)].map(g => g.segment) : [...s])

export const width = (s: string): number =>
  graphemes(s).reduce((w, g) => (/^\p{M}+$/u.test(g) ? w : w + (WIDE.test(g) ? 2 : 1)), 0)

const wrapRanges = (text: string, w: number): [number, number][] => {
  if (width(text) <= w) return [[0, text.length]]
  const out: [number, number][] = []
  let line: [number, number] | undefined
  for (const word of text.matchAll(/\S+/g)) {
    let start = word.index
    const end = start + word[0].length
    while (width(text.slice(start, end)) > w) {
      if (line) out.push(line)
      line = undefined
      let cut = start
      for (const g of graphemes(text.slice(start, end))) {
        if (cut > start && width(text.slice(start, cut + g.length)) > w) break
        cut += g.length
      }
      out.push([start, cut])
      start = cut
    }
    if (start === end) continue
    if (line && width(text.slice(line[0], end)) <= w) line = [line[0], end]
    else {
      if (line) out.push(line)
      line = [start, end]
    }
  }
  if (line) out.push(line)
  return out.length ? out : [[0, 0]]
}

const sliceInline = (nodes: Inline[], from: number, to: number): Inline[] => {
  const out: Inline[] = []
  let at = 0
  for (const n of nodes) {
    const length = inlineText([n]).length
    const a = Math.max(from - at, 0)
    const b = Math.min(to - at, length)
    at += length
    if (a >= b) continue
    if ('children' in n) out.push({ ...n, children: sliceInline(n.children, a, b) })
    else out.push({ ...n, text: n.text.slice(a, b) })
  }
  return out
}

const hasLink = (nodes: Inline[]): boolean => nodes.some(n => n.kind === 'link' || ('children' in n && hasLink(n.children)))

const mostLines = (text: string, w: number): number => (text.match(/\S+/g)?.length ?? 0) + Math.ceil(width(text) / w)

const wrapInline = (nodes: Inline[], w: number): Inline[][] => {
  const text = inlineText(nodes)
  return width(text) <= w ? [nodes] : wrapRanges(text, w).map(([a, b]) => sliceInline(nodes, a, b))
}

const flowOf = (style: Style, nodes: Inline[], columns: number) => (style.reorder ? flow(nodes, columns, width, style.shape) : null)

const renderInline = (el: ElementTable, style: Style, nodes: Inline[], keyBase: string): RenderElement[] => {
  const { Text } = el
  const t = style.theme
  return nodes.map((n, i) => {
    const key = `${keyBase}.${i}`
    switch (n.kind) {
      case 'text':
        return <Text key={key}>{n.text}</Text>
      case 'strong':
        return <Text key={key} bold color={t.strong}>{renderInline(el, style, n.children, key)}</Text>
      case 'emphasis':
        return <Text key={key} italic color={t.emphasis}>{renderInline(el, style, n.children, key)}</Text>
      case 'strike':
        return <Text key={key} strikethrough dimColor>{renderInline(el, style, n.children, key)}</Text>
      case 'code':
        return <Text key={key} color={t.inlineCode}>{n.text}</Text>
      case 'link':
        return /^[a-z][\w+.-]*:/i.test(n.href)
          ? n.text === n.href ? <el.Link key={key} href={n.href} /> : <el.Link key={key} href={n.href}><Text color={t.link} underline>{n.text}</Text></el.Link>
          : <Text key={key} color={t.link} underline>{n.text}</Text>
      case 'number':
        return <Text key={key} color={t.number}>{n.text}</Text>
      case 'path':
        return <Text key={key} color={t.path}>{n.text}</Text>
      case 'dim':
        return <Text key={key} dimColor>{n.text}</Text>
    }
  })
}

const renderFlow = (el: ElementTable, style: Style, lines: Inline[][], key: string, props: { italic?: boolean; color?: string; bold?: boolean } = {}) => {
  const { Text } = el
  return lines.map((line, i) => <Text key={`${key}.${i}`} {...props}>{renderInline(el, style, line, `${key}.${i}`)}</Text>)
}

const PRISM_COLORS: Record<string, keyof Theme> = {
  comment: 'codeComment', prolog: 'codeComment', doctype: 'codeComment', cdata: 'codeComment',
  string: 'codeString', char: 'codeString', 'template-string': 'codeString', 'attr-value': 'codeString', url: 'codeString',
  number: 'number', boolean: 'number', constant: 'number', symbol: 'number', inserted: 'number',
  keyword: 'codeFlag', important: 'codeFlag', atrule: 'codeFlag', rule: 'codeFlag', deleted: 'codeFlag',
  function: 'codeCommand', 'class-name': 'codeCommand', builtin: 'codeCommand', key: 'codeCommand', selector: 'codeCommand',
  property: 'link', tag: 'link', 'attr-name': 'emphasis', variable: 'emphasis', regex: 'path',
}

type Segment = { text: string; color?: string; italic: boolean }

const flatten = (tokens: PrismToken[], style: Style, color?: string, italic = false): Segment[] =>
  tokens.flatMap(token => {
    if (typeof token === 'string') return [{ text: token, color, italic }]
    const names = [token.type, ...(Array.isArray(token.alias) ? token.alias : token.alias ? [token.alias] : [])]
    const slot = names.map(n => PRISM_COLORS[n]).find(Boolean)
    const inner = Array.isArray(token.content) ? token.content : [token.type === 'comment' && typeof token.content === 'string' && style.reorder ? commentVisual(token.content, style.shape) : token.content]
    return flatten(inner, style, slot ? style.theme[slot] : color, italic || token.type === 'comment')
  })

export const remember = <T,>(cache: Map<string, T>, key: string, make: () => T, limit = 200): T => {
  const hit = cache.get(key)
  if (hit !== undefined) return hit
  const value = make()
  cache.set(key, value)
  if (cache.size > limit) cache.delete(cache.keys().next().value!)
  return value
}

const highlighted = new WeakMap<Style, Map<string, Segment[][]>>()

const grammarFor = (lang: string) => {
  const name = lang.toLowerCase()
  const grammar = Object.hasOwn(languages, name) ? languages[name] : undefined
  return grammar !== null && typeof grammar === 'object' ? grammar : undefined
}

export const highlightBlock = ({ Text }: ElementTable, style: Style, lines: string[], lang: string, key: string): RenderElement[] | null => {
  const grammar = grammarFor(lang)
  if (!grammar) return null
  const code = lines.join('\n')
  const cache = highlighted.get(style) ?? new Map<string, Segment[][]>()
  highlighted.set(style, cache)
  const rows = remember(cache, `${lang}\0${code}`, () => {
    const out: Segment[][] = [[]]
    for (const seg of flatten(tokenize(code, grammar), style)) {
      seg.text.split('\n').forEach((piece, i) => {
        if (i > 0) out.push([])
        if (piece) out[out.length - 1]!.push({ ...seg, text: piece })
      })
    }
    return out
  })
  return rows.map((row, r) => (
    <Text key={`${key}.${r}`} color={style.theme.codeText}>
      {row.length ? row.map((s, i) => <Text key={`${key}.${r}.${i}`} color={s.color} italic={s.italic}>{s.text}</Text>) : ' '}
    </Text>
  ))
}

const isShellLang = (lang: string) => lang === '' || /^(sh|bash|zsh|shell|console|fish|powershell|ps1)$/i.test(lang)

export const codeLine = (el: ElementTable, style: Style, line: string, lang: string, key: string): RenderElement => {
  const { Text } = el
  const t = style.theme
  const isShell = isShellLang(lang)
  if (/[\u2500-\u257F]/.test(line)) return <Text key={key} color={t.codeText}>{line}</Text>
  const comment = style.reorder ? commentTail(line, style.shape) : null
  if (comment) {
    return (
      <Text key={key} color={t.codeText}>
        {comment.head ? codeLine(el, style, comment.head, lang, `${key}.h`) : null}
        <Text color={t.codeComment}>{comment.marker + comment.tail}</Text>
      </Text>
    )
  }
  if (!isShell) return <Text key={key} color={t.codeText}>{line || ' '}</Text>
  if (/^\s*#/.test(line)) return <Text key={key} color={t.codeComment}>{line}</Text>
  const parts = line.split(/("[^"]*"|'[^']*'|\s+)/).filter(p => p !== '')
  let seenCommand = false
  return (
    <Text key={key} color={t.codeText}>
      {parts.map((p, i) => {
        if (/^\s+$/.test(p)) return <Text key={`${key}.${i}`}>{p}</Text>
        if (/^["']/.test(p)) return <Text key={`${key}.${i}`} color={t.codeString}>{p}</Text>
        if (/^--?[\w-]/.test(p)) return <Text key={`${key}.${i}`} color={t.codeFlag}>{p}</Text>
        if (!seenCommand && !/^[$>|&;]+$/.test(p)) {
          seenCommand = true
          return <Text key={`${key}.${i}`} color={t.codeCommand}>{p}</Text>
        }
        if (/^(\||&&|;|\|\|)$/.test(p)) seenCommand = false
        return <Text key={`${key}.${i}`}>{p}</Text>
      })}
    </Text>
  )
}

const columnWidths = (natural: number[], available: number, gap: number): number[] => {
  const room = Math.max(natural.length, available - gap * (natural.length - 1))
  const total = natural.reduce((a, b) => a + b, 0)
  if (total <= room) return natural
  const widths = natural.map(() => 0)
  let open = natural.map((_, c) => c)
  let left = room
  for (let fits = [-1]; fits.length; ) {
    const share = Math.floor(left / open.length)
    fits = open.filter(c => natural[c]! <= share)
    fits.forEach(c => (widths[c] = natural[c]!, left -= natural[c]!))
    open = open.filter(c => !fits.includes(c))
  }
  open.forEach((c, i) => (widths[c] = Math.max(1, Math.floor(left / open.length) + (i < left % open.length ? 1 : 0))))
  while (widths.reduce((a, b) => a + b, 0) > room) {
    const widest = widths.indexOf(Math.max(...widths))
    if (widths[widest]! <= 1) break
    widths[widest]!--
  }
  return widths
}

const displayText = (inline: Inline[]): string =>
  inline.map(n => (n.kind === 'link' && n.text !== n.href ? `${n.text} (${n.href})` : 'children' in n ? displayText(n.children) : n.text)).join('')

const isRtlTable = (style: Style, block: Extract<Block, { kind: 'table' }>): boolean => {
  const cells = [...block.header, ...block.rows.flat()].filter(cell => displayText(cell).trim() !== '')
  return cells.filter(cell => flowOf(style, cell, Infinity)?.base === 'R').length * 2 > cells.length
}

const ART_WIDTH = 100

export const tableArt = (block: Extract<Block, { kind: 'table' }>): string => {
  const cells = [block.header, ...block.rows].map(r => block.header.map((_, c) => displayText(r[c] ?? [])))
  const widths = columnWidths(block.header.map((_, c) => Math.max(...cells.map(r => width(r[c]!)))), ART_WIDTH - 4, 3)
  const pad = (text: string, c: number, align: 'left' | 'right' | 'center') => {
    const room = widths[c]! - width(text)
    const left = align === 'right' ? room : align === 'center' ? Math.floor(room / 2) : 0
    return ' '.repeat(left) + text + ' '.repeat(room - left)
  }
  const line = (l: string, m: string, r: string) => l + widths.map(w => '─'.repeat(w + 2)).join(m) + r
  const row = (r: string[], header: boolean) => {
    const lines = r.map((text, c) => wrapRanges(text, widths[c]!).map(([a, b]) => text.slice(a, b)))
    return Array.from({ length: Math.max(...lines.map(l => l.length)) }, (_, i) =>
      `│ ${lines.map((l, c) => pad(l[i] ?? '', c, header ? 'center' : block.align[c] ?? 'left')).join(' │ ')} │`)
  }
  const art = [line('┌', '┬', '┐'), ...row(cells[0]!, true), ...cells.slice(1).flatMap(r => [line('├', '┼', '┤'), ...row(r, false)]), line('└', '┴', '┘')]
  return ['```', ...art, '```'].join('\n')
}

const renderTable = (el: ElementTable, style: Style, block: Extract<Block, { kind: 'table' }>, columns: number, key: string) => {
  const { Box, Text } = el
  const t = style.theme
  const rtl = isRtlTable(style, block)
  const box = style.tableStyle === 'box'
  const gap = box ? 0 : style.tableStyle === 'grid' ? 3 : 2
  const natural = block.header.map((h, c) =>
    Math.max(width(displayText(h)), ...block.rows.map(r => width(displayText(r[c] ?? [])))),
  )
  const widths = box ? columnWidths(natural, columns - 4, 3) : columnWidths(natural, columns, gap)
  const order = natural.map((_, c) => c)
  if (rtl) order.reverse()
  const ruleChar = style.tableStyle === 'grid' ? '━' : '─'
  const justify = (c: number) =>
    block.align[c] === 'right' ? 'flex-end' : block.align[c] === 'center' ? 'center' : 'flex-start'

  const rule = (k: string, heavy: boolean) => (
    <Box key={k} flexDirection="row" columnGap={gap}>
      {order.map(c => (
        <Text key={`${k}.${c}`} color={t.tableRule} dimColor={!heavy && !t.tableRule}>
          {(heavy ? ruleChar : '─').repeat(widths[c]!)}
        </Text>
      ))}
    </Box>
  )

  const bar = (k: string, text: string, lines = 1) => (
    <Text key={k} color={t.tableRule} dimColor={!t.tableRule}>{Array.from({ length: lines }, () => text).join('\n')}</Text>
  )
  const clipped = (lines: number) => (k: string, text: string) => (
    <Box key={k} minWidth={width(text)}>
      <Box position="absolute" top={0} bottom={0} left={0} minWidth={width(text)} overflow="hidden">
        {bar(`${k}.b`, text, lines)}
      </Box>
    </Box>
  )
  const edge = (k: string, [left, fill, mid, right]: string) =>
    bar(k, left + order.map(c => fill!.repeat(widths[c]! + 2)).join(mid) + right)

  const row = (cells: Inline[][], k: string, isHeader: boolean, border: (k: string, text: string) => RenderElement = bar) => (
    <Box key={k} flexDirection="row" columnGap={gap} alignItems="stretch">
      {box && border(`${k}.l`, '│ ')}
      {order.map((c, i) => {
        const w = widths[c]!
        const cell = flowOf(style, cells[c] ?? [], Infinity)
        const content = cell ? cell.lines[0]! : (cells[c] ?? [])
        const side = cell?.base === 'R' && block.align[c] !== 'center' ? 'flex-end' : justify(c)
        const cellBox = (
          <Box key={`${k}.${c}`} width={w} flexShrink={0} justifyContent={side}>
            {isHeader
              ? <Text bold color={t.tableHeader}>{inlineText(content)}</Text>
              : <Text>{renderInline(el, style, content, `${k}.${c}`)}</Text>}
          </Box>
        )
        return box && i > 0 ? [border(`${k}.${c}s`, ' │ '), cellBox] : cellBox
      })}
      {box && border(`${k}.r`, ' │')}
    </Box>
  )

  const wrappedRow = (cells: Inline[][], k: string, isHeader: boolean) => {
    if (!isHeader && cells.some(hasLink)) return [row(cells, k, isHeader, clipped(Math.max(1, ...widths.map((w, c) => mostLines(displayText(cells[c] ?? []), w)))))]
    const wrapped = widths.map((w, c) => {
      const content = cells[c] ?? []
      if (natural[c]! <= w) return [content]
      return wrapInline(isHeader ? [{ kind: 'text', text: inlineText(content) }] : content, w)
    })
    return Array.from({ length: Math.max(...wrapped.map(l => l.length)) }, (_, i) =>
      row(wrapped.map(l => l[i] ?? []), `${k}.${i}`, isHeader))
  }

  if (box) {
    const lines: RenderElement[] = [edge(`${key}.t`, '┌─┬┐'), ...wrappedRow(block.header, `${key}.h`, true), edge(`${key}.hr`, '╞═╪╡')]
    block.rows.forEach((r, i) => {
      if (i > 0) lines.push(edge(`${key}.r${i}r`, '├─┼┤'))
      lines.push(...wrappedRow(r, `${key}.r${i}`, false))
    })
    lines.push(edge(`${key}.b`, '└─┴┘'))
    return <Box key={key} flexDirection="column" {...(rtl ? { alignSelf: 'flex-end' as const } : {})}>{lines}</Box>
  }

  const body: RenderElement[] = [row(block.header, `${key}.h`, true), rule(`${key}.hr`, true)]
  block.rows.forEach((r, i) => {
    body.push(row(r, `${key}.r${i}`, false))
    if (style.tableStyle !== 'minimal' && i < block.rows.length - 1) body.push(rule(`${key}.r${i}r`, false))
  })
  return <Box key={key} flexDirection="column" {...(rtl ? { alignSelf: 'flex-end' as const } : {})}>{body}</Box>
}

const renderHeading = (el: ElementTable, style: Style, block: Extract<Block, { kind: 'heading' }>, key: string) => {
  const rtl = flowOf(style, block.inline, Infinity)
  if (!rtl) return drawHeading(el, style, block, block.inline, key)
  const heading = drawHeading(el, style, block, rtl.lines[0]!, key)
  return rtl.base === 'R' ? <el.Box key={key} alignSelf="flex-end">{heading}</el.Box> : heading
}

const drawHeading = (el: ElementTable, style: Style, block: Extract<Block, { kind: 'heading' }>, inline: Inline[], key: string) => {
  const { Box, Text } = el
  const t = style.theme
  const color = block.level <= 2 ? t.heading : t.accent ?? t.heading
  const label = inlineText(inline)
  switch (style.headingStyle) {
    case 'uppercase':
      return <Text key={key} bold color={color}>{block.level === 1 ? label.toUpperCase() : label}</Text>
    case 'underline':
      return <Text key={key} bold underline={block.level <= 2} color={color}>{label}</Text>
    case 'banner':
      if (block.level === 1) return <Box key={key} alignSelf="flex-start" borderStyle="bold" borderColor={color} paddingX={1}><Text bold color={color}>{renderInline(el, style, inline, key)}</Text></Box>
      return block.level === 2
        ? <Box key={key} flexDirection="column" alignSelf="flex-start"><Text bold color={color}>{renderInline(el, style, inline, key)}</Text><Text color={color}>{'━'.repeat(width(label))}</Text></Box>
        : <Text key={key} bold color={block.level === 3 ? color : t.strong}>{renderInline(el, style, inline, key)}</Text>
    default:
      return <Text key={key} bold color={color}>{renderInline(el, style, inline, key)}</Text>
  }
}

const ALERT_COLOR = { note: 'blue', tip: 'green', important: 'magenta', warning: 'yellow', caution: 'red' } as const

const renderParagraph = (el: ElementTable, style: Style, block: Extract<Block, { kind: 'paragraph' }>, columns: number, key: string) => {
  const { Box, Text } = el
  const rtl = flowOf(style, block.inline, columns)
  if (rtl?.base === 'R') return <Box key={key} flexDirection="column" alignItems="flex-end">{renderFlow(el, style, rtl.lines, key)}</Box>
  return <Text key={key} bold={style.narration}>{renderInline(el, style, rtl ? rtl.lines[0]! : block.inline, key)}</Text>
}

const renderQuote = (el: ElementTable, style: Style, block: Extract<Block, { kind: 'quote' }>, columns: number, key: string) => {
  const { Box, Text } = el
  const t = style.theme
  const rtl = flowOf(style, block.inline, columns - 2)
  if (rtl?.base === 'R') {
    return (
      <Box key={key} flexDirection="row" justifyContent="flex-end">
        <Box flexDirection="column" alignItems="flex-end">{renderFlow(el, style, rtl.lines, key, { italic: true, color: t.quote })}</Box>
        <Text color={t.accent}> │</Text>
      </Box>
    )
  }
  return (
    <Box key={key} flexDirection="row">
      <Text color={t.accent}>│ </Text>
      <Text italic color={t.quote}>{renderInline(el, style, rtl ? rtl.lines[0]! : block.inline, key)}</Text>
    </Box>
  )
}

const renderAlert = (el: ElementTable, style: Style, block: Extract<Block, { kind: 'alert' }>, columns: number, key: string) => {
  const { Box, Text } = el
  const color = ALERT_COLOR[block.level]
  const title = <Text bold color={color}>{block.level[0]!.toUpperCase() + block.level.slice(1)}</Text>
  const rtl = flowOf(style, block.inline, columns - 4)
  if (rtl?.base === 'R') {
    return (
      <Box key={key} flexDirection="column" alignSelf="flex-end" alignItems="flex-end" borderStyle="round" borderColor={color} paddingX={1}>
        {title}
        {renderFlow(el, style, rtl.lines, key)}
      </Box>
    )
  }
  const inline = rtl ? rtl.lines[0]! : block.inline
  return (
    <Box key={key} flexDirection="column" alignSelf="flex-start" borderStyle="round" borderColor={color} paddingX={1}>
      {title}
      {inline.length ? <Text>{renderInline(el, style, inline, key)}</Text> : null}
    </Box>
  )
}

const TASK_GLYPHS = { checks: ['[ ]', '[✓]'], ticks: ['○', '✓'], box: ['□', '✓'], progress: ['○', '✓'] } as const

const renderList = (el: ElementTable, style: Style, block: Extract<Block, { kind: 'list' }>, columns: number, key: string) => {
  const { Box, Text } = el
  const t = style.theme
  const tasks = block.items.filter(item => item.task !== undefined)
  const done = tasks.filter(item => item.task).length
  const filled = tasks.length ? Math.round((done / tasks.length) * 20) : 0
  const strike = style.taskStyle === 'checks' || style.taskStyle === 'box'
  const tick = style.taskStyle === 'ticks' || style.taskStyle === 'progress'
  return (
    <Box key={key} flexDirection="column">
      {style.taskStyle === 'progress' && tasks.length > 0 && (
        <Text>
          <Text color={t.accent}>{'━'.repeat(filled)}</Text>
          <Text color={t.bullet} dimColor>{'─'.repeat(20 - filled)}</Text>
          <Text color={t.bullet}>{` ${done}/${tasks.length} done`}</Text>
        </Text>
      )}
      {block.items.map((item, i) => {
        const k = `${key}.${i}`
        const glyph = item.task !== undefined ? TASK_GLYPHS[style.taskStyle][item.task ? 1 : 0] : /\d/.test(item.marker) ? item.marker : item.depth ? '◦' : '•'
        const glyphColor = item.task && tick ? t.accent : t.bullet
        const rtl = flowOf(style, item.inline, columns - item.depth * 2 - glyph.length - 1)
        if (rtl?.base === 'R') {
          return (
            <Box key={k} flexDirection="row" justifyContent="flex-end" paddingRight={item.depth * 2}>
              <Box flexDirection="column" alignItems="flex-end">{renderFlow(el, style, rtl.lines, k)}</Box>
              <Text color={glyphColor}>{` ${glyph}`}</Text>
            </Box>
          )
        }
        return (
          <Box key={k} flexDirection="row" paddingLeft={item.depth * 2}>
            <Text color={glyphColor}>{`${glyph} `}</Text>
            <Text dimColor={item.task === true} strikethrough={item.task === true && strike}>{renderInline(el, style, rtl ? rtl.lines[0]! : item.inline, k)}</Text>
          </Box>
        )
      })}
    </Box>
  )
}

export type CopyButton = (text: string | (() => string), key: string, label?: string) => RenderElement | null
export type Drawn = Map<number, { element: RenderElement; art: string }>

const copySource = (block: Block): string | undefined =>
  block.kind === 'code' ? block.lines.join('\n') : block.kind === 'table' || block.kind === 'list' ? block.raw : block.kind === 'quote' || block.kind === 'alert' ? block.raw.split('\n').map(line => line.replace(/^\s*>\s?/, '')).join('\n') : undefined

export const renderBlocks = (el: ElementTable, style: Style, blocks: Block[], columns: number, drawn: Drawn = new Map(), copy?: CopyButton, png?: CopyButton): RenderElement[] => {
  const { Box, Text } = el
  const t = style.theme
  const rendered = blocks.map((block, b) => {
    const key = `b${b}`
    switch (block.kind) {
      case 'heading':
        return renderHeading(el, style, block, key)
      case 'paragraph':
        return renderParagraph(el, style, block, columns, key)
      case 'quote':
        return renderQuote(el, style, block, columns, key)
      case 'alert':
        return renderAlert(el, style, block, columns, key)
      case 'rule':
        return <Text key={key} color={t.rule} dimColor={!t.rule}>{'─'.repeat(Math.max(8, Math.min(columns, 80)))}</Text>
      case 'code':
        return drawn.get(b)?.element ?? (
          <Box key={key} flexDirection="column" alignSelf="flex-start">
            <Box flexDirection="row" justifyContent="space-between" columnGap={4}>
              <Text color={t.codeComment}>{`── ${block.lang || 'code'}`}</Text>
              {copy?.(block.lines.join('\n'), `copy${b}`) ?? null}
            </Box>
            <Box flexDirection="column" paddingLeft={2}>
              {(isShellLang(block.lang) ? null : highlightBlock(el, style, block.lines, block.lang, key)) ?? block.lines.map((line, i) => codeLine(el, style, line, block.lang, `${key}.${i}`))}
            </Box>
          </Box>
        )
      case 'list':
        return renderList(el, style, block, columns, key)
      case 'table':
        return renderTable(el, style, block, columns, key)
    }
  })
  const copied = rendered.map((element, b) => {
    const block = blocks[b]
    const text = block ? copySource(block) : undefined
    const isPlainCode = block?.kind === 'code' && !drawn.has(b)
    const art = drawn.get(b)?.art ?? (block?.kind === 'table' ? () => tableArt(block) : undefined)
    const first = text === undefined || isPlainCode ? null : copy?.(text, `copy${b}`, art === undefined || block?.kind === 'table' ? undefined : '⧉ source')
    const second = first && art !== undefined ? copy?.(art, `art${b}`, '⧉ art') : null
    const third = second && art !== undefined ? png?.(art, `png${b}`, '▣ png') : null
    const button = second ? (
      <el.Box key={`copies${b}`} flexDirection="row" columnGap={1}>
        {first}
        {second}
        {third}
      </el.Box>
    ) : first
    if (!button) return element
    const { Box } = el
    const rtl = style.reorder && block !== undefined && hasRtl(block.raw)
    return block?.kind === 'quote' || block?.kind === 'alert' ? (
      <Box key={`c${b}`} flexDirection="row" columnGap={2} {...(rtl ? { justifyContent: 'flex-end' as const } : {})}>
        {element}
        {button}
      </Box>
    ) : (
      <Box key={`c${b}`} flexDirection="column" {...(rtl && (block?.kind === 'list' || (block?.kind === 'table' && isRtlTable(style, block))) ? {} : { alignSelf: 'flex-start' as const })}>
        <Box justifyContent="flex-end">{button}</Box>
        {element}
      </Box>
    )
  })
  const isFigure = (b: number) => blocks[b]?.kind === 'table' || drawn.has(b)
  const out: RenderElement[] = []
  for (let b = 0; b < rendered.length; b++) {
    if (!isFigure(b) || !isFigure(b + 1)) {
      out.push(copied[b]!)
      continue
    }
    const start = b
    while (isFigure(b + 1)) b++
    out.push(
      <Box key={`row${start}`} flexDirection="row" flexWrap="wrap" columnGap={4} rowGap={1}>
        {copied.slice(start, b + 1).map((figure, i) => <Box key={`f${start + i}`} flexShrink={0}>{figure}</Box>)}
      </Box>,
    )
  }
  return out
}

export type ToolRow = { tool: string; input: unknown; isRunning: boolean; isErrored: boolean; isInterrupted: boolean }

const VERBS: Record<string, string> = {
  Bash: 'Ran', PowerShell: 'Ran', Read: 'Read', Write: 'Wrote', Edit: 'Edited', MultiEdit: 'Edited', NotebookEdit: 'Edited',
  Grep: 'Searched', Glob: 'Listed', WebFetch: 'Fetched', WebSearch: 'Searched the web for', Agent: 'Delegated', Task: 'Delegated',
}

const field = (input: unknown, ...keys: string[]): string | undefined => {
  if (input === null || typeof input !== 'object') return undefined
  for (const k of keys) {
    const v = (input as Record<string, unknown>)[k]
    if (typeof v === 'string' && v.trim() !== '') return v
  }
  return undefined
}

const toolDim = (style: Style) => style.toolStyle !== "classic"

const toolGutter = ({ Box, Text }: ElementTable, style: Style, color: string | undefined, running: boolean) =>
  style.toolStyle.startsWith("tree")
    ? <Box width={4} flexShrink={0}><Text color={color}>{'  ⎿ '}</Text></Box>
    : <Box width={2} flexShrink={0}><Text color={color}>{running ? '◌' : '●'}</Text></Box>

const toolLayout = (el: ElementTable, style: Style, columns: number, label: string, color: string | undefined, running: boolean, text: RenderElement) => {
  const { Box, Text } = el
  if (style.toolStyle !== "chat") return <Box flexDirection="row">{toolGutter(el, style, color, running)}{text}</Box>
  const w = Math.min(width(label) + 2, Math.max(20, Math.floor(columns * 0.6)))
  return (
    <Box flexDirection="row" justifyContent="flex-end" width="100%">
      <Box width={w} flexDirection="row">{text}<Text color={color}>{running ? " ◌" : " ●"}</Text></Box>
    </Box>
  )
}

export const renderToolRow = (el: ElementTable, style: Style, row: ToolRow, columns = 100): RenderElement => {
  const { Box, Text } = el
  const t = style.theme
  const isShell = row.tool === 'Bash' || row.tool === 'PowerShell'
  const verb = VERBS[row.tool] ?? row.tool.replace(/^mcp__([^_]+)__/, '$1 ')
  const target = isShell
    ? field(row.input, 'command')?.split('\n')[0]
    : field(row.input, 'file_path', 'notebook_path', 'path', 'pattern', 'url', 'query', 'description')
  const dot = row.isErrored ? t.codeFlag : row.isInterrupted ? t.codeComment : row.isRunning ? t.accent : t.number
  const isPath = target !== undefined && /^(~|\.{0,2}\/|[A-Za-z]:\\)/.test(target)

  const label = `${verb}${target === undefined ? "" : ` ${target}`}${row.isInterrupted ? " interrupted" : row.isErrored ? " failed" : ""}`
  return toolLayout(el, style, columns, label, dot, row.isRunning, (
      <Text wrap="truncate-end" dimColor={toolDim(style)}>
        <Text bold={!toolDim(style)} dimColor={toolDim(style)}>{verb}</Text>
        {target === undefined ? null : <Text> </Text>}
        {target === undefined ? null : isShell ? codeLine(el, style, target, 'bash', 'cmd') : <Text color={isPath ? t.path : t.inlineCode} dimColor={toolDim(style)}>{target}</Text>}
        {row.isInterrupted ? <Text dimColor> interrupted</Text> : row.isErrored ? <Text color={t.codeFlag}> failed</Text> : null}
      </Text>
  ))
}

const OUTPUT_LINES = 120

const lines = (value: unknown): string[] => (typeof value === 'string' && value !== '' ? value.replace(/\n$/, '').split('\n') : [])

export const renderExpandedShell = (el: ElementTable, style: Style, row: ToolRow & { output?: unknown }): RenderElement => {
  const { Box, Text } = el
  const t = style.theme
  const command = (field(row.input, 'command') ?? '').split('\n')
  const out = row.output !== null && typeof row.output === 'object' ? (row.output as Record<string, unknown>) : {}
  const stdout = lines(out.stdout)
  const stderr = lines(out.stderr)
  const shown = [...stdout.map(text => ({ text, color: undefined as string | undefined })), ...stderr.map(text => ({ text, color: t.codeFlag as string | undefined }))]
  const visible = shown.slice(0, OUTPUT_LINES)
  const dot = row.isErrored ? t.codeFlag : row.isInterrupted ? t.codeComment : row.isRunning ? t.accent : t.number
  return (
    <Box flexDirection="column">
      <Box flexDirection="row">
        <Box width={2} flexShrink={0}>
          <Text color={dot}>{row.isRunning ? '◌' : '●'}</Text>
        </Box>
        <Box flexDirection="column">
          {command.map((line, i) => (
            <Text key={`c${i}`}>
              {i === 0 ? <Text bold>{`${row.tool}(`}</Text> : null}
              {codeLine(el, style, line, 'bash', `cmd${i}`)}
              {i === command.length - 1 ? <Text bold>)</Text> : null}
            </Text>
          ))}
        </Box>
      </Box>
      {row.isRunning ? null : (
        <Box paddingLeft={2}>
          <Box flexDirection="column" alignSelf="flex-start" borderStyle="round" borderColor={t.codeComment} paddingX={1}>
            {visible.length === 0 ? <Text dimColor>(No output)</Text> : visible.map((l, i) => <Text key={`o${i}`} color={l.color}>{l.text === '' ? ' ' : l.text}</Text>)}
            {shown.length > visible.length ? <Text dimColor>{`\u2026 +${shown.length - visible.length} lines`}</Text> : null}
          </Box>
        </Box>
      )}
    </Box>
  )
}

const GROUPS: [RegExp, string, string][] = [
  [/^(Bash|PowerShell)$/, 'ran', 'command'],
  [/^Read$/, 'read', 'file'],
  [/^(Write|Edit|MultiEdit|NotebookEdit)$/, 'edited', 'file'],
  [/^(Grep|Glob)$/, 'searched', 'pattern'],
  [/^(WebFetch|WebSearch)$/, 'fetched', 'page'],
  [/^(Agent|Task)$/, 'delegated', 'task'],
]

export const groupSummary = (calls: readonly { tool: string }[]): string => {
  const counts = new Map<string, number>()
  for (const call of calls) {
    const [, verb, noun] = GROUPS.find(([re]) => re.test(call.tool)) ?? [, 'used', call.tool.replace(/^mcp__([^_]+)__/, '$1 ')]
    const label = `${verb} ${noun}`
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }
  const parts = [...counts].map(([label, n]) => {
    const [verb, ...noun] = label.split(' ')
    const name = noun.join(' ')
    return `${verb} ${n} ${n === 1 ? name : name.endsWith('h') ? `${name}es` : `${name}s`}`
  })
  const text = parts.join(', ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export const renderToolGroup = (el: ElementTable, style: Style, calls: readonly ToolRow[], isActive: boolean, columns = 100): RenderElement => {
  const { Box, Text } = el
  const t = style.theme
  const failed = calls.filter(c => c.isErrored).length
  const running = isActive && calls.some(c => c.isRunning)
  const dot = failed ? t.codeFlag : running ? t.accent : t.number
  const last = calls[calls.length - 1]
  const lastTarget = last ? field(last.input, 'command', 'file_path', 'notebook_path', 'path', 'pattern', 'url', 'query', 'description')?.split('\n')[0] : undefined
  const label = `${groupSummary(calls)}${failed ? ` · ${failed} failed` : ""}${lastTarget ? ` · last: ${lastTarget}` : ""}`
  return toolLayout(el, style, columns, label, dot, running, (
      <Text wrap="truncate-end" dimColor={toolDim(style)}>
        <Text bold={!toolDim(style)} dimColor={toolDim(style)}>{groupSummary(calls)}</Text>
        {failed ? <Text color={t.codeFlag}>{` · ${failed} failed`}</Text> : null}
        {lastTarget ? <Text dimColor>{` · last: ${lastTarget}`}</Text> : null}
      </Text>
  ))
}

export const formatDuration = (ms: number): string => {
  const s = Math.round(ms / 1000)
  if (s < 60) return `${Math.max(s, 0)}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

export const renderTurnDuration = ({ Text }: ElementTable, style: Style, word: string, durationMs: number): RenderElement => (
  <Text color={style.theme.codeComment}>
    {`✻ ${word} for `}
    <Text color={style.theme.number}>{formatDuration(durationMs)}</Text>
  </Text>
)

export const renderUserPrompt = (el: ElementTable, style: Style, text: string, columns: number): RenderElement => {
  const { Box, Text } = el
  const t = style.theme
  const color = style.promptStyle === 'chevron' ? t.accent : t.heading
  const lines = text.split('\n').map(line => flowOf(style, [{ kind: 'text', text: line }], columns - 4))
  const rtl = lines.some(l => l?.base === 'R')
  const body = (
    <Box flexDirection="column" {...(rtl ? { alignItems: 'flex-end' as const } : {})}>
      {text.split('\n').map((line, i) => {
        const flow = lines[i]
        return flow ? renderFlow(el, style, flow.lines, `p${i}`, { color, bold: style.promptStyle === 'chevron' }) : <Text key={`p${i}`} color={color} bold={style.promptStyle === 'chevron'}>{line}</Text>
      })}
    </Box>
  )
  if (style.promptStyle === 'bubble') {
    return <Box borderStyle="round" borderColor={t.accent} paddingX={1} alignSelf={rtl ? 'flex-end' : 'flex-start'}>{body}</Box>
  }
  const mark = <Text color={t.accent} bold>{style.promptStyle === 'bar' ? (rtl ? ' ▐' : '▌ ') : rtl ? ' ‹' : '› '}</Text>
  return <Box flexDirection="row" {...(rtl ? { justifyContent: 'flex-end' as const } : {})}>{rtl ? body : mark}{rtl ? mark : body}</Box>
}
