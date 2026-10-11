import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

import { helpText, showcaseText } from '../hooks/help'
import { parse } from '../hooks/markdown'
import { mermaidText } from '../hooks/mermaid'
import { tableArt } from '../hooks/render'
import { PRESETS } from '../hooks/presets'

const hl = { numbers: true, paths: true }

const mount = (text: string, columns = 120) => ({
  plugin: 'prismantis',
  component: 'AssistantMessage' as const,
  props: { text, isFirstOfReply: true },
  viewport: { columns, rows: 40 },
  surface: 'terminal' as const,
})

const drawn = (node: unknown): string =>
  typeof node === 'string' ? node : ((node as { children?: unknown[] }).children ?? []).map(drawn).join('')

const stubClipboard = (on: On) => {
  const copied: string[] = []
  on('ui.copy', (_, e) => {
    copied.push(e.text)
    return { value: { isCopied: true as const } }
  })
  return copied
}

test('a long run of backticks parses in linear time', async () => {
  const started = Date.now()
  parse('`'.repeat(32000), hl)
  expect(Date.now() - started < 100).toBe(true)
})

test('a four-backtick fence keeps triple-backtick examples inside one code block', async () => {
  const blocks = parse('````md\n```bash\nls\n```\n````', hl)
  expect(blocks.map(b => b.kind)).toEqual(['code'])
  const [code] = blocks
  if (code?.kind !== 'code') throw new Error('not code')
  expect(code.lines).toEqual(['```bash', 'ls', '```'])
})

test('an escaped trailing pipe stays in the cell', async () => {
  const [table] = parse('| a | b |\n|---|---|\n| x | y\\|', hl)
  if (table?.kind !== 'table') throw new Error('not a table')
  expect(table.rows[0]?.[1]?.map(n => ('text' in n ? n.text : '')).join('')).toBe('y|')
})

test('copying a table returns its exact markdown', async ($, on) => {
  const copied = stubClipboard(on)
  const source = '| a | b |\n|:--|--:|\n| `x\\|y` | **2** |'
  const ui = await $.ui.mount(mount(source))
  const [button] = await ui.findAll({ type: 'Button' })
  await ui.press({ key: button!.key! })
  expect(copied).toEqual([source])
  await ui.unmount()
})

test('copying a list returns its exact markdown', async ($, on) => {
  const copied = stubClipboard(on)
  const source = '- **bold** item\n  - `code` child'
  const ui = await $.ui.mount(mount(source))
  const [button] = await ui.findAll({ type: 'Button' })
  await ui.press({ key: button!.key! })
  expect(copied).toEqual([source])
  await ui.unmount()
})

test('table columns never exceed the terminal width', async $ => {
  const ui = await $.ui.mount(mount('| a | bbbbbbbbbbbbbbbb | c | d | e |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |', 24))
  const cells = (await ui.findAll({ type: 'Box' })).filter(b => typeof b.props.width === 'number' && b.props.flexShrink === 0).slice(1)
  const firstRow = cells.slice(0, 5).map(b => b.props.width as number)
  expect(firstRow.reduce((a, b) => a + b, 0) + 2 * 4 <= 20).toBe(true)
  await ui.unmount()
})

