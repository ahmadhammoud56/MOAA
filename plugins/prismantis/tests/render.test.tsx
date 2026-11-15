import { expect, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'

import { displayText, parse } from '../hooks/markdown'
import { PRESETS } from '../hooks/presets'
import { MARK, diffTint, replyFill } from '../hooks/render'
import { width } from '../hooks/layout'
import { resolveStyle } from '../hooks/theme'
import { clipboardEnv, startSession } from './clipboard-env'

const TABLE = [
  '| Service | Regions | Version |',
  '|---|---|---:|',
  '| api-gateway | us, eu | server 2.14.0 |',
  '| billing | us, eu, ap | 1.8.3 |',
].join('\n')

const draw = (text: string) => ({
  plugin: 'prismantis',
  component: 'AssistantMessage' as const,
  props: { text, isFirstOfReply: true },
  viewport: { columns: 120, rows: 40 },
})

test('parses tables, code, lists and inline decorations', async () => {
  const blocks = parse(`# Title\n\n${TABLE}\n\n- see \`x\` at ~/git/app.ts\n\n\`\`\`bash\ngh pr view 12 --json\n\`\`\``, { numbers: true, paths: true })
  expect(blocks.map(b => b.kind)).toEqual(['heading', 'table', 'list', 'code'])
  const table = blocks[1]
  if (table?.kind !== 'table') throw new Error('not a table')
  expect(table.rows.length).toBe(2)
  expect(table.align[2]).toBe('right')
  expect(table.rows[0]?.[2]?.some(n => n.kind === 'number' && n.text === '2.14.0')).toBe(true)
  const list = blocks[2]
  if (list?.kind !== 'list') throw new Error('not a list')
  expect(list.items[0]?.inline.some(n => n.kind === 'path' && n.text === '~/git/app.ts')).toBe(true)
})

test('a code span drops the one space that pads it on both sides, so a span can show backticks', async () => {
  const [p] = parse('`` `c` `` and `  x  ` and ` y` and `   `', { numbers: false, paths: false })
  if (p?.kind !== 'paragraph') throw new Error('not a paragraph')
  expect(p.inline.filter(n => n.kind === 'code').map(n => (n as { text: string }).text)).toEqual(['`c`', ' x ', ' y', '   '])
})

test('escaped pipes stay inside a cell', async () => {
  const [t] = parse('| a | b |\n|---|---|\n| x \\| y | z |', { numbers: false, paths: false })
  if (t?.kind !== 'table') throw new Error('not a table')
  expect(t.rows[0]?.length).toBe(2)
})

test('a separator shorter than the header pads align to the header columns', async () => {
  const [t] = parse('| a | b | c |\n|:---|---:|\n| x | y |', { numbers: false, paths: false })
  if (t?.kind !== 'table') throw new Error('not a table')
  expect(t.align).toEqual(['left', 'right', 'left'])
  expect(t.rows[0]).toHaveLength(3)
  expect(t.rows[0]?.[2]).toEqual([])
})

test('user colors override the theme, bad colors are ignored', async () => {
  const s = resolveStyle({ theme: 'catppuccin-mocha', tableHeaderColor: '#ff0000', numberColor: 'not a color', pathColor: 'cyan', linkColor: 'javascript:x' })
  expect(s.theme.tableHeader).toBe('#ff0000')
  expect(s.theme.number).toBe(PRESETS['catppuccin-mocha'].number)
  expect(s.theme.path).toBe('cyan')
  expect(s.theme.link).toBe(PRESETS['catppuccin-mocha'].link)
})

test('a short #abc color reaches the theme as six digits, so a tint built from it still draws', () => {
  const t = resolveStyle({ diffAddedColor: '#0a0', tableRuleColor: ' #ABC ' }).theme
  expect([t.diffAdded, t.tableRule]).toEqual(['#00aa00', '#AABBCC'])
  expect(diffTint(t.codeText, t.diffAdded)).toBeDefined()
})

test('draws a colored table on terminal and desktop', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...draw(TABLE), surface })
    const header = await ui.find({ type: 'Text', text: /^Service$/ })
    expect(header?.props.color).toBe(PRESETS['catppuccin-mocha'].tableHeader)
    expect(header?.props.bold).toBe(true)
    const version = await ui.find({ type: 'Text', text: /^2\.14\.0$/ })
    expect(version?.props.color).toBe(PRESETS['catppuccin-mocha'].number)
    await ui.unmount()
  }
})

test('options reach the drawing', { options: { tableHeaderColor: '#123456', highlightNumbers: false } }, async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^Service$/ }))?.props.color).toBe('#123456')
  expect((await ui.find({ type: 'Text', text: /^2\.14\.0$/ }))).toBeUndefined()
  await ui.unmount()
})

test('shell blocks color command and flags', async $ => {
  const ui = await $.ui.mount({ ...draw('```bash\ngh pr review 45 --approve\n```'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^gh$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].codeCommand)
  expect((await ui.find({ type: 'Text', text: /^--approve$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].codeFlag)
  await ui.unmount()
})

const DIAGRAM = [
  'why prod runs a new chart',
  '',
  'A prod app is two knobs.',
  '      ┌──────────────┐',
  '      │ chart ref    │',
  '      └──────┬───────┘',
  'moves when the branch tip moves',
  '             ▼',
].join('\n')

test('an untagged block holding a box diagram draws no line in shell colors', async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(['```', DIAGRAM, '```'].join('\n')), surface: 'terminal' })
  const inks = (await ui.findAll({ type: 'Text' })).map(n => n.props.color)
  expect(inks).not.toContain(t.codeCommand)
  expect(inks).not.toContain(t.codeFlag)
  for (const line of ['why prod runs a new chart', 'A prod app is two knobs.', 'moves when the branch tip moves']) {
    expect((await ui.find({ type: 'Text', text: new RegExp(`^${line}$`) }))?.props.color).toBe(t.codeText)
  }
  await ui.unmount()
})

test('a tagged shell block keeps its command color when a box glyph shares the block', async $ => {
  const ui = await $.ui.mount({ ...draw('```bash\ntree src\n├── a.ts\n└── b.ts\n```'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^tree$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].codeCommand)
  await ui.unmount()
})

test('an untagged block without a box glyph still reads as shell', async $ => {
  const ui = await $.ui.mount({ ...draw('```\nnpm run build --silent\n```'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^npm$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].codeCommand)
  await ui.unmount()
})

test('disabled leaves the engine renderer alone', { options: { enabled: false } }, async ($, on) => {
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^Service$/ })).toBeUndefined()
  expect((await ui.find({ type: "Text", text: /^engine$/ }))?.text).toBe("engine")
  await ui.unmount()
})

for (const surfaces of [undefined, 'all', 'desktop-app, nope', '']) {
  test(`surfaces ${JSON.stringify(surfaces)} draws everywhere`, { options: surfaces === undefined ? {} : { surfaces } }, async $ => {
    for (const surface of ['terminal', 'desktop'] as const) {
      const ui = await $.ui.mount({ ...draw(TABLE), surface })
      expect((await ui.find({ type: 'Text', text: /^Service$/ }))?.text).toBe('Service')
      await ui.unmount()
    }
  })
}

test('surfaces terminal leaves the desktop to the engine', { options: { surfaces: ' Terminal ,bogus' } }, async ($, on) => {
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  const desktop = await $.ui.mount({ ...draw(TABLE), surface: 'desktop' })
  expect(await desktop.find({ type: 'Text', text: /^Service$/ })).toBeUndefined()
  expect((await desktop.find({ type: 'Text', text: /^engine$/ }))?.text).toBe('engine')
  await desktop.unmount()
  const row = await $.ui.mount({ plugin: 'prismantis', surface: 'desktop', component: 'TurnDuration', props: { word: 'Cooked', durationMs: 4000 } })
  expect((await row.find({ type: 'Text', text: /^engine$/ }))?.text).toBe('engine')
  await row.unmount()
  const terminal = await $.ui.mount({ ...draw(TABLE), surface: 'terminal' })
  expect((await terminal.find({ type: 'Text', text: /^Service$/ }))?.text).toBe('Service')
  await terminal.unmount()
})

test('box art from a mermaid mod above is not shell-colored', async $ => {
  const ui = await $.ui.mount({ ...draw('```\n┌───┐\n│ A │\n└───┘\n```'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^│ A │$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].codeText)
  await ui.unmount()
})

const FLOW = 'Flow:\n\n```mermaid\ngraph LR\nA[User] --> B[Gateway]\n```'

test('mermaid draws as colored box art', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...draw(FLOW), surface })
    const label = await ui.find({ type: 'Text', text: /Gateway/ })
    expect(label).toBeDefined()
    const user = await ui.find({ type: 'Text', text: /^User$/ })
    const gateway = await ui.find({ type: 'Text', text: /^Gateway$/ })
    expect(user?.props.color).toBeDefined()
    expect(user?.props.color).not.toBe(gateway?.props.color)
    await ui.unmount()
  }
})

test('mermaid off keeps the source', { options: { mermaid: false } }, async $ => {
  const ui = await $.ui.mount({ ...draw(FLOW), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^graph LR$/ })).toBeDefined()
  await ui.unmount()
})

test('every preset defines every token with a valid color', async () => {
  const tokens = Object.keys(PRESETS['catppuccin-mocha'])
  for (const [name, theme] of Object.entries(PRESETS)) {
    if (name === 'mono') continue
    expect(Object.keys(theme).sort()).toEqual([...tokens].sort())
    for (const value of Object.values(theme)) expect(/^#[0-9a-f]{6}$/.test(value as string)).toBe(true)
  }
})

test('picks a named theme and falls back on unknown names', async () => {
  expect(resolveStyle({ theme: 'dracula' }).theme.tableHeader).toBe('#f1fa8c')
  expect(resolveStyle({ theme: 'neon' }).theme.tableHeader).toBe('#00e5ff')
  expect(resolveStyle({ theme: 'nope' }).theme.tableHeader).toBe(PRESETS['catppuccin-mocha'].tableHeader)
})

const toolRow = (tool: string, input: unknown, extra: Partial<{ isRunning: boolean; isErrored: boolean; isInterrupted: boolean }> = {}) => ({
  plugin: 'prismantis',
  component: 'ToolUse' as const,
  props: { tool_use_id: 't1', tool, input, isRunning: false, isErrored: false, isInterrupted: false, ...extra },
  viewport: { columns: 120, rows: 40 },
})

test('tool rows read like Ran <command> with shell colors', { options: { toolStyle: 'classic' } }, async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...toolRow('Bash', { command: 'gh pr view 12 --json state' }), surface })
    expect((await ui.find({ type: 'Text', text: /^Ran$/ }))?.props.bold).toBe(true)
    expect((await ui.find({ type: 'Text', text: /^gh$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].codeCommand)
    await ui.unmount()
  }
})

