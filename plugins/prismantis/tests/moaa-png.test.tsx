import { expect, test } from 'claude-code/testing'

import { clipboardEnv, startSession } from './clipboard-env'

const mount = {
  plugin: 'prismantis',
  component: 'AssistantMessage' as const,
  props: { text: '| a | b |\n|---|---|\n| 1 | 2 |', isFirstOfReply: true },
  viewport: { columns: 120, rows: 40 },
  surface: 'terminal' as const,
}

for (const [env, shown] of [[{}, false], [{ PRISMANTIS_PNG_BUTTON: '1' }, true]] as const) {
  test(`a table's ▣ png button is ${shown ? 'shown with' : 'hidden without'} PRISMANTIS_PNG_BUTTON`, async ($, on) => {
    clipboardEnv(on, 'other', env)
    await startSession($, on)
    const ui = await $.ui.mount(mount)
    const labels = (await ui.findAll({ type: 'Button' })).map(b => b.props.label)
    expect(labels.includes('⧉ art')).toBe(true)
    expect(labels.includes('▣ png')).toBe(shown)
    await ui.unmount()
  })
}
