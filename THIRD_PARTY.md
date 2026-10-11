# Third-party sources

This repository is **private**. Some vendored items have no licence, so you need the authors' permission before making this repository public (see "Before going public" below).

## Vendored (copied into this repo)

| Path | Upstream | Licence | Notes |
|---|---|---|---|
| `plugins/agent-arena-mode` | own work | MIT | |
| `specialist-council` | own work | none yet (own work) | Add a LICENSE before sharing. |
| `plugins/flightdeck` | https://github.com/scasella/claude-flightdeck | MIT | See `MODIFICATIONS.md`. |
| `plugins/prismantis` | https://github.com/NahumLitvin/prismantis | MIT | Includes local PNG-export changes; see `MODIFICATIONS.md` and `png-button.patch`. |
| `plugins/plot-deck` | copied from kyryl-shtefiienko/LPS `mods/` | none stated | |
| `skills/networkx` | K-Dense scientific skills | BSD-3-Clause | |
| `skills/pyzotero` | K-Dense scientific skills | MIT | |
| `skills/scientific-brainstorming` | K-Dense scientific skills | MIT | |
| `skills/uncertainty-and-units` | K-Dense scientific skills | MIT | |
| `skills/headroom` | headroomlabs-ai/headroom | Apache-2.0 | |
| `skills/agent-teams`, `skills/local-build`, `skills/path-safety`, `skills/paper2agent`, `skills/reverse-engineer-anything` | unknown origin | none stated | |
| `agents/code-improver.md` | unknown origin | none stated | |
| `vendor/ansys-mcp-server.patch` | https://github.com/vorobjewsen30-max/ansys-mcp-server @ `36b18a9` | MIT | Local edits to `pyproject.toml`, `requirements.txt` and `server.py`. The installer clones upstream and applies this patch. |

## Referenced (installed from upstream, never copied)

All marketplaces in `config/kit.json`:

- obra/superpowers
- affaan-m/ECC
- multica-ai/andrej-karpathy-skills
- mattpocock/skills
- anthropics/skills (the document skills are proprietary; reference only)
- JuliusBrussee/caveman
- thedotmack/claude-mem (optional)
- Egonex-AI/Understand-Anything
- ruvnet/ruflo
- sickn33/agentic-awesome-skills
- dietrichgebert/ponytail
- typesafe-ai/skills
- kyryl-shtefiienko/LPS

The `rea-agents@6.3.0` MCP server comes from npm.

## Before going public

1. Add a LICENSE to `specialist-council`.
2. Resolve the rows marked "none stated" or "unknown origin": get permission, replace them, or drop them.
3. Run `python scripts/scan.py`.
