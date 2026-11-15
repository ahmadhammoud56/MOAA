import { expect, mock, test } from 'claude-code/testing'

import { LINUX_TABLE_COPY, MAC_IMAGE_COPY, WIN_IMAGE_COPY, WIN_TABLE_COPY, imageCommand } from '../hooks/clipboard'
import { PRESETS } from '../hooks/presets'
import { clipboardEnv, payloadOf, recordCopies, recordToasts, runResult, startSession } from './clipboard-env'

const source = '| Name | Value |\n|--|--:|\n| **שלום** | `$(ignored)` |'
const plain = 'Name\tValue\nשלום\t$(ignored)'
const mount = {
  plugin: 'prismantis',
  component: 'AssistantMessage' as const,
  props: { text: source, isFirstOfReply: true },
  viewport: { columns: 120, rows: 40 },
  surface: 'terminal' as const,
}

const backends = {
  macos: { platform: 'macos', env: {}, argv: ['/usr/bin/osascript', '-l', 'JavaScript'] },
  wayland: { platform: 'other', env: { WAYLAND_DISPLAY: 'wayland-0', DISPLAY: ':0' }, argv: ['copyq', 'eval', LINUX_TABLE_COPY, '-'] },
  x11: { platform: 'other', env: { DISPLAY: ':0' }, argv: ['copyq', 'eval', LINUX_TABLE_COPY, '-'] },
} as const

for (const [backend, setup] of Object.entries(backends)) test(`${backend} copies HTML and plain text together`, async ($, on) => {
  clipboardEnv(on, setup.platform, setup.env)
  const calls: { argv: readonly string[]; input: string }[] = []
  on('process.run', (_, e) => {
    calls.push({ argv: e.argv, input: e.init?.stdin ?? '' })
    return runResult(0)
  })
  const copies = recordCopies(on)
  const toasts = recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount(mount)
  expect((await ui.findAll({ type: 'Button' })).map(button => button.props.label).filter(label => label !== '⧉ copy reply')).toEqual(['⧉ md', '⧉ art', '⧉ html', ...(backend === 'macos' ? ['▣ png'] : [])])
  expect(calls).toHaveLength(0)
  await ui.press({ key: 'html0' })
  expect(calls).toHaveLength(1)
  expect(calls[0]!.argv).toEqual(setup.argv)
  const payload = payloadOf(calls[0]!.input)
  expect(payload.text).toBe(plain)
  expect(payload.html).toContain('<strong>שלום</strong>')
  expect(payload.html).toContain('<code style="white-space: pre-wrap">$(ignored)</code>')
  expect(copies).toHaveLength(0)
  expect(toasts).toEqual(['Copied formatted table'])
  await ui.unmount()
})

test('windows copies HTML and CRLF plain text through PowerShell', async ($, on) => {
  clipboardEnv(on, 'other', { OS: 'Windows_NT', SystemRoot: 'C:\\Windows' })
  const calls: { argv: readonly string[]; input: string }[] = []
  on('process.run', (_, e) => {
    calls.push({ argv: e.argv, input: e.init?.stdin ?? '' })
    return runResult(0)
  })
  const copies = recordCopies(on)
  const toasts = recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, props: { text: '| Name | Value |\n|--|--|\n| ✅ done | ❌ failed |', isFirstOfReply: true } })
  expect((await ui.findAll({ type: 'Button' })).map(button => button.props.label).filter(label => label !== '⧉ copy reply')).toEqual(['⧉ md', '⧉ art', '⧉ html', '▣ png'])
  expect(calls).toHaveLength(0)
  await ui.press({ key: 'html0' })
  expect(calls).toHaveLength(1)
  expect(calls[0]!.argv[0]).toBe('C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe')
  expect(calls[0]!.argv).not.toContain('-ExecutionPolicy')
  expect(calls[0]!.argv).toContain('-STA')
  expect(calls[0]!.argv.at(-1)).toBe(WIN_TABLE_COPY)
  expect(calls[0]!.input).toMatch(/^[\x00-\x7e]*$/)
  const payload = payloadOf(calls[0]!.input)
  expect(payload.html.startsWith('<table>')).toBe(true)
  expect(payload.html).toContain('<th style="text-align: left">Name</th>')
  expect(payload.html).not.toContain('Excel')
  expect(payload.html).toContain('✅ done')
  expect(payload.text).toBe('Name\tValue\r\n✅ done\t❌ failed')
  expect(copies).toHaveLength(0)
  expect(toasts).toEqual(['Copied formatted table'])
  await ui.unmount()
})

