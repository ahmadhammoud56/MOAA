# moaa-core

One install for MOAA's core. It depends on:

- `specialist-council`: 60 role agents with per-role model and effort
- `agent-arena-mode`: eight competition modes and the library that forges council members
- `moaa-catalog`: skills on demand

```
/plugin marketplace add ahmadhammoud56/MOAA
/plugin install moaa-core@moaa
```

Claude Code installs the three dependencies with it. Add `war-room`, `allies` or `strata` from the same marketplace
when you want them. For the full setup (third-party plugins, skills, MCP servers), use the installer in the
repository root instead.

## Inline-Python guard

On by default. A `PreToolUse` hook (Bash and PowerShell) runs `guard.py hook pre-tool` (standard library only). When a
command runs `python -c`, `py -c`, `python3 -c` (any flags, `.exe` or a full path) and the code has a newline or is
longer than 150 characters, it adds a note next to the tool result: write the code to a `.py` file in the scratchpad
and run that instead, because Windows shell quoting breaks such code. It never blocks, denies or asks; the call goes
through the normal permission flow, and any error in the guard means it adds nothing.

```bash
py guard.py status
py guard.py off
py guard.py on
```

`MOAA_GUARD=off` in the environment skips it for that process. State lives in `~/.claude/moaa-core/config.json`
(`CLAUDE_CONFIG_DIR` respected).

## project-docs skill

`/moaa-core:project-docs` audits the current project for the agent doc set (`AGENTS.md`, `CLAUDE.md`, `README.md`,
`ARCHITECTURE.md`, `CODE_STYLE.md`, `TESTING.md`, `SECURITY.md`, and `PRD.md` / `DESIGN_SYSTEM.md` for app or UI
projects), reports each as present, missing or stale, and drafts the ones you pick from the code. `AGENTS.md` is the
single cross-agent source (Codex, Gemini, OpenCode read it) and `CLAUDE.md` imports it with `@AGENTS.md`. It hands
off to installed skills where they fit (`agentic-awesome-skills:agents-md`, `ecc:plan-prd`,
`agentic-awesome-skills:design-md`, `ecc:update-codemaps`).

## Tests

```bash
py -m unittest discover -s tests
```

`tests/e2e/` holds the raw output of a piped hook call and a live headless `claude -p` run.
