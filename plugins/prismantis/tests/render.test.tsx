import { expect, test } from 'claude-code/testing'

import { parse } from '../hooks/markdown'
import { PRESETS } from '../hooks/presets'
import { resolveStyle } from '../hooks/theme'

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

test('escaped pipes stay inside a cell', async () => {
  const [t] = parse('| a | b |\n|---|---|\n| x \\| y | z |', { numbers: false, paths: false })
  if (t?.kind !== 'table') throw new Error('not a table')
  expect(t.rows[0]?.length).toBe(2)
})

test('user colors override the theme, bad colors are ignored', async () => {
  const s = resolveStyle({ theme: 'catppuccin-mocha', tableHeaderColor: '#ff0000', numberColor: 'not a color', pathColor: 'cyan', linkColor: 'javascript:x' })
  expect(s.theme.tableHeader).toBe('#ff0000')
  expect(s.theme.number).toBe(PRESETS['catppuccin-mocha'].number)
  expect(s.theme.path).toBe('cyan')
  expect(s.theme.link).toBe(PRESETS['catppuccin-mocha'].link)
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
  expect(buttons.every(b => b.props.variant === "primary")).toBe(true)
  await ui.press({ key: buttons[2]!.key! })
  expect(copied).toEqual(['ls -la'])
  await ui.unmount()
})

test('copyButtons off draws no buttons', { options: { copyButtons: false } }, async $ => {
  const ui = await $.ui.mount({ ...draw('```bash\nls\n```'), surface: 'terminal' })
  expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
  await ui.unmount()
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

test('fence languages that name Prism internals fall back to plain code', async $ => {
  for (const lang of ['extend', 'toString', 'constructor', '__proto__']) {
    const ui = await $.ui.mount({ ...draw(`\`\`\`${lang}\nhello\n\`\`\``), surface: 'terminal' })
    expect((await ui.find({ type: 'Text', text: /^hello$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].codeText)
    await ui.unmount()
  }
})

test('tables draw boxed by default, with a double line under the header', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...draw(TABLE), surface })
    const top = (await ui.find({ type: 'Text', text: /^┌[─┬]+┐$/ }))?.text ?? ''
    expect(top.split('┬').length).toBe(3)
    const lines = [top, ...(await Promise.all([/^╞[═╪]+╡$/, /^├[─┼]+┤$/, /^└[─┴]+┘$/].map(async re => (await ui.find({ type: 'Text', text: re }))?.text ?? '')))]
    expect(lines.every(l => l.length === top.length && l.length > 0)).toBe(true)
    expect((await ui.find({ type: 'Text', text: /^Service$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].tableHeader)
    await ui.unmount()
  }
})

test('tableStyle rules keeps the open look', { options: { tableStyle: 'rules' } }, async $ => {
  const ui = await $.ui.mount({ ...draw(TABLE), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /┌|│/ })).toBeUndefined()
  await ui.unmount()
})