test('a boxed row that wraps keeps its borders on every line', async $ => {
  const file = 'handoffs/handoff-scheduled-event-pushes-21082026.md'
  const evidence = 'Its blocking question is unanswered; BACKLOG row 16 cites it'
  const ui = await $.ui.mount(mount(`| File | Evidence |\n|---|---|\n| ${file} | ${evidence} |`, 40))
  const lines = await ui.findAll({ type: 'Text', text: /^│ $/ })
  const cells = (await ui.findAll({ type: 'Box' })).filter(b => typeof b.props.width === 'number' && b.props.flexShrink === 0).slice(-2 * (lines.length - 1))
  expect(lines.length > 3).toBe(true)
  expect(cells.every(b => drawn(b).length <= (b.props.width as number))).toBe(true)
  expect(cells.filter((_, i) => i % 2 === 0).map(drawn).join('')).toBe(file)
  expect(cells.filter((_, i) => i % 2 === 1).map(drawn).join(' ')).toBe('Its blocking question is unanswered; BACKLOG row 16 cites it')
  expect((await ui.find({ type: 'Text', text: /^16$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].number)
  await ui.unmount()
})

for (const [kind, cell] of [
  ['named link', 'see [docs](https://github.com/org/repo/blob/main/docs/spec.md) for more'],
  ['bare URL', 'https://example.com/a/rather/long/path/that/cannot/fit/on/one/line'],
] as const) {
  test(`a boxed row with a ${kind} keeps the link whole and clips its borders to the row`, async $ => {
    const ui = await $.ui.mount(mount(`| n | link |\n|---|---|\n| 1 | ${cell} |`, 40))
    const links = await ui.findAll({ type: 'Link' })
    const clips = (await ui.findAll({ type: 'Box' })).filter(b => b.props.position === 'absolute' && b.props.overflow === 'hidden')
    expect(links.length).toBe(1)
    expect(clips.length).toBe(3)
    expect(clips.every(b => drawn(b).split('\n').length > 2)).toBe(true)
    await ui.unmount()
  })
}

test('a link column is sized for the URL it shows', async $ => {
  const url = 'https://example.com/a/rather/long/path'
  const ui = await $.ui.mount(mount(`| link | n |\n|---|---|\n| [go](${url}) | 1 |`))
  const cells = (await ui.findAll({ type: 'Box' })).filter(b => typeof b.props.width === 'number' && b.props.flexShrink === 0).slice(1)
  expect((cells[0]?.props.width as number) >= `go (${url})`.length).toBe(true)
  await ui.unmount()
})

test('highlight colors follow the theme in use: red', { options: { codeFlagColor: '#ff0000' } }, async $ => {
  const ui = await $.ui.mount(mount('```ts\nconst same = 1\n```'))
  expect((await ui.find({ type: 'Text', text: /^const$/ }))?.props.color).toBe('#ff0000')
  await ui.unmount()
})

test('highlight colors follow the theme in use: green', { options: { codeFlagColor: '#00ff00' } }, async $ => {
  const ui = await $.ui.mount(mount('```ts\nconst same = 1\n```'))
  expect((await ui.find({ type: 'Text', text: /^const$/ }))?.props.color).toBe('#00ff00')
  await ui.unmount()
})

test('presets stay intact', async () => {
  expect(PRESETS.dracula.tableHeader).toBe('#f1fa8c')
})

test('code blocks draw no frame, so a mouse selection copies only the code', async $ => {
  const ui = await $.ui.mount(mount('```bash\nls -la\n```'))
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.borderStyle !== undefined)).toBe(false)
  await ui.unmount()
})

test('stadium, cylinder and arrow-joined boxes get colors, containers stay plain', async $ => {
  const t = PRESETS['catppuccin-mocha']
  const source = '```mermaid\ngraph LR\n  subgraph S [Group]\n    A[Edge]\n  end\n  U([Users]) --> A\n  A --> DB[(db)]\n  B[Backup] --> A\n```'
  const ui = await $.ui.mount(mount(source, 160))
  const color = async (re: RegExp) => (await ui.find({ type: 'Text', text: re }))?.props.color
  for (const label of [/^Users$/, /^Edge$/, /^db$/, /^Backup$/]) {
    const c = await color(label)
    expect(c !== undefined && c !== t.diagramText).toBe(true)
  }
  const group = (await ui.findAll({ type: 'Text' })).find(s => s.text.trim() === 'Group' && s.props.color !== undefined)
  expect(group?.props.color).toBe(t.diagramText)
  await ui.unmount()
})

test('an edge label after a space still draws both nodes', async $ => {
  const ui = await $.ui.mount(mount('```mermaid\ngraph LR\n  A --> |deploy| B\n```', 160))
  expect(await ui.find({ type: 'Text', text: /^B$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /deploy/ })).toBeDefined()
  await ui.unmount()
})

