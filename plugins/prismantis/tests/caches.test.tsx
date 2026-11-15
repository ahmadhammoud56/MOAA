import { expect, test } from 'claude-code/testing'

import { remember } from '../hooks/render'

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

test('a streaming reply keeps a bounded number of characters cached, not its last 200 prefixes', async () => {
  const cache = new Map<string, number>()
  const reply = 'word '.repeat(20000)
  for (let end = 100; end <= reply.length; end += 100) remember(cache, reply.slice(0, end), () => end)
  expect([...cache.keys()].reduce((sum, key) => sum + key.length, 0)).toBeLessThanOrEqual(1000000)
  expect(cache.get(reply)).toBe(reply.length)
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

test('a cache miss in a full cache reads a few keys, not all 2000', async () => {
  let reads = 0
  class Counted extends Map<string, number> {
    override *keys(): MapIterator<string> {
      for (const key of super.keys()) {
        reads++
        yield key
      }
    }
  }
  const cache = new Counted()
  for (let i = 0; i < 2500; i++) remember(cache, `paragraph ${i}`, () => i, 2000)
  reads = 0
  remember(cache, 'one more paragraph', () => 0, 2000)
  expect(reads).toBeLessThan(10)
  expect(cache.size).toBe(2000)
})
