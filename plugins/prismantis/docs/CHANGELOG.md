# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.34.0] - 2026-10-22

### Added

- `promptStyle: wide` draws your prompt in the rounded accent bubble across the full width, so each prompt marks a clear break between turns when you scroll back ([#272](https://github.com/NahumLitvin/prismantis/pull/272)).

### Fixed

- On Warp, Ghostty, WezTerm, VS Code and Alacritty, a shell command with a Hebrew argument keeps the command first, also when most of its words are Hebrew ([#271](https://github.com/NahumLitvin/prismantis/pull/271)).

## [0.33.1] - 2026-10-21

### Added

- `/prismantis demo-rtl` shows a `text` code block in Hebrew ([#264](https://github.com/NahumLitvin/prismantis/pull/264)).

### Fixed

- On Warp, Ghostty, WezTerm, VS Code and Alacritty, Hebrew in plain text and shell code blocks, and Hebrew strings in highlighted code, read right to left while the code around them stays where it is. A Hebrew line wider than the block wraps first, so its first row opens the sentence ([#264](https://github.com/NahumLitvin/prismantis/pull/264)).
- On iTerm, inline code and paths in a Hebrew reply draw exactly as written, also when they start or end with `/`, `~`, `.` or `-` ([#265](https://github.com/NahumLitvin/prismantis/pull/265)).
- A Hebrew list with an English item reads as one list on the right, and an English list with one Hebrew item stays on the left ([#266](https://github.com/NahumLitvin/prismantis/pull/266)).

## [0.33.0] - 2026-10-21

### Added

- `/prismantis setup` has steps for headings, copy buttons, times and diffs, each drawn in every look, and in a short terminal the arrows move the focus instead of scrolling ([#253](https://github.com/NahumLitvin/prismantis/pull/253)).
- A paste of 4 lines or more in your prompt draws in a double frame of its own, folded to one `pasted text · N lines` button that opens it as highlighted code, instead of Claude Code's raw `<pasted_content>` tags and every pasted line ([#260](https://github.com/NahumLitvin/prismantis/pull/260)).

### Changed

- With `copyButtonStyle` set to `hover`, each block keeps one dim ⧉ beside it and its buttons appear only while the pointer is on that ⧉, so moving across a reply no longer flashes buttons over the text. Blocks lay out two columns narrower in this mode to make room ([#254](https://github.com/NahumLitvin/prismantis/pull/254)).
- A path that starts with `/` links only when another name follows, so slash commands like `/config` and top folders like `/tmp` stay path-colored text with no hyperlink ([#242](https://github.com/NahumLitvin/prismantis/pull/242)).

### Fixed

- On iTerm, a mostly English table with some Hebrew cells stays one table, every row left to right with its columns lined up ([#255](https://github.com/NahumLitvin/prismantis/pull/255)).
- Copying a table with `art` keeps its borders in line when cells carry bidi marks, as Hebrew replies often do ([#256](https://github.com/NahumLitvin/prismantis/pull/256)).
- A shell command's diff card with file links on no longer vanishes into a `ui.render call rejected` line ([#260](https://github.com/NahumLitvin/prismantis/pull/260)).

## [0.32.1] - 2026-10-20

### Fixed

- A `{role:text}` tag outside a figure, in a table cell or a sentence, draws as its text instead of printing raw. Inline code, unknown roles like `{err:x}` and look-alikes like `{id:42}` stay as written. The figure hint now says roles are for figures only ([#248](https://github.com/NahumLitvin/prismantis/pull/248)).

## [0.32.0] - 2026-10-20

### Added

- On Claude Code 2.1.289 and later, in a terminal that draws hyperlinks and not over SSH, paths in replies (`/`, `~/`, `./`, `../`), the files in tool rows and `file://` links open their file or folder on click. Under WSL they open through `wsl.localhost`. The look is unchanged ([#238](https://github.com/NahumLitvin/prismantis/pull/238)).
- Diff cards highlight code in the file's language and mark the words that changed on a deeper tint, as Claude Code's own diffs do. Removed lines stay plain, unchanged lines are no longer dimmed, `marks` keeps diff colors on the `+` and `−` only, and wrapped lines repeat their mark and tint ([#234](https://github.com/NahumLitvin/prismantis/pull/234)).
- New, deleted and moved files draw as files instead of long green or red diffs: `Created <path> (N lines)` over a preview of the first 10 lines, `Deleted <path> (N lines)` that opens to what it held, and `Renamed <old> → <new>`. From 2.1.295 a click anywhere on a long card opens and closes it ([#236](https://github.com/NahumLitvin/prismantis/pull/236)).

### Changed

- A `file://` link stays clickable only when its label shows the path it opens. Other `file://` links draw as `label (target)` text ([#240](https://github.com/NahumLitvin/prismantis/pull/240)).
- Programs and launchers never open on click: a path or `file://` link ending in an executable or launcher extension (`.exe`, `.app`, `.sh`, `.command`, `.lnk` and 71 more), or inside an `.app` bundle, draws as text ([#240](https://github.com/NahumLitvin/prismantis/pull/240)).

### Fixed

- A box in a figure whose rows slip a few columns off its frame draws closed. Boxes next to it keep their place, or move over in one piece when the box has to grow ([#171](https://github.com/NahumLitvin/prismantis/pull/171)).
- Box figures come out with straight walls more often, especially with Hebrew rows of mixed length, because the figure hint asks the model to pad box rows to the top border ([#243](https://github.com/NahumLitvin/prismantis/pull/243)).

## [0.31.1] - 2026-10-19

### Fixed

- A line holding only an HTML-like tag (`<tldr>`, `<summary>`) draws dim on its own row instead of joining the next line, and `/tldr` no longer gets the path colour. Inline tags (`a <b>bold</b> word`) are unchanged ([#228](https://github.com/NahumLitvin/prismantis/pull/228)).
- Gantt bars line up with their real start and end dates more closely, so tasks of similar length no longer draw the same ([#224](https://github.com/NahumLitvin/prismantis/pull/224)).

## [0.31.0] - 2026-10-19

### Added

- xychart series can be named, `line "east" [..]` or `bar east [..]`, and the legend shows the name instead of `Line 1` or `Bar 1`. Series with no name keep the numbered label ([#225](https://github.com/NahumLitvin/prismantis/pull/225)).

### Fixed

- Each line and bar series of a multi-series xychart draws in its own theme color, and its legend swatch matches. Before, every line drew in one color and grouped bars got a color per bar ([#225](https://github.com/NahumLitvin/prismantis/pull/225)).
- A named xychart series draws instead of vanishing from the chart ([#225](https://github.com/NahumLitvin/prismantis/pull/225)).

## [0.30.0] - 2026-10-19

### Added

- Mermaid `pie` charts draw as a round circle with a legend: each slice in its own theme color, the legend's swatches matching, edges smoothed with quadrant blocks. `pieStyle: bars` in `/config` keeps one bar per slice. Round falls back to bars in ascii mode, in a terminal too narrow for it, and when the theme has fewer distinct colors than slices (Dracula, Nord and Rosé Pine have four, mono none) ([#221](https://github.com/NahumLitvin/prismantis/pull/221)).
- `/prismantis setup` has a seventh step, Pie charts, drawing both styles ([#221](https://github.com/NahumLitvin/prismantis/pull/221)).

### Fixed

- The Codex README links the fenced-block proof of concept on the Codex fork instead of a closed PR ([#220](https://github.com/NahumLitvin/prismantis/pull/220)).

## [0.29.0] - 2026-10-19

### Added

- `/prismantis setup` typed in a terminal opens a pane. Each step lists its styles as buttons; the arrows or Tab move the focus and the pane draws a sample of the style in focus beside the list. Enter saves the pick and moves to the next step, Esc closes the pane and keeps the picks made so far. Sessions with no terminal, like the desktop app, keep the walk in the transcript. Contributed by @b33eep ([#206](https://github.com/NahumLitvin/prismantis/pull/206)).
- Lua code blocks are highlighted. Requested by @emrearmagan ([#213](https://github.com/NahumLitvin/prismantis/issues/213), [#216](https://github.com/NahumLitvin/prismantis/pull/216)).

### Changed

- The Korean section of `/prismantis demo` reads more naturally. Contributed by @gobenpark ([#208](https://github.com/NahumLitvin/prismantis/pull/208)).

### Fixed

- Hebrew numbered items draw ".1" and "(1", number first, where prismantis orders the row itself: terminals without bidi, kitty and Windows Terminal. Terminal.app, GNOME, Konsole and iTerm2 are unchanged. Contributed by @tomerbr1 ([#210](https://github.com/NahumLitvin/prismantis/pull/210)).
- Diagram edges with a Hebrew label keep their lines and arrowhead in place, in box-drawing and ASCII mode alike; before, the arrow could point back at the source. A label like "גרסה+beta" stays whole. Contributed by @tomerbr1 ([#210](https://github.com/NahumLitvin/prismantis/pull/210), [#217](https://github.com/NahumLitvin/prismantis/pull/217)).

## [0.28.0] - 2026-10-17

### Added

- `/prismantis demo` adds a Korean section when `LC_ALL` or `LANG` is Korean: a paragraph, a list, a table, a figure and a flowchart, all in Korean. `/prismantis demo ko` shows it anywhere ([#202](https://github.com/NahumLitvin/prismantis/pull/202)).
- When you say a reply drew wrong, Claude may offer, after asking, to open a minimal repro issue on prismantis. A one-line note rides your first prompt and every tenth after it; `issueHint: false` turns it off ([#203](https://github.com/NahumLitvin/prismantis/pull/203)).

### Fixed

- Figures draw Korean, Japanese and Chinese text. They refused any two-column letter and fell back to source, so labels in those languages never drew; now each takes two columns and frames line up. Emoji are still refused, since terminals disagree on their width. Reported by @gobenpark ([#192](https://github.com/NahumLitvin/prismantis/issues/192), [#201](https://github.com/NahumLitvin/prismantis/pull/201)).

## [0.27.0] - 2026-10-17

### Added

- `/prismantis setup` has a sixth step, Tool output. It draws `full` and `quiet` with the same two calls, a `git status` and a build that fails, so you can see how much of each call shows before picking. Pick with `/prismantis setup output quiet` or `/prismantis setup output 2`. Contributed by @b33eep ([#198](https://github.com/NahumLitvin/prismantis/pull/198)).

## [0.26.0] - 2026-10-17

### Changed

- Hebrew draws right to left in iTerm2 with bidirectional text on. iTerm2 picks each row's direction from its first letter and ignores invisible marks, so a Hebrew row that opens with English now starts with a dim `׀`, and tables, quotes, alerts and banner headings draw their frame with `׀` walls that move with the text. Hebrew rows in mermaid diagrams and figures stay in place, and mixed labels like "האם יש cache?" read right to left. Contributed by @tomerbr1 ([#181](https://github.com/NahumLitvin/prismantis/pull/181)).

### Fixed

- On terminals without bidi (VS Code, Warp, Ghostty, WezTerm), Hebrew labels in mermaid diagrams and figures read right to left. They came out in typing order, so they read backwards ([#194](https://github.com/NahumLitvin/prismantis/pull/194)).
- A done task in Hebrew keeps its dim, struck look in every terminal ([#181](https://github.com/NahumLitvin/prismantis/pull/181)).
- In Windows Terminal, Hebrew code rows keep their order, and text copied from the terminal comes out with plain spaces ([#181](https://github.com/NahumLitvin/prismantis/pull/181)).

## [0.25.2] - 2026-10-17

### Fixed

- A reply holding an 8-bit control character (U+0080 to U+009F, such as the one-byte CSI `\u009b`) now draws with prismantis. Those characters passed the control filter, so Claude Code refused the drawing and showed the reply as plain text; they are now stripped with the other control sequences ([#188](https://github.com/NahumLitvin/prismantis/pull/188)).

## [0.25.1] - 2026-10-16

### Security

- An image source in a reply can no longer point at another machine. `file://` URLs take only an empty host or `localhost`, and paths that start with `//` or `\\` are refused, so on Windows a reply cannot make the mod open an SMB connection, which could leak the login hash. Images load only in kitty and Ghostty, or with `CLAUDE_CODE_FORCE_TERMINAL_IMAGES`, so 0.25.0 was reachable only on Windows with that variable set. Such a source now shows its alt text, and a malformed `%` escape in a `file://` source no longer throws. Reported by @tomerbr1 ([#182](https://github.com/NahumLitvin/prismantis/issues/182), [#185](https://github.com/NahumLitvin/prismantis/pull/185)).

## [0.25.0] - 2026-10-16

### Added

- `/prismantis setup` walks five steps: theme, tables, tasks, your prompts and tool rows. Each step draws every option in its own style. Pick by name or number (`/prismantis setup tables grid` or `/prismantis setup tables 3`), and the pick saves to `/config`, applies right away and shows the next step. Light themes are marked as made for a light terminal ([#178](https://github.com/NahumLitvin/prismantis/pull/178)).
- Mermaid `pie` and `gantt` blocks draw as colored box art instead of source. A pie draws one bar per slice, largest first, with its share, and the value under `showData`. A gantt draws sections and tasks as bars on a shared date or time axis, with `after`, `until`, durations from `ms` to `w` and milestones. `excludes weekends` and `axisFormat` are not handled yet ([#177](https://github.com/NahumLitvin/prismantis/pull/177)).
- In kitty and Ghostty, a markdown image on a line of its own draws as a picture when it is a PNG from a local path, `~/`, `file://` or a `data:` URL, up to 20 rows and 2 MiB. Web images are never downloaded and stay links that show the alt text. Other terminals, tmux and images inside a sentence show the alt text in the link color instead of a stray `!` ([#179](https://github.com/NahumLitvin/prismantis/pull/179)).

### Fixed

- On the desktop app, VS Code and mobile, code blocks keep their indentation and alignment. They draw through the app's own code element, in the app's highlight colors, and folding and the copy button work as before ([#176](https://github.com/NahumLitvin/prismantis/pull/176)).

## [0.24.1] - 2026-10-16

### Fixed

- With `copyButtonStyle: hover`, hovering a block no longer blanks the rest of the row its copy buttons appear on. The buttons cover only their own cells on code blocks, tables, lists, quotes, alerts and mermaid diagrams, a block narrower than its buttons widens to fit them, and right-to-left lists, quotes, alerts and tables show their buttons at the left, where their lines end ([#170](https://github.com/NahumLitvin/prismantis/pull/170)).

## [0.24.0] - 2026-10-15

### Added

- Footnote marks are clickable. Click a mark in a sentence, list item, quote, alert or table cell to see its note in a toast, point at a note to light every mark that cites it, or at a mark to light its note. This works in the desktop app and where the terminal passes the mouse through, as fullscreen mode does, on Claude Code 2.1.295 or later; earlier versions draw the marks as before ([#138](https://github.com/NahumLitvin/prismantis/pull/138)).

### Changed

- Blockquotes and GitHub alerts keep their markdown structure. Paragraphs, lists, code blocks, tables and nested quotes inside a quote draw as they do anywhere else, inside the bar or under the alert title. Code blocks and tables inside a quote keep their own copy buttons, `/prismantis copy code` finds a code block inside a quote, and footnotes inside a quote are numbered with the others ([#155](https://github.com/NahumLitvin/prismantis/pull/155)).

### Fixed

- In fullscreen, a boxed table row with a link no longer draws its borders down through the lines after the table once the table scrolls past the top of the screen ([#155](https://github.com/NahumLitvin/prismantis/pull/155)).

## [0.23.0] - 2026-10-15

### Added

- The `⧉ html` table copy works in a local Windows terminal. It puts the table on the clipboard as HTML and tab-separated text through Windows' built-in PowerShell, so pasting into Slack makes a native table, and Word and web editors keep the header row and column alignment. Over SSH the button stays hidden, as on macOS and Linux ([#144](https://github.com/NahumLitvin/prismantis/pull/144)).

## [0.22.0] - 2026-10-15

### Added

- `diffAdded` and `diffRemoved` theme tokens hold each preset's own green and red for diffs, from its upstream palette: Rosé Pine's foam and love, Nord's nord14 and nord11, Dracula's green and red, Everforest's `#a7c080` and `#e67e80`, GitHub's git added and deleted colors. `diffAddedColor` and `diffRemovedColor` set them like any other token ([#152](https://github.com/NahumLitvin/prismantis/issues/152)).

### Changed

- Diff lines tint from the theme's `diffAdded` and `diffRemoved` instead of its number and flag colors, taking the color's hue at full strength before the 30% black or 20% white mix, so they read bolder (`catppuccin-mocha`'s added lines go from `#324430` to `#064d00`). The `+N −M` counts and the `+` and `−` marks take the same two colors. In `rose-pine-dawn`, `everforest`, `gruvbox-light`, `dracula`, `rose-pine` and `nord`, whose number and flag colors are two pinks, purples or blues, added and removed lines were hard to tell apart (ΔE 2.6 to 11.5); every preset now keeps them at least ΔE 26 apart with code text at 4.5:1 or more, checked by a test ([#152](https://github.com/NahumLitvin/prismantis/issues/152)).

### Fixed

- `codex plugin add prismantis@prismantis` installs the plugin. Codex 0.162 skips a marketplace entry whose source is `github`, the form Claude Code uses, and reported "plugin `prismantis` was not found". The repo now also ships `.agents/plugins/marketplace.json`, which Codex reads first, with the same release pinned as a git `url` source. Claude Code still reads its own marketplace and installs as before.

## [0.21.0] - 2026-10-15

### Added

- Codex: installing prismantis in Codex gives it the same model note as Claude Code, plus what Codex's own renderer cannot draw, so replies come back with tables, fenced commands, mermaid sized for Codex and text figures. `$prismantis` shows the demo, and `$prismantis-themes` installs the 16 themes as Codex syntax themes, which color code, inline code, table headers and mermaid boxes; `/theme` picks one. Prose, headings and copy buttons stay Codex's own. Codex asks you to trust the hook once in `/hooks`. Everything in it is generated from the Claude Code side.

## [0.20.0] - 2026-10-14

### Added

- `diffStyle` picks how Edit, Write and shell edit diffs draw: `card` (the default) frames the lines in a rounded box with tinted lines, `full` drops the box and tints each changed line across the width, `marks` drops the tint and draws the changed lines in the number and flag colors, which reads in 256-color terminals and `mono` too, and `bar` drops the tint and puts a `▌` in the line's color before each changed line. Every style keeps the `+N −M` header, line numbers, folding at 20 lines and one block per changed file. Tool output other than diffs is unchanged ([#132](https://github.com/NahumLitvin/prismantis/issues/132)).
- `copyButtonStyle: hover` shows copy buttons only while the pointer is on their block: a block's buttons float over its top-right corner, or from its left edge on a block narrower than they are, and `⧉ copy reply` over the reply's bottom-right corner, out of the flow, so they reserve no line and nothing moves when they show. `inline`, the default, keeps today's look. ctrl+x tab does not reach a hidden button; `/prismantis copy` still copies without a mouse. The mobile app, which has no pointer, draws them inline.

### Changed

- Diff lines sit on a bolder tint that keeps code text readable: the number or flag color mixed into black on dark themes (30%) or white on light ones (20%), whichever contrasts more with the code text, and less where the text would drop below 4.5:1 (only `solarized-light`, at 17% and 13%). It used to be 20% over the rule color, a gray, which put code text at 3.1:1 in `tokyo-night` and under 4.5:1 in 7 of the 15 color presets; now every one is at 4.5:1 or more ([#132](https://github.com/NahumLitvin/prismantis/issues/132), [#146](https://github.com/NahumLitvin/prismantis/issues/146)).

### Fixed

- Files a shell command changed (`sed -i`, a script) draw as the same diff card as Edit and Write results, in the theme's number and flag colors, instead of Claude Code's own red and green diff. Each changed file gets its own card headed by its path, with `… +K more files` when Claude Code listed more, and each card folds on its own. The command's output still draws above the cards. Dim notes under them say what Claude Code's own diff says: on the first one of a session, that it shows every file that changed while the command ran, by it or anything else; that another command ran in the repository at the same time, when Claude Code saw one; and that a git step in the command (`checkout`, `reset`, `stash`, `pull`, …) can move the working tree. `toolOutput: quiet` keeps these diffs under the command's first lines, where it used to drop them. A failed command, a diff the card cannot read, and `toolRows: false` keep Claude Code's drawing ([#132](https://github.com/NahumLitvin/prismantis/issues/132)).
- The `ruleColor` description in `/config` no longer says it colors heading banners, which take the heading color. It names what the color draws: horizontal rules, diff card borders and chart gridlines ([#132](https://github.com/NahumLitvin/prismantis/issues/132)).

## [0.19.0] - 2026-10-14

### Changed

- Links that open a file in VS Code, `vscode://file/…` and `vscode-insiders://file/…`, are clickable terminal hyperlinks on Claude Code 2.1.294 and later, so a reply can point at `src/app.ts:42` and a click opens that line. Claude Code 2.1.287 throws out the whole reply for such a link and 2.1.294 is the first release known to accept it, so below 2.1.294, when the version cannot be read, and on the desktop app and other remote surfaces, they draw as plain text, as other unclickable links do. Other `vscode://` links, which reach extensions' URI handlers (`vscode://vscode.git/clone?url=…`), always draw as plain text.

### Fixed

- Bar chart heights line up with the y-axis. A bar used to fill the `0` row as well as its own, and charts could settle on one row per tick, so 400 reached the 500 line and 1200 stopped at 1000. Bars are now drawn to the half cell: each one rises from the middle of the axis line, reaches every gridline at or below its value, stops exactly on a gridline it equals, and never passes its value. A terminal draws `─` and `·` through the middle of a cell, so the line under a bar and a tip that ends mid-cell are half blocks (`▀`, `▄`) in the bar's color. `0` sits on the axis line, a line chart at `0` runs along it, every tick gets the same number of rows, and an axis without a set range ends on a whole tick.
- Bar charts with negative values. Every bar used to fill the `0` row, so `2` and `-2` drew to the same height, and an all-negative chart ran its bars up past the top of the chart. The `0` line is now drawn solid like the axis line, and bars grow up or down from its middle and stop exactly where their value is, to the half cell. An all-negative chart hangs its bars from a solid line at the top of the axis.
- Bar values sit at the end of their bar. A value was centered on its tick column, which is right of the middle of an even-width bar, so `1200` hung off its bar's edge. A negative bar's value sat above `0` on the positive side, and the bar at the top of an untitled chart, or any bar in an all-negative chart, lost its value. Values are now centered on their bar, half a cell to the right when they cannot center exactly (`1200` covers a four-wide bar, `800` sits over its last three cells), a negative bar's value sits under it, and a bar that reaches the top of the axis keeps its value on a row above the chart.
- A line over a bar chart passes behind the bars instead of overwriting their tips, so a bar under the line no longer looks shorter than its value.
- Footnote marks in a table's header row draw in the footnote color, as they do in paragraphs and body cells. Before, they took the header color and looked like part of the column name.

## [0.18.4] - 2026-10-14

### Fixed

- Named links like `[docs](https://example.com)` keep the link color but no longer draw their own underline, so the terminal's hyperlink style shows (in Windows Terminal, a dashed underline that turns solid on hover). A terminal that styles hyperlinks only on hover shows colored text until then.
- Bare URLs draw in the link color again, as they did before they became hyperlinks in 0.9.0. Terminals without hyperlinks still show the URL once.
- Plain `http:` links and bare `http://` URLs are clickable terminal hyperlinks on Claude Code 2.1.289 and later, as in Claude Code without prismantis. They drew in the link color but could not be clicked since 0.13.0, because such a link makes Claude Code 2.1.288 and earlier throw out the whole reply; there, and when the version cannot be read, they draw as plain text, as below. The desktop app and other remote surfaces link only `https:` and `http://localhost`, so there they draw as plain text too.
- Links that cannot be clicked no longer look clickable. `mailto:` and other links that do not become hyperlinks draw as plain text, the label then the target in parentheses, as Claude Code draws them: `[mail](mailto:someone@example.com)` draws as `mail (someone@example.com)`, and a label that matches its target draws once. This holds in paragraphs, lists, quotes, headings, table cells, right-to-left text and `$.prismantis.markdown`. Copying keeps the markdown as written.

## [0.18.3] - 2026-10-13

### Changed

- A table cell holding one very long word (a hash, a base64 blob, a minified line) wraps in linear time: a 10,000-character cell redraws in 3 ms instead of 355 ms. Right-to-left lines are laid out once per text and width instead of on every redraw (stream replay bench, 1.2 ms to 0.9 ms per redraw); the first draw of a long Hebrew reply costs about 15% more.
- A streaming reply redraws about 3.7x faster (1.0 ms instead of 3.9 ms per redraw in the stream replay bench), and Hebrew text about 4.8x faster. Diagrams no longer re-measure their art on every redraw, and single characters skip the grapheme segmenter. Nothing looks different.
- A reply with diagrams redraws faster again while it streams: their art width is measured once instead of on every redraw, up to three times per diagram that does not fit (stream replay bench, 3.2 ms to 1.2 ms per redraw).

### Fixed

- `/prismantis theme random` no longer turns off right-to-left reordering, the HTML table copy and path shortening for the rest of the session. It changes only the colors.
- Switching theme while a formula is still being typeset no longer stores the old color as the new theme's image; the formula is typeset again in the new color.
- In kitty, a link whose URL holds Hebrew keeps its URL as written instead of reversing it.
- A TeX command or a shell program named like a built-in JavaScript property (`\toString`, `\constructor`, a `toString` command) no longer draws `function toString() { [native code] }` or breaks quiet tool rows.
- `awk '@include "inplace"'`, `awk -E`, `awk --exec` and `awk -l` can edit files, so `toolOutput: quiet` no longer hides their output as a read.
- `http://localhost:5173?debug=1` and `http://localhost#/home` are clickable again.
- A footnote definition quoted inside a code block no longer becomes a real footnote.
- Two long code blocks that differ only in where their lines break fold and unfold on their own.
- An expanded shell command whose result is an error message shows that message instead of "(No output)".
- Code-shaped prose draws as written. `## Using C#` keeps its `#`, a link with parentheses such as `wiki/Foo_(bar)` keeps its whole URL, bare or named, and a file link written as ``[`render.tsx`](…)`` loses its backticks. `f(*args, **kwargs)` and `f(_a, _)` no longer turn italic or bold, and `**bold *italic* inside**` stays bold. The demo shows these cases.
- A named link in a right-to-left line stays clickable and keeps its target. Before, reordering a Hebrew line turned the link's target into its own reversed text.
- `http://localhost@evil.example/` and `http://localhost.evil.example/` no longer pass as localhost links. Only `http://localhost`, with an optional port, becomes clickable over plain `http`.
- `awk -i inplace` edits a file, so `toolOutput: quiet` no longer hides its output as a read.
- Copying a table as art no longer fails when a column is narrower than a wide character such as `中`.
- After `/prismantis theme random`, new LaTeX formulas draw in the new theme's color instead of the old one.
- Text-style symbols such as `↔`, `™`, `©`, `▶` and `⚠` count as one column, as terminals draw them, so a diagram box around them closes. Emoji drawn as emoji (`✅`, `⚠️`), flags, keycaps like `1️⃣` and rare CJK characters such as `𠀀` count as two.

## [0.18.2] - 2026-10-13

### Fixed

- LaTeX math draws as images wherever `CLAUDE_CODE_FORCE_TERMINAL_IMAGES` is set, the variable that makes Claude Code draw images, also inside tmux, as Claude Code does. Before, prismantis found the terminal only by `TERM_PROGRAM`, `TERM` and `KITTY_WINDOW_ID`, so a background session, whose process carries none of them, drew every formula as text even when viewed in kitty or Ghostty.

## [0.18.1] - 2026-10-13

### Security

- Releases are immutable from 0.18.1 on: a release tag stays on its commit and cannot be moved, deleted or reused, and `gh release verify v0.18.1 -R NahumLitvin/prismantis` checks GitHub's signed attestation for it. Earlier releases stay as they were ([#101](https://github.com/NahumLitvin/prismantis/issues/101)).

## [0.18.0] - 2026-10-13

### Added

- Figures: code blocks tagged `figure` draw line by line as written, colored by role markup such as `{warn:timeout}`, for what reads better as a picture than as a diagram (a timeout racing a retry, a screen layout, before and after). Roles take existing theme colors, so themes and color overrides apply: `accent` the diagram color, `dim` the comment color, `strong` the strong color, and `warn`, `ok` and `note` the theme's reddest, greenest and most amber accent color, each a different one, so their meaning holds in every preset; `warn` draws bold in a theme without colors (`mono`). A figure stays a code block while it streams, when it has more than 80 lines, when a line is wider than the window or than 100 columns, or when a glyph may draw as an emoji or takes two columns, a control character, direction mark or other character that draws no column is in it, or role markup is wrong; a closed figure that stays code says why in one dim line above it, as diagrams do. Frames are not checked: a box that does not close or a side, corner or divider out of its column draws as written. Figures draw with `mermaid` off too, with `⧉ source` still copying the block as written.
- The model-only note behind `diagramHints` gains a short part on figures: when position carries meaning (durations racing on a time axis, a screen layout, phases, before and after) prefer a figure over mermaid, and the prose does not retell it; when you ask to explain, compare or plan something and pictures would make it easier to grasp, build the reply around them, with the core on the first screen as a picture or a sentence; then the role markup, at most 74 columns, one-column glyphs, and edge ticks `▏` for time axes so `█` bars line up. The main part now also skips a diagram that repeats what a figure shows, and skips diagrams and pictures in short or simple answers.

### Changed

- With `diagramHints` on (the default), the model-only note is now about 630 tokens per prompt you type or another plugin sends: about 275 for the main part and about 360 for the new figure part, plus about 80 for the LaTeX part while it runs. All three are counted with Claude's tokenizer; 0.16.0 documented 190 and 60 from a rougher count. Turn `diagramHints` off to drop the whole note.
- The `diagramHints` note also goes with prompts another plugin sends (`$.prompt.submit`, framed or `asUser`), so replies in a session a plugin drives get the same tables, diagrams and figures as typed prompts. Notifications, scheduled tasks and the prompt a headless `claude -p` run starts with still get none; a plugin's prompt inside such a run gets it. A plugin whose prompts must not carry the note works with `diagramHints` off.

### Fixed

- Tables whose delimiter row uses one dash per cell (`|-|-|`), valid GFM, now draw as tables. Before, they drew as one line of text.
- Flowchart edges written without spaces around the arrow, such as `A-->B`, `A-.->B` or `A-->|yes|B`, draw as edges. Before, the first node took in the arrow's dashes and the diagram drew one box labeled `A--` and no arrows. Node names with a hyphen, such as `my-node`, still draw whole.

## [0.17.1] - 2026-10-12

### Security

- Installs and updates come from the release they name, not whatever is on `main`: the marketplace entry pins each release to its tag and commit. A merged change reaches nobody until a release is cut and pinned.

### Fixed

- A reply holding a terminal control character, such as a stray escape sequence, draws with prismantis again instead of falling back to Claude Code's own text. Control characters are dropped from what is drawn and never reach the terminal.

## [0.17.0] - 2026-10-12

### Changed

- Display math that cannot draw as an image (Warp, iTerm2, any terminal without kitty graphics, latex off, or a formula the renderer rejects) now reads as Unicode instead of TeX source: `\frac{T}{R}\left(1 + \ln\frac{R}{T}\right)` draws as `(T/R)·(1 + ln(R/T))`, with sub- and superscripts, Greek, `\mathbb`/`\mathcal` letters and common operators. A formula with a command it does not know keeps its TeX block. Inline math uses the same conversion.

## [0.16.0] - 2026-10-11

### Added

- `clock` shows when you sent each prompt and when each turn finished: the time goes before your prompt and after the duration on the turn's last line (`✻ Baked for 1m 55s · 14:32`). `24h` or `12h`; a time from another day gets its date. With `promptStyle: off` the time goes in front of Claude Code's own prompt row. A row takes only a time recorded before it was first drawn, so prompts and turns from before a resume get no time, and an old row that redraws never takes a new one. Off by default. New option `clock`.

### Fixed

- Inline HTML tags in mermaid labels draw as styles, not as literal tags: `<i>`/`<em>` italic, `<b>`/`<strong>` bold, `<u>` underline, `<s>`/`<del>` struck. Other inline tags such as `<code>` and `<span>` are dropped and their text kept.

## [0.15.1] - 2026-10-11

### Fixed

- A fenced code block indented under a list item draws as a code block inside that item, with its own copy button, highlighting and fold, and the text after it stays in the item. Before, the fences showed as text in the item, and a blank line inside the block ended the list and turned the rest of the reply into code. `/prismantis copy code` finds these blocks too ([#87](https://github.com/NahumLitvin/prismantis/issues/87)).
- The note above a mermaid block that stays source (`diagram is 244 cols, terminal is 96`) drew in near-white body color; it now uses the same gray as the `── mermaid` label under it.
- A tool row whose path is the project root prints `.` also when a Windows drive root differs in letter case or separators (`e:\projects\example` against `E:\projects\example`); POSIX paths still compare exactly.
- The benchmark baseline in `docs/bench-baseline.json` is refreshed, so `bench:check` no longer flags every stage on current hardware.

## [0.15.0] - 2026-10-10

### Added

- Code blocks of 10 lines or more get dim line numbers, and blocks over 30 lines fold to their first 20 with a `+M more lines` button that opens the rest and a `show less` button that folds it back. `⧉ copy` still copies the whole block. The last 500 opened blocks are remembered ([#16](https://github.com/NahumLitvin/prismantis/issues/16)).
- Footnotes draw as superscript marks numbered by first reference, with the notes collected under a dim rule at the end of the reply. A reference without a definition stays as written ([#18](https://github.com/NahumLitvin/prismantis/issues/18)).
- A mermaid block that stays source says why in one dim line above it: `diagram is 188 cols, terminal is 120` when the art is wider than the terminal, `diagram failed to render` when a supported diagram type throws, and `pie diagrams draw as source for now` for types the renderer has no drawing for (pie, gantt, mindmap, timeline, journey, gitGraph). A block still streaming shows no note. Bar and line chart heights are now tested against their values ([#33](https://github.com/NahumLitvin/prismantis/issues/33), [#63](https://github.com/NahumLitvin/prismantis/issues/63)).
- `theme: random` picks one of the dark color presets each time the mod loads (session start or reload) and keeps it until the next load; with random set, each `/prismantis random` re-rolls and redraws right away. `/prismantis theme` shows the pick and the command to keep it, and a bare `/prismantis <theme>` switches like `/prismantis theme <theme>` ([#21](https://github.com/NahumLitvin/prismantis/issues/21)).
- Edit and Write results draw as a diff card: a rounded box headed `+N −M`, added and removed lines on a faint background tint blended from the theme's number and flag colors, line numbers and context dimmed, a zero count dimmed, long lines wrapped right of the line numbers. Diffs over 20 lines fold behind a `+K more lines` button like code blocks, and an opened card stops at 400 lines. A new file shows as all additions. Results it cannot read go to Claude Code's own drawing, and `toolRows: false` turns it off with the other tool rows ([#15](https://github.com/NahumLitvin/prismantis/issues/15)).

### Fixed

- Tool rows on Windows show paths relative to the project (`Wrote notes\scratch.md`) instead of the full `E:\…` path. The project root and the tool's path both come backslashed there, and the match looked for a `/`; both sides are now compared with forward slashes, case-insensitively under a drive letter, and `~` falls back to `USERPROFILE` when `HOME` is unset ([#83](https://github.com/NahumLitvin/prismantis/issues/83)).

## [0.14.0] - 2026-10-09

### Added

- `toolOutput: quiet` shows what Claude did, not what it read. Reads, searches, listings, web fetches and shell commands made only of read-only programs draw their row and nothing under it, and the row says it in plain words (`Read src/report.py lines 1–10`, `Searched src/ for "TODO"`); a shell call without such a form shows its description and the programs it ran. Other shell commands draw their first lines and a count, without the approval line, also inside a collapsed group. Edits keep their diff. A failed call shows the last real line of its error, a refused call (permission rule, auto mode classifier) its full reason. The ids of read-only calls are kept to the last 2000, so a long session does not grow them ([#53](https://github.com/NahumLitvin/prismantis/issues/53)).

### Fixed

- Tool row paths stay relative to the project after `/cd` or a worktree move. They followed the directory the session started in, so paths in a moved session fell back to `~/…`.

## [0.13.1] - 2026-10-09

### Fixed

- Inline `$…$` math draws as italic text without its dollar signs, so `($\rho = 4.3 / 5$)` reads as ρ = 4.3 / 5. Common TeX commands become symbols. Prices like `$5 and $10` and shell variables like `$HOME` stay as written.
- Chart y-axis ticks sit the same number of rows apart. A 0 to 2500 axis used to step 2, 3, 2, 3, 2 rows between its labels, because the chart height ignored how many ticks it needed; it now takes the nearest height that divides evenly.

## [0.13.0] - 2026-10-09

### Added

- Tables offer `⧉ md`, `⧉ art` and `⧉ html` copy actions. `⧉ html` copies the table as HTML, with headers, column alignment and inline formatting, together with tab-separated plain text, and verifies both before reporting success. `⧉ html` shows in a local macOS terminal or a Linux graphical session, where it needs CopyQ running; over SSH, on desktop and on other systems tables offer `⧉ md` and `⧉ art`. Without CopyQ, or when the clipboard helper fails, the action copies the plain text alone.
- LaTeX math: `$$…$$` and ` ```math ` formulas draw as typeset images in kitty and Ghostty through [RaTeX](https://github.com/erweixin/RaTeX)'s renderer, sized to the reply text and padded to whole rows, with a copy button for the LaTeX. Off by default: the `latex` option turns it on, and `ratex-render` must be on your `PATH`. Without the renderer or in other terminals they stay text in a `math` code block. New option `latex` ([#43](https://github.com/NahumLitvin/prismantis/issues/43)).

### Fixed

- Slash command output that carries terminal colors, like `/context`, is left to Claude Code's own drawing. It used to be refused for its escape codes, with a dim `refused` line in the transcript.
- A flowchart whose long edge label made it too wide for the terminal draws with that label cut short, where it used to fall back to its mermaid source. `⧉ source` still copies the full text.
- Tool rows show file paths relative to the project, and under the home directory as `~/…`, like Claude Code's own rows, instead of the full absolute path.
- Mermaid boxes stay closed around Korean, Chinese and Japanese labels. beautiful-mermaid counts each character as one column, so a wide character pushed the right border inward by one column per character. Wide characters are now measured as two columns before layout and drawn in their real width, in flowcharts, sequence diagrams and chart axes alike ([#56](https://github.com/NahumLitvin/prismantis/pull/56)).
- Only `https` and `http://localhost` links become clickable terminal hyperlinks, which every supported Claude Code accepts. On 2.1.287 a `mailto:` or plain `http:` link made Claude Code throw out the whole reply and draw its own. Other links, `javascript:` and `file:` included, draw as link text.
- Earlier replies stay parsed while a long reply streams in, and code and diagrams are not highlighted again on desktop, in fullscreen Apple Terminal or when another mod draws markdown through `$.prismantis.markdown`.
- The terminal is detected once per session instead of on every prompt, and the list of expanded tool calls no longer grows for the whole session.
- A left-to-right flowchart too wide for the terminal draws top to bottom, where it used to fall back to its mermaid source. A five-node pipeline with two-line labels went from 155 columns to 77.

## [0.12.0] - 2026-10-07

### Fixed

- A short table column next to a very wide one no longer breaks inside its words (`10` drawn as `1`/`0`). Columns that fit their share keep their full width, and only the wide ones split the rest ([#41](https://github.com/NahumLitvin/prismantis/pull/41)).
- Boxed tables keep their borders on every line of a row whose cells wrap. The `│` bars used to stop after the first line, leaving the rest of the row open. Rows with a link keep their link whole and get borders that follow the row's height, in terminals with or without clickable links ([#48](https://github.com/NahumLitvin/prismantis/pull/48), thanks @vrevolverrr and @b33eep).
- Double underscores inside a word stay as written, as CommonMark has it: `mcp__serena__activate_project` no longer draws as `mcp` **serena** `activate_project`. `__bold__` on its own still draws bold ([#51](https://github.com/NahumLitvin/prismantis/pull/51), thanks @vrevolverrr).
- A table column keeps at least the width of its longest word when the longest words of all columns fit, so a file path or URL in a narrow table is no longer cut in the middle. The other columns, even ones that would otherwise keep their full width, wrap to make room ([#49](https://github.com/NahumLitvin/prismantis/pull/49), thanks @b33eep).
- Hebrew and Arabic read right to left in Apple Terminal's fullscreen layout, tables included. Apple Terminal runs its own left-to-right bidi over every fullscreen line, so prismantis now sends each line already reordered for that pass. A number touching Latin text (`250ms`) and ordered-list numbers can still land on the wrong side ([#42](https://github.com/NahumLitvin/prismantis/pull/42)).
- Tables with many rows draw about twice as fast as in 0.11.0, because plain ASCII text is measured by its length.

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
