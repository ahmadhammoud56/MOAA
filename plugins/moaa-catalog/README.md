# moaa-catalog

Skills on demand for Claude Code. Every enabled plugin lists each of its skills (name and description) in every
request, used or not. With large packs that is thousands of lines per request. MOAA installs those packs disabled
and this plugin makes their skills reachable anyway:

- **Index.** `~/.claude/moaa-catalog/index.json` holds name, description and path of every skill in an installed
  but disabled plugin. It is rebuilt only when `settings.json` or the installed-plugin record change (about 5 s for
  3,600 skills on a warm disk, longer on a cold one); otherwise a lookup reads it in about 20 ms. The hooks never
  rebuild it inline: SessionStart and a prompt that finds it stale start a background rebuild (`catalog.py index`),
  and the prompt is matched against the previous index meanwhile, so the hook stays far below its 10 s timeout.
- **Search.** `catalog.py search <words>` ranks by how many words match, weighting rare words and name hits.
- **Hook.** On each prompt, a `UserPromptSubmit` hook adds up to three lines when a disabled skill matches strongly
  (rare words worth at least two unique-word hits, one of them in the skill's name). Ordinary prompts, harness
  notices and the desktop app's hidden summary prompt add nothing; `<system-reminder>` blocks the desktop app puts in
  front of your words are ignored, so the first prompt after a restart is matched too. `MOAA_CATALOG_HINTS=off`
  silences the hook for one process (strata sets it on its helper runs). Short forms expand (k8s, tf, py, ...) and project files (`package.json`, `main.tf`, ...) boost
  matching skills without triggering on their own.
- **Use.** `catalog.py use <path>` prints the skill for the current session and logs the use. A pack used three
  times in 30 days gets an "enable it" suggestion; enabling stays a visible `claude plugin enable` command that loads
  from the next session.

In MOAA's `all-on` mode (every plugin enabled, listing cut to names plus short descriptions) the index and the hook
also cover enabled skills, pointing to the Skill tool for them.

Only disabled skills are served by `use`; a pack's hooks, agents and MCP servers need it enabled. Standard library only,
read-only apart from its own index and usage log. MIT licensed.
