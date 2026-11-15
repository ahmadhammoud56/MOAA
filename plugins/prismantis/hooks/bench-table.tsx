import type { ElementTable, RenderElement } from 'claude-code'

import { inlineText } from './markdown'
import type { TableCell, TableBlock } from './markdown'
import type { Theme } from './theme'

export type BenchTable = 'off' | 'color' | 'trend'

export type Bench = { column: number; higher: boolean; series: { column: number; values: (number | undefined)[] } | undefined }

const DELTA = /^([+\u2212-]|\u00b1)?\s*(\d+(?:\.\d+)?)\s*(%|x|\u00d7)$/i

const SIZE = /^[^0-9\u00b1+-]*([-+]?\d+(?:\.\d+)?)\s*(?:\u00b5s|us|ms|s|m|h|%|x|\u00d7|kb|mb|gb|\/s|k|t)?$/i

const BETTER = /((?:req|ops)\s*\/\s*s|qps|fps|(?:kb|mb|gb)\/s|throughput|score)/i

const numberCell = (cell: TableCell): number | undefined => {
  const m = SIZE.exec(inlineText(cell).trim())
  return m ? Number(m[1]) : undefined
}

const deltaOf = (cell: TableCell): boolean | undefined => {
  const sign = DELTA.exec(inlineText(cell).trim())?.[1]
  if (!sign || sign === '\u00b1') return undefined
  return sign !== '\u2212' && sign !== '-'
}

const numberize = (block: TableBlock, read: (cell: TableCell) => number | undefined) => {
  let chosen: { column: number; values: (number | undefined)[] } | undefined
  let best = 1
  for (let c = 0; c < block.header.length; c++) {
    let count = 0
    const values = block.rows.map(row => {
      const value = read(row[c]!)
      if (value !== undefined) count++
      return value
    })
    if (count >= 2 && count * 2 > block.rows.length && (!chosen || count > best)) {
      chosen = { column: c, values }
      best = count
    }
  }
  return chosen
}

const deltasOf = (block: TableBlock): { column: number; deltas: (boolean | undefined)[] } | undefined => {
  let chosen: { column: number; deltas: (boolean | undefined)[] } | undefined
  let best = 1
  for (let c = 0; c < block.header.length; c++) {
    let count = 0
    const deltas = block.rows.map(row => {
      const delta = deltaOf(row[c]!)
      if (delta !== undefined) count++
      return delta
    })
    if (count >= 2 && count * 2 > block.rows.length && (!chosen || count > best)) {
      chosen = { column: c, deltas }
      best = count
    }
  }
  return chosen
}

export const benchOf = (block: TableBlock, option: BenchTable): Bench | undefined => {
  if (option === 'off' || block.rows.length < 2) return undefined
  const delta = deltasOf(block)
  if (!delta) return undefined
  return { column: delta.column, higher: block.header.some(h => BETTER.test(inlineText(h))), series: numberize(block, numberCell) }
}

export const benchLook = (t: Theme, bench: Bench | undefined, c: number, cell: TableCell, plain: { color?: string } = {}): { color?: string } => {
  if (!bench || c !== bench.column) return plain
  const delta = deltaOf(cell)
  if (delta === undefined) return plain
  return { color: delta === bench.higher ? t.diffAdded : t.diffRemoved }
}

const BLOCKS = ['\u2581', '\u2582', '\u2583', '\u2584', '\u2585', '\u2586', '\u2587', '\u2588']

export const benchSpark = ({ Text }: ElementTable, t: Theme, block: TableBlock, bench: Bench | undefined, option: BenchTable, key: string): RenderElement | undefined => {
  if (option !== 'trend' || !bench || !bench.series) return undefined
  const values = bench.series.values
  if (values.length !== block.rows.length || values.some(v => v === undefined)) return undefined
  const min = Math.min(...(values as number[]))
  const max = Math.max(...(values as number[]))
  const span = max - min || 1
  const row = values.map((v, i) => {
    const here = v as number
    const glyph = BLOCKS[Math.round(((here - min) / span) * 7)]!
    const prev = values[i - 1]
    if (prev === undefined || prev === here) return <Text key={`${key}.${i}`}>{glyph}</Text>
    return <Text key={`${key}.${i}`} color={bench.higher === here > prev ? t.diffAdded : t.diffRemoved}>{glyph}</Text>
  })
  return <Text key={key}>{row}</Text>
}
