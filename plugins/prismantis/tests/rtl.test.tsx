import { expect, mock, test } from 'claude-code/testing'

import type { Inline } from '../hooks/markdown'
import { inlineText } from '../hooks/markdown'
import { rtlShowcaseText } from '../hooks/help'
import { commentTail, flow } from '../hooks/rtl'

const measure = (s: string) => [...s].length
const plain = (text: string, columns = 100) => flow([{ kind: 'text', text }], columns, measure)
const visual = (text: string) => plain(text)?.lines.map(inlineText).join('\n')

const mount = (text: string, columns = 120) => ({
  plugin: 'prismantis',
  component: 'AssistantMessage' as const,
  props: { text, isFirstOfReply: true },
  viewport: { columns, rows: 40 },
  surface: 'terminal' as const,
})

test('pure Hebrew reverses and takes a right base', async () => {
  expect(plain('שלום')?.base).toBe('R')
  expect(visual('שלום')).toBe('םולש')
})

test('a Latin run inside Hebrew keeps its own order', async () => {
  expect(visual('שלום Warp')).toBe('Warp םולש')
  expect(visual('שרת web-server רץ על פורט')).toBe('טרופ לע ץר web-server תרש')
})

test('hyphen and percent around a number follow the Hebrew base', async () => {
  expect(visual('שרתים ו-100% פעילים')).toBe('םיליעפ 100%-ו םיתרש')
})

test('parentheses mirror inside a Hebrew line', async () => {
  expect(visual('שרתים (east ו-west) פעילים')).toBe('םיליעפ (west-ו east) םיתרש')
})

test('inline code and paths stay one left-to-right unit inside Hebrew', async () => {
  const nodes: Inline[] = [{ kind: 'text', text: 'מחליפים עם ' }, { kind: 'code', text: '/prismantis theme nord' }, { kind: 'text', text: ' ו-' }, { kind: 'path', text: '~/app/main.ts' }]
  const line = flow(nodes, 100, measure)?.lines[0]
  expect(line?.find(n => n.kind === 'code')).toEqual({ kind: 'code', text: '/prismantis theme nord' })
  expect(line?.find(n => n.kind === 'path')).toEqual({ kind: 'path', text: '~/app/main.ts' })
})

test('a percent sign stays on the right of its number', async () => {
  expect(visual('ירידה של 5%')).toBe('5% לש הדירי')
})

test('an English sentence with one Hebrew word stays left and flips only that word', async () => {
  const f = plain('The cluster is ready שלום now')
  expect(f?.base).toBe('L')
  expect(f?.lines.map(inlineText)).toEqual(['The cluster is ready םולש now'])
})

test('Hebrew points stay attached to their letter', async () => {
  expect(visual('שָלום')).toBe('םולשָ')
})

test('Arabic reverses and Arabic-Indic digits keep their order', async () => {
  expect(visual('مرحبا')).toBe('ابحرم')
  expect(visual('١٢٣ مرحبا')).toBe('ابحرم ١٢٣')
})

test('bold, code and links keep their style through reordering', async () => {
  const nodes: Inline[] = [
    { kind: 'strong', children: [{ kind: 'text', text: 'שלום' }] },
    { kind: 'text', text: ' עולם ' },
    { kind: 'code', text: 'kubectl' },
    { kind: 'text', text: ' ' },
    { kind: 'link', text: 'תיעוד', href: 'https://x.dev' },
  ]
  const line = flow(nodes, 100, measure)?.lines[0]
  expect(line?.map(n => n.kind)).toEqual(['dim', 'link', 'text', 'code', 'text', 'strong'])
  const strong = line?.find(n => n.kind === 'strong')
  expect(strong?.kind === 'strong' && inlineText(strong.children)).toBe('םולש')
  expect(line?.find(n => n.kind === 'code')).toEqual({ kind: 'code', text: 'kubectl' })
})

test('a long right-based paragraph wraps in reading order, each line reordered', async () => {
  const f = plain('אחד שניים שלושה ארבעה חמישה שישה שבעה', 14)
  expect(f?.lines.map(inlineText)).toEqual(['םיינש דחא', 'העברא השולש', 'השיש השימח', 'העבש'])
})

test('text with no right-to-left character takes the old path', async () => {
  expect(plain('hello world 100%')).toBeNull()
  expect(flow([{ kind: 'strong', children: [{ kind: 'text', text: 'ok' }] }], 100, measure)).toBeNull()
  expect(commentTail('ls # hello')).toBeNull()
})

