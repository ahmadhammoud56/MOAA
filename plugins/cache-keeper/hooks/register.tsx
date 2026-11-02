import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { CacheInfo, Warmth } from '../types'

const info = atom({ plugin: 'cache-keeper', key: 'info' } as const, { lastCallAt: 0, tokens: 0, model: '' } as CacheInfo)
const warmth = atom({ plugin: 'cache-keeper', key: 'warmth' } as const,
  { on: false, lastPromptAt: 0, pings: 0, usd: 0 } as Warmth)
const tick = atom({ plugin: 'cache-keeper', key: 'tick' } as const, 0)
const PANE = 'cache-keeper'
const isHidden = atom({ plugin: 'cache-keeper', key: 'isHidden' } as const, false)

// USD per million tokens: [cache write (5 min), cache read]. ponytail: list prices change; the band claims an
// estimate only, and MOAA_CACHE_PRICE="write,read" overrides the table.
const PRICES: Record<string, [number, number]> = { opus: [6.25, 0.5], sonnet: [3.75, 0.3], haiku: [1.25, 0.1] }

const num = (v: string | undefined, fallback: number) => {
  const n = Number(v)
  return v !== undefined && v !== '' && Number.isFinite(n) && n > 0 ? n : fallback
}

/** Settings from the environment (each name literal, so the engine can list them). */
const settings = async ($: any) => ({
  off: (await $.env.get('MOAA_CACHE_KEEPER')) === 'off',
  // Claude Code on a subscription caches for 1 hour; with an API key set MOAA_CACHE_TTL_MIN=5.
  ttl: num(await $.env.get('MOAA_CACHE_TTL_MIN'), 60) * 60_000,
  idleCap: num(await $.env.get('MOAA_CACHE_IDLE_CAP_MIN'), 30) * 60_000,
  handoffPct: num(await $.env.get('MOAA_CACHE_HANDOFF_PCT'), 60),
  price: String((await $.env.get('MOAA_CACHE_PRICE')) ?? ''),
})

const priceOf = (custom: string, model: string): [number, number] => {
  const c = custom.split(',').map(Number)
  if (c.length === 2 && c.every(n => Number.isFinite(n) && n > 0)) return [c[0]!, c[1]!]
  const family = Object.keys(PRICES).find(f => model.toLowerCase().includes(f)) ?? 'opus'
  return PRICES[family] ?? [6.25, 0.5]
}

const mmss = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** 412k, 1.3M, 2.0B: the thresholds sit where rounding would otherwise print 1000k or 1000.0M. */
const tok = (n: number) =>
  n >= 999_950_000 ? `${(n / 1e9).toFixed(1)}B`
    : n >= 999_500 ? `${(n / 1e6).toFixed(1)}M`
    : n >= 1000 ? `${Math.round(n / 1000)}k`
    : String(n)

/** The status line under the prompt: drawn on every surface, Remote Control included (the band is terminal and
 *  desktop only). */

/** A per-chat snapshot for the shared Meters panel (strata-meter draws it). */
async function snapshot($: any, name: string, value: unknown) {
  try {
    const home = String((await $.env.get('USERPROFILE')) || (await $.env.get('HOME')) || '.').replace(/\\/g, '/')
    const sid = String(await $.session.id()).replace(/[^\w-]/g, '_')
    await $.fs.write(`${home}/.claude/moaa-mods/meters/${sid}.${name}.json`, JSON.stringify(value))
  } catch {
    // the panel shows "no reading" instead
  }
}

