import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

type Claims = {
  sessions: Record<string, { at: number; cwd: string; branch: string }>
  files: Record<string, { sid: string; at: number }>
}

const CLAIM_MS = 10 * 60_000 // a file edited in the last 10 minutes belongs to that chat
const ALIVE_MS = 3 * 60_000 // a chat whose heartbeat is older than this is gone (crashed or closed)
const PRUNE_MS = 60 * 60_000

export const norm = (path: string, cwd: string) => {
  let p = path.replace(/\\/g, '/')
  if (!/^([a-zA-Z]:)?\//.test(p)) p = `${cwd.replace(/\\/g, '/').replace(/\/$/, '')}/${p}`
  const parts: string[] = []
  for (const s of p.split('/')) {
    if (s === '..') parts.pop()
    else if (s !== '.' && s !== '') parts.push(s)
  }
  const out = (p.startsWith('/') ? '/' : '') + parts.join('/')
  return /^[a-zA-Z]:/.test(out) ? out.toLowerCase() : out // Windows paths compare case-insensitively
}

/** The other live chat holding a recent claim on `file`, or undefined. */
export const holder = (c: Claims, file: string, me: string, now: number) => {
  const claim = c.files[file]
  if (!claim || claim.sid === me || now - claim.at > CLAIM_MS) return undefined
  const s = c.sessions[claim.sid]
  return s && now - s.at <= ALIVE_MS ? { sid: claim.sid, minutes: Math.max(1, Math.round((now - claim.at) / 60_000)), ...s } : undefined
}

export const prune = (c: Claims, now: number): Claims => ({
  sessions: Object.fromEntries(Object.entries(c.sessions).filter(([, s]) => now - s.at < PRUNE_MS)),
  files: Object.fromEntries(Object.entries(c.files).filter(([, f]) => now - f.at < PRUNE_MS)),
})

const store = async ($: any) => {
  const home = String((await $.env.get('USERPROFILE')) || (await $.env.get('HOME')) || '.').replace(/\\/g, '/')
  return `${home}/.claude/moaa-mods/claims.json`
}

const load = async ($: any): Promise<Claims> => {
  try {
    const raw = JSON.parse(String(await $.fs.read(await store($))))
    return { sessions: raw.sessions ?? {}, files: raw.files ?? {} }
  } catch {
    return { sessions: {}, files: {} }
  }
}

// ponytail: read-modify-write without a lock; two chats writing in the same millisecond can drop one claim, which
// only weakens a warning. A lock file is the upgrade if that ever matters.
const save = async ($: any, c: Claims) => $.fs.write(await store($), JSON.stringify(c))

const mode = async ($: any) => {
  const m = String((await $.env.get('MOAA_COLLISION_GUARD')) ?? 'block').toLowerCase()
  return m === 'off' || m === 'warn' ? m : 'block'
}

const branchOf = async ($: any, cwd: string) => {
  try {
    const r = await $.process.run(['git', '-C', cwd, 'branch', '--show-current'])
    return r.exitCode === 0 ? r.stdout.trim() : ''
  } catch {
    return ''
  }
}

/** One spelling per file (short 8.3 names, links and `..` resolved); a file not written yet keeps its own path. */
async function realPath($: any, path: string) {
  try {
    const s = await $.fs.stat(path, { resolve: true })
    return String(s.realPath ?? path)
  } catch {
    return path
  }
}

const PANE = 'collision-guard'
const tick = atom({ plugin: 'collision-guard', key: 'tick' } as const, 0)

let me = ''
let cwd = '.'
const seen: Record<string, string> = {} // other chats' last branch, to notice a switch in a shared checkout

async function beat($: any) {
  const now = await $.clock.now()
  const c = prune(await load($), now)
  c.sessions[me] = { at: now, cwd, branch: await branchOf($, cwd) }
  for (const [sid, s] of Object.entries(c.sessions)) {
    if (sid === me || s.cwd !== cwd || now - s.at > ALIVE_MS) continue
    if (seen[sid] !== undefined && s.branch && seen[sid] !== s.branch) {
      $.ui.toast(`collision-guard: another chat in this folder switched branch ${seen[sid]} -> ${s.branch}`)
    }
    seen[sid] = s.branch
  }
  await save($, c)
  await update($, tick, n => n + 1) // redraw the panel
}

/** The edit guard, shared by the three edit tools. */
async function guard($: any, e: any, next: any) {
    const m = await mode($)
    const target = (e as any).file_path ?? (e as any).notebook_path
    if (m === 'off' || !me || !target) return next(e)
    const file = norm(await realPath($, norm(String(target), cwd)), cwd)
    const now = await $.clock.now()
    const other = holder(await load($), file, me, now)
    if (other) {
      const why = `collision-guard: ${target} was edited ${other.minutes} min ago by another live Claude chat ` +
        `(session ${other.sid.slice(0, 8)}, in ${other.cwd}${other.branch ? `, branch ${other.branch}` : ''}). ` +
        'Coordinate first: let that chat finish, work in a separate worktree (War Room or `allies.py run --write`), ' +
        'or claim the file on the team board (`team.py claim`). Off: MOAA_COLLISION_GUARD=warn or off.'
      if (m === 'block') return { deny: why }
      $.ui.toast(why.slice(0, 160))
    }
    const ran = await next(e)
    if (ran.deny === undefined && ran.isError !== true) {
      const c = await load($)
      c.files[file] = { sid: me, at: await $.clock.now() }
      await save($, c)
    }
    return ran
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const done = await next(e)
    if ((await mode($)) === 'off') return done
    me = await $.session.id()
    cwd = e.cwd
    await beat($)
    $.clock.every(60_000, () => beat($))
    await $.command.register({ name: 'collision-guard', description: 'Collision Guard: open its side panel' })
    void $.ui.open({ id: PANE, title: 'Collision Guard' })
    return done
  })

  on('session.end', async ($, e, next) => {
    try {
      const c = await load($)
      delete c.sessions[me]
      for (const [f, claim] of Object.entries(c.files)) if (claim.sid === me) delete c.files[f]
      await save($, c)
    } catch {
      // leaving stale claims is fine: they expire
    }
    return next(e)
  })

  on('command.run', { command: 'collision-guard' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Collision Guard' })
    return { text: 'Collision Guard: panel opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    await read($, tick)
    const { Box, Text } = $.ui.resolve(e)
    const m = await mode($)
    if (m === 'off') return <Text dimColor>Off (MOAA_COLLISION_GUARD=off).</Text>
    const now = await $.clock.now()
    const c = await load($)
    const live = Object.entries(c.sessions).filter(([, s]) => now - s.at <= ALIVE_MS)
    const held = (sid: string) => Object.entries(c.files).filter(([, f]) => f.sid === sid && now - f.at <= CLAIM_MS)
    const here = (s: { cwd: string }) => norm(s.cwd, '/') === norm(cwd, '/')
    live.sort((a, b) => Number(here(b[1])) - Number(here(a[1])))
    return (
      <Box flexDirection="column">
        <Text color="green">{m === 'block' ? 'blocking' : 'warning only'} · {live.length} live chat{live.length === 1 ? '' : 's'}</Text>
        {live.map(([sid, s]) => (
          <Box flexDirection="column">
            <Text color={sid === me ? 'cyan' : here(s) ? 'yellow' : undefined}>
              {sid === me ? 'this chat' : `chat ${sid.slice(0, 8)}`}{here(s) ? ' (this folder)' : ''}{s.branch ? ` · ${s.branch}` : ''}
            </Text>
            {sid !== me && !here(s) && <Text dimColor>  {s.cwd}</Text>}
            {held(sid).slice(0, 6).map(([f, claim]) => (
              <Text dimColor>  {f.split('/').slice(-2).join('/')} · {Math.max(1, Math.round((now - claim.at) / 60_000))}m</Text>
            ))}
            {held(sid).length > 6 && <Text dimColor>  and {held(sid).length - 6} more</Text>}
          </Box>
        ))}
      </Box>
    )
  })

  // the edit tools; a broken guard never stops an edit. ponytail: @ts-ignore for TS2589, the matcher's tool table
  // (built-in plus every connected MCP tool) is too deep for tsc; the engine checks the matcher itself.
  // @ts-ignore
  on('tool.call', { tool: 'Write' }, ($, e, next) => guard($, e, next)).catch(($, e, next) => next(e))
  // @ts-ignore
  on('tool.call', { tool: 'Edit' }, ($, e, next) => guard($, e, next)).catch(($, e, next) => next(e))
  // @ts-ignore
  on('tool.call', { tool: 'NotebookEdit' }, ($, e, next) => guard($, e, next)).catch(($, e, next) => next(e))
}
