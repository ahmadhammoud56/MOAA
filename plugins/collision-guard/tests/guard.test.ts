import { expect, test } from 'claude-code/testing'

import { holder, ignored, norm, prune } from '../hooks/register'

const NOW = 10_000_000

test('paths are compared absolute, normalized and case-folded on Windows', async () => {
  expect(norm('src\\a.ts', 'C:\\Repo')).toBe('c:/repo/src/a.ts')
  expect(norm('C:\\Repo\\SRC\\a.ts', '/elsewhere')).toBe('c:/repo/src/a.ts')
  expect(norm('./b/../a.ts', '/home/u/repo')).toBe('/home/u/repo/a.ts')
})

test('a recent claim of another live chat holds the file; stale or own claims do not', async () => {
  const claims = {
    sessions: { other: { at: NOW - 30_000, cwd: '/r', branch: 'main' }, gone: { at: NOW - 600_000, cwd: '/r', branch: '' } },
    files: { '/r/a.ts': { sid: 'other', at: NOW - 120_000 }, '/r/b.ts': { sid: 'gone', at: NOW - 60_000 },
             '/r/c.ts': { sid: 'other', at: NOW - 900_000 }, '/r/d.ts': { sid: 'me', at: NOW } },
  }
  expect(holder(claims, '/r/a.ts', 'me', NOW)?.sid).toBe('other')
  expect(holder(claims, '/r/b.ts', 'me', NOW)).toBeUndefined() // that chat is gone
  expect(holder(claims, '/r/c.ts', 'me', NOW)).toBeUndefined() // the claim expired
  expect(holder(claims, '/r/d.ts', 'me', NOW)).toBeUndefined() // my own
})

test('old entries are pruned', async () => {
  const c = prune({ sessions: { s: { at: 0, cwd: '/', branch: '' } }, files: { f: { sid: 's', at: 0 } } }, NOW)
  expect(Object.keys(c.sessions).length).toBe(0)
  expect(Object.keys(c.files).length).toBe(0)
})

test('an edit of a file another live chat holds is denied, with a way out', async ($, on) => {
  const claims = {
    sessions: { other: { at: NOW, cwd: '/r', branch: 'main' } },
    files: { '/r/a.ts': { sid: 'other', at: NOW - 60_000 } },
  }
  on('session.id', () => ({ value: 'me' }))
  on('clock.now', () => ({ value: NOW }))
  on('env.get', () => ({ value: undefined }))
  on('fs.read', () => ({ value: JSON.stringify(claims) }))
  on('fs.write', () => ({ value: undefined }))
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: {} }))
  await $.session.start({ cwd: '/r', surface: 'terminal', isInteractive: true })
  const r = await ($.tool.call as any)({ tool: 'Edit', file_path: '/r/a.ts', old_string: 'a', new_string: 'b' })
  expect(String(r.deny)).toContain('another live Claude chat')
  expect(String(r.deny)).toContain('worktree')
  const ok = await ($.tool.call as any)({ tool: 'Edit', file_path: '/r/free.ts', old_string: 'a', new_string: 'b' })
  expect(ok.deny).toBeUndefined()
})

test('ignore patterns: a bare name matches the file name, a pattern with a slash the whole path', async () => {
  const pats = ['quadro.md', '*/docs/handoffs/*', '*.lock']
  expect(ignored('/r/docs/x/quadro.md', pats)).toBe(true)
  expect(ignored('/r/docs/handoffs/2026-11-08-a.md', pats)).toBe(true)
  expect(ignored('/r/package.lock', pats)).toBe(true)
  expect(ignored('/r/quadro.md.bak', pats)).toBe(false) // a bare name matches the whole file name
  expect(ignored('/r/src/a.ts', pats)).toBe(false)
  expect(ignored('/r/a.ts', [])).toBe(false)
  expect(ignored('c:/repo/quadro.md', ['QUADRO.MD'])).toBe(true) // Windows paths are case-folded, so are the patterns
})

test('a file matching MOAA_COLLISION_GUARD_IGNORE is shared: never denied, never claimed', async ($, on) => {
  const claims = {
    sessions: { other: { at: NOW, cwd: '/r', branch: 'main' } },
    files: { '/r/quadro.md': { sid: 'other', at: NOW - 60_000 }, '/r/a.ts': { sid: 'other', at: NOW - 60_000 } },
  }
  const written: string[] = []
  on('session.id', () => ({ value: 'me' }))
  on('clock.now', () => ({ value: NOW }))
  on('env.get', (_: any, e: any) => ({ value: e.name === 'MOAA_COLLISION_GUARD_IGNORE' ? ' quadro.md , */handoffs/* ' : undefined }))
  on('fs.read', () => ({ value: JSON.stringify(claims) }))
  on('fs.write', (_: any, e: any) => { written.push(JSON.stringify(e)); return { value: undefined } })
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: {} }))
  await $.session.start({ cwd: '/r', surface: 'terminal', isInteractive: true })
  written.length = 0
  const shared = await ($.tool.call as any)({ tool: 'Edit', file_path: '/r/quadro.md', old_string: 'a', new_string: 'b' })
  expect(shared.deny).toBeUndefined()
  const handoff = await ($.tool.call as any)({ tool: 'Write', file_path: '/r/handoffs/h.md', content: 'x' })
  expect(handoff.deny).toBeUndefined()
  expect(written.some(w => w.includes('/r/handoffs/h.md'))).toBe(false) // not claimed for this chat either
  await ($.tool.call as any)({ tool: 'Edit', file_path: '/r/free.ts', old_string: 'a', new_string: 'b' })
  expect(written.some(w => w.includes('/r/free.ts'))).toBe(true) // control: an ordinary edit is claimed, so the check above means something
  const held = await ($.tool.call as any)({ tool: 'Edit', file_path: '/r/a.ts', old_string: 'a', new_string: 'b' })
  expect(String(held.deny)).toContain('another live Claude chat') // everything else is still guarded
})