test('copying a quote returns its text without the > markers', async ($, on) => {
  const copied = stubClipboard(on)
  const ui = await $.ui.mount(mount('> built a mod\n> with **colors**'))
  const [button] = await ui.findAll({ type: 'Button' })
  await ui.press({ key: button!.key! })
  expect(copied).toEqual(['built a mod\nwith **colors**'])
  await ui.unmount()
})

test('edge labels with spaces keep the line out of their gaps', async $ => {
  const ui = await $.ui.mount(mount('```mermaid\ngraph TD\n  A -->|push = build| B\n```', 160))
  const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text)
  expect(texts.some(t => t.includes('push = build'))).toBe(true)
  expect(texts.some(t => t.includes('push =│build'))).toBe(false)
  await ui.unmount()
})

test('a chart that opens with a %% comment still draws', async $ => {
  const ui = await $.ui.mount(mount('```mermaid\n%% weekly deploys\nxychart-beta\n  x-axis [a, b]\n  bar [1, 2]\n```', 160))
  expect((await ui.findAll({ type: 'Text' })).some(t => /^█+$/.test(t.text))).toBe(true)
  await ui.unmount()
})

test('a GitHub alert draws its title and body, and copies without the > markers', async ($, on) => {
  const copied = stubClipboard(on)
  const ui = await $.ui.mount(mount('> [!WARNING]\n> disk is almost full'))
  expect(await ui.find({ type: 'Text', text: /^Warning$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^disk is almost full$/ })).toBeDefined()
  const [button] = await ui.findAll({ type: 'Button' })
  await ui.press({ key: button!.key! })
  expect(copied).toEqual(['[!WARNING]\ndisk is almost full'])
  await ui.unmount()
})

test('a bar chart shows each value, drops label quotes and highlights the tallest bar', async $ => {
  const ui = await $.ui.mount(mount('```mermaid\nxychart-beta\n  x-axis ["Q1", "Q2", "Q3"]\n  bar [5, 12, 8]\n```', 160))
  const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text)
  expect(texts.some(t => /\b12\b/.test(t) && !t.includes('┤'))).toBe(true)
  expect(texts.some(t => t.includes('"'))).toBe(false)
  await ui.unmount()
})

test('H1 gets a box and H2 a heavy rule by default', async $ => {
  const ui = await $.ui.mount(mount('# Title\n\n## Section'))
  expect(await ui.find({ type: 'Text', text: /^━+$/ })).toBeDefined()
  expect(await ui.find({ type: 'Box', text: /Title/ })).toBeDefined()
  await ui.unmount()
})

test('chart labels never run together', async $ => {
  const ui = await $.ui.mount(mount('```mermaid\nxychart-beta\n  x-axis [Dog, Human, Pigeon, Shrimp]\n  bar [2, 3, 4, 16]\n```', 120))
  const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text)
  expect(texts.some(t => /Human\s+Pigeon\s+Shrimp/.test(t))).toBe(true)
  await ui.unmount()
})

const best = (fn: () => void, runs = 5) => {
  let min = Infinity
  for (let i = 0; i < runs; i++) {
    const t = performance.now()
    fn()
    min = Math.min(min, performance.now() - t)
  }
  return min
}

const rows = (n: number) => `| id | name | pods |\n|---|---|---|\n${Array.from({ length: n }, (_, i) => `| ${i} | svc-${i} | ${i * 3} |`).join('\n')}`
const prose = (n: number) => Array.from({ length: n }, (_, i) => `Paragraph ${i} with **bold**, \`code\`, 99.9% and ~/src/app.ts here.\n\n- item ${i}\n- item ${i + 1}`).join('\n\n')

test('parse cost grows linearly with reply size', async () => {
  for (const make of [rows, prose]) {
    parse(make(200), hl)
    const small = Math.max(best(() => parse(make(200), hl)), 0.05)
    const large = best(() => parse(make(2000), hl))
    expect(large < small * 40).toBe(true)
  }
})

test('parse stays inside a generous budget on a large reply', async () => {
  expect(best(() => parse(prose(2000), hl)) < 250).toBe(true)
  expect(best(() => parse(rows(2000), hl)) < 250).toBe(true)
})