test('file tools show the path in the path color and failures say so', async $ => {
  const ui = await $.ui.mount({ ...toolRow('Edit', { file_path: '/tmp/app.ts' }, { isErrored: true }), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^Edited$/ }))).toBeDefined()
  expect((await ui.find({ type: 'Text', text: /^\/tmp\/app\.ts$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].path)
  expect((await ui.find({ type: 'Text', text: /failed/ }))).toBeDefined()
  await ui.unmount()
})

test('toolRows off leaves tool rows to the engine', { options: { toolRows: false } }, async ($, on) => {
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  const ui = await $.ui.mount({ ...toolRow('Bash', { command: 'ls' }), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^engine$/ }))).toBeDefined()
  await ui.unmount()
})

test('rgb() and ansi256() colors reach the drawing', { options: { tableHeaderColor: 'rgb(255,204,0)', numberColor: 'ansi256(114)' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^Service$/ }))?.props.color).toBe('rgb(255,204,0)')
  expect((await ui.find({ type: 'Text', text: /^2\.14\.0$/ }))?.props.color).toBe('ansi256(114)')
  await ui.unmount()
})

test('bullets nested under a numbered list draw as bullets', async $ => {
  const ui = await $.ui.mount({ ...draw('1. Roll out\n   - canary first'), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^◦ $/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^- $/ })).toBeUndefined()
  await ui.unmount()
})

test('a single-series bar chart highlights the tallest bar and mutes the rest', async $ => {
  const chart = '```mermaid\nxychart-beta\n  x-axis [Mon, Tue, Wed]\n  y-axis 0 --> 9\n  bar [3, 7, 5]\n```'
  const ui = await $.ui.mount({ ...draw(chart), surface: 'terminal' })
  const t = PRESETS['catppuccin-mocha']
  const hues = new Set((await ui.findAll({ type: 'Text', text: /^█+$/ })).map(b => b.props.color))
  expect([...hues].sort()).toEqual([t.emphasis, t.quote].sort())
  await ui.unmount()
})

test('each line of a multi-line chart and its legend swatch share one color, distinct from the other lines', async $ => {
  const chart = '```mermaid\nxychart-beta\n  x-axis [a, b, c, d]\n  y-axis 0 --> 10\n  line [9, 9, 9, 9]\n  line [5, 5, 5, 5]\n  line [1, 1, 1, 1]\n```'
  const ui = await $.ui.mount({ ...draw(chart), surface: 'terminal' })
  const lines = (await ui.findAll({ type: 'Text', text: /^─{4,}$/ })).map(l => l.props.color)
  expect(new Set(lines).size).toBe(3)
  const swatches = (await ui.findAll({ type: 'Text', text: /^─$/ })).map(s => s.props.color)
  expect(new Set(swatches)).toEqual(new Set(lines))
  await ui.unmount()
})

test('a named series shows its name in the legend and a nameless one keeps Line N', async $ => {
  const chart = '```mermaid\nxychart-beta\n  x-axis [a, b, c]\n  y-axis 0 --> 10\n  line "east" [8, 8, 8]\n  line [2, 2, 2]\n```'
  const ui = await $.ui.mount({ ...draw(chart), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /east/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Line 2/ })).toBeDefined()
  expect(new Set((await ui.findAll({ type: 'Text', text: /^─{3,}$/ })).map(l => l.props.color)).size).toBe(2)
  await ui.unmount()
})

test('grouped bars take one color per series, not one per bar', async $ => {
  const chart = '```mermaid\nxychart-beta\n  x-axis [a, b, c]\n  y-axis 0 --> 10\n  bar [8, 8, 8]\n  bar [4, 4, 4]\n```'
  const ui = await $.ui.mount({ ...draw(chart), surface: 'terminal' })
  const hues = new Set((await ui.findAll({ type: 'Text', text: /^[█▄▀]+$/ })).map(b => b.props.color))
  expect(hues.size).toBe(2)
  await ui.unmount()
})

test('a participant keeps one color at both ends of a sequence diagram', async $ => {
  const seq = '```mermaid\nsequenceDiagram\n  Browser->>App: GET /cart\n  App-->>Browser: 200\n```'
  const ui = await $.ui.mount({ ...draw(seq), surface: 'terminal' })
  const ends = await ui.findAll({ type: 'Text', text: /^Browser$/ })
  expect(ends.length).toBe(2)
  expect(ends[0]?.props.color).toBe(ends[1]?.props.color)
  await ui.unmount()
})

test('back-to-back tables and diagrams share a wrapping row', async $ => {
  const text = `${TABLE}\n\n${FLOW.replace('Flow:\n\n', '')}\n\nAfter.`
  const ui = await $.ui.mount({ ...draw(text), surface: 'terminal' })
  const rows = (await ui.findAll({ type: 'Box' })).filter(b => b.props.flexWrap === 'wrap')
  expect(rows.length).toBe(1)
  expect(rows[0]?.text).toContain('Service')
  expect(rows[0]?.text).toContain('Gateway')
  expect(rows[0]?.text).not.toContain('After.')
  await ui.unmount()
})

test('code blocks, tables and quotes get a copy button, tables an art button, the reply a copy reply button', async ($, on) => {
  const copied: string[] = []
  on('ui.copy', (_, e) => {
    copied.push(e.text)
    return { value: { isCopied: true as const } }
  })
  const text = `${TABLE}\n\n\`\`\`bash\nls -la\n\`\`\`\n\n> reply text\n\nplain paragraph`
  const ui = await $.ui.mount({ ...draw(text), surface: 'terminal' })
  const buttons = await ui.findAll({ type: 'Button' })
  expect(buttons.length).toBe(5)
  expect(buttons.every(b => b.props.plain === true && b.props.dimColor === true)).toBe(true)
  await ui.press({ key: 'copy1' })
  expect(copied).toEqual(['ls -la'])
  await ui.unmount()
})

const COPY_SAMPLE = `${TABLE}\n\n\`\`\`bash\nls -la\n\`\`\`\n\n> reply text\n\nplain paragraph`

const floatingCopies = async (ui: { findAll: (query: { type: string }) => Promise<{ props: Record<string, unknown>; text?: string }[]> }) =>
  (await ui.findAll({ type: 'Box' })).filter(b => b.props.position === 'absolute' && b.props.display === 'none').map(b => b.text)

type DrawnNode = { type?: string; props?: Record<string, unknown>; hover?: { scope?: string; display?: string }; children?: unknown[] }
const drawnKids = (node: DrawnNode) => (node.children ?? []).filter((child): child is DrawnNode => !!child && typeof child === 'object')
const withParents = (node: DrawnNode, parent?: DrawnNode): { node: DrawnNode; parent?: DrawnNode }[] => [{ node, parent }, ...drawnKids(node).flatMap(child => withParents(child, node))]
const shownText = (node: DrawnNode): string => (node.children ?? []).map(child => (typeof child === 'string' ? child : child && typeof child === 'object' ? shownText(child as DrawnNode) : '')).join('')
const holdsButton = (node: DrawnNode): boolean => node.type === 'Button' || drawnKids(node).some(holdsButton)
const inFlow = (node: DrawnNode) => node.props?.position !== 'absolute'
const reveals = (tree: DrawnNode) => withParents(tree).filter(({ node }) => holdsButton(node) && node.props?.position === 'absolute' && node.props.display === 'none')
const markersOf = (tree: DrawnNode, scope: string) => withParents(tree).filter(({ node }) => node.hover?.scope === scope && node.props?.display !== 'none')

const labelsOf = (node: DrawnNode) => withParents(node).filter(({ node: n }) => n.type === 'Button').map(({ node: n }) => n.props?.label).join(' ')
const SURFACES = ['terminal', 'desktop'] as const

for (const surface of SURFACES) test(`copyButtonStyle hover hides every copy button until the pointer is on its ⧉ marker on ${surface}`, { options: { copyButtonStyle: 'hover' } }, async ($, on) => {
  const copied: string[] = []
  on('ui.copy', (_, e) => {
    copied.push(e.text)
    return { value: { isCopied: true as const } }
  })
  const ui = await $.ui.mount({ ...draw(COPY_SAMPLE), surface })
  const tree = (await ui.drawn()) as DrawnNode
  expect(await ui.findAll({ type: 'Button' })).toHaveLength(5)
  expect(await floatingCopies(ui)).toEqual(['⧉ md ⧉ art', '⧉ copy', '⧉ copy', '⧉ copy reply'])
  expect(reveals(tree).flatMap(({ node }) => withParents(node).filter(({ node: n }) => n.type === 'Button'))).toHaveLength(5)
  for (const { node, parent } of reveals(tree)) {
    const scope = node.hover?.scope ?? ''
    expect(node.hover).toEqual({ scope, display: 'flex' })
    expect(parent?.hover?.scope).toBe(scope)
    expect(markersOf(tree, scope).map(({ node: marker }) => ({ text: drawnKids(marker).filter(inFlow).map(shownText).join(''), flows: inFlow(marker) }))).toEqual([{ text: '⧉', flows: !scope.endsWith(':reply') }])
  }
  await ui.press({ key: 'copy1' })
  expect(copied).toEqual(['ls -la'])
  await ui.unmount()
})

