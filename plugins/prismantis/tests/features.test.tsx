import type { On } from 'claude-code'
import { expect, mock, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'

import { parse } from '../hooks/markdown'
import { PRESETS } from '../hooks/presets'
import { formatDuration, groupSummary } from '../hooks/render'

const t = PRESETS['catppuccin-mocha']
const engine = (on: On) =>
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })

const call = (tool: string, input: unknown, id: string) => ({ tool_use_id: id, tool, input, isRunning: false, isErrored: false, isInterrupted: false })

test('collapsed tool groups draw one summary line', { options: { toolStyle: 'classic' } }, async $ => {
  const ui = await $.ui.mount({
    plugin: 'prismantis',
    surface: 'terminal',
    component: 'ToolGroup',
    props: { calls: [call('Bash', { command: 'ls' }, 'a'), call('Bash', { command: 'pwd' }, 'b'), call('Read', { file_path: '/tmp/x' }, 'c')], isActive: false, isExpanded: false },
  })
  expect((await ui.find({ type: 'Text', text: /^Ran 2 commands, read 1 file$/ }))?.props.bold).toBe(true)
  await ui.unmount()
})

const expand = async ($: Parameters<TestBody>[0], id: string) => {
  const group = await $.ui.mount({
    plugin: 'prismantis',
    surface: 'terminal',
    component: 'ToolGroup',
    props: { calls: [call('Bash', { command: 'ls' }, id)], isActive: false, isExpanded: true },
  })
  await group.unmount()
}

test('expanded non-shell rows go back to the engine so their output shows', async ($, on) => {
  engine(on)
  await expand($, 'exp-1')
  const row = await $.ui.mount({
    plugin: 'prismantis',
    surface: 'terminal',
    component: 'ToolUse',
    props: { ...call('Read', { file_path: '/tmp/x' }, 'exp-1'), output: { stdout: 'file' } },
  })
  expect(await row.find({ type: 'Text', text: /^engine$/ })).toBeDefined()
  await row.unmount()
})

