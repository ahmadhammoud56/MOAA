import { expect, mock, test } from 'claude-code/testing'

import { remember } from '../hooks/render'

const mount = (text: string, isFullscreen = false) => ({
  plugin: 'prismantis',
  component: 'AssistantMessage' as const,
  props: { text, isFirstOfReply: true },
  viewport: { columns: 120, rows: 40, isFullscreen },
  surface: 'terminal' as const,
})

const drawn = (node: unknown): string =>
  typeof node === 'string' ? node : ((node as { children?: unknown[] }).children ?? []).map(drawn).join('')

test('a cached entry read again outlives newer ones', async () => {
  const cache = new Map<string, string>()
  remember(cache, 'old', () => 'old', 3)
  for (let i = 0; i < 112; i++) {
    remember(cache, `stream ${i}`, () => 'part', 3)
    remember(cache, 'old', () => 'parsed again', 3)
  }
  expect(cache.get('old')).toBe('old')
  expect(cache.size).toBe(3)
})

test('highlighted code keeps each right-to-left shape apart under one theme', { options: { rtl: 'apple-terminal' } }, async ($, on) => {
  mock.env(on, {})
  on('session.start', () => ({ cwd: '/tmp' }))
  await $.session.start({ cwd: '/tmp', surface: 'terminal', isInteractive: true })
  const text = '```js\nconst port = 8080 // שלום kubectl עולם\n```'
  const line = async (isFullscreen: boolean) => {
    const ui = await $.ui.mount(mount(text, isFullscreen))
    const row = (await ui.findAll({ type: 'Text' })).map(drawn).find(t => t.startsWith('const port'))
    await ui.unmount()
    return row
  }
  const windowed = await line(false)
  const fullscreen = await line(true)
  expect(fullscreen).not.toBe(windowed)
  expect(await line(false)).toBe(windowed)
})

test('the terminal is looked up once, not on every prompt', async ($, on) => {
  const reads: string[] = []
  on('env.get', (_, e) => {
    reads.push(e.name)
    return { value: e.name === 'TERM_PROGRAM' ? 'WarpTerminal' : undefined }
  })
  on('prompt.submit', (_, e) => ({ text: e.text, context: e.context }))
  for (const text of ['one', 'two', 'three']) await $.prompt.submit({ text, wait: false, origin: { kind: 'composer' } })
  expect(reads.filter(name => name === 'TERM_PROGRAM').length).toBe(1)
})

const call = (id: string) => ({ tool_use_id: id, tool: 'Read', input: { file_path: '/tmp/x' }, isRunning: false, isErrored: false, isInterrupted: false })

test('only the 500 most recently expanded tool calls stay expanded', async ($, on) => {
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  const ids = Array.from({ length: 501 }, (_, i) => `bounded-${i}`)
  const group = await $.ui.mount({ plugin: 'prismantis', surface: 'terminal', component: 'ToolGroup', props: { calls: ids.map(call), isActive: false, isExpanded: true } })
  await group.unmount()
  const isEngine = async (id: string) => {
    const ui = await $.ui.mount({ plugin: 'prismantis', surface: 'terminal', component: 'ToolUse', props: { ...call(id), output: { stdout: 'file' } } })
    const found = (await ui.find({ type: 'Text', text: /^engine$/ })) !== undefined
    await ui.unmount()
    return found
  }
  expect(await isEngine('bounded-500')).toBe(true)
  expect(await isEngine('bounded-0')).toBe(false)
})