async function pinStatus($: any) {
  const cfg = await settings($)
  const c = await read($, info)
  if (cfg.off || !c.lastCallAt) return $.ui.status(undefined)
  const w = await read($, warmth)
  const left = c.lastCallAt + cfg.ttl - (await $.clock.now())
  const [w0] = priceOf(cfg.price, c.model)
  await snapshot($, 'cache', { leftMs: left, ttlMs: cfg.ttl, tokens: c.tokens, rewarm: (c.tokens * w0) / 1e6, keepWarm: w.on, at: await $.clock.now() })
  if (await read($, isHidden)) return $.ui.status(undefined) // hidden: the status line only; the Meters panel stays
  const k = `${tok(c.tokens)} tokens`
  const warm = w.on ? `keeping warm (${w.pings} pings, $${w.usd.toFixed(2)})` : 'keep warm: /cache-keeper on'
  if (left > 0) return $.ui.status(`cache ${left < 60_000 ? 'cooling' : 'warm'} ${mmss(left)} left · ${k} · ${warm}`)
  const pct = (await $.session.usage()).context.percent ?? 0
  const [write, readP] = priceOf(cfg.price, c.model)
  $.ui.status(pct >= cfg.handoffPct
    ? `cache cold · context ${Math.round(pct)}%: a strata handoff (fresh chat) beats re-warming`
    : `cache cold · next prompt re-writes ${k}, about $${((c.tokens * write) / 1e6).toFixed(2)} ` +
      `($${((c.tokens * (write - readP)) / 1e6).toFixed(2)} more than warm)`)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const done = await next(e)
    const cfg = await settings($)
    if (cfg.off) return done
    await $.command.register({ name: 'cache-keeper', description: 'Cache Keeper: on | off (keep this chat warm), hide, show, pane, status' })
    // One timer: redraw the countdown, and send a keep-warm ping shortly before the cache would lapse.
    $.clock.every(15_000, async () => {
      await update($, tick, n => n + 1)
      await pinStatus($)
      const w = await read($, warmth)
      const c = await read($, info)
      if (!w.on || !c.lastCallAt) return
      const now = await $.clock.now()
      if (now - w.lastPromptAt > cfg.idleCap) {
        await update($, warmth, v => ({ ...v, on: false }))
        $.ui.toast(`Cache Keeper: stopped keeping warm after ${cfg.idleCap / 60_000} idle minutes`)
        return
      }
      if (now - c.lastCallAt < cfg.ttl - 75_000) return
      // A fork re-sends this chat's own prefix, so the API reads (and so refreshes) the cached entry.
      const r = await $.model.fork({ prompt: 'Keep-warm ping: reply with the single word OK.' })
      if (!r.isAnswered) return
      const [write, readPrice] = priceOf(cfg.price, c.model)
      const input = write / 1.25 // base input price; output is 5x input
      const u = r.usage
      const usd = (u.cache_read_input_tokens * readPrice + (u.cache_creation_input_tokens ?? 0) * write
        + u.input_tokens * input + u.output_tokens * input * 5) / 1e6
      await update($, info, v => ({ ...v, lastCallAt: now }))
      await update($, warmth, v => ({ ...v, pings: v.pings + 1, usd: v.usd + usd }))
    })
    return done
  })

  on('prompt.submit', async ($, e, next) => {
    const now = await $.clock.now()
    await update($, warmth, v => ({ ...v, lastPromptAt: now }))
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined && e.usage) {
      const u = e.usage
      const now = await $.clock.now()
      const tokens = u.input_tokens + u.cache_read_input_tokens + (u.cache_creation_input_tokens ?? 0)
      await update($, info, () => ({ lastCallAt: now, tokens, model: u.model }))
      await pinStatus($)
    }
    return next(e)
  })

  on('command.run', { command: 'cache-keeper' }, async ($, e) => {
    const arg = e.args.trim()
    if (arg === 'on' || arg === 'off') {
      const now = await $.clock.now()
      await update($, warmth, v => ({ ...v, on: arg === 'on', lastPromptAt: now }))
      return { text: `Cache Keeper: keep-warm ${arg} for this chat.` }
    }
    if (arg === 'pane') {
      await $.ui.open({ id: PANE, title: 'Cache' })
      return { text: 'Cache Keeper: panel opened.' }
    }
    if (arg === 'hide' || arg === 'show') {
      await update($, isHidden, () => arg === 'hide')
      await pinStatus($)
      return { text: `Cache Keeper: band ${arg === 'hide' ? 'hidden' : 'shown'}.` }
    }
    const c = await read($, info)
    const w = await read($, warmth)
    return { text: `Cache Keeper: ${c.tokens} prompt tokens on ${c.model || 'no model yet'}; keep-warm ${w.on ? 'on' : 'off'}, ${w.pings} pings, about $${w.usd.toFixed(2)}.` }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    await read($, tick)
    const { Box, Button, Text } = $.ui.resolve(e)
    const c = await read($, info)
    if (!c.lastCallAt) return <Text dimColor>No model call yet in this chat.</Text>
    const cfg = await settings($)
    const w = await read($, warmth)
    const left = c.lastCallAt + cfg.ttl - (await $.clock.now())
    const [write] = priceOf(cfg.price, c.model)
    const pct = (await $.session.usage()).context.percent ?? 0
    const state = left <= 0 ? 'cold' : left < 60_000 ? 'cooling' : 'warm'
    return (
      <Box flexDirection="column">
        <Text color={state === 'warm' ? 'green' : state === 'cooling' ? 'yellow' : 'red'}>● cache {state}</Text>
        <Text>{state === 'cold' ? 'expired' : `${mmss(left)} left of ${cfg.ttl / 60_000} min`}</Text>
        <Text dimColor>{tok(c.tokens)} tokens · context {Math.round(pct)}%</Text>
        <Text dimColor>re-warm ≈ ${((c.tokens * write) / 1e6).toFixed(2)}, ${((c.tokens * (write - priceOf(cfg.price, c.model)[1])) / 1e6).toFixed(2)} more than warm ({c.model})</Text>
        {state === 'cold' && pct >= cfg.handoffPct && <Text color="yellow">Cheaper: strata handoff to a fresh chat</Text>}
        <Text dimColor>{w.on ? `keeping warm · ${w.pings} pings · $${w.usd.toFixed(2)}` : 'keep-warm off'}</Text>
        <Button
          key="pane-warm"
          label={w.on ? 'Stop keeping warm' : 'Keep warm'}
          onPress={async () => {
            const t = await $.clock.now()
            await update($, warmth, v => ({ ...v, on: !v.on, lastPromptAt: t }))
          }}
        />
      </Box>
    )
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    await read($, tick) // the timer's write redraws the countdown
    const c = await read($, info)
    const cfg = await settings($)
    if (e.props.hasSurvey || cfg.off || (await read($, isHidden)) || !c.lastCallAt) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const w = await read($, warmth)
    const left = c.lastCallAt + cfg.ttl - (await $.clock.now())
    const [write] = priceOf(cfg.price, c.model)
    const rewarm = (c.tokens * write) / 1e6
    const pct = (await $.session.usage()).context.percent ?? 0
    const state = left <= 0 ? 'cold' : left < 60_000 ? 'cooling' : 'warm'
    const color = state === 'warm' ? 'green' : state === 'cooling' ? 'yellow' : 'red'
    const advice = state !== 'cold' ? ` ${mmss(left)} left`
      : pct >= cfg.handoffPct ? ` · context ${Math.round(pct)}%: a strata handoff (fresh chat) beats re-warming`
      : ` · next prompt re-writes it, about $${rewarm.toFixed(2)}`
    return (
      <Box>
        <Text color={color}>● cache {state}</Text>
        <Text dimColor>
          {advice} · {tok(c.tokens)} tokens
          {w.on ? ` · keeping warm (${w.pings} pings, $${w.usd.toFixed(2)})` : ''}{' '}
        </Text>
        <Button
          key="warm"
          label={w.on ? 'Stop keeping warm' : 'Keep warm'}
          onPress={async () => {
            const t = await $.clock.now()
            await update($, warmth, v => ({ ...v, on: !v.on, lastPromptAt: t }))
          }}
        />
        <Button key="hide" label="Hide" onPress={() => update($, isHidden, () => true)} />
      </Box>
    )
  })
}