test('expanded shell rows color the command and show stdout and stderr', async ($, on) => {
  engine(on)
  await expand($, 'exp-2')
  const row = await $.ui.mount({
    plugin: 'prismantis',
    surface: 'terminal',
    component: 'ToolUse',
    props: { ...call('Bash', { command: 'gh run list --repo "a/b"' }, 'exp-2'), output: { stdout: 'in_progress\n', stderr: 'warn' } },
  })
  expect(await row.find({ type: 'Text', text: /^Bash\($/ })).toBeDefined()
  expect(await row.find({ type: 'Text', text: /^gh$/ })).toBeDefined()
  expect(await row.find({ type: 'Text', text: /^--repo$/ })).toBeDefined()
  expect(await row.find({ type: 'Text', text: /^"a\/b"$/ })).toBeDefined()
  expect(await row.find({ type: 'Text', text: /^in_progress$/ })).toBeDefined()
  expect(await row.find({ type: 'Text', text: /^warn$/ })).toBeDefined()
  await row.unmount()
})

test('expanded shell output is capped so a huge result cannot hit the node limit', async ($, on) => {
  engine(on)
  await expand($, 'exp-3')
  const stdout = Array.from({ length: 5000 }, (_, i) => `line ${i}`).join('\n')
  const row = await $.ui.mount({
    plugin: 'prismantis',
    surface: 'terminal',
    component: 'ToolUse',
    props: { ...call('Bash', { command: 'seq 5000' }, 'exp-3'), output: { stdout } },
  })
  expect(await row.find({ type: 'Text', text: /^… \+4880 lines$/ })).toBeDefined()
  await row.unmount()
})

test('an expanded shell row with no output says so', async ($, on) => {
  engine(on)
  await expand($, 'exp-4')
  const row = await $.ui.mount({
    plugin: 'prismantis',
    surface: 'terminal',
    component: 'ToolUse',
    props: { ...call('Bash', { command: 'true' }, 'exp-4'), output: { stdout: '', stderr: '' } },
  })
  expect(await row.find({ type: 'Text', text: /^\(No output\)$/ })).toBeDefined()
  await row.unmount()
})

test('standalone tool rows keep the prismantis look', async $ => {
  const ui = await $.ui.mount({
    plugin: 'prismantis',
    surface: 'terminal',
    component: 'ToolUse',
    props: { ...call('Bash', { command: 'ls' }, 'solo-1'), output: { stdout: 'file' } },
  })
  expect(await ui.find({ type: 'Text', text: /^Ran$/ })).toBeDefined()
  await ui.unmount()
})

test('group summaries count by kind', async () => {
  expect(groupSummary([{ tool: 'Grep' }, { tool: 'Grep' }, { tool: 'Edit' }])).toBe('Searched 2 patterns, edited 1 file')
  expect(groupSummary([{ tool: 'WebSearch' }])).toBe('Fetched 1 page')
})

test('turn footer formats durations', async () => {
  expect(formatDuration(3000)).toBe('3s')
  expect(formatDuration(380000)).toBe('6m 20s')
  expect(formatDuration(3720000)).toBe('1h 2m')
})

test('turn footer keeps the word and colors the duration', async $ => {
  const ui = await $.ui.mount({ plugin: 'prismantis', surface: 'terminal', component: 'TurnDuration', props: { word: 'Baked', durationMs: 380000 } })
  expect((await ui.find({ type: 'Text', text: /^6m 20s$/ }))?.props.color).toBe(t.number)
  await ui.unmount()
})

test('slash command output renders as markdown, errors stay native', async ($, on) => {
  engine(on)
  const ok = await $.ui.mount({ plugin: 'prismantis', surface: 'terminal', component: 'CommandOutput', props: { command: 'cost', args: '', text: '| a | b |\n|---|---|\n| 1 | 2 |', isErrored: false } })
  expect((await ok.find({ type: 'Text', text: /^a$/ }))?.props.color).toBe(t.tableHeader)
  await ok.unmount()
  const bad = await $.ui.mount({ plugin: 'prismantis', surface: 'terminal', component: 'CommandOutput', props: { command: 'cost', args: '', text: 'boom', isErrored: true } })
  expect(await bad.find({ type: 'Text', text: /^engine$/ })).toBeDefined()
  await bad.unmount()
})

test('your prompts carry the render hint as model-only context', async ($, on) => {
  const seen: (readonly string[] | undefined)[] = []
  mock.env(on, {})
  on('prompt.submit', (_, e) => {
    seen.push(e.context)
    return { text: e.text, context: e.context }
  })
  await $.prompt.submit({ text: 'show me deploys per day', wait: false, origin: { kind: 'composer' } })
  expect(seen[0]?.some(c => c.includes('prismantis'))).toBe(true)
  expect(seen[0]?.some(c => c.includes('fenced block') && c.includes('copy button'))).toBe(true)
})

test('no render hint when diagramHints is off', { options: { diagramHints: false } }, async ($, on) => {
  const seen: (readonly string[] | undefined)[] = []
  mock.env(on, {})
  on('prompt.submit', (_, e) => {
    seen.push(e.context)
    return { text: e.text, context: e.context }
  })
  await $.prompt.submit({ text: 'hi', wait: false, origin: { kind: 'composer' } })
  expect((seen[0] ?? []).some(c => c.includes('prismantis'))).toBe(false)
})

test('a continuation line joins the list item it is indented under', async () => {
  const [list] = parse('- parent\n  - child\n  more about parent', { numbers: false, paths: false })
  if (list?.kind !== 'list') throw new Error('not a list')
  expect(list.items.map(i => i.inline.map(n => ('text' in n ? n.text : '')).join(''))).toEqual(['parent more about parent', 'child'])
})

test('double-backtick code keeps single backticks inside', async () => {
  const [p] = parse('use ``a `b` c`` here', { numbers: false, paths: false })
  if (p?.kind !== 'paragraph') throw new Error('not a paragraph')
  expect(p.inline.filter(n => n.kind === 'code').map(n => ('text' in n ? n.text : ''))).toEqual(['a `b` c'])
})

test('wide characters take two columns in tables', async $ => {
  const ui = await $.ui.mount({
    plugin: 'prismantis',
    surface: 'terminal',
    component: 'AssistantMessage',
    props: { text: '| 名前 | n |\n|---|---|\n| 寿司 | 1 |', isFirstOfReply: true },
    viewport: { columns: 120, rows: 40 },
  })
  const cells = (await ui.findAll({ type: 'Box' })).filter(b => typeof b.props.width === 'number' && b.props.flexShrink === 0).slice(1)
  expect(cells[0]?.props.width).toBe(4)
  await ui.unmount()
})

const FULL = [
  '# prismantis',
  '',
  'Status: 3 regions in 6m 20s, p95 82ms. Notes in ~/notes/today.md and https://example.com/docs',
  '',
  '| Name | Size |',
  '| :--- | ---: |',
  '| alpha | 5cm |',
  '',
  '1. first',
  '   - nested',
  '',
  '```mermaid',
  'graph LR',
  '  A --> B',
  '```',
  '',
  '```mermaid',
  'sequenceDiagram',
  '  A->>B: hi',
  '```',
  '',
  '```mermaid',
  'xychart-beta',
  '  x-axis [a, b]',
  '  bar [1, 2]',
  '```',
  '',
  '```ts',
  'const x = "y"',
  '```',
  '',
  '```bash',
  'ls -la',
  '```',
  '',
  '> a quote',
].join('\n')

test('a full reply draws every element itself, with the right copy buttons', async ($, on) => {
  engine(on)
  const ui = await $.ui.mount({
    plugin: 'prismantis',
    surface: 'terminal',
    component: 'AssistantMessage',
    props: { text: FULL, isFirstOfReply: true },
    viewport: { columns: 200, rows: 60 },
  })
  expect(await ui.find({ type: 'Text', text: /^engine$/ })).toBeUndefined()
  expect((await ui.find({ type: 'Text', text: /^Name$/ }))?.props.color).toBe(t.tableHeader)
  const labels = (await ui.findAll({ type: 'Button' })).map(b => b.props.label)
  expect(labels.filter(l => l === '⧉ copy').length).toBe(5)
  expect(labels.filter(l => l === '⧉ source').length).toBe(3)
  expect(labels.filter(l => l === '⧉ art').length).toBe(4)
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.flexWrap === 'wrap')).toBe(true)
  await ui.unmount()
})

