# Claude Code runtime

Use the main conversation as coordinator. This package installs native leaf agents named `council-<role-id>` and one inline `/specialist-council` skill. The coordinator has no `context: fork` field. Workers have `disallowedTools: [Agent]` and must not delegate. This is the council's chosen topology, not a claim that all Claude Code versions prohibit nested agents.

## Discover and dispatch

1. Use the live Claude Code tool descriptions and registered agent identifiers. Current versions use the Agent tool; older versions may expose Task. Do not call ChatGPT collaboration APIs or fabricate tool fields.
2. Resolve a requested role through `catalog.json` when available or the role cards. For standard installation, select `council-<role-id>` as the actual registered custom agent type. Do not use the display title as an assumed tool identifier. If agents are missing, report that the agent files also need installation; a skill folder alone does not register sibling agent files.
3. Dispatch the selected custom agents with the complete common input, role-specific assignment, personality overlay, rubric, ownership, budget, and return contract. Where the live API names the type field `subagent_type`, supply the exact registered identifier there. Use whatever equivalent field the current API actually advertises.
4. Launch independent work before waiting for completion. Use concurrent dispatch or background execution where available and permitted, then collect every required result. If this host cannot run concurrently, report sequential execution. Do not assume a fixed global slot count; default to 2 to 3 workers and schedule waves within actual capacity.
5. Track returned IDs and statuses. Use the advertised task/output, resume, or messaging tools for that version. Do not assume a resume creates fresh context: use a new agent for an independent initial candidate. A failed or partial result is not a completed candidate.

In ensemble mode use fresh custom-agent sessions with the same neutral source packet. Do not choose a conversation-fork shortcut that reveals the parent's preferred answer. Each candidate owes a complete solution, even when their styles differ. Do not share initial candidate results until submission. For hybrid work, identify which jobs depend on earlier results and launch only independent jobs together.

For a newly invented role, keep its task-local identity separate from the registered agent type. Use the nearest registered council agent as a carrier, or a currently advertised general-purpose agent, and provide the custom role's complete responsibility, method, evidence criteria, personality, and countercheck in its brief. Never fabricate a `council-<new-id>` registered type. If an existing card conflicts with the new role, use the general-purpose carrier. Do not persist a new agent definition unless the user requests it. The same registered type can be invoked more than once for independent variants, each with a distinct task identity and fresh context.

The registered agents contain their role cards, but do not inherit all parent-invoked skill content. Include the selected personality's behavior and bias countercheck directly in each worker brief. Do not merely tell a worker to be a personality whose definition it has not received. Do not preload the coordinator skill into workers.

## Models, effort, and custom settings

Every agent has a preset `model` and `effort` in its frontmatter, chosen by specialty and role (see [model-profile.md](model-profile.md); source of truth `profile.json`, applied by `council.py`). Tiers: haiku `claude-haiku-5-5`, sonnet `claude-sonnet-5-5`, opus `claude-opus-5-5`, fable `claude-fable-5-1`. Explicit IDs pin the 5.5 generation; a Claude Code build that does not recognize an ID will fail to load that agent, so update the CLI rather than editing models ad hoc.

Before dispatch, resolve each worker's setting: `python "${CLAUDE_PLUGIN_ROOT}/council.py" resolve --role ROLE --style STYLE1,STYLE2` as one standalone command (no `cd`, no `&&` chaining); use the plugin root path the skill was loaded with. For a forged member pass `--role forged-<slug>`. The installer pre-approves `python ...specialist-council...council.py ...` commands; a chained `cd ... && python council.py` is not approved and triggers a permission prompt. A personality shifts effort only, never the model; the resolved effort goes in the Agent tool's per-call `effort` field when the host exposes it. Otherwise the frontmatter effort applies and the shift is reported as requested only. Leave the per-call `model` out by default: the agent's frontmatter already pins the full model ID. The Agent tool's `model` field accepts only the tier aliases `haiku`, `sonnet`, `opus` and `fable`, never a full ID such as `claude-opus-5-5`, which fails input validation. A user's explicit model or effort request overrides the preset; pass it as the per-call tier alias and `effort`, and record it. Do not upgrade a whole team to the top tier because a task "seems important"; change one role deliberately and say why.

Role agents are plugin agents named `specialist-council:council-<role>`. Arena-forged members are user agents `council-forged-<slug>` and carry the model and effort under which they were validated; see `~/.claude/specialist-council/forged/registry.json`. Use only members whose registry status is `active`. Suspension (a later failed validation) unregisters the agent card and parks it as `~/.claude/specialist-council/forged/<slug>/agent.suspended.md`; `council.py check` fails if a non-active member still has a registered card or an active member is inconsistent.

If a requested setting is unavailable, preserve the task and disclose the fallback. Do not retry authorization failures through another model, agent, or shell process. If the runtime reports effective settings, use them; otherwise label settings requested or inherited. A model switch does not prove better specialization.

For a separate judge, finish and freeze candidates first, then dispatch `specialist-council:council-arbiter` with the task, neutral candidate labels, evidence, and rubric. An invocation-level supported model override can select a judge model. The parent still owns final integration and validation. Never rank by model name or persona.

## Files, tools, and lifecycle

Agents normally share project files. Assign disjoint writes and one owner for shared configuration and final artifacts. Worktree isolation may be used only when the project and host support it; verify its actual source revision and required uncommitted inputs before trusting the comparison. Worktree defaults can differ from the parent's current checkout. Separate folders do not enforce access control.

Background execution can have different tool availability or permission behavior. If a required tool is unavailable, use an allowed foreground workflow or return the limitation. Do not enable permission bypasses, add MCP servers, change global settings, enable experimental features, or install dependencies merely to make delegation work.

Handle user corrections across affected workers, preserve deadlines and budgets, stop affected workers on cancellation, and require results from every indispensable assignment before reporting completion. Keep all external actions within the user's existing task authorization.

## Compatibility sources

Checked against official documentation on 2026-09-05. Runtime details vary by version and organization policy; these links support rechecking precise fields:

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude Code custom subagents](https://code.claude.com/docs/en/sub-agents)

This port has package and installer verification plus independent review. It must not claim live Claude Code execution unless an actual Claude Code session has been run successfully.