test('windows without SystemRoot falls back to plain text without running PowerShell', async ($, on) => {
  clipboardEnv(on, 'other', { OS: 'Windows_NT' })
  let processes = 0
  on('process.run', () => {
    processes++
    return runResult(0)
  })
  const copies = recordCopies(on)
  const toasts = recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount(mount)
  await ui.press({ key: 'html0' })
  expect(processes).toBe(0)
  expect(copies).toEqual([plain])
  expect(toasts).toEqual(['Copied as plain text (Windows clipboard helper failed)'])
  await ui.unmount()
})

for (const failure of ['exit', 'refused'] as const) test(`native clipboard ${failure} falls back to plain text`, async ($, on) => {
  clipboardEnv(on, 'macos')
  on('process.run', () => failure === 'refused' ? { deny: 'Cannot start helper' } : runResult(1, 'Clipboard unavailable'))
  const copies = recordCopies(on)
  const toasts = recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount(mount)
  await ui.press({ key: 'html0' })
  expect(toasts).toEqual([`Copied as plain text (${failure === 'exit' ? 'Clipboard unavailable' : 'macOS clipboard helper failed'})`])
  expect(copies).toEqual([plain])
  await ui.unmount()
})

for (const failure of ['missing', 'exit', 'timeout'] as const) test(`Linux clipboard ${failure} falls back to plain text`, async ($, on) => {
  clipboardEnv(on, 'other', { DISPLAY: ':0' })
  on('process.run', () => failure === 'timeout' ? { deny: 'Process timed out' } : runResult(failure === 'missing' ? 127 : 1))
  const copies = recordCopies(on)
  const toasts = recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount(mount)
  await ui.press({ key: 'html0' })
  expect(copies).toEqual([plain])
  expect(toasts).toEqual(['Copied as plain text (CopyQ failed; install and start CopyQ in the graphical session)'])
  await ui.unmount()
})

const hidden = {
  'over SSH_CONNECTION': { platform: 'macos', env: { SSH_CONNECTION: 'remote connection' }, surface: 'terminal' },
  'over SSH_TTY': { platform: 'macos', env: { SSH_TTY: '/dev/ttys001' }, surface: 'terminal' },
  'over SSH with a forwarded display': { platform: 'other', env: { SSH_CONNECTION: 'remote connection', DISPLAY: 'localhost:10.0' }, surface: 'terminal' },
  'over SSH on Windows': { platform: 'other', env: { OS: 'Windows_NT', SSH_CONNECTION: 'remote connection' }, surface: 'terminal' },
  'without a graphical session': { platform: 'other', env: {}, surface: 'terminal' },
  'on desktop': { platform: 'macos', env: {}, surface: 'desktop' },
  'on desktop in Linux': { platform: 'other', env: { WAYLAND_DISPLAY: 'wayland-0' }, surface: 'desktop' },
} as const

for (const [where, setup] of Object.entries(hidden)) test(`the HTML action is hidden ${where}`, async ($, on) => {
  clipboardEnv(on, setup.platform, setup.env)
  let processes = 0
  on('process.run', () => {
    processes++
    return { deny: 'Must not run the native helper' }
  })
  const copies = recordCopies(on)
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, surface: setup.surface })
  expect((await ui.findAll({ type: 'Button' })).map(button => button.props.label).filter(label => label !== '⧉ copy reply')).toEqual(['⧉ md', '⧉ art'])
  await ui.press({ key: 'copy0' })
  expect(copies).toEqual([source])
  expect(processes).toBe(0)
  await ui.unmount()
})

