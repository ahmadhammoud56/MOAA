import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Reading } from '../types'

const PANE = 'strata-meter'
const reading = atom({ plugin: 'strata-meter', key: 'reading' } as const, null as Reading | null)

const bar = (pct: number, width: number) => {
  const n = Math.round((Math.max(0, Math.min(100, pct)) / 100) * width)
  return '█'.repeat(n) + '░'.repeat(width - n)
}

const mmss = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** A rounded meter like the desktop app's Context bar. */
const meterSvg = (pct: number, color: string) => {
  const w = Math.round((Math.max(0, Math.min(100, pct)) / 100) * 64)
  return `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="8" viewBox="0 0 64 8">` +
    `<rect width="64" height="8" rx="4" fill="#d1d5db" fill-opacity="0.5"/>` +
    (w > 0 ? `<rect width="${Math.max(w, 8)}" height="8" rx="4" fill="${color}"/>` : '') + `</svg>`
}

const json = async ($: any, path: string) => {
  try {
    return JSON.parse(String(await $.fs.read(path)))
  } catch {
    return {}
  }
}

let stats = { pending: -1, atoms: 0, at: 0 } // `strata.py stats`, refreshed every few minutes (it opens SQLite)

/** strata.py of the newest installed strata, else undefined. */
async function strataScript($: any, home: string) {
  const dir = `${home}/.claude/plugins/cache/moaa/strata`
  try {
    const vers = (await $.fs.list(dir)).map((e: any) => String(e.name ?? e)).filter((n: string) => /^\d+\.\d+\.\d+$/.test(n))
    vers.sort((a: string, b: string) => {
      const x = a.split('.').map(Number), y = b.split('.').map(Number)
      return (x[0] ?? 0) - (y[0] ?? 0) || (x[1] ?? 0) - (y[1] ?? 0) || (x[2] ?? 0) - (y[2] ?? 0)
    })
    return vers.length ? `${dir}/${vers[vers.length - 1]}/strata.py` : undefined
  } catch {
    return undefined
  }
}

