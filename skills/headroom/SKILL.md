---
name: headroom
description: Configure, use, or troubleshoot Headroom for local LLM-context compression with Codex, Claude Code, MCP clients, Python, TypeScript, or an OpenAI-compatible proxy. Use when the user explicitly mentions Headroom or asks to reduce coding-agent token use by compressing tool output, logs, files, JSON, or retrieved context. Do not trigger for ordinary prompt shortening or generic model-cost questions that do not involve Headroom.
license: Apache-2.0
metadata:
  source: https://github.com/headroomlabs-ai/headroom
  upstream-revision: b8b222f9403878efe08376eac71a626caf1920d6
---

# Headroom

Help the user choose and operate the smallest Headroom setup that matches their goal. Headroom is separate software; loading this skill does not install or start it.

## Choose the integration

Use the user's existing environment and stated goal to select one mode:

| Goal | Preferred mode |
| --- | --- |
| Compress traffic for a Codex or Claude Code session | `headroom wrap codex` or `headroom wrap claude` |
| Expose on-demand compression, retrieval, and stats | MCP server via `headroom mcp serve` |
| Route an existing OpenAI-compatible client without code changes | Local proxy on `127.0.0.1:8787` |
| Compress inside Python code | Python `compress()` API |
| Use the TypeScript SDK | TypeScript package plus a running Python proxy |
| Keep Headroom available across restarts | `headroom deploy` or a requested `headroom install` preset |

Prefer an on-demand wrapper or MCP setup for evaluation. Use persistent deployment only when the user asks for durable background operation.

## Install and verify

Headroom requires Python 3.10 or newer. For a host-level CLI in an isolated environment, the upstream default is:

```bash
uv tool install --python 3.13 "headroom-ai[all]"
headroom --version
headroom doctor
```

Install a smaller extra when the requested mode is narrow:

- MCP only: `uv tool install --python 3.13 "headroom-ai[mcp]"`
- Proxy: `uv tool install --python 3.13 "headroom-ai[proxy]"`
- Python core library: `pip install headroom-ai`
- TypeScript SDK: `npm install headroom-ai`; it still requires a running Python proxy

Do not install packages, start persistent services, or modify agent configuration unless the user's request authorizes that change. Never place provider keys or other credentials in commands, committed files, or chat output.

## Agent workflows

For a temporary agent session, run the matching wrapper and keep that process alive:

```bash
headroom wrap codex
headroom wrap claude
```

Use `headroom unwrap <tool>` to restore durable settings created by wrapping. Check configuration and savings with the commands supported by the installed release, especially `headroom doctor`, `headroom perf`, and `headroom dashboard`.

For MCP, point the host at the absolute path to the `headroom` executable when the host does not inherit the interactive shell `PATH`:

```toml
[mcp_servers.headroom]
command = "/absolute/path/to/headroom"
args = ["mcp", "serve"]
```

On Windows, locate it with `where headroom`. Do not assume the normal proxy exposes an HTTP MCP endpoint at `/mcp`; use `headroom mcp serve --transport http` when HTTP MCP is specifically required.

For an OpenAI-compatible client, start the local proxy and point the client at it:

```bash
headroom proxy --port 8787
```

Keep the default loopback bind unless the user deliberately needs remote access. Verify the proxy before changing client configuration.

## Persistent deployment

When the user explicitly wants a durable runtime, prefer the turnkey flow:

```bash
headroom deploy
headroom install status
```

For an explicit lifecycle, use `headroom install start`, `stop`, `restart`, or `remove`. Explain which provider or user configuration will change before applying a persistent profile, and preserve a clear undo path.

## Diagnose before changing

When Headroom is not working:

1. Check `headroom --version` and `headroom doctor`.
2. Confirm the installed extra covers the requested mode.
3. Resolve the actual executable path and verify the agent can see it.
4. Check whether port `8787` is already in use before starting another proxy.
5. For MCP, run `headroom mcp status`; a proxy is optional unless proxy-backed retrieval is intended.
6. Confirm savings with Headroom's stats or dashboard instead of assuming compression helped. Short or already-dense content may see little benefit.

Use the current upstream documentation for release-sensitive flags and platform details:

- Repository: https://github.com/headroomlabs-ai/headroom
- Installation: https://docs.headroomlabs.ai/docs/installation
- Quickstart: https://docs.headroomlabs.ai/docs/quickstart
- MCP: https://docs.headroomlabs.ai/docs/mcp
- Persistent installs: https://docs.headroomlabs.ai/docs/persistent-installs

This skill was prepared from upstream revision `b8b222f9403878efe08376eac71a626caf1920d6`. Recheck the official documentation when commands or supported integrations may have changed.
