import { atom, read, update } from 'claude-code'
import type { EngineInterface, PluginOptions, PromptOrigin, Register, RenderElement, RenderSurface } from 'claude-code'

import { clockText, endedAt, promptKey, sentAt, withRecord } from './clock'
import type { Formula } from './latex'
import { LATEX_DPR, LATEX_FONT_PX, MAX_IMAGE_BYTES, fitImage, fitsImage, imageFile, imageOf, keepFormulas, mathOf, oldestOver, padFor, pickFormula, pngSize, ratexColor, renderedOf } from './latex'
import type { Block } from './markdown'
import { nestedBlocks, parse } from './markdown'
import type { ClipboardBackend, HelperCommand } from './clipboard'
import { clipboardCommand, drawsImages, imageCommand } from './clipboard'
import { FIGURE_HINT } from './figure'
import { drawDiagrams } from './mermaid'
import type { CopyButton, DrawPaste, Fold, Hues, TerminalEnv } from './render'
import { MARK, bashEdits, lineCount, drawMath, drawsHyperlinks, editNotes, fileRoot, hasShellOutput, instanceKey, isReadOnlyCall, leftToEngine, markerRoom, mirrored, noteTip, pasteLang, pathsToProbe, toolPathsToProbe, remember, rememberCall, renderBashEdits, renderBlocks, renderDiffCard, renderExpandedShell, renderFailure, renderReply, renderShellResult, renderToolGroup, renderToolRow, renderTurnDuration, renderUserPrompt, replyRoom, replyStyleFor, takesClickableMarks, takesEditorLinks, takesHttpLinks, takesMonoText, withoutBashEdits } from './render'
import type { SetupStep } from './help'
import { ESSENTIAL_STEPS, HINT, ISSUE_HINT, NARROW_PANE, narrowHint, SETUP_DONE, SETUP_ESSENTIALS_DONE, SETUP_MORE, SETUP_PANE_KEYS, SETUP_PANE_OPENED, THEME_PREVIEW, findSetup, helpText, languageShowcase, rtlShowcaseText, setupParts, setupSteps, setupText, showcaseText } from './help'
import { PRESET_NAMES } from './presets'
import { textRows } from './layout'
import type { Style } from './theme'
import { RANDOM_THEMES, pickTheme, resolveStyle } from './theme'
import { DEFAULT_COLUMNS, MIN_COLUMNS } from './layout'
import type { Terminal } from './rtl'
import { ROW_MARK_TEXT, TERMINALS, hasRtl, opensLatin } from './rtl'

const HINTED_ORIGINS = ['composer', 'bridge', 'plugin'] as const satisfies readonly PromptOrigin['kind'][]

const takesHint = (origin: PromptOrigin): boolean => HINTED_ORIGINS.some(kind => kind === origin.kind)

const drawsWhereAsked = async ($: EngineInterface, origin: PromptOrigin, drawn: RenderSurface[]): Promise<boolean> => {
  const all = await $.session.surfaces()
  const asked = all.filter(s => (s === 'terminal') === (origin.kind === 'composer'))
  return !all.length || (asked.length ? asked : all).some(s => drawn.includes(s))
}

const LATEX_HINT = 'This terminal typesets LaTeX math: a formula in $$…$$ on lines of its own, or in a ```math block, renders as an image (KaTeX syntax). Inline $…$ does not render, so write inline math as plain text or Unicode.'

const detectTerminal = async ($: EngineInterface): Promise<Terminal | null> => {
  const program = await $.env.get('TERM_PROGRAM')
  const term = await $.env.get('TERM')
  if ((await $.env.get('KITTY_WINDOW_ID')) || term === 'xterm-kitty') return 'kitty'
  if (program === 'Apple_Terminal') return 'apple-terminal'
  if (program === 'WarpTerminal') return 'warp'
  if (program === 'ghostty') return 'ghostty'
  if (program === 'WezTerm') return 'wezterm'
  if (program === 'vscode') return 'vscode'
  if (program === 'iTerm.app') return 'iterm'
  if (term === 'alacritty' || (await $.env.get('ALACRITTY_WINDOW_ID'))) return 'alacritty'
  if (await $.env.get('WT_SESSION')) return 'windows-terminal'
  if (await $.env.get('VTE_VERSION')) return 'gnome'
  if (await $.env.get('KONSOLE_VERSION')) return 'konsole'
  return null
}

const applyRtl = async ($: EngineInterface, style: Style): Promise<Terminal | null> => {
  if (style.rtl === 'off') return null
  if (style.rtl !== 'auto') return style.rtl
  const terminal = await detectTerminal($)
  style.reorder = terminal !== null
  if (terminal) style.shape = TERMINALS[terminal]
  return terminal
}

const expandedCalls = new Set<string>()
const readOnlyCalls = new Set<string>()

const DESKTOP_ROOM = 0.84

const columnsOf = (viewport: { columns?: number } | undefined, style: Pick<Style, 'monoFace'>) => {
  const reported = viewport?.columns ?? DEFAULT_COLUMNS
  return Math.max(MIN_COLUMNS, (style.monoFace ? Math.floor(reported * DESKTOP_ROOM) : reported) - 4)
}

const formulas = atom({ plugin: 'prismantis', key: 'formulas' } as const, {})
const latexDir = atom({ plugin: 'prismantis', key: 'dir' } as const, '')
const unfolded = atom({ plugin: 'prismantis', key: 'unfolded' } as const, [] as string[])
const sent = atom({ plugin: 'prismantis', key: 'sent' } as const, [])
const turnEnds = atom({ plugin: 'prismantis', key: 'turnEnds' } as const, [])
const setupAt = atom({ plugin: 'prismantis', key: 'setupAt' } as const, 0)
const setupFocus = atom({ plugin: 'prismantis', key: 'setupFocus' } as const, '')
const setupLand = atom({ plugin: 'prismantis', key: 'setupLand' } as const, '')
const foundPaths = atom({ plugin: 'prismantis', key: 'foundPaths' } as const, [])
const awaiting = atom({ plugin: 'prismantis', key: 'awaiting' } as const, [] as { key: string; at: number }[])
const blink = atom({ plugin: 'prismantis', key: 'blink' } as const, false)
const BLINK_MS = 500
const HELD_TURNS = 2
type Blinker = { timer?: ReturnType<EngineInterface['clock']['every']>; tools: number; ready: Set<string>; held: Map<string, number> }
const stopBlink = (blinker: Blinker) => {
  blinker.timer?.cancel()
  blinker.timer = undefined
}
const darkDot = async ($: EngineInterface, style: Style, running: boolean): Promise<boolean> =>
  style.runningDot === 'blink' && running && (await read($, blink))

const unreadLook = async ($: EngineInterface, style: Style, shown: Style, text: string, requestId: string): Promise<Style> => {
  if (!style.unreadPrompts) return shown
  const drawnAt = await firstDrawn($, requestId)
  const entry = (await read($, awaiting)).find(a => a.key === promptKey(text))
  if (!entry || drawnAt < entry.at) return shown
  const ink = (await read($, blink)) ? shown.theme.rule : shown.theme.codeComment
  return { ...shown, theme: { ...shown.theme, heading: ink, accent: ink, promptText: ink } }
}

const markUnread = async ($: EngineInterface, style: Style, e: { text: string; command?: unknown; wait?: boolean; turnId?: string; origin: { kind: string } }, blinker: Blinker) => {
  if (!style.unreadPrompts || style.promptStyle === 'off' || e.command || (e.origin.kind !== 'composer' && e.origin.kind !== 'bridge')) return
  const key = promptKey(e.text)
  if (e.wait && e.turnId !== undefined) blinker.held.set(key, 0)
  else blinker.ready.add(key)
  const at = await $.clock.now()
  await persist($, () => update($, awaiting, list => [...list.filter(a => a.key !== key), { key, at }].slice(-20)))
  await keepBlinking($, blinker)
}

const startTurn = (blinker: Blinker, key: string) => {
  for (const [k, turns] of blinker.held) {
    if (k === key) blinker.ready.add(k)
    if (k === key || turns + 1 >= HELD_TURNS) blinker.held.delete(k)
    else blinker.held.set(k, turns + 1)
  }
}

const markRead = async ($: EngineInterface, asked: string[], blinker: Blinker) => {
  for (const key of asked) blinker.ready.delete(key)
  const list = await read($, awaiting)
  const left = list.filter(a => blinker.ready.has(a.key) || blinker.held.has(a.key))
  if (left.length !== list.length) await persist($, () => update($, awaiting, () => left))
  await keepBlinking($, blinker)
}

const groupRunning = (props: { isActive: boolean; calls: readonly { isRunning: boolean }[] }): boolean => props.isActive && props.calls.some(c => c.isRunning)

