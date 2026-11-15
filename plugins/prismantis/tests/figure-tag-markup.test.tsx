import { expect, test } from 'claude-code/testing'

import { figureRuns, figureText } from '../hooks/figure'

test('a role written as a closing tag colors its text, like the colon form', async () => {
  const colon = figureRuns('{ok:has} level + pos')
  const tag = figureRuns('{ok}has{/ok} level + pos')
  expect(tag).toEqual(colon)
  expect(tag[0]).toEqual({ text: 'has', role: 'ok' })
})

test('closing-tag markup takes no columns', async () => {
  expect(figureText('{strong}who has what{/strong}')).toBe('who has what')
  expect(figureText('  {ok}has{/ok} level + pos      {warn}no parts yet{/warn}')).toBe('  has level + pos      no parts yet')
})

test('both forms may stand on one line', async () => {
  expect(figureText('{dim}left{/dim} and {accent:right}')).toBe('left and right')
})

test('a tag closed by another role is left as written', async () => {
  expect(figureText('{ok}mismatch{/warn}')).toBe('{ok}mismatch{/warn}')
})

test('an unclosed role is left as written', async () => {
  expect(figureText('{strong}unclosed')).toBe('{strong}unclosed')
})
