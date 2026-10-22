# prismantis: MOAA's modifications

Upstream: [NahumLitvin/prismantis](https://github.com/NahumLitvin/prismantis), **v0.34.0** (`82afde8`), MIT, see
`LICENSE`. This folder is upstream v0.34.0 with the changes below.

## Left out of the copy

- `codex/`, `.codex-plugin/` and `.agents/`: upstream's Codex plugin, generated from the same source. Claude Code does
  not use them.
- `.claude/`: upstream's developer skills (add-theme, demo, live-check, drive-check, release) for working on
  prismantis itself. MOAA's `.gitignore` excludes `.claude/` folders.
- The screenshots and GIFs in `docs/` (14 MB). Nothing reads them at runtime, and every install copies the whole
  plugin folder. The README's images still show on upstream's GitHub page.

## PNG button for tables and diagrams (opt-in)

A `▣ png` button after the copy buttons on tables and mermaid diagrams. It renders the block's text art to a PNG,
copies the image to the Windows clipboard and keeps no file: it renders to a temp file and deletes it after the copy.
If the copy fails, the temp file is kept and its path is shown. Upstream's `⧉ html` button copies a table as an HTML
table; this one copies it as an image.

**It is off unless `PRISMANTIS_PNG_BUTTON` is set** (any non-empty value), for example in `settings.json`:

```json
{ "env": { "PRISMANTIS_PNG_BUTTON": "1" } }
```

Off by default keeps upstream's behaviour, and upstream's test suite, which checks the exact set of copy buttons,
unchanged.

| File | What it does |
| --- | --- |
| `hooks/register.tsx` | `savePng()` runs the script below; `copyPngToClipboard()` puts the image on the clipboard through PowerShell (`-STA`, `Clipboard.SetImage`); `png()` makes the button and shows a toast; the session probe reads `PRISMANTIS_PNG_BUTTON` into `style.pngCopy`. |
| `hooks/render.tsx` | `renderBlocks` takes the `png` button maker and adds `▣ png` after `⧉ art` (and `⧉ html`), inline and in the hover style. |
| `hooks/theme.ts` | `pngCopy: boolean` on `Style`, `false` by default. |
| `scripts/text2png.py` | Renders monospace text from stdin to a PNG with Pillow (Cascadia Mono, Consolas or DejaVu Sans Mono, 28 px). |
| `tests/moaa-png.test.tsx` | The button is hidden without the variable and shown with it. |

Needs Python with Pillow (`pip install pillow`). The clipboard step is Windows only; macOS and Linux would need
`osascript`, `wl-copy` or `xclip`.

`png-button.patch` holds all of the above as a unified diff against clean upstream v0.34.0
(`patch --dry-run -p1` applies it cleanly to those files).

## Checked for this update (2026-10-22)

- `claude plugin validate .`: passed.
- `claude plugin test .`: 844 passed, 0 failed (upstream's 842 plus the 2 above). Clean upstream v0.34.0 also
  passes all 842 here.
- `tsc -p .` could not be run meaningfully on this machine: the generated `.claude-plugin/types/` package was missing,
  so almost every error was "Cannot find module 'claude-code'", on clean upstream too. Upstream's CI runs it with the
  types present.
- Not yet checked: the button in a live session.

## Update to a newer upstream

1. Export the new upstream tag without the parts listed above.
2. Apply `png-button.patch` (`patch -p1`). If it no longer applies, re-apply the changes in the table by hand.
3. Run `claude plugin validate .` and `claude plugin test .`, then regenerate the patch against the new tag.
4. Bump `tested_version` for `prismantis@moaa` in `config/kit.json`, and update the version in `THIRD_PARTY.md` and
   this file.
