import type { On } from 'claude-code'
import { expect, mock, test } from 'claude-code/testing'

import { pieRgba } from '../hooks/charts'
import { showcaseText } from '../hooks/help'
import { fitImage, imageFile } from '../hooks/latex'
import { parse } from '../hooks/markdown'
import { diagramPalette, PIE_ROW_PX } from '../hooks/mermaid'
import { PRESETS } from '../hooks/presets'
import { startSession } from './clipboard-env'

const PNG_160x80 = 'iVBORw0KGgoAAAANSUhEUgAAAKAAAABQAQAAAAC2JkOZAAAAFklEQVR42mNgGAWjYBSMglEwCgYeAAAGkAAB8Q2GVgAAAABJRU5ErkJggg=='
const KITTY = { TERM: 'xterm-kitty', HOME: '/home/me' }

const reply = (text: string) => ({
  plugin: 'prismantis',
  component: 'AssistantMessage' as const,
  props: { text, isFirstOfReply: true },
  viewport: { columns: 120, rows: 40 },
  surface: 'terminal' as const,
})

const files = (on: On, found: Record<string, string> = {}, kinds: Record<string, 'file' | 'other'> = {}) => {
  const reads: string[] = []
  const unix = (path: string) => path.replace(/\\/g, '/').replace(/^[A-Za-z]:/, '')
  on('fs.stat', (_, e) => {
    const path = unix(e.path)
    return path in found || path in kinds ? { value: { kind: kinds[path] ?? 'file', size: ((found[path] ?? '').length * 3) / 4, mtimeMs: 0, isLink: false } } : { deny: `no such file ${path}` }
  })
  on('fs.read', (_, e) => {
    const path = unix(e.path)
    reads.push(path)
    return path in found ? { value: { base64: found[path]! } } : { deny: `no such file ${path}` }
  })
  return reads
}

test('a local PNG on its own line draws as an image in kitty', async ($, on) => {
  mock.env(on, KITTY)
  const reads = files(on, { '/home/me/shot.png': PNG_160x80 })

  const ui = await $.ui.mount(reply('Here:\n\n![the screenshot](~/shot.png)'))

  const image = await ui.find({ type: 'Image' })
  expect(image?.props.alt).toBe('the screenshot')
  expect(image?.props.source).toEqual({ png: PNG_160x80 })
  expect(Number(image?.props.columns) / Number(image?.props.rows)).toBe(4)
  expect(reads).toEqual(['/home/me/shot.png'])
  await ui.unmount()
})

test('a PNG data URL draws without reading a file', async ($, on) => {
  mock.env(on, KITTY)
  const reads = files(on)

  const ui = await $.ui.mount(reply(`![dot](data:image/png;base64,${PNG_160x80})`))

  expect((await ui.find({ type: 'Image' }))?.props.alt).toBe('dot')
  expect(reads).toEqual([])
  await ui.unmount()
})

test('a web image is never fetched and stays a link with its alt text', async ($, on) => {
  mock.env(on, KITTY)
  const reads = files(on)

  const ui = await $.ui.mount(reply('![build badge](https://example.com/badge.png)'))

  expect(await ui.find({ type: 'Image' })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^build badge/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /!\[/ })).toBeUndefined()
  expect(reads).toEqual([])
  await ui.unmount()
})

