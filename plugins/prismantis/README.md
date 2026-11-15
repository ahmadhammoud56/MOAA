# prismantis

A Claude Code mod that redraws Claude's replies in color: tables, headings, lists, quotes, highlighted code, numbers, paths and links, mermaid diagrams and charts, and tool rows, in 17 themes, with copy buttons. Run `/prismantis setup` to pick a look, or `/prismantis demo` to see everything it draws.

Screenshots, every option and the changelog are in the [full README](https://github.com/NahumLitvin/prismantis#readme).

## What it runs, reads and changes

Prismantis makes no network calls. Everything below stays on your machine.

- **Programs.** Clicking `⧉ html` or `▣ png` runs the clipboard helper with the copied table, diagram or figure on stdin: `osascript` on macOS, `powershell.exe` on Windows (it reads `SystemRoot` to find it), or `copyq` on Linux. With `latex` on, it runs `ratex-render` from your `PATH` with the reply's formulas on stdin. It runs nothing else.
- **Files.** It reads a local PNG that a reply links as a Markdown image, up to 2 MB, to draw it in kitty or Ghostty. It reads back the PNGs `ratex-render` writes to `$TMPDIR/prismantis-latex-<session>-<id>`. It writes no files itself.
- **Settings.** `/prismantis setup` and `/prismantis theme` save your pick through `/config`, only into prismantis's own options (`prismantis.theme`, `prismantis.tableStyle` and the other setup steps). Nothing else in your settings changes.
- **Hooks.** It draws through `ui.render`, answers the `/prismantis` command through `command.run`, adds the model-only [diagram hints](https://github.com/NahumLitvin/prismantis#diagram-hints) note in `prompt.submit`, and adds `$.prismantis.markdown` for [other mods](https://github.com/NahumLitvin/prismantis#other-mods) in `engine.create`. `prismantis.markdown` is that call's own event.

## License

[MIT](LICENSE), by Nahum Litvin. Bundled third-party code and palettes are credited in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