for (const surface of SURFACES) test(`copyButtonStyle hover draws a block's buttons over its marker, from the marker's row and side, on ${surface}`, { options: { copyButtonStyle: 'hover' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('| Region | p99 |\n|---|---:|\n| eu | 12 |\n\n```bash\nls\n```\n\n> ```bash\n> npm test\n> ```\n>\n> Run that first.'), surface })
  const tree = (await ui.drawn()) as DrawnNode
  const floats = reveals(tree).filter(({ node }) => labelsOf(node) !== '⧉ copy reply')
  expect(floats.map(({ node }) => labelsOf(node))).toEqual(['⧉ md ⧉ art', '⧉ copy', '⧉ copy', '⧉ copy'])
  for (const { node, parent } of floats) {
    const marker = parent!
    expect(marker.hover?.scope).toBe(node.hover?.scope)
    expect(['flex-start', 'flex-end']).toContain(marker.props?.alignSelf)
    expect({ right: node.props?.right, left: node.props?.left, width: node.props?.width, minWidth: node.props?.minWidth }).toEqual({ right: 0, left: undefined, width: undefined, minWidth: undefined })
    expect(marker.props?.alignSelf === 'flex-end' ? { bottom: node.props?.bottom } : { top: node.props?.top }).toEqual(marker.props?.alignSelf === 'flex-end' ? { bottom: 0 } : { top: 0 })
  }
  await ui.unmount()
})

for (const surface of SURFACES) test(`copyButtonStyle hover makes a block at least as wide as its buttons, so buttons drawn from its marker never run off its left edge, on ${surface}`, { options: { copyButtonStyle: 'hover' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('| a |\n|---|\n| 1 |\n\n```\nx\n```'), surface })
  expect(((await ui.find({ key: 'c0' }))?.children[0] as DrawnNode).props?.minWidth).toBe('[ ⧉ md ] [ ⧉ art ]'.length)
  expect((await ui.find({ key: 'b1' }))?.props.minWidth).toBe('── code [ ⧉ copy ]'.length)
  await ui.unmount()
})

for (const surface of SURFACES) test(`copyButtonStyle hover reserves its buttons' width beside a narrow block, so a table drawn next to it never covers them, on ${surface}`, { options: { copyButtonStyle: 'hover' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('| a | b |\n|---|---|\n| 1 | 2 |\n\n| c | d |\n|---|---|\n| 3 | 4 |'), surface })
  for (const key of ['c0', 'c1']) expect(((await ui.find({ key }))?.children[0] as DrawnNode).props?.minWidth).toBe('[ ⧉ md ] [ ⧉ art ]'.length)
  await ui.unmount()
})

for (const surface of SURFACES) test(`copyButtonStyle hover gives every block with copy buttons one dim ⧉ in the flow, a column clear of it, on ${surface}`, { options: { copyButtonStyle: 'hover' } }, async $ => {
  const text = '| a |\n|---|\n| 1 |\n\n```\nx\n```\n\n- y\n\n> z\n\n> [!NOTE]\n> w\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\nplain'
  const ui = await $.ui.mount({ ...draw(text), surface })
  const tree = (await ui.drawn()) as DrawnNode
  const marks = withParents(tree).filter(({ node }) => node.type === 'Text' && shownText(node) === '⧉')
  expect(marks).toHaveLength(7)
  for (const { node } of marks) expect(node.props?.dimColor).toBe(true)
  const blocks = marks.map(({ parent }) => parent!).filter(box => !box.hover?.scope?.endsWith(':reply'))
  expect(blocks).toHaveLength(6)
  for (const box of blocks) expect({ scoped: box.hover?.scope !== undefined, flows: inFlow(box) }).toEqual({ scoped: true, flows: true })
  for (const key of ['c0', 'c2', 'c3', 'c4', 'c5']) expect(((await ui.find({ key }))?.children[0] as DrawnNode).props?.columnGap).toBe(1)
  await ui.unmount()
})

test('copyButtonStyle hover keeps a long code label and its ⧉ on one row at the narrowest width', { options: { replyStyle: 'off', copyButtonStyle: 'hover' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('```typescriptreact\nx\n```'), viewport: { columns: 24, rows: 40 }, surface: 'terminal' })
  const code = (await ui.find({ key: 'b0' }))!
  const header = code.children.find((child): child is DrawnNode => !!child && typeof child === 'object' && (child as DrawnNode).props?.justifyContent === 'space-between')!
  const label = shownText(drawnKids(header)[0]!)
  expect(width(label) + (header.props?.columnGap as number) + 1).toBeLessThanOrEqual(code.props.minWidth as number)
  await ui.unmount()
})

for (const surface of SURFACES) test(`copyButtonStyle hover puts the reply's ⧉ in its bottom-right corner, in a gutter of its own, with copy reply drawn over it, on ${surface}`, { options: { replyStyle: 'off', copyButtonStyle: 'hover' } }, async $ => {
  for (const text of [COPY_SAMPLE, 'שלום עולם']) {
    const ui = await $.ui.mount({ ...draw(text), surface })
    const anchor = await ui.find({ key: 'reply' })
    expect({ position: anchor?.props.position, bottom: anchor?.props.bottom, right: anchor?.props.right, text: anchor?.text }).toEqual({ position: 'absolute', bottom: 0, right: -2, text: '⧉⧉ copy reply' })
    const reveal = (anchor?.children ?? []).find((child): child is DrawnNode => !!child && typeof child === 'object' && (child as DrawnNode).props?.display === 'none')
    expect({ top: reveal?.props?.top, right: reveal?.props?.right }).toEqual({ top: 0, right: 0 })
    const row = drawnKids((await ui.drawn()) as DrawnNode)
    expect({ width: row.at(-1)?.props?.width, children: row.at(-1)?.children ?? [] }).toEqual({ width: 2, children: [] })
    await ui.unmount()
  }
})

for (const surface of SURFACES) test(`copyButtonStyle hover shows nothing while the pointer is on a block, only on its marker, on ${surface}`, { options: { copyButtonStyle: 'hover' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(`${COPY_SAMPLE}\n\n- item\n  \`\`\`\n  v\n  \`\`\``), surface })
  const tree = (await ui.drawn()) as DrawnNode
  const shown = withParents(tree).filter(({ node }) => node.hover?.display === 'flex')
  expect(shown.length).toBeGreaterThan(0)
  for (const { node } of shown) expect(markersOf(tree, node.hover?.scope ?? '').length).toBe(1)
  await ui.unmount()
})

const WIDE = `| A | B |\n|---|---|\n| ${'alpha '.repeat(12)}| ${'bravo '.repeat(12)}|\n\nx\n\n\`\`\`mermaid\nflowchart LR\n  A[${'a'.repeat(12)}] --> B[${'b'.repeat(12)}] --> C[${'c'.repeat(12)}]\n\`\`\`\n\ny\n\n\`\`\`mermaid\nflowchart LR\n  A[${'a'.repeat(7)}] --> B[${'b'.repeat(7)}] --> C[${'c'.repeat(7)}] --> D[${'d'.repeat(7)}]\n\`\`\``
const widest = (node: DrawnNode): number => (node.type === 'Text' ? width(shownText(node)) : Math.max(0, ...drawnKids(node).map(widest)))
for (const copyButtonStyle of ['dim', 'inline', 'hover'] as const) test(`copyButtonStyle ${copyButtonStyle} lays a full-width table and diagram out ${copyButtonStyle === 'hover' ? 'two columns narrower, so the ⧉ fits beside them' : 'to the whole width'}`, { options: { replyStyle: 'off', copyButtonStyle } }, async $ => {
  const ui = await $.ui.mount({ ...draw(WIDE), viewport: { columns: 60, rows: 40 }, surface: 'terminal' })
  const [table, wide, wider] = await Promise.all(['c0', 'c2', 'c4'].map(async key => widest((await ui.find({ key })) as DrawnNode)))
  if (copyButtonStyle !== 'hover') expect({ table, wide: wide! > 56 - MARK - 2 }).toEqual({ table: 56, wide: true })
  else expect({ table, fits: [wide!, wider!].every(w => w + MARK <= 56) }).toEqual({ table: 56 - MARK, fits: true })
  await ui.unmount()
})

test('copyButtonStyle hover drops trailing buttons a narrow terminal has no room for, keeping the first', { options: { copyButtonStyle: 'hover' } }, async ($, on) => {
  clipboardEnv(on, 'macos')
  await startSession($, on)
  for (const [columns, labels] of [[120, '⧉ md ⧉ art ⧉ html ▣ png'], [24, '⧉ md ⧉ art']] as const) {
    const ui = await $.ui.mount({ ...draw('| a |\n|---|\n| 1 |'), viewport: { columns, rows: 40 }, surface: 'terminal' })
    expect(reveals((await ui.drawn()) as DrawnNode).map(({ node }) => withParents(node).filter(({ node: n }) => n.type === 'Button').map(({ node: n }) => n.props?.label).join(' '))).toEqual([labels])
    await ui.unmount()
  }
})

test('copyButtonStyle dim, the default, keeps every copy button in the flow', async $ => {
  const ui = await $.ui.mount({ ...draw(COPY_SAMPLE), surface: 'terminal' })
  expect(await ui.findAll({ type: 'Button' })).toHaveLength(5)
  expect(await floatingCopies(ui)).toHaveLength(0)
  await ui.unmount()
})

test('copyButtonStyle hover draws inline on mobile, which has no pointer', { options: { copyButtonStyle: 'hover' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(COPY_SAMPLE), surface: 'mobile' })
  expect(await floatingCopies(ui)).toHaveLength(0)
  await ui.unmount()
})

test('copyButtons off draws no buttons', { options: { copyButtons: false } }, async $ => {
  const ui = await $.ui.mount({ ...draw(`${TABLE}\n\n\`\`\`bash\nls\n\`\`\``), surface: 'terminal' })
  expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
  await ui.unmount()
})

for (const copyButtonStyle of ['dim', 'inline', 'hover'] as const) test(`textCopyButtons off drops the ${copyButtonStyle} buttons on lists, quotes and alerts and keeps code, table and reply buttons`, { options: { textCopyButtons: false, copyButtonStyle } }, async $ => {
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...draw(`- one\n- two\n\n> quoted\n\n> [!NOTE]\n> noted\n\n${TABLE}\n\n\`\`\`bash\nls\n\`\`\``), surface })
    const labels = (await ui.findAll({ type: 'Button' })).map(b => String(b.props.label))
    expect(labels.filter(l => l === '⧉ copy')).toHaveLength(1)
    expect(labels).toContain('⧉ md')
    expect(labels).toContain('⧉ copy reply')
    await ui.unmount()
  }
})

