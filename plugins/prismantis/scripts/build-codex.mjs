import { build } from 'esbuild'
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const out = join(root, 'codex')

const bundled = await build({
  stdin: {
    contents: `export { HINT, showcaseText } from './hooks/help'
export { FIGURE_HINT } from './hooks/figure'
export { PRESETS, PRESET_NAMES } from './hooks/presets'
export { PRISM_COLORS } from './hooks/render'`,
    resolveDir: root,
    loader: 'ts',
  },
  bundle: true,
  write: false,
  format: 'esm',
  platform: 'node',
  external: ['claude-code'],
  logLevel: 'error',
})
const cc = await import(`data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].text).toString('base64')}`)

const CODEX = [
  'This session runs in OpenAI Codex, not Claude Code. The notes after this paragraph are what prismantis tells Claude in Claude Code; follow them with these Codex differences.',
  'Codex draws markdown tables, headings, lists, links and fenced code itself, and mermaid only for flowchart, sequenceDiagram, stateDiagram-v2, classDiagram and erDiagram. Any other mermaid kind prints as source, so draw it as a figure instead.',
  'Codex also prints a diagram as source when it is wider than the terminal or a label, message or note holds ; or quotes or HTML: use flowchart TD past 4 steps, at most 4 nodes side by side, labels under 20 characters, and sequence diagrams with at most 4 one-word participants and messages under 16 characters.',
  'A figure block prints as written in a plain code block, so leave out the {role:text} color markup. There are no copy buttons and GitHub alerts draw as plain quotes.',
].join(' ')

const TEXTMATE = {
  comment: ['comment'], prolog: ['meta.preprocessor'], doctype: ['meta.tag.sgml.doctype'], cdata: ['string.unquoted.cdata'],
  string: ['string'], char: ['constant.character'], 'template-string': ['string.template'], 'attr-value': ['string.quoted.attribute-value'], url: ['markup.underline.link'],
  number: ['constant.numeric'], boolean: ['constant.language'], constant: ['constant', 'variable.other.constant'], symbol: ['constant.other.symbol'], inserted: ['markup.inserted'],
  keyword: ['keyword', 'storage', 'storage.type', 'storage.modifier'], important: ['keyword.other.important'], atrule: ['keyword.control.at-rule'], rule: ['keyword.other.rule'], deleted: ['markup.deleted'],
  function: ['entity.name.function', 'support.function'], 'class-name': ['entity.name.type', 'entity.name.class', 'support.type', 'support.class'], builtin: ['support.function.builtin'], key: ['support.type.property-name'], selector: ['entity.name.selector'],
  property: ['variable.other.property'], tag: ['entity.name.tag'], 'attr-name': ['entity.other.attribute-name'], variable: ['variable'], regex: ['string.regexp'],
}
const EXTRA = { inlineCode: ['markup.inline.raw.string.markdown', 'markup.raw.inline.markdown'], heading: ['markup.heading'], strong: ['markup.bold'], emphasis: ['markup.italic'], quote: ['markup.quote'], bullet: ['markup.list'], link: ['markup.underline.link'] }

