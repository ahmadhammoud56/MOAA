import type { ElementTable, RenderElement } from 'claude-code'

import type { ChartArt } from './charts'
import { ganttText, pieText } from './charts'
import { drawFigure, isFigureLang } from './figure'
import type { Block } from './markdown'
import type { Drawn } from './render'
import { cells, graphemes, heldLtr, mirrored, remember, width } from './render'
import { asIs, hasRtl, holdEngine, holdRow, holdVisual, led } from './rtl'
import type { Style, Theme } from './theme'
import { renderMermaidAscii, setChartSize } from './vendor/mermaid-text.js'

const MAX_LINES = 80
const PAD = '\uFDD0'
const textCache = new Map<string, string | null>()

export const chartSize = (columns: number, source = '') => {
  const labels = (/^\s*x-axis\b[^[\n]*\[([^\]\n]*)\]/m.exec(source)?.[1] ?? '').split(',').map(s => s.trim().replace(/^"|"$/g, ''))
  const fit = labels.length * (Math.max(...labels.map(l => l.length)) + 2)
  const width = Math.max(24, Math.min(60, Math.max(Math.floor(columns / 6), fit), columns - 12))
  return { width, height: Math.max(8, Math.min(20, Math.round(width * 0.3))) }
}

const padWide = (source: string) => (/^[\x00-\x7F]*$/.test(source) ? source : graphemes(source).map(g => (g.length === 1 && width(g) === 2 ? g + PAD : g)).join(''))

const unquoteCategories = (source: string) =>
  source.replace(/^(\s*x-axis\b[^[\n]*\[)([^\]\n]*)\]/m, (_, head: string, items: string) => `${head}${items.replace(/"([^"]*)"/g, (_q, s: string) => s.replaceAll(',', ' '))}]`)

const BLOCK = /[█▀▄]/

const labelBars = (art: string, source: string): string => {
  const series = source.match(/^\s*(bar|line)\b.*$/gm) ?? []
  const values = /^\s*bar\b[^[\n]*\[([^\]\n]*)\]/m.exec(source)?.[1]?.split(',').map(v => v.trim())
  if (series.length !== 1 || !values || /^\s*xychart(-beta)?\s+horizontal/m.test(source)) return art
  const grid = ['', ...art.split('\n')].map(l => [...l])
  const gutter = (r: number) => /^\s*(-?[\d.]+)[┤┼]/.exec(grid[r]?.join('') ?? '')?.[1]
  const axis = grid.findLastIndex((_, r) => gutter(r) !== undefined)
  const ticks = [...(grid[axis]?.join('') ?? '').matchAll(/┬|▀+/g)].map(m => m.index + Math.floor(m[0].length / 2))
  if (ticks.length !== values.length) return art
  const zero = grid.findIndex((_, r) => gutter(r) === '0')
  const top = grid.findIndex((_, r) => gutter(r) !== undefined)
  const base = zero !== -1 ? zero : gutter(top)?.startsWith('-') ? top : axis
  ticks.forEach((x, k) => {
    const filled = grid.flatMap((row, r) => (BLOCK.test(row[x] ?? '') ? [r] : []))
    const y = Number(values[k]) < 0 ? (filled.at(-1) ?? base) + 1 : (filled[0] ?? base) - 1
    const text = [...values[k]!]
    const bar = grid[filled[0] ?? -1] ?? []
    let [left, right] = [x, x]
    while (BLOCK.test(bar[left - 1] ?? '')) left--
    while (BLOCK.test(bar[right + 1] ?? '')) right++
    const from = left + Math.ceil((right - left + 1 - text.length) / 2)
    const row = y < axis ? grid[y] : undefined
    if (!row) return
    while (row.length < from + text.length) row.push(' ')
    if (!text.every((_, i) => /[ ·]/.test(row[from + i] ?? ' '))) return
    text.forEach((ch, i) => (row[from + i] = ch))
  })
  return grid.map(row => row.join('').trimEnd()).join('\n').replace(/^\n/, '')
}