test('lists copy as markdown', async ($, on) => {
  const copied: string[] = []
  on('ui.copy', (_, e) => {
    copied.push(e.text)
    return { value: { isCopied: true as const } }
  })
  const ui = await $.ui.mount({ ...draw('1. Build\n2. Ship\n   - canary'), surface: 'terminal' })
  const [button] = await ui.findAll({ type: 'Button' })
  await ui.press({ key: button!.key! })
  expect(copied).toEqual(['1. Build\n2. Ship\n   - canary'])
  await ui.unmount()
})

test('diagrams offer two copies: mermaid source and drawn art', async ($, on) => {
  const copied: string[] = []
  on('ui.copy', (_, e) => {
    copied.push(e.text)
    return { value: { isCopied: true as const } }
  })
  const ui = await $.ui.mount({ ...draw(FLOW), surface: 'terminal' })
  const buttons = await ui.findAll({ type: 'Button' })
  expect(buttons.map(b => b.props.label)).toEqual(['⧉ source', '⧉ art', '⧉ copy reply'])
  for (const b of buttons) await ui.press({ key: b.key! })
  expect(copied[0]).toBe('graph LR\nA[User] --> B[Gateway]')
  expect(copied[1]).toContain('┌')
  await ui.unmount()
})

test('JSON and YAML get keys, strings, numbers and comments colored', async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw('```yaml\nname: "shop" # app\nreplicas: 3\n```'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^name$/ }))?.props.color).toBe(t.codeCommand)
  expect((await ui.find({ type: 'Text', text: /^"shop"$/ }))?.props.color).toBe(t.codeString)
  expect((await ui.find({ type: 'Text', text: /^3$/ }))?.props.color).toBe(t.number)
  expect((await ui.find({ type: 'Text', text: /^# app$/ }))?.props.color).toBe(t.codeComment)
  await ui.unmount()
})

test('Prism colors TypeScript keywords, strings and comments', async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw('```ts\nconst name = "shop" // app\n```'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^const$/ }))?.props.color).toBe(t.codeFlag)
  expect((await ui.find({ type: 'Text', text: /^"shop"$/ }))?.props.color).toBe(t.codeString)
  expect((await ui.find({ type: 'Text', text: /^\/\/ app$/ }))?.props.italic).toBe(true)
  await ui.unmount()
})

test('Prism colors Lua keywords and comments', async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw('```lua\nlocal name = "shop" -- app\n```'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^local$/ }))?.props.color).toBe(t.codeFlag)
  expect((await ui.find({ type: 'Text', text: /^-- app$/ }))?.props.italic).toBe(true)
  await ui.unmount()
})

test('Prism colors PHP variables, properties and comments', async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw('```php\n$total = $order->sum; // app\n```'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^\$total$/ }))?.props.color).toBe(t.emphasis)
  expect((await ui.find({ type: 'Text', text: /^sum$/ }))?.props.color).toBe(t.link)
  expect((await ui.find({ type: 'Text', text: /^\/\/ app$/ }))?.props.italic).toBe(true)
  await ui.unmount()
})

test('a highlighted code line draws each run of one color as one span', async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw('```ts\nconst name = await fetch("/api/0", { retries: 1 }) // app\n```'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^ name = $/ }))?.props.color).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^, \{ retries: $/ })).toBeDefined()
  expect((await ui.find({ type: 'Text', text: /^const$/ }))?.props.color).toBe(t.codeFlag)
  expect((await ui.find({ type: 'Text', text: /^"\/api\/0"$/ }))?.props.color).toBe(t.codeString)
  expect((await ui.find({ type: 'Text', text: /^\/\/ app$/ }))?.props.italic).toBe(true)
  await ui.unmount()
})

test('fence languages that name Prism internals fall back to plain code', async $ => {
  for (const lang of ['extend', 'toString', 'constructor', '__proto__']) {
    const ui = await $.ui.mount({ ...draw(`\`\`\`${lang}\nhello\n\`\`\``), surface: 'terminal' })
    expect((await ui.find({ type: 'Text', text: /^hello$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].codeText)
    await ui.unmount()
  }
})

test('code blocks draw through the native Code element off the terminal', async $ => {
  const ui = await $.ui.mount({ ...draw('```ts\nconst name = "shop"\n  return name\n```'), surface: 'desktop' })
  const code = await ui.find({ type: 'Code' })
  expect(code?.props.source).toBe('const name = "shop"\n  return name')
  expect(code?.props.language).toBe('ts')
  expect(code?.props.startLine).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^const$/ })).toBeUndefined()
  await ui.unmount()
  const long = await $.ui.mount({ ...draw(longCode(12)), surface: 'desktop' })
  expect((await long.find({ type: 'Code' }))?.props.startLine).toBe(1)
  expect(await long.find({ type: 'Text', text: /^ 1  $/ })).toBeUndefined()
  await long.unmount()
  const term = await $.ui.mount({ ...draw('```ts\nconst name = "shop"\n```'), surface: 'terminal' })
  expect(await term.find({ type: 'Code' })).toBeUndefined()
  await term.unmount()
})

test('tables draw boxed by default in the terminal, with a double line under the header', async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'terminal' })
  const top = (await ui.find({ type: 'Text', text: /^┌[─┬]+┐$/ }))?.text ?? ''
  expect(top.split('┬').length).toBe(3)
  const lines = [top, ...(await Promise.all([/^╞[═╪]+╡$/, /^├[─┼]+┤$/, /^└[─┴]+┘$/].map(async re => (await ui.find({ type: 'Text', text: re }))?.text ?? '')))]
  expect(lines.every(l => l.length === top.length && l.length > 0)).toBe(true)
  expect((await ui.find({ type: 'Text', text: /^Service$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].tableHeader)
  await ui.unmount()
})

test('a table row with a link beside a column of only line breaks still draws as a table', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...draw('| Link | |\n|---|---|\n| https://x.com | <br> |'), surface })
    expect(await ui.find({ type: 'Text', text: /^Link$/ })).toBeDefined()
    await ui.unmount()
  }
})

const percent = (width: unknown) => (typeof width === 'string' && /^\d+%$/.test(width) ? Number(width.slice(0, -1)) : NaN)

const STACKS = '| Scroll | Checksum |\n|:-------|:---------|\n| ~/jade-palace/noodle-scrolls/scrolls/scroll-07-training-notes.md | 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08 |\n| /srv/dojo/moves.md | 2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae |'

for (const tableLayout of ['classic', 'auto', 'compact', 'stacked'] as const) test(`tableLayout ${tableLayout} in the terminal ${(tableLayout === 'classic' ? "keeps today's look" : tableLayout === 'auto' ? 'stretches the columns and stacks only a table too wide for even its longest words' : tableLayout === 'compact' ? 'sits every column at its longest word' : 'draws every row as label and value pairs')}`, { options: { tableLayout } }, async $ => {
  const ui = await $.ui.mount({ ...draw(tableLayout === 'stacked' ? STACKS : TABLE), surface: 'terminal' })
  if (tableLayout === 'stacked') {
    expect((await ui.findAll({ type: 'Text', text: /^Scroll *$/ }))).toHaveLength(2)
    expect((await ui.findAll({ type: 'Text', text: /^Checksum$/ }))).toHaveLength(2)
    expect(await ui.find({ type: 'Text', text: /^┌[─┬]+┐$/ })).toBeUndefined()
  } else {
    const boxes = await ui.findAll({ type: 'Box' })
    expect(['Service', 'Regions', 'Version'].map(name => {
      const cell = boxes.find(b => b.text === name && typeof b.props.width === 'number')
      if (!cell) throw new Error(`column ${name} not drawn`)
      return cell.props.width as number
    })).toEqual(tableLayout === 'compact' ? [11, 7, 7] : [11, 10, 13])
  }
  await ui.unmount()
})

test('tableLayout auto stacks in the terminal when not even the longest words fit', { options: { tableLayout: 'auto' } }, async $ => {
  const narrow = await $.ui.mount({ ...draw(STACKS), surface: 'terminal', viewport: { columns: 40, rows: 40 } })
  expect((await narrow.findAll({ type: 'Text', text: /^Checksum$/ }))).toHaveLength(2)
  expect(await narrow.find({ type: 'Text', text: /^┌[─┬]+┐$/ })).toBeUndefined()
  await narrow.unmount()
})

test('tableLayout stacked on desktop falls back to the shared percent layout', { options: { tableLayout: 'stacked' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'desktop' })
  expect(await ui.findAll({ type: 'Text', text: /^Checksum$/ })).toHaveLength(0)
  const headers = (await ui.findAll({ type: 'Box' })).filter(b => /^(Service|Regions|Version)$/.test(b.text ?? '') && b.props.width !== undefined)
  expect(headers.map(b => percent(b?.props.width)).reduce((sum, n) => sum + n, 0)).toBe(100)
  await ui.unmount()
})

const STATUS = [
  '| Suite | Cases | Result |',
  '|-------|------:|--------|',
  '| Unit | 412 | ✓ |',
  '| Propagation | 88 | failed |',
  '| Smoke | 24 | pending |',
  '| Regression | 130 | ✓ |',
  '| Cache | 15 | degraded |',
].join('\n')

for (const surface of ['terminal', 'desktop'] as const) test(`statusMatrix ${surface} colors the status cells of a table in theme colors`, { options: { statusMatrix: 'color' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(STATUS), surface })
  expect((await ui.find({ type: 'Text', text: /^failed$/ }))?.props.color).toBe(t.diffRemoved)
  expect((await ui.find({ type: 'Text', text: /^pending$/ }))?.props.color).toBe(t.codeComment)
  expect((await ui.find({ type: 'Text', text: /^degraded$/ }))?.props.color).toBe(t.tableHeader)
  expect(t.tableHeader).not.toBe(t.diffRemoved)
  expect(t.tableHeader).not.toBe(t.codeString)
  const checks = await ui.findAll({ type: 'Text', text: /^✓$/ })
  expect(checks.length >= 2).toBe(true)
  expect(checks.filter(n => n.props.color === t.codeString).length >= 2).toBe(true)
  expect((await ui.find({ type: 'Text', text: /^Propagation$/ }))?.props.color).toBeUndefined()
  await ui.unmount()
})

