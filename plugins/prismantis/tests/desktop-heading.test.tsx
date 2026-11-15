import { expect, test } from 'claude-code/testing'

import { width } from '../hooks/layout'
import { PRESETS } from '../hooks/presets'

const reply = (text: string, surface: 'terminal' | 'desktop') => ({
  plugin: 'prismantis',
  surface,
  component: 'AssistantMessage' as const,
  props: { text, isFirstOfReply: true },
  viewport: { columns: 153, rows: 54 },
})

for (const surface of ['terminal', 'desktop'] as const) {
  test(`a level 2 banner heading on ${surface} draws its rule as long as the heading`, async $ => {
    const ui = await $.ui.mount(reply('## Heading level two', surface))
    const rule = (await ui.findAll({ type: 'Text' })).find(t => /^━+$/.test(t.text))
    if (surface === 'terminal') expect(rule?.text).toBe('━'.repeat(width('Heading level two')))
    else {
      expect(rule).toBeUndefined()
      const lines = (await ui.findAll({ type: 'Box' })).filter(b => b.props.width === 0 && b.props.flexGrow === 1 && b.props.height === 0.12)
      expect(lines.map(b => b.props.backgroundColor)).toEqual([PRESETS['catppuccin-mocha'].heading])
    }
    await ui.unmount()
  })

  test(`a thematic break on ${surface} draws one rule up to 80 columns wide`, async $ => {
    const ui = await $.ui.mount(reply('Above\n\n---\n\nBelow', surface))
    const text = (await ui.findAll({ type: 'Text' })).find(t => /^─+$/.test(t.text))
    if (surface === 'terminal') expect(text?.text).toBe('─'.repeat(80))
    else {
      expect(text).toBeUndefined()
      const lines = (await ui.findAll({ type: 'Box' })).filter(b => b.props.height === 0.06 && b.props.backgroundColor !== undefined)
      expect(lines.map(b => [b.props.width, b.props.flexShrink, b.props.minWidth, b.props.backgroundColor])).toEqual([[80, 1, 0, PRESETS['catppuccin-mocha'].rule]])
    }
    await ui.unmount()
  })
}

test('a theme without heading and rule colors draws desktop lines in gray', { options: { theme: 'mono' } }, async $ => {
  const ui = await $.ui.mount(reply('## Heading\n\n---', 'desktop'))
  const lines = (await ui.findAll({ type: 'Box' })).filter(b => b.props.height === 0.12 || b.props.height === 0.06)
  expect(lines.length).toBe(2)
  expect(lines.every(b => b.props.backgroundColor === 'gray')).toBe(true)
  await ui.unmount()
})