test('only the comment tail of a code line is reordered', async () => {
  expect(commentTail('ls # שלום')).toEqual({ head: 'ls', marker: ' # ', tail: 'םולש' })
  expect(commentTail('// שלום עולם')).toEqual({ head: '', marker: '// ', tail: 'םלוע םולש' })
})

test('a Hebrew paragraph is right aligned and reordered', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('שלום עולם'))
  expect(await ui.find({ type: 'Text', text: /^םלוע םולש$/ })).toBeDefined()
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.alignItems === 'flex-end')).toBe(true)
  await ui.unmount()
})

test('a Hebrew paragraph wraps into right aligned lines at the viewport width', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('אחד שניים שלושה ארבעה חמישה שישה שבעה', 30))
  const lines = (await ui.findAll({ type: 'Text' })).filter(t => /[א-ת]/.test(t.text))
  expect(lines.length >= 2).toBe(true)
  await ui.unmount()
})

test('bullets move to the right end and ordered items keep their number', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('- שלום\n- עולם\n\n1. אחד\n2. שניים'))
  expect((await ui.findAll({ type: 'Text', text: /^ •$/ })).length).toBe(2)
  expect(await ui.find({ type: 'Text', text: /^ 1\.$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^ 2\.$/ })).toBeDefined()
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.justifyContent === 'flex-end')).toBe(true)
  await ui.unmount()
})

test('an English list keeps the left bullet', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('- hello\n- world'))
  expect((await ui.findAll({ type: 'Text', text: /^• $/ })).length).toBe(2)
  await ui.unmount()
})

test('table cells are reordered one by one and English cells are untouched', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('| שם | a |\n|---|---|\n| שלום | b |'))
  expect(await ui.find({ type: 'Text', text: /^םש$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^םולש$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^b$/ })).toBeDefined()
  await ui.unmount()
})

test('a Hebrew table is mirrored and right aligned, with the first column on the right', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('| לוחם | סרט |\n|---|---|\n| מנטיס | פנדה |'))
  const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text)
  expect(texts.indexOf('טרס') < texts.indexOf('םחול')).toBe(true)
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.alignSelf === 'flex-end')).toBe(true)
  await ui.unmount()
})

test('an English table with one Hebrew cell keeps its column order and side', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('| name | tag |\n|---|---|\n| web | שלום |\n| api | db |'))
  const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text)
  expect(texts.indexOf('name') < texts.indexOf('tag')).toBe(true)
  expect((await ui.findAll({ type: 'Box' })).some(b => b.key !== 'reply' && b.props.alignSelf === 'flex-end')).toBe(false)
  await ui.unmount()
})

test('a code comment is reordered and the code itself is not', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('```bash\nls -la # שלום\n```\n\n```text\nשלום\n```'))
  expect(await ui.find({ type: 'Text', text: /^ # םולש$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^ls$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^שלום$/ })).toBeDefined()
  await ui.unmount()
})

test('a highlighted comment is reordered too', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('```ts\nconst x = 1 // שלום\n```'))
  expect(await ui.find({ type: 'Text', text: /^\/\/ םולש$/ })).toBeDefined()
  await ui.unmount()
})

test('quotes and alerts put their bar and box on the right', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('> שלום\n\n> [!NOTE]\n> עולם'))
  expect(await ui.find({ type: 'Text', text: /^ │$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^םולש$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^םלוע$/ })).toBeDefined()
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.alignSelf === 'flex-end' && b.props.borderStyle === 'round')).toBe(true)
  await ui.unmount()
})

test('headings are right aligned and reordered', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('## שלום'))
  expect(await ui.find({ type: 'Text', text: /^םולש$/ })).toBeDefined()
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.alignSelf === 'flex-end')).toBe(true)
  await ui.unmount()
})

test('an English reply draws exactly as before', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount(mount('# Title\n\nplain text\n\n- item\n\n> quote'))
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.alignItems === 'flex-end' || b.props.paddingRight !== undefined)).toBe(false)
  expect(await ui.find({ type: 'Text', text: /^• $/ })).toBeDefined()
  await ui.unmount()
})

test('by default Hebrew is left exactly as written', async $ => {
  const ui = await $.ui.mount(mount('שלום עולם\n\n- אחד'))
  expect(await ui.find({ type: 'Text', text: /^שלום עולם$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^• $/ })).toBeDefined()
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.alignItems === 'flex-end' || b.props.justifyContent === 'flex-end' && b.props.paddingRight !== undefined)).toBe(false)
  await ui.unmount()
})