const REPORT = [
  '| Check | Time | Result |',
  '|:------|-----:|:-------|',
  '| parse | 120 ms | ✓ |',
  '| draw | 4 s | ✓ |',
  '| scan | 130 ms | failed |',
  '| typeset | 2.6 s | pending |',
].join('\n')
const BENCH = [
  '| Benchmark | Before | After | Change |',
  '|:----------|-------:|------:|:-------|',
  '| parse | 12.4 ms | 11.1 ms | -10% |',
  '| layout | 19.6 ms | 22.4 ms | +14% |',
  '| paint | 2.1 ms | 0.8 ms | -62% |',
  '| typeset | 0.9 ms | 0.9 ms | 0% |',
].join('\n')

const SCHEMA = [
  '| Column | Type | Key | Default |',
  '|:-------|:-----|:----|:--------|',
  '| id | uuid | PK | |',
  '| email | varchar(255) | UNIQUE | |',
  '| org_id | bigint | FK | |',
  '| created_at | timestamp | | now() |',
].join('\n')

const KEYLESS = [
  '| Column | Type | Notes |',
  '|:-------|:-----|:------|',
  '| id | uuid | PK |',
  '| org_id | bigint | FK |',
].join('\n')


test('statusMatrix off keeps tables as written', async $ => {
  const ui = await $.ui.mount({ ...draw(STATUS), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^failed$/ }))?.props.color).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^ · $/ })).toBeUndefined()
  await ui.unmount()
})

test('a Color column and a none column are not a status column', { options: { statusMatrix: 'summary' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('| Thing | Color | Default |\n|---|---|---|\n| a | red | none |\n| b | green | n/a |'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^red$/ }))?.props.color).toBeUndefined()
  expect((await ui.find({ type: 'Text', text: /^green$/ }))?.props.color).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^ · $/ })).toBeUndefined()
  await ui.unmount()
})

test('statusMatrix summary draws a count line under the table, like `✓ 2 · ✗ 1 · ● 1`', { options: { statusMatrix: 'summary' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(STATUS), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^✓ 2$/ }))?.props.color).toBe(t.codeString)
  expect((await ui.find({ type: 'Text', text: /^✗ 1$/ }))?.props.color).toBe(t.diffRemoved)
  expect((await ui.find({ type: 'Text', text: /^⚠ 1$/ }))?.props.color).toBe(t.tableHeader)
  expect((await ui.find({ type: 'Text', text: /^● 1$/ }))?.props.color).toBe(t.codeComment)
  const seps = await ui.findAll({ type: 'Text', text: /^ · $/ })
  expect(seps).toHaveLength(3)
  expect(seps.every(n => n.props.dimColor)).toBe(true)
  await ui.unmount()
})

test('statusMatrix group reorders rows by status and draws a heavy rule where the status changes', { options: { statusMatrix: 'group' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(STATUS), surface: 'terminal' })
  expect((await ui.findAll({ type: 'Text', text: /^╞[═╪]+╡$/ }))).toHaveLength(4)
  const suite = await ui.findAll({ type: 'Text', text: /^(Unit|Regression|Propagation|Smoke|Cache)$/ })
  expect([...new Set(suite.map(n => n.text))]).toEqual(['Unit', 'Regression', 'Propagation', 'Cache', 'Smoke'])
  expect((await ui.findAll({ type: 'Text', text: /^failed$/ })).some(n => n.props.color === t.diffRemoved)).toBe(true)
  expect((await ui.findAll({ type: 'Text', text: /^pending$/ })).some(n => n.props.color === t.codeComment)).toBe(true)
  expect((await ui.findAll({ type: 'Text', text: /^degraded$/ })).some(n => n.props.color === t.tableHeader)).toBe(true)
  await ui.unmount()
})

test('a table without a status column draws unchanged', { options: { statusMatrix: 'summary' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: / · / })).toBeUndefined()
  expect((await ui.find({ type: 'Text', text: /^api-gateway$/ }))?.props.color).toBeUndefined()
  await ui.unmount()
})

test('statusMatrix stays off stacked tables', { options: { statusMatrix: 'summary', tableLayout: 'stacked' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(STATUS), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^failed$/ }))?.props.color).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^✓ 2$/ })).toBeUndefined()
  await ui.unmount()
})

for (const surface of ['terminal', 'desktop'] as const) test(`testMatrix ${surface} draws the pass share, other results and the total time under a results table`, { options: { testMatrix: 'report' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(REPORT), surface })
  expect((await ui.find({ type: 'Text', text: /^✓ 2$/ }))?.props.color).toBe(t.codeString)
  expect(await ui.find({ type: 'Text', text: /^ of 4 \(50%\)$/ })).toBeTruthy()
  expect((await ui.find({ type: 'Text', text: /^✗ 1$/ }))?.props.color).toBe(t.diffRemoved)
  expect((await ui.find({ type: 'Text', text: /^● 1$/ }))?.props.color).toBe(t.codeComment)
  const seps = await ui.findAll({ type: 'Text', text: /^ · $/ })
  expect(seps).toHaveLength(3)
  expect(seps.every(x => x.props.dimColor)).toBe(true)
  expect((await ui.find({ type: 'Text', text: /^6\.9s total$/ }))?.props.dimColor).toBe(true)
  expect((await ui.find({ type: 'Text', text: /^failed$/ }))?.props.color).toBeUndefined()
  await ui.unmount()
})

test('testMatrix totals a run under a millisecond in microseconds', { options: { testMatrix: 'report' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('| Check | Time | Result |\n|:------|-----:|:-------|\n| parse | 250 µs | ✓ |\n| draw | 550 µs | failed |'), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^800µs total$/ })).toBeTruthy()
  await ui.unmount()
})

test('testMatrix off keeps tables as written', { options: { testMatrix: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(REPORT), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^ of 4 / })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^ · $/ })).toBeUndefined()
  await ui.unmount()
})

test('a status column with no time column draws no report', { options: { testMatrix: 'report' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(STATUS), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^ of / })).toBeUndefined()
  await ui.unmount()
})

test('a time column whose cells do not mostly read like durations draws no report', { options: { testMatrix: 'report' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('| Check | Time | Result |\n|:------|-----:|:-------|\n| parse | 120 ms | ✓ |\n| draw | a lot | ✓ |\n| scan | hard | failed |'), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^ of / })).toBeUndefined()
  await ui.unmount()
})

test('testMatrix report replaces the statusMatrix summary count line', { options: { statusMatrix: 'summary', testMatrix: 'report' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(REPORT), surface: 'terminal' })
  expect(await ui.findAll({ type: 'Text', text: /^✓ 2$/ })).toHaveLength(1)
  expect((await ui.findAll({ type: 'Text', text: /^✓ 2$/ })).every(x => x.props.color === t.codeString)).toBe(true)
  expect(await ui.findAll({ type: 'Text', text: /^ · $/ })).toHaveLength(3)
  expect(await ui.find({ type: 'Text', text: /^6\.9s total$/ })).toBeTruthy()
  await ui.unmount()
})

test('testMatrix stays off stacked tables', { options: { testMatrix: 'report', tableLayout: 'stacked' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(REPORT), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^ of 4 / })).toBeUndefined()
  await ui.unmount()
})

for (const tableStyle of ['box', 'rules', 'grid', 'minimal'] as const) test(`tableStyle ${tableStyle} in the terminal keeps its character rules in fixed columns`, { options: { tableStyle } }, async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'terminal' })
  const boxes = await ui.findAll({ type: 'Box' })
  expect(boxes.some(b => b.props.backgroundColor !== undefined && Number(b.props.height ?? 1) < 1)).toBe(false)
  expect(boxes.filter(b => /^(Service|Regions|Version)$/.test(b.text ?? '')).every(b => typeof b.props.width === 'number' && b.props.flexShrink === 0)).toBe(true)
  expect((await ui.find({ key: 'b0' }))?.props.alignSelf).toBeUndefined()
  if (tableStyle === 'box') expect(await ui.find({ type: 'Text', text: /^┌[─┬]+┐$/ })).toBeDefined()
  else expect(await ui.findAll({ type: 'Text', text: /^[─━]+$/ })).toHaveLength(tableStyle === 'minimal' ? 3 : 6)
  await ui.unmount()
})

for (const tableStyle of ['box', 'rules', 'grid', 'minimal'] as const) test(`tableStyle ${tableStyle} on desktop draws its lines as thin colored boxes that share the percent widths of their columns`, { options: { tableStyle } }, async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'desktop' })
  const ink = PRESETS['catppuccin-mocha'].tableRule
  const boxes = await ui.findAll({ type: 'Box' })
  expect(await ui.find({ type: 'Text', text: /[┌┐└┘│╞╡├┤┬┴┼╪─━═]/ })).toBeUndefined()
  const headers = ['Service', 'Regions', 'Version'].map(name => boxes.find(b => b.text === name && b.props.width !== undefined))
  const shares = headers.map(b => percent(b?.props.width))
  expect(shares.reduce((sum, n) => sum + n, 0)).toBe(100)
  expect(headers.map(b => [b?.props.flexShrink, b?.props.minWidth])).toEqual([[1, 'api-gateway'.length], [1, 'Regions'.length], [1, 'Version'.length]])
  expect((await ui.find({ key: 'b0' }))?.props.alignSelf).toBe('flex-start')
  expect(headers.every(b => b?.props.alignItems === 'flex-start')).toBe(true)
  const lines = boxes.filter(b => b.props.backgroundColor === ink)
  const walls = lines.filter(b => b.props.width === 0.12)
  const runs = lines.filter(b => typeof b.props.width === 'string')
  const spans = lines.filter(b => b.props.width === undefined)
  if (tableStyle === 'box') {
    expect(walls).toHaveLength(12)
    expect(spans.map(b => b.props.height)).toEqual(Array(5).fill(0.06))
    expect(runs).toHaveLength(0)
    expect(headers.every(b => b?.props.paddingY === 1)).toBe(true)
  } else {
    expect(walls).toHaveLength(0)
    expect(spans).toHaveLength(0)
    const rows = tableStyle === 'minimal' ? 1 : 2
    expect(runs.map(b => percent(b.props.width))).toEqual(Array.from({ length: rows }, () => shares).flat())
    expect(runs.map(b => b.props.minWidth)).toEqual(Array.from({ length: rows }, () => headers.map(h => h?.props.minWidth)).flat())
    expect(runs.slice(0, 3).map(b => b.props.height)).toEqual(Array(3).fill(tableStyle === 'grid' ? 0.12 : 0.06))
  }
  await ui.unmount()
})

