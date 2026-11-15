import type { ElementTable, RenderElement } from 'claude-code'

import { inlineText } from './markdown'
import type { TableCell, TableBlock } from './markdown'
import type { Theme } from './theme'

export type StatusMatrix = 'off' | 'color' | 'summary' | 'group'

export type Bucket = 'pass' | 'fail' | 'warn' | 'wait'

const BUCKETS: readonly Bucket[] = ['pass', 'fail', 'warn', 'wait']

const WORDS: Record<Bucket, readonly string[]> = {
  pass: ['✓', '✔', 'passed', 'pass', 'succeeded', 'succeeds', 'succeed', 'success', 'ok', 'okay', 'done', 'healthy', 'completed', 'complete', 'online', 'active', 'ready'],
  fail: ['✗', '✘', 'failed', 'fail', 'failure', 'errored', 'error', 'broken', 'down', 'offline', 'inactive', 'dead', 'critical', 'rejected', 'denied'],
  warn: ['⚠', '▲', 'warning', 'warn', 'degraded', 'stale', 'flaky', 'timeout', 'retrying', 'retried'],
  wait: ['●', '○', 'pending', 'running', 'queued', 'waiting', 'in-progress', 'scheduled', 'paused', 'skipped', 'skip'],
}

export const GLYPH: Record<Bucket, string> = { pass: '✓', fail: '✗', warn: '⚠', wait: '●' }

export const TOKEN: Record<Bucket, 'codeString' | 'diffRemoved' | 'tableHeader' | 'codeComment'> =
  { pass: 'codeString', fail: 'diffRemoved', warn: 'tableHeader', wait: 'codeComment' }

const BYWORD: Partial<Record<string, Bucket>> = {}

for (const bucket of BUCKETS) for (const word of WORDS[bucket]) BYWORD[word] = bucket

const BYGLYPH: Partial<Record<string, Bucket>> = { '✓': 'pass', '✗': 'fail', '⚠': 'warn', '●': 'wait' }

export const bucketOf = (cell: TableCell): Bucket | undefined => BYWORD[inlineText(cell).trim().toLowerCase()]

export type Status = { column: number; buckets: (Bucket | undefined)[]; counts: Partial<Record<Bucket, number>> }

const countsOf = (buckets: (Bucket | undefined)[]): Partial<Record<Bucket, number>> => {
  const counts: Partial<Record<Bucket, number>> = {}
  for (const bucket of buckets) if (bucket) counts[bucket] = (counts[bucket] ?? 0) + 1
  return counts
}

const columnOf = (block: TableBlock): Status | undefined => {
  let chosen: Status | undefined
  let best = 1
  for (let c = 0; c < block.header.length; c++) {
    let count = 0
    const buckets = block.rows.map(row => {
      const bucket = bucketOf(row[c]!)
      if (bucket) count++
      return bucket
    })
    if (count >= 2 && count * 2 > block.rows.length && (!chosen || count > best)) {
      chosen = { column: c, buckets, counts: countsOf(buckets) }
      best = count
    }
  }
  return chosen
}

export const statusOf = (block: TableBlock, option: StatusMatrix, stacked: boolean): Status | undefined => {
  if (option === 'off' || stacked || block.rows.length < 2) return undefined
  return columnOf(block)
}

export type StatusLayout = { rows: TableCell[][]; buckets: (Bucket | undefined)[] }

export const statusRows = (block: TableBlock, status: Status | undefined, option: StatusMatrix): StatusLayout => {
  if (!status) return { rows: block.rows, buckets: [] }
  if (option !== 'group') return { rows: block.rows, buckets: status.buckets }
  const grouped = [...BUCKETS, undefined].flatMap(bucket =>
    block.rows.map((cells, r) => ({ cells, bucket: status.buckets[r] })).filter(cell => cell.bucket === bucket))
  return { rows: grouped.map(cell => cell.cells), buckets: grouped.map(cell => cell.bucket) }
}

export const statusLook = (t: Theme, status: Status | undefined, c: number, cell: TableCell, plain: { color?: string } = {}): { color?: string } => {
  if (!status || c !== status.column) return plain
  const text = inlineText(cell).trim().toLowerCase()
  const bucket = BYWORD[text] ?? BYGLYPH[inlineText(cell).trim()[0] ?? '']
  return bucket ? { color: t[TOKEN[bucket]] } : plain
}

export const statusHeavy = (option: StatusMatrix, buckets: (Bucket | undefined)[], i: number): boolean =>
  option === 'group' && buckets[i] !== buckets[i + 1]

export const statusEdge = (option: StatusMatrix, buckets: (Bucket | undefined)[], i: number, plain: string, heavy: string): string =>
  statusHeavy(option, buckets, i) ? heavy : plain

export const statusFooter = ({ Text }: ElementTable, t: Theme, status: Status | undefined, option: StatusMatrix, key: string): RenderElement | undefined => {
  if (!status || option === 'off' || option === 'color') return undefined
  const row = BUCKETS.filter(b => (status.counts[b] ?? 0) > 0).flatMap((b, i) => [
    ...(i > 0 ? [<Text key={`${key}.s${i}`} dimColor>{' · '}</Text>] : []),
    <Text key={`${key}.${b}`} color={t[TOKEN[b]]}>{`${GLYPH[b]} ${status.counts[b]}`}</Text>,
  ])
  return row.length ? <Text key={key}>{row}</Text> : undefined
}