test('headless runs get no render hint', async ($, on) => {
  const seen: (readonly string[] | undefined)[] = []
  mock.env(on, {})
  on('prompt.submit', (_, e) => {
    seen.push(e.context)
    return { text: e.text, context: e.context }
  })
  await $.prompt.submit({ text: 'hi', wait: false, origin: { kind: 'sdk' } })
  expect((seen[0] ?? []).some(c => c.includes('prismantis'))).toBe(false)
})

test('/prismantis theme <name> switches the theme through config', async ($, on) => {
  const writes: { key: string; value: unknown }[] = []
  on('config.set', (_, e) => {
    writes.push({ key: e.key, value: e.value })
    return { value: e.value }
  })
  const result = await $.command.run({ command: 'prismantis', args: 'theme nord', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 } })
  expect(writes).toEqual([{ key: 'prismantis.theme', value: 'nord' }])
  expect(result.text).toBe('Theme set to nord.')
})

test('/prismantis rejects unknown themes and lists the real ones', async ($, on) => {
  const writes: unknown[] = []
  on('config.set', (_, e) => {
    writes.push(e.value)
    return { value: e.value }
  })
  const bad = await $.command.run({ command: 'prismantis', args: 'theme neon', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 } })
  expect(writes).toEqual([])
  expect(bad.text?.startsWith('Unknown theme "neon".')).toBe(true)
  const list = await $.command.run({ command: 'prismantis', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 } })
  expect(list.text?.includes('dracula')).toBe(true)
})

test('task list items parse as checked or open, nested ones too', async () => {
  const [list] = parse('- [ ] write tests\n- [x] ship it\n  - [X] nested done\n- plain', { numbers: false, paths: false })
  if (list?.kind !== 'list') throw new Error('not a list')
  expect(list.items.map(i => i.task)).toEqual([false, true, true, undefined])
  expect(list.items[0]?.inline).toEqual([{ kind: 'text', text: 'write tests' }])
})

test('task lists draw brackets and check marks, done items dimmed and struck through', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'prismantis', component: 'AssistantMessage', props: { text: '- [ ] todo\n- [x] done', isFirstOfReply: true }, viewport: { columns: 80, rows: 20 }, surface })
    expect((await ui.find({ type: 'Text', text: /^\[ \] $/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].bullet)
    expect(await ui.find({ type: 'Text', text: /^\[✓\] $/ })).toBeDefined()
    expect((await ui.find({ type: 'Text', text: /^done$/ }))?.props).toMatchObject({ dimColor: true, strikethrough: true })
    expect((await ui.find({ type: 'Text', text: /^todo$/ }))?.props.dimColor).toBeFalsy()
    await ui.unmount()
  }
})

const tasks = (surface: 'terminal' | 'desktop') => ({ plugin: 'prismantis', component: 'AssistantMessage' as const, props: { text: '- [ ] todo\n- [x] done', isFirstOfReply: true }, viewport: { columns: 80, rows: 20 }, surface })