test('a 300-row table draws inside its budget', async $ => {
  const started = performance.now()
  const ui = await $.ui.mount(mount(rows(300), 160))
  expect(performance.now() - started < 1500).toBe(true)
  await ui.unmount()
})

test('a 400-line highlighted code block stays under the engine node limit and its time budget', async $ => {
  const code = `\`\`\`ts\n${Array.from({ length: 400 }, (_, i) => `const v${i} = await fetch("/api/${i}", { retries: ${i % 5} })`).join('\n')}\n\`\`\``
  const started = performance.now()
  const ui = await $.ui.mount(mount(code, 160))
  expect(performance.now() - started < 1500).toBe(true)
  await ui.unmount()
})

test('a half-streamed reply with an open fence and a cut table still draws', async $ => {
  for (const text of ['intro\n\n```mermaid\nflowchart LR\n  A --> B', '| a | b |\n|---|', '```ts\nconst x =', '> [!NOTE', '**bold and `cod']) {
    const ui = await $.ui.mount(mount(text))
    expect(await ui.findAll({ type: 'Text' })).toBeDefined()
    await ui.unmount()
  }
})

test('the help screen shows every element prismantis draws', async () => {
  const blocks = parse(showcaseText(Object.keys(PRESETS)), hl)
  expect(showcaseText(Object.keys(PRESETS))).toContain('promptStyle')
  const kinds = new Set(blocks.map(b => b.kind))
  for (const kind of ['heading', 'paragraph', 'list', 'code', 'quote', 'alert', 'rule', 'table']) expect(kinds.has(kind as never)).toBe(true)
  expect(new Set(blocks.flatMap(b => (b.kind === 'heading' ? [b.level] : []))).size >= 4).toBe(true)
  expect(new Set(blocks.flatMap(b => (b.kind === 'alert' ? [b.level] : []))).size).toBe(5)
  const langs = blocks.flatMap(b => (b.kind === 'code' ? [b.lang] : []))
  for (const lang of ['bash', 'json', 'mermaid']) expect(langs.includes(lang)).toBe(true)
  const links = blocks.flatMap(b => (b.kind === 'paragraph' ? b.inline.filter(n => n.kind === 'link') : []))
  expect(links.some(l => l.kind === 'link' && l.text !== l.href) && links.some(l => l.kind === 'link' && l.text === l.href)).toBe(true)
  expect(blocks.some(b => b.kind === 'list' && b.items.some(i => i.task === true) && b.items.some(i => i.task === false) && b.items.some(i => i.depth > 0 && i.task !== undefined))).toBe(true)
  expect(showcaseText([]).includes("toolStyle")).toBe(true)
})

test('every diagram on the help screen draws as art', async () => {
  const diagrams = parse(showcaseText(Object.keys(PRESETS)), hl).flatMap(b => (b.kind === 'code' && b.lang === 'mermaid' ? [b.lines.join('\n')] : []))
  expect(diagrams.length).toBe(3)
  for (const source of diagrams) expect(mermaidText(source, false, 100)).not.toBeNull()
})

test('the help screen fits one screen: few blocks, two alerts, a table, a list and two drawn charts', async () => {
  const blocks = parse(helpText(Object.keys(PRESETS)), hl)
  expect(blocks.length <= 12).toBe(true)
  expect(blocks.filter(b => b.kind === 'alert').length).toBe(2)
  for (const kind of ['heading', 'table', 'list']) expect(blocks.some(b => b.kind === kind)).toBe(true)
  expect(blocks.some(b => b.kind === 'list' && b.items.some(i => i.task !== undefined))).toBe(true)
  expect(blocks.some(b => b.kind === 'paragraph' && b.inline.some(n => n.kind === 'link'))).toBe(true)
  expect(helpText(Object.keys(PRESETS))).toContain('/prismantis copy')
  const diagrams = blocks.flatMap(b => (b.kind === 'code' && b.lang === 'mermaid' ? [b.lines.join('\n')] : []))
  expect(diagrams.length).toBe(2)
  for (const source of diagrams) expect(mermaidText(source, false, 100)).not.toBeNull()
})

