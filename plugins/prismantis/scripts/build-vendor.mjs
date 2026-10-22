import { build } from 'esbuild'
import { readFileSync } from 'node:fs'

const bundledPackages = new Set()
const track = result => {
  for (const input of Object.keys(result.metafile.inputs)) {
    const match = /node_modules\/((?:@[^/]+\/)?[^/]+)/.exec(input)
    if (match) bundledPackages.add(match[1])
  }
}

const XYCHART = /beautiful-mermaid\/src\/ascii\/xychart\.ts$/
const SIZE = ['const PLOT_WIDTH = 60', 'const PLOT_HEIGHT = 20']
const BAR_SCALE = [
  [
    `  const yTicks = niceTickValues(yRange.min, yRange.max)
  const yLabels = yTicks.map(v => formatTickValue(v))
  const yGutter = Math.max(...yLabels.map(l => l.length)) + 1

  const plotW = Math.max(PLOT_WIDTH, dataCount * 6)
  const plotH = PLOT_HEIGHT
`,
    `  const rawTicks = niceTickValues(yRange.min, yRange.max)
  const step = rawTicks.length > 1 ? rawTicks[1]! - rawTicks[0]! : Math.abs(yRange.max - yRange.min) || 1
  const lo = Math.floor(yRange.min / step + 1e-9) * step
  const hi = Math.max(lo + step, Math.ceil(yRange.max / step - 1e-9) * step)
  const intervals = Math.round((hi - lo) / step)
  const yTicks = Array.from({ length: intervals + 1 }, (_, i) => Math.round((lo + i * step) * 1e10) / 1e10)
  const yLabels = yTicks.map(v => formatTickValue(v))
  const yGutter = Math.max(...yLabels.map(l => l.length)) + 1

  const plotW = Math.max(PLOT_WIDTH, dataCount * 6)
  const perTick = Math.max(1, Math.round(PLOT_HEIGHT / intervals))
  const plotH = intervals * perTick
  const unit = step / perTick
  const level = (v: number): number => (v - lo) / unit
  const base = level(Math.min(Math.max(0, lo), hi))
  const zero = Math.round(base) - 1
`,
  ],
  [
    `  const valueToRow = (v: number): number => {
    const t = (v - yRange.min) / (yRange.max - yRange.min || 1)
    return Math.round(t * (plotH - 1))
  }
`,
    `  const valueToRow = (v: number): number => Math.min(plotH - 1, Math.max(-1, Math.round(level(v)) - 1))
`,
  ],
  [
    `    const row = valueToRow(tick)
    if (row < 0 || row >= plotH) continue
    const displayRow = plotTop + (plotH - 1 - row)
    const label = formatTickValue(tick)
    // Tick mark on axis
    set(canvas, roles, displayRow, plotLeft - 1, row === 0 ? ch.origin : ch.yTick, 'border')
`,
    `    const row = Math.round(level(tick)) - 1
    if (row < -1 || row >= plotH) continue
    const displayRow = plotTop + (plotH - 1 - row)
    const label = formatTickValue(tick)
    set(canvas, roles, displayRow, plotLeft - 1, row === -1 || row === zero ? ch.origin : ch.yTick, 'border')
`,
  ],
  [
    `    const row = valueToRow(tick)
    if (row < 0 || row >= plotH) continue
    const displayRow = plotTop + (plotH - 1 - row)
    for (let c = plotLeft; c < plotLeft + bandW * dataCount; c++) {
      if (get(canvas, displayRow, c) === ' ') {
        set(canvas, roles, displayRow, c, ch.grid, 'line')
`,
    `    const row = Math.round(level(tick)) - 1
    if (row < 0 || row >= plotH) continue
    const displayRow = plotTop + (plotH - 1 - row)
    for (let c = plotLeft; c < plotLeft + bandW * dataCount; c++) {
      if (get(canvas, displayRow, c) === ' ') {
        set(canvas, roles, displayRow, c, row === zero ? ch.hLine : ch.grid, row === zero ? 'border' : 'line')
`,
  ],
  [
    `    const baseRow = valueToRow(Math.max(0, yRange.min))
`,
    '',
  ],
  [
    `        const valRow = valueToRow(entry.data[i]!)
        const fromRow = Math.min(baseRow, valRow)
        const toRow = Math.max(baseRow, valRow)

        for (let row = fromRow; row <= toRow; row++) {
          const displayRow = plotTop + (plotH - 1 - row)
          for (let c = bx; c < bx + singleBarW; c++) {
            set(canvas, roles, displayRow, c, ch.bar, 'arrow', hexColors, hexColor)
          }
        }
`,
    `        const exact = level(entry.data[i]!)
        const value = exact < base ? Math.ceil(exact * 2 - 1e-9) / 2 : Math.floor(exact * 2 + 1e-9) / 2
        const from = Math.max(0, Math.min(base, value))
        const to = Math.min(plotH, Math.max(base, value))

        for (let row = -1; row < plotH; row++) {
          const low = from <= row + 0.5 + 1e-9 && to >= row + 1 - 1e-9
          const high = from <= row + 1 + 1e-9 && to >= row + 1.5 - 1e-9
          const glyph = ch === ASC ? (value < base ? high : low) && ch.bar : low && high ? ch.bar : low ? '▄' : high && '▀'
          if (!glyph) continue
          const displayRow = plotTop + (plotH - 1 - row)
          for (let c = bx; c < bx + singleBarW; c++) {
            set(canvas, roles, displayRow, c, glyph, 'arrow', hexColors, hexColor)
          }
        }
`,
  ],
  [
    `  const drawAt = (col: number, row: number, char: string) => {
    const displayRow = plotTop + (plotH - 1 - row)
    if (displayRow >= 0 && col >= plotLeft && col < plotLeft + plotTotalW) {
`,
    `  const drawAt = (col: number, row: number, char: string) => {
    const displayRow = plotTop + (plotH - 1 - row)
    if (displayRow >= 0 && col >= plotLeft && col < plotLeft + plotTotalW && ![ch.bar, '▀', '▄'].includes(get(canvas, displayRow, col))) {
`,
  ],
]
const XY_PARSER = /beautiful-mermaid\/src\/xychart\/parser\.ts$/
const SERIES_NAMES = ['bar', 'line'].map(kind => [
  `const ${kind}Match = line.match(/^${kind}\\s+\\[([^\\]]+)\\]/)`,
  `series.push({ type: '${kind}', data: parseNumericArray(${kind}Match[1]!) })`,
  `const ${kind}Match = line.match(/^${kind}\\s+(?:"([^"]*)"\\s*|([^\\s"[]+)\\s+)?\\[([^\\]]+)\\]/)`,
  `series.push({ type: '${kind}', name: ${kind}Match[1] ?? ${kind}Match[2], data: parseNumericArray(${kind}Match[3]!) })`,
])
const LEGEND_NAMES = [['label: `Bar ${barIdx + 1}`', 'label: s.name || `Bar ${barIdx + 1}`'], ['label: `Line ${lineIdx + 1}`', 'label: s.name || `Line ${lineIdx + 1}`']]
const CANVAS = /beautiful-mermaid\/src\/ascii\/canvas\.ts$/
const CANVAS_ANCHOR = 'export function isJunctionChar('
const CLEAR_LABEL_GAPS = `export function clearLabelGaps(canvas: Canvas, label: Canvas): void {
  for (let y = 0; y < (label[0]?.length ?? 0); y++) {
    const xs = label.map((col, x) => (col[y] !== ' ' ? x : -1)).filter(x => x >= 0)
    if (xs.length === 0) continue
    for (let x = xs[0]!; x <= xs[xs.length - 1]!; x++) {
      if (label[x]![y] === ' ' && !isAlphanumeric(canvas[x]![y]!)) canvas[x]![y] = ' '
    }
  }
}
`
const DRAW = /beautiful-mermaid\/src\/ascii\/draw\.ts$/
const DRAW_ANCHOR = '  graph.canvas = mergeCanvases(graph.canvas, zero, useAscii, ...labelCanvases)'
const DRAW_IMPORT = 'import { mkCanvas, copyCanvas,'
const PARSER = /beautiful-mermaid\/src\/parser\.ts$/
const NODE_ID_START = 'const NODE_PATTERNS'
const NODE_ID_END = 'const CLASS_SHORTHAND_REGEX'
const NODE_ID = '[\\w-]+'
const NODE_ID_BEFORE_ARROW = '(?:\\w|-(?![-.>]))+'