test('the HTML check runs once, on session start or on the first prompt after a reload', async ($, on) => {
  let checks = 0
  mock.env(on, {})
  on('fs.stat', (_, e, next) => {
    if (!e.path.replace(/\\/g, '/').endsWith('/usr/bin/osascript')) return next(e)
    checks++
    return { value: { kind: 'file' as const, size: 0, mtimeMs: 0, isLink: false } }
  })
  on('prompt.submit', (_, e) => ({ text: e.text, context: e.context }))
  on('session.start', () => ({ cwd: '/tmp' }))
  const before = await $.ui.mount(mount)
  expect((await before.findAll({ type: 'Button' })).map(button => button.props.label).filter(label => label !== '⧉ copy reply')).toEqual(['⧉ md', '⧉ art'])
  await before.unmount()
  await $.prompt.submit({ text: 'hi', wait: false, origin: { kind: 'composer' } })
  await $.prompt.submit({ text: 'again', wait: false, origin: { kind: 'composer' } })
  await $.session.start({ cwd: '/tmp', surface: 'terminal', isInteractive: true })
  const after = await $.ui.mount(mount)
  expect((await after.findAll({ type: 'Button' })).map(button => button.props.label).filter(label => label !== '⧉ copy reply')).toEqual(['⧉ md', '⧉ art', '⧉ html', '▣ png'])
  expect(checks).toBe(1)
  await after.unmount()
})

test('a table drawn before the HTML check lands gains ⧉ html when it lands', async ($, on) => {
  let release = () => {}
  const held = new Promise<void>(resolve => { release = resolve })
  mock.env(on, {})
  on('fs.stat', async (_, e, next) => {
    if (!e.path.replace(/\\/g, '/').endsWith('/usr/bin/osascript')) return next(e)
    await held
    return { value: { kind: 'file' as const, size: 0, mtimeMs: 0, isLink: false } }
  })
  on('session.start', () => ({ cwd: '/tmp' }))
  const ui = await $.ui.mount(mount)
  const labels = async () => (await ui.findAll({ type: 'Button' })).map(button => button.props.label).filter(label => label !== '⧉ copy reply')
  const started = $.session.start({ cwd: '/tmp', surface: 'terminal', isInteractive: true })
  expect(await labels()).toEqual(['⧉ md', '⧉ art'])
  release()
  await started
  expect(await labels()).toEqual(['⧉ md', '⧉ art', '⧉ html', '▣ png'])
  await ui.unmount()
})

for (const key of ['copy0', 'html0']) for (const failure of ['unavailable', 'refused'] as const) test(`${key} reports a ${failure} surface clipboard`, async ($, on) => {
  clipboardEnv(on, 'macos')
  on('process.run', () => runResult(1))
  on('ui.copy', () => failure === 'refused'
    ? { deny: 'Clipboard denied' }
    : { value: { isCopied: false as const, reason: 'no-clipboard' as const } })
  const toasts = recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount(mount)
  await ui.press({ key })
  expect(toasts).toEqual([failure === 'refused' ? 'Copy failed' : 'Copy failed: no-clipboard'])
  await ui.unmount()
})

test('the image helper gets each glyph at its terminal column, and the theme colors as RGB, on stdin', async () => {
  const text = '┌──┬──┐\n│苹│ab│\n└──┴──┘'
  const mac = imageCommand('macos', text, { foreground: '#cdd6f4', background: '#1e1e2e' })!
  expect(mac.argv).toEqual(['/usr/bin/osascript', '-l', 'JavaScript'])
  expect(mac.stdin.endsWith(`\n${MAC_IMAGE_COPY}`)).toBe(true)
  const row = (s: string) => [...s].map((text, at) => ({ at, text }))
  expect(payloadOf(mac.stdin)).toEqual({
    lines: [row('┌──┬──┐'), [{ at: 0, text: '│' }, { at: 1, text: '苹' }, { at: 3, text: '│' }, { at: 4, text: 'a' }, { at: 5, text: 'b' }, { at: 6, text: '│' }], row('└──┴──┘')],
    columns: 7,
    foreground: [205, 214, 244],
    background: [30, 30, 46],
  })
  const win = imageCommand('windows', text, { foreground: 'ansi256(15)', background: '#fff' }, 'C:\\Windows')!
  expect(win.argv).toEqual(['C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe', '-NoProfile', '-NonInteractive', '-STA', '-Command', WIN_IMAGE_COPY])
  expect(win.stdin).toMatch(/^[\x00-\x7e]*$/)
  expect(payloadOf(win.stdin)).toEqual({ ...payloadOf(mac.stdin), foreground: [0, 0, 0], background: [255, 255, 255] })
  expect(payloadOf(imageCommand('macos', 'x', { foreground: 'cyan' })!.stdin)).toMatchObject({ foreground: [0, 0, 0], background: [255, 255, 255] })
  expect(payloadOf(imageCommand('macos', 'x', { foreground: '#c9d4f2' })!.stdin)).toMatchObject({ foreground: [0, 0, 0], background: [255, 255, 255] })
  expect(payloadOf(imageCommand('macos', 'x', { foreground: '#202020', background: '#1e1e2e' })!.stdin)).toMatchObject({ foreground: [255, 255, 255] })
})

