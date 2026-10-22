# moaa-core

One install for MOAA's core. It has no components of its own; it depends on:

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
