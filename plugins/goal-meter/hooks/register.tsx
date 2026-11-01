import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Goal, Progress } from '../types'

const goal = atom({ plugin: 'goal-meter', key: 'goal' } as const, null as Goal | null)
const PANE = 'goal-meter'
const progress = atom({ plugin: 'goal-meter', key: 'progress' } as const, null as Progress | null)

/** Acceptance items in a long-task brief: the numbered lines under **Acceptance:**. */
export const countAcceptance = (brief: string) => {
  const part = brief.split(/\*\*Acceptance:?\*\*:?/)[1]?.split(/\n\*\*[A-Z]/)[0] ?? ''
  return part.split('\n').filter(l => /^\d+\.\s/.test(l)).length
}

/** Rows of a checks.md table whose final verdict (last cell that is not "-") starts with "verified". */
export const countVerified = (checks: string) =>
  checks.split('\n').filter(l => /^\|\s*\d+\s*\|/.test(l)).filter(l => {
    const cells = l.split('|').map(c => c.trim()).filter(Boolean)
    const last = [...cells].reverse().find(c => c !== '-') ?? ''
    return /^verified/i.test(last)
  }).length

const bar = (done: number, total: number, width = 20) => {
  const n = total > 0 ? Math.round((Math.min(done, total) / total) * width) : 0
  return '█'.repeat(n) + '░'.repeat(width - n)
}

const measure = async ($: any, g: Goal): Promise<Progress | null> => {
  const task = /\.claude[\\/]long-task[\\/]([\w.-]+)/.exec(g.text)?.[1]
  if (task) {
    const dir = `.claude/long-task/${task}`
    const brief = (await $.fs.exists(`${dir}/brief.md`)) ? await $.fs.read(`${dir}/brief.md`) : ''
    const checks = (await $.fs.exists(`${dir}/checks.md`)) ? await $.fs.read(`${dir}/checks.md`) : ''
    const total = countAcceptance(String(brief))
    if (total) return { done: Math.min(countVerified(String(checks)), total), total, label: 'checks verified' }
  }
  const loop = /\.claude[\\/]loop[\\/]([\w.-]+)/.exec(g.text)?.[1]
  if (loop && (await $.fs.exists(`.claude/loop/${loop}/loop.json`))) {
    const cfg = JSON.parse(String(await $.fs.read(`.claude/loop/${loop}/loop.json`)))
    const target = cfg.target != null ? `, target ${cfg.target}` : ''
    return { done: cfg.iters ?? 0, total: cfg.max_iters || 0, label: `attempts, best ${cfg.best}${target}` }
  }
  return g.limit ? { done: g.turns, total: g.limit, label: 'turns' } : null
}

const setGoal = async ($: any, args: string) => {
  const text = args.trim()
  if (!text || /^(clear|off|stop)$/i.test(text)) {
    await update($, goal, () => null)
    await update($, progress, () => null)
    return
  }
  const limit = Number(/stop after (\d+) turns?/i.exec(text)?.[1] ?? 0)
  const g: Goal = { text, turns: 0, limit }
  await update($, goal, () => g)
  await update($, progress, () => null)
  try {
    const p = await measure($, g)
    await update($, progress, () => p)
  } catch {
    // an unreadable brief leaves the bar empty
  }
}

/** The status line under the prompt (drawn everywhere, Remote Control included). */

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
  const g = await read($, goal)
  if (!g || (await $.env.get('MOAA_GOAL_METER')) === 'off') {
    await snapshot($, 'goal', null)
    return $.ui.status(undefined)
  }
  const p = await read($, progress)
  await snapshot($, 'goal', { text: g.text, turns: g.turns, limit: g.limit, done: p?.done ?? 0, total: p?.total ?? 0, label: p?.label ?? '' })
  const short = g.text.length > 50 ? `${g.text.slice(0, 47)}...` : g.text
  $.ui.status(p && p.total
    ? `goal ${bar(p.done, p.total, 12)} ${p.done}/${p.total} ${p.label} · ${short}`
    : `goal · turn ${g.turns} · ${short}`)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const done = await next(e)
    if ((await $.env.get('MOAA_GOAL_METER')) === 'off') return done
    await $.command.register({ name: 'goal-meter', description: 'Goal Meter: open its side panel' })
    return done
  })

  on('command.run', { command: 'goal-meter' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Goal' })
    return { text: 'Goal Meter: panel opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const g = await read($, goal)
    if (!g) return <Text dimColor>No goal set. /goal sets one.</Text>
    const p = await read($, progress)
    const pct = p && p.total ? Math.round((Math.min(p.done, p.total) / p.total) * 100) : null
    return (
      <Box flexDirection="column">
        <Text>{g.text}</Text>
        {p && p.total ? <Text color="cyan">{bar(p.done, p.total, 24)} {pct}%</Text> : null}
        {p && p.total ? <Text dimColor>{p.done} of {p.total} {p.label}</Text> : null}
        <Text dimColor>turn {g.turns}{g.limit ? ` of ${g.limit}` : ''}</Text>
      </Box>
    )
  })

  on('command.run', { command: 'goal' }, async ($, e, next) => {
    if ((await $.env.get('MOAA_GOAL_METER')) !== 'off') await setGoal($, e.args)
    await pinStatus($)
    return next(e)
  })

  // A typed `/goal ...` may arrive as a prompt carrying the command rather than a command run.
  on('prompt.submit', async ($, e, next) => {
    if (e.command?.name === 'goal' && (await $.env.get('MOAA_GOAL_METER')) !== 'off') {
      await setGoal($, e.command.args ?? '')
      await pinStatus($)
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const g = await read($, goal)
    if (e.agentId === undefined && g) {
      const turned = { ...g, turns: g.turns + 1 }
      await update($, goal, () => turned)
      try {
        const p = await measure($, turned)
        await update($, progress, () => p)
      } catch {
        // keep the last reading
      }
      await pinStatus($)
    }
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const g = await read($, goal)
    if (!g || e.props.hasSurvey || (await $.env.get('MOAA_GOAL_METER')) === 'off') return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const p = await read($, progress)
    const pct = p && p.total ? Math.round((Math.min(p.done, p.total) / p.total) * 100) : null
    const short = g.text.length > 60 ? `${g.text.slice(0, 57)}...` : g.text
    return (
      <Box>
        <Text color="cyan">goal </Text>
        {p && p.total
          ? <Text>{bar(p.done, p.total)} {p.done} of {p.total} {p.label} · {pct}%</Text>
          : <Text dimColor>turn {g.turns}</Text>}
        <Text dimColor>{'  '}{short}</Text>
      </Box>
    )
  })
}