test('the image helper gets right-to-left cell text in drawn order, each letter in its own column, borders kept in place', async () => {
  const lines = payloadOf(imageCommand('macos', '│ שלום │ 3 │\n│ Pears אגסים │', {}).stdin).lines
  expect(lines[0]).toEqual([{ at: 0, text: '│' }, { at: 2, text: 'ם' }, { at: 3, text: 'ו' }, { at: 4, text: 'ל' }, { at: 5, text: 'ש' }, { at: 7, text: '│' }, { at: 9, text: '3' }, { at: 11, text: '│' }])
  expect(lines[1].map((g: { text: string }) => g.text).join('')).toBe('│Pearsםיסגא│')
  expect(lines[1].at(-1)).toEqual({ at: 14, text: '│' })
})

test('▣ png of a 500 row table gets a helper timeout sized to its input, capped at 30 s', async ($, on) => {
  clipboardEnv(on, 'macos')
  const timeouts: (number | undefined)[] = []
  on('process.run', (_, e) => {
    timeouts.push(e.init?.timeoutMs)
    return runResult(0)
  })
  recordToasts(on)
  await startSession($, on)
  const rows = Array.from({ length: 500 }, (_, i) => `| ${i + 1} | row${i + 1} | ${(i + 1) * 37} |`).join('\n')
  const ui = await $.ui.mount({ ...mount, props: { text: `| # | name | value |\n|--:|:--|--:|\n${rows}`, isFirstOfReply: true } })
  await ui.press({ key: 'png0' })
  await ui.press({ key: 'html0' })
  expect(timeouts[0]).toBeGreaterThan(9000)
  expect(timeouts[0]).toBeLessThanOrEqual(30000)
  expect(timeouts[1]).toBeLessThan(timeouts[0]!)
  await ui.unmount()
})

test('the png helper gets block glyphs as cell fractions to fill, so bars and pies draw with no seams', () => {
  const glyphs = payloadOf(imageCommand('macos', '█▌▀▁▏▚a─', {}).stdin).lines[0] as { text: string; fill?: number[][] }[]
  expect(glyphs.map(g => g.fill)).toEqual([
    [[0, 0, 0.5, 0.5], [0.5, 0, 1, 0.5], [0, 0.5, 0.5, 1], [0.5, 0.5, 1, 1]],
    [[0, 0, 0.5, 0.5], [0, 0.5, 0.5, 1]],
    [[0, 0, 0.5, 0.5], [0.5, 0, 1, 0.5]],
    [[0, 0.875, 1, 1]],
    [[0, 0, 0.125, 1]],
    [[0, 0, 0.5, 0.5], [0.5, 0.5, 1, 1]],
    undefined,
    undefined,
  ])
})

const figures = '| Item | Qty |\n|--|--:|\n| 苹果 | 3 |\n\n```mermaid\ngraph LR\nA[User] --> B[Gateway]\n```'
const pngSetups = {
  macos: { platform: 'macos', env: {}, script: MAC_IMAGE_COPY },
  windows: { platform: 'other', env: { OS: 'Windows_NT', SystemRoot: 'C:\\Windows' }, script: WIN_IMAGE_COPY },
  linux: { platform: 'other', env: { DISPLAY: ':0' }, script: undefined },
} as const

