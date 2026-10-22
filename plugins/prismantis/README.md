<h1 align="center"><img src="docs/brand/banner.png" alt="prismantis" width="640"></h1>

<p align="center"><em>Sees 16 colors. Your terminal only had 8.</em></p>

<p align="center">
  <a href="https://github.com/NahumLitvin/prismantis/releases"><img src="https://img.shields.io/github/v/release/NahumLitvin/prismantis?style=flat-square&color=cba6f7" alt="Release"></a>
  <a href="https://github.com/NahumLitvin/prismantis/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/NahumLitvin/prismantis/ci.yml?branch=main&style=flat-square&label=ci" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/NahumLitvin/prismantis?style=flat-square&color=cba6f7" alt="License"></a>
  <img src="https://img.shields.io/badge/Claude%20Code-2.1.287%2B-cba6f7?style=flat-square" alt="Claude Code 2.1.287 or later">
  <a href="https://github.com/hesreallyhim/awesome-claude-code"><img src="https://awesome.re/mentioned-badge.svg" alt="Mentioned in Awesome Claude Code"></a>
  <a href="https://statuslin.es/mods/prismantis"><img src="https://img.shields.io/badge/listed%20on-statuslin.es-c96442?style=flat-square" alt="Listed on statuslin.es"></a>
</p>

<p align="center">
  <a href="#install"><strong>Install</strong></a> ·
  <a href="#themes">Themes</a> ·
  <a href="#features">Features</a> ·
  <a href="#configure">Configure</a> ·
  <a href="docs/CHANGELOG.md">Changelog</a>
</p>

![Plain Claude Code replies wiping into prismantis: a table, a bar chart and a mermaid flowchart](docs/tour.gif)

<sub>Same prompt, same model: plain Claude Code, then with prismantis. <a href="https://github.com/user-attachments/assets/7f4744fc-ca52-4ea3-adb3-43467190dc62">▶ Watch the full 44-second tour</a> (tables, charts, diagrams, diffs, callouts, right-to-left text).</sub>

## TL;DR