test('taskStyle progress draws ticks under a done-count bar', { options: { taskStyle: 'progress' } }, async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount(tasks(surface))
    expect(await ui.find({ type: 'Text', text: /^ 1\/2 done$/ })).toBeDefined()
    expect((await ui.find({ type: 'Text', text: /^━{10}$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].accent)
    expect(await ui.find({ type: 'Text', text: /^○ $/ })).toBeDefined()
    expect((await ui.find({ type: 'Text', text: /^✓ $/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].accent)
    expect((await ui.find({ type: 'Text', text: /^done$/ }))?.props).toMatchObject({ dimColor: true, strikethrough: false })
    await ui.unmount()
  }
})

test('taskStyle box draws a box and a tick', { options: { taskStyle: 'box' } }, async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount(tasks(surface))
    expect(await ui.find({ type: 'Text', text: /^□ $/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^✓ $/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^ 1\/2 done$/ })).toBeUndefined()
    expect((await ui.find({ type: 'Text', text: /^done$/ }))?.props.strikethrough).toBe(true)
    await ui.unmount()
  }
})

test('markdown links and bare URLs draw as clickable links', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'prismantis', component: 'AssistantMessage', props: { text: 'See [the docs](https://example.com/docs) or https://example.com/raw for more.', isFirstOfReply: true }, viewport: { columns: 100, rows: 20 }, surface })
    const links = await ui.findAll({ type: 'Link' })
    expect(links.map(l => l.props.href)).toEqual(['https://example.com/docs', 'https://example.com/raw'])
    expect((await ui.find({ type: 'Text', text: /^the docs$/ }))?.props.underline).toBe(true)
    expect(await ui.find({ type: 'Text', text: /\(https:\/\/example\.com\/docs\)/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /^https:\/\/example\.com\/raw$/ })).toBeUndefined()
    await ui.unmount()
  }
})

const run = (args: string) => ({ command: 'prismantis', args, origin: { kind: 'composer' as const }, presentation: { isFullscreen: false, columns: 120 } })

const transcript = (on: On, messages: { role: 'user' | 'assistant'; text: string }[]) => {
  const copied: string[] = []
  on('session.messages', () => ({ value: messages.map(m => ({ ...m, toolUses: [] })) }))
  on('ui.copy', (_, e) => {
    copied.push(e.text)
    return { value: { isCopied: true as const } }
  })
  return copied
}

test('/prismantis copy copies the last reply without a mouse', async ($, on) => {
  const copied = transcript(on, [{ role: 'user', text: 'hi' }, { role: 'assistant', text: 'old' }, { role: 'user', text: 'again' }, { role: 'assistant', text: 'שלום, the newest reply' }])
  const result = await $.command.run(run('copy'))
  expect(copied).toEqual(['שלום, the newest reply'])
  expect(result.text).toBe('Copied the last reply.')
})

test('/prismantis copy code copies the last code block of the last reply', async ($, on) => {
  const copied = transcript(on, [{ role: 'assistant', text: 'Run:\n\n```bash\nls\n```\n\nthen:\n\n```bash\nnpm test\n```' }])
  const result = await $.command.run(run('copy code'))
  expect(copied).toEqual(['npm test'])
  expect(result.text).toBe('Copied the last code block.')
})

test('/prismantis copy says so when there is nothing to copy', async ($, on) => {
  const copied = transcript(on, [{ role: 'assistant', text: 'no code here' }])
  expect((await $.command.run(run('copy code'))).text).toBe('The last reply has no code block.')
  expect(copied).toEqual([])
})

const prompt = (text: string, kind: 'composer' | 'task-notification' = 'composer', surface: 'terminal' | 'desktop' = 'terminal') =>
  ({ plugin: 'prismantis', component: 'UserMessage' as const, props: { text, origin: { kind } as never, isExpanded: true }, viewport: { columns: 80, rows: 10 }, surface })

test('your prompts draw in a rounded accent bubble by default', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount(prompt('how many frog raids?', 'composer', surface))
    const bubble = (await ui.findAll({ type: 'Box' })).find(b => b.props.borderStyle === 'round')
    expect(bubble?.props.borderColor).toBe(PRESETS['catppuccin-mocha'].accent)
    expect((await ui.find({ type: 'Text', text: /^how many frog raids\?$/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].heading)
    await ui.unmount()
  }
})

test('promptStyle bar draws an accent bar', { options: { promptStyle: 'bar' } }, async $ => {
  const ui = await $.ui.mount(prompt('hi'))
  expect((await ui.find({ type: 'Text', text: /^▌ $/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].accent)
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.borderStyle)).toBe(false)
  await ui.unmount()
})