for (const surface of ['terminal', 'desktop'] as const) for (const [backend, setup] of Object.entries(pngSetups)) test(`▣ png on tables and diagrams ${setup.script && surface === 'terminal' ? 'copies an image' : 'is hidden'} on ${backend} ${surface}`, async ($, on) => {
  clipboardEnv(on, setup.platform, setup.env)
  const calls: { argv: readonly string[]; input: string }[] = []
  on('process.run', (_, e) => {
    calls.push({ argv: e.argv, input: e.init?.stdin ?? '' })
    return runResult(0)
  })
  const copies = recordCopies(on)
  const toasts = recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, surface, props: { text: figures, isFirstOfReply: true } })
  const pngs = (await ui.findAll({ type: 'Button' })).filter(button => button.props.label === '▣ png').map(button => button.key)
  if (!setup.script || surface !== 'terminal') {
    expect(pngs).toEqual([])
    await ui.unmount()
    return
  }
  expect(pngs).toEqual(['png0', 'png1'])
  await ui.press({ key: 'art0' })
  await ui.press({ key: 'png0' })
  expect(calls).toHaveLength(1)
  expect([...calls[0]!.argv, calls[0]!.input].some(s => s.endsWith(setup.script))).toBe(true)
  const drawn = payloadOf(calls[0]!.input).lines.map((glyphs: { text: string }[]) => glyphs.map(g => g.text).join(''))
  expect(copies[0]).toContain('```')
  expect(drawn.join('\n')).not.toContain('`')
  expect(drawn).toEqual(copies[0]!.split('\n').slice(1, -1).map((line, i) => (i === 2 ? line.replace(/[├┼┤─]/g, c => ({ '├': '╞', '┼': '╪', '┤': '╡', '─': '═' })[c]!) : line.replace(/ /g, ''))))
  await ui.press({ key: 'png1' })
  expect(payloadOf(calls[1]!.input).lines.flat().map((run: { text: string }) => run.text).join('')).toContain('Gateway')
  expect(toasts).toEqual(['Copied', 'Copied as image', 'Copied as image'])
  await ui.unmount()
})

test('a failed image copy falls back to the drawn text and says why', async ($, on) => {
  clipboardEnv(on, 'macos')
  on('process.run', () => runResult(1, 'Cannot draw image'))
  const copies = recordCopies(on)
  const toasts = recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, props: { text: figures, isFirstOfReply: true } })
  await ui.press({ key: 'png0' })
  expect(copies[0]).toContain('│ 苹果 │')
  expect(toasts).toEqual(['Copied as plain text (Cannot draw image)'])
  await ui.unmount()
})

test('the last copy pressed wins: ⧉ md pressed while ▣ png still draws lands after the image, and ⧉ art pressed between is dropped', async ($, on) => {
  clipboardEnv(on, 'macos')
  const order: string[] = []
  let release = () => {}
  const drawing = new Promise<void>(resolve => { release = resolve })
  on('process.run', async () => {
    await drawing
    order.push('png')
    return runResult(0)
  })
  on('ui.copy', (_, e) => {
    order.push(e.text.startsWith('|') ? 'md' : 'text')
    return { value: { isCopied: true as const } }
  })
  const toasts = recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount(mount)
  const png = ui.press({ key: 'png0' })
  const art = ui.press({ key: 'art0' })
  const md = ui.press({ key: 'copy0' })
  release()
  await Promise.all([png, art, md])
  expect(order).toEqual(['png', 'md'])
  expect(toasts).toEqual(['Copied as image', 'Copied'])
  await ui.unmount()
})

test('/prismantis copy run while ▣ png still draws lands after the image', async ($, on) => {
  clipboardEnv(on, 'macos')
  const order: string[] = []
  let release = () => {}
  const drawing = new Promise<void>(resolve => { release = resolve })
  on('process.run', async () => {
    await drawing
    order.push('png')
    return runResult(0)
  })
  on('session.messages', () => ({ value: [{ role: 'assistant' as const, text: source, toolUses: [] }] }))
  on('ui.copy', (_, e) => {
    order.push(e.text === source ? 'reply' : 'other')
    return { value: { isCopied: true as const } }
  })
  recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount(mount)
  const png = ui.press({ key: 'png0' })
  const command = $.command.run({ command: 'prismantis', args: 'copy', origin: { kind: 'composer' as const }, presentation: { isFullscreen: false, columns: 120 } })
  const said = command.then(result => order.push(result.text ?? ''))
  for (let i = 0; i < 200; i++) await Promise.resolve()
  release()
  await Promise.all([png, said])
  expect(order).toEqual(['png', 'reply', 'Copied the last reply.'])
  await ui.unmount()
})

test('/prismantis copy with an unknown target copies nothing and says how to use it', async ($, on) => {
  on('session.messages', () => ({ value: [{ role: 'assistant' as const, text: source, toolUses: [] }] }))
  const copies = recordCopies(on)
  const result = await $.command.run({ command: 'prismantis', args: 'copy cdoe', origin: { kind: 'composer' as const }, presentation: { isFullscreen: false, columns: 120 } })
  expect(copies).toEqual([])
  expect(result.text).toBe('Unknown copy target "cdoe". Use /prismantis copy, or /prismantis copy code for the last code block.')
})

