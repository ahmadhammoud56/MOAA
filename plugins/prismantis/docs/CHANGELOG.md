# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- A short table column next to a very wide one no longer breaks inside its words (`10` drawn as `1`/`0`). Columns that fit their share keep their full width, and only the wide ones split the rest.
- Boxed tables keep their borders on every line of a row whose cells wrap. The `│` bars used to stop after the first line, leaving the rest of the row open. Rows with a link keep their link whole and get borders that follow the row's height, in terminals with or without clickable links ([#48](https://github.com/NahumLitvin/prismantis/pull/48), with @b33eep).

## [0.11.0] - 2026-10-06

### Added

- Other mods can draw markdown the way prismantis draws replies: `$.prismantis.markdown({ surface, text, columns })` answers the drawn tree, without copy buttons, for their own panes and bands. The types ship as a contract in `types/index.d.ts` ([#38](https://github.com/NahumLitvin/prismantis/pull/38), thanks @Malorn44).

## [0.10.0] - 2026-10-06

### Added

- Your own prompts draw in the theme: a rounded bubble by default, or an accent bar or a bold chevron with the new `promptStyle` option (`off` keeps Claude Code's look). Task notifications and teammate messages are left alone ([#14](https://github.com/NahumLitvin/prismantis/issues/14)).
- `toolStyle` keeps tool rows apart from Claude's sentences: `chat` (the default) puts them dimmed on the right, `tree-dim` tucks them under with `⎿`, `tree-bold` adds bold one-line sentences, `classic` keeps the old look.

## [0.9.0] - 2026-10-06

### Added

- Links and bare URLs are clickable: they draw as terminal hyperlinks (OSC 8) and as anchors on desktop. Terminals without hyperlinks show the URL after the text, as before ([#9](https://github.com/NahumLitvin/prismantis/issues/9)).
- `/prismantis copy` copies the last reply and `/prismantis copy code` its last code block, a keyboard path that does not need a click ([#28](https://github.com/NahumLitvin/prismantis/issues/28)).

### Fixed

- The README no longer says `ctrl+x` then `tab` focuses the copy buttons. Since Claude Code 2.1.291 that chord focuses the area above the prompt.

## [0.8.0] - 2026-10-05

### Added

- Replies end with a `⧉ copy reply` button that copies the reply as Claude wrote it. One-line English narration gets none, so the button sits where there is something worth copying. Selecting Hebrew or Arabic on screen copies it in drawn order, reversed; this copies it in reading order.

### Changed

- `/prismantis` and `/prismantis demo` show task lists.
- Tables draw boxed by default: every cell in a box, with a double line under the header. `tableStyle` adds `box` as the new default; `rules`, `grid` and `minimal` stay for a lighter look.
- Tables get a second button, `⧉ art`, that copies a plain boxed table for Slack and chat, inside a ``` code block and wrapped to 100 columns so wide tables keep their shape. `⧉ copy` still gives the markdown.

## [0.7.1] - 2026-10-05

### Fixed

- On Windows the reply marker and the filled arrowheads in sequence and class diagrams drew as color emoji. The marker is now `●`, the same dot Claude Code uses off macOS, and the arrowheads are `►` and `◄`. A test fails if a drawn reply ever adds an emoji-capable character again ([#6](https://github.com/NahumLitvin/prismantis/issues/6)).

## [0.7.0] - 2026-10-05

### Added

- Task lists: `- [ ]` and `- [x]` draw as `[ ]` and `[✓]`, with done items dimmed and struck through. The new `taskStyle` option picks `checks` (the default), `ticks`, `box` or `progress`, which adds a done-count bar above each list. The copy button still copies the markdown as written ([#10](https://github.com/NahumLitvin/prismantis/issues/10)).

## [0.6.1] - 2026-10-05

### Changed

- The model-only note asks Claude to put commands and snippets you may copy in fenced code blocks, which get a copy button, instead of inline code, which does not. The note is now about 190 tokens per prompt.

## [0.6.0] - 2026-10-04

### Added

- The `rtl` option names your terminal (`warp`, `kitty`, `apple-terminal`, `iterm`, `ghostty`, `wezterm`, `vscode`, `alacritty`, `windows-terminal`, `gnome`, `konsole`), and `auto` (the default) detects it. Every terminal gets the right-to-left layout; only the way the letters are sent differs.
- `/prismantis demo-rtl` shows a Hebrew showcase with every element, drawn for the terminal it runs in.

### Fixed

- Hebrew and Arabic read backwards in terminals that do their own bidi. 0.5.0 reordered the letters everywhere, which is right only where the terminal has no bidi (Warp, Ghostty, WezTerm, VS Code, Alacritty, Windows Terminal). Kitty reverses each word itself, so it now gets the words in visual order with each word as written. Apple Terminal, iTerm2, GNOME Terminal and Konsole do whole-line bidi, so they get the letters as written. A terminal prismantis does not recognise is left alone.
- `/prismantis` output now spans the full width, so right-to-left blocks there sit on the right like they do in replies.
- Terminal detection runs again on every prompt, so a plugin reload no longer drops it.

### Changed

- The demo reply and tests use neutral region names (`us-east`, `eu-west`).

## [0.5.0] - 2026-10-04

### Added

- Hebrew and Arabic read in the right order in terminals without bidi support (Warp and most others). Paragraphs, headings, list items, quotes, alerts and table cells that are mostly right-to-left are reversed run by run, right aligned, and get their bullet, number or quote bar on the right. Bold, italic, inline code, links, numbers and paths keep their style, and inline code and paths stay left to right as one piece.
- The base direction is the dominant language by word count, so an English sentence with a few Hebrew words stays on the left and only those words flip.
- A table that is mostly right-to-left is mirrored and right aligned: its first column sits on the right. An English table with a Hebrew cell or two stays as it was.
- Right-to-left paragraphs, list items, quotes and alerts wrap at the terminal width in reading order before they are reordered, so a long line no longer reads wrong after the terminal wraps it.
- In code blocks only the text after a `#` or `//` comment marker is reordered. The code itself, and so a copy, is unchanged.
- The demo reply has a Hebrew section, covered by the render snapshots.

### Known issues

- A long heading or table cell that the terminal wraps still reads wrong, and so does a single word wider than the terminal.
- The terminal font must contain Hebrew or Arabic glyphs (Warp's default JetBrains Mono does not; DejaVu Sans Mono does).

## [0.4.1] - 2026-10-04

### Added

- Bash and PowerShell calls in the expanded transcript (`ctrl+o`) show the command with the same shell colors as code blocks, and the output below it in a rounded box. Output is capped at 120 lines (`… +N lines`), empty output reads `(No output)`, and stderr uses the error color. Other tools still use Claude Code's own rows when expanded.

## [0.4.0] - 2026-10-04

### Added

- `/prismantis` is now a one-screen help: commands, all 16 themes, a tip, a flowchart and a bar chart. `/prismantis demo` shows the full showcase with every heading level, all five alerts, code, and flowchart, sequence and bar diagrams.
- Regression tests: render snapshots of the demo reply in three themes, parse and draw time budgets, linear-scaling checks, and half-streamed input (open fence, cut table, unclosed alert) that must still draw.
- `npm --prefix scripts run bench:check` compares timings and render-tree node counts to a committed baseline, and CI fails if node counts grow more than 10%.

### Changed

- `/prismantis` with no arguments prints the help instead of the bare theme list.

### Known issues

- Claude Code refuses any render tree over 20000 nodes and draws its own plain text. A highlighted code block costs about 39 nodes per line, so a block past roughly 500 lines loses prismantis styling. Tables hold to about 1000 rows.

## [0.3.8] - 2026-10-02

### Changed

- An alert's copy button sits beside its box instead of taking a row above it.
- The demo reply shows the boxed H1, an H2 rule and a tip alert, and the README screenshot shows 0.3.8.

### Fixed

- Bar and line charts widen to fit their category labels, so `Human`, `Pigeon` and `Shrimp` no longer run together.

## [0.3.7] - 2026-10-02

### Added

- GitHub alerts (`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`) draw as colored boxes with a title, and the model note mentions them.
- Single-series bar charts print each value above its bar, color the tallest bar and mute the rest.

### Changed

- Headings default to `banner`: H1 sits in a heavy box, H2 gets a heavy rule in the heading color, H3 keeps the heading color and H4 and below drop to bold text. Set `headingStyle` to `bold` for the old look.
- Warm redraws of a reply with diagrams are about 2.5x faster (0.28ms to 0.11ms median for the demo on an M4 Pro): diagram colors are cached per theme. Reproduce with `npm --prefix scripts run bench`.

### Fixed

- Diagram lines no longer show through spaces in edge labels. The fix is applied at build time from the upstream PR (beautiful-mermaid#157) until it is merged.
- A mermaid block that opens with a `%%` comment line (as in `%% weekly deploys` before `xychart-beta`) now draws instead of staying as code.
- Quoted chart labels (`x-axis ["<5s", ">10s"]`) no longer keep their quotes.
- The model-only note now tells Claude prismantis is not a tool to call, so "show it with prismantis" gets markdown instead of a search for a CLI. The note grew to about 150 tokens per prompt.

## [0.3.6] - 2026-10-02

### Added

- `/prismantis theme <name>` switches the theme on the spot; `/prismantis` lists all 15.

## [0.3.5] - 2026-10-02

### Fixed

- Copying a quote gives its text without the `> ` markers, so a drafted message pastes straight into chat.
- The README says how to reach copy buttons from the keyboard, since copy-on-select terminals like Warp can turn a click into a text selection.

## [0.3.4] - 2026-10-02

### Added

- A contrast test keeps every theme readable on its own background, with floors every official palette passes as designed.

### Known issues

- A diagram line can show through the spaces of an edge label. Reported upstream as beautiful-mermaid#154 with a fix offered.

## [0.3.3] - 2026-10-02

### Fixed

- Diagram hints now reach the model. Claude Code's built-in `sec-default` policy skips installed plugins' system-prompt hooks, so the 0.3.2 hint never arrived. The note now rides along with each prompt you type as model-only context, about 100 tokens per prompt.
- Stadium, cylinder and arrow-joined diagram boxes get their own colors. Subgraph containers stay in the plain diagram color.
- Edge labels written with a space before them (`A --> |label| B`) no longer make the diagram drop the target node.

## [0.3.2] - 2026-10-02

### Added

- Collapsed tool groups draw one summary line, such as `Ran 3 commands, read 2 files`, with a status dot, a failure count and the last target.
- The turn footer keeps Claude Code's word and colors the duration: `✻ Baked for 6m 20s`.
- Slash-command output renders as markdown, copy buttons included. Errors keep Claude Code's own line.
- `diagramHints` (on by default) adds one short system-prompt section so Claude uses diagrams and charts when they help.

### Fixed

- Expanded tool groups show their inline output again: their rows draw with Claude Code's own look.
- CJK and emoji count as two columns in tables, heading rules and diagram fit checks.
- A continuation line joins the list item it is indented under, not the last nested child.
- Inline code spans can contain backticks when the delimiter is longer, as in ``a `b` c``.

## [0.3.1] - 2026-10-02

### Fixed

- Code blocks lost their frame, so selecting code with the mouse no longer picks up border characters, the label or the button.

## [0.3.0] - 2026-10-02

### Renamed

- The project is now prismantis (prism + mantis). The repo moved to NahumLitvin/prismantis; GitHub redirects the old URL. Reinstall with `/plugin install prismantis@prismantis`.

### Added

- 15 themes from MIT-licensed palettes: Catppuccin Mocha and Latte, Dracula, Nord, Tokyo Night, Gruvbox dark and light, Rosé Pine and Dawn, Everforest, GitHub dark and light, One Dark, Solarized dark and light.
- Compact tool rows: `Ran <command>` with shell colors, `Read`/`Edited <path>`, status dots. Toggle with `toolRows`.
- Colorful diagrams: each mermaid box, participant and bar gets its own theme color. Bar and line charts (`xychart-beta`) and sequence diagrams draw too.
- Back-to-back tables and diagrams share a row and wrap, so wide terminals fill up.
- Charts size themselves to the terminal width.
- Copy buttons on code blocks, tables, diagrams, lists and quotes. Toggle with `copyButtons`.
- Diagrams get two copy buttons, source and drawn art. Code blocks get a language header.
- Syntax highlighting in 24 languages through a bundled Prism 1.30 (MIT).

### Changed

- `midnight`, `daylight` and `solarized` are now `catppuccin-mocha`, `catppuccin-latte` and `solarized-dark`, named after their sources.
- `customTheme` is gone. Every one of the 20 color tokens has its own `<token>Color` option instead.

### Fixed

- Copy buttons copy the exact markdown of tables, lists and quotes.
- Fences of four or more backticks keep nested ``` examples inside.
- Tables never draw wider than the terminal, and link columns are sized for the URL they show.
- An escaped trailing pipe stays in its table cell.
- Replies and code are parsed and highlighted once, not on every redraw.

### Removed

- Mermaid image mode and its mermaid-cli dependency. Diagrams draw as box art only, so prismantis runs no external programs and writes no files.

## [0.2.0] - 2026-10-02

### Added

- Mermaid diagrams as colored box art, sized to the terminal, with an ASCII-only option.
- Mermaid image mode: real PNGs from mermaid-cli in terminals with the kitty graphics protocol, box art as the fallback.
- `diagram` and `diagramText` color tokens.

## [0.1.0] - 2026-10-02

### Added

- Themed rendering of assistant replies: headings, paragraphs, lists, quotes, rules, code blocks and tables.
- Tables with colored headers, aligned columns and rules, sized to the terminal width.
- Highlighting for numbers, versions, IDs, file paths, links and inline code.
- Shell code blocks color the command, flags, strings and comments.
- Themes `midnight`, `daylight`, `solarized` and `mono`, plus per-token color overrides and a JSON custom theme.