- Claude Code prints mermaid as source and tool calls as walls of text. prismantis draws them: real charts and flowcharts, typeset LaTeX math in kitty and Ghostty, colored tables and code, and quiet tool rows.
- 15 palettes plus `mono`, and copy buttons on everything.
- Two commands to install, `/plugin` to turn it off. Claude Code's own renderer comes back the moment you do.
- No network calls. It runs a program only when you click `⧉ html` (the clipboard helper) or turn on LaTeX (RaTeX's renderer).

```
/plugin marketplace add NahumLitvin/prismantis
```

```
/plugin install prismantis@prismantis
```

Then run `/prismantis setup` to pick a theme and styles from drawn samples, and `/prismantis demo` for a tour of the main features. In a terminal, setup opens a pane: the arrows or Tab move through the styles of a step with a preview of the one in focus, Enter saves it and shows the next step. Where the session has no terminal, as in the desktop app, it walks the same steps in the transcript.

## Install

Requires Claude Code **2.1.287** or later. Run the two commands above.

To update, run this, then `/reload` in every open session. A session keeps the version it loaded until it reloads.

```bash
claude plugin marketplace update prismantis && claude plugin update prismantis@prismantis
```

To uninstall:

```bash
claude plugin uninstall prismantis@prismantis
```

For LaTeX math, install RaTeX's renderer and set `latex` to `true`; see [LaTeX math](#latex-math). Until then formulas draw as text.

### Codex

prismantis also runs in Codex, with themes for code, tables and diagrams and the same session note. Install, what works today, and the two Codex issues it waits on for parity: [codex/README.md](codex/README.md).

## Features

| Feature | What you get |
| --- | --- |
| [Themes](#themes) | `/prismantis theme <name>` switches on the spot. 16 themes and 20 color slots you can override |
| [Tables](#tables) | colored headers, rules, column alignment, colored numbers, sized to the terminal |
| [Code](#code) | a language header and copy button, Prism highlighting in two dozen languages, shell lines colored like a prompt |
| [Diagrams and charts](#diagrams-and-charts) | flowcharts, sequence, state, class and ER diagrams, bar and line charts, one color per box, participant and bar |
| [Figures](#figures) | ` ```figure ` text pictures drawn as written in the theme's colors, for timelines, layouts and before and after; glyphs and markup checked before they are drawn |
| [LaTeX math](#latex-math) | `$$` and ` ```math ` formulas typeset as images in kitty and Ghostty by [RaTeX](https://github.com/erweixin/RaTeX), text everywhere else |
| [Layout](#layout) | back-to-back tables and diagrams sit side by side and wrap on narrow terminals |
| [Copy buttons](#copy-buttons) | `⧉ md`, `⧉ art` and `⧉ html` on tables, `[ ⧉ copy ]` on code, lists and quotes, `/prismantis copy` without a mouse |
| [Tool rows](#tool-rows) | `Ran gh pr view 12`, `Read ~/src/app.ts`, groups summed up as `Ran 3 commands, read 2 files`, with status dots; `toolOutput: quiet` hides what Claude only read and says in plain words what each call did |
| [Turn footer](#turn-footer) | `✻ Baked for 6m 20s` with the duration in the number color |
| [Slash commands](#slash-commands) | command output (`/cost`, `/context`, plugin commands) gets the same tables and code styling |
| [Diagram hints](#diagram-hints) | a short model-only note on each prompt so Claude reaches for diagrams, charts and figures when they help, and builds explaining replies around the pictures |
| [Text](#text) | bold, italic, strikethrough, inline code, links, versions, durations, percentages and clickable paths in their own colors |
| [Headings, lists, quotes](#headings-lists-quotes) | 4 heading styles, nested lists, task lists, quotes with an accent bar |
| [Your prompts](#your-prompts) | what you type draws in a bubble, an accent bar or a chevron, so you find your turns when you scroll back, and `clock` adds when you sent it and when the turn finished |
| [Right to left](#right-to-left) | Hebrew and Arabic read right to left, with bullets, quote bars and table columns mirrored |
| [Other mods](#other-mods) | `$.prismantis.markdown` draws any markdown the way replies are drawn, for mod authors |

### Themes

![The same reply in all 15 color themes, ten dark and five light: a tip box, a task list, a flowchart and a bar chart](docs/themes.png)

![Random theme: plain Claude Code on the left, prismantis with theme random on the right](docs/compare/random-theme.png)

Dark: `catppuccin-mocha` (default), `dracula`, `nord`, `tokyo-night`, `gruvbox-dark`, `rose-pine`, `everforest`, `github-dark`, `one-dark`, `solarized-dark`.

Light: `catppuccin-latte`, `gruvbox-light`, `rose-pine-dawn`, `github-light`, `solarized-light`.

`mono` drops the palette for bold and dim; alerts keep their colors. Switch with `/prismantis theme nord`, or run `/prismantis` for the help screen with every theme. Every palette is MIT licensed and credited in [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).

### Tables

![Tables: plain Claude Code on the left, prismantis on the right](docs/compare/tables.png)

Header cells take the `tableHeader` color, and the default `box` style puts a double line under the header. `tableStyle` picks `box` (the default, every cell boxed), `rules`, `grid` or `minimal`. `:---:` and `---:` alignment is honored, numbers in cells get the number color, and columns shrink to fit the terminal.

### Code

![Code: plain Claude Code on the left, prismantis on the right](docs/compare/code.png)

![Code fold: plain Claude Code on the left, prismantis numbering and folding a 45 line block on the right](docs/compare/code-fold.png)

Each code block gets a header row: the language on the left, a copy button on the right. The code sits indented below with no frame, so selecting it with the mouse copies only the code.

- **Prism** highlights JavaScript, TypeScript, JSX/TSX, Python, Go, Rust, Java, Kotlin, Swift, C, C++, C#, Ruby, JSON, YAML, TOML, SQL, HTML, CSS, Dockerfile, HCL, Lua and diff.
- **Shell** blocks (`bash`, `sh`, `zsh`, `fish`, `powershell`, unlabeled) color the command word, `--flags`, quoted strings and `# comments`, and restart after `|`, `&&` and `;`.

### Diagrams and charts

![Diagrams and charts: plain Claude Code on the left, prismantis on the right](docs/compare/diagrams.png)

![Diagrams and charts: plain Claude Code on the left, prismantis on the right](docs/compare/charts.png)

![Diagram too wide: plain Claude Code on the left, prismantis falling back to the source with a note on the right](docs/compare/fallback-note.png)

Code blocks tagged `mermaid` draw as colored text art:

- flowcharts (`graph LR`, `graph TD`, decisions), sequence, state, class and ER diagrams
- bar and line charts with `xychart-beta`, sized to the terminal width
- `pie` charts as a circle with a colored legend, largest slice first, and `gantt` schedules as bars on a shared date or time axis, starting on a half cell and ending on an eighth so close durations draw apart
- each box and participant gets its own theme color, the same at both ends of a sequence diagram
- bars in a multi-series chart get their own colors; a single-series chart prints each value above its bar and colors the tallest one
- gridlines stay dim, axis numbers use the number color

`pieStyle` picks how a pie draws. `round` falls back to bars in ascii mode, with more slices than the theme has distinct colors (mono always) or in a narrow terminal:

| `round` (default) | `bars` |
|---|---|
| a circle, each slice in its own color, with a legend | one bar per slice, largest first, with its share |
| ![round](docs/pies/round.png) | ![bars](docs/pies/bars.png) |

![A round pie of visitors by referrer with a colored legend, beside a gantt chart of a week of releases on a shared date axis](docs/pies/pie-and-gantt.png)

Diagrams too wide for the window, or over 80 lines, stay as code. `mermaidAscii` swaps box-drawing characters for `+ - |`.

### Figures

Some things read better as a picture than as a diagram: a timeout racing a retry, the layout of a screen, a system before and after a change. Code blocks tagged `figure` draw line by line as written, in the theme's colors:

![A figure drawn by prismantis: a time axis with ticks at 0, 10 and 12 s, the provider bar timing out at 10 s, the handler bar finishing at 12 s, and bookings going from 0 to 1 to 2](docs/figure.png)

<details>
<summary>The markdown Claude wrote for it</summary>

````markdown
```figure
{dim:timeout at 10 s, handler books at 12 s, retry books again}
          {note:0 s}           {note:10 s}  {note:12 s}              {note:later}
          {accent:▏─────────────▏─────▏─────────────────▏}
Provider  {accent:██████████████}{warn:✗} timeout               {accent:█} retry
Handler   {ok:████████████████████} 200, nobody waits
Bookings  0                   {ok:1}                 {warn:2 twice}
```
````

</details>

- `{role:text}` colors a run: `accent` for frames, lines and arrows (diagram color), `warn` for the break or the risk, `ok` for what is healthy or done, `note` for time and effort, `dim` for side notes (comment color), `strong` for the one thing that matters (strong color); the rest takes the diagram text color. `warn`, `ok` and `note` take the theme's reddest, greenest and most amber accent color, each a different one and none the diagram color, so a risk never looks like a frame line in any theme; hex and `rgb()` colors you set take part in that pick, and a role whose own slot (flag, string or heading color) you set to a color name or `ansi256()` keeps that color
- ▶ and ◀ draw as ► and ◄, as in diagrams, so no glyph turns into an emoji; in `mono`, `warn` draws bold
- a figure stays a code block while it streams (so a reply that opens with a figure shows its markup until the block closes), when it has more than 80 lines, when a line is wider than the window or than 100 columns, and when a line would not draw as written: a glyph that may draw as an emoji or takes two columns, a tab, a control character, a direction mark or another character that draws no column (a zero-width space, a soft hyphen), or role markup in the wrong case, misspelled, nested or left open; once the block is closed, a dim line above it says why, such as `figure line 4: "⚠" may draw as an emoji, use a text glyph`
- frames are not checked: a box that does not close or a side, corner or divider out of its column draws as written, as Claude typed it, so a frame that is slightly off still draws
- `⧉ source` copies the block as Claude wrote it, `⧉ art` the drawn text
- figures draw whether `mermaid` is on or off; only the [diagram hints](#diagram-hints) note follows `mermaid`
- Claude learns about figures from the [diagram hints](#diagram-hints) note: prefer a figure over mermaid when position carries meaning (durations racing on a time axis, a screen layout, phases, before and after); when you ask to explain, compare or plan something and pictures would make it easier to grasp, build the reply around them, with the core on the first screen; the prose does not retell the picture; then the roles, the width and the glyphs that draw cleanly; plain flows and charts stay mermaid

### LaTeX math

![LaTeX math: plain Claude Code on the left, prismantis on the right](docs/compare/latex.png)

Display math, `$$…$$` on lines of its own or a ` ```math ` block, draws as a typeset image in the theme's diagram text color, one formula per line. With copy buttons on, its `⧉ copy` button copies the formula's LaTeX, since selecting an image copies blank cells. It needs [RaTeX](https://github.com/erweixin/RaTeX)'s PNG renderer, a single binary that typesets KaTeX syntax in a few milliseconds without TeX, a browser or Node:

```bash
gh release download -R erweixin/RaTeX -p 'ratex-cli-*-aarch64-apple-darwin.tar.gz'
tar -xzf ratex-cli-*.tar.gz
mkdir -p ~/.local/bin
install ratex-cli-*/render ~/.local/bin/ratex-render
```

Pick the archive for your platform (`x86_64-apple-darwin`, `x86_64-unknown-linux-musl`, ...). Any directory on your `PATH` works, but the file must be named `ratex-render`.

LaTeX is off until you set `latex` to `true`. Then prismantis runs `ratex-render` once in kitty and Ghostty, outside tmux, or wherever `CLAUDE_CODE_FORCE_TERMINAL_IMAGES` makes Claude Code draw images, such as a background session viewed in one of them, and keeps LaTeX on only if that test formula comes back. If a later run fails, formulas already drawn stay and new ones stay text until you `/reload`. A reply shown before the test finishes draws its formulas as text, then redraws them as images. Anywhere else, without the renderer, or with `latex` off, formulas draw as text in a `math` code block. So does a formula the renderer rejects, or one too wide for the terminal even at one row. While LaTeX is on, the [diagram hints](#diagram-hints) note also tells Claude that `$$` math renders. Inline `$…$` draws as italic text without its dollar signs, with common commands such as `\rho`, `\cdot` and `\le` shown as symbols; amounts like `$5` stay as written.

Formula text matches the reply text. A terminal image fills whole rows, so a formula that falls between two row counts is rendered again with more padding rather than stretched.

### Layout

![Layout: plain Claude Code on the left, prismantis on the right](docs/compare/layout.png)

When tables, diagrams and figures follow each other, they share a row and wrap once the terminal runs out of width. A wide terminal shows a table, a flowchart and two charts side by side.

### Copy buttons

![Copy buttons: plain Claude Code on the left, prismantis on the right](docs/compare/copy.png)

- **Tables:** `⧉ md` copies the original Markdown and `⧉ art` a boxed table that pastes well into Slack. `⧉ html` copies a formatted table (headers, alignment, inline formatting) plus a tab-separated plain-text copy.
- **Code, lists and quotes:** `[ ⧉ copy ]` on each. Code copies without its fences, lists as markdown, quotes without their `> ` markers.
- **Diagrams and figures:** `⧉ source` copies the mermaid or figure source, `⧉ art` the drawn art.
- **Whole replies:** replies with more than one block, or any Hebrew or Arabic, end with `⧉ copy reply`, which copies the reply as Claude wrote it. Selecting right-to-left text on screen copies letters in drawn order, not reading order.
- **No mouse:** `/prismantis copy` copies the last reply, `/prismantis copy code` its last code block.

`copyButtonStyle` picks where the buttons sit. `inline`, the default, is the look above. `hover` puts a dim ⧉ beside each block's first row instead, at its left on a right-to-left block, and one in the reply's bottom-right corner for the whole reply. Pointing at a ⧉ draws its buttons over it, so they take no line and nothing moves when they show; the pointer on the block itself shows nothing. ctrl+x tab does not reach a hidden button, and the mobile app, which has no pointer, draws them inline.

![copyButtonStyle hover: at rest a table, a bash block and the reply each show a dim ⧉; with the pointer on the table's ⧉, its ⧉ md, ⧉ art and ⧉ html buttons draw over the marker and the end of the header row](docs/copy/hover.png)

`⧉ html` shows in a local macOS terminal or a Linux graphical session. macOS needs nothing extra. Linux needs [CopyQ](https://copyq.readthedocs.io/en/stable/installation.html) running (see its [Wayland caveats](https://copyq.readthedocs.io/en/stable/known-issues.html#on-linux-some-features-do-not-work-under-wayland)). On Ubuntu:

```bash
sudo apt install -y copyq && copyq --start-server && copyq config autostart true
```

Clicking works where the terminal passes clicks through, as fullscreen mode does. Terminals with copy-on-select, such as Warp, may grab the word "copy" instead.

### Tool rows

![Tool rows: plain Claude Code on the left, prismantis on the right](docs/compare/tools.png)

![Diff cards: plain Claude Code on the left, prismantis on the right](docs/compare/diff-cards.png)

Each tool call draws as one line: a verb and its target, `Ran` with a colored shell command, `Read` and `Edited` with the path, which opens the file on click like a path in a reply (see [Text](#text)). A status dot shows done, running or failed, and output still draws below. Edits draw as a diff card in the theme's colors, and so do files a shell command changed (`sed -i`, a script), one card per file headed by its path. A file Write creates is no diff, as in Claude Code's own preview: `Created <path> (N lines)` heads its first 10 lines as numbered code in the theme's colors, and a click anywhere on it, title or lines, or on `+N more lines` opens the rest; `show less` or another click folds it again. A diff card or a new file's preview with lines folded away opens the same way. A file an Edit or a shell command creates shows its first 10 lines as added diff lines under the same header. A file a shell command deletes is one `Deleted <path> (N lines)` line, and a click on it opens its removed lines. A file moved unchanged is one `Renamed <old> → <new>` line. Before Claude Code 2.1.295, files Write creates keep Claude Code's own preview, a new file's lines open with a `+N more lines` button and a deleted file's with a `show N lines` button. In the desktop app a click on the code lines does nothing; the `+N more lines` button does it. In diff cards added and unchanged lines are highlighted in the file's language, removed lines stay plain as in Claude Code, and when a line is edited rather than rewritten, the words that changed get a deeper tint. `diffStyle` picks the look: `card` (default) frames the lines in a rounded box, `full` drops the box and tints each changed line across the width, `marks` drops the tint and colors only the `+` and `−` marks, and `bar` puts a colored `▌` before each changed line.

| `card` (default) | `full` | `marks` | `bar` |
|---|---|---|---|
| rounded box, tinted lines | no box, lines tinted across the width | no tint, colored `+` and `−` | no tint, a colored `▌` before each changed line |
| ![card](docs/diff/card.png) | ![full](docs/diff/full.png) | ![marks](docs/diff/marks.png) | ![bar](docs/diff/bar.png) |

Collapsed groups draw one line too: `Ran 3 commands, read 2 files · last: npm test`, with `· N failed` in the flag color when any call failed. Expand a group (ctrl+o or `--verbose`): shell calls keep their colored command with the output boxed below, and other calls use Claude Code's own rows. ctrl+o on a reply shows the original text.

`toolStyle` keeps tool rows apart from what Claude says:

| `chat` (default) | `tree-dim` | `tree-bold` | `classic` |
|---|---|---|---|
| dimmed on the right, capped at 60% of the width | tucked under the sentence with `⎿`, dimmed | `tree-dim` with one-line sentences in bold | bold verb and status dot, full brightness |
| ![chat](docs/tools/chat.png) | ![tree-dim](docs/tools/tree-dim.png) | ![tree-bold](docs/tools/tree-bold.png) | ![classic](docs/tools/classic.png) |

`toolOutput: quiet` shows what Claude did, not what it read: reads, searches and read-only shell commands draw one plain row like `Read src/report.py lines 1–10` and nothing under it. Edits keep their diff and failures show their real error; the full rules are in [docs/tool-output.md](docs/tool-output.md).

![quiet: rows say what was read, nothing drawn under reads](docs/tools/quiet.png)

### Turn footer

![Turn footer: plain Claude Code on the left, prismantis on the right](docs/compare/footer.png)

The line that closes a turn keeps Claude Code's word and colors the duration: `✻ Baked for 6m 20s`. Terminal only, since that's the only surface that draws it.

### Slash commands

Output from slash commands, built-in or from other plugins, is drawn like a reply, copy buttons included. Errors keep Claude Code's own red line.

### Diagram hints

Claude rarely writes a chart unless it knows the terminal can draw one. With `diagramHints` on (the default), each prompt you type or another plugin sends carries a short note that only the model reads. It says tables, alerts, code, mermaid diagrams and `xychart-beta` charts render here, and asks for commands in fenced blocks, since only those get a copy button. A second part describes [figures](#figures): prefer one over mermaid when position carries meaning (durations racing on a time axis, a screen layout, phases, before and after), keep mermaid for plain flows and charts, and draw none for short answers, code changes or reports; the prose never retells the picture. When you ask Claude to explain, compare or plan something and pictures would make it easier to grasp, it builds the reply around them, with the core on the first screen as a picture or a sentence. Then come the role markup, at most 74 columns so a figure fits an 80-column window, glyphs one column wide, and edge ticks `▏` for a time axis so `█` bars line up.

The note costs about 630 tokens per prompt: about 275 for the main part and about 360 for the figure part, plus about 80 while [LaTeX math](#latex-math) is on, when it also says `$$` formulas render. All three are counted with Claude's tokenizer. It's off whenever `mermaid` is off, and skipped for the prompt a headless `claude -p` run starts with and for background notifications; a prompt another plugin sends inside such a run still carries it.

### Text

![Text: plain Claude Code on the left, prismantis on the right](docs/compare/text.png)

![Footnotes: plain Claude Code on the left, prismantis on the right](docs/compare/footnotes.png)

**Bold**, *italic*, ~~strikethrough~~, `inline code`, links and bare URLs, clickable as terminal hyperlinks. Numbers, versions (`v2.14.0`), durations (`250ms`, `3h`), sizes (`16Gi`) and percentages (`99.9%`) take the number color, and paths like `~/src/app.ts` the path color.

Paths open their file or folder on click, as do `file://` links that show their own path, from Claude Code 2.1.289 on. A path that starts with `~/`, `./` or `../` links to its file, with `~` read as your home folder and `./` from the session's project folder. A path that starts with `/` links once it has two parts, like `/tmp/app.ts`, so a slash command like `/config` stays text, and so does a top folder like `/tmp`. A `:12` after a path stays text. The files in tool rows of Claude Code's own file tools (Read, Edit, MultiEdit, Write, NotebookEdit, Grep, Glob) and the headers of shell-edit diff cards link too, a one-part path like `/etc` included, to the whole path even where the row shortens it. A `file://` link shows its own path when its text, apart from trailing punctuation, is the link itself or the path the link opens: `/tmp/a.md`, `C:\Users\me\a.md` and `\\server\share\a.md` as written, or a `~/`, `./` or `../` path read as above. A link with any other text, such as `[the docs](file:///tmp/setup.command)`, draws as `the docs (file:///tmp/setup.command)` in plain text, so a reply cannot hide what a click opens behind a harmless name. Under WSL the link goes through `wsl.localhost`, so Windows Terminal opens the file from the Linux side; a Linux terminal under WSLg (GNOME Terminal, Konsole, kitty) gets plain `file:///` links, which it opens itself. Paths link only in a terminal that draws hyperlinks, judged the way Claude Code judges it (`FORCE_HYPERLINK`, Windows Terminal, iTerm2, WezTerm, kitty, Ghostty, VS Code 1.72 and later, and others), so a terminal without them never shows a URL after each path. In a session over SSH (`SSH_CONNECTION` or `SSH_TTY` set) paths and `file://` links stay text, since a file link would open a file on the computer the terminal runs on rather than the one Claude Code runs on. A link longer than the 2048 characters Claude Code draws stays text too. Paths in inline code stay plain, and the desktop app draws paths and `file://` links as before.

Programs and launchers never link, so a click on one cannot run it. A path, a tool row's file or a `file://` link whose last name ends in one of these extensions stays text, a path in the path color and a `file://` link as its text and target, and so does anything inside an `.app` bundle: on macOS `.app`, `.command`, `.tool`, `.terminal`, `.pkg`, `.mpkg`, `.mobileconfig`, `.prefPane`, `.workflow`, `.action`, `.fileloc`, `.inetloc` and `.webloc`; on Windows `.exe`, `.com`, `.scr`, `.pif`, `.cpl`, `.msi`, `.msp`, `.msu`, `.msix`, `.msixbundle`, `.appx`, `.appxbundle`, `.appinstaller`, `.application`, `.appref-ms`, `.vsix`, `.bat`, `.cmd`, `.ps1`, `.psc1`, `.vbs`, `.vbe`, `.js`, `.jse`, `.wsf`, `.wsh`, `.wsc`, `.hta`, `.chm`, `.msc`, `.reg`, `.xll`, `.wsb`, `.diagcab`, `.ahk`, `.au3`, `.lnk`, `.url`, `.scf` and `.settingcontent-ms`; on Linux `.desktop`, `.sh`, `.bash`, `.zsh`, `.csh`, `.ksh`, `.run`, `.AppImage`, `.deb`, `.rpm`, `.snap`, `.flatpak` and `.flatpakref`; and anywhere `.jar`, `.jnlp`, `.py`, `.pyw`, `.pyz`, `.pyzw`, `.pyc`, `.pl`, `.rb` and `.rbw`. Case does not matter, and neither does a trailing slash, a `?query` or `#fragment`, percent-encoding, trailing dots or spaces, or an NTFS `:stream` after the name. So `.js`, `.sh` and `.py` files in a reply or a tool row do not open on click. The check reads names only: a program without one of these extensions, such as a Unix executable with no extension, still links, and an `.html` file still opens in the browser, scripts and all.

Footnotes draw as superscript marks, with the notes under a dim rule at the end of the reply. Click a mark, in a sentence, a list, a quote or a table cell, to see its note in a toast. Point at a note to light every mark that cites it, or at a mark to light its note. Clicks and pointing work where the terminal passes the mouse through, as fullscreen mode does, and in the desktop app. They need Claude Code 2.1.295 or later; earlier versions draw the marks as before.

### Headings, lists, quotes

![Headings, lists, quotes: plain Claude Code on the left, prismantis on the right](docs/compare/headings.png)

Terminals have one font size, so headings stand out through style and color. `headingStyle` picks the look:

| `banner` (default) | `bold` | `underline` | `uppercase` |
|---|---|---|---|
| a box around H1, a heavy rule under H2 | bold in the heading color | `bold` with H1 and H2 underlined | `bold` with H1 in capitals |
| ![banner](docs/headings/banner.png) | ![bold](docs/headings/bold.png) | ![underline](docs/headings/underline.png) | ![uppercase](docs/headings/uppercase.png) |

Lists keep their numbers and nest with `•` and `◦`. Quotes get an accent bar down every line and keep their paragraphs, lists, code, tables and nested quotes, and GitHub alerts (`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`) draw as colored boxes.

Task lists draw as `[ ]` and `[✓]`, with done items dimmed and struck through. `taskStyle` switches to `ticks` (`○` `✓`), `box` (`□` `✓`) or `progress`, which adds a done-count bar above each list.

![A task list with done items struck through](docs/task-lists.png)

### Your prompts

![Your prompts: plain Claude Code on the left, prismantis on the right](docs/compare/prompts.png)

What you type, at the prompt or through Remote Control, draws in the theme's colors. `promptStyle` picks the look, and `off` keeps Claude Code's own. Task notifications and teammate messages are left alone.

| `bubble` (default) | `wide` | `bar` | `chevron` |
|---|---|---|---|
| ![a prompt in a rounded box](docs/prompts/bubble.png) | ![a prompt in a rounded box across the full width](docs/prompts/wide.png) | ![a prompt with an accent bar](docs/prompts/bar.png) | ![a prompt with a bold chevron](docs/prompts/chevron.png) |

`clock` adds the time: each prompt shows when you sent it, and the line that closes each turn when it finished (`✻ Baked for 1m 55s · 14:32`). It reads `24h` or `12h`, and a time from another day gets its date. With `promptStyle: off` the time goes in front of Claude Code's own prompt row. Off by default.

| `clock` | on a prompt | and on a turn's last line |
|---|---|---|
| `24h` | ![a prompt bubble that starts with the time it was sent](docs/clock/prompt.png) | ![a turn line that ends with the time it finished](docs/clock/turn.png) |
| `12h` | ![a prompt bubble that starts with 5:45 PM](docs/clock/prompt-12h.png) | ![a turn line that ends with 5:45 PM](docs/clock/turn-12h.png) |

### Right to left

![Right to left: plain Claude Code on the left, prismantis on the right](docs/compare/rtl.png)

Hebrew and Arabic blocks are right aligned, with bullets, numbers and quote bars on the right and table columns mirrored. Code, numbers, paths and links stay left to right inside them. Terminals treat right-to-left letters differently, so prismantis detects yours and sends the letters the way it needs them. `/prismantis demo-rtl` shows every element, and the `rtl` option forces a terminal's handling or turns it off.

## Configure

Open `/config` and look for the **prismantis** rows, or set values in `~/.claude/settings.json`:

```json
{
  "pluginConfigs": {
    "prismantis@prismantis": {
      "options": {
        "theme": "tokyo-night",
        "tableStyle": "grid",
        "headingStyle": "banner",
        "tableHeaderColor": "#ffcc00",
        "numberColor": "cyan"
      }
    }
  }
}
```

Options sit under `options`, keyed by the plugin's install name. Project settings are not read for plugin options.

| Option | Values | Default |
| --- | --- | --- |
| `enabled` | `true`, `false` | `true` |
| `theme` | see [Themes](#themes), or `random` for a new dark color preset each time the mod loads | `catppuccin-mocha` |
| `tableStyle` | `box`, `rules`, `grid`, `minimal` | `box` |
| `taskStyle` | `checks` (`[ ]` `[✓]`, done struck through), `ticks` (`○` `✓`), `box` (`□` `✓`), `progress` (ticks with a done-count bar) | `checks` |
| `promptStyle` | `bubble`, `wide`, `bar`, `chevron`, `off` | `bubble` |
| `clock` | `off`, `24h`, `12h` | `off` |
| `headingStyle` | `banner`, `bold`, `underline`, `uppercase` | `banner` |
| `highlightNumbers` | `true`, `false` | `true` |
| `highlightPaths` | `true`, `false` | `true` |
| `toolRows` | `true`, `false` | `true` |
| `toolStyle` | `chat`, `tree-dim`, `tree-bold`, `classic` | `chat` |
| `toolOutput` | `full`, `quiet` | `full` |
| `copyButtons` | `true`, `false` | `true` |
| `copyButtonStyle` | `inline`, `hover` | `inline` |
| `diagramHints` | `true`, `false` | `true` |
| `issueHint` | `true`, `false` | `true` |
| `rtl` | `auto`, a terminal (`warp`, `kitty`, `apple-terminal`, `iterm`, `ghostty`, `wezterm`, `vscode`, `alacritty`, `windows-terminal`, `gnome`, `konsole`), `off` | `auto` |
| `mermaid` | `true`, `false` | `true` |
| `mermaidAscii` | `true`, `false` | `false` |
| `pieStyle` | `round` (a circle with a legend), `bars` (one bar per slice) | `round` |
| `latex` | `true`, `false` | `false` |
| `<token>Color` | any color, see below | theme |
| `diffStyle` | `card` (rounded box, tinted lines), `full` (no box, lines tinted across the width), `marks` (no tint, colored `+` and `−` marks), `bar` (no tint, a colored `▌` before each changed line) | `card` |
A color is hex (`#a6e3a1`, `#fc0`), `rgb(166,227,161)`, `ansi256(114)` or a name (`green`, `cyanBright`). Values that don't parse are ignored. Every token has a `<token>Color` option and a row in `/config`:

| Token | Colors |
| --- | --- |
| `accent` | reply bullet, H3+ headings, quote bar, running tool dots |
| `heading` | H1 and H2 |
| `strong` | **bold** text, `strong` in figures |
| `emphasis` | *italic* text, variables, attribute names |
| `inlineCode` | `inline code` |
| `codeText` | code block text |
| `codeCommand` | shell commands, functions, class names, keys |
| `codeFlag` | `--flags`, keywords, failures |
| `codeString` | strings |
| `codeComment` | comments, the code block's language label, `dim` in figures |
| `link` | links, URLs, properties, tags |
| `path` | file paths, regexes |
| `number` | numbers, versions, durations, done dots |
| `quote` | quote text |
| `rule` | rules, diff card borders, chart gridlines |
| `tableHeader` | table header cells |
| `tableRule` | table rules |
| `bullet` | list bullets and numbers |
| `diagram` | diagram lines, `accent` in figures |
| `diagramText` | diagram labels, LaTeX formulas and figure text |
| `diffAdded` | added diff lines: their tint, `+` marks and count (the theme's own green) |
| `diffRemoved` | removed diff lines: their tint, `−` marks and count (the theme's own red) |

## Troubleshooting

- **A setting or update didn't take:** run `/reload`. A session keeps what it loaded.
- **A diagram shows as code:** its source is over 80 lines or 8,000 characters, it's wider than the window, it doesn't parse, or `mermaid` is off. Widen the terminal or split the diagram.
- **A figure shows as code:** it is still streaming, it has more than 80 lines, a line is wider than the window or than 100 columns, or a line holds a glyph, character or markup that would not draw as written; the dim line above it names the line (see [Figures](#figures)). A frame that is slightly off draws as written, never as code. Widen the terminal, or ask Claude to fix the glyph or the markup.
- **No `⧉ html` on tables:** you're over SSH, in the desktop app or VS Code, or on Linux with no graphical session. `⧉ md` and `⧉ art` still work.
- **`⧉ html` copied plain text only:** CopyQ isn't running, or the clipboard helper failed. The toast says why.
- **Clicking a copy button selects the word "copy":** your terminal copies on select. Use `/prismantis copy`.

## Limits

- The parser covers what Claude writes (headings, lists, tables, fences, quotes, emphasis, links). It's not full CommonMark: HTML draws as plain text, and a quote ends at the first line without `>`.
- Widths count CJK and emoji as two columns. Terminals disagree on a few emoji, so those can still be off by one.
- Languages outside the 24 above draw in `codeText`.
- Tested by hand in the macOS terminal; CI runs the tests on macOS, Linux and Windows. The desktop app, VS Code and mobile use the same mod API but are not checked by hand yet.

<details>
<summary>For LLMs and agents</summary>

To change the code, read [AGENTS.md](AGENTS.md) instead.

- **What it is:** a Claude Code mod (function hooks in TypeScript) that redraws assistant replies, slash-command output, tool rows, the turn footer and user prompts. It changes how things look, and with `diagramHints` on (the default) it also asks Claude to build a reply around pictures when they make it easier to grasp, with the core on the first screen as a picture or a sentence. The one thing it sends the model is the optional diagram hint below.
- **Install:** `/plugin marketplace add NahumLitvin/prismantis`, then `/plugin install prismantis@prismantis`. Needs Claude Code 2.1.287+. Changes apply after `/reload`.
- **Configure:** `/prismantis theme <name>` and `/prismantis setup` set options at runtime. Every option is a key under `pluginConfigs["prismantis@prismantis"].options` in `~/.claude/settings.json` (or a row in `/config`), then `/reload`. Options and defaults are in the [Configure](#configure) table; the machine-readable source is `userConfig` in [.claude-plugin/plugin.json](.claude-plugin/plugin.json). Color values that don't parse are ignored.
- **Side effects:** no network. Programs it runs: the `⧉ html` clipboard helper (`/usr/bin/osascript` on macOS, `copyq` on Linux, 5 second timeout, only on a click), and `ratex-render` while `latex` is on. With `diagramHints` on, it adds about 630 tokens of model-only context (about 710 while `latex` is on) to each prompt you type and each prompt another plugin sends, as broken down under [Diagram hints](#diagram-hints).
- **Turning it off:** `"enabled": false`, or disable the plugin in `/plugin`.
- **For other mods:** `$.prismantis.markdown({ surface, text, columns })`, typed in [types/index.d.ts](types/index.d.ts). See [Other mods](#other-mods).

</details>

## Roadmap

Planned features are on the [roadmap board](https://github.com/users/NahumLitvin/projects/2), one issue each. Give an issue a 👍 to vote for it, or open one for what you miss.

## Develop

```bash
git clone https://github.com/NahumLitvin/prismantis
claude --plugin-dir ./prismantis
```

Edits hot-reload in that session. Before a PR run `claude plugin validate .` and `claude plugin test .`, and print [docs/demo.md](docs/demo.md) to check the look. `npm --prefix scripts run bench` times a full render of the demo reply, so speed claims can be checked on any machine. The full rules and verify loop are in [AGENTS.md](AGENTS.md).

### Other mods

Other mods can draw markdown in the user's theme with `$.prismantis.markdown`. Pass the surface, the text and the content width in columns.

- It answers the tree to draw, or `undefined` when prismantis is disabled or the text holds nothing to draw.
- It throws when prismantis isn't installed, so call it in a `try`.
- Prismantis draws at least 20 columns wide. Copy buttons are left out, because a button can't cross from one mod to another.

```tsx
let drawn
try {
  drawn = await $.prismantis.markdown({ surface: e.surface, text, columns: e.props.bodyColumns })
} catch {}
return drawn ?? <Markdown text={text} />
```

The types are in [types/index.d.ts](types/index.d.ts). List prismantis under `dependencies` in your `plugin.json` and Claude Code lays them into your `.claude-plugin/types/`. When prismantis is optional, declare the noun in your own contract instead:

```ts
declare module 'claude-code' {
  interface EngineInterface {
    prismantis: {
      markdown: (args: { surface: RenderSurface; text: string; columns: number }) => Promise<RenderElement | undefined>
    }
  }
}
```

## Author

Built by [Nahum Litvin](https://github.com/NahumLitvin), who writes about running untrusted code in production at [catchkill9.dev](https://www.catchkill9.dev/).

## License

[MIT](LICENSE). Bundled third-party code is listed in [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).
