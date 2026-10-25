# Getting started with MOAA (about 5 minutes)

## 1. Install (1 minute)

```bash
git clone https://github.com/ahmadhammoud56/MOAA.git && cd MOAA
./install.sh                     # Windows PowerShell: .\install.ps1
```

That is the **core profile**: 14 plugins (council, arena, War Room, allies, strata, the skill catalog and a few
proven packs). Add the packs for your kind of work, installed and enabled:

```bash
./install.sh --profile web       # or data, devops, research, science; comma-separated for several
```

`--full` installs all 97 plugins, with the big skill packs installed but disabled (see step 5). `--dry-run` previews
any of these. Restart Claude Code afterwards.

## 2. Ask the council (1 minute)

```
/specialist-council:specialist-council  Is 221 prime? Factor it.
```

The coordinator picks roles, resolves each role's model and effort, runs them in parallel and cross-checks the
answers. For real work, describe the task as you would to a senior colleague; the council chooses the team.

## 3. Let agents compete (1 minute)

```
/agent-arena-mode:judge --quick -- Write fib(n) with fib(1)=fib(2)=1 and give fib(20).
```

The arena runs candidates, judges them against a rubric and keeps the winners in a library. An agent that wins
validated runs repeatedly is forged into a permanent council member.

## 4. Run a team on a big job (optional)

```
/war-room:war-room
```

War Room starts several real Claude Code sessions with council roles, a shared task board, review gates and a merge
queue, and opens a local app to watch them. Templates (`feature team`, `bug hunt`, `review swarm`, ...) give you a
plan to start from. With the allies plugin, a worker can be Codex or Gemini instead of Claude.

## 5. Keep it lean (1 minute)

Every enabled plugin lists all its skills in every request, used or not. Check what yours costs:

```bash
python scripts/install.py --report
```

- `--prune` lists plugins you have not used in 45 days; `--prune --yes` disables them, `--restore` undoes it.
- `--mode all-on` keeps every plugin enabled (all hooks, agents and MCP servers live) and trims the skill listing
  to names plus short descriptions; `--mode lean` disables the big packs instead.
- `--lean` brings an install from before 0.9.0 in line (big packs disabled).
- Disabled skills are still found: the **moaa-catalog** plugin suggests a matching one when your prompt clearly needs
  it, and Claude can load it into the session with one call.

## 6. Always on

Three features need no command. **prompt-refiner** turns each new request into a clear brief and asks about unclear
points with options (`refiner.py off` to stop, `raw:` to skip one prompt). **strata's context handoff** writes a
handoff at about 85% of the context window, so you open a new chat instead of compacting. **strata's project RAG**
indexes the project's files and adds the matching passages when a request clearly needs them (`rag.py off` to stop).

## 7. Stay up to date

Clone installs: `python scripts/install.py --update`. Marketplace installs: `python scripts/install.py --auto-update`
once (or the toggle in `/plugin` > Marketplaces). moaa-catalog tells you at session start when a release is out.

## 8. Knowledge that compounds (optional)

`/strata:wiki` compiles your papers and notes into linked pages Claude keeps current (Karpathy's LLM Wiki);
`/strata:graph` records findings with their sources and checks they are grounded; `/agent-arena-mode:karpathy-loop`
improves anything you can measure, keeping only changes that move the number.

## 9. When something is off

- `/moaa-catalog:moaa-help` explains what is installed and how to use it, from inside Claude Code.
- `python scripts/install.py --status` compares your install with this repo (changes nothing).
- `python scripts/install.py --uninstall` reverses everything the installer recorded.

More: [README](../README.md), [Guide](GUIDE.md), [War Room](../plugins/war-room/README.md), [MODELS.md](../MODELS.md),
[SECURITY.md](../SECURITY.md).