const keepBlinking = async ($: EngineInterface, blinker: Blinker) => {
  const waiting = (await read($, awaiting)).length > 0 || blinker.tools > 0
  if (waiting && !blinker.timer) blinker.timer = $.clock.every(BLINK_MS, () => void update($, blink, lit => !lit).catch(() => undefined))
  if (!waiting && blinker.timer) {
    stopBlink(blinker)
    await persist($, () => update($, blink, () => false))
  }
}

const WRITE_TRIES = 20
const WRITE_RETRY_MS = 50

const persist = async ($: EngineInterface, write: () => Promise<unknown>): Promise<void> => {
  for (let tries = WRITE_TRIES; ; tries--) {
    try {
      await write()
      return
    } catch (error) {
      if (tries <= 1) throw error
    }
    await $.clock.sleep(WRITE_RETRY_MS)
  }
}

const firstDrawn = async ($: EngineInterface, id: string): Promise<number> => {
  const ref = { plugin: 'prismantis', key: 'drawn', id } as const
  const { value } = await $.state.get(ref)
  if (value !== undefined) return value
  const now = await $.clock.now()
  $.clock.after(0, () => void persist($, () => $.state.set(ref, now, { ifVersion: 0 })).catch(() => undefined))
  return now
}

type Typeset = Exclude<Formula, { error: true }> & { tex: string }

const showsImages = async ($: EngineInterface): Promise<boolean> => {
  if (await $.env.get('CLAUDE_CODE_FORCE_TERMINAL_IMAGES')) return true
  if (await $.env.get('TMUX')) return false
  const terminal = await detectTerminal($)
  return terminal === 'kitty' || terminal === 'ghostty'
}

type Latex = { command: string; dir: string }
type LatexSession = { style: Style; color: string; pending: Set<string>; wanted: Set<string>; batch: string[]; engine?: Promise<Latex | null>; ready?: Latex | null; stopped?: boolean; queue: Promise<void> }

const formulaKey = (color: string, tex: string) => `${color}\0${tex}`

const typeset = async ($: EngineInterface, color: string, engine: Latex, texs: string[], fontSize = LATEX_FONT_PX, dpr = LATEX_DPR): Promise<Formula[]> => {
  const { stdout } = await $.process.run(
    [engine.command, '--output-dir', engine.dir, '--color', color, '--background-color', 'transparent', '--font-size', String(fontSize), '--dpr', String(dpr)],
    { stdin: `${texs.join('\n')}\n`, timeoutMs: 2000 },
  )
  const rendered = renderedOf(stdout)
  return fewAtOnce(texs.map((_, i) => () => (rendered.has(i + 1) ? readFormula($, `${engine.dir}/${String(i + 1).padStart(4, '0')}.png`) : Promise.resolve<Formula>({ error: true }))))
}

const fewAtOnce = async <T,>(jobs: (() => Promise<T>)[], width = 4): Promise<T[]> => {
  const done: T[] = []
  let next = 0
  const worker = async () => {
    while (next < jobs.length) {
      const i = next++
      done[i] = await jobs[i]!()
    }
  }
  await Promise.all(Array.from({ length: Math.min(width, jobs.length) }, worker))
  return done
}

const readFormula = async ($: EngineInterface, path: string): Promise<Formula> => {
  const stat = await $.fs.stat(path).catch(() => null)
  if (stat?.kind !== 'file' || stat.size > MAX_IMAGE_BYTES) return { error: true }
  const png = await $.fs.read(path, { as: 'bytes' }).then(r => r.base64, () => '')
  const size = png ? pngSize(png) : null
  return size && fitsImage(png) ? { png, ...size } : { error: true }
}

const withPadding = async ($: EngineInterface, color: string, engine: Latex, texs: string[], results: Formula[]): Promise<Formula[]> => {
  const padded: Formula[] = []
  for (const [i, result] of results.entries()) {
    const pad = 'png' in result ? padFor(result) : null
    const [again] = pad ? await typeset($, color, engine, [texs[i]!], pad.fontSize, pad.dpr).catch((): Formula[] => []) : []
    padded.push(again && 'png' in again && 'png' in result ? { ...result, padded: again } : result)
  }
  return padded
}

const startLatex = async ($: EngineInterface, latex: LatexSession): Promise<Latex | null> => {
  if (!latex.style.latex || !(await $.session.surfaces()).includes('terminal') || !(await showsImages($))) return null
  const tmp = (await $.env.get('TMPDIR')) ?? (await $.env.get('TEMP')) ?? '/tmp'
  const suffix = (await read($, latexDir)) || crypto.randomUUID()
  await persist($, () => update($, latexDir, () => suffix))
  const engine = { command: 'ratex-render', dir: `${tmp.replace(/[\\/]+$/, '')}/prismantis-latex-${await $.session.id()}-${suffix}` }
  const [check] = await typeset($, latex.color, engine, ['x^2'])
  return check && 'png' in check ? engine : null
}

const latexEngine = ($: EngineInterface, latex: LatexSession): Promise<Latex | null> =>
  (latex.engine ??= startLatex($, latex)
    .catch(() => null)
    .then(engine => {
      latex.ready = engine
      if (engine) $.ui.invalidate('ui.render')
      return engine
    }))

const stopLatex = (latex: LatexSession) => {
  latex.stopped = true
  latex.pending.clear()
  latex.batch = []
}

const typesetLater = async ($: EngineInterface, latex: LatexSession, texs: string[]): Promise<void> => {
  const color = latex.color
  const engine = await latexEngine($, latex)
  if (!engine || latex.stopped) return
  const results = await typeset($, color, engine, texs).then(
    done => withPadding($, color, engine, texs, done),
    () => null,
  )
  if (!results) return stopLatex(latex)
  const fresh = texs.map((tex, i) => [formulaKey(color, tex), results[i]!] as const)
  await persist($, () => update($, formulas, store => keepFormulas(store, fresh, latex.wanted)))
  latex.wanted.clear()
  for (const tex of texs) latex.pending.delete(formulaKey(color, tex))
}

const mathOfBlocks = async ($: EngineInterface, latex: LatexSession, surface: string, blocks: Block[]): Promise<Map<number, Typeset>> => {
  const maths = [...blocks.entries()].flatMap(([i, block]) => {
    const tex = mathOf(block)
    return tex === null ? [] : [{ i, tex, key: formulaKey(latex.color, tex) }]
  })
  if (surface !== 'terminal' || maths.length === 0) return new Map()
  void latexEngine($, latex)
  if (!latex.ready) return new Map()
  for (const { key } of maths) latex.wanted.add(key)
  const store = (await read($, formulas)) as Record<string, Formula>
  const missing = latex.stopped ? [] : [...new Map(maths.map(({ key, tex }) => [key, tex]))].filter(([key]) => !store[key] && !latex.pending.has(key))
  if (missing.length) {
    if (latex.batch.length === 0) {
      $.clock.after(0, () => {
        const texs = latex.batch
        latex.batch = []
        latex.queue = latex.queue.then(() => typesetLater($, latex, texs)).catch(() => stopLatex(latex))
      })
    }
    for (const [key, tex] of missing) {
      latex.pending.add(key)
      latex.batch.push(tex)
    }
  }
  return new Map(maths.flatMap(({ i, tex, key }) => {
    const formula = store[key]
    return formula && 'png' in formula ? [[i, { tex, ...formula }] as const] : []
  }))
}

type Picture = { png: string; width: number; height: number; alt: string }

const pictureOf = async ($: EngineInterface, src: string, home: string): Promise<Omit<Picture, 'alt'> | null> => {
  const file = imageFile(src, home)
  if (!file) return null
  const stat = 'path' in file ? await $.fs.stat(file.path).catch(() => null) : null
  if ('path' in file && (stat?.kind !== 'file' || stat.size > MAX_IMAGE_BYTES)) return null
  const png = 'png' in file ? file.png : await $.fs.read(file.path, { as: 'bytes' }).then(r => r.base64, () => '')
  const size = png ? pngSize(png) : null
  return size && size.width > 0 && size.height > 0 && fitsImage(png) ? { png, ...size } : null
}

const loaded = new Map<string, { picture: Promise<Omit<Picture, 'alt'> | null>; bytes: number }>()

const loadPicture = ($: EngineInterface, src: string, home: string) => remember(loaded, src, () => {
  const entry = { picture: pictureOf($, src, home), bytes: 0 }
  void entry.picture.then(picture => {
    entry.bytes = src.length + (picture ? (picture.png.length * 3) / 4 : 0)
    for (const old of oldestOver(loaded, (_, e) => e.bytes)) loaded.delete(old)
  })
  return entry
}, Infinity).picture