test('other terminals show the alt text instead of the markdown', async ($, on) => {
  mock.env(on, { TERM: 'xterm-256color', HOME: '/home/me' })
  const reads = files(on, { '/home/me/shot.png': PNG_160x80 })

  const ui = await $.ui.mount(reply('![the screenshot](~/shot.png)'))

  expect(await ui.find({ type: 'Image' })).toBeUndefined()
  expect((await ui.findAll({ type: 'Text', text: /^the screenshot$/ })).map(n => n.props.color)).toContain(PRESETS['catppuccin-mocha'].link)
  expect(await ui.find({ type: 'Text', text: /!\[|shot\.png/ })).toBeUndefined()
  expect(reads).toEqual([])
  await ui.unmount()
})

test('a file that is not a PNG, or an image inside a sentence, stays text', async ($, on) => {
  mock.env(on, KITTY)
  const reads = files(on, { '/tmp/notes.txt': btoa('just some text, not a picture at all') }, { '/tmp/pipe.png': 'other' })

  for (const text of ['![notes](/tmp/notes.txt)', '![missing](/tmp/gone.png)', '![pipe](/tmp/pipe.png)', 'see ![the shot](/tmp/notes.txt) here']) {
    const ui = await $.ui.mount(reply(text))
    expect(await ui.find({ type: 'Image' })).toBeUndefined()
    await ui.unmount()
  }
  expect(reads).toEqual(['/tmp/notes.txt'])
})

const fileLinksOn = (on: On) => on('session.version', () => ({ value: { version: '2.1.289', base: '2.1.289' } }))

test('with file links on, a file:// image line still draws as an image and links nothing', async ($, on) => {
  mock.env(on, { ...KITTY, WSL_DISTRO_NAME: 'Ubuntu' })
  fileLinksOn(on)
  files(on, { '/home/me/shot.png': PNG_160x80 })

  for (const src of ['file:///home/me/shot.png', '~/shot.png', '/home/me/shot.png']) {
    const ui = await $.ui.mount(reply(`Here:\n\n![the screenshot](${src})`))
    expect((await ui.find({ type: 'Image' }))?.props.alt).toBe('the screenshot')
    expect(await ui.findAll({ type: 'Link' })).toHaveLength(0)
    await ui.unmount()
  }
})

test('with file links on, an image in a terminal without kitty graphics shows its alt text, not a hyperlink', async ($, on) => {
  mock.env(on, { TERM: 'xterm-256color', HOME: '/home/me', FORCE_HYPERLINK: '1' })
  fileLinksOn(on)
  files(on, { '/home/me/shot.png': PNG_160x80 })

  for (const text of ['![the screenshot](file:///home/me/shot.png)', 'see ![the screenshot](file:///home/me/shot.png) here']) {
    const ui = await $.ui.mount(reply(text))
    expect(await ui.find({ type: 'Image' })).toBeUndefined()
    expect(await ui.findAll({ type: 'Link' })).toHaveLength(0)
    expect((await ui.findAll({ type: 'Text', text: /^the screenshot$/ })).map(n => n.props.color)).toContain(PRESETS['catppuccin-mocha'].link)
    await ui.unmount()
  }
})

test('image sources resolve to local files or inline bytes only', async () => {
  expect(imageFile('file:///tmp/a%20b.png', '/h')).toEqual({ path: '/tmp/a b.png' })
  expect(imageFile('~/a.png', '/h')).toEqual({ path: '/h/a.png' })
  expect(imageFile('file://localhost/tmp/a.png', '/h')).toEqual({ path: '/tmp/a.png' })
  for (const src of ['file://host/share/a.png', 'file:////host/share/a.png', 'file://%2F%2Fhost/a.png', '//host/share/a.png', '\\\\host\\share\\a.png', '/\\host\\a.png', 'file:///tmp/%E0.png']) expect(imageFile(src, '/h')).toBeNull()
  expect(imageFile('docs/a.png', '/h')).toEqual({ path: 'docs/a.png' })
  for (const src of ['https://x.io/a.png', 'http://x.io/a.png', 'ftp://x.io/a.png', 'data:image/png;base64,abc', 'data:text/html;base64,PGh0bWw+PGh0bWw+PGh0bWw+PGh0bWw+PGh0bWw+']) expect(imageFile(src, '/h')).toBeNull()
  expect(fitImage({ width: 4000, height: 100 }, 80)).toEqual({ columns: 78, rows: 1 })
  expect(fitImage({ width: 400, height: 4000 }, 80).rows).toBe(20)
})

test('the demo carries an image sample', async () => {
  const blocks = parse(showcaseText([]), { numbers: false, paths: false })
  expect(blocks.some(b => b.kind === 'paragraph' && b.inline.length === 1 && b.inline[0]!.kind === 'image')).toBe(true)
})

const PIE = '```mermaid\npie title Pets\n  "Dogs" : 386\n  "Cats" : 85\n  "Rats" : 15\n```'

test('a round pie draws as a smooth image beside its text legend in kitty', async ($, on) => {
  mock.env(on, KITTY)
  await startSession($, on)

  const ui = await $.ui.mount(reply(PIE))

  const image = await ui.find({ type: 'Image' })
  const side = 12 * PIE_ROW_PX
  expect(image?.props.source).toEqual({ rgba: expect.any(String), width: side, height: side })
  expect([image?.props.columns, image?.props.rows]).toEqual([24, 12])
  expect(atob(String((image?.props.source as { rgba: string }).rgba)).length).toBe(side * side * 4)
  expect(await ui.find({ type: 'Text', text: /^Pets$/ })).toBeDefined()
  const texts = await ui.findAll({ type: 'Text' })
  const swatches = texts.filter(n => n.text === '██').map(n => n.props.color)
  expect(swatches).toEqual(diagramPalette(PRESETS['catppuccin-mocha']).slice(0, 3))
  expect(await ui.find({ type: 'Text', text: /▟/ })).toBeUndefined()
  await ui.unmount()
})

const textPie = async (ui: { find: (q: { type: string; text?: RegExp }) => Promise<unknown> }) => [!!(await ui.find({ type: 'Image' })), !!(await ui.find({ type: 'Text', text: /▟/ }))]

test('a round pie stays text without kitty graphics', async ($, on) => {
  mock.env(on, { TERM: 'xterm-256color', HOME: '/home/me' })
  await startSession($, on)
  const plain = await $.ui.mount(reply(PIE))
  expect(await textPie(plain)).toEqual([false, true])
  await plain.unmount()
})

test('a round pie in kitty stays text on the desktop and while its block is open', async ($, on) => {
  mock.env(on, KITTY)
  await startSession($, on)
  for (const mounted of [{ ...reply(PIE), surface: 'desktop' as const }, reply(PIE.replace(/```$/, ''))]) {
    const ui = await $.ui.mount(mounted)
    expect((await textPie(ui))[0]).toBe(false)
    await ui.unmount()
  }
})

for (const linkColor of ['cyan', 'blueBright', 'ansi256(12)']) test(`a round pie stays text when a slice color is the terminal's own ${linkColor}`, { options: { linkColor } }, async ($, on) => {
  mock.env(on, KITTY)
  await startSession($, on)
  const ui = await $.ui.mount(reply(PIE))
  expect(await textPie(ui)).toEqual([false, true])
  await ui.unmount()
})

for (const [name, env, options] of [
  ['under tmux', { ...KITTY, TMUX: '/tmp/tmux-501/default,1,0' }, {}],
  ['in a mirrored layout', KITTY, { rtl: 'iterm' }],
] as const) test(`a round pie in kitty stays text ${name}`, { options }, async ($, on) => {
  mock.env(on, env)
  await startSession($, on)
  const ui = await $.ui.mount(reply(PIE))
  expect(await textPie(ui)).toEqual([false, true])
  await ui.unmount()
})

test('a round pie with Hebrew labels stays text in Ghostty, so the legend keeps its reordering', async ($, on) => {
  mock.env(on, { TERM_PROGRAM: 'ghostty', TERM: 'xterm-ghostty', HOME: '/home/me' })
  await startSession($, on)
  const ui = await $.ui.mount(reply(PIE.replace('"Dogs"', '"כלבים גדולים"')))
  expect(await textPie(ui)).toEqual([false, true])
  expect(await ui.find({ type: 'Text', text: /םילודג םיבלכ/ })).toBeDefined()
  await ui.unmount()
})

test('pie pixels take their slice color, fade at the rim and stay clear outside the circle', () => {
  const side = 100
  const px = pieRgba([0.25, 1], [[255, 0, 0], [0, 0, 255]], side)
  const at = (x: number, y: number) => [...px.subarray((y * side + x) * 4, (y * side + x) * 4 + 4)]
  expect(at(75, 25)).toEqual([255, 0, 0, 255])
  expect(at(25, 75)).toEqual([0, 0, 255, 255])
  expect(at(0, 0)).toEqual([0, 0, 0, 0])
  const alphas = Array.from({ length: side * side }, (_, i) => px[i * 4 + 3]!)
  expect(alphas.some(a => a > 0 && a < 255)).toBe(true)
})

test('the image cache keeps about 32 MB of pictures and reads an evicted one again', async ($, on) => {
  mock.env(on, KITTY)
  const head = PNG_160x80.replace(/=+$/, '')
  const big = head + 'A'.repeat(2_600_000 - head.length)
  const paths = Array.from({ length: 18 }, (_, i) => `/home/me/big${i}.png`)
  const reads = files(on, Object.fromEntries(paths.map(path => [path, big])))

  for (const path of [...paths, paths[17]!, paths[0]!]) {
    const ui = await $.ui.mount(reply(`![shot](${path})`))
    expect(await ui.findAll({ type: 'Image' })).toHaveLength(1)
    await ui.unmount()
  }

  expect(reads.filter(path => path === paths[0])).toHaveLength(2)
  expect(reads.filter(path => path === paths[17])).toHaveLength(1)
})