test('a theme without a table rule color draws desktop table lines in gray', { options: { theme: 'mono' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'desktop' })
  const walls = (await ui.findAll({ type: 'Box' })).filter(b => b.props.width === 0.12)
  expect(walls.length > 0 && walls.every(b => b.props.backgroundColor === 'gray')).toBe(true)
  await ui.unmount()
})

test('tableStyle rules keeps the open look', { options: { tableStyle: 'rules' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /┌|│/ })).toBeUndefined()
  await ui.unmount()
})

const longCode = (n: number) => `\`\`\`text\n${Array.from({ length: n }, (_, i) => `step ${i + 1}`).join('\n')}\n\`\`\``

test('code blocks of 10+ lines get one numbered Text per line, shorter ones none', async $ => {
  const ui = await $.ui.mount({ ...draw(longCode(12)), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^ 1  $/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^12  $/ })).toBeDefined()
  await ui.unmount()
  const short = await $.ui.mount({ ...draw(longCode(9)), surface: 'terminal' })
  expect(await short.find({ type: 'Text', text: /^step 9$/ })).toBeDefined()
  expect(await short.find({ type: 'Text', text: /^9  step 9$/ })).toBeUndefined()
  await short.unmount()
})

test('a wrapped numbered line keeps its continuation after the gutter', async $ => {
  const long = `${'word '.repeat(40).trim()}`
  const text = `\`\`\`text\n${[long, ...Array.from({ length: 11 }, (_, i) => `step ${i + 2}`)].join('\n')}\n\`\`\``
  const ui = await $.ui.mount({ ...draw(text), surface: 'terminal' })
  const rows = (await ui.findAll({ type: 'Box' })).filter(b => b.props.flexDirection === 'row' && /^ 1  /.test(b.text ?? ''))
  expect(rows.length).toBe(1)
  expect((await ui.find({ type: 'Text', text: /^ 1  $/ }))).toBeDefined()
  expect((await ui.find({ type: 'Text', text: long }))).toBeDefined()
  await ui.unmount()
})

test('long code blocks fold to 20 lines, open and fold back on press, and copy every line', async ($, on) => {
  const copied: string[] = []
  on('ui.copy', (_, e) => {
    copied.push(e.text)
    return { value: { isCopied: true as const } }
  })
  for (const [surface, n] of [['terminal', 40], ['desktop', 45]] as const) {
    const ui = await $.ui.mount({ ...draw(longCode(n)), surface })
    const shown = async () => surface === 'desktop' ? String((await ui.find({ type: 'Code' }))!.props.source).split('\n').length : (await ui.findAll({ type: 'Text', text: /^ *\d+  $/ })).length
    expect(await shown()).toBe(20)
    expect((await ui.find({ key: 'fold0' }))?.props.label).toBe(`+${n - 20} more lines`)
    await ui.press({ key: 'copy0' })
    expect(copied.at(-1)).toBe(Array.from({ length: n }, (_, i) => `step ${i + 1}`).join('\n'))
    await ui.press({ key: 'fold0' })
    expect(await shown()).toBe(n)
    expect((await ui.find({ key: 'fold0' }))?.props.label).toBe('show less')
    await ui.press({ key: 'fold0' })
    expect(await shown()).toBe(20)
    expect((await ui.find({ key: 'fold0' }))?.props.label).toBe(`+${n - 20} more lines`)
    await ui.unmount()
  }
})

test('folds open starts a long code block open, folds it on press and opens it again', { options: { folds: 'open' } }, async $ => {
  for (const [surface, n] of [['terminal', 40], ['desktop', 45]] as const) {
    const ui = await $.ui.mount({ ...draw(longCode(n)), surface })
    const shown = async () => surface === 'desktop' ? String((await ui.find({ type: 'Code' }))!.props.source).split('\n').length : (await ui.findAll({ type: 'Text', text: /^ *\d+  $/ })).length
    expect(await shown()).toBe(n)
    expect((await ui.find({ key: 'fold0' }))?.props.label).toBe('show less')
    await ui.press({ key: 'fold0' })
    expect(await shown()).toBe(20)
    expect((await ui.find({ key: 'fold0' }))?.props.label).toBe(`+${n - 20} more lines`)
    await ui.press({ key: 'fold0' })
    expect(await shown()).toBe(n)
    await ui.unmount()
  }
})

const nodeCount = (n: unknown): number =>
  n == null || n === false ? 0 : Array.isArray(n) ? n.reduce((a: number, c) => a + nodeCount(c), 0) : typeof n !== 'object' ? 1 : 1 + nodeCount((n as { children?: unknown[] }).children)

const hugeCode = (name = 'v') => `\`\`\`ts\n${Array.from({ length: 900 }, (_, i) => `const ${name}${i} = await fetch("/api/${i}", { retries: ${i % 5}, cache: false })`).join('\n')}\n\`\`\``

const takesLongCode = ($: Parameters<TestBody>[0]) =>
  $.ui.mount({ ...draw(`\`\`\`ts\n${'x'.repeat(10001)}\n\`\`\``), surface: 'desktop' }).then(ui => ui.unmount().then(() => true), () => false)

test('an opened 900-line code block shows 400 lines, counts the rest and keeps show less under the node ceiling', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    if (surface === 'desktop' && !(await takesLongCode($))) continue
    const ui = await $.ui.mount({ ...draw(hugeCode(surface)), surface })
    await ui.press({ key: 'fold0' })
    expect(nodeCount(await ui.drawn())).toBeLessThan(20000)
    expect((await ui.find({ key: 'fold0' }))?.props.label).toBe('show less')
    expect(await ui.find({ type: 'Text', text: /^… \+500 lines$/ })).toBeDefined()
    if (surface === 'terminal') expect([!!(await ui.find({ type: 'Text', text: /^const terminal399 / })), !!(await ui.find({ type: 'Text', text: /^const terminal400 / }))]).toEqual([true, false])
    else expect(String((await ui.find({ type: 'Code' }))!.props.source).split('\n').length).toBe(400)
    await ui.unmount()
  }
})

const textIn = (n: unknown): number =>
  Array.isArray(n) ? n.reduce((a: number, c) => a + textIn(c), 0) : typeof n === 'string' ? n.length : n !== null && typeof n === 'object' ? textIn((n as { children?: unknown }).children) : 0

test('a reply past the node budget draws its remaining blocks as dim source, ends on a copy note and stays under the engine ceilings', async $ => {
  const items = (n: number, mark: string, gap: string) => Array.from({ length: n }, (_, i) => `${mark}**item** ${i} with \`code\` and some words`).join(gap)
  for (const [surface, n, mark, gap] of [['terminal', 3000, '- ', '\n'], ['desktop', 3000, '- ', '\n'], ['terminal', 5000, '', '\n\n']] as const) {
    const ui = await $.ui.mount({ ...draw(`# Inventory\n\n${items(n, mark, gap)}`), surface })
    const drawn = await ui.drawn()
    expect(nodeCount(drawn)).toBeLessThan(20000)
    expect(textIn(drawn)).toBeLessThan(60000)
    expect(await ui.find({ type: 'Text', text: /^Inventory$/ })).toBeDefined()
    const texts = await ui.findAll({ type: 'Text' })
    const last = texts[texts.length - 1]!
    expect(last.text).toMatch(/^… \+\d+ lines · \/prismantis copy for the whole reply$/)
    expect(last.props.dimColor).toBe(true)
    expect(Math.max(...texts.map(t => (t.text ?? '').length))).toBeLessThanOrEqual(10000)
    await ui.unmount()
  }
})

test('a reply of long paragraphs under the node budget still stops under the engine text ceiling and keeps its copy button', async $ => {
  const words = 'word '.repeat(80)
  const ui = await $.ui.mount({ ...draw(`# Notes\n\n${Array.from({ length: 300 }, (_, i) => `Note ${i}: ${words}`).join('\n\n')}`), surface: 'terminal' })
  const drawn = await ui.drawn()
  expect(textIn(drawn)).toBeLessThan(100000)
  const texts = await ui.findAll({ type: 'Text' })
  expect(texts[texts.length - 1]!.text).toMatch(/^… \+\d+ lines · \/prismantis copy for the whole reply$/)
  expect((await ui.findAll({ type: 'Button' })).some(b => b.props.label === '⧉ copy reply')).toBe(true)
  await ui.unmount()
})

test('folds open caps a 900-line code block at 400 lines', { options: { folds: 'open' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(hugeCode()), surface: 'terminal' })
  expect(nodeCount(await ui.drawn())).toBeLessThan(20000)
  expect((await ui.find({ key: 'fold0' }))?.props.label).toBe('show less')
  expect(await ui.find({ type: 'Text', text: /^… \+500 lines$/ })).toBeDefined()
})

test('a folded code block colors its last shown line from the whole block, so a string that runs past the fold stays a string', async $ => {
  const t = PRESETS['catppuccin-mocha']
  const lines = [...Array.from({ length: 19 }, (_, i) => `let a${i} = ${i}`), 'const s = `line twenty', ...Array.from({ length: 20 }, (_, i) => `more ${i}`), 'end`']
  const ui = await $.ui.mount({ ...draw(`\`\`\`ts\n${lines.join('\n')}\n\`\`\``), surface: 'terminal' })
  expect((await ui.findAll({ type: 'Text', text: /^ *\d+  $/ })).length).toBe(20)
  expect((await ui.findAll({ type: 'Text' })).filter(n => n.props.color === t.codeString && /line twenty/.test(n.text ?? '')).length).toBe(1)
  await ui.unmount()
})

