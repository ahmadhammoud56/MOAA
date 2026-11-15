export type Inline =
  | { kind: 'text'; text: string }
  | { kind: 'strong'; children: Inline[] }
  | { kind: 'emphasis'; children: Inline[] }
  | { kind: 'strike'; children: Inline[] }
  | { kind: 'code'; text: string; href?: string }
  | { kind: 'math'; text: string }
  | { kind: 'link'; text: string; href: string }
  | { kind: 'image'; text: string; src: string }
  | { kind: 'number'; text: string }
  | { kind: 'path'; text: string; href?: string }
  | { kind: 'dim'; text: string; tint?: string }
  | { kind: 'footnote'; text: string; note?: number }

export type Note = { mark: string; inline: Inline[]; note: number }

export type TableAlign = 'left' | 'right' | 'center'
export type TableCell = Inline[]
export type TableBlock = Extract<Block, { kind: 'table' }>

export type Block = { raw: string } & (
  | { kind: 'heading'; level: number; inline: Inline[] }
  | { kind: 'paragraph'; inline: Inline[] }
  | { kind: 'list'; ordered: boolean; items: ListItem[] }
  | { kind: 'code'; lang: string; lines: string[]; isOpen?: true }
  | { kind: 'quote'; blocks: Block[] }
  | { kind: 'alert'; level: AlertLevel; blocks: Block[] }
  | { kind: 'rule' }
  | { kind: 'table'; header: TableCell[]; align: TableAlign[]; rows: TableCell[][] }
  | { kind: 'notes'; notes: Note[] }
)

export type ListItem = { marker: string; depth: number; task?: boolean; inline: Inline[]; blocks?: Block[] }

type Draft = Block extends infer B ? (B extends unknown ? Omit<B, 'raw'> : never) : never

export type AlertLevel = 'note' | 'tip' | 'important' | 'warning' | 'caution'
const ALERT = /^\[!(note|tip|important|warning|caution)\]\s*(.*)$/i

export type Highlight = { numbers: boolean; paths: boolean }

export const FIGURE_ROLES = ['accent', 'warn', 'ok', 'note', 'dim', 'strong'] as const

const ROLE_MARKUP = new RegExp(`\\{(?:${FIGURE_ROLES.join('|')}):([^{}]*)\\}`, 'g')

