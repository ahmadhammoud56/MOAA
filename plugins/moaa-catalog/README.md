# moaa-catalog

Skills on demand for Claude Code. Every enabled plugin lists each of its skills (name and description) in every
request, used or not. With large packs that is thousands of lines per request. MOAA installs those packs disabled
and this plugin makes their skills reachable anyway:

- **Index.** `~/.claude/moaa-catalog/index.json` holds name, description and path of every skill in an installed
  but disabled plugin. It is rebuilt only when `settings.json` or the installed-plugin record change (about 0.5 to 2
  s for 2,500 skills); otherwise a lookup reads it in about 20 ms.
- **Search.** `catalog.py search <words>` ranks by how many words match, weighting rare words and name hits.
- **Hook.** On each prompt, a `UserPromptSubmit` hook adds up to three lines when a disabled skill matches strongly
  (rare words worth at least two unique-word hits, one of them in the skill's name). Ordinary prompts and harness
  notices add nothing. Short forms expand (k8s, tf, py, ...) and project files (`package.json`, `main.tf`, ...) boost
  matching skills without triggering on their own.
- **Use.** `catalog.py use <path>` prints the skill for the current session and logs the use. A pack used three
  times in 30 days gets an "enable it" suggestion; enabling stays a visible `claude plugin enable` command that loads
  from the next session.

In MOAA's `all-on` mode (every plugin enabled, listing cut to names plus short descriptions) the index and the hook
also cover enabled skills, pointing to the Skill tool for them.

Only disabled skills are served by `use`; a pack's hooks, agents and MCP servers need it enabled. Standard library only,
read-only apart from its own index and usage log. MIT licensed.