test('two code blocks that differ only in where lines break fold on their own', async $ => {
  const body = Array.from({ length: 29 }, () => 'x').join('\n')
  const ui = await $.ui.mount({ ...draw(`\`\`\`text\nab\nc\n${body}\n\`\`\`\n\nand\n\n\`\`\`text\na\nbc\n${body}\n\`\`\``), surface: 'terminal' as const })
  await ui.press({ key: 'fold0' })
  expect((await ui.find({ key: 'fold0' }))?.props.label).toBe('show less')
  expect((await ui.find({ key: 'fold2' }))?.props.label).toBe('+11 more lines')
  await ui.unmount()
})

for (const surface of ['terminal', 'desktop'] as const) test(`a list item on ${surface} ${surface === 'desktop' ? 'keeps its marker on the first line, unshrunk, when its text wraps' : 'draws its marker as plain text beside its text'}`, async $ => {
  const ui = await $.ui.mount({ ...draw(`1. ${'long words '.repeat(30).trim()}\n2. Short`), surface })
  const rows = (await ui.findAll({ type: 'Box' })).filter(b => b.props.flexDirection === 'row' && /^1\. long/.test(b.text ?? ''))
  const row = rows[rows.length - 1]
  expect(row).toBeDefined()
  const holders = (await ui.findAll({ type: 'Box' })).filter(b => b.props.flexShrink === 0 && b.text === '1. ')
  if (surface === 'desktop') {
    expect(row!.props.alignItems).toBe('flex-start')
    expect(holders).toHaveLength(1)
  } else {
    expect(row!.props.alignItems).toBeUndefined()
    expect(holders).toHaveLength(0)
  }
  await ui.unmount()
})

test('desktop columns ask for no more than their planned width, so long words break as in the terminal', async $ => {
  const table = '| a | b | c |\n|---|---|---|\n| src/components/navigation/sidebar.tsx | tests/integration/checkout.test.ts | docs/records/001-architecture-overview.md |'
  const ui = await $.ui.mount({ ...draw(table), surface: 'desktop', viewport: { columns: 40, rows: 20 } })
  const headers = ['a', 'b', 'c'].map(async name => (await ui.findAll({ type: 'Box' })).find(b => b.text === name && typeof b.props.width === 'string'))
  const minimums = (await Promise.all(headers)).map(b => b?.props.minWidth as number)
  expect(minimums.every(n => typeof n === 'number')).toBe(true)
  expect(minimums.reduce((sum, n) => sum + n, 0)).toBeLessThanOrEqual(36)
  await ui.unmount()
})

test('a held box table on desktop keeps the gap between each wall and the cell after it', { options: { rtl: 'iterm' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('| Name | Value |\n|---|---|\n| greeting | שלום |'), surface: 'desktop' })
  const walls = (await ui.findAll({ type: 'Box' })).filter(b => b.props.width === 0.12)
  expect(walls).toHaveLength(6)
  expect(walls.filter(b => b.props.marginRight === 1)).toHaveLength(4)
  expect(walls.filter(b => b.props.marginLeft === 1)).toHaveLength(4)
  await ui.unmount()
})

for (const surface of ['terminal', 'desktop'] as const) test(`a right-to-left box table with the inverse shape on ${surface} draws its rows ${surface === 'desktop' ? 'with the same walls as its frame' : 'as text lines'}`, { options: { rtl: 'apple-terminal' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('| שם | ערך |\n|---|---|\n| אחד | שתיים |'), surface })
  const glyphs = await ui.find({ type: 'Text', text: /│/ })
  const walls = (await ui.findAll({ type: 'Box' })).filter(b => b.props.width === 0.12)
  if (surface === 'desktop') {
    expect(glyphs).toBeUndefined()
    expect(walls.length).toBeGreaterThan(0)
  } else {
    expect(glyphs).toBeDefined()
    expect(walls).toHaveLength(0)
  }
  await ui.unmount()
})

for (const rtl of ['iterm', 'apple-terminal'] as const) for (const surface of ['terminal', 'desktop'] as const) test(`a wrapped right-to-left list item with rtl ${rtl} on ${surface} ${surface === 'desktop' ? 'keeps its marker on the first line, unshrunk' : 'draws its marker as plain text'}`, { options: { rtl } }, async $ => {
  const ui = await $.ui.mount({ ...draw(`1. ${'מילים ארוכות '.repeat(25).trim()}\n2. קצר`), surface })
  const boxes = await ui.findAll({ type: 'Box' })
  const holders = boxes.filter(b => b.props.flexShrink === 0 && /^\s*1\.?\s*$|^\s*\.1\s*$/.test(b.text ?? ''))
  const rows = boxes.filter(b => b.props.flexDirection === 'row' && b.props.alignItems === 'flex-start' && /מילים/.test(b.text ?? ''))
  if (surface === 'desktop') {
    expect(holders.length).toBeGreaterThan(0)
    expect(rows.length).toBeGreaterThan(0)
  } else {
    expect(holders).toHaveLength(0)
    expect(rows).toHaveLength(0)
  }
  await ui.unmount()
})

test('a line break stays only before a tinted translation line', async () => {
  const gray = (s: string) => `\u001b[90m${s}\u001b[39m`
  const [plain, para, list] = parse(`one\ntwo\n\nHello world.\n${gray('你好世界。')}\n\n- item\n  ${gray('项目')}\n  more`, { numbers: false, paths: false })
  if (plain?.kind !== 'paragraph' || para?.kind !== 'paragraph' || list?.kind !== 'list') throw new Error('unexpected blocks')
  expect(plain.inline).toEqual([{ kind: 'text', text: 'one two' }])
  expect(para.inline.map(n => ('text' in n ? n.text : ''))).toEqual(['Hello world.\n', '你好世界。'])
  expect(list.items[0]?.inline.map(n => ('text' in n ? n.text : ''))).toEqual(['item\n', '项目', ' more'])
})

test('translation colors from BBilingual survive, other escape codes do not', async () => {
  const gray = (s: string) => `\u001b[90m${s}\u001b[39m`
  const [para, heading, other] = parse(`Hi **all**.\n${gray('你好')}**${gray('大家')}**\n\n## Results / ${gray('结果')}\n\nkeep \u001b[31mred\u001b[0m \u001b[36mcyan\u001b[39m`, { numbers: false, paths: false })
  if (para?.kind !== 'paragraph' || heading?.kind !== 'heading' || other?.kind !== 'paragraph') throw new Error('unexpected blocks')
  expect(para.inline.at(-2)).toEqual({ kind: 'dim', text: '你好', tint: 'gray' })
  expect(para.inline.at(-1)).toEqual({ kind: 'strong', children: [{ kind: 'dim', text: '大家', tint: 'gray' }] })
  expect(heading.inline.at(-1)).toEqual({ kind: 'dim', text: '结果', tint: 'gray' })
  expect(other.inline).toEqual([{ kind: 'text', text: 'keep red ' }, { kind: 'dim', text: 'cyan', tint: 'cyan' }])
  expect(JSON.stringify([para, heading, other])).not.toMatch(/[\u001b\uE000-\uE1FF]/)
  expect(para.raw).toBe('Hi **all**.\n你好**大家**')
})

test('a tinted translation is drawn in its color', async $ => {
  for (const [code, look] of [['90', { color: 'gray' }], ['36', { color: 'cyan' }], ['3', { italic: true }], ['2', { dimColor: true }]] as const) {
    const ui = await $.ui.mount({ ...draw(`Hello.\n\u001b[${code}m你好\u001b[${code === '2' ? '22' : code === '3' ? '23' : '39'}m`), surface: 'terminal' })
    expect((await ui.find({ type: 'Text', text: /^你好$/ }))?.props).toMatchObject(look)
    await ui.unmount()
  }
})

const CODE = '```ts\nconst a = 1\n```'

for (const surface of SURFACES) test(`copyButtonStyle dim, the default, draws a copy button dim on ${surface}`, async $ => {
  const ui = await $.ui.mount({ ...draw(CODE), surface })
  const button = await ui.find({ key: 'copy0' })
  expect(button?.props.plain).toBe(true)
  expect(button?.props.dimColor).toBe(true)
  expect(button?.props.label).toBe('⧉ copy')
  await ui.unmount()
})

for (const surface of SURFACES) test(`copyButtonStyle inline draws a copy button in the accent color on ${surface}`, { options: { copyButtonStyle: 'inline' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(CODE), surface })
  const button = await ui.find({ key: 'copy0' })
  expect(button?.props.variant).toBe('primary')
  expect(button?.props.dimColor).toBe(undefined)
  await ui.unmount()
})

const FILL = '#1c2233'

const codeLooks = [
  { options: { codeStyle: 'plain' }, border: undefined, fill: undefined, padding: undefined },
  { options: { codeStyle: 'framed' }, border: 'round', fill: undefined, padding: 1 },
  { options: { codeStyle: 'filled' }, border: undefined, fill: FILL, padding: 1 },
  { options: { codeStyle: 'card' }, border: 'round', fill: FILL, padding: 1 },
  { options: { codeStyle: 'fancy' }, border: undefined, fill: undefined, padding: undefined },
] as const

for (const look of codeLooks) test(`codeStyle ${look.options.codeStyle} draws its frame and fill`, { options: { ...look.options, codeFillColor: FILL, replyStyle: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(CODE), surface: 'terminal' })
  const block = await ui.find({ key: 'b0' })
  expect(block?.props.borderStyle).toBe(look.border)
  expect(block?.props.backgroundColor).toBe(look.fill)
  expect(block?.props.paddingX).toBe(look.padding)
  await ui.unmount()
})

test('a code block is plain by default, so a code color alone draws nothing', { options: { codeFillColor: FILL, codeBorderColor: '#123456', replyStyle: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(CODE), surface: 'terminal' })
  const block = await ui.find({ key: 'b0' })
  expect(block?.props.borderStyle).toBe(undefined)
  expect(block?.props.backgroundColor).toBe(undefined)
  expect(block?.props.paddingX).toBe(undefined)
  await ui.unmount()
})

for (const codeStyle of ['framed', 'filled', 'card'] as const) test(`codeStyle ${codeStyle} leaves the native code block alone off the terminal`, { options: { codeStyle, replyStyle: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(CODE), surface: 'desktop' })
  const block = await ui.find({ key: 'b0' })
  expect(block?.props.borderStyle).toBe(undefined)
  expect(block?.props.backgroundColor).toBe(undefined)
  await ui.unmount()
})