const SIDEWAYS = /^(\s*(?:flowchart|graph)[ \t]+)(LR|RL)\b/

const SUPPORTED = /^(flowchart|graph|statediagram(-v2)?|xychart(-beta)?|sequencediagram|classdiagram|erdiagram|pie|gantt)$/i

const kindOf = (source: string) => source.replace(/^(\s*%%[^\n]*\n)+/, '').trim().split(/\s/)[0] ?? ''

const unsupportedKind = (source: string): string | undefined => {
  const kind = kindOf(source)
  return kind && !SUPPORTED.test(kind) ? kind : undefined
}

const OWN: Record<string, typeof pieText> = {
  pie: pieText,
  gantt: (source, ascii, columns) => {
    const text = ganttText(source, ascii, columns)
    return text === null ? null : { text }
  },
}

const INLINE_TAG = /<\/?(?:b|i|u|s|em|strong|del|code|small|sub|sup|span|mark)\b[^<>\n]*>/gi

type Mark = { italic?: boolean; bold?: boolean; underline?: boolean; strikethrough?: boolean }
const TAG_MARK: Record<string, keyof Mark> = { i: 'italic', em: 'italic', b: 'bold', strong: 'bold', u: 'underline', s: 'strikethrough', del: 'strikethrough' }

export const inlineMarks = (source: string): [string[], Mark][] =>
  [...source.matchAll(/<(i|em|b|strong|u|s|del)\b[^<>\n]*>([^<\n]+)<\/\1\s*>/gi)]
    .map(m => [cells(m[2]!.trim()), { [TAG_MARK[m[1]!.toLowerCase()]!]: true }] as [string[], Mark])

const fitted = new Map<string, ChartArt | null>()
const artWidths = new Map<string, number>()
const artWidth = (art: string) => remember(artWidths, art, () => Math.max(...art.split('\n').map(width)))

export const mermaidText = (source: string, ascii: boolean, columns: number, pieColors = 0): string | null => mermaidArt(source, ascii, columns, pieColors)?.text ?? null

const mermaidArt = (source: string, ascii: boolean, columns: number, pieColors: number): ChartArt | null =>
  remember(fitted, `${ascii}:${columns}:${pieColors}:${source}`, () => {
    source = source.replace(INLINE_TAG, '')
    if (source.length > 8000 || source.split('\n').length > MAX_LINES) return null
    const own = OWN[kindOf(source).toLowerCase()]
    if (own) return own(source, ascii, columns, pieColors)
    const art = draw(source, ascii, columns)
    const text = art === null || artWidth(art) <= columns - 2 || !SIDEWAYS.test(source) ? art : (draw(source.replace(SIDEWAYS, '$1TD'), ascii, columns) ?? art)
    return text === null ? null : { text, series: chartSeries(source, ascii, columns) }
  })

const prepared = (padded: string) => unquoteCategories(padded.replace(/^(\s*%%[^\n]*\n)+/, '')).replace(/(-->|-\.->|==>|---|-\.-|===)[ \t]+\|/g, '$1|')

