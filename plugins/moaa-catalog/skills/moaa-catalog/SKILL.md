---
name: moaa-catalog
description: Find the right skill when none of the listed ones clearly fits a task (a framework, file format, cloud service or workflow), or when a moaa-catalog hook note names one; covers disabled plugins, and enabled ones whose descriptions are trimmed. Search first; never enable plugins just to look.
---

# MOAA catalog: skills on demand

MOAA installs big skill packs (agentic-awesome-skills, ruflo extras) disabled, so their skills are not listed in every
request. Their files stay on disk, indexed in `~/.claude/moaa-catalog/index.json` (rebuilt only when plugins or
settings change; a search takes milliseconds).

1. A hook may already have named matches for the user's prompt ("moaa-catalog: skills that may fit...").
   Otherwise search with 1 to 4 specific words:

   ```
   python "${CLAUDE_PLUGIN_ROOT}/catalog.py" search <words>
   ```

2. A hit from an enabled plugin says `Skill tool, skill "plugin:name"`: invoke it that way. A hit from a disabled
   plugin is loaded into this session with one call, which also logs the use:

   ```
   python "${CLAUDE_PLUGIN_ROOT}/catalog.py" use "<path to its SKILL.md>"
   ```

   Follow what it prints for this task. Files it mentions sit next to that SKILL.md.
3. Only skills work this way. When a pack's hooks, agents or MCP tools are needed, or `use` reports the pack is used
   often, tell the user and run `claude plugin enable <plugin id>` (loads from the next session). For one project
   only, add `"enabledPlugins": {"<plugin id>": true}` to that project's `.claude/settings.json`.

`catalog.py packs` lists the disabled plugins with their skill counts. Nothing here changes settings or plugins.
