import { atom, read, update } from 'claude-code'
import type { EngineInterface, PluginOptions, PromptOrigin, Register, RenderElement, RenderSurface } from 'claude-code'

import { clockText, endedAt, promptKey, sentAt, withRecord } from './clock'
import type { Formula } from './latex'
import { LATEX_DPR, LATEX_FONT_PX, MAX_IMAGE_BYTES, fitImage, fitsImage, imageFile, imageOf, keepFormulas, mathOf, padFor, pickFormula, pngSize, ratexColor, renderedOf } from './latex'
import type { Block } from './markdown'
import { nestedBlocks, parse } from './markdown'
import type { ClipboardBackend } from './clipboard'
import { clipboardCommand } from './clipboard'
import { FIGURE_HINT } from './figure'
import { drawDiagrams } from './mermaid'
import type { CopyButton, DrawPaste, Fold, TerminalEnv } from './render'
import { MARK, bashEdits, drawMath, drawsHyperlinks, editNotes, fileRoot, hasShellOutput, instanceKey, isReadOnlyCall, leftToEngine, markerRoom, mirrored, noteTip, pasteLang, remember, rememberCall, renderBashEdits, renderBlocks, renderDiffCard, renderExpandedShell, renderFailure, renderShellResult, renderToolGroup, renderToolRow, renderTurnDuration, renderUserPrompt, takesClickableMarks, takesEditorLinks, takesHttpLinks, withoutBashEdits } from './render'
import type { SetupStep } from './help'
import { HINT, ISSUE_HINT, SETUP_DONE, SETUP_PANE_KEYS, SETUP_PANE_OPENED, THEME_PREVIEW, findSetup, helpText, languageShowcase, rtlShowcaseText, setupParts, setupSteps, setupText, showcaseText } from './help'
import { PRESET_NAMES } from './presets'
import type { Style } from './theme'
import { RANDOM_THEMES, pickTheme, resolveStyle } from './theme'
import type { Terminal } from './rtl'
import { ROW_MARK_TEXT, TERMINALS, hasRtl, opensLatin } from './rtl'

const HINTED_ORIGINS = ['composer', 'bridge', 'plugin'] as const satisfies readonly PromptOrigin['kind'][]

const takesHint = (origin: PromptOrigin): boolean => HINTED_ORIGINS.some(kind => kind === origin.kind)

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

const savePng = async ($: EngineInterface, art: string): Promise<string> => {
  const home = (await $.env.get('USERPROFILE')) ?? (await $.env.get('HOME')) ?? '.'
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const tmp = (await $.env.get('TEMP')) ?? home
  const out = `${tmp}/prismantis-${stamp}.png`
  const script = `${$.plugin.root}/scripts/text2png.py`
  for (const python of ['python', 'py', 'python3']) {
    const run = await $.process.run([python, script, out], { stdin: art }).catch(() => undefined)
    if (run?.exitCode === 0) return out
  }
  throw new Error('no python with pillow')
}