test('copyButtons off draws no ▣ png',{ options: { copyButtons: false } }, async ($, on) => {
  clipboardEnv(on, 'macos')
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, props: { text: figures, isFirstOfReply: true } })
  expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
  await ui.unmount()
})

test('▣ png draws a table as the screen does: header bold in its color, rules, inline colors and table text', { options: { theme: 'catppuccin-mocha', tableTextColor: '#ffffff' } }, async ($, on) => {
  clipboardEnv(on, 'macos')
  const inputs: string[] = []
  on('process.run', (_, e) => {
    inputs.push(e.init?.stdin ?? '')
    return runResult(0)
  })
  recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, props: { text: '| Name | Note |\n|--|--|\n| plain | `code` **bold** *slant* |', isFirstOfReply: true } })
  await ui.press({ key: 'png0' })
  type Glyph = { at: number; text: string; color?: number[]; bold?: boolean; italic?: boolean }
  const lines = (payloadOf(inputs[0]!) as { lines: Glyph[][] }).lines
  const rgb = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))
  const t = PRESETS['catppuccin-mocha']
  const at = (row: number, text: string) => lines[row]!.find(g => g.text === text)!
  expect(lines[2]!.map(g => g.text).join('')).toMatch(/^╞═+╪═+╡$/)
  expect(lines[1]![1]).toMatchObject({ at: 2, text: 'N', color: rgb(t.tableHeader!), bold: true })
  expect(at(0, '┌').color).toEqual(rgb(t.tableRule!))
  expect(at(3, 'p').color).toEqual([255, 255, 255])
  expect(at(3, 'c').color).toEqual(rgb(t.inlineCode!))
  expect(at(3, 'b')).toMatchObject({ color: rgb(t.strong!), bold: true })
  expect(at(3, 's')).toMatchObject({ color: rgb(t.emphasis!), italic: true })
  expect(at(3, 'p').bold).toBeUndefined()
  await ui.unmount()
})

test('the png helper keeps a rule glyph in its drawn color and still makes a bar or a letter readable', () => {
  const text = '─█a'
  const glyphs = payloadOf(imageCommand('macos', text, { foreground: '#000000', background: '#ffffff' }, undefined, [['#f5f5f5', '#f5f5f5', '#f5f5f5']]).stdin).lines[0]
  expect(glyphs.map((g: { color?: number[] }) => g.color)).toEqual([[245, 245, 245], [0, 0, 0], [0, 0, 0]])
})

test('pngBackgroundColor sets the background of the png copy', { options: { pngBackgroundColor: '#000000' } }, async ($, on) => {
  clipboardEnv(on, 'macos')
  const inputs: string[] = []
  on('process.run', (_, e) => {
    inputs.push(e.init?.stdin ?? '')
    return runResult(0)
  })
  recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, props: { text: figures, isFirstOfReply: true } })
  await ui.press({ key: 'png0' })
  expect(payloadOf(inputs[0]!).background).toEqual([0, 0, 0])
  await ui.unmount()
})

test('a pngBackgroundColor the png helper cannot read falls back to the theme background', { options: { pngBackgroundColor: 'red', theme: 'catppuccin-mocha' } }, async ($, on) => {
  clipboardEnv(on, 'macos')
  const inputs: string[] = []
  on('process.run', (_, e) => {
    inputs.push(e.init?.stdin ?? '')
    return runResult(0)
  })
  recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, props: { text: figures, isFirstOfReply: true } })
  await ui.press({ key: 'png0' })
  expect(payloadOf(inputs[0]!).background).toEqual([0x1e, 0x1e, 0x2e])
  await ui.unmount()
})

test('▣ png keeps the colors the figure and the diagram draw with', async ($, on) => {
  clipboardEnv(on, 'macos')
  const inputs: string[] = []
  on('process.run', (_, e) => {
    inputs.push(e.init?.stdin ?? '')
    return runResult(0)
  })
  recordToasts(on)
  await startSession($, on)
  const text = '```figure\n{accent:┌──┐} {warn:DOWN} up\n```\n\n```mermaid\nflowchart TD\n  A[Start] --> B[End]\n```'
  const ui = await $.ui.mount({ ...mount, props: { text, isFirstOfReply: true } })
  for (const key of ['png0', 'png1']) await ui.press({ key })
  const colors = (input: string) => {
    const payload = payloadOf(input) as { lines: { text: string; color?: number[] }[][] }
    return new Map(payload.lines.flat().map(g => [g.text, String(g.color)]))
  }
  const figure = colors(inputs[0]!)
  expect(figure.get('D')).not.toBe(figure.get('u'))
  expect(figure.get('┌')).not.toBe(figure.get('u'))
  const diagram = colors(inputs[1]!)
  expect(diagram.get('┌')).not.toBe('undefined')
  await ui.unmount()
})