const PRISM_LANGUAGES = ['clike', 'markup', 'css', 'javascript', 'typescript', 'jsx', 'tsx', 'python', 'go', 'rust', 'java', 'kotlin', 'swift', 'c', 'cpp', 'csharp', 'ruby', 'json', 'yaml', 'toml', 'sql', 'diff', 'docker', 'hcl', 'lua']

track(await build({
  metafile: true,
  stdin: {
    contents: [
      "const Prism = require('./node_modules/prismjs/components/prism-core.js')",
      'globalThis.Prism = Prism',
      ...PRISM_LANGUAGES.map(l => `require('./node_modules/prismjs/components/prism-${l}.js')`),
      'export const languages = Prism.languages',
      'export const tokenize = (code, grammar) => Prism.tokenize(code, grammar)',
    ].join('\n'),
    resolveDir: '.',
    loader: 'js',
  },
  bundle: true,
  format: 'esm',
  platform: 'neutral',
  target: 'es2023',
  minifySyntax: true,
  minifyWhitespace: true,
  outfile: '../hooks/vendor/prism.js',
  legalComments: 'none',
}))

track(await build({
  metafile: true,
  stdin: {
    contents: [
      "export { renderMermaidAscii } from './node_modules/beautiful-mermaid/src/ascii/index.ts'",
      "export { setChartSize } from './node_modules/beautiful-mermaid/src/ascii/xychart.ts'",
    ].join('\n'),
    resolveDir: '.',
    loader: 'ts',
  },
  bundle: true,
  format: 'esm',
  platform: 'neutral',
  target: 'es2023',
  minifySyntax: true,
  minifyWhitespace: true,
  outfile: '../hooks/vendor/mermaid-text.js',
  legalComments: 'none',
  plugins: [{
    name: 'chart-size',
    setup(api) {
      api.onLoad({ filter: XYCHART }, args => {
        let src = readFileSync(args.path, 'utf8')
        for (const line of SIZE) {
          if (!src.includes(line)) throw new Error(`xychart.ts no longer has "${line}"`)
          src = src.replace(line, line.replace('const', 'let'))
        }
        for (const [from, to] of BAR_SCALE) {
          if (!src.includes(from)) throw new Error(`xychart.ts no longer has "${from.trim().split('\n')[0]}"`)
          src = src.replace(from, to)
        }
        for (const [from, to] of LEGEND_NAMES) {
          if (!src.includes(from)) throw new Error(`xychart.ts no longer has "${from}"`)
          src = src.replace(from, to)
        }
        src += '\nexport const setChartSize = (width: number, height: number) => { PLOT_WIDTH = width; PLOT_HEIGHT = height }\n'
        return { contents: src, loader: 'ts' }
      })
      api.onLoad({ filter: XY_PARSER }, args => {
        let src = readFileSync(args.path, 'utf8')
        for (const [match, push, named, namedPush] of SERIES_NAMES) {
          if (!src.includes(match) || !src.includes(push)) throw new Error(`xychart/parser.ts no longer has "${match}"`)
          src = src.replace(match, named).replace(push, namedPush)
        }
        return { contents: src, loader: 'ts' }
      })
      api.onLoad({ filter: CANVAS }, args => {
        const src = readFileSync(args.path, 'utf8')
        if (!src.includes(CANVAS_ANCHOR)) throw new Error('canvas.ts no longer has isJunctionChar')
        return { contents: src.replace(CANVAS_ANCHOR, `${CLEAR_LABEL_GAPS}\n${CANVAS_ANCHOR}`), loader: 'ts' }
      })
      api.onLoad({ filter: DRAW }, args => {
        const src = readFileSync(args.path, 'utf8')
        if (!src.includes(DRAW_ANCHOR)) throw new Error('draw.ts no longer merges label canvases the same way')
        if (!src.includes(DRAW_IMPORT)) throw new Error('draw.ts no longer imports from canvas.ts the same way')
        const patched = src
          .replace(DRAW_ANCHOR, `${DRAW_ANCHOR}\n  for (const label of labelCanvases) clearLabelGaps(graph.canvas, label)`)
          .replace(DRAW_IMPORT, DRAW_IMPORT.replace('{ ', '{ clearLabelGaps, '))
        return { contents: patched, loader: 'ts' }
      })
      api.onLoad({ filter: PARSER }, args => {
        const src = readFileSync(args.path, 'utf8')
        const start = src.indexOf(NODE_ID_START)
        const end = src.indexOf(NODE_ID_END, start)
        if (start < 0 || end < 0) throw new Error('parser.ts no longer declares NODE_PATTERNS before CLASS_SHORTHAND_REGEX')
        const ids = src.slice(start, end)
        if (!ids.includes(NODE_ID)) throw new Error(`parser.ts node patterns no longer use ${NODE_ID}`)
        return { contents: src.slice(0, start) + ids.replaceAll(NODE_ID, NODE_ID_BEFORE_ARROW) + src.slice(end), loader: 'ts' }
      })
    },
  }],
}))

for (const name of bundledPackages) {
  const { license } = JSON.parse(readFileSync(`node_modules/${name}/package.json`, 'utf8'))
  if (license !== 'MIT') throw new Error(`${name} is ${license}, only MIT may be bundled`)
  console.log(`bundled ${name}: ${license}`)
}