async function refresh($: any) {
  const home = String((await $.env.get('USERPROFILE')) || (await $.env.get('HOME')) || '.').replace(/\\/g, '/')
  const data = String((await $.env.get('MOAA_STRATA_DIR')) || `${home}/.claude/strata`).replace(/\\/g, '/')
  const cfg = await json($, `${data}/config.json`)
  const sid = String(await $.session.id()).replace(/[^\w-]/g, '_').slice(0, 80)
  const st = await json($, `${data}/handoff/${sid}.json`)
  const engine = await json($, `${data}/engine.json`)
  const now = await $.clock.now()
  if (now - stats.at > 180_000) {
    stats.at = now
    const script = await strataScript($, home)
    if (script) {
      for (const py of ['py', 'python3', 'python']) {
        try {
          const r = await $.process.run([py, script, 'stats'])
          if (r.exitCode !== 0) continue
          const s = JSON.parse(r.stdout)
          stats = { pending: s.pending ?? -1, atoms: s.l1_atoms ?? 0, at: now }
          break
        } catch {
          // try the next interpreter
        }
      }
    }
  }
  const vault = String(cfg.vault_path ?? '~/code/brain').replace(/^~/, home)
  const day = new Date(now).toISOString().slice(0, 10)
  let today = 0
  try {
    today = String(await $.fs.read(`${vault}/daily/${day}.md`)).split('\n').filter(l => l.startsWith('- ')).length
  } catch {
    // no line yet today
  }
  const r: Reading = {
    pct: (await $.session.usage()).context.percent ?? 0,
    threshold: Number(cfg.handoff_threshold ?? 85),
    handoffOn: cfg.handoff !== false,
    canaryHits: Number(st.canary_hits ?? 0),
    canaryMisses: Number(st.canary_misses ?? 0),
    pending: stats.pending,
    atoms: stats.atoms,
    pausedMin: Math.max(0, Math.ceil((Number(engine.until ?? 0) * 1000 - now) / 60_000)),
    fallback: String(cfg.fallback ?? 'local'),
    vault,
    vaultOk: cfg.vault !== false && (await $.fs.exists(`${vault}/Home.md`)),
    today,
    cache: (await json($, `${home}/.claude/moaa-mods/meters/${sid}.cache.json`)).ttlMs ? await json($, `${home}/.claude/moaa-mods/meters/${sid}.cache.json`) : null,
    goal: (await json($, `${home}/.claude/moaa-mods/meters/${sid}.goal.json`))?.text ? await json($, `${home}/.claude/moaa-mods/meters/${sid}.goal.json`) : null,
  }
  await update($, reading, () => r)
  if ((await $.env.get('MOAA_STRATA_METER')) === 'off') return $.ui.status(undefined)
  const pend = r.pending >= 0 ? ` · ${r.pending} to extract` : ''
  const pause = r.pausedMin ? ` · Haiku paused ${r.pausedMin}m` : ''
  $.ui.status(`strata ${bar(r.pct, 10)} ${Math.round(r.pct)}%/${r.threshold}% · canary ${r.canaryHits}✓ ${r.canaryMisses}✗${pend}${pause}`)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const done = await next(e)
    if ((await $.env.get('MOAA_STRATA_METER')) === 'off') return done
    await $.command.register({ name: 'strata-meter', description: 'Meters panel: context, cache, goal and strata' })
    void $.ui.open({ id: PANE, title: 'Meters' })
    await refresh($)
    $.clock.every(30_000, () => refresh($))
    return done
  })

  on('turn.complete', async ($, e, next) => {
    const out = await next(e)
    if (e.agentId === undefined) await refresh($)
    return out
  })

  on('command.run', { command: 'strata-meter' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Meters' })
    await refresh($)
    return { text: 'strata meter: panel opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const els = $.ui.resolve(e) as any
    const { Box, Text } = els
    const r = await read($, reading)
    if (!r) return <Text dimColor>Reading...</Text>
    // A desktop draws a real meter (an SVG track like the app's own Context row); other surfaces a text bar.
    const meter = (key: string, pct: number, color: string, alt: string) => els.Svg
      ? <els.Svg key={key} alt={alt} width={64} height={8} source={meterSvg(pct, color)} />
      : <Text color={color}>{bar(pct, 10)}</Text>
    const row = (key: string, label: string, value: string, pct: number | null, color = '#3b82f6') => (
      <Box key={key} flexDirection="row" gap={1}>
        <Text bold>{label.padEnd(8)}</Text>
        <Text dimColor>{value.padStart(14)}</Text>
        {pct === null ? null : meter(`${key}-m`, pct, color, `${label} ${Math.round(pct)}%`)}
      </Box>
    )
    const c = r.cache
    const cachePct = c ? Math.max(0, Math.min(100, (c.leftMs / c.ttlMs) * 100)) : null
    const cacheColor = !c || c.leftMs <= 0 ? '#ef4444' : c.leftMs < 60_000 ? '#f59e0b' : '#22c55e'
    const g = r.goal
    const goalPct = g && g.total ? (Math.min(g.done, g.total) / g.total) * 100 : g && g.limit ? (g.turns / g.limit) * 100 : null
    const near = r.pct >= r.threshold - 10
    return (
      <Box flexDirection="column" gap={0}>
        {row('ctx', 'Context', `${Math.round(r.pct)}% / ${r.threshold}%`, (r.pct / r.threshold) * 100, near ? '#f59e0b' : '#3b82f6')}
        {row('cache', 'Cache', !c ? 'no call yet' : c.leftMs > 0 ? `${mmss(c.leftMs)} left` : `cold $${c.rewarm.toFixed(2)}`, cachePct, cacheColor)}
        {row('goal', 'Goal', !g ? 'none' : g.total ? `${g.done}/${g.total}` : `turn ${g.turns}${g.limit ? `/${g.limit}` : ''}`, goalPct, '#8b5cf6')}
        {row('canary', 'Canary', `${r.canaryHits}✓ ${r.canaryMisses}✗`, null)}
        {row('memory', 'Memory', r.pending >= 0 ? `${r.pending} to extract` : `${r.atoms} notes`, null)}
        {r.pausedMin ? row('engine', 'Engine', `paused ${r.pausedMin}m`, null) : null}
        {row('vault', 'Vault', r.vaultOk ? `${r.today} chats today` : 'missing', null)}
      </Box>
    )
})
}