test('rtl off keeps Hebrew as written even in Warp', { options: { rtl: 'off' } }, async ($, on) => {
  mock.env(on, { TERM_PROGRAM: 'WarpTerminal' })
  const ui = await $.ui.mount(mount('שלום עולם'))
  expect(await ui.find({ type: 'Text', text: /^שלום עולם$/ })).toBeDefined()
  await ui.unmount()
})

test('auto reorders Hebrew in Warp', async ($, on) => {
  mock.env(on, { TERM_PROGRAM: 'WarpTerminal' })
  on('session.start', () => ({ cwd: '/tmp' }))
  await $.session.start({ cwd: '/tmp', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount(mount('שלום עולם'))
  expect(await ui.find({ type: 'Text', text: /^םלוע םולש$/ })).toBeDefined()
  await ui.unmount()
})

test('auto in kitty puts words in visual order and leaves each word for kitty to reverse', async ($, on) => {
  mock.env(on, { TERM: 'xterm-kitty', KITTY_WINDOW_ID: '1', TERM_PROGRAM: 'WarpTerminal' })
  on('session.start', () => ({ cwd: '/tmp' }))
  await $.session.start({ cwd: '/tmp', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount(mount('שלום עולם\n\n- פרוסים בשני אזורים (us-east ו-eu-west)'))
  expect(await ui.find({ type: 'Text', text: /^עולם שלום$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^\(eu-west-ו us-east\) אזורים בשני פרוסים$/ })).toBeDefined()
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.alignItems === 'flex-end')).toBe(true)
  await ui.unmount()
})

test('auto in Apple Terminal keeps the right-to-left layout and leaves the letters to its own bidi', async ($, on) => {
  mock.env(on, { TERM_PROGRAM: 'Apple_Terminal' })
  on('session.start', () => ({ cwd: '/tmp' }))
  await $.session.start({ cwd: '/tmp', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount(mount('שלום עולם'))
  expect(await ui.find({ type: 'Text', text: /^שלום עולם$/ })).toBeDefined()
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.alignItems === 'flex-end')).toBe(true)
  await ui.unmount()
})

test('auto leaves an unknown terminal alone', async ($, on) => {
  mock.env(on, { TERM_PROGRAM: 'iTerm.app' })
  on('session.start', () => ({ cwd: '/tmp' }))
  await $.session.start({ cwd: '/tmp', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount(mount('שלום עולם'))
  expect(await ui.find({ type: 'Text', text: /^שלום עולם$/ })).toBeDefined()
  await ui.unmount()
})

test('logical mode wraps in reading order and keeps every line as written', async () => {
  const f = flow([{ kind: 'text', text: 'אחד שניים שלושה ארבעה חמישה' }], 12, measure, 'logical')
  expect(f?.base).toBe('R')
  expect(f?.lines.map(inlineText)).toEqual(['אחד שניים', 'שלושה ארבעה', 'חמישה'])
})

test('auto reorders fully in Ghostty, which has no bidi of its own', async ($, on) => {
  mock.env(on, { TERM_PROGRAM: 'ghostty', TERM: 'xterm-ghostty' })
  on('session.start', () => ({ cwd: '/tmp' }))
  await $.session.start({ cwd: '/tmp', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount(mount('שלום עולם'))
  expect(await ui.find({ type: 'Text', text: /^םלוע םולש$/ })).toBeDefined()
  await ui.unmount()
})

test('detection also runs when a prompt is submitted, so a reload without session start still gets it', async ($, on) => {
  mock.env(on, { TERM_PROGRAM: 'WarpTerminal' })
  on('prompt.submit', (_, e) => ({ text: e.text, context: e.context }))
  await $.prompt.submit({ text: 'hi', wait: false, origin: { kind: 'composer' } })
  const ui = await $.ui.mount(mount('שלום עולם'))
  expect(await ui.find({ type: 'Text', text: /^םלוע םולש$/ })).toBeDefined()
  await ui.unmount()
})

test('the demo-rtl screen has every element and draws right to left', { options: { rtl: 'warp' } }, async $ => {
  const ui = await $.ui.mount({ plugin: 'prismantis', component: 'CommandOutput' as const, props: { command: 'prismantis', args: 'demo-rtl', text: rtlShowcaseText(), isErrored: false }, viewport: { columns: 120, rows: 40 }, surface: 'terminal' as const })
  expect(await ui.find({ type: 'Text', text: /^לאמשל ןימימ תירבע$/ })).toBeDefined()
  expect((await ui.findAll({ type: 'Box' })).filter(b => b.props.alignItems === 'flex-end').length >= 3).toBe(true)
  expect((await ui.findAll({ type: 'Box' })).some(b => b.props.width === '100%')).toBe(true)
  await ui.unmount()
})