const imagesOn = async ($: EngineInterface, probes: Probes, surface: RenderSurface): Promise<boolean> => surface === 'terminal' && (await (probes.images ??= showsImages($).catch(() => false)))

const picturesOf = async ($: EngineInterface, style: Style, probes: Probes, surface: RenderSurface, blocks: Block[]): Promise<Map<number, Picture>> => {
  const images = [...blocks.entries()].flatMap(([i, block]) => {
    const image = imageOf(block)
    return image ? [{ i, ...image }] : []
  })
  if (images.length === 0 || !(await imagesOn($, probes, surface))) return new Map()
  await locate($, style)
  const found = await Promise.all(images.map(async ({ i, alt, src }) => {
    const picture = await loadPicture($, src, style.home)
    return picture ? [[i, { ...picture, alt }] as const] : []
  }))
  return new Map(found.flat())
}

const locate = async ($: EngineInterface, style: Style) => {
  style.cwd = await $.session.root().catch(() => style.cwd)
  style.home ||= (await $.env.get('HOME').catch(() => undefined)) ?? (await $.env.get('USERPROFILE').catch(() => undefined)) ?? ''
}

const htmlBackend = async ($: EngineInterface): Promise<ClipboardBackend | null> => {
  if (await $.env.get('SSH_CONNECTION') || await $.env.get('SSH_TTY')) return null
  if (await $.env.get('OS') === 'Windows_NT') return 'windows'
  const helper = await $.fs.stat('/usr/bin/osascript').catch(() => null)
  if (helper?.kind === 'file') return 'macos'
  return await $.env.get('WAYLAND_DISPLAY') || await $.env.get('DISPLAY') ? 'linux' : null
}

type LinkReach = { http: boolean; editor: boolean; marks: boolean; monoText: boolean; files: string | null; paths: boolean; hyperlinks: boolean }

type Probes = { terminal?: Promise<Terminal | null>; multiplexed?: Promise<boolean>; htmlCopy?: Promise<ClipboardBackend | null>; links?: Promise<LinkReach>; images?: Promise<boolean> }

const terminalEnv = async ($: EngineInterface): Promise<TerminalEnv> => ({
  FORCE_HYPERLINK: await $.env.get('FORCE_HYPERLINK'),
  TERM_PROGRAM: await $.env.get('TERM_PROGRAM'),
  TERM_PROGRAM_VERSION: await $.env.get('TERM_PROGRAM_VERSION'),
  TERM: await $.env.get('TERM'),
  WT_SESSION: await $.env.get('WT_SESSION'),
  LC_TERMINAL: await $.env.get('LC_TERMINAL'),
  VTE_VERSION: await $.env.get('VTE_VERSION'),
  TERMINAL_EMULATOR: await $.env.get('TERMINAL_EMULATOR'),
})

const overSsh = async ($: EngineInterface): Promise<boolean> => Boolean(await $.env.get('SSH_CONNECTION') || await $.env.get('SSH_TTY'))

const fileRootOf = async ($: EngineInterface): Promise<string> => {
  const distro = await $.env.get('WSL_DISTRO_NAME')
  const linuxTerminal = distro !== undefined && Boolean(await $.env.get('VTE_VERSION') || await $.env.get('KONSOLE_VERSION') || await $.env.get('KITTY_WINDOW_ID'))
  return fileRoot(linuxTerminal ? undefined : distro)
}

const readLinkReach = async ($: EngineInterface, style: Style): Promise<LinkReach> => {
  const base = await $.session.version().then(v => v.base, () => undefined)
  const http = takesHttpLinks(base)
  if (http) await locate($, style)
  const files = http && !(await overSsh($).catch(() => true)) ? await fileRootOf($).catch(() => 'file://') : null
  const hyperlinks = drawsHyperlinks(await terminalEnv($).catch(() => ({})))
  return { http, editor: takesEditorLinks(base), marks: takesClickableMarks(base), monoText: takesMonoText(base), files, paths: files !== null && hyperlinks, hyperlinks }
}

const linkReach = ($: EngineInterface, probes: Probes, style: Style): Promise<LinkReach> => (probes.links ??= readLinkReach($, style))

type PathChecks = { asked: Set<string>; batch: string[]; list?: readonly string[]; found: ReadonlySet<string> }

const MAX_FOUND = 2000

const MAX_BATCH = 200

const MAX_ASKED = 5000

const WRITE_TOOLS = new Set(['Write', 'Edit', 'MultiEdit', 'NotebookEdit'])

const writtenPath = (call: Record<string, unknown>): string | undefined => {
  const path = call.file_path ?? call.notebook_path
  return WRITE_TOOLS.has(String(call.tool)) && typeof path === 'string' ? path.replace(/\\/g, '/') : undefined
}

const forgetMisses = (checks: PathChecks, call: Record<string, unknown>) => {
  if (checks.asked.size < MAX_ASKED && isReadOnlyCall(String(call.tool), call)) return
  const path = checks.asked.size < MAX_ASKED ? writtenPath(call) : undefined
  if (path === undefined) checks.asked = new Set(checks.found)
  else for (let at = path; at.includes('/'); at = at.slice(0, at.lastIndexOf('/'))) checks.asked.delete(at)
}

const statPaths = async ($: EngineInterface, paths: string[]): Promise<void> => {
  const kinds = await Promise.all(paths.map(path => $.fs.stat(path).then(stat => stat.kind, () => 'other')))
  const hits = paths.flatMap((path, i) => (kinds[i] === 'dir' ? [path, `${path}/`] : kinds[i] === 'file' ? [path] : []))
  if (hits.length) await persist($, () => update($, foundPaths, list => [...list, ...hits].slice(-MAX_FOUND)))
}

const askPaths = ($: EngineInterface, checks: PathChecks, paths: string[]) => {
  for (const path of paths) {
    if (checks.asked.has(path)) continue
    if (checks.batch.length >= MAX_BATCH) return
    if (checks.batch.length === 0) {
      $.clock.after(0, () => {
        const batch = checks.batch
        checks.batch = []
        void statPaths($, batch).catch(() => undefined)
      })
    }
    checks.asked.add(path)
    checks.batch.push(path)
  }
}

const withFoundPaths = async ($: EngineInterface, checks: PathChecks, style: Style, blocks: Block[]): Promise<Style> => withFound($, checks, style, pathsToProbe(blocks, style))

const withFound = async ($: EngineInterface, checks: PathChecks, style: Style, paths: string[]): Promise<Style> => {
  if (paths.length === 0) return style
  askPaths($, checks, paths)
  const list = await read($, foundPaths)
  if (list !== checks.list) {
    checks.list = list
    checks.found = new Set(list)
  }
  return { ...style, found: checks.found }
}

const fileCard = async ($: EngineInterface, el: ReturnType<EngineInterface['ui']['resolve']>, output: unknown, id: string, style: Style, probes: Probes, drawn: () => Style, columns?: number): Promise<RenderElement | undefined> => {
  const press = (await linkReach($, probes, style)).marks
  if (leftToEngine(output, press)) return undefined
  await locate($, style)
  return renderDiffCard(el, drawn(), output, folder($, el, await read($, unfolded), press, style.folds === 'open'), id, columns)
}

const multiplexed = async ($: EngineInterface): Promise<boolean> => Boolean(await $.env.get('TMUX') || await $.env.get('STY') || await $.env.get('ZELLIJ'))

const probe = async ($: EngineInterface, style: Style, probes: Probes): Promise<Terminal | null> => {
  probes.terminal ??= applyRtl($, style)
  const terminal = await probes.terminal
  probes.htmlCopy ??= htmlBackend($)
  probes.multiplexed ??= multiplexed($).catch(() => false)
  const { htmlCopy, smallDot } = style
  style.htmlCopy = await probes.htmlCopy
  style.smallDot = await probes.multiplexed
  if (style.htmlCopy !== htmlCopy || style.smallDot !== smallDot) $.ui.invalidate('ui.render')
  return terminal
}

const runHelper = async ($: EngineInterface, backend: ClipboardBackend, build: (systemRoot?: string) => HelperCommand): Promise<string | null> => {
  const systemRoot = backend === 'windows' ? await $.env.get('SystemRoot') : undefined
  const command = build(systemRoot)
  if (backend === 'windows' && !systemRoot) return command.failure
  const result = await $.process.run(command.argv, { stdin: command.stdin, timeoutMs: Math.min(30000, (backend === 'windows' ? 15000 : 5000) + Math.ceil(command.stdin.length / 100)) }).catch(() => null)
  if (!result) return command.failure
  return result.exitCode === 0 ? null : result.stderr.trim() || command.failure
}

