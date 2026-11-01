import { expect, test } from 'claude-code/testing'

const NOW = 50_000_000
const BAND = { plugin: 'cache-keeper', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 3, bodyColumns: 100, scroll: { offset: 0, bodyRows: 3 }, view: {} } } as const

const seed = (on: any, lastCallAt: number, percent: number) => {
  const values: Record<string, unknown> = {
    info: { lastCallAt, tokens: 412_000, model: 'claude-opus-5-5' },
    warmth: { on: false, lastPromptAt: lastCallAt, pings: 0, usd: 0 },
    tick: 0,
    isHidden: false,
  }
  on('state.get', (_: unknown, e: any) => ({ value: { value: values[e.key], version: 1 } }))
  on('clock.now', () => ({ value: NOW }))
  on('env.get', () => ({ value: undefined }))
  on('session.usage', () => ({ value: { startedAt: 0, context: { window: 1_000_000, percent }, rateLimits: [] } }))
}

test('a warm cache shows its countdown and a keep-warm button', async ($, on) => {
  seed(on, NOW - 60_000, 20)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect((await ui.find({ type: 'Text', text: /cache warm/ }))?.text).toContain('cache warm')
    expect((await ui.find({ type: 'Text', text: /left/ }))?.text).toContain('59:00 left')
    expect(await ui.find({ key: 'warm' })).toBeDefined()
    await ui.unmount()
  }
})

test('a cold cache with a full context suggests a strata handoff', async ($, on) => {
  seed(on, NOW - 70 * 60_000, 75)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /cache cold/ }))?.text).toContain('cache cold')
  expect((await ui.find({ type: 'Text', text: /handoff/ }))?.text).toContain('strata handoff')
  await ui.unmount()
})

test('a cold cache with room left shows the re-warm cost', async ($, on) => {
  seed(on, NOW - 70 * 60_000, 20)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /re-writes/ }))?.text).toContain('$2.58')
  await ui.unmount()
})