const NEUTRAL = '#808080'
const PROBE = { fg: NEUTRAL, border: NEUTRAL, line: NEUTRAL, arrow: NEUTRAL, corner: NEUTRAL, junction: NEUTRAL, accent: '#ff0000', bg: '#000000' }
const SGR = /\x1b\[([\d;]*)m/g

const seriesOf = (colored: string): number[][] => {
  const hues = colored.split('\n').map(line => {
    const row: (string | undefined)[] = []
    let hue: string | undefined
    let at = 0
    const take = (text: string) => graphemes(text).forEach(() => row.push(hue))
    for (const m of line.matchAll(SGR)) {
      take(line.slice(at, m.index))
      hue = m[1]!.startsWith('38;2;') && m[1] !== '38;2;128;128;128' ? m[1] : undefined
      at = m.index + m[0].length
    }
    take(line.slice(at))
    return row
  })
  const legend = hues.find(row => row.some(Boolean)) ?? []
  const order = [...new Set(legend.filter((h): h is string => h !== undefined))]
  return hues.map(row => row.map(h => (h === undefined ? -1 : order.indexOf(h))))
}

const seriesCache = new Map<string, number[][] | null>()

const chartSeries = (source: string, ascii: boolean, columns: number): number[][] | undefined => {
  if (!/^\s*xychart/.test(source) || (source.match(/^\s*(bar|line)\b/gm) ?? []).length < 2) return undefined
  const padded = padWide(source)
  const size = chartSize(columns, padded)
  return remember(seriesCache, `${ascii}:${size.width}:${source}`, () => {
    try {
      setChartSize(size.width, size.height)
      return seriesOf(renderMermaidAscii(prepared(padded), { useAscii: ascii, colorMode: 'truecolor', theme: PROBE, paddingX: 3, paddingY: 1 }))
    } catch {
      return null
    }
  }) ?? undefined
}

const draw = (source: string, ascii: boolean, columns: number): string | null => {
  const isChart = /^\s*xychart/.test(source)
  const padded = padWide(source)
  const size = chartSize(columns, isChart ? padded : '')
  const key = `${ascii}:${isChart ? size.width : 0}:${source}`
  return remember(textCache, key, () => {
    try {
      if (isChart) setChartSize(size.width, size.height)
      const art = renderMermaidAscii(prepared(padded), { useAscii: ascii, colorMode: 'none', paddingX: 3, paddingY: 1 }).replace(/[ \t]+$/gm, '').trimEnd().replace(/▶/g, '►').replace(/◀/g, '◄')
      return (isChart ? labelBars(art, padded) : art.split('\n').filter(l => !/^[\s│|]*$/.test(l)).join('\n')).replaceAll(PAD, '')
    } catch {
      return null
    }
  })
}

const LINE = /[─-╿◇▏]/
const ARROW = /[►◄▲▼]/
const PART = /[▐▏▎▍▌▋▊▉]/

const barStart = (row: string[], c: number): number => {
  const ch = row[c] ?? ''
  const solid = BLOCK.test(ch) ? ch : PART.test(ch) && row[c + 1] === '█' ? '█' : PART.test(ch) && row[c - 1] === '█' ? '█' : ''
  if (!solid) return -1
  let start = BLOCK.test(ch) ? c : row[c + 1] === '█' ? c + 1 : c - 1
  while (row[start - 1] === solid) start--
  return start
}

type Painted = { grid: string[][]; colors: (string | undefined)[][] }

export const diagramPalette = (t: Theme): string[] => [...new Set([t.link, t.number, t.heading, t.emphasis, t.path, t.codeFlag, t.accent])].filter((c): c is string => c !== undefined)

const paint = (art: string, style: Style, series?: number[][]): Painted => {
  const t = style.theme
  const grid = art.split('\n').map(cells)
  const cell = (r: number, c: number) => grid[r]?.[c] ?? ''
  const color: (string | undefined)[][] = grid.map(row => row.map(() => undefined))
  const palette = diagramPalette(t)
  const next = (i: number) => palette[i % palette.length]
  const labels = new Map<string, string | undefined>()

  const rects: { r: number; c: number; r2: number; c2: number }[] = []
  for (let r = 0; r < grid.length; r++) {
    for (let c = 0; c < (grid[r]?.length ?? 0); c++) {
      if (!/[┌╭(]/.test(cell(r, c))) continue
      let c2 = c + 1
      while (/[─┬┴┼▲▼]/.test(cell(r, c2))) c2++
      if (!/[┐╮)]/.test(cell(r, c2)) || c2 === c + 1) continue
      let r2 = r + 1
      while (/[│├┤┼►◄]/.test(cell(r2, c))) r2++
      if (!/[└╰(]/.test(cell(r2, c)) || !/[┘╯)]/.test(cell(r2, c2))) continue
      rects.push({ r, c, r2, c2 })
    }
  }
  const inside = (a: (typeof rects)[number], b: (typeof rects)[number]) => a !== b && b.r > a.r && b.r2 < a.r2 && b.c > a.c && b.c2 < a.c2
  for (const box of rects.filter(a => !rects.some(b => inside(a, b)))) {
    const { r, c, r2, c2 } = box
    const label = grid.slice(r + 1, r2).map(row => row.slice(c + 1, c2).join('')).join(' ').trim()
    if (!labels.has(label)) labels.set(label, next(labels.size))
    const hue = labels.get(label)
    for (let y = r; y <= r2; y++) for (let x = c; x <= c2; x++) if (cell(y, x).trim()) color[y]![x] = hue
  }

  const bars = [...new Set(grid.flatMap(row => row.flatMap((ch, c) => (BLOCK.test(ch) && row[c - 1] !== ch ? [c] : []))))].sort((a, b) => a - b)
  const ends = bars.map(x => {
    const row = grid.find(row => BLOCK.test(row[x] ?? ''))!
    let end = x
    while (row[end + 1] === row[x]) end++
    return end
  })
  const tops = bars.map(x => {
    const r = grid.findIndex(row => BLOCK.test(row[x] ?? ''))
    return r * 2 + (grid[r]![x] === '▄' ? 1 : 0)
  })
  const single = bars.length > 1 && bars.every((x, i) => i === 0 || x - ends[i - 1]! > 2)
  const barColor = (i: number) => (single ? (tops[i] === Math.min(...tops) ? t.emphasis ?? t.accent : t.quote) : next(i))
  series?.forEach((row, r) => row.forEach((owner, c) => owner >= 0 && grid[r]?.[c]?.trim() && (color[r]![c] = next(owner))))
  grid.forEach((row, r) =>
    row.forEach((ch, c) => {
      if (color[r]![c] !== undefined) return
      const start = barStart(row, c)
      if (start >= 0) color[r]![c] = barColor(bars.indexOf(start))
      else if (ch === '·') color[r]![c] = t.rule
      else if (ARROW.test(ch)) color[r]![c] = t.accent
      else if (LINE.test(ch)) color[r]![c] = t.diagram
      else if (/^\d+[┤┼]/.test(row.slice(c).join(''))) color[r]![c] = t.number
      else color[r]![c] = t.diagramText
    }),
  )
  return { grid, colors: color }
}

const paintPie = (art: string, slices: number[][], style: Style): Painted => {
  const t = style.theme
  const palette = diagramPalette(t)
  const grid = art.split('\n').map(cells)
  const hue = (slice: number) => (slice < 0 ? t.diagramText : palette[slice % palette.length])
  return { grid, colors: grid.map((row, r) => row.map((_, c) => hue(slices[r]?.[c] ?? -1))) }
}

const painted = new WeakMap<Theme, Map<string, Painted>>()

const piePainted = new WeakMap<Theme, WeakMap<number[][], Painted>>()

const painting = (style: Style, art: string, slices?: number[][], series?: number[][]): Painted => {
  if (!slices) {
    const cache = painted.get(style.theme) ?? new Map<string, Painted>()
    painted.set(style.theme, cache)
    return remember(cache, art, () => paint(art, style, series))
  }
  const cache = piePainted.get(style.theme) ?? new WeakMap<number[][], Painted>()
  piePainted.set(style.theme, cache)
  const done = cache.get(slices) ?? paintPie(art, slices, style)
  cache.set(slices, done)
  return done
}

export const boxArt = ({ Box, Text }: ElementTable, style: Style, art: string, key: string, marks: [string[], Mark][] = [], slices?: number[][], series?: number[][]): RenderElement => {
  const { grid, colors } = painting(style, art, slices, series)
  const visual = style.reorder && style.shape === 'visual' && hasRtl(art)
  return (
    <Box key={key} flexDirection="column" paddingLeft={mirrored(style) ? 0 : 2}>
      {grid.map((row, i) => {
        const { cells: chars, from } = mirrored(style) ? led(row, holdRow(row)) : style.shape === 'engine' ? holdEngine(row) : visual ? holdVisual(row) : asIs(row)
        const marked: (Mark | undefined)[] = row.map(() => undefined)
        for (const [phrase, mark] of marks)
          for (let c = 0; c + phrase.length <= row.length; c++)
            if (phrase.every((ch, k) => row[c + k] === ch)) for (let k = 0; k < phrase.length; k++) marked[c + k] = mark
        const hueAt = (p: number) => colors[i]?.[from[p]!]
        const markAt = (p: number) => marked[from[p]!]
        const parts: RenderElement[] = []
        let at = 0
        while (at < chars.length) {
          const hue = hueAt(at)
          const mark = markAt(at)
          let end = at + 1
          while (end < chars.length && hueAt(end) === hue && markAt(end) === mark) end++
          parts.push(<Text key={`t${parts.length}`} color={hue} {...mark}>{chars.slice(at, end).join('')}</Text>)
          at = end
        }
        return <Text key={`${key}.${i}`} {...heldLtr(style)}>{parts.length ? parts : ' '}</Text>
      })}
    </Box>
  )
}

const EDGE_LABEL = /(-[-.=]+\s*)"([^"\n]+)"(\s*[-.=]+>)|\|([^|\n]+)\|/g

