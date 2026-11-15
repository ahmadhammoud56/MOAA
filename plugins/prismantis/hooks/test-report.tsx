import type { ElementTable, RenderElement } from 'claude-code'

import { inlineText } from './markdown'
import type { TableBlock } from './markdown'
import { GLYPH, TOKEN, statusOf } from './status'
import type { Bucket, Status } from './status'
import type { Theme } from './theme'

export type TestMatrix = 'off' | 'report'

const UNIT: Record<string, number> = { 'µs': 0.001, 'us': 0.001, 'ms': 1, 's': 1000, 'm': 60000, 'h': 3600000 }

const RUN = /(\d+(?:\.\d+)?)\s*(µs|us|ms|s|m|h)(?![a-z])/g

const BARE = /^\d+(?:\.\d+)?$/

const millisOf = (cell: string, bareMs: boolean): number | undefined => {
  const text = cell.trim().toLowerCase()
  RUN.lastIndex = 0
  let total = 0
  let runs = 0
  for (let word = RUN.exec(text); word; word = RUN.exec(text)) {
    total += Number(word[1]) * UNIT[word[2]!]!
    runs++
  }
  if (runs === 0 && bareMs && BARE.test(text)) return Number(text)
  if (runs === 0 || text.replace(RUN, '').trim() !== '') return undefined
  return total
}

const share = (value: number): string => (value % 1 === 0 ? value.toFixed(0) : value.toFixed(1))

const fmt = (ms: number): string => {
  if (ms < 1) return `${Math.round(ms * 1000)}µs`
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) {
    const s = Math.round(ms / 100) / 10
    return `${share(s)}s`
  }
  const h = Math.floor(ms / 3600000)
  const m = Math.floor((ms % 3600000) / 60000)
  const s = Math.round((ms % 60000) / 1000)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return h > 0 ? `${h}h ${pad(m)}m ${pad(s)}s` : `${m}m ${pad(s)}s`
}

type Timed = { column: number; total: number }

const timedColumnOf = (block: TableBlock): Timed | undefined => {
  let chosen: Timed | undefined
  let best = 1
  for (let c = 0; c < block.header.length; c++) {
    const bareMs = inlineText(block.header[c]!).toLowerCase().includes('ms')
    let count = 0
    let total = 0
    for (const row of block.rows) {
      const ms = millisOf(inlineText(row[c]!), bareMs)
      if (ms !== undefined) {
        count++
        total += ms
      }
    }
    if (count >= 2 && count * 2 > block.rows.length && (!chosen || count > best)) {
      chosen = { column: c, total }
      best = count
    }
  }
  return chosen
}

const shareOf = (status: Status, rows: number): string =>
  share(Math.round(((status.counts.pass ?? 0) / rows) * 1000) / 10)

const KINDS: readonly Bucket[] = ['fail', 'warn', 'wait']

export const testReport = ({ Text }: ElementTable, t: Theme, block: TableBlock, option: TestMatrix, key: string): RenderElement | undefined => {
  if (option === 'off') return undefined
  const status = statusOf(block, 'color', false)
  if (!status) return undefined
  const time = timedColumnOf(block)
  if (!time) return undefined
  const rows = block.rows.length
  const row = [
    <Text key={`${key}.pass`} color={t[TOKEN.pass]}>{`${GLYPH.pass} ${status.counts.pass ?? 0}`}</Text>,
    <Text key={`${key}.share`}>{` of ${rows} (${shareOf(status, rows)}%)`}</Text>,
    ...KINDS.flatMap((bucket) =>
      (status.counts[bucket] ?? 0) > 0
        ? [
            <Text key={`${key}.${bucket}.s`} dimColor>{' · '}</Text>,
            <Text key={`${key}.${bucket}`} color={t[TOKEN[bucket]]}>{`${GLYPH[bucket]} ${status.counts[bucket]}`}</Text>,
          ]
        : []),
    <Text key={`${key}.time.s`} dimColor>{' · '}</Text>,
    <Text key={`${key}.time`} dimColor>{`${fmt(time.total)} total`}</Text>,
  ]
  return <Text key={key}>{row}</Text>
}
