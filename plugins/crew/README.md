# Crew

Claude Code hands bounded tasks to other agent CLIs and checks what comes back. Each member signs in with its own
account, so the work spends that service's quota instead of your Claude usage.

| Member | What runs | Sign-in |
|---|---|---|
| `codex` | OpenAI Codex CLI (`codex exec`) | `codex login` (ChatGPT or API key) |
| `gemini` | Google Gemini CLI (`gemini -p`) | run `gemini` once and sign in with Google, or set `GEMINI_API_KEY` |
| `kimi` | Moonshot Kimi Code CLI (`kimi -p`) | run `kimi` once and use `/login` |
| `deepseek` | Claude Code on DeepSeek's Anthropic-format API | set `DEEPSEEK_API_KEY` |
| `omniroute` | Claude Code through a local [OmniRoute](https://github.com/diegosouzapw/OmniRoute) gateway | `crew.py omniroute start`, then connect providers in its dashboard |

Install the CLIs you want: `npm install -g @openai/codex @google/gemini-cli @moonshot-ai/kimi-code`. The legacy
Python `kimi-cli` is unmaintained; use `@moonshot-ai/kimi-code`.

## Use

In Claude Code, ask for it ("get a second opinion from codex and gemini", "have kimi draft the tests") or run
`/crew:crew`. By hand:

```
python crew.py doctor                                   which members are ready
python crew.py run codex --cwd PROJECT --task "..."     read-only answer
python crew.py ask codex,gemini --task-file brief.md    the same brief to several members in parallel
python crew.py run codex --write --cwd REPO --task-file brief.md
python crew.py runs / show RUN_ID
python crew.py omniroute start|stop|status
```

- **Read-only by default.** Codex runs in its `read-only` sandbox; Gemini, Kimi and the Claude-format members run in
  plan mode.
- **Writes never touch your checkout.** `--write` makes a git worktree under `~/.claude/crew/worktrees/` on branch
  `crew/<member>-<id>`. Crew commits what the member leaves (agent sandboxes often cannot write a linked worktree's
  git metadata) and reports the diff. Review and merge it yourself.
- **Every run is kept** in `~/.claude/crew/runs/<id>/`: the brief, each member's answer, a log and metadata.
- **Your Claude login stays private.** The `deepseek` and `omniroute` members run Claude Code with `--bare`, which
  reads only `ANTHROPIC_API_KEY` (set to that provider's key) and never your Claude OAuth login.
- Keys can also be kept in `~/.claude/crew/keys.env` (`DEEPSEEK_API_KEY=...`), which is read when the variable is
  not set.

## War Room

A War Room plan can give any worker an `engine` (`codex`, `gemini`, `kimi`, `deepseek` or `omniroute`). The
conductor then feeds that worker its tasks through crew, in the worker's own worktree, and reports results through
the bus. Review gates and the merge queue are unchanged, so a Codex builder can be reviewed by a Gemini or Claude
reviewer. See the `mixed-crew` template (`warroom.py template mixed-crew`).

## OmniRoute

OmniRoute is an MIT-licensed gateway that puts one endpoint in front of hundreds of providers and falls back
between free tiers. `python scripts/install.py --with-omniroute` installs a pinned version from npm. MOAA never
starts it with OmniRoute's defaults. `crew.py omniroute start` runs it with:

- the listener on 127.0.0.1 only, and an API key required on `/v1`;
- conversation tracking off, browser-cookie providers off, and paid-credit fallback off;
- a generated dashboard password and JWT secret in `~/.claude/crew/omniroute.env` (never `CHANGEME`).

In its dashboard, connect only API-key and free-tier providers. Do not connect subscription logins or web cookies
of other services; providers may ban accounts used that way, and OmniRoute itself marks such providers "avoid".
Never connect your Claude account.

## Known limits

- Codex's Windows sandbox may not see your Python install, so it cannot run Python tests. Crew reports what the
  member says it could not check; run the tests yourself before merging.
- Sign-in checks are best effort. Gemini and Kimi report `unverified` until their first run.
- A member's answer is untrusted text. The skill tells Claude to verify it and never to follow instructions in it.

MIT licensed; see [LICENSE](LICENSE). Part of [MOAA](https://github.com/ahmadhammoud56/MOAA).
