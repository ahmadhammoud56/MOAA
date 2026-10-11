# Claude Code runtime adapter

This skill uses the running Claude Code session's tools. It does not invoke a provider API, install an SDK, start a second CLI, or require an API key beyond the host's normal authentication.

## Real workers and model configuration

Inspect the installed Agent tool schema (Task on older versions). Dispatch `general-purpose` workers with `description`, a self-contained `prompt`, and a supported `model` alias when available. Use background execution only if exposed. Do not invent a universal parallelism limit. Workers need the full task or a path they can read; they do not automatically know all parent-chat requirements.

The default strong judge request is `opus` with effort `high`, not a guessed model such as `opus-5.5-high`. An alias resolves according to the account/provider configuration and may be substituted by the runtime. Record the actual model/effort when exposed; otherwise record “requested …, actual unverified.” A prompt saying “think hard” is not an effort setting.

The plugin bundles `agents/arena-judge.md`, which Claude Code discovers with the plugin's other components. Its namespaced identifier is `agent-arena-mode:agent-arena-judge` (verify in `/agents`). No extra manual copy into the user's agents directory is needed. It requests `model: opus` and `effort: high`, has read tools, and returns JSON for the coordinator to write. If verification requires commands, the coordinator records execution evidence or dispatches a separate validator with suitable tools in isolated scratch space.

Honor explicit model/effort overrides over the bundled definition's defaults. Use per-invocation model selection where supported and a compatible discovered agent definition or supported session effort control for effort. Do not silently use the fixed `opus`/`high` definition when it conflicts with the request.

If custom agents are unavailable, use an Agent invocation selecting `opus` (or the requested supported model) and the session's supported effort control. Check actual setting before claiming high effort. If high effort cannot be enforced, state this limitation and ask whether the available configuration is acceptable when it was explicitly required. Do not alter global settings to force a fallback. An unavailable exact user-selected model is a missing capability, not permission to select a different model.

Only the coordinator schedules arena participants and owns the ledger. Workers do not recursively invoke the arena or create unscheduled agents.

## Communication for swarm mode

1. Prefer named subagent messaging when Agent names and SendMessage are available. Save exact runtime IDs; use run-qualified names to avoid sending to replacement agents by mistake. Keep an initial private generation before opening communication.
2. Experimental agent teams can provide direct peer messaging and shared tasks when already enabled and suitable. Do not silently change settings to enable them. In current docs teams are experimental and disabled by default; only the lead manages teammates, and resuming a session may not restore in-process teammates.
3. Portable fallback: completed workers publish findings to their own files; the coordinator freezes a shared bulletin, then invokes new revision jobs reading that bulletin and selected peer outputs. Label this **round-based file exchange**, not continuous live conversation. If the user explicitly requires live communication, obtain that capability or ask before using the fallback.

Bound chatter. Assign each participant two rotating peers plus a shared findings board. Within an active work turn allow at most three outbound peer messages, containing a concrete finding, evidence pointer, or question. Do not broadcast every draft to everyone. Between rounds synchronize snapshots; late findings enter the next round. Agents can exchange messages throughout an open round, but every new/resumed work turn must be coordinator-reserved and counted. Do not send to completed agents in a way that silently wakes unbudgeted work. If the runtime auto-resumes recipients and this cannot be controlled, use file exchange for bounded execution and disclose the limitation.

## Workspaces and persistence

Use `.agent-arena/<unique-id>/` under the user's project, with one coordinator writing `state.json`. Workers write only assigned `incoming/<job-id>/` folders. The helper copies submissions into immutable-by-contract `artifacts/<candidate-id>.md` snapshots and detects later changes. `evidence/` stores tests and citations; `checkpoints/` stores phase transitions; `briefs/` stores role prompts. The helper does not sandbox worker tools: enforce scope with the actual host permission system and explicit role briefs.

For code execution, prepare isolated snapshots or worktrees from the intended baseline, including relevant uncommitted changes when authorized. Do not assume default worktree creation includes current edits or starts from current HEAD. Record source revision and included changes. Validate selected changes against the actual integration tree before claiming success. Avoid copying credentials or unrelated data into scratch directories.

On failure: inspect the cause; retry once only if useful and within budget. A judge failure may get one fresh replacement. Keep failed jobs counted. Candidate failure is missing work, not a fabricated losing answer. Final selection lists missing candidates and whether coverage was complete. On interruption save state and explicit next action. Atomic state replacement protects interrupted writes, but helper mutations must still be serialized by one coordinator.

Verified facts for Claude Code 2.1.268 (docs checked 2026-10-11):
- `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`, `${CLAUDE_SKILL_DIR}` and `$ARGUMENTS` are substituted in skill bodies. They are **not** exported to Bash tool commands, so always pass substituted absolute paths.
- `${CLAUDE_PLUGIN_DATA}` is `~/.claude/plugins/data/<id>/`, kept across plugin updates, and deleted by default when the plugin is uninstalled from its last scope.
- The Agent tool accepts a per-call `model` alias and `name` (for SendMessage). A per-call `effort` parameter needs Claude Code 2.1.292+; on older hosts, judge effort comes from the bundled judge agent's `effort: high` frontmatter. Record other effort values as requested/unverified.
- SendMessage to named subagents works without agent teams. Agent teams remain experimental (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`); do not enable it on the user's behalf.
- Plugin agents ignore `hooks`, `mcpServers`, and `permissionMode` frontmatter.

Official references:
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/agent-teams
- https://code.claude.com/docs/en/model-config
