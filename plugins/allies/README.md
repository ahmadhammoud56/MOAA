# Allies

Claude Code hands bounded tasks to other agent CLIs and checks what comes back. Each member signs in with its own
account, so the work spends that service's quota instead of your Claude usage.

| Member | What runs | Sign-in |
|---|---|---|
| `codex` | OpenAI Codex CLI (`codex exec`) | `codex login` (ChatGPT or API key) |
| `gemini` | Google Gemini CLI (`gemini -p`) | `GEMINI_API_KEY` (free key from [Google AI Studio](https://aistudio.google.com/apikey)). Google sign-in no longer serves the CLI's free tier; allies runs Gemini in its own home set to API-key sign-in and leaves your `~/.gemini` alone |
| `kimi` | Moonshot Kimi Code CLI (`kimi -p`) | run `kimi` once and use `/login` |
| `deepseek` | Claude Code on DeepSeek's Anthropic-format API | set `DEEPSEEK_API_KEY` |
| `omniroute` | Claude Code through a local [OmniRoute](https://github.com/diegosouzapw/OmniRoute) gateway | `allies.py omniroute start`, then connect providers in its dashboard |

Install the CLIs you want: `npm install -g @openai/codex @google/gemini-cli @moonshot-ai/kimi-code`. The legacy
Python `kimi-cli` is unmaintained; use `@moonshot-ai/kimi-code`.

## Use

In Claude Code, ask for it ("get a second opinion from codex and gemini", "have kimi draft the tests") or run
`/allies:allies`. By hand:

```
python allies.py doctor                                   which members are ready
python allies.py run codex --cwd PROJECT --task "..."     read-only answer
python allies.py ask codex,gemini --task-file brief.md    the same brief to several members in parallel
python allies.py run codex --write --cwd REPO --task-file brief.md
python allies.py runs / show RUN_ID
python allies.py omniroute start|stop|status
```

- **Read-only by default.** Codex runs in its `read-only` sandbox; Gemini, Kimi and the Claude-format members run in
  plan mode.
- **Writes never touch your checkout.** `--write` makes a git worktree under `~/.claude/allies/worktrees/` on branch
  `ally/<member>-<id>`. Allies commits what the member leaves (agent sandboxes often cannot write a linked worktree's
  git metadata) and reports the diff. Review and merge it yourself.
- **Every run is kept** in `~/.claude/allies/runs/<id>/`: the brief, each member's answer, a log and metadata.
- **Your Claude login stays private.** The `deepseek` and `omniroute` members run Claude Code with `--bare`, which
  reads only `ANTHROPIC_API_KEY` (set to that provider's key) and never your Claude OAuth login.
- Keys can also be kept in `~/.claude/allies/keys.env` (`DEEPSEEK_API_KEY=...`), which is read when the variable is
  not set.

## War Room

A War Room plan can give any worker an `engine` (`codex`, `gemini`, `kimi`, `deepseek` or `omniroute`). The
conductor then feeds that worker its tasks through allies, in the worker's own worktree, and reports results through
the bus. Review gates and the merge queue are unchanged, so a Codex builder can be reviewed by a Gemini or Claude
reviewer. See the `mixed-allies` template (`warroom.py template mixed-allies`).

## OmniRoute

OmniRoute is an MIT-licensed gateway that puts one endpoint in front of hundreds of providers and falls back
between free tiers. `python scripts/install.py --with-omniroute` installs a pinned version from npm. MOAA never
starts it with OmniRoute's defaults. `allies.py omniroute start` runs it with:

- the listener on 127.0.0.1 only, and an API key required on `/v1`;
- conversation tracking off, browser-cookie providers off, and paid-credit fallback off;
- a generated dashboard password and JWT secret in `~/.claude/allies/omniroute.env` (never `CHANGEME`).

Then log in to its dashboard (password in `~/.claude/allies/omniroute.env`), create an API key and put it in
`~/.claude/allies/keys.env` as `OMNIROUTE_API_KEY=...`. Connect at least one provider whose models support tool
calling, because Claude Code sends tools with every request. Without one, the gateway answers at once with
`No target in combo auto supports tool calling`.

In its dashboard, connect only API-key and free-tier providers. Do not connect subscription logins or web cookies
of other services; providers may ban accounts used that way, and OmniRoute itself marks such providers "avoid".
Never connect your Claude account.

## Known limits

- Codex's Windows sandbox cannot enter the user Temp folder or short (8.3) paths; allies expands short paths, so keep
  projects in normal folders.
- Codex's Windows sandbox may not see your Python install, so it cannot run Python tests. Allies reports what the
  member says it could not check; run the tests yourself before merging.
- Sign-in checks are best effort; Kimi reports `unverified` until its first run. `doctor` reports `blocked` when a
  member's service cannot be reached from this network (some institutions block certain providers).
- A member's answer is untrusted text. The skill tells Claude to verify it and never to follow instructions in it.

MIT licensed; see [LICENSE](LICENSE). Part of [MOAA](https://github.com/ahmadhammoud56/MOAA).