const MAX_INLINE = 4000
const MAX_QUOTE_DEPTH = 8
const MAX_TEX_DEPTH = 32
const QUOTE = /^\s*>/
const TABLE_SEP = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/
const FENCE = /^\s*(`{3,}|~{3,})\s*([\w+-]*)/
const NOTE_DEF = /^\[\^([^\]\s]+)\]:\s*(.*)$/
const TAG_LINE = /^\s*<\/?(?!br\b(?!>))[a-z][\w-]*(?:\s[^<>]*)?>\s*$/i
const SETEXT = /^ {0,3}(?:=+|-+)\s*$/
const SUPERSCRIPT = '⁰¹²³⁴⁵⁶⁷⁸⁹'

const splitRow = (line: string): string[] => {
  const trimmed = line.trim().replace(/^\|/, '').replace(/(?<!\\)\|$/, '')
  const cells: string[] = []
  let cell = ''
  for (let i = 0; i < trimmed.length; i++) {
    const ch = trimmed[i]
    if (ch === '\\' && trimmed[i + 1] === '|') {
      cell += '|'
      i++
    } else if (ch === '|') {
      cells.push(cell.trim())
      cell = ''
    } else {
      cell += ch
    }
  }
  cells.push(cell.trim())
  return cells
}

const CELL_BREAK = /(`+)(?!`).+?(?<!`)\1(?!`)|<br\s*\/?>/gi

const parseCell = (text: string, hl: Highlight): Inline[] => {
  if (text.length > MAX_INLINE) return parseInline(text, hl)
  const out: Inline[] = []
  let at = 0
  for (const m of text.matchAll(CELL_BREAK)) {
    if (m[1] !== undefined) continue
    out.push(...parseInline(text.slice(at, m.index).trim(), hl), { kind: 'text', text: '\n' })
    at = m.index + m[0].length
  }
  return at ? [...out, ...parseInline(text.slice(at).trim(), hl)] : parseInline(text, hl)
}

const INLINE = /(`+)(?!`)(.+?)(?<!`)\1(?!`)|\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)(?:\s+(?:"[^"\n]*"|'[^'\n]*'))?\)|\*\*(?!\s)((?:[^*]|\*[^*\s][^*]*?(?<!\s)\*)+?)(?<!\s)\*\*|(?<![\w_])__(?!\s)([^_]+?)(?<!\s)__(?![\w_])|~~([^~]+?)~~|(?<![\w*])\*([^*\s][^*]*?)(?<!\s)\*(?!\w)|(?<![\w_])_([^_\s][^_]*?)(?<!\s)_(?!\w)|(https?:\/\/(?:[^\s<>()]|\([^\s<>()]*\))*(?:[^\s<>().,;:!?'"]|\([^\s<>()]*\)))|(?<![\\$\w])\$(?=\S)((?:\\.|[^$\n\\])+?)(?<=\S)\$(?![\w$])|\[\^([^\]\s]+)\]|!\[([^\]]*)\]\(((?:[^()\s]|\([^()\s]*\))+)(?:\s+(?:"[^"\n]*"|'[^'\n]*'))?\)|<(https?:\/\/[^\s<>]+)>|\\([!-/:-@[-`{-~])/g
const NUMBER = /(?<![\w.#/-]|\d[.,:])((?:(?<!\p{L})-(?=\d))?v?\d+(?:[.,:]\d+)*(?:%|ms|s|m|h|d|Gi|Mi|GB|MB|KB|x)?)(?![\w/])/gu
const PATH = /(?<![\w/.:])((?:~|\.{1,2})?\/[\w.@+-]+(?:\/[\w.@+-]*)*)/g

const NAMED: Record<string, string> = {
  amp: '&', AMP: '&', lt: '<', LT: '<', gt: '>', GT: '>', quot: '"', QUOT: '"', apos: "'", nbsp: '\u00a0', COPY: '©', REG: '®', copy: '©', reg: '®', trade: '™', mdash: '—', ndash: '–', hellip: '…', minus: '−',
  times: '×', divide: '÷', plusmn: '±', deg: '°', middot: '·', bull: '•', sect: '§', para: '¶', micro: 'µ', laquo: '«', raquo: '»',
  lsquo: '‘', rsquo: '’', ldquo: '“', rdquo: '”', sbquo: '‚', bdquo: '„', euro: '€', pound: '£', yen: '¥', cent: '¢', frac12: '½', frac14: '¼', frac34: '¾', sup2: '²', sup3: '³',
  larr: '←', rarr: '→', uarr: '↑', darr: '↓', harr: '↔', lArr: '⇐', rArr: '⇒', hArr: '⇔', le: '≤', ge: '≥', ne: '≠', asymp: '≈', infin: '∞', check: '✓', cross: '✗', star: '☆', hearts: '♥', ensp: '\u2002', emsp: '\u2003', thinsp: '\u2009',
}
const ENTITY = /&(?:#(\d{1,7})|#[xX]([\da-fA-F]{1,6})|([A-Za-z][A-Za-z\d]{1,31}));/g
const codePoint = (n: number) => String.fromCodePoint(n > 0 && n <= 0x10ffff && (n < 0xd800 || n > 0xdfff) ? n : 0xfffd)
export const decodeEntities = (text: string): string =>
  text.includes('&') ? text.replace(ENTITY, (m, dec?: string, hex?: string, name?: string) => (name ? (Object.hasOwn(NAMED, name) ? NAMED[name]! : m) : codePoint(dec ? Number(dec) : parseInt(hex!, 16)))).replace(CONTROL, '') : text
const linkText = (text: string) => (/^`[^`]+`$/.test(text) ? text.slice(1, -1) : decodeEntities(text))

const decorate = (raw: string, hl: Highlight): Inline[] => {
  const text = decodeEntities(raw.replace(ROLE_MARKUP, '$1'))
  if (!hl.numbers && !hl.paths) return [{ kind: 'text', text }]
  const marks: { start: number; end: number; kind: 'number' | 'path' }[] = []
  if (hl.paths) for (const m of text.matchAll(PATH)) marks.push({ start: m.index, end: m.index + m[0].length, kind: 'path' })
  if (hl.numbers) {
    for (const m of text.matchAll(NUMBER)) {
      const start = m.index
      if (!marks.some(p => start < p.end && start + m[0].length > p.start)) {
        marks.push({ start, end: start + m[0].length, kind: 'number' })
      }
    }
  }
  marks.sort((a, b) => a.start - b.start)
  const out: Inline[] = []
  let at = 0
  for (const m of marks) {
    if (m.start > at) out.push({ kind: 'text', text: text.slice(at, m.start) })
    out.push({ kind: m.kind, text: text.slice(m.start, m.end) })
    at = m.end
  }
  if (at < text.length) out.push({ kind: 'text', text: text.slice(at) })
  return out
}

const inlineOf = (m: RegExpExecArray, hl: Highlight): Inline[] => {
  if (m[2] !== undefined) return [{ kind: 'code', text: m[2].replace(/^ ([^]*[^ ][^]*) $/, '$1') }]
  if (m[3] !== undefined) return [{ kind: 'link', text: linkText(m[3]), href: m[4]! }]
  if (m[5] !== undefined || m[6] !== undefined) return [{ kind: 'strong', children: parseInline(m[5] ?? m[6] ?? "", hl) }]
  if (m[7] !== undefined) return [{ kind: 'strike', children: parseInline(m[7], hl) }]
  if (m[8] !== undefined || m[9] !== undefined) return [{ kind: 'emphasis', children: parseInline(m[8] ?? m[9] ?? "", hl) }]
  if (m[11] !== undefined) return isTex(m[11]) ? [{ kind: 'math', text: texText(m[11]) }] : decorate(m[0], hl)
  if (m[12] !== undefined) return [{ kind: 'footnote', text: m[12] }]
  if (m[14] !== undefined) return [{ kind: 'image', text: m[13] || 'image', src: m[14] }]
  const url = m[10] ?? m[15]
  return url === undefined ? [] : [{ kind: 'link', text: url, href: url }]
}

export const parseInline = (text: string, hl: Highlight): Inline[] => {
  if (text.length > MAX_INLINE) return [{ kind: 'text', text: dropTints(text) }]
  const out: Inline[] = []
  let at = 0
  let plain = ''
  for (const m of text.matchAll(INLINE)) {
    plain += text.slice(at, m.index)
    at = m.index + m[0].length
    if (m[16] !== undefined) {
      plain += m[16]
      continue
    }
    if (plain) out.push(...tinted(plain, hl))
    plain = ''
    out.push(...inlineOf(m, hl))
  }
  plain += text.slice(at)
  if (plain) out.push(...tinted(plain, hl))
  return out
}

const TEX: Record<string, string> = {
  alpha: 'α', beta: 'β', gamma: 'γ', Gamma: 'Γ', delta: 'δ', Delta: 'Δ', epsilon: 'ε', varepsilon: 'ε', zeta: 'ζ', eta: 'η', theta: 'θ', Theta: 'Θ', iota: 'ι', kappa: 'κ', lambda: 'λ', Lambda: 'Λ', mu: 'μ', nu: 'ν', xi: 'ξ', Xi: 'Ξ', pi: 'π', Pi: 'Π', rho: 'ρ', sigma: 'σ', Sigma: 'Σ', tau: 'τ', upsilon: 'υ', phi: 'φ', varphi: 'φ', Phi: 'Φ', chi: 'χ', psi: 'ψ', Psi: 'Ψ', omega: 'ω', Omega: 'Ω',
  cdot: '·', times: '×', div: '÷', pm: '±', mp: '∓', le: '≤', leq: '≤', ge: '≥', geq: '≥', neq: '≠', ne: '≠', approx: '≈', sim: '∼', equiv: '≡', propto: '∝', infty: '∞', to: '→', rightarrow: '→', leftarrow: '←', Rightarrow: '⇒', iff: '⇔', mapsto: '↦',
  sum: 'Σ', prod: '∏', int: '∫', iint: '∬', oint: '∮', partial: '∂', nabla: '∇', in: '∈', notin: '∉', subset: '⊂', subseteq: '⊆', cup: '∪', cap: '∩', forall: '∀', exists: '∃', neg: '¬', land: '∧', lor: '∨', emptyset: '∅',
  ldots: '…', cdots: '⋯', dots: '…', ell: 'ℓ', hbar: 'ℏ', lceil: '⌈', rceil: '⌉', lfloor: '⌊', rfloor: '⌋', langle: '⟨', rangle: '⟩', mid: '∣', quad: ' ', qquad: '  ',
}
const FUNCTIONS = new Set(['ln', 'log', 'exp', 'min', 'max', 'sin', 'cos', 'tan', 'lim', 'det', 'sup', 'inf', 'arg', 'deg', 'gcd', 'Pr'])
const PLAIN = new Set(['text', 'mathrm', 'mathit', 'mathbf', 'textbf', 'texttt', 'mathsf', 'operatorname', 'boldsymbol'])
const SPACES: Record<string, string> = { ',': ' ', ';': ' ', ':': ' ', ' ': ' ', '!': '', '\\': ' ', '{': '{', '}': '}', '%': '%', '$': '$', '&': '&', '#': '#', '_': '_' }
const scriptMap = (from: string, to: string) => new Map(Array.from(from).map((c, i) => [c, Array.from(to)[i]!]))
const SUP = scriptMap('0123456789+-−=()niabcdefghjklmoprstuvwxyzABDEGHIJKLMNOPRTUVW', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ⁿⁱᵃᵇᶜᵈᵉᶠᵍʰʲᵏˡᵐᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ')
const SUB = scriptMap('0123456789+-−=()aehijklmnoprstuvx', '₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ')
const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
const FONTS: Record<string, string> = { mathbb: '𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ', mathcal: '𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵' }
const FN = '\u0000'

const script = (text: string, map: Map<string, string>, mark: string) => {
  const chars = Array.from(text)
  const values = new Set(map.values())
  if (chars.length > 0 && chars.every(c => map.has(c) || values.has(c))) return chars.map(c => map.get(c) ?? c).join('')
  return mark + (chars.length === 1 ? text : `(${text})`)
}
const atomic = (text: string) => /^√?[\p{L}\p{N}.,]+$/u.test(text) || Array.from(text).length === 1

const texUnicode = (tex: string): string => {
  let i = 0
  const name = () => {
    const m = /^[A-Za-z]+/.exec(tex.slice(i))
    if (m) return (i += m[0].length, m[0])
    return tex[i++] ?? ''
  }
  const arg = (): string => {
    while (tex[i] === ' ') i++
    if (tex[i] === '{') {
      let depth = 0
      const start = ++i
      for (; i < tex.length; i++) {
        if (tex[i] === '\\') i++
        else if (tex[i] === '{') depth++
        else if (tex[i] === '}' && depth-- === 0) break
      }
      return tex.slice(start, i++)
    }
    if (tex[i] === '\\') return (i++, `\\${name()}`)
    return tex[i++] ?? ''
  }
  const out: string[] = []
  const prev = () => out.join('').slice(-1)
  while (i < tex.length) {
    const c = tex[i++]!
    if (c === '\\') {
      const cmd = name()
      if (Object.hasOwn(SPACES, cmd)) out.push(SPACES[cmd]!)
      else if (cmd === 'frac' || cmd === 'dfrac' || cmd === 'tfrac') {
        const top = texUnicode(arg())
        const bottom = texUnicode(arg())
        const frac = `${atomic(top) ? top : `(${top})`}/${atomic(bottom) ? bottom : `(${bottom})`}`
        const loose = /^$|[\s(=,[]$/.test(prev()) && /^(\s|$|\\right|[)\],])/.test(tex.slice(i))
        out.push(loose ? frac : `(${frac})`)
      } else if (cmd === 'sqrt') {
        const inner = texUnicode(arg())
        out.push(`√${atomic(inner) ? inner : `(${inner})`}`)
      } else if (PLAIN.has(cmd)) out.push(cmd === 'text' ? arg() : texUnicode(arg()))
      else if (Object.hasOwn(FONTS, cmd)) out.push(Array.from(arg()).map(l => (LETTERS.includes(l) ? Array.from(FONTS[cmd]!)[LETTERS.indexOf(l)]! : l)).join(''))
      else if (cmd === 'left' || cmd === 'right' || cmd === 'big' || cmd === 'Big' || cmd === 'bigg') {
        const d = tex[i] === '\\' ? (i++, name()) : tex[i++] ?? ''
        out.push(d === '.' ? '' : d === '{' || d === '}' ? d : Object.hasOwn(TEX, d) ? TEX[d]! : d)
      } else if (FUNCTIONS.has(cmd)) out.push(cmd + FN)
      else out.push(Object.hasOwn(TEX, cmd) ? TEX[cmd]! : `\\${cmd}`)
    } else if (c === '^' || c === '_') out.push(script(texUnicode(arg()), c === '^' ? SUP : SUB, c))
    else if (c === '{') {
      i--
      out.push(texUnicode(arg()))
    } else if (c === '}' ) continue
    else if (c === '~' || c === '&') out.push(' ')
    else out.push(c)
  }
  return out.join('')
}

const isTex = (tex: string) => /[\\^_={}]/.test(tex) || /^[A-Za-z]$/.test(tex)

export const texParses = (tex: string): boolean => {
  if (tex.length > MAX_INLINE) return false
  let depth = 0
  for (let i = 0; i < tex.length; i++) {
    if (tex[i] === '\\') i++
    else if (tex[i] === '{' && ++depth > MAX_TEX_DEPTH) return false
    else if (tex[i] === '}' && --depth < 0) return false
  }
  return depth === 0
}

export const texText = (tex: string): string =>
  !texParses(tex) ? tex : texUnicode(tex)
    .replace(new RegExp(`${FN}(?=[\\p{L}\\p{N}])`, 'gu'), ' ')
    .replaceAll(FN, '')
    .replace(/\)\(/g, ')·(')
    .replace(/ {2,}/g, ' ')
    .trim()

export const inlineText = (inline: Inline[]): string =>
  inline.map(n => ('children' in n ? inlineText(n.children) : n.text)).join('')

const mathAt = (lines: string[], start: number, miss: { end: number }): { lines: string[]; end: number } | null => {
  const trimmed = (n: number) => (lines[n] ?? '').trim()
  const first = trimmed(start)
  if (start < miss.end || !first.startsWith('$$')) return null
  const open = first.slice(2)
  let end = start
  if (!(open.length >= 2 && open.endsWith('$$'))) {
    end = start + 1
    while (end < lines.length && !trimmed(end).endsWith('$$')) {
      if (trimmed(end) === '') return (miss.end = end, null)
      end++
    }
    if (end === lines.length) return (miss.end = end, null)
  }
  const body = end === start ? [open.slice(0, -2)] : [open, ...lines.slice(start + 1, end), trimmed(end).slice(0, -2)]
  const tex = body.filter(line => line.trim() !== '').map((line, i, all) => (i === 0 || i === all.length - 1 ? line.trim() : line))
  return tex.length ? { lines: tex, end } : null
}

export const displayText = (inline: Inline[]): string =>
  inline.map(n => (n.kind === 'link' && n.text !== n.href ? `${n.text} (${n.href})` : 'children' in n ? displayText(n.children) : n.text)).join('')

export const isWebLink = (href: string): boolean => /^(https?:|mailto:)/i.test(href)

const markOf = (n: number) => [...String(n)].map(d => SUPERSCRIPT[Number(d)]).join('')

const numberNotes = (blocks: Block[], defs: Map<string, string>, hl: Highlight): Block[] => {
  const order = new Map<string, number>()
  const seen = (nodes: Inline[]): void => nodes.forEach(n => {
    if (n.kind === 'footnote' && defs.has(n.text) && !order.has(n.text)) order.set(n.text, order.size + 1)
    else if ('children' in n) seen(n.children)
  })
  const fix = (nodes: Inline[]): Inline[] => nodes.map(n =>
    n.kind === 'footnote' ? (order.has(n.text) ? { kind: 'footnote', text: markOf(order.get(n.text)!), note: order.get(n.text)! } : { kind: 'text', text: `[^${n.text}]` })
    : 'children' in n ? { ...n, children: fix(n.children) } : n)
  const mapInlines = (b: Block, f: (nodes: Inline[]) => Inline[]): Block =>
    'inline' in b ? { ...b, inline: f(b.inline) }
    : b.kind === 'list' ? { ...b, items: b.items.map(it => ({ ...it, inline: f(it.inline), ...(it.blocks ? { blocks: it.blocks.map(c => mapInlines(c, f)) } : {}) })) }
    : b.kind === 'table' ? { ...b, header: b.header.map(f), rows: b.rows.map(r => r.map(f)) }
    : b.kind === 'quote' || b.kind === 'alert' ? { ...b, blocks: b.blocks.map(c => mapInlines(c, f)) }
    : b
  blocks.forEach(b => mapInlines(b, nodes => (seen(nodes), nodes)))
  for (const label of defs.keys()) if (!order.has(label)) order.set(label, order.size + 1)
  const out = blocks.map(b => mapInlines(b, fix))
  const notes = [...defs].sort(([a], [b]) => order.get(a)! - order.get(b)!).map(([label, text]) => ({ mark: markOf(order.get(label)!), inline: fix(parseInline(text, hl)), note: order.get(label)! }))
  return defs.size ? [...out, { kind: 'notes', notes, raw: '' }] : out
}

export const CONTROL = /\u001b\][^\u0007\u001b\n]{0,1024}(?:\u0007|\u001b\\)?|\u001b\[[0-?]*[ -/]*[@-~]|\u001b[@-_]?|[\u0000-\u0008\u000b-\u001f\u007f-\u009f]/g

const TINT_ON: Record<string, string> = { '2': 'dim', '3': 'italic', '90': 'gray', '36': 'cyan', '32': 'green', '33': 'yellow' }
const TINT_KEYS = Object.keys(TINT_ON)
const keepTints = (raw: string): string =>
  raw.replace(/\u001b\[(\d+)m/g, (m, code: string) =>
    code in TINT_ON ? `\uE000${String.fromCharCode(0xe100 + TINT_KEYS.indexOf(code))}` : code === '22' || code === '23' || code === '39' ? '\uE001' : m)
const TINTED = /\uE000([\uE100-\uE1FF])([^\uE000\uE001]*)\uE001?/g
const breakBefore = (line: string) => (line.trimStart().startsWith('\uE000') ? '\n' : ' ')
const joinLines = (lines: string[]) =>
  lines.map((l, i) => {
    const t = l.trim()
    if (i === lines.length - 1) return t
    return / {2,}$/.test(l) || t.endsWith('\\') ? `${t.replace(/\\$/, '')}\n` : `${t}${breakBefore(lines[i + 1]!)}`
  }).join('')
const dropTints = (text: string) => text.replace(/\uE000[\uE100-\uE1FF]?|\uE001/g, '')
const tinted = (text: string, hl: Highlight): Inline[] => {
  if (!text.includes('\uE000') && !text.includes('\uE001')) return decorate(text, hl)
  const out: Inline[] = []
  let at = 0
  for (const m of text.matchAll(TINTED)) {
    if (m.index > at) out.push(...decorate(dropTints(text.slice(at, m.index)), hl))
    if (m[2]) out.push({ kind: 'dim', text: m[2].replace(ROLE_MARKUP, '$1'), tint: TINT_ON[TINT_KEYS[m[1]!.charCodeAt(0) - 0xe100]!] })
    at = m.index + m[0].length
  }
  if (at < text.length) out.push(...decorate(dropTints(text.slice(at)), hl))
  return out
}

const untint = (b: Block): Block => {
  const raw = dropTints(b.raw)
  if (b.kind === 'code') return { ...b, raw, lines: b.lines.map(dropTints) }
  if (b.kind === 'quote' || b.kind === 'alert') return { ...b, raw, blocks: b.blocks.map(untint) }
  if (b.kind === 'list') return { ...b, raw, items: b.items.map(it => (it.blocks ? { ...it, blocks: it.blocks.map(untint) } : it)) }
  return { ...b, raw }
}

export const parse = (raw: string, hl: Highlight): Block[] => {
  const source = keepTints(raw).replace(CONTROL, '')
  const parsed = parseBlocks(source, hl)
  const blocks = /[\uE000\uE001]/.test(source) ? parsed.map(untint) : parsed
  return source.includes('[^') ? numberNotes(blocks, notesOf(source), hl) : blocks
}

const notesOf = (source: string, defs = new Map<string, string>(), depth = 0): Map<string, string> => {
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  let closer: RegExp | undefined
  let last: string | undefined
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!
    if (!closer && depth < MAX_QUOTE_DEPTH && QUOTE.test(line)) {
      const body: string[] = []
      while (i < lines.length && QUOTE.test(lines[i]!)) body.push(lines[i++]!.replace(/^\s*>\s?/, ''))
      i--
      notesOf(body.join('\n'), defs, depth + 1)
      last = undefined
      continue
    }
    const run = FENCE.exec(line)?.[1]
    const fenced = closer !== undefined || run !== undefined
    if (closer?.test(line)) closer = undefined
    else if (!closer && run) closer = closerOf(run)
    const def = fenced ? null : NOTE_DEF.exec(line)
    if (def) {
      last = def[1]!
      if (!defs.has(last)) defs.set(last, def[2] ?? '')
    } else if (last !== undefined && /^\s{2,}\S/.test(line)) defs.set(last, `${defs.get(last)} ${line.trim()}`)
    else last = undefined
  }
  return defs
}

const indentOf = (line: string): number => (line.match(/^\s*/)?.[0] ?? '').replace(/\t/g, '  ').length
const closerOf = (run: string) => new RegExp(`^\\s*\\${run[0]}{${run.length},}\\s*$`)

export const nestedBlocks = (blocks: Block[]): Block[] =>
  blocks.flatMap(b => [b, ...nestedBlocks(b.kind === 'list' ? b.items.flatMap(it => it.blocks ?? []) : b.kind === 'quote' || b.kind === 'alert' ? b.blocks : [])])

const tableRows = (lines: string[], width: number, hl: Highlight): Inline[][][] => {
  const end = lines.findIndex(l => !l.includes('|') || l.trim() === '')
  return lines.slice(0, end < 0 ? lines.length : end).map(l => {
    const cells = splitRow(l)
    return Array.from({ length: width }, (_, c) => parseCell(cells[c] ?? '', hl))
  })
}

type ListDraft = { items: ListItem[]; contentIndent: number[]; texts: string[][] }

const attachLine = (lines: string[], i: number, list: ListDraft, hl: Highlight, depth: number): number => {
  const at = (n: number) => lines[n] ?? ''
  const { items, contentIndent, texts } = list
  const indent = indentOf(at(i))
  let owner = items.length - 1
  while (owner > 0 && contentIndent[owner]! > indent) owner--
  const target = items[owner]!
  const fence = FENCE.exec(at(i))
  const last = target.blocks?.at(-1)
  if (fence) {
    const from = i
    const run = fence[1] ?? '```'
    const closer = closerOf(run)
    const strip = new RegExp(`^ {0,${indent}}`)
    const body: string[] = []
    i++
    while (i < lines.length && !closer.test(at(i)) && (at(i).trim() === '' || indentOf(at(i)) >= indent)) body.push(at(i++).replace(strip, ''))
    const isOpen = i === lines.length
    if (!isOpen && !closer.test(at(i))) {
      while (body.at(-1)?.trim() === '') body.pop()
      i--
    }
    target.blocks = [...(target.blocks ?? []), { kind: 'code', lang: fence[2] ?? '', lines: body, ...(isOpen ? { isOpen: true as const } : {}), raw: lines.slice(from, i + 1).join('\n') }]
  } else if (depth < MAX_QUOTE_DEPTH && QUOTE.test(at(i))) {
    const from = i
    while (QUOTE.test(at(i + 1)) && indentOf(at(i + 1)) >= 2) i++
    target.blocks = [...(target.blocks ?? []), ...parseBlocks(lines.slice(from, i + 1).join('\n'), hl, depth)]
  } else if (last?.kind === 'paragraph') {
    last.raw += `\n${at(i)}`
    last.inline = parseInline(joinLines(last.raw.split('\n')), hl)
  } else if (last) {
    target.blocks!.push({ kind: 'paragraph', inline: parseInline(at(i).trim(), hl), raw: at(i) })
  } else {
    texts[owner]!.push(at(i))
  }
  return i
}

const lineBlock = (line: string, hl: Highlight): Draft | null => {
  if (TAG_LINE.test(line)) return { kind: 'paragraph', inline: [{ kind: 'dim', text: line.trim() }] }
  const heading = /^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$/.exec(line)
  if (heading) return { kind: 'heading', level: (heading[1] ?? '#').length, inline: parseInline(heading[2] ?? '', hl) }
  return /^\s*([-*_])(\s*\1){2,}\s*$/.test(line) ? { kind: 'rule' } : null
}

const parseBlocks = (source: string, hl: Highlight, depth = 0): Block[] => {
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  const at = (n: number) => lines[n] ?? ''
  const blocks: Block[] = []
  const add = (block: Draft, from: number, to: number) => blocks.push({ ...block, raw: lines.slice(from, to).join('\n') } as Block)
  const mathMiss = { end: -1 }
  let paraStart = 0
  let para: string[] = []

  const flush = (end: number) => {
    if (para.length) add({ kind: 'paragraph', inline: parseInline(joinLines(para), hl) }, paraStart, end)
    para = []
  }

  for (let i = 0; i < lines.length; i++) {
    const line = at(i)
    const fence = FENCE.exec(line)
    if (fence) {
      flush(i)
      const start = i
      const run = fence[1] ?? '```'
      const closer = closerOf(run)
      const body: string[] = []
      i++
      while (i < lines.length && !closer.test(at(i))) body.push(at(i++))
      add({ kind: 'code', lang: fence[2] ?? '', lines: body, ...(i < lines.length ? {} : { isOpen: true as const }) }, start, i + 1)
      continue
    }
    const math = mathAt(lines, i, mathMiss)
    if (math) {
      flush(i)
      add({ kind: 'code', lang: 'math', lines: math.lines }, i, math.end + 1)
      i = math.end
      continue
    }
    if (line.trim() === '') {
      flush(i)
      continue
    }
    if (NOTE_DEF.test(line)) {
      flush(i)
      while (/^\s{2,}\S/.test(at(i + 1))) i++
      continue
    }
    if (para.length && SETEXT.test(line)) {
      add({ kind: 'heading', level: line.trim().startsWith('=') ? 1 : 2, inline: parseInline(joinLines(para), hl) }, paraStart, i + 1)
      para = []
      continue
    }
    const single = lineBlock(line, hl)
    if (single) {
      flush(i)
      add(single, i, i + 1)
      continue
    }
    if (line.includes('|') && i + 1 < lines.length && TABLE_SEP.test(at(i + 1))) {
      flush(i)
      const start = i
      const header = splitRow(line)
      const align = Array.from({ length: header.length }, (_, c) => {
        const sep = splitRow(at(i + 1))[c] ?? ''
        return (sep.startsWith(':') && sep.endsWith(':') ? 'center' : sep.endsWith(':') ? 'right' : 'left') as TableAlign
      })
      const rows = tableRows(lines.slice(i + 2), header.length, hl)
      i += 2 + rows.length
      add({ kind: 'table', header: header.map(c => parseCell(c, { numbers: false, paths: false })), align, rows }, start, i)
      i--
      continue
    }
    if (depth < MAX_QUOTE_DEPTH && QUOTE.test(line)) {
      flush(i)
      const start = i
      const body: string[] = []
      while (i < lines.length && QUOTE.test(at(i))) body.push(at(i++).replace(/^\s*>\s?/, ''))
      const alert = ALERT.exec(body[0] ?? '')
      const inner = (rows: string[]) => parseBlocks(rows.join('\n'), hl, depth + 1)
      if (alert) add({ kind: 'alert', level: alert[1]!.toLowerCase() as AlertLevel, blocks: inner([alert[2]!, ...body.slice(1)]) }, start, i)
      else {
        const quoted = inner(body)
        if (quoted.length) add({ kind: 'quote', blocks: quoted }, start, i)
      }
      i--
      continue
    }
    const item = LIST_ITEM.exec(line)
    if (item) {
      flush(i)
      const start = i
      const ordered = /\d/.test(item[2] ?? '')
      const items: ListItem[] = []
      const contentIndent: number[] = []
      const texts: string[][] = []
      while (i < lines.length) {
        const it = LIST_ITEM.exec(at(i))
        if (it) {
          const lead = indentOf(it[1] ?? '')
          contentIndent.push(lead + (it[2] ?? '').length + 1)
          const task = /^\[([ xX])\]\s+(.*)$/.exec(it[3] ?? '')
          texts.push([task ? task[2]! : it[3] ?? ''])
          items.push({ marker: it[2] ?? '-', depth: Math.floor(lead / 2), ...(task ? { task: task[1] !== ' ' } : {}), inline: parseInline(texts.at(-1)![0]!, hl) })
        } else if (/^\s{2,}\S/.test(at(i)) && items.length) {
          i = attachLine(lines, i, { items, contentIndent, texts }, hl, depth)
        } else {
          break
        }
        i++
      }
      texts.forEach((t, k) => { if (t.length > 1) items[k]!.inline = parseInline(joinLines(t), hl) })
      add({ kind: 'list', ordered, items }, start, i)
      i--
      continue
    }
    if (!para.length) paraStart = i
    para.push(line)
  }
  flush(lines.length)
  return blocks
}