test('a code block fill defaults to a shade that differs from the reply fill', { options: { codeStyle: 'filled', replyStyle: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(CODE), surface: 'terminal' })
  const style = resolveStyle({})
  const fill = (await ui.find({ key: 'b0' }))?.props.backgroundColor
  expect(typeof fill).toBe('string')
  expect(fill).not.toBe(replyFill(style.theme, style.background))
  await ui.unmount()
})

test('codeStyle filled draws the frame in a theme with no colors to fill with', { options: { theme: 'mono', codeStyle: 'filled', replyStyle: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(CODE), surface: 'terminal' })
  const block = await ui.find({ key: 'b0' })
  expect(block?.props.borderStyle).toBe('round')
  expect(block?.props.backgroundColor).toBe(undefined)
  await ui.unmount()
})

test('a code block frame takes the rule color', { options: { codeStyle: 'framed', ruleColor: '#654321', replyStyle: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(CODE), surface: 'terminal' })
  expect((await ui.find({ key: 'b0' }))?.props.borderColor).toBe('#654321')
  await ui.unmount()
})

test('codeBorderColor colors a code block frame apart from the rule color', { options: { codeStyle: 'framed', ruleColor: '#654321', codeBorderColor: '#123456', replyStyle: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(CODE), surface: 'terminal' })
  expect((await ui.find({ key: 'b0' }))?.props.borderColor).toBe('#123456')
  await ui.unmount()
})

test('a framed code block with hover buttons stays wide enough for its head inside the frame', { options: { codeStyle: 'framed', copyButtonStyle: 'hover', replyStyle: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('```\nx\n```'), surface: 'terminal' })
  expect((await ui.find({ key: 'b0' }))?.props.minWidth).toBe('── code [ ⧉ copy ]'.length + 4)
  await ui.unmount()
})

test('two trailing spaces or a backslash end a paragraph line', async $ => {
  const [spaces, slash, soft, rtl] = parse('🟩🟩  \n ✅ DELIVERED  \n🟩🟩\n\none\\\ntwo\n\nthree  \nfour\\\n\nשלום  \nעולם', { numbers: false, paths: false })
  const text = (b: typeof spaces) => (b?.kind === 'paragraph' ? b.inline.map(n => ('text' in n ? n.text : '')).join('') : '')
  expect([text(spaces), text(slash), text(soft), text(rtl)]).toEqual(['🟩🟩\n✅ DELIVERED\n🟩🟩', 'one\ntwo', 'three\nfour\\', 'שלום\nעולם'])
  expect(spaces?.raw).toBe('🟩🟩  \n ✅ DELIVERED  \n🟩🟩')
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...draw('🟩🟩  \n✅ DELIVERED  \n🟩🟩'), surface })
    expect(await ui.find({ type: 'Text', text: /^🟩🟩\n✅ DELIVERED\n🟩🟩$/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('two trailing spaces or a backslash end a list item line', async $ => {
  const [list] = parse('- one  \n  two\\\n  three\n  four\n- שלום  \n  עולם\n  ```\n  c\n  ```\n  para  \n  next', { numbers: false, paths: false })
  if (list?.kind !== 'list') throw new Error('not a list')
  expect(list.items.map(it => displayText(it.inline))).toEqual(['one\ntwo\nthree four', 'שלום\nעולם'])
  const para = list.items[1]?.blocks?.[1]
  expect(para?.kind === 'paragraph' && displayText(para.inline)).toBe('para\nnext')
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...draw('- one  \n  two\n- שלום  \n  עולם'), surface })
    expect(await ui.find({ type: 'Text', text: /^one\ntwo$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /^שלום\nעולם$/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('a deeply nested list stops indenting at half the width, so its deepest items keep room for their text', { options: { replyStyle: 'off' } }, async $ => {
  const nest = Array.from({ length: 50 }, (_, i) => `${'  '.repeat(i)}- level ${i + 1}`).join('\n')
  const ui = await $.ui.mount({ ...draw(nest), viewport: { columns: 60, rows: 40 }, surface: 'terminal' })
  const pads = (await ui.findAll({ type: 'Box' })).map(b => Number(b.props.paddingLeft ?? 0))
  expect(Math.max(...pads)).toBeLessThanOrEqual(28)
  expect(await ui.find({ type: 'Text', text: /^level 50$/ })).toBeDefined()
  await ui.unmount()
})

for (const surface of ['terminal', 'desktop'] as const) test(`benchTable ${surface} colors changes in theme colors`, { options: { benchTable: 'color' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(BENCH), surface })
  expect((await ui.find({ type: 'Text', text: /^-10%$/ }))?.props.color).toBe(t.diffAdded)
  expect((await ui.find({ type: 'Text', text: /^\+14%$/ }))?.props.color).toBe(t.diffRemoved)
  expect((await ui.find({ type: 'Text', text: /^-62%$/ }))?.props.color).toBe(t.diffAdded)
  expect((await ui.find({ type: 'Text', text: /^0%$/ }))?.props.color).toBeUndefined()
  expect((await ui.find({ type: 'Text', text: /^parse$/ }))?.props.color).toBeUndefined()
  await ui.unmount()
})

test('benchTable trend draws a sparkline of the runs under the table', { options: { benchTable: 'trend' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(BENCH), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^\u2585$/ }))?.props.color).toBeUndefined()
  expect((await ui.find({ type: 'Text', text: /^\u2588$/ }))?.props.color).toBe(t.diffRemoved)
  expect((await ui.findAll({ type: 'Text', text: /^\u2581$/ })).every(x => x.props.color === t.diffAdded)).toBe(true)
  expect(await ui.findAll({ type: 'Text', text: /^\u2581$/ })).toHaveLength(2)
  await ui.unmount()
})

test('benchTable off keeps tables as written', { options: { benchTable: 'off' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(BENCH), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^-10%$/ }))?.props.color).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^\u2585$/ })).toBeUndefined()
  await ui.unmount()
})

test('a table without a change column draws no sparkline either', { options: { benchTable: 'trend' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(STATUS), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^\u2585$/ })).toBeUndefined()
  await ui.unmount()
})

test('a rate header makes higher changes the improvement', { options: { benchTable: 'color' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw('| Suite | Score | Change |\n|---|---:|:---|\n| parse | 82 | +3% |\n| layout | 88 | +6% |'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^\+3%$/ }))?.props.color).toBe(t.diffAdded)
  expect((await ui.find({ type: 'Text', text: /^\+6%$/ }))?.props.color).toBe(t.diffAdded)
  await ui.unmount()
})

test('benchTable stays off stacked tables', { options: { benchTable: 'trend', tableLayout: 'stacked', theme: 'dracula' } }, async $ => {
  const t = PRESETS['dracula']
  const ui = await $.ui.mount({ ...draw(BENCH), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^-10%$/ }))?.props.color).toBe(t.number)
  expect(await ui.find({ type: 'Text', text: /^\u2585$/ })).toBeUndefined()
  await ui.unmount()
})

for (const surface of ['terminal', 'desktop'] as const) test(`schemaTable ${surface} colors type cells by their family`, { options: { schemaTable: 'types' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(SCHEMA), surface })
  expect((await ui.find({ type: 'Text', text: /^uuid$/ }))?.props.color).toBe(t.codeString)
  expect((await ui.find({ type: 'Text', text: /^bigint$/ }))?.props.color).toBe(t.number)
  expect((await ui.find({ type: 'Text', text: /^timestamp$/ }))?.props.color).toBe(t.link)
  await ui.unmount()
})

test('schemaTable keys marks the constraint cells', { options: { schemaTable: 'keys' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(SCHEMA), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^PK$/ }))?.props.color).toBe(t.accent)
  expect((await ui.find({ type: 'Text', text: /^UNIQUE$/ }))?.props.color).toBe(t.codeComment)
  expect((await ui.find({ type: 'Text', text: /^FK/ }))?.props.color).toBe(t.link)
  await ui.unmount()
})

test('schemaTable full colors the types and marks the keys', { options: { schemaTable: 'full' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(SCHEMA), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^uuid$/ }))?.props.color).toBe(t.codeString)
  expect((await ui.find({ type: 'Text', text: /^PK$/ }))?.props.color).toBe(t.accent)
  await ui.unmount()
})

test('schemaTable keys finds a key column with no header to name it', { options: { schemaTable: 'keys' } }, async $ => {
  const t = PRESETS['catppuccin-mocha']
  const ui = await $.ui.mount({ ...draw(KEYLESS), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^PK$/ }))?.props.color).toBe(t.accent)
  expect((await ui.find({ type: 'Text', text: /^uuid$/ }))?.props.color).toBeUndefined()
  await ui.unmount()
})

test('schemaTable off keeps tables as written', async $ => {
  const ui = await $.ui.mount({ ...draw(SCHEMA), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^uuid$/ }))?.props.color).toBeUndefined()
  expect((await ui.find({ type: 'Text', text: /^PK$/ }))?.props.color).toBeUndefined()
  await ui.unmount()
})

test('a table with no column and type header draws no schema colors', { options: { schemaTable: 'full' } }, async $ => {
  const ui = await $.ui.mount({ ...draw('| Name | Type |\n|:-----|:-----|\n| id | uuid |'), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^uuid$/ }))?.props.color).toBeUndefined()
  await ui.unmount()
})

test('schemaTable stays off stacked tables', { options: { schemaTable: 'full', tableLayout: 'stacked' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(SCHEMA), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^uuid$/ }))?.props.color).toBeUndefined()
  await ui.unmount()
})

test('schemaTable types tells the families apart in a theme where they differ', { options: { schemaTable: 'types', theme: 'dracula' } }, async $ => {
  const t = PRESETS['dracula']
  const ui = await $.ui.mount({ ...draw(SCHEMA), surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^uuid$/ }))?.props.color).toBe(t.codeString)
  expect((await ui.find({ type: 'Text', text: /^bigint$/ }))?.props.color).toBe(t.number)
  expect(t.codeString).not.toBe(t.number)
  await ui.unmount()
})
