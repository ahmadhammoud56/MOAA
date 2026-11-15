import { expect, test } from 'claude-code/testing'

const PANE = { plugin: 'strata-meter', component: 'Pane', requestId: 'strata-meter',
  props: { title: 'Meters', isFocused: false, bodyColumns: 40, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} } } as const

const READING = { pct: 58, threshold: 85, handoffOn: true, canaryHits: 24, canaryMisses: 1, pending: 37, atoms: 290,
  pausedMin: 12, fallback: 'opencode,local', vault: '/v', vaultOk: true, today: 5,
  cache: { leftMs: 52 * 60_000 + 10_000, ttlMs: 3_600_000, tokens: 412_000, rewarm: 2.58, keepWarm: false },
  goal: { text: 'all checks pass', turns: 3, limit: 0, done: 11, total: 11, label: 'checks verified' }, chats: 2 }

const BAND = { plugin: 'strata-meter', component: 'AbovePrompt',
  props: { hasSurvey: false, isCollapsed: false, isWorking: false, maxRows: 10, bodyColumns: 100, scroll: { offset: 0, bodyRows: 10 }, view: {} } } as const

test('the band shows context, canary and open chats in one row on every surface', async ($, on) => {
  on('state.get', () => ({ value: { value: READING, version: 1 } }))
  on('env.get', () => ({ value: undefined }))
  on('ui.render', ($: any, e: any) => { // the bands beneath (Cache Keeper, Goal Meter): one marker row
    const { Text } = $.ui.resolve(e)
    return <Text>band below</Text>
  })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface } as any)
    expect(await ui.find({ type: 'Text', text: /context 58%\/85% · canary 24✓ 1✗ · 37 to extract · Haiku paused 12m · 2 chats open/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /band below/ })).toBeDefined() // the other mods' bands still show
    await ui.unmount()
  }
})

test('the Meters panel shows every meter, as SVG on a desktop and text in a terminal', async ($, on) => {
  on('state.get', () => ({ value: { value: READING, version: 1 } }))
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect(await ui.find({ type: 'Text', text: /58% \/ 85%/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /52:10 left/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /11\/11/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /37 to extract/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /paused 12m/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /5 chats today/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /2 open/ })).toBeDefined()
    if (surface === 'desktop') expect((await ui.find({ type: 'Svg' }) as any)?.props?.alt).toBe('Context 68%')
    await ui.unmount()
  }
})
