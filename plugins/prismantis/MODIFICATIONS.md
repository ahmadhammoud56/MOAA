# prismantis: my modifications

Upstream: [NahumLitvin/prismantis](https://github.com/NahumLitvin/prismantis) (v0.11.0, MIT, see `LICENSE`). Upstream has no PNG export. Everything below is a local addition.

## PNG button for tables and diagrams

A `▣ png` button next to the copy buttons on tables and mermaid diagrams. It renders the block's text art to a PNG, copies the image to the Windows clipboard, and keeps no file (it renders to a temp file and deletes it after the copy; if the copy fails the temp file is kept and its path is shown).

| File | What it does |
| --- | --- |
| `hooks/register.tsx` | `savePng()` runs the script below; `copyPngToClipboard()` puts the image on the clipboard through PowerShell (`-STA`, `Clipboard.SetImage`); the `png` button handler shows a toast. |
| `hooks/render.tsx` | Adds the `▣ png` button after the copy buttons on tables and diagrams. |
| `scripts/text2png.py` | Renders monospace text from stdin to a PNG with Pillow (Cascadia Mono, Consolas or DejaVu Sans Mono, 28 px). |

Needs Python with Pillow (`pip install pillow`). The clipboard step is Windows only; macOS and Linux would need `osascript`, `wl-copy` or `xclip`.

- `png-button.patch`: all of the above as a unified diff against clean upstream 0.11.0.
- This folder is a full copy of the plugin with the changes applied.

## Apply to a fresh install

```sh
cd ~/.claude/plugins/cache/prismantis/prismantis/0.11.0
patch -p1 < /path/to/LPS/mods/prismantis/png-button.patch
```

Then run `/reload-plugins`. A plugin update overwrites the change, so re-apply the patch afterwards.
