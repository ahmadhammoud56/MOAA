const WIDE = /[\u1100-\u115F\u2E80-\uA4CF\uAC00-\uD7A3\uF900-\uFAFF\uFE30-\uFE4F\uFF00-\uFF60\uFFE0-\uFFE6\u{20000}-\u{3FFFD}\u20E3]|\p{Emoji_Presentation}|\p{Extended_Pictographic}\uFE0F/u
const segmenter = new Intl.Segmenter()

export const DEFAULT_COLUMNS = 100

export const MIN_COLUMNS = 20

export const graphemes = (s: string): string[] => [...segmenter.segment(s)].map(g => g.segment)

const CLUSTER_UNITS = 32

export const clusters = (s: string, count: number): string => {
  let n = 0
  for (const { index, segment } of segmenter.segment(s)) if (n++ === count || index + segment.length > count * CLUSTER_UNITS) return s.slice(0, index)
  return s
}

export const cells = (s: string): string[] => (/^[ -~]*$/.test(s) ? [...s] : graphemes(s).flatMap(g => (WIDE.test(g) ? [g, ''] : [g])))

const ZERO = /^[\p{M}\p{Default_Ignorable_Code_Point}]+$/u

export const width = (s: string): number =>
  /^[ -~]*$/.test(s) ? s.length
  : s.length === 1 ? (ZERO.test(s) ? 0 : WIDE.test(s) ? 2 : 1)
  : graphemes(s).reduce((w, g) => (ZERO.test(g) ? w : w + (WIDE.test(g) ? 2 : 1)), 0)

export const widestLine = (text: string): number => Math.max(...text.split('\n').map(width))

export const wrapRanges = (text: string, w: number): [number, number][] => {
  const br = text.indexOf('\n')
  if (br >= 0) return [...wrapRanges(text.slice(0, br), w), ...wrapRanges(text.slice(br + 1), w).map(([a, b]): [number, number] => [a + br + 1, b + br + 1])]
  if (width(text) <= w) return [[0, text.length]]
  const out: [number, number][] = []
  let line: [number, number] | undefined
  let used = 0
  for (const word of text.matchAll(/\S+/g)) {
    let start = word.index
    const end = start + word[0].length
    let size = width(word[0])
    if (size > w) {
      if (line) out.push(line)
      line = undefined
      let cut = start
      let taken = 0
      for (const g of graphemes(text.slice(start, end))) {
        const step = width(g)
        if (cut > start && taken + step > w) {
          out.push([start, cut])
          start = cut
          size -= taken
          taken = 0
          if (size <= w) break
        }
        cut += g.length
        taken += step
      }
    }
    if (start === end) continue
    const joined = line ? used + width(text.slice(line[1], start)) + size : Infinity
    if (line && joined <= w) {
      line = [line[0], end]
      used = joined
    } else {
      if (line) out.push(line)
      line = [start, end]
      used = size
    }
  }
  if (line) out.push(line)
  return out.length ? out : [[0, 0]]
}

export const mostLines = (text: string, w: number): number => (text.match(/\S+/g)?.length ?? 0) + Math.ceil(width(text) / Math.max(1, w))

export const textRows = (text: string, w: number): number =>
  text.split('\n').reduce((sum, line) => sum + (width(line) <= w ? 1 : mostLines(line, w)), 0)

export const longestWord = (text: string): number => Math.max(0, ...text.split(/\s+/).map(width))

export const columnWidths = (natural: number[], available: number, gap: number, words: number[] = []): number[] => {
  const room = Math.max(natural.length, available - gap * (natural.length - 1))
  const total = natural.reduce((a, b) => a + b, 0)
  if (total <= room) return natural
  const minimum = natural.map((w, c) => Math.min(w, Math.max(1, words[c] ?? 1)))
  const widths = natural.map(() => 0)
  let open = natural.map((_, c) => c)
  let left = room
  for (let fixed = [-1]; fixed.length; ) {
    const share = Math.floor(left / open.length)
    const claim = (c: number) => (natural[c]! <= share ? natural[c]! : minimum[c]!)
    const minimumsFit = open.reduce((a, c) => a + minimum[c]!, 0) <= left
    const needed = open.reduce((a, c) => a + claim(c), 0)
    fixed = open.filter(c => natural[c]! <= share)
    if (minimumsFit && (!fixed.length || needed > left)) fixed = open.filter(c => minimum[c]! > share)
    fixed.forEach(c => (widths[c] = claim(c), left -= widths[c]!))
    open = open.filter(c => !fixed.includes(c))
  }
  open.forEach((c, i) => (widths[c] = Math.max(1, Math.floor(left / open.length) + (i < left % open.length ? 1 : 0))))
  while (widths.reduce((a, b) => a + b, 0) > room) {
    const widest = widths.indexOf(Math.max(...widths))
    if (widths[widest]! <= 1) break
    widths[widest]!--
  }
  return widths
}