const richCommand = (style: Style, backend: ClipboardBackend, content: string, rich: (() => string) | 'png', hues?: Hues) => (systemRoot?: string): HelperCommand => rich === 'png'
  ? imageCommand(backend, content, { foreground: style.theme.diagramText ?? style.theme.codeText, background: style.theme.pngBackground, themeBackground: style.background }, systemRoot, hues)
  : clipboardCommand(backend, rich(), content, systemRoot)

const offers = (style: Style, rich?: (() => string) | 'png'): boolean => !rich || (rich === 'png' ? drawsImages(style.htmlCopy) : !!style.htmlCopy)

const folder = ($: EngineInterface, el: ReturnType<EngineInterface['ui']['resolve']>, open?: string[], faces = false, startOpen = false): Fold => (id, hidden, key, look) => {
  if (!open) return null
  const toggled = open.includes(id)
  const folded = startOpen ? toggled : !toggled
  const label = folded ? look?.label ?? `+${hidden} more lines` : 'show less'
  const toggle = () => update($, unfolded, ids => (toggled ? ids.filter(x => x !== id) : [...ids, id].slice(-500)))
  if (!faces) return { folded, faced: false, element: <el.Button key={key} variant="secondary" label={label} onPress={toggle} /> }
  const element = look?.face ? <el.Button key={key} plain label={label} onPress={toggle}>{look.face(folded)}</el.Button> : <el.Button key={key} variant="secondary" label={label} onPress={toggle} />
  return { folded, faced: look?.face !== undefined, element, around: (rows, hover) => <el.Button key={`${key}.rows`} plain label={label} hover={hover} onPress={toggle}>{rows}</el.Button> }
}

const copies = { last: 0, pending: 0, queue: Promise.resolve() as Promise<unknown> }

const lastCopy = (run: () => Promise<string>): Promise<string | null> => {
  const turn = ++copies.last
  const done = copies.pending ? copies.queue.then(() => (turn === copies.last ? run() : null)) : run()
  copies.pending++
  copies.queue = done.catch(() => null).finally(() => copies.pending--)
  return done
}

const copyNow = async ($: EngineInterface, style: Style, content: string, surface: RenderSurface, rich?: (() => string) | 'png', hues?: Hues): Promise<string> => {
  const backend = style.htmlCopy
  const failure = rich && backend ? await runHelper($, backend, richCommand(style, backend, content, rich, hues)) : undefined
  if (failure === null) return rich === 'png' ? 'Copied as image' : 'Copied formatted table'
  const result = await $.ui.copy({ text: content, surface })
  if (!result.isCopied) return `Copy failed: ${result.reason}`
  return failure ? `Copied as plain text (${failure})` : 'Copied'
}

const drawMarkdown = ($: EngineInterface, el: ReturnType<EngineInterface['ui']['resolve']>, style: Style, blocks: ReturnType<typeof parse>, columns: number, math: Map<number, Typeset> = new Map(), pictures: Map<number, Picture> = new Map(), reply?: string, open?: string[], notes?: { id: string; press: boolean }): RenderElement[] => {
  const { Button } = el
  const copy = (text: string | (() => string), key: string, label = '⧉ copy', rich?: (() => string) | 'png', hues?: () => Hues) => {
    const copied = (surface: RenderSurface) => lastCopy(() => copyNow($, style, typeof text === 'function' ? text() : text, surface, rich, hues?.()))
    return style.copyButtons && offers(style, rich) ? (
      <Button
        key={key}
        {...(style.copyButtonStyle === 'dim' ? { plain: true as const, dimColor: true } : { variant: 'primary' as const })}
        label={label}
        onPress={async press => {
          const said = await copied(press.surface).catch(() => 'Copy failed')
          if (said) $.ui.toast(said)
        }}
      />
    ) : null
  }
  const drawn = drawDiagrams(el, style, blocks, columns - markerRoom(style))
  const Image = 'Image' in el ? el.Image : null
  if (Image) {
    for (const [i, formula] of math) {
      const picked = pickFormula(formula, columns)
      if (picked) drawn.set(i, { element: <Image key={`b${i}`} source={{ png: picked.picture.png }} columns={picked.fit.columns} rows={picked.fit.rows} alt={formula.tex} /> })
    }
    for (const [i, picture] of pictures) {
      const fit = fitImage(picture, columns)
      drawn.set(i, { element: <Image key={`b${i}`} source={{ png: picture.png }} columns={fit.columns} rows={fit.rows} alt={picture.alt} /> })
    }
  }
  const tip = notes?.press ? noteTip(blocks, text => void $.ui.toast(text)) : undefined
  const elements = renderBlocks(el, notes ? { ...style, noteKey: instanceKey(notes.id) } : style, blocks, columns, drawMath(el, style, blocks, drawn), copy, folder($, el, open, false, style.folds === 'open'), tip)
  const button = reply === undefined ? null : copy(reply, 'reply', '⧉ copy reply')
  if (!button) return elements
  return [...elements, style.copyButtonStyle === 'hover' ? replyMarker(el, button, notes?.id) : <el.Box key="reply" alignSelf="flex-end">{button}</el.Box>]
}

const replyMarker = (el: ReturnType<EngineInterface['ui']['resolve']>, button: RenderElement, id?: string) => {
  const scope = `copy:${id === undefined ? '' : instanceKey(id)}:reply`
  return (
    <el.Box key="reply" position="absolute" bottom={0} right={-MARK} hover={{ scope }}>
      <el.Text dimColor>⧉</el.Text>
      <el.Box position="absolute" top={0} right={0} display="none" hover={{ scope, display: 'flex' }}>{button}</el.Box>
    </el.Box>
  )
}

const THEME_ARGS = [...PRESET_NAMES, 'random']

type Picked = { theme: string; options: PluginOptions; latex: LatexSession }

const expandedRow = (props: object): boolean => 'isExpanded' in props && props.isExpanded === true

const setOption = ($: EngineInterface, key: SetupStep['key'], value: string) => $.config.set({ key: `prismantis.${key}`, value })

const saveOption = ($: EngineInterface, key: SetupStep['key'], value: string): Promise<string | undefined> =>
  setOption($, key, value).then(
    r => r.deny,
    (e: unknown) => `${e instanceof Error ? e.message : String(e)}. Set "${key}": "${value}" by hand in the ${$.plugin.name} options under pluginConfigs in ~/.claude/settings.json, then restart.`,
  )

const setTheme = async ($: EngineInterface, picked: Picked, name: string): Promise<string> => {
  const deny = await saveOption($, 'theme', name)
  if (deny) return `Could not switch theme: ${deny}`
  if (name !== 'random' || picked.options.theme !== 'random') return `Theme set to ${name}.`
  const others = RANDOM_THEMES.filter(t => t !== picked.theme)
  picked.theme = others[Math.floor(Math.random() * others.length)]!
  const style = picked.latex.style
  style.theme = resolveStyle({ ...picked.options, theme: picked.theme }).theme
  picked.latex.color = ratexColor(style.theme.diagramText ?? style.theme.codeText ?? '#808080')
  $.ui.invalidate('ui.render')
  return `Theme set to random: ${picked.theme} for now.\nkeep it: /prismantis theme ${picked.theme}`
}

const saveSetupPick = async ($: EngineInterface, picked: Picked, step: SetupStep, value: string): Promise<string> =>
  step.key === 'theme' ? setTheme($, picked, value) : saveOption($, step.key, value).then(deny => (deny ? `Could not save ${step.key}: ${deny}` : `${step.title} set to ${value}.`))

const SETUP_PANE = 'prismantis-setup'

const SETUP_PICK = 'pick:'
const SETUP_LIST_COLUMNS = 30
const SETUP_HEAD_ROWS = 5

const openPane = ($: EngineInterface) => $.ui.open({ id: SETUP_PANE, title: 'prismantis setup', focus: true, closeOnEscape: true, rows: 40, columns: 90 })

const openSetupPane = async ($: EngineInterface, at: number): Promise<string | undefined> => {
  await update($, setupAt, () => at)
  await update($, setupFocus, () => '')
  await update($, setupLand, () => '')
  const opened = await openPane($)
  if (opened.isPlaced) return SETUP_PANE_OPENED
  await $.ui.close({ id: SETUP_PANE })
  return undefined
}

const pickKey = (step: SetupStep, value: string) => `${SETUP_PICK}${step.name}:${value}`

const showSetupStep = async ($: EngineInterface, at: number, step: SetupStep, value: string): Promise<void> => {
  await update($, setupFocus, () => value)
  await update($, setupLand, () => pickKey(step, value))
  await update($, setupAt, () => at)
}