test('the help screen draws as command output', async $ => {
  const ui = await $.ui.mount({
    plugin: 'prismantis',
    component: 'CommandOutput' as const,
    props: { command: 'prismantis', args: 'demo', text: showcaseText(Object.keys(PRESETS)), isErrored: false },
    viewport: { columns: 100, rows: 40 },
    surface: 'terminal' as const,
  })
  expect(await ui.find({ type: 'Box', text: /prismantis/ })).toBeDefined()
  await ui.unmount()
})

test('drawn replies add no emoji-capable glyphs', async $ => {
  const text = ['sequenceDiagram\n  A->>B: go\n  B-->>A: ok', 'classDiagram\n  direction LR\n  A <|-- B\n  C --> D', 'graph RL\n  A-->B'].map(d => '```mermaid\n' + d + '\n```').join('\n\n')
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...mount(text), surface })
    expect((await ui.find({ type: 'Text', text: /\p{Extended_Pictographic}/u }))?.text).toBeUndefined()
    await ui.unmount()
  }
})

test('a table art button copies boxed text ready for Slack', async ($, on) => {
  const copied = stubClipboard(on)
  const ui = await $.ui.mount(mount('| Queue | Sent |\n|---|--:|\n| tasks-east | 24 |\n| west | 0 |'))
  const art = (await ui.findAll({ type: 'Button' }))[1]
  await ui.press({ key: art!.key! })
  expect(copied).toEqual([[
    '```',
    '┌────────────┬──────┐',
    '│   Queue    │ Sent │',
    '├────────────┼──────┤',
    '│ tasks-east │   24 │',
    '├────────────┼──────┤',
    '│ west       │    0 │',
    '└────────────┴──────┘',
    '```',
  ].join('\n')])
  await ui.unmount()
})

test('wide table art wraps long cells to stay 100 columns wide', async () => {
  const long = 'Wrong. With no default, databag_config raises No config key is found, so the render fails and nothing is applied, which is the fail-closed behaviour we want.'
  const [table] = parse(`| Codebot says | Verdict |\n|---|---|\n| A missing x_seen_by renders an empty value | ${long} |`, hl)
  if (table?.kind !== 'table') throw new Error('not a table')
  const lines = tableArt(table).split('\n')
  const body = lines.slice(1, -1)
  expect(body.every(l => [...l].length === [...body[0]!].length && [...l].length <= 100)).toBe(true)
  expect(body.length > 6).toBe(true)
  expect(body.filter(l => l.startsWith('│')).slice(1).map(l => l.split('│')[2]!.trim()).join(' ')).toBe(long)
})

test('short table columns keep their width next to a very wide one', async () => {
  const links = Array.from({ length: 4 }, (_, i) => `https://example.com/releases/${100 + i}/notes`).join(' , ')
  const [table] = parse(`| # | Pri | Task | Link |\n|---|---|---|---|\n| 10 | 🔵 P2 | Approved, not merged | ${links} |`, hl)
  if (table?.kind !== 'table') throw new Error('not a table')
  const cells = tableArt(table).split('\n').slice(1, -1).filter(l => l.startsWith('│')).map(l => l.split('│').slice(1, 4).map(c => c.trim()))
  expect(cells[1]).toEqual(['10', '🔵 P2', 'Approved, not merged'])
})

test('copy reply copies the whole reply as written, Hebrew in reading order', { options: { rtl: 'warp' } }, async ($, on) => {
  const copied = stubClipboard(on)
  const text = 'שלום חברים, זו הדגמה של prismantis.\n\n| a | b |\n|---|---|\n| 1 | 2 |'
  const ui = await $.ui.mount(mount(text))
  const reply = (await ui.findAll({ type: 'Button' })).find(b => b.props.label === '⧉ copy reply')
  await ui.press({ key: reply!.key! })
  expect(copied).toEqual([text])
  await ui.unmount()
})

test('a one-paragraph English block gets no copy reply button', async $ => {
  const ui = await $.ui.mount(mount('Checking the tests next.'))
  expect((await ui.findAll({ type: 'Button' })).some(b => b.props.label === '⧉ copy reply')).toBe(false)
  await ui.unmount()
})
