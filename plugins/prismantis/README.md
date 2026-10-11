<h1 align="center"><img src="docs/brand/banner.png" alt="prismantis" width="640"></h1>

[![ci](https://github.com/NahumLitvin/prismantis/actions/workflows/ci.yml/badge.svg)](https://github.com/NahumLitvin/prismantis/actions/workflows/ci.yml)

> Sees 16 colors. Your terminal only had 8.

Colorful, themeable replies for [Claude Code](https://claude.com/claude-code): tables, code, diagrams, charts and tool calls, in 15 themes, with copy buttons on everything.

![prismantis in a real Claude Code session: tool calls dimmed on the right and Claude on the left, your prompt in a bubble, then headings, an alert, a table, a bar chart and a flowchart](docs/demo.gif)

![prismantis on the default Catppuccin Mocha theme: a boxed title, a section heading, a table, a nested list, a flowchart, a sequence diagram, a bar chart with values and its tallest bar highlighted, a line chart, highlighted TypeScript and shell blocks, a tip alert and copy buttons](docs/screenshot.png)

## Features

| Feature | What you get |
| --- | --- |
| [Themes](#themes) | `/prismantis theme <name>` switches on the spot. 15 MIT palettes (Catppuccin, Dracula, Nord, Tokyo Night, Gruvbox, Rosé Pine, Everforest, GitHub, One Dark, Solarized) plus 20 color slots you can override |
| [Tables](#tables) | colored headers, rules, column alignment, colored numbers, sized to the terminal |
| [Code](#code) | a language header and copy button, Prism highlighting in 24 languages, shell lines colored like a prompt |
| [Diagrams and charts](#diagrams-and-charts) | flowcharts, sequence, state, class and ER diagrams, bar and line charts, one color per box, participant and bar |
| [Layout](#layout) | back-to-back tables and diagrams sit side by side and wrap on narrow terminals |
| [Copy buttons](#copy-buttons) | `[ ⧉ copy ]` on code, tables, lists and quotes, plus `⧉ art` on tables and diagrams for pasting into Slack, and `/prismantis copy` without a mouse |
| [Tool rows](#tool-rows) | `Ran gh pr view 12`, `Read ~/src/app.ts`, groups summed up as `Ran 3 commands, read 2 files`, with status dots |
| [Turn footer](#turn-footer) | `✻ Baked for 6m 20s` with the duration in the number color |
| [Slash commands](#slash-commands) | command output (`/cost`, `/context`, plugin commands) gets the same tables and code styling |
| [Other mods](#other-mods) | `$.prismantis.markdown` draws any markdown the way replies are drawn, for another mod's pane or band |
| [Diagram hints](#diagram-hints) | a short model-only note on each prompt so Claude reaches for diagrams and charts when they help |
| [Text](#text) | bold, italic, strikethrough, inline code, links, versions, durations, percentages and paths in their own colors |
| [Headings, lists, quotes](#headings-lists-quotes) | 4 heading styles, nested lists, task lists, quotes with an accent bar |
| [Your prompts](#your-prompts) | what you type draws in a rounded bubble, an accent bar or a chevron, so you can find your turns when you scroll back |
| [Right to left](#right-to-left) | Hebrew and Arabic read right to left, right aligned, with bullets, quote bars and table columns mirrored, in Warp, kitty, Apple Terminal and more |

Try it: ask Claude to print [docs/demo.md](docs/demo.md) verbatim as its whole reply. Every feature is in there.

## Install

Requires Claude Code **2.1.287** or later.

```
/plugin marketplace add NahumLitvin/prismantis
```

```
/plugin install prismantis@prismantis
```

To update, run `claude plugin marketplace update prismantis && claude plugin update prismantis@prismantis`, then `/reload` in every open session. A session keeps the version it loaded until it reloads.

Tested in the terminal on macOS; CI runs the tests on macOS, Linux and Windows. The desktop app, VS Code and mobile should work through the same mod API but have not been checked by hand yet. Turn it off any time in `/plugin`, and Claude Code's own renderer comes back. Press ctrl+o on a reply to see the original.

It's a [Claude Code mod](https://claude.com/blog/claude-code-mods) in plain TypeScript. It bundles two MIT libraries, [beautiful-mermaid](https://github.com/lukilabs/beautiful-mermaid) for diagrams and [Prism](https://github.com/PrismJS/prism) for highlighting. It makes no network calls, reads no files and runs no commands. It redraws text already on your screen and, with `diagramHints` on, attaches a short model-only note to your prompts.

### Themes

Dark: `catppuccin-mocha` (default), `dracula`, `nord`, `tokyo-night`, `gruvbox-dark`, `rose-pine`, `everforest`, `github-dark`, `one-dark`, `solarized-dark`.

Light: `catppuccin-latte`, `gruvbox-light`, `rose-pine-dawn`, `github-light`, `solarized-light`.

Switch on the spot with `/prismantis theme nord`, or run `/prismantis` for the help screen with every theme. `mono` uses no color, only bold and dim. Every palette is MIT licensed and credited in [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).

### Tables

Header cells take the `tableHeader` color, and every cell sits in a box with a double line under the header (`tableStyle`: `box`, or `rules`, `grid` and `minimal` for lighter looks), and `:---:`/`---:` alignment is honored. Numbers inside cells are colored like everywhere else. Columns shrink to fit the terminal.

### Code

Code blocks get a header row with the language on the left and a copy button on the right, and the code sits indented below with no frame, so selecting it with the mouse copies only the code.

- **Prism** highlights JavaScript, TypeScript, JSX/TSX, Python, Go, Rust, Java, Kotlin, Swift, C, C++, C#, Ruby, JSON, YAML, TOML, SQL, HTML, CSS, Dockerfile, HCL and diff: keywords, strings, numbers, comments, keys, functions and properties each get a theme color.
- **Shell** blocks (`bash`, `sh`, `zsh`, unlabeled) color the command word, `--flags`, quoted strings and `# comments`, and restart after `|`, `&&` and `;`.

### Diagrams and charts

Code blocks tagged `mermaid` draw as colored text art:

- flowcharts (`graph LR`, `graph TD`, decisions), sequence, state, class and ER diagrams
- bar and line charts with `xychart-beta`, sized to the terminal width
- each box and participant gets its own theme color, the same at both ends of a sequence diagram
- each bar gets its own color, gridlines stay dim, axis numbers use the number color

Diagrams too wide for the window, or over 80 lines, stay as code. `mermaidAscii` swaps box-drawing characters for `+ - |`. Pie charts are not supported.

### Layout

When tables and diagrams follow each other, they share a row and wrap to the next line once the terminal runs out of width. A wide terminal shows a table, a flowchart and two charts side by side.

### Copy buttons

`[ ⧉ copy ]`, drawn in Claude Code's accent color, sits on code blocks, tables, lists and quotes and puts the raw markdown on your clipboard. Quotes copy without their `> ` markers, ready to paste as a message. Diagrams get two: `⧉ source` copies the mermaid code and `⧉ art` copies the drawn art, ready to paste into a chat code block. Tables get `⧉ art` too: a plain boxed table that reads right in Slack, where pasted markdown does not. Replies end with `⧉ copy reply`, which copies the reply as Claude wrote it (one-line English narration gets none). Use it for Hebrew and Arabic: selecting right-to-left text on screen copies the letters in the order they are drawn, not the order they are read. Clicking works where the terminal passes clicks through (fullscreen mode does); terminals with copy-on-select, such as Warp, may grab the word "copy" instead. Without a mouse, `/prismantis copy` copies the last reply and `/prismantis copy code` its last code block. Since Claude Code 2.1.291 `ctrl+x` then `tab` focuses the area above the prompt, not the buttons in replies.

### Tool rows

Each tool call draws as one line: a bold verb and its target, `Ran` with a colored shell command, `Read` and `Edited` with the path. The dot is green when done, hollow while running and red on failure. Output still draws below. Collapsed groups draw one line too, `Ran 3 commands, read 2 files · last: npm test`, with a red count when any call failed. Expand a group (ctrl+o or `--verbose`) and its calls draw with Claude Code's own rows, inline output included.

`toolStyle` keeps tool rows apart from what Claude says. The default, `chat`, puts them dimmed on the right, like the other side of a chat, and leaves Claude's sentences on the left. Rows are capped at 60% of the width.

![chat: tool rows dimmed on the right](docs/tools/chat.png)

`tree-dim` tucks them under the sentence with `⎿` and dims them.

![tree-dim: tool rows tucked under with ⎿](docs/tools/tree-dim.png)

`tree-bold` is `tree-dim` with one-line sentences in bold.

![tree-bold: one-line sentences in bold](docs/tools/tree-bold.png)

`classic` is the original look: a bold verb and a status dot, at full brightness.

![classic: bold verb and status dot](docs/tools/classic.png)

### Turn footer

The line that closes a turn keeps Claude Code's word and colors the duration: `✻ Baked for 6m 20s`. Terminal only, since that's the only surface that draws it.

### Slash commands

Output from slash commands, built-in or from other plugins, is parsed as markdown and drawn like a reply, copy buttons included. Errors keep Claude Code's own red line.

### Other mods

A mod that draws markdown in its own pane or band can have prismantis draw it, in the user's theme, by calling `$.prismantis.markdown` with the surface, the text and the columns it has.

- It answers the tree to draw, or `undefined` when prismantis is disabled or the text holds nothing to draw.
- It throws when prismantis isn't installed, so call it in a `try`.
- `columns` is the width of your content. Prismantis draws at least 20 columns wide.
- Theme, RTL and number and path highlighting follow the user's prismantis settings.
- Copy buttons are left out, because a button can't cross from one mod to another.

```tsx
let drawn
try {
  drawn = await $.prismantis.markdown({ surface: e.surface, text, columns: e.props.bodyColumns })
} catch {}
return drawn ?? <Markdown text={text} />
```

The types are in [types/index.d.ts](types/index.d.ts). List prismantis under `dependencies` in your `plugin.json` to have Claude Code lay them into your `.claude-plugin/types/`. When prismantis is optional, declare the noun in your own contract instead:

```ts
declare module 'claude-code' {
  interface EngineInterface {
    prismantis: {
      markdown: (args: { surface: RenderSurface; text: string; columns: number }) => Promise<RenderElement | undefined>
    }
  }
}
```

### Diagram hints

Claude rarely writes a chart unless it knows the terminal can draw one. With `diagramHints` on (the default), prismantis attaches a short note to each prompt you type, read by the model and never shown, saying tables, alerts, code, mermaid diagrams and `xychart-beta` charts render here and to use one when a numeric series or a flow is easier to see than read. It also asks for commands in fenced blocks, since only those get a copy button. It costs about 190 tokens per prompt. It's off whenever `mermaid` is off, and skipped for headless `claude -p` runs and background notifications. Claude Code doesn't let installed plugins edit the system prompt (its built-in `sec-default` policy keeps that for the organization), so the note rides along with your prompt instead.

### Text

**Bold**, *italic*, ~~strikethrough~~, `inline code`, links and bare URLs, clickable as terminal hyperlinks (where the terminal has none, the URL shows dimmed after the text). Numbers, versions (`v2.14.0`), durations (`250ms`, `3h`), sizes (`16Gi`) and percentages (`99.9%`) take the number color, and paths like `~/src/app.ts` the path color.

### Headings, lists, quotes

`headingStyle` picks `banner` (the default: a box around H1, a heavy rule under H2), `bold`, `underline` or `uppercase`. Terminals have one font size, so headings stand out through style and color. Lists keep their numbers and nest with `•` and `◦`. Quotes get an accent bar, and GitHub alerts (`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`) draw as colored boxes. Single-series bar charts print each value above its bar and color the tallest one.

Task lists draw as `[ ]` and `[✓]`, with done items dimmed and struck through. `taskStyle` switches to `ticks` (`○` `✓`), `box` (`□` `✓`) or `progress`, which adds a done-count bar above each list.

![A task list with done items struck through](docs/task-lists.png)

### Your prompts

What you type, at the prompt or through Remote Control, draws in the theme's colors. `promptStyle` picks the look, and `off` keeps Claude Code's own. Task notifications and teammate messages are left alone.

| `bubble` (default) | `bar` | `chevron` |
|---|---|---|
| ![a prompt in a rounded box](docs/prompts/bubble.png) | ![a prompt with an accent bar](docs/prompts/bar.png) | ![a prompt with a bold chevron](docs/prompts/chevron.png) |

### Right to left

![Hebrew drawn right to left](docs/rtl.png)

Hebrew and Arabic blocks are right aligned, with bullets, numbers and quote bars on the right and table columns mirrored, while code, numbers, paths and links stay left to right inside them. Terminals differ in how they treat right-to-left letters, so prismantis detects yours and sends the letters the way it needs them. `/prismantis demo-rtl` shows every element, and the `rtl` option forces a terminal's handling or turns it off.

## Configure

Open `/config` and look for the **prismantis** rows, or set values in `~/.claude/settings.json`:

```json
{
  "pluginConfigs": {
    "prismantis": {
      "theme": "tokyo-night",
      "tableStyle": "grid",
      "headingStyle": "banner",
      "tableHeaderColor": "#ffcc00",
      "numberColor": "cyan"
    }
  }
}
```

| Option | Values | Default |
| --- | --- | --- |
| `enabled` | `true`, `false` | `true` |
| `theme` | see [Themes](#themes) | `catppuccin-mocha` |
| `tableStyle` | `box`, `rules`, `grid`, `minimal` | `box` |
| `taskStyle` | `checks` (`[ ]` `[✓]`, done struck through), `ticks` (`○` `✓`), `box` (`□` `✓`), `progress` (ticks with a done-count bar) | `checks` |
| `promptStyle` | `bubble`, `bar`, `chevron`, `off` | `bubble` |
| `headingStyle` | `banner`, `bold`, `underline`, `uppercase` | `banner` |
| `highlightNumbers` | `true`, `false` | `true` |
| `highlightPaths` | `true`, `false` | `true` |
| `toolRows` | `true`, `false` | `true` |
| `toolStyle` | `chat`, `tree-dim`, `tree-bold`, `classic` | `chat` |
| `copyButtons` | `true`, `false` | `true` |
| `diagramHints` | `true`, `false` | `true` |
| `rtl` | `auto`, a terminal (`warp`, `kitty`, `apple-terminal`, `iterm`, `ghostty`, `wezterm`, `vscode`, `alacritty`, `windows-terminal`, `gnome`, `konsole`), `off` | `auto` |
| `mermaid` | `true`, `false` | `true` |
| `mermaidAscii` | `true`, `false` | `false` |
| `<token>Color` | any color, see below | theme |

A color is hex (`#a6e3a1`, `#fc0`), `rgb(166,227,161)`, `ansi256(114)` or a name (`green`, `cyanBright`). Values that don't parse are ignored. Every token has a `<token>Color` option and a row in `/config`:

| Token | Colors |
| --- | --- |
| `accent` | reply bullet, H3+ headings, quote bar, running tool dots |
| `heading` | H1 and H2 |
| `strong` | **bold** text |
| `emphasis` | *italic* text, variables, attribute names |
| `inlineCode` | `inline code` |
| `codeText` | code block text |
| `codeCommand` | shell commands, functions, class names, keys |
| `codeFlag` | `--flags`, keywords, failures |
| `codeString` | strings |
| `codeComment` | comments, the code block's language label |
| `link` | links, URLs, properties, tags |
| `path` | file paths, regexes |
| `number` | numbers, versions, durations, done dots |
| `quote` | quote text |
| `rule` | rules, chart gridlines |
| `tableHeader` | table header cells |
| `tableRule` | table rules |
| `bullet` | list bullets and numbers |
| `diagram` | diagram lines |
| `diagramText` | diagram labels |

## Limits

- The parser covers what Claude writes (headings, lists, tables, fences, quotes, emphasis, links). It's not full CommonMark: nested quotes and HTML draw as plain text.
- Widths count CJK and emoji as two columns. Terminals disagree on a few emoji, so those can still be off by one.- Languages outside the 24 above draw in `codeText`.

## Roadmap

Planned features are on the [roadmap board](https://github.com/users/NahumLitvin/projects/2), one issue each. Give an issue a 👍 to vote for it, or open one for what you miss.

## Develop

```
git clone https://github.com/NahumLitvin/prismantis
claude --plugin-dir ./prismantis
```

Edits hot-reload in that session. Before a PR run `claude plugin validate .` and `claude plugin test .`, and print [docs/demo.md](docs/demo.md) to check the look. `npm --prefix scripts run bench` times a full render of the demo reply, so speed claims can be checked on any machine. CI also type-checks, rebuilds the vendored bundles byte for byte and installs from a clean config. See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## Author

Built by [Nahum Litvin](https://github.com/NahumLitvin), who writes about running untrusted code in production at [catchkill9.dev](https://www.catchkill9.dev/).

## License

[MIT](LICENSE). Bundled third-party code is listed in [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).