const pickInPane = async ($: EngineInterface, picked: Picked, at: number, value: string, currentOf: (step: SetupStep) => string): Promise<void> => {
  const steps = setupSteps(PRESET_NAMES)
  const step = steps[at]!
  const nextStep = at + 1 === ESSENTIAL_STEPS ? undefined : steps[at + 1]
  const done = `${step.title} set to ${value}.`
  if (nextStep) await showSetupStep($, at + 1, nextStep, currentOf(nextStep))
  else await $.ui.close({ id: SETUP_PANE })
  $.ui.toast(nextStep ? done : `${done} ${at + 1 === ESSENTIAL_STEPS ? SETUP_ESSENTIALS_DONE : 'Setup done.'}`)
  const saved = await saveSetupPick($, picked, step, value)
  if (saved === done) return
  $.ui.toast(saved)
  if (!saved.startsWith('Could not')) return
  await showSetupStep($, at, step, value)
  if (!nextStep) await openPane($)
}

const landSetupFocus = ($: EngineInterface, key: string): void => {
  $.clock.after(0, async () => {
    await $.ui.focus({ requestId: SETUP_PANE, key }).catch(() => undefined)
    await update($, setupLand, land => (land === key ? '' : land))
  })
}

const setupStart = (steps: SetupStep[], stepName?: string): number => (stepName === SETUP_MORE ? ESSENTIAL_STEPS : stepName ? steps.findIndex(s => s.name === stepName) : 0)

const afterSetupPick = (steps: SetupStep[], at: number): string => {
  if (at + 1 === ESSENTIAL_STEPS) return SETUP_ESSENTIALS_DONE
  return at + 1 < steps.length ? setupText(setupParts(PRESET_NAMES, at + 1)) : SETUP_DONE
}

const setup = async ($: EngineInterface, picked: Picked, origin: PromptOrigin, stepName?: string, pick?: string): Promise<string> => {
  const steps = setupSteps(PRESET_NAMES)
  const at = setupStart(steps, stepName)
  const paneable = (!stepName || stepName === SETUP_MORE) && !pick && origin.kind === 'composer'
  const opened = paneable && (await $.session.surfaces()).includes('terminal') ? await openSetupPane($, at) : undefined
  if (opened) return opened
  const step = steps[at]
  if (!step) return `Unknown setup step "${stepName}". Steps: ${steps.map(s => s.name).join(', ')}`
  if (!pick) return setupText(setupParts(PRESET_NAMES, at))
  const choices = step.key === 'theme' ? THEME_ARGS : step.options
  const value = /^\d+$/.test(pick) ? step.options[Number(pick) - 1] : pick
  if (!value || !choices.includes(value)) return `Unknown ${step.name} pick "${pick}". Pick 1-${step.options.length} or one of: ${choices.join(', ')}`
  const saved = await saveSetupPick($, picked, step, value)
  if (saved.startsWith('Could not')) return saved
  return `${saved}\n\n${afterSetupPick(steps, at)}`
}

const SETUP_GIT_STATUS = [
  'On branch main',
  'Changes not staged for commit:',
  '  (use "git add <file>..." to update what will be committed)',
  '        modified:   src/app.ts',
  '',
  'no changes added to commit (use "git add" and/or "git commit -a")',
]
const SETUP_BUILD_ERROR = [
  '> app@1.4.0 build',
  '> tsc',
  ...[3, 7, 12, 18, 25, 31, 40, 44, 52, 60].map(line => `src/app.ts(${line},5): error TS2322: Type 'string' is not assignable to type 'number'.`),
  'Found 10 errors in the same file, starting at: src/app.ts:3',
]

const toolOutputSample = (el: ReturnType<EngineInterface['ui']['resolve']>, style: Style, value: string, id: string, columns: number): RenderElement[] => {
  const status = { tool: 'Bash', input: { command: 'git status' }, isRunning: false, isErrored: false, isInterrupted: false }
  const build = { tool: 'Bash', input: { command: 'npm run build', description: 'Build the app' }, isRunning: false, isErrored: true, isInterrupted: false }
  const statusRow = <el.Box key={`${id}s`}>{renderToolRow(el, style, status, columns)}</el.Box>
  const buildRow = <el.Box key={`${id}r`}>{renderToolRow(el, style, build, columns)}</el.Box>
  if (value === 'quiet') return [statusRow, buildRow, renderFailure(el, style, SETUP_BUILD_ERROR.join('\n'), `${id}e`) ?? <el.Box key={`${id}e`} />]
  const folded = (lines: readonly string[], keep: number, color?: string) => [
    ...lines.slice(0, keep).map((line, i) => <el.Text key={`l${i}`} color={color}>{`${i === 0 ? '  ⎿  ' : '     '}${line}`}</el.Text>),
    <el.Text key="more" dimColor>{`     … +${lines.length - keep} lines (ctrl+o to expand)`}</el.Text>,
  ]
  return [
    statusRow,
    <el.Box key={`${id}so`} flexDirection="column">
      {folded(SETUP_GIT_STATUS, 3)}
      <el.Text key="allowed" dimColor>{'  ⎿  Allowed by auto mode classifier'}</el.Text>
    </el.Box>,
    buildRow,
    <el.Box key={`${id}e`} flexDirection="column">{folded(['Error: Exit code 2', ...SETUP_BUILD_ERROR], 10, style.theme.codeFlag)}</el.Box>,
  ]
}

const SETUP_TABLE = '| Item | Qty |\n|:-----|----:|\n| Apples | 3 |\n| Pears | 5 |'
const SETUP_SENT = new Date(2026, 0, 15, 14, 32).getTime()

const copySample = (el: ReturnType<EngineInterface['ui']['resolve']>, style: Style, value: string, id: string, columns: number): RenderElement[] => {
  const label: CopyButton = (_text, key, name = '⧉ copy', rich) => (offers(style, rich) ? (style.copyButtonStyle === 'dim' ? <el.Text key={key} dimColor>{name}</el.Text> : <el.Text key={key} bold>{`[ ${name} ]`}</el.Text>) : null)
  const table = renderBlocks(el, style, parse(SETUP_TABLE, { numbers: style.highlightNumbers, paths: style.highlightPaths }), columns, new Map(), label)
  return [
    <el.Box key={`${id}t`} flexDirection="column">{table}</el.Box>,
    ...(value === 'hover' ? [<el.Text key={`${id}h`} dimColor>{'Its buttons show only while the pointer is on its ⧉.'}</el.Text>] : []),
  ]
}

const clockSample = (el: ReturnType<EngineInterface['ui']['resolve']>, style: Style, value: string, id: string, columns: number): RenderElement[] => {
  const time = value === '24h' || value === '12h' ? clockText(SETUP_SENT, SETUP_SENT, value) : undefined
  const prompt = style.promptStyle === 'off' ? <el.Text dimColor>{`> ${time === undefined ? '' : `[${time}] `}fix the failing test`}</el.Text> : renderUserPrompt(el, style, 'fix the failing test', columns, time)
  return [<el.Box key={`${id}p`}>{prompt}</el.Box>, <el.Box key={`${id}d`}>{renderTurnDuration(el, style, 'Baked', 115000, time)}</el.Box>]
}

const promptSample = (el: ReturnType<EngineInterface['ui']['resolve']>, style: Style, value: string, id: string, columns: number): RenderElement[] =>
  [value === 'off' ? <el.Text key={id} dimColor>{'> fix the failing test'}</el.Text> : <el.Box key={id}>{renderUserPrompt(el, style, 'fix the failing test', columns)}</el.Box>]

const SETUP_REPLY = 'The failing test passes now: `retries` was read before the config loaded.'

const replySample = ($: EngineInterface, el: ReturnType<EngineInterface['ui']['resolve']>, style: Style, id: string, columns: number): RenderElement[] => {
  const framed = replyStyleFor(style, SETUP_REPLY)
  const drawn = drawMarkdown($, el, framed, parse(SETUP_REPLY, { numbers: style.highlightNumbers, paths: style.highlightPaths }), columns - replyRoom(framed))
  return [<el.Box key={id} flexDirection="column">{renderReply(el, framed, drawn, true, columns, false)}</el.Box>]
}

const SETUP_EDIT = {
  filePath: 'src/config.ts',
  structuredPatch: [{ oldStart: 12, newStart: 12, lines: [' export const config = {', '-  retries: 3,', '-  timeout: 5000,', '+  retries: 5,', '+  timeout: 10_000,', '   verbose: false,', ' }'] }],
}