const rule = (scopes, fg) => `\t\t<dict><key>scope</key><string>${scopes.join(', ')}</string><key>settings</key><dict><key>foreground</key><string>${fg}</string></dict></dict>`
const tmTheme = (name, t) => {
  const rules = []
  for (const [prism, slot] of Object.entries(cc.PRISM_COLORS)) if (t[slot] && TEXTMATE[prism]) rules.push(rule(TEXTMATE[prism], t[slot]))
  for (const [slot, scopes] of Object.entries(EXTRA)) if (t[slot]) rules.push(rule(scopes, t[slot]))
  const fg = t.codeText ? `<key>foreground</key><string>${t.codeText}</string>` : ''
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>name</key><string>${name}</string>
\t<key>settings</key>
\t<array>
\t\t<dict><key>settings</key><dict>${fg}</dict></dict>
${rules.join('\n')}
\t</array>
</dict>
</plist>
`
}

const skill = (name, description, body) => `---\nname: ${name}\ndescription: ${description}\n---\n\n${body}`

rmSync(out, { recursive: true, force: true })
const write = (path, text) => {
  mkdirSync(dirname(join(out, path)), { recursive: true })
  writeFileSync(join(out, path), text)
}

write('hint.md', `${CODEX}\n\n${cc.HINT}\n\n${cc.FIGURE_HINT}\n`)
write('hooks.json', `${JSON.stringify({ hooks: { SessionStart: [{ hooks: [{ type: 'command', command: 'cat "$PLUGIN_ROOT/codex/hint.md"', commandWindows: 'type "%PLUGIN_ROOT%\\codex\\hint.md"' }] }] } }, null, 2)}\n`)
const DEMO_NOTE = '> This is the Claude Code demo. In Codex, copy buttons, tool rows, diff cards, alert boxes, heading styles, prose colors, figures and charts are not drawn yet: see codex/README.md in the prismantis repo.'
write('skills/prismantis/SKILL.md', skill('prismantis', 'Show the prismantis demo. Use when the user runs $prismantis or asks what prismantis is or does.',
  `Reply with exactly the markdown between the START and END lines, nothing before or after it.\n\nSTART\n${DEMO_NOTE}\n${cc.showcaseText(cc.PRESET_NAMES)}END\n`))
for (const name of cc.PRESET_NAMES) write(`skills/prismantis-themes/themes/prismantis-${name}.tmTheme`, tmTheme(`prismantis-${name}`, cc.PRESETS[name]))
write('skills/prismantis-themes/SKILL.md', skill('prismantis-themes', 'Install the prismantis color themes for code and diagrams. Use when the user runs $prismantis-themes or asks for prismantis themes in Codex.',
  `Copy every .tmTheme file from the themes folder next to this SKILL.md into "\${CODEX_HOME:-$HOME/.codex}/themes", creating that folder if needed, with one shell command. Then reply in one line: the themes are installed, and /theme picks one (they are named prismantis-<theme>, ${cc.PRESET_NAMES.length} of them).\n`))

write('README.md', [
  '# prismantis for Codex',
  '',
  'Codex has no way for a plugin to redraw replies, so prismantis in Codex does two things: it gives Codex the same session note as Claude Code, so replies come back with tables, diagrams and figures, and it ships the ' + cc.PRESET_NAMES.length + ' prismantis themes as Codex syntax themes.',
  '',
  '| Codex alone | With prismantis |',
  '|---|---|',
  '| ![Codex in its default colors](../docs/compare/codex-before.png) | ![Codex in prismantis-dracula](../docs/compare/codex-after.png) |',
  '',
  '## Install',
  '',
  '```bash',
  'codex plugin marketplace add NahumLitvin/prismantis && codex plugin add prismantis@prismantis',
  '```',
  '',
  'Trust its hook once in `/hooks`, run `$prismantis-themes` to install the themes, and pick one with `/theme`. `$prismantis` prints the demo.',
  '',
  '## What works',
  '',
  'Full parity with Claude Code waits on two Codex issues. [openai/codex#53662](https://github.com/openai/codex/issues/53662), theme colors for prose, was accepted and merged as [openai/codex#54217](https://github.com/openai/codex/pull/54217) on 2026-10-15. It is not in a Codex release yet; a Codex built from main already colors headings, italic, lists, quotes and links in the prismantis themes. [openai/codex#53663](https://github.com/openai/codex/issues/53663), plugins drawing their own fenced blocks, is open, with a proof of concept in [NahumLitvin/codex#1](https://github.com/NahumLitvin/codex/pull/1).',
  '',
  '| Feature | Codex today | After openai/codex#53662 | After openai/codex#53663 |',
  '|---|---|---|---|',
  '| Code, inline code, table headers and mermaid boxes in the theme colors | ✓ | ✓ | ✓ |',
  '| The session note: tables, diagrams and figures in replies | ✓ | ✓ | ✓ |',
  '| Headings, bold, italic, quotes, lists and links in the theme colors | | ✓ | ✓ |',
  '| Figures and xychart bar and line charts drawn | | | ✓ |',
  '| Copy buttons, tool rows, diff cards, prompt styles, alert boxes, footnotes, right-to-left text | | | |',
  '',
  'The themes already carry the prose colors, so they show up in the first Codex release that includes #54217, with no prismantis update. The last row needs Codex to let plugins redraw its interface, as Claude Code does.',
  '',
  'This folder is generated from the Claude Code source by `npm --prefix scripts run build:codex`. Edit the source, not these files.',
  '',
].join('\n'))

const manifest = JSON.parse(readFileSync(join(root, '.claude-plugin/plugin.json'), 'utf8'))
mkdirSync(join(root, '.codex-plugin'), { recursive: true })
writeFileSync(join(root, '.codex-plugin/plugin.json'), `${JSON.stringify({ name: manifest.name, version: manifest.version, description: `Themeable Codex replies: ${cc.PRESET_NAMES.length} prismantis syntax themes for code, inline code, table headers and mermaid, and a session note that gets tables, diagrams and figures into replies.`, hooks: './codex/hooks.json', skills: './codex/skills' }, null, 2)}\n`)

const market = JSON.parse(readFileSync(join(root, '.claude-plugin/marketplace.json'), 'utf8'))
const plugins = market.plugins.map(({ source, ...plugin }) => ({ ...plugin, source: { source: 'url', url: `https://github.com/${source.repo}.git`, ref: source.ref, sha: source.sha } }))
mkdirSync(join(root, '.agents/plugins'), { recursive: true })
writeFileSync(join(root, '.agents/plugins/marketplace.json'), `${JSON.stringify({ ...market, plugins }, null, 2)}\n`)
