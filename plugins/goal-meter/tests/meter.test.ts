import { expect, test } from 'claude-code/testing'

import { countAcceptance, countVerified } from '../hooks/register'

const BRIEF = `**Task:** x

**Acceptance:**
1. doctor passes
2. versions bumped
3. tests pass

**Constraints:** none
`

const CHECKS = `| # | Check | Auditor | After fix |
|---|---|---|---|
| 1 | doctor | unresolved | verified, re-checked |
| 2 | versions | incorrect | verified |
| 3 | tests | verified | - |
| 4 | extra | incorrect | still open |
`

test('acceptance items are counted from the brief', async () => {
  expect(countAcceptance(BRIEF)).toBe(3)
  expect(countAcceptance('no acceptance here')).toBe(0)
})

test('a check counts once its last verdict says verified', async () => {
  expect(countVerified(CHECKS)).toBe(3)
})