test('the png helper keeps a chart gridline dot in its dim rule color', () => {
  const glyphs = JSON.parse(imageCommand('windows', '·a', { foreground: '#cdd6f4', background: '#1e1e2e' }, 'C:\\Windows', [['#45475a', '#45475a']]).stdin).lines[0]
  expect(glyphs.map((g: { color?: number[] }) => g.color)).toEqual([[0x45, 0x47, 0x5a], [255, 255, 255]])
})

test('▣ png in mono draws table rules and chart gridline dots dim, not in the text color', { options: { theme: 'mono' } }, async ($, on) => {
  clipboardEnv(on, 'macos')
  const inputs: string[] = []
  on('process.run', (_, e) => {
    inputs.push(e.init?.stdin ?? '')
    return runResult(0)
  })
  recordToasts(on)
  await startSession($, on)
  const chart = '```mermaid\nxychart-beta\n  x-axis [mon, tue]\n  y-axis "pods" 0 --> 100\n  bar [30, 90]\n```'
  const ui = await $.ui.mount({ ...mount, props: { text: `${source}\n\n${chart}`, isFirstOfReply: true } })
  await ui.press({ key: 'png0' })
  await ui.press({ key: 'png1' })
  type Payload = { lines: { text: string; color?: number[] }[][]; foreground: number[] }
  const colorOf = (input: string, glyph: string) => {
    const payload = payloadOf(input) as Payload
    return { ink: payload.lines.flat().find(g => g.text === glyph)!.color, text: payload.foreground }
  }
  for (const [input, glyph] of [[inputs[0]!, '─'], [inputs[1]!, '·']] as const) {
    const { ink, text } = colorOf(input, glyph)
    expect(ink).toBeDefined()
    expect(ink).not.toEqual(text)
  }
  await ui.unmount()
})

test('a Hebrew table copies to png and html with its columns right to left, as the screen draws it', { options: { rtl: 'warp' } }, async ($, on) => {
  clipboardEnv(on, 'other', { OS: 'Windows_NT', SystemRoot: 'C:\\Windows' })
  const inputs: string[] = []
  on('process.run', (_, e) => {
    inputs.push(e.init?.stdin ?? '')
    return runResult(0)
  })
  recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, props: { text: '| שם | כמות |\n|--|--:|\n| תפוחים | 3 |', isFirstOfReply: true } })
  await ui.press({ key: 'png0' })
  await ui.press({ key: 'html0' })
  const row = (JSON.parse(inputs[0]!) as { lines: { at: number; text: string }[][] }).lines[3]!
  expect(row.find(g => g.text === '3')!.at).toBeLessThan(row.find(g => /[א-ת]/.test(g.text))!.at)
  expect(JSON.parse(inputs[1]!).html).toMatch(/^<table dir="rtl">/)
  await ui.unmount()
})

test('⧉ art copies a Hebrew table with its columns right to left, as the screen and ▣ png draw it', { options: { rtl: 'warp' } }, async ($, on) => {
  clipboardEnv(on, 'macos')
  on('process.run', () => runResult(0))
  const copies = recordCopies(on)
  recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount({ ...mount, props: { text: '| שם | כמות |\n|--|--:|\n| תפוחים | 3 |', isFirstOfReply: true } })
  await ui.press({ key: 'art0' })
  expect(copies[0]!.split('\n')[4]).toBe('│    3 │ תפוחים │')
  await ui.unmount()
})

test('a Latin table copies to html with no dir', async ($, on) => {
  clipboardEnv(on, 'other', { OS: 'Windows_NT', SystemRoot: 'C:\\Windows' })
  const inputs: string[] = []
  on('process.run', (_, e) => {
    inputs.push(e.init?.stdin ?? '')
    return runResult(0)
  })
  recordToasts(on)
  await startSession($, on)
  const ui = await $.ui.mount(mount)
  await ui.press({ key: 'html0' })
  expect(JSON.parse(inputs[0]!).html).toMatch(/^<table>/)
  await ui.unmount()
})
