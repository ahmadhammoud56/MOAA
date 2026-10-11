import type { Inline } from './markdown'

type Dir = 'R' | 'L'
export type Flow = { base: Dir; lines: Inline[][] }
export type Shape = 'visual' | 'words' | 'logical'

export const TERMINALS = {
  warp: 'visual',
  ghostty: 'visual',
  wezterm: 'visual',
  vscode: 'visual',
  alacritty: 'visual',
  'windows-terminal': 'visual',
  'apple-terminal': 'logical',
  kitty: 'words',
  iterm: 'logical',
  gnome: 'logical',
  konsole: 'logical',
} as const satisfies Record<string, Shape>

export type Terminal = keyof typeof TERMINALS

type Fmt = { wrap: ('strong' | 'emphasis' | 'strike')[]; leaf: 'text' | 'code' | 'number' | 'path' | 'link' | 'dim' }
type Unit = { ch: string; fmt: Fmt }

const R = /[֐-׿؀-ٟ٪-ۯۺ-ݿࢠ-ࣿיִ-﷿ﹰ-﻿]/
const L = /[A-Za-z0-9À-ɏ٠-٩۰-۹]/
const LATIN = /[A-Za-zÀ-ɏ]/
const MARK = /\p{M}/u
const MIRROR: Record<string, string> = { '(': ')', ')': '(', '[': ']', ']': '[', '{': '}', '}': '{', '<': '>', '>': '<' }
const DIGIT = /[0-9\u0660-\u0669\u06F0-\u06F9]/
const TERMINATOR = /[%\u2030\u00B0$\u20AC\u00A3\u00A5\u20AA]/
const COMMENT = /^(.*?)((?:^|\s)(?:#|\/\/)\s+)(.*)$/

const classify = (ch: string): Dir | null => (R.test(ch) ? 'R' : L.test(ch) ? 'L' : null)

const units = (text: string, fmt: Fmt): Unit[] => {
  const out: Unit[] = []
  for (const cp of text) {
    const last = out.at(-1)
    if (last && MARK.test(cp)) last.ch += cp
    else out.push({ ch: cp, fmt })
  }
  return out
}

const flatten = (nodes: Inline[], wrap: Fmt['wrap'] = []): Unit[] =>
  nodes.flatMap(n => {
    switch (n.kind) {
      case 'strong':
      case 'emphasis':
      case 'strike':
        return flatten(n.children, [...wrap, n.kind])
      case 'link':
        return n.text === n.href
          ? units(n.text, { wrap, leaf: 'link' })
          : [...units(n.text, { wrap, leaf: 'link' }), ...units(` (${n.href})`, { wrap, leaf: 'dim' })]
      default:
        return units(n.text, { wrap, leaf: n.kind })
    }
  })

const sameFmt = (a: Fmt, b: Fmt) => a.leaf === b.leaf && a.wrap.length === b.wrap.length && a.wrap.every((k, i) => k === b.wrap[i])

const leafNode = (leaf: Fmt['leaf'], text: string): Inline => (leaf === 'link' ? { kind: 'link', text, href: text } : { kind: leaf, text })

const rebuild = (all: Unit[]): Inline[] => {
  const out: Inline[] = []
  let i = 0
  while (i < all.length) {
    const fmt = all[i]!.fmt
    let text = ''
    let j = i
    while (j < all.length && sameFmt(all[j]!.fmt, fmt)) text += all[j++]!.ch
    out.push(fmt.wrap.reduceRight<Inline>((inner, kind) => ({ kind, children: [inner] }), leafNode(fmt.leaf, text)))
    i = j
  }
  return out
}

const baseOf = (all: Unit[]): Dir => {
  const words = all.map(u => u.ch).join('').split(/\s+/)
  const rw = words.filter(w => R.test(w)).length
  const lw = words.filter(w => LATIN.test(w) && !R.test(w)).length
  if (rw !== lw) return rw > lw ? 'R' : 'L'
  return all.map(u => classify(u.ch)).find(Boolean) ?? 'R'
}

const reorder = (all: Unit[], base: Dir): Unit[] => {
  const strong = all.map((u, i) => {
    const own = classify(u.ch)
    if (own) return own
    if (u.fmt.leaf === 'code' || u.fmt.leaf === 'path') return 'L'
    return TERMINATOR.test(u.ch) && (DIGIT.test(all[i - 1]?.ch ?? '') || DIGIT.test(all[i + 1]?.ch ?? '')) ? 'L' : null
  })
  const prev: (Dir | null)[] = []
  let seen: Dir | null = null
  strong.forEach((s, i) => {
    seen = s ?? seen
    prev[i] = seen
  })
  const next: (Dir | null)[] = []
  seen = null
  for (let i = strong.length - 1; i >= 0; i--) {
    seen = strong[i] ?? seen
    next[i] = seen
  }
  const dir = strong.map((s, i): Dir => s ?? ((prev[i] ?? base) === (next[i] ?? base) ? (prev[i] ?? base) : base))
  const runs: { d: Dir; u: Unit[] }[] = []
  all.forEach((u, i) => {
    const last = runs.at(-1)
    if (last && last.d === dir[i]) last.u.push(u)
    else runs.push({ d: dir[i]!, u: [u] })
  })
  const out = runs.map(r => (r.d === 'R' ? r.u.map(u => ({ ...u, ch: MIRROR[u.ch] ?? u.ch })).reverse() : r.u))
  return (base === 'R' ? out.reverse() : out).flat()
}

const wrapUnits = (all: Unit[], max: number, measure: (s: string) => number): Unit[][] => {
  const tokens: Unit[][] = []
  all.forEach((u, i) => {
    if (i === 0 || (u.ch !== ' ' && all[i - 1]!.ch === ' ')) tokens.push([])
    tokens.at(-1)!.push(u)
  })
  const lines: Unit[][] = [[]]
  let used = 0
  const trim = (line: Unit[]) => {
    while (line.at(-1)?.ch === ' ') line.pop()
  }
  for (const token of tokens) {
    let core = token.length
    while (core > 0 && token[core - 1]!.ch === ' ') core--
    const w = token.slice(0, core).reduce((sum, u) => sum + measure(u.ch), 0)
    if (lines.at(-1)!.length && used + w > max) {
      trim(lines.at(-1)!)
      lines.push([])
      used = 0
    }
    lines.at(-1)!.push(...token)
    used += w + (token.length - core)
  }
  trim(lines.at(-1)!)
  return lines
}

const clusters = (text: string): string[] => units(text, { wrap: [], leaf: 'text' }).map(u => u.ch)

const RUN = new RegExp(`(?:${R.source}|\\p{M})+`, 'gu')

const shapeText = (text: string, shape: Shape): string =>
  shape === 'words' && R.test(text) ? text.replace(RUN, run => clusters(run).reverse().join('')) : text

const shapeNodes = (nodes: Inline[], shape: Shape): Inline[] =>
  nodes.map(n => {
    if ('children' in n) return { ...n, children: shapeNodes(n.children, shape) }
    if (n.kind === 'link') return { ...n, text: shapeText(n.text, shape), href: shapeText(n.href, shape) }
    return { ...n, text: shapeText(n.text, shape) }
  })

const containsRtl = (nodes: Inline[]): boolean => nodes.some(n => ('children' in n ? containsRtl(n.children) : R.test(n.text)))

export const flow = (nodes: Inline[], columns: number, measure: (s: string) => number, shape: Shape = 'visual'): Flow | null => {
  if (!containsRtl(nodes)) return null
  const all = flatten(nodes)
  const base = baseOf(all)
  const logical = base === 'R' ? wrapUnits(all, columns, measure) : [all]
  const lines = logical.map(line => rebuild(shape === 'logical' ? line : reorder(line, base)))
  return { base, lines: shape === 'words' ? lines.map(line => shapeNodes(line, shape)) : lines }
}

const visualText = (text: string): string => {
  if (!R.test(text)) return text
  const all = units(text, { wrap: [], leaf: 'text' })
  return reorder(all, baseOf(all)).map(u => u.ch).join('')
}

export const commentTail = (line: string, shape: Shape = 'visual'): { head: string; marker: string; tail: string } | null => {
  if (shape === 'logical' || !R.test(line)) return null
  const m = COMMENT.exec(line)
  return m && R.test(m[3]!) ? { head: m[1]!, marker: m[2]!, tail: shapeText(visualText(m[3]!), shape) } : null
}

export const commentVisual = (text: string, shape: Shape = 'visual'): string => {
  const c = commentTail(text, shape)
  return c ? c.head + c.marker + c.tail : text
}

export const hasRtl = (text: string): boolean => R.test(text)
