# Third-party sources and licences

MOAA's own code (the Specialist Council, the Agent Arena, the installer) is MIT licensed by Ahmad Hammoud; see [LICENSE](LICENSE). Every vendored component keeps its upstream LICENSE in its own directory. [NOTICE](NOTICE) has the short attribution list.

## Vendored (copied into this repo)

| Path | Upstream | Licence | Status |
|---|---|---|---|
| `plugins/specialist-council` | own work | MIT | ok |
| `plugins/agent-arena-mode` | own work | MIT | ok |
| `plugins/flightdeck` | [scasella/claude-flightdeck](https://github.com/scasella/claude-flightdeck) | MIT | ok; local changes in `MODIFICATIONS.md` |
| `plugins/prismantis` | [NahumLitvin/prismantis](https://github.com/NahumLitvin/prismantis) | MIT | ok; local PNG-export changes in `MODIFICATIONS.md` |
| `skills/networkx`, `skills/pyzotero`, `skills/scientific-brainstorming`, `skills/uncertainty-and-units` | [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | MIT | ok |
| `skills/headroom` | [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | Apache-2.0 (+ NOTICE) | ok |
| `skills/reverse-engineer-anything` | [morluto/rea](https://github.com/morluto/rea) | MIT | ok |
| `skills/paper2agent` | [jmiao24/Paper2Agent](https://github.com/jmiao24/Paper2Agent) | MIT (code). The bundled paper and supplement text was licence-checked by the maintainer. | ok |
| `vendor/ansys-mcp-server.patch` | [vorobjewsen30-max/ansys-mcp-server](https://github.com/vorobjewsen30-max/ansys-mcp-server) @ `36b18a9` | MIT, declared in its `pyproject.toml` (the repo has no LICENSE file) | ok; only a patch is shipped, and upstream is cloned at install time |
| `plugins/plot-deck` | [kyryl-shtefiienko/LPS](https://github.com/kyryl-shtefiienko/LPS) `mods/`, by Kyryl Shtefiienko | none upstream; redistributed **with the author's permission** (see `PERMISSION.md`) | ok |
| `skills/agent-teams`, `skills/local-build`, `skills/path-safety`, `agents/code-improver.md` | own work (Ahmad Hammoud) | MIT (root LICENSE) | ok |

## Release check

No open blockers. `python scripts/scan.py --public` passes when every vendored item has a LICENSE, is declared own work, or has recorded redistribution permission.

## Referenced (installed from upstream, never copied)

The installer adds these marketplaces and installs from them. Their code is not in this repository.

| Marketplace | Upstream |
|---|---|
| superpowers-dev | [obra/superpowers](https://github.com/obra/superpowers) |
| ecc | [affaan-m/ECC](https://github.com/affaan-m/ECC) |
| karpathy-skills | [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) |
| mattpocock | [mattpocock/skills](https://github.com/mattpocock/skills) |
| anthropic-agent-skills | [anthropics/skills](https://github.com/anthropics/skills) (the document skills are proprietary) |
| caveman | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) |
| thedotmack (optional) | [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) |
| understand-anything | [Egonex-AI/Understand-Anything](https://github.com/Egonex-AI/Understand-Anything) |
| ruflo | [ruvnet/ruflo](https://github.com/ruvnet/ruflo) |
| agentic-awesome-skills | [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) |
| ponytail | [dietrichgebert/ponytail](https://github.com/dietrichgebert/ponytail) |
| typesafe-ai | [typesafe-ai/skills](https://github.com/typesafe-ai/skills) |
| lps-marketplace | [kyryl-shtefiienko/LPS](https://github.com/kyryl-shtefiienko/LPS) |

The MCP server `rea-agents@6.3.0` comes from npm ([morluto/rea](https://github.com/morluto/rea), MIT).