const copyPngToClipboard = async ($: EngineInterface, path: string): Promise<boolean> => {
  const file = path.replace(/\//g, '\\')
  const script = `Add-Type -AssemblyName System.Windows.Forms,System.Drawing; $f='${file.replace(/'/g, "''")}'; $i=[System.Drawing.Image]::FromFile($f); $b=New-Object System.Drawing.Bitmap($i); $i.Dispose(); [System.Windows.Forms.Clipboard]::SetImage($b); $b.Dispose(); Remove-Item -LiteralPath $f`
  const run = await $.process.run(['powershell', '-NoProfile', '-STA', '-Command', script]).catch(() => undefined)
  return run?.exitCode === 0
}

const readOnlyCalls = new Set<string>()

const columnsOf = (viewport?: { columns?: number }) => Math.max(20, (viewport?.columns ?? 100) - 4)

const formulas = atom({ plugin: 'prismantis', key: 'formulas' } as const, {})
const latexDir = atom({ plugin: 'prismantis', key: 'dir' } as const, '')
const unfolded = atom({ plugin: 'prismantis', key: 'unfolded' } as const, [] as string[])
const sent = atom({ plugin: 'prismantis', key: 'sent' } as const, [])
const turnEnds = atom({ plugin: 'prismantis', key: 'turnEnds' } as const, [])
const setupAt = atom({ plugin: 'prismantis', key: 'setupAt' } as const, 0)
const setupFocus = atom({ plugin: 'prismantis', key: 'setupFocus' } as const, '')
const setupLand = atom({ plugin: 'prismantis', key: 'setupLand' } as const, '')

const firstDrawn = async ($: EngineInterface, id: string): Promise<number> => {
  const ref = { plugin: 'prismantis', key: 'drawn', id } as const
  const { value } = await $.state.get(ref)
  if (value !== undefined) return value
  const now = await $.clock.now()
  $.clock.after(0, () => void $.state.set(ref, now, { ifVersion: 0 }))
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
  return Promise.all(texs.map(async (_, i): Promise<Formula> => {
    if (!rendered.has(i + 1)) return { error: true }
    const png = await $.fs.read(`${engine.dir}/${String(i + 1).padStart(4, '0')}.png`, { as: 'bytes' }).then(r => r.base64, () => '')
    const size = png ? pngSize(png) : null
    return size && fitsImage(png) ? { png, ...size } : { error: true }
  }))
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
  await update($, latexDir, () => suffix)
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
  await update($, formulas, store => keepFormulas(store, fresh, latex.wanted))
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

const loaded = new Map<string, Promise<Omit<Picture, 'alt'> | null>>()

const picturesOf = async ($: EngineInterface, style: Style, probes: Probes, surface: string, blocks: Block[]): Promise<Map<number, Picture>> => {
  const images = [...blocks.entries()].flatMap(([i, block]) => {
    const image = imageOf(block)
    return image ? [{ i, ...image }] : []
  })
  if (surface !== 'terminal' || images.length === 0 || !(await (probes.images ??= showsImages($).catch(() => false)))) return new Map()
  await locate($, style)
  const found = await Promise.all(images.map(async ({ i, alt, src }) => {
    const picture = await remember(loaded, src, () => pictureOf($, src, style.home), 50)
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

type LinkReach = { http: boolean; editor: boolean; marks: boolean; files: string | null; paths: boolean }

type Probes = { terminal?: Promise<Terminal | null>; htmlCopy?: Promise<ClipboardBackend | null>; links?: Promise<LinkReach>; images?: Promise<boolean> }

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
  return { http, editor: takesEditorLinks(base), marks: takesClickableMarks(base), files, paths: files !== null && drawsHyperlinks(await terminalEnv($).catch(() => ({}))) }
}

const linkReach = ($: EngineInterface, probes: Probes, style: Style): Promise<LinkReach> => (probes.links ??= readLinkReach($, style))

const fileCard = async ($: EngineInterface, el: ReturnType<EngineInterface['ui']['resolve']>, output: unknown, id: string, style: Style, probes: Probes, drawn: () => Style, columns?: number): Promise<RenderElement | undefined> => {
  const press = (await linkReach($, probes, style)).marks
  if (leftToEngine(output, press)) return undefined
  await locate($, style)
  return renderDiffCard(el, drawn(), output, folder($, el, await read($, unfolded), press), id, columns)
}

const probe = async ($: EngineInterface, style: Style, probes: Probes): Promise<Terminal | null> => {
  probes.terminal ??= applyRtl($, style)
  const terminal = await probes.terminal
  probes.htmlCopy ??= htmlBackend($)
  const before = style.htmlCopy
  style.htmlCopy = await probes.htmlCopy
  const png = Boolean(await $.env.get('PRISMANTIS_PNG_BUTTON').catch(() => undefined))
  if (style.htmlCopy !== before || style.pngCopy !== png) $.ui.invalidate('ui.render')
  style.pngCopy = png
  return terminal
}

const copyTable = async ($: EngineInterface, backend: ClipboardBackend, html: string, text: string): Promise<string | null> => {
  const systemRoot = backend === 'windows' ? await $.env.get('SystemRoot') : undefined
  const command = clipboardCommand(backend, html, text, systemRoot)
  if (backend === 'windows' && !systemRoot) return command.failure
  const result = await $.process.run(command.argv, { stdin: command.stdin, timeoutMs: 5000 }).catch(() => null)
  if (!result) return command.failure
  return result.exitCode === 0 ? null : result.stderr.trim() || command.failure
}

const folder = ($: EngineInterface, el: ReturnType<EngineInterface['ui']['resolve']>, open?: string[], faces = false): Fold => (id, hidden, key, look) => {
  if (!open) return null
  const folded = !open.includes(id)
  const label = folded ? look?.label ?? `+${hidden} more lines` : 'show less'
  const toggle = () => update($, unfolded, ids => (folded ? [...ids, id].slice(-500) : ids.filter(x => x !== id)))
  if (!faces) return { folded, faced: false, element: <el.Button key={key} variant="secondary" label={label} onPress={toggle} /> }
  const element = look?.face ? <el.Button key={key} plain label={label} onPress={toggle}>{look.face(folded)}</el.Button> : <el.Button key={key} variant="secondary" label={label} onPress={toggle} />
  return { folded, faced: look?.face !== undefined, element, around: (rows, hover) => <el.Button key={`${key}.rows`} plain label={label} hover={hover} onPress={toggle}>{rows}</el.Button> }
}

const drawMarkdown = ($: EngineInterface, el: ReturnType<EngineInterface['ui']['resolve']>, style: Style, blocks: ReturnType<typeof parse>, columns: number, math: Map<number, Typeset> = new Map(), pictures: Map<number, Picture> = new Map(), reply?: string, open?: string[], notes?: { id: string; press: boolean }): RenderElement[] => {
  const { Button } = el
  const copy = (text: string | (() => string), key: string, label = '⧉ copy', html?: () => string) => {
    const copied = async (surface: RenderSurface): Promise<string> => {
      const content = typeof text === 'function' ? text() : text
      const backend = style.htmlCopy
      const failure = html && backend ? await copyTable($, backend, html(), content) : undefined
      if (failure === null) return 'Copied formatted table'
      const result = await $.ui.copy({ text: content, surface })
      if (!result.isCopied) return `Copy failed: ${result.reason}`
      return failure ? `Copied as plain text (${failure})` : 'Copied'
    }
    return style.copyButtons && (!html || style.htmlCopy) ? (
      <Button
        key={key}
        variant="primary"
        label={label}
        onPress={async press => $.ui.toast(await copied(press.surface).catch(() => 'Copy failed'))}
      />
    ) : null
  }
  const png = (text: string | (() => string), key: string, label = '▣ png') =>
    style.copyButtons && style.pngCopy ? (
      <Button
        key={key}
        variant="primary"
        label={label}
        onPress={() => {
          savePng($, typeof text === 'function' ? text() : text)
            .then(async path => $.ui.toast((await copyPngToClipboard($, path)) ? 'Copied image' : `Clipboard copy failed, image kept at ${path}`))
            .catch(() => $.ui.toast('PNG save failed (needs python + pillow)'))
        }}
      />
    ) : null
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
  const elements = renderBlocks(el, notes ? { ...style, noteKey: instanceKey(notes.id) } : style, blocks, columns, drawMath(el, style, blocks, drawn), copy, folder($, el, open), tip, png)
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

const setTheme = async ($: EngineInterface, picked: Picked, name: string): Promise<string> => {
  const result = await $.config.set({ key: `${$.plugin.name}.theme`, value: name })
  if (result.deny) return `Could not switch theme: ${result.deny}`
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
  step.key === 'theme' ? setTheme($, picked, value) : $.config.set({ key: `${$.plugin.name}.${step.key}`, value }).then(r => (r.deny ? `Could not save ${step.key}: ${r.deny}` : `${step.title} set to ${value}.`))

const SETUP_PANE = 'prismantis-setup'

const SETUP_PICK = 'pick:'
const SETUP_LIST_COLUMNS = 30
const SETUP_HEAD_ROWS = 8

const openPane = ($: EngineInterface) => $.ui.open({ id: SETUP_PANE, title: 'prismantis setup', focus: true, closeOnEscape: true, rows: 40, columns: 90 })

const openSetupPane = async ($: EngineInterface): Promise<string | undefined> => {
  await update($, setupAt, () => 0)
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
  const nextStep = steps[at + 1]
  const done = `${step.title} set to ${value}.`
  if (nextStep) await showSetupStep($, at + 1, nextStep, currentOf(nextStep))
  else await $.ui.close({ id: SETUP_PANE })
  $.ui.toast(nextStep ? done : `${done} Setup done.`)
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

const setup = async ($: EngineInterface, picked: Picked, origin: PromptOrigin, stepName?: string, pick?: string): Promise<string> => {
  const inTerminal = !stepName && origin.kind === 'composer' && (await $.session.surfaces()).includes('terminal')
  const opened = inTerminal ? await openSetupPane($) : undefined
  if (opened) return opened
  const steps = setupSteps(PRESET_NAMES)
  const at = stepName ? steps.findIndex(s => s.name === stepName) : 0
  const step = steps[at]
  if (!step) return `Unknown setup step "${stepName}". Steps: ${steps.map(s => s.name).join(', ')}`
  if (!pick) return setupText(setupParts(PRESET_NAMES, at))
  const choices = step.key === 'theme' ? THEME_ARGS : step.options
  const value = /^\d+$/.test(pick) ? step.options[Number(pick) - 1] : pick
  if (!value || !choices.includes(value)) return `Unknown ${step.name} pick "${pick}". Pick 1-${step.options.length} or one of: ${choices.join(', ')}`
  const saved = await saveSetupPick($, picked, step, value)
  if (saved.startsWith('Could not')) return saved
  return `${saved}\n\n${at + 1 < steps.length ? setupText(setupParts(PRESET_NAMES, at + 1)) : SETUP_DONE}`
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
  const label: CopyButton = (_text, key, name = '⧉ copy', html) => (html && !style.htmlCopy ? null : <el.Text key={key} bold>{`[ ${name} ]`}</el.Text>)
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

const SETUP_EDIT = {
  filePath: 'src/config.ts',
  structuredPatch: [{ oldStart: 12, newStart: 12, lines: [' export const config = {', '-  retries: 3,', '-  timeout: 5000,', '+  retries: 5,', '+  timeout: 10_000,', '   verbose: false,', ' }'] }],
}

const diffSample = (el: ReturnType<EngineInterface['ui']['resolve']>, style: Style, id: string, columns: number): RenderElement[] => [
  <el.Box key={`${id}r`}>{renderToolRow(el, style, { tool: 'Edit', input: { file_path: 'src/config.ts' }, isRunning: false, isErrored: false, isInterrupted: false }, columns)}</el.Box>,
  <el.Box key={`${id}d`} flexDirection="column">{renderDiffCard(el, style, SETUP_EDIT, () => null, id, columns)}</el.Box>,
]

type SetupView = { el: ReturnType<EngineInterface['ui']['resolve']>; base: Style; options: PluginOptions; at: number; step: SetupStep; current: string; columns: number; rows: number; pick: (value: string) => void }

const setupKeyboardPane = ($: EngineInterface, v: SetupView, focused: string, randomTheme: string): RenderElement => {
  const { el, step } = v
  const choices = step.key === 'theme' ? THEME_ARGS : step.options
  const shown = choices.includes(focused) ? focused : v.current
  const sampled = shown === 'random' ? randomTheme : shown
  const parts = setupParts(PRESET_NAMES, v.at)
  const options = parts.options.filter(o => o.value === sampled).map(o => (step.key === 'theme' ? { ...o, text: `${o.text.split('\n\n')[0]}\n\n${THEME_PREVIEW}` } : o))
  const drawn = drawSetup($, el, v.base, v.options, { at: v.at, before: '', parts: { ...parts, options, tail: '' } }, Math.max(40, v.columns - SETUP_LIST_COLUMNS))
  const buttons = choices.map(value => <el.Button key={pickKey(step, value)} label={value === v.current ? `${value} (now)` : value} variant={value === shown ? 'primary' : 'secondary'} autoFocus={value === v.current ? true : undefined} onPress={() => v.pick(value)} />)
  const fits = choices.length + SETUP_HEAD_ROWS <= v.rows
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
  const sample = (style: Style, value: string, id: string): RenderElement[] => {
    if (key === 'promptStyle') return [value === 'off' ? <el.Text key={id} dimColor>{'> fix the failing test'}</el.Text> : <el.Box key={id}>{renderUserPrompt(el, style, 'fix the failing test', columns)}</el.Box>]
    if (key === 'toolStyle') return [md({ ...style, narration: style.toolStyle === 'tree-bold' }, 'Reading the config.', `${id}s`), <el.Box key={id}>{renderToolRow(el, style, { tool: 'Read', input: { file_path: 'src/config.ts' }, isRunning: false, isErrored: false, isInterrupted: false }, columns)}</el.Box>]
    if (key === 'toolOutput') return toolOutputSample(el, style, value, id, columns)
    if (key === 'diffStyle') return diffSample(el, style, id, columns)
    if (key === 'copyButtonStyle') return copySample(el, style, value, id, columns)
    if (key === 'clock') return clockSample(el, style, value, id, columns)
    return []
  }
  const picks = found.parts.options.map(({ value, text }, i) => {
    const style = key === 'theme' ? { ...base, theme: resolveStyle({ ...options, theme: value }).theme } : { ...base, [key]: value }
    return <el.Box key={`o${i}`} flexDirection="column">{md(style, text, 'm')}{sample(style, value, 'x')}</el.Box>
  })
  return [...(found.before ? [md(base, found.before, 'before')] : []), md(base, found.parts.head, 'head'), ...picks, md(base, found.parts.tail, 'tail')]
}

const hintsFor = (style: Style, latex: LatexSession, nth: number): string[] => [
  ...(style.diagramHints ? [HINT, FIGURE_HINT, ...(latex.ready && !latex.stopped ? [LATEX_HINT] : [])] : []),
  ...(style.issueHint && nth % 10 === 0 ? [ISSUE_HINT] : []),
]

const localeOf = async ($: EngineInterface, asked?: string): Promise<string> => asked ?? (await $.env.get('LC_ALL').catch(() => undefined)) ?? (await $.env.get('LANG').catch(() => undefined)) ?? ''

export const register: Register = (on, options) => {
  on('engine.create', async (_$, e, next) => ({ ...(await next(e)), prismantis: { markdown: async () => undefined } }))
  if (options.enabled === false) return
  const firstTheme = pickTheme(options.theme)
  const style = resolveStyle({ ...options, theme: firstTheme })
  const parsed = new Map<string, ReturnType<typeof parse>>()
  const parseCached = (text: string, cache = parsed, limit?: number) => remember(cache, text, () => parse(text, { numbers: style.highlightNumbers, paths: style.highlightPaths }), limit)
  const shared = new Map<string, ReturnType<typeof parse>>()
  let terminal: Terminal | null = null
  const fit = (viewport?: { isFullscreen?: boolean }): Style => (terminal === 'apple-terminal' && viewport?.isFullscreen ? { ...style, shape: 'inverse' } : style)
  let prompts = 0
  const latex: LatexSession = { style, color: ratexColor(style.theme.diagramText ?? style.theme.codeText ?? '#808080'), pending: new Set(), wanted: new Set(), batch: [], queue: Promise.resolve() }
  const picked: Picked = { theme: firstTheme, options, latex }
  const probes: Probes = {}
  const forSurface = (base: Style, surface: RenderSurface, links: LinkReach): Style => {
    const drawn = surface === 'terminal' ? (links.http || links.editor ? { ...base, httpLinks: links.http, editorLinks: links.editor, fileLinks: links.files, pathLinks: links.paths } : base) : { ...base, htmlCopy: null, nativeCode: true }
    return surface === 'mobile' && drawn.copyButtonStyle === 'hover' ? { ...drawn, copyButtonStyle: 'inline' } : drawn
  }
  const fullWidth = (text: string) => (style.reorder && hasRtl(text) ? { width: '100%' as const } : {})

  const quiet = style.toolOutput === 'quiet'
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
    on('ui.render', { component: 'ToolGroup' }, async ($, e, next) => {
      await locate($, style)
      for (const call of e.props.calls) noteCommand(call.tool_use_id, call.tool, call.input)
      if (quiet) for (const call of e.props.calls) if (call.tool_use_id && isReadOnlyCall(call.tool, call.input)) rememberCall(readOnlyCalls, call.tool_use_id)
      if (e.props.isExpanded) {
        for (const call of e.props.calls) if (call.tool_use_id) rememberCall(expandedCalls, call.tool_use_id, 500)
        return next(e)
      }
      return renderToolGroup($.ui.resolve(e), forSurface(fit(e.viewport), e.surface, await linkReach($, probes, style)), e.props.calls, e.props.isActive, e.viewport?.columns)
    })
    on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
      await locate($, style)
      noteCommand(e.props.tool_use_id, e.props.tool, e.props.input)
      if (quiet && isReadOnlyCall(e.props.tool, e.props.input)) rememberCall(readOnlyCalls, e.props.tool_use_id)
      if (!expandedCalls.has(e.props.tool_use_id)) return renderToolRow($.ui.resolve(e), forSurface(fit(e.viewport), e.surface, await linkReach($, probes, style)), e.props, e.viewport?.columns)
      const shell = e.props.tool === 'Bash' || e.props.tool === 'PowerShell'
      return shell && typeof e.props.output !== 'string' ? renderExpandedShell($.ui.resolve(e), fit(e.viewport), e.props) : next(e)
    })
    on('ui.render', { component: 'ToolResult' }, async ($, e, next) => {
      const cards = (): Style => ({ ...fit(e.viewport), pressPreview: e.surface === 'terminal' })
      if ((e.props.tool === 'Edit' || e.props.tool === 'Write') && !e.props.isErrored) return (await fileCard($, $.ui.resolve(e), e.props.output, e.props.tool_use_id, style, probes, cards, e.viewport?.columns)) ?? next(e)
      const edits = e.props.tool === 'Bash' && !e.props.isErrored ? bashEdits(e.props.output) : undefined
      if (edits) {
        await locate($, style)
        const el = $.ui.resolve(e)
        const output = withoutBashEdits(e.props.output)
        const above = !hasShellOutput(output) ? null : quiet ? renderShellResult(el, fit(e.viewport), output) : await next({ ...e, props: { ...e.props, output } })
        firstEdit ??= e.props.tool_use_id
        const notes = editNotes(edits, firstEdit === e.props.tool_use_id, shellCommands.get(e.props.tool_use_id))
        const drawn = renderBashEdits(el, forSurface(cards(), e.surface, await linkReach($, probes, style)), edits, folder($, el, await read($, unfolded), (await linkReach($, probes, style)).marks), e.props.tool_use_id, above !== null, notes, e.viewport?.columns)
        return above === null ? drawn : <el.Box flexDirection="column">{above}{drawn}</el.Box>
      }
      if (!quiet) return next(e)
      await locate($, style)
      const el = $.ui.resolve(e)
      const shell = e.props.tool === 'Bash' || e.props.tool === 'PowerShell'
      const out = (e.props.output ?? {}) as Record<string, unknown>
      if (shell && (out.backgroundTaskId || out.isImage || out.interrupted)) return next(e)
      if (e.props.isErrored) return renderFailure(el, fit(e.viewport), e.props.output) ?? next(e)
      if (readOnlyCalls.has(e.props.tool_use_id)) return <el.Box />
      return shell ? renderShellResult(el, fit(e.viewport), e.props.output) : next(e)
    })
  }

  on('session.start', async ($, e, next) => {
    terminal = await probe($, style, probes)
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
      const reply = (await $.session.messages()).findLast(m => m.role === 'assistant' && m.text.trim())
      if (!reply) return { text: 'Nothing to copy yet.' }
      const code = name === 'code' ? nestedBlocks(parseCached(reply.text)).findLast(b => b.kind === 'code') : undefined
      if (name === 'code' && code?.kind !== 'code') return { text: 'The last reply has no code block.' }
      const result = await $.ui.copy({ text: code?.kind === 'code' ? code.lines.join('\n') : reply.text })
      return { text: result.isCopied ? `Copied the last ${code ? 'code block' : 'reply'}.` : `Copy failed: ${result.reason}` }
    }
    if (sub === 'demo-rtl') {
      terminal = await probe($, style, probes)
      return { text: rtlShowcaseText() }
    }
    if (sub !== 'theme') return { text: helpText(PRESET_NAMES) }
    if (!name) return { text: options.theme === 'random' ? `current: ${picked.theme} (random)\nkeep it: /prismantis theme ${picked.theme}` : `current: ${picked.theme}` }
    if (!THEME_ARGS.includes(name)) return { text: `Unknown theme "${name}". Themes: ${PRESET_NAMES.join(', ')}, random` }
    return { text: await setTheme($, picked, name) }
  })

  on('ui.render', { component: 'TurnDuration' }, async ($, e) => {
    const at = style.clock === 'off' ? undefined : endedAt(await read($, turnEnds), e.props.durationMs, await firstDrawn($, e.requestId))
    const time = at === undefined ? undefined : clockText(at, await $.clock.now(), style.clock)
    return renderTurnDuration($.ui.resolve(e), style, e.props.word, e.props.durationMs, time)
  })

  on('turn.complete', async ($, e, next) => {
    if (style.clock !== 'off' && e.agentId === undefined) {
      const at = await $.clock.now()
      await update($, turnEnds, list => withRecord(list, { durationMs: e.durationMs, at }))
    }
    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    if (style.clock !== 'off' && (e.origin.kind === 'composer' || e.origin.kind === 'bridge')) {
      const at = await $.clock.now()
      await update($, sent, list => withRecord(list, { text: promptKey(e.text), at }))
    }
    terminal = await probe($, style, probes)
    if (!takesHint(e.origin)) return next(e)
    if (style.diagramHints) void latexEngine($, latex)
    const hints = hintsFor(style, latex, prompts++)
    return hints.length ? next({ ...e, context: [...(e.context ?? []), ...hints] }) : next(e)
  })

  let landing = ''
  const currentOf = (step: SetupStep): string => (step.key === 'theme' ? (options.theme === 'random' ? 'random' : picked.theme) : String(style[step.key]))

  on('ui.focus', async ($, e, next) => {
    if (e.component === 'Pane' && e.requestId === SETUP_PANE && e.element?.startsWith(SETUP_PICK)) await update($, setupFocus, () => e.element!.slice(e.element!.indexOf(':', SETUP_PICK.length) + 1))
    return next(e)
  })

  on('ui.scroll', { component: 'Pane', requestId: SETUP_PANE }, async ($, e, next) => {
    if (e.origin.kind !== 'person' || e.pointer || Math.abs(e.by) !== 1) return next(e)
    const steps = setupSteps(PRESET_NAMES)
    const step = steps[Math.min(await read($, setupAt), steps.length - 1)]!
    const choices = step.key === 'theme' ? THEME_ARGS : step.options
    const focused = await read($, setupFocus)
    const at = choices.indexOf(choices.includes(focused) ? focused : currentOf(step))
    const target = choices[at + e.by]
    if (target === undefined) return next(e)
    await $.ui.focus({ requestId: SETUP_PANE, key: pickKey(step, target) }).catch(() => undefined)
    return {}
  })

  on('ui.render', { component: 'Pane', requestId: SETUP_PANE }, async ($, e) => {
    const steps = setupSteps(PRESET_NAMES)
    const at = Math.min(await read($, setupAt), steps.length - 1)
    const step = steps[at]!
    const land = await read($, setupLand)
    if (land !== landing) {
      landing = land
      if (land) landSetupFocus($, land)
    }
    const base = { ...forSurface(fit(e.viewport), e.surface, await linkReach($, probes, style)), copyButtons: false, pathLinks: false }
    const view: SetupView = { el: $.ui.resolve(e), base, options, at, step, current: currentOf(step), columns: e.props.bodyColumns, rows: e.props.scroll.bodyRows, pick: value => void pickInPane($, picked, at, value, currentOf) }
    return setupKeyboardPane($, view, await read($, setupFocus), picked.theme)
  })

  on('ui.render', { component: 'InfoNotice' }, async (_$, e, next) =>
    mirrored(style) && hasRtl(e.props.text) && opensLatin(e.props.text) ? next({ ...e, props: { ...e.props, text: ROW_MARK_TEXT + e.props.text } }) : next(e))

  on('ui.render', { component: 'CommandOutput' }, async ($, e, next) => {
    if (e.props.isErrored) return next(e)
    if (e.props.text.includes('\u001b')) return next(e)
    const found = e.props.command === 'prismantis' ? findSetup(PRESET_NAMES, e.props.text) : undefined
    if (found) {
      const el = $.ui.resolve(e)
      const base = { ...forSurface(fit(e.viewport), e.surface, await linkReach($, probes, style)), copyButtons: false, pathLinks: false }
      return <el.Box flexDirection="column" rowGap={1}>{drawSetup($, el, base, options, found, columnsOf(e.viewport))}</el.Box>
    }
    const blocks = parseCached(e.props.text)
    if (blocks.length === 0) return next(e)
    const el = $.ui.resolve(e)
    const { Box } = el
    const reach = await linkReach($, probes, style)
    const math = await mathOfBlocks($, latex, e.surface, blocks)
    const pictures = await picturesOf($, style, probes, e.surface, blocks)
    const open = await read($, unfolded)
    const surfaceStyle = forSurface(fit(e.viewport), e.surface, reach)
    return <Box flexDirection="column" rowGap={1} {...fullWidth(e.props.text)}>{drawMarkdown($, el, surfaceStyle, blocks, columnsOf(e.viewport), math, pictures, undefined, open, { id: e.requestId, press: reach.marks })}</Box>
  })

  on('ui.render', { component: 'UserMessage' }, async ($, e, next) => {
    const kind = e.props.origin.kind
    const own = kind === 'composer' || kind === 'bridge' || (kind === 'unclassified' && !e.props.from && !e.props.task)
    if (!own) return next(e)
    const at = style.clock === 'off' ? undefined : sentAt(await read($, sent), e.props.text, await firstDrawn($, e.requestId))
    const time = at === undefined ? undefined : clockText(at, await $.clock.now(), style.clock)
    if (style.promptStyle === 'off') return time === undefined ? next(e) : next({ ...e, props: { ...e.props, text: `[${time}] ${e.props.text}` } })
    const el = $.ui.resolve(e)
    const drawn = forSurface(fit(e.viewport), e.surface, await linkReach($, probes, style))
    const columns = columnsOf(e.viewport)
    const open = await read($, unfolded)
    const paste: DrawPaste = (body, key) => {
      const lines = body.split('\n')
      const title = `pasted text · ${lines.length} lines`
      const toggle = folder($, el, open)(`${e.requestId}:${key}`, lines.length, key, { label: title })
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

  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => {
    const blocks = parseCached(e.props.text)
    if (blocks.length === 0) return next(e)
    const el = $.ui.resolve(e)
    const { Box, Text } = el
    const narration = style.toolStyle === 'tree-bold' && blocks.length === 1 && blocks[0]!.kind === 'paragraph'
    const reach = await linkReach($, probes, style)
    const math = await mathOfBlocks($, latex, e.surface, blocks)
    const pictures = await picturesOf($, style, probes, e.surface, blocks)
    const surfaceStyle = forSurface(fit(e.viewport), e.surface, reach)
    const open = await read($, unfolded)
    const reply = blocks.length > 1 || hasRtl(e.props.text) ? e.props.text : undefined
    const corner = reply !== undefined && markerRoom(surfaceStyle) > 0
    return (
      <Box key="msg" flexDirection="row">
        <Box width={2} flexShrink={0}>
          <Text color={style.theme.accent}>{e.props.isFirstOfReply ? '●' : ' '}</Text>
        </Box>
        <Box flexDirection="column" rowGap={1} flexGrow={1}>
          {drawMarkdown($, el, narration ? { ...surfaceStyle, narration } : surfaceStyle, blocks, columnsOf(e.viewport), math, pictures, reply, open, { id: e.requestId, press: reach.marks })}
        </Box>
        {corner ? <Box width={MARK} flexShrink={0} /> : null}
      </Box>
    )
  })

  on('prismantis.markdown', async ($, e, next) => {
    const blocks = parseCached(e.text, shared, 20)
    if (blocks.length === 0) return next(e)
    const el = $.ui.resolve({ surface: e.surface, component: 'AssistantMessage' })
    const { Box } = el
    const surfaceStyle = forSurface(style, e.surface, await linkReach($, probes, style))
    return { value: <Box flexDirection="column" rowGap={1} {...fullWidth(e.text)}>{drawMarkdown($, el, { ...surfaceStyle, copyButtons: false }, blocks, Math.max(20, e.columns || 0))}</Box> }
  })
}