test('promptStyle chevron draws a bold accent prompt', { options: { promptStyle: 'chevron' } }, async $ => {
  const ui = await $.ui.mount(prompt('hi'))
  expect(await ui.find({ type: 'Text', text: /^› $/ })).toBeDefined()
  expect((await ui.find({ type: 'Text', text: /^hi$/ }))?.props).toMatchObject({ bold: true, color: PRESETS['catppuccin-mocha'].accent })
  await ui.unmount()
})

test('promptStyle off and task notifications keep the engine look', { options: { promptStyle: 'off' } }, async ($, on) => {
  engine(on)
  const ui = await $.ui.mount(prompt('hi'))
  expect(await ui.find({ type: 'Text', text: /^engine$/ })).toBeDefined()
  await ui.unmount()
})

test('task notifications are not drawn as your prompt', async ($, on) => {
  engine(on)
  const ui = await $.ui.mount(prompt('task done', 'task-notification'))
  expect(await ui.find({ type: 'Text', text: /^engine$/ })).toBeDefined()
  await ui.unmount()
})

test('a Hebrew prompt bubble sits on the right', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(prompt('כמה פשיטות היו השבוע?'))
  expect((await ui.findAll({ type: 'Box' })).find(b => b.props.borderStyle === 'round')?.props.alignSelf).toBe('flex-end')
  await ui.unmount()
})

test('an unstamped prompt is yours, a teammate message is not', async ($, on) => {
  engine(on)
  const mine = await $.ui.mount(prompt('typed on the command line', 'unclassified' as never))
  expect((await mine.findAll({ type: 'Box' })).some(b => b.props.borderStyle === 'round')).toBe(true)
  await mine.unmount()
  const peer = await $.ui.mount({ ...prompt('from a teammate', 'unclassified' as never), props: { text: 'from a teammate', origin: { kind: 'unclassified' } as never, isExpanded: true, from: { name: 'bob' } as never } })
  expect(await peer.find({ type: 'Text', text: /^engine$/ })).toBeDefined()
  await peer.unmount()
})

const readRow = { plugin: 'prismantis', component: 'ToolUse' as const, props: call('Read', { file_path: '/tmp/x' }, 'ts-1'), viewport: { columns: 100, rows: 10 }, surface: 'terminal' as const }

test('chat puts tool rows on the right, dimmed, by default', async $ => {
  const ui = await $.ui.mount(readRow)
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.justifyContent === 'flex-end')).toBe(true)
  expect(await ui.find({ type: 'Text', text: /⎿/ })).toBeUndefined()
  expect((await ui.findAll({ type: 'Text' })).find(t => t.props.wrap === 'truncate-end')?.props.dimColor).toBe(true)
  await ui.unmount()
})

test('toolStyle tree-dim tucks tool rows under the sentence', { options: { toolStyle: 'tree-dim' } }, async $ => {
  const ui = await $.ui.mount(readRow)
  expect((await ui.find({ type: 'Text', text: /^ {2}⎿ $/ }))?.props.color).toBe(PRESETS['catppuccin-mocha'].number)
  expect((await ui.findAll({ type: 'Text' })).find(t => t.props.wrap === 'truncate-end')?.props.dimColor).toBe(true)
  await ui.unmount()
})

test('toolStyle classic is the original look', { options: { toolStyle: 'classic' } }, async $ => {
  const ui = await $.ui.mount(readRow)
  expect(await ui.find({ type: 'Text', text: /⎿/ })).toBeUndefined()
  expect((await ui.findAll({ type: 'Text' })).find(t => t.props.wrap === 'truncate-end')?.props.dimColor).toBe(false)
  await ui.unmount()
})

test('toolStyle tree-bold draws one-line narration in bold', { options: { toolStyle: 'tree-bold' } }, async $ => {
  const one = await $.ui.mount({ plugin: 'prismantis', component: 'AssistantMessage', props: { text: 'Checking the tests next.', isFirstOfReply: true }, viewport: { columns: 80, rows: 10 }, surface: 'terminal' })
  expect((await one.find({ type: 'Text', text: /^Checking the tests next\.$/ }))?.props.bold).toBe(true)
  await one.unmount()
  const long = await $.ui.mount({ plugin: 'prismantis', component: 'AssistantMessage', props: { text: 'First.\n\nSecond.', isFirstOfReply: true }, viewport: { columns: 80, rows: 10 }, surface: 'terminal' })
  expect((await long.find({ type: 'Text', text: /^First\.$/ }))?.props.bold).toBeFalsy()
  await long.unmount()
})