const diffSample = (el: ReturnType<EngineInterface['ui']['resolve']>, style: Style, id: string, columns: number): RenderElement[] => [
  <el.Box key={`${id}r`}>{renderToolRow(el, style, { tool: 'Edit', input: { file_path: 'src/config.ts' }, isRunning: false, isErrored: false, isInterrupted: false }, columns)}</el.Box>,
  <el.Box key={`${id}d`} flexDirection="column">{renderDiffCard(el, style, SETUP_EDIT, () => null, id, columns)}</el.Box>,
]

type SetupView = { el: ReturnType<EngineInterface['ui']['resolve']>; base: Style; options: PluginOptions; at: number; step: SetupStep; current: string; columns: number; rows: number; pick: (value: string) => void }

const shownRows = (text: string, columns: number) => textRows(text.replace(/`/g, ''), columns)

const previewColumns = (v: SetupView, choices: readonly string[]): number =>
  Math.max(MIN_COLUMNS, Math.min(Math.max(40, v.columns - SETUP_LIST_COLUMNS), v.columns - 8 - Math.max(...choices.map(value => (value === v.current ? `${value} (now)` : value).length))))

const paneFits = (v: SetupView, choices: number, preview: string, columns: number): boolean =>
  SETUP_HEAD_ROWS + shownRows(v.step.note, v.columns) + shownRows(SETUP_PANE_KEYS, v.columns) + Math.max(choices, 1 + shownRows(preview, columns)) <= v.rows

const setupKeyboardPane = ($: EngineInterface, v: SetupView, focused: string, randomTheme: string): RenderElement => {
  const { el, step } = v
  const choices = step.key === 'theme' ? THEME_ARGS : step.options
  const shown = choices.includes(focused) ? focused : v.current
  const sampled = shown === 'random' ? randomTheme : shown
  const parts = setupParts(PRESET_NAMES, v.at)
  const options = parts.options.filter(o => o.value === sampled).map(o => (step.key === 'theme' ? { ...o, text: `${o.text.split('\n\n')[0]}\n\n${THEME_PREVIEW}` } : o))
  const columns = previewColumns(v, choices)
  const drawn = drawSetup($, el, v.base, v.options, { at: v.at, before: '', parts: { ...parts, options, tail: '' } }, columns)
  const buttons = choices.map(value => <el.Button key={pickKey(step, value)} label={value === v.current ? `${value} (now)` : value} variant={value === shown ? 'primary' : 'secondary'} autoFocus={value === v.current ? true : undefined} onPress={() => v.pick(value)} />)
  const fits = paneFits(v, choices.length, options[0]?.text ?? '', columns)
  return (
    <el.Box flexDirection="column" rowGap={1} {...(fits ? { height: v.rows, overflow: 'hidden' as const } : {})}>
      <el.Box flexDirection="column" flexShrink={0}>{drawn[0]}</el.Box>
      <el.Box flexShrink={0}><el.Text dimColor>{SETUP_PANE_KEYS}</el.Text></el.Box>
      <el.Box flexDirection="row" columnGap={4} flexShrink={1} overflow="hidden">
        <el.Box flexDirection="column" flexShrink={0}>{buttons}</el.Box>
        <el.Box flexDirection="column" flexGrow={1} overflow="hidden">
          <el.Box flexDirection="column" flexShrink={0}>{drawn.slice(1, -1)}</el.Box>
        </el.Box>
      </el.Box>
    </el.Box>
  )
}

const drawSetup = ($: EngineInterface, el: ReturnType<EngineInterface['ui']['resolve']>, base: Style, options: PluginOptions, found: NonNullable<ReturnType<typeof findSetup>>, columns: number): RenderElement[] => {
  const key = setupSteps(PRESET_NAMES)[found.at]!.key
  const md = (style: Style, text: string, id: string) => <el.Box key={id} flexDirection="column" rowGap={1}>{drawMarkdown($, el, style, parse(text, { numbers: style.highlightNumbers, paths: style.highlightPaths }), columns)}</el.Box>
  const samples: Partial<Record<SetupStep['key'], (style: Style, value: string, id: string) => RenderElement[]>> = {
    promptStyle: (style, value, id) => promptSample(el, style, value, id, columns),
    toolStyle: (style, _, id) => [md({ ...style, narration: style.toolStyle === 'tree-bold' }, 'Reading the config.', `${id}s`), <el.Box key={id}>{renderToolRow(el, style, { tool: 'Read', input: { file_path: 'src/config.ts' }, isRunning: false, isErrored: false, isInterrupted: false }, columns)}</el.Box>],
    toolOutput: (style, value, id) => toolOutputSample(el, style, value, id, columns),
    diffStyle: (style, _, id) => diffSample(el, style, id, columns),
    copyButtonStyle: (style, value, id) => copySample(el, style, value, id, columns),
    clock: (style, value, id) => clockSample(el, style, value, id, columns),
    replyStyle: (style, _, id) => replySample($, el, style, id, columns),
    bubbleLabels: (style, _, id) => [...promptSample(el, style, style.promptStyle, `${id}p`, columns), ...replySample($, el, style, id, columns)],
  }
  const sample = (style: Style, value: string, id: string): RenderElement[] => samples[key]?.(style, value, id) ?? []
  const picks = found.parts.options.map(({ value, text }, i) => {
    const style = key === 'theme' ? { ...base, theme: resolveStyle({ ...options, theme: value }).theme } : { ...base, [key]: value }
    return <el.Box key={`o${i}`} flexDirection="column">{md(style, text, 'm')}{sample(style, value, 'x')}</el.Box>
  })
  return [...(found.before ? [md(base, found.before, 'before')] : []), md(base, found.parts.head, 'head'), ...picks, md(base, found.parts.tail, 'tail')]
}

const hintsFor = (style: Style, latex: LatexSession, nth: number, pane?: number): string[] => [
  ...(style.diagramHints ? [HINT, FIGURE_HINT, ...(pane !== undefined && pane < NARROW_PANE ? [narrowHint(pane)] : []), ...(latex.ready && !latex.stopped ? [LATEX_HINT] : [])] : []),
  ...(style.issueHint && nth % 10 === 0 ? [ISSUE_HINT] : []),
]

const localeOf = async ($: EngineInterface, asked?: string): Promise<string> => asked ?? (await $.env.get('LC_ALL').catch(() => undefined)) ?? (await $.env.get('LANG').catch(() => undefined)) ?? ''

export const register: Register = (on, options) => {
  on('engine.create', async (_$, e, next) => ({ ...(await next(e)), prismantis: { markdown: async () => undefined } }))
  if (options.enabled === false) return
  const firstTheme = pickTheme(options.theme)
  const style = resolveStyle({ ...options, theme: firstTheme })
  const here: { surface?: RenderSurface[] } = style.surfaces ? { surface: style.surfaces } : {}
  const blinker: Blinker = { tools: 0, ready: new Set(), held: new Map() }
  const parsed = new Map<string, ReturnType<typeof parse>>()
  const parseCached = (text: string, cache = parsed, limit?: number) => remember(cache, text, () => parse(text, { numbers: style.highlightNumbers, paths: style.highlightPaths }), limit)
  const shared = new Map<string, ReturnType<typeof parse>>()
  let prompts = 0
  let pane: number | undefined
  const latex: LatexSession = { style, color: ratexColor(style.theme.diagramText ?? style.theme.codeText ?? '#808080'), pending: new Set(), wanted: new Set(), batch: [], queue: Promise.resolve() }
  const picked: Picked = { theme: firstTheme, options, latex }
  const probes: Probes = {}
  const pathChecks: PathChecks = { asked: new Set(), batch: [], found: new Set() }
  const forSurface = (base: Style, { surface, viewport }: { surface: RenderSurface; viewport?: { isFullscreen?: boolean } }, links: LinkReach): Style => {
    const drawn = surface === 'terminal' ? { ...base, hyperlinks: links.hyperlinks, ...(links.http || links.editor ? { httpLinks: links.http, editorLinks: links.editor, obsidianLinks: links.editor && viewport?.isFullscreen === false, fileLinks: links.files, pathLinks: links.paths } : {}) } : { ...base, hyperlinks: true, htmlCopy: null, nativeCode: true, gridFace: surface === 'desktop', monoFace: surface === 'desktop' && links.monoText }
    return surface === 'mobile' && drawn.copyButtonStyle === 'hover' ? { ...drawn, copyButtonStyle: 'inline' } : drawn
  }
  const fullWidth = (text: string) => (style.reorder && hasRtl(text) ? { width: '100%' as const } : {})

  const quiet = style.toolOutput === 'quiet'
  const quietRow = (expanded: boolean | undefined) => quiet && !expanded
  const shellCommands = new Map<string, string>()
  const noteCommand = (id: string | undefined, tool: string, input: unknown) => {
    const command = tool === 'Bash' && input !== null && typeof input === 'object' ? (input as { command?: unknown }).command : undefined
    if (!id || typeof command !== 'string') return
    shellCommands.delete(id)
    shellCommands.set(id, command)
    if (shellCommands.size > 500) shellCommands.delete(shellCommands.keys().next().value!)
  }
  let firstEdit: string | undefined
  if (options.toolRows !== false) {
    on('ui.render', { component: 'ToolGroup', ...here }, async ($, e, next) => {
      await locate($, style)
      for (const call of e.props.calls) noteCommand(call.tool_use_id, call.tool, call.input)
      if (quiet) for (const call of e.props.calls) if (call.tool_use_id && isReadOnlyCall(call.tool, call.input)) rememberCall(readOnlyCalls, call.tool_use_id)
      if (e.props.isExpanded) {
        for (const call of e.props.calls) if (call.tool_use_id) rememberCall(expandedCalls, call.tool_use_id, 500)
        return next(e)
      }
      const dotDark = await darkDot($, style, groupRunning(e.props))
      const drawn = forSurface(style, e, await linkReach($, probes, style))
      return renderToolGroup($.ui.resolve(e), { ...(await withFound($, pathChecks, drawn, toolPathsToProbe(drawn, e.props.calls.map(call => call.input)))), dotDark }, e.props.calls, e.props.isActive, e.viewport?.columns)
    })
    on('ui.render', { component: 'ToolUse', ...here }, async ($, e, next) => {
      await locate($, style)
      noteCommand(e.props.tool_use_id, e.props.tool, e.props.input)
      if (quiet && isReadOnlyCall(e.props.tool, e.props.input)) rememberCall(readOnlyCalls, e.props.tool_use_id)
      const dotDark = await darkDot($, style, e.props.isRunning)
      const drawn = forSurface(style, e, await linkReach($, probes, style))
      if (expandedRow(e.props)) return next(e)
      if (!expandedCalls.has(e.props.tool_use_id)) return renderToolRow($.ui.resolve(e), { ...(await withFound($, pathChecks, drawn, toolPathsToProbe(drawn, [e.props.input]))), dotDark }, e.props, e.viewport?.columns)
      const shell = e.props.tool === 'Bash' || e.props.tool === 'PowerShell'
      return shell && typeof e.props.output !== 'string' ? renderExpandedShell($.ui.resolve(e), { ...style, dotDark }, e.props, e.viewport?.columns) : next(e)
    })
    on('ui.render', { component: 'ToolResult', ...here }, async ($, e, next) => {
      const cards = (): Style => ({ ...style, pressPreview: e.surface === 'terminal' })
      if ((e.props.tool === 'Edit' || e.props.tool === 'Write') && !e.props.isErrored) return (await fileCard($, $.ui.resolve(e), e.props.output, e.props.tool_use_id, style, probes, cards, e.viewport?.columns)) ?? next(e)
      const edits = e.props.tool === 'Bash' && !e.props.isErrored ? bashEdits(e.props.output) : undefined
      if (edits) {
        await locate($, style)
        const el = $.ui.resolve(e)
        const output = withoutBashEdits(e.props.output)
        const above = !hasShellOutput(output) ? null : quiet ? renderShellResult(el, style, output) : await next({ ...e, props: { ...e.props, output } })
        firstEdit ??= e.props.tool_use_id
        const notes = editNotes(edits, firstEdit === e.props.tool_use_id, shellCommands.get(e.props.tool_use_id))
        const drawn = renderBashEdits(el, forSurface(cards(), e, await linkReach($, probes, style)), edits, folder($, el, await read($, unfolded), (await linkReach($, probes, style)).marks, style.folds === 'open'), e.props.tool_use_id, above !== null, notes, e.viewport?.columns)
        return above === null ? drawn : <el.Box flexDirection="column">{above}{drawn}</el.Box>
      }
      if (!quietRow(expandedRow(e.props))) return next(e)
      await locate($, style)
      const el = $.ui.resolve(e)
      const shell = e.props.tool === 'Bash' || e.props.tool === 'PowerShell'
      const out = (e.props.output ?? {}) as Record<string, unknown>
      if (shell && (out.backgroundTaskId || out.isImage || out.interrupted)) return next(e)
      if (e.props.isErrored) return renderFailure(el, style, e.props.output) ?? next(e)
      if (readOnlyCalls.has(e.props.tool_use_id)) return <el.Box />
      return shell ? renderShellResult(el, style, e.props.output) : next(e)
    })
  }

  on('tool.call', async ($, e, next) => {
    if (style.runningDot !== 'blink') {
      const done = await next(e)
      forgetMisses(pathChecks, e)
      return done
    }
    blinker.tools++
    await keepBlinking($, blinker)
    try {
      return await next(e)
    } finally {
      blinker.tools--
      await keepBlinking($, blinker)
      forgetMisses(pathChecks, e)
    }
  })

  on('session.start', async ($, e, next) => {
    await probe($, style, probes)
    void latexEngine($, latex)
    const started = await next(e)
    await $.command
      .register({ name: 'prismantis', description: 'Switch the prismantis theme, pick styles from samples, copy the last reply, or show the demo', argumentHint: '[theme [<name> | random] | setup [<step> [<pick>]] | copy [code] | demo]' })
      .catch(() => undefined)
    return started
  })

  on('command.run', { command: 'prismantis' }, async ($, e) => {
    const [first, second, third] = e.args.trim().split(/\s+/)
    const [sub, name] = THEME_ARGS.includes(first ?? '') ? ['theme', first] : [first, second]
    if (sub === 'demo') return { text: showcaseText(PRESET_NAMES) + languageShowcase(await localeOf($, name)) }
    if (sub === 'setup') return { text: await setup($, picked, e.origin, name, third) }
    if (sub === 'copy') {
      if (name && name !== 'code') return { text: `Unknown copy target "${name}". Use /prismantis copy, or /prismantis copy code for the last code block.` }
      const reply = (await $.session.messages()).findLast(m => m.role === 'assistant' && m.text.trim())
      if (!reply) return { text: 'Nothing to copy yet.' }
      const code = name === 'code' ? nestedBlocks(parseCached(reply.text)).findLast(b => b.kind === 'code' && !/^(mermaid|figure)$/i.test(b.lang)) : undefined
      if (name === 'code' && code?.kind !== 'code') return { text: 'The last reply has no code block.' }
      const text = code?.kind === 'code' ? code.lines.join('\n') : reply.text
      const said = await lastCopy(async () => {
        const result = await $.ui.copy({ text })
        return result.isCopied ? `Copied the last ${code ? 'code block' : 'reply'}.` : `Copy failed: ${result.reason}`
      })
      return { text: said ?? 'A newer copy replaced this one.' }
    }
    if (sub === 'demo-rtl') {
      await probe($, style, probes)
      return { text: rtlShowcaseText() }
    }
    if (sub !== 'theme') return { text: helpText(PRESET_NAMES) }
    if (!name) return { text: options.theme === 'random' ? `current: ${picked.theme} (random)\nkeep it: /prismantis theme ${picked.theme}` : `current: ${picked.theme}` }
    if (!THEME_ARGS.includes(name)) return { text: `Unknown theme "${name}". Themes: ${PRESET_NAMES.join(', ')}, random` }
    return { text: await setTheme($, picked, name) }
  })

  on('ui.render', { component: 'TurnDuration', ...here }, async ($, e) => {
    const at = style.clock === 'off' ? undefined : endedAt(await read($, turnEnds), e.props.durationMs, await firstDrawn($, e.requestId))
    const time = at === undefined ? undefined : clockText(at, await $.clock.now(), style.clock)
    return renderTurnDuration($.ui.resolve(e), style, e.props.word, e.props.durationMs, time)
  })

  on('turn.complete', async ($, e, next) => {
    if (style.clock !== 'off' && e.agentId === undefined) {
      const at = await $.clock.now()
      await persist($, () => update($, turnEnds, list => withRecord(list, { durationMs: e.durationMs, at })))
    }
    return next(e)
  })

  on('turn.start', async (_$, e, next) => {
    if ((e as { agentId?: string }).agentId === undefined) startTurn(blinker, promptKey(e.text))
    return next(e)
  })
  on('turn.step', async function* ($, e, next) {
    let asked = style.unreadPrompts && e.agentId === undefined ? [...blinker.ready] : undefined
    for await (const chunk of next(e)) {
      if (asked) await markRead($, asked, blinker)
      asked = undefined
      yield chunk
    }
  })

  on('prompt.submit', async ($, e, next) => {
    await markUnread($, style, e, blinker)
    if (style.clock !== 'off' && (e.origin.kind === 'composer' || e.origin.kind === 'bridge')) {
      const at = await $.clock.now()
      await persist($, () => update($, sent, list => withRecord(list, { text: promptKey(e.text), at })))
    }
    await probe($, style, probes)
    if (!takesHint(e.origin) || (style.surfaces && !(await drawsWhereAsked($, e.origin, style.surfaces)))) return next(e)
    if (style.diagramHints) void latexEngine($, latex)
    const hints = hintsFor(style, latex, prompts++, pane)
    return hints.length ? next({ ...e, context: [...(e.context ?? []), ...hints] }) : next(e)
  })

  let landing = ''
  const currentOf = (step: SetupStep): string => (step.key === 'theme' ? (options.theme === 'random' ? 'random' : picked.theme) : String(style[step.key]))

  on('ui.focus', async ($, e, next) => {
    if (e.component === 'Pane' && e.requestId === SETUP_PANE && e.element?.startsWith(SETUP_PICK)) await update($, setupFocus, () => e.element!.slice(e.element!.indexOf(':', SETUP_PICK.length) + 1))
    return next(e)
  })

  on('ui.scroll', { component: 'Pane', requestId: SETUP_PANE }, async ($, e, next) => {
    if (e.origin.kind !== 'person' || e.pointer || e.by === 0 || Math.abs(e.by) >= e.bodyRows) return next(e)
    const steps = setupSteps(PRESET_NAMES)
    const step = steps[Math.min(await read($, setupAt), steps.length - 1)]!
    const choices = step.key === 'theme' ? THEME_ARGS : step.options
    const focused = await read($, setupFocus)
    const at = choices.indexOf(choices.includes(focused) ? focused : currentOf(step))
    const target = choices[Math.max(0, Math.min(choices.length - 1, at + e.by))]!
    if (target === choices[at]) return next(e)
    await $.ui.focus({ requestId: SETUP_PANE, key: pickKey(step, target) }).catch(() => undefined)
    return {}
  })

  on('ui.render', { component: 'Pane', requestId: SETUP_PANE, ...here }, async ($, e) => {
    const steps = setupSteps(PRESET_NAMES)
    const at = Math.min(await read($, setupAt), steps.length - 1)
    const step = steps[at]!
    const land = await read($, setupLand)
    if (land !== landing) {
      landing = land
      if (land) landSetupFocus($, land)
    }
    const base = { ...forSurface(style, e, await linkReach($, probes, style)), copyButtons: false, pathLinks: false, images: await imagesOn($, probes, e.surface) }
    const view: SetupView = { el: $.ui.resolve(e), base, options, at, step, current: currentOf(step), columns: e.props.bodyColumns, rows: e.props.scroll.bodyRows, pick: value => void pickInPane($, picked, at, value, currentOf).catch(() => undefined) }
    return setupKeyboardPane($, view, await read($, setupFocus), picked.theme)
  })

  on('ui.render', { component: 'InfoNotice', ...here }, async (_$, e, next) =>
    mirrored(style) && hasRtl(e.props.text) && opensLatin(e.props.text) ? next({ ...e, props: { ...e.props, text: ROW_MARK_TEXT + e.props.text } }) : next(e))

  on('ui.render', { component: 'CommandOutput', ...here }, async ($, e, next) => {
    if (e.props.isErrored) return next(e)
    if (e.props.text.includes('\u001b')) return next(e)
    const found = e.props.command === 'prismantis' ? findSetup(PRESET_NAMES, e.props.text) : undefined
    if (found) {
      const el = $.ui.resolve(e)
      const base = { ...forSurface(style, e, await linkReach($, probes, style)), copyButtons: false, pathLinks: false, images: await imagesOn($, probes, e.surface) }
      return <el.Box flexDirection="column" rowGap={1}>{drawSetup($, el, base, options, found, columnsOf(e.viewport, base))}</el.Box>
    }
    const blocks = parseCached(e.props.text)
    if (blocks.length === 0) return next(e)
    const el = $.ui.resolve(e)
    const { Box } = el
    const reach = await linkReach($, probes, style)
    const math = await mathOfBlocks($, latex, e.surface, blocks)
    const pictures = await picturesOf($, style, probes, e.surface, blocks)
    const open = await read($, unfolded)
    const surfaceStyle = { ...(await withFoundPaths($, pathChecks, forSurface(style, e, reach), blocks)), images: await imagesOn($, probes, e.surface) }
    return <Box flexDirection="column" rowGap={1} {...fullWidth(e.props.text)}>{drawMarkdown($, el, surfaceStyle, blocks, columnsOf(e.viewport, surfaceStyle), math, pictures, undefined, open, { id: e.requestId, press: reach.marks })}</Box>
  })

  on('ui.render', { component: 'UserMessage', ...here }, async ($, e, next) => {
    const kind = e.props.origin.kind
    const own = kind === 'composer' || kind === 'bridge' || ((kind === 'unclassified' || kind === 'sdk') && !e.props.from && !e.props.task)
    if (!own) return next(e)
    const at = style.clock === 'off' ? undefined : sentAt(await read($, sent), e.props.text, await firstDrawn($, e.requestId))
    const time = at === undefined ? undefined : clockText(at, await $.clock.now(), style.clock)
    if (style.promptStyle === 'off') return time === undefined ? next(e) : next({ ...e, props: { ...e.props, text: `[${time}] ${e.props.text}` } })
    const el = $.ui.resolve(e)
    const drawn = await unreadLook($, style, forSurface(style, e, await linkReach($, probes, style)), e.props.text, e.requestId)
    const columns = columnsOf(e.viewport, drawn)
    const open = await read($, unfolded)
    const paste: DrawPaste = (body, key) => {
      const lines = body.split('\n')
      const title = `pasted text · ${lineCount(lines.length)}`
      const toggle = folder($, el, open, false, style.folds === 'open')(`${e.requestId}:${key}`, lines.length, key, { label: title })
      const opened = toggle?.folded === false
      return (
        <el.Box key={key} borderStyle="double" borderColor={drawn.theme.codeComment} paddingX={1} flexDirection="column" alignSelf="flex-start">
          {opened ? <el.Box key="head" flexDirection="row" justifyContent="space-between" columnGap={4}><el.Text color={drawn.theme.codeComment}>{title}</el.Text>{toggle.element}</el.Box> : toggle?.element ?? null}
          {opened ? drawMarkdown($, el, drawn, [{ kind: 'code', lang: pasteLang(body), lines, raw: body }], columns - 8, undefined, undefined, undefined, open) : null}
        </el.Box>
      )
    }
    return renderUserPrompt(el, drawn, e.props.text, columns, time, paste)
  })

  on('ui.render', { component: 'AssistantMessage', ...here }, async ($, e, next) => {
    if (e.surface === 'terminal' && e.viewport?.columns) pane = e.viewport.columns
    const blocks = parseCached(e.props.text)
    if (blocks.length === 0) return next(e)
    const el = $.ui.resolve(e)
    const narration = style.toolStyle === 'tree-bold' && blocks.length === 1 && blocks[0]!.kind === 'paragraph'
    const reach = await linkReach($, probes, style)
    const math = await mathOfBlocks($, latex, e.surface, blocks)
    const pictures = await picturesOf($, style, probes, e.surface, blocks)
    const surfaceStyle = { ...(await withFoundPaths($, pathChecks, forSurface(style, e, reach), blocks)), images: await imagesOn($, probes, e.surface) }
    const open = await read($, unfolded)
    const reply = blocks.length > 1 || hasRtl(e.props.text) ? e.props.text : undefined
    const corner = reply !== undefined && markerRoom(surfaceStyle) > 0
    const columns = columnsOf(e.viewport, surfaceStyle)
    const framed = replyStyleFor(surfaceStyle, e.props.text)
    const drawn = drawMarkdown($, el, narration ? { ...framed, narration } : framed, blocks, columns - replyRoom(framed), math, pictures, reply, open, { id: e.requestId, press: reach.marks })
    return renderReply(el, framed, drawn, e.props.isFirstOfReply === true, columns, corner)
  })

  on('prismantis.markdown', here, async ($, e, next) => {
    const blocks = parseCached(e.text, shared, 20)
    if (blocks.length === 0) return next(e)
    const el = $.ui.resolve({ surface: e.surface, component: 'AssistantMessage' })
    const { Box } = el
    const surfaceStyle = forSurface(style, e, await linkReach($, probes, style))
    return { value: <Box flexDirection="column" rowGap={1} {...fullWidth(e.text)}>{drawMarkdown($, el, { ...surfaceStyle, copyButtons: false }, blocks, Math.max(MIN_COLUMNS, e.columns || 0))}</Box> }
  })
}