const cap = (label: string, max: number) => {
  const flat = label.replace(/<br\s*\/?>/gi, ' ').replace(/\s+/g, ' ').trim()
  const chars = graphemes(flat)
  return chars.length > max ? `${chars.slice(0, max - 1).join('').trimEnd()}…` : flat
}

export const shortenEdgeLabels = (source: string, max: number): string =>
  source.replace(EDGE_LABEL, (_, open, quoted, close, piped) =>
    quoted !== undefined ? `${open}"${cap(quoted, max)}"${close}` : `|${cap(piped, max)}|`)

const pieColorsOf = (style: Style) => (style.pieStyle === 'round' ? diagramPalette(style.theme).length : 0)

export const drawDiagrams = (el: ElementTable, style: Style, blocks: Block[], columns: number): Drawn => {
  const drawn: Drawn = new Map()
  const pieColors = pieColorsOf(style)
  if (style.mermaid) {
    for (const [i, block] of blocks.entries()) {
      if (block.kind !== 'code' || block.lang.toLowerCase() !== 'mermaid') continue
      const source = block.lines.join('\n')
      let narrowest = Infinity
      for (const max of [Infinity, 24, 12]) {
        const art = mermaidArt(max === Infinity ? source : shortenEdgeLabels(source, max), style.mermaidAscii, columns, pieColors)
        const wide = art === null ? Infinity : artWidth(art.text)
        narrowest = Math.min(narrowest, wide)
        if (art === null || wide > columns - 2) continue
        drawn.set(i, { element: boxArt(el, style, art.text, `b${i}`, inlineMarks(source), art.slices, art.series), art: art.text })
        break
      }
      if (!drawn.has(i) && !block.isOpen) {
        const kind = unsupportedKind(source)
        drawn.set(i, { note: kind ? `${kind} diagrams draw as source for now` : narrowest === Infinity ? 'diagram failed to render' : `diagram is ${narrowest} cols, terminal is ${columns}` })
      }
    }
  }
  for (const [i, block] of blocks.entries()) {
    if (block.kind !== 'code' || !isFigureLang(block.lang)) continue
    const figure = drawFigure(el, style, block, columns, `b${i}`)
    if (figure) drawn.set(i, figure)
  }
  return drawn
}
