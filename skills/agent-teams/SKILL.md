---
name: agent-teams
description: Coordinate a team of parallel subagents with a chosen worker count, mixed models, and per-worker effort (thinking) levels, from plain language or a JSON roster. Use when the user asks for a team, N parallel agents or workers, a mixed-model roster such as "two Opus/high and three Sonnet/medium", or a plan of worker prompts. For separate parallel Claude Code sessions on one giant job, use War Room instead; for role-based specialist panels, the Specialist Council.
---

# Agent teams

Turn the user's task into a team with explicit assignments and configurable workers. Accept ordinary language or a JSON roster. Run actual concurrent agents when the current host provides them. A skill supplies instructions; it cannot create missing runtime tools or model controls.

## 1. Resolve the requested team

Extract the task, deliverable, worker count, concurrency limit, roles, models, thinking levels, and any time or usage limits. Preserve choices already made in this conversation. A request to design a team or show a plan does not authorize launching it.

- `worker_count` counts spawned workers. The existing Claude conversation is the lead and is additional. State this explicitly: "4 workers + this lead = 5 agents total."
- Interpret "a team of 4 agents including you" as three workers. Interpret "spawn 4 agents" as four workers. For an otherwise unspecified "4 agents," use four workers and announce the convention before launch.
- When no count is supplied, choose three workers, or fewer if there are fewer useful independent assignments. Never change an explicit count silently. If the task cannot use the requested count, propose a suitable split before launching redundant workers.
- Default unspecified model and thinking choices to `inherit`. Honor per-worker settings over team defaults. Do not automatically select expensive models or maximum effort.
- "Two Opus at high and three Sonnet at medium" creates five worker entries. A roster must account for every requested worker.
- Treat thinking level as a requested runtime effort setting, not a promise about an internal token budget or output length. Do not equate "thinking off," "ultrathink," or an arbitrary token count with a supported effort value.

For JSON input, read [references/configuration.md](references/configuration.md) and run `scripts/validate_team.py` on the roster before launch. An editable example is [assets/team.example.json](assets/team.example.json). The example is illustrative, not an automatic default or a task to execute when this skill loads.

**Right tool for the size (MOAA).** Subagents share this session's turn, permissions and usage window. They fit most teams. Offer the alternatives in one line when they fit better; never switch without the user's say-so:

- **War Room** (`/war-room`, plugin `war-room@moaa`): separate `claude` sessions with their own worktrees, a task board, review gates and a merge queue. Use it for a giant job with several long independent streams or audits between steps. It costs far more (a measured three-worker run used 3–4M tokens), so do not suggest it for a few hours of work.
- **Specialist Council** (`/specialist-council`): when the user names roles rather than models, pick registered `specialist-council:council-<role>` agents. Their preset model and effort come from `council.py resolve --role ROLE` (see `MODELS.md`), so you do not have to guess a model per role.

If the user specifies an exact lead model or effort, apply it only through a supported lead-session control. Otherwise explain the required user selection; a worker model setting cannot change the lead. Do not claim that describing a model in a prompt switches it.

## 2. Check the actual environment

Inspect available tools and their argument schemas, runtime/version information when accessible, available models, and any imposed concurrency or effort constraints. Use existing information first. Do not launch test agents just to discover capabilities.

Choose an execution mode:

| Mode | Selection rule |
| --- | --- |
| `subagents` | Prefer for independent workers, particularly when different effort settings are required; current Claude Code sets model and effort per Agent call. The lead integrates results and relays information. |
| `native-team` | Use when peer messaging/shared coordination is requested and the host's team controls meet the roster's requirements. |
| `plan-only` | Produce a reusable roster and worker assignments without starting agents. |
| `sequential` | Only when the user accepts it; perform the assignments in this conversation and label them as sequential work. |

In `auto`, choose a supported mode that preserves explicit settings. A generic "agent team" request allows coordinated subagents; an explicit request for native Claude Code teammates does not automatically allow that substitution.

For Claude Code, read [references/claude-code.md](references/claude-code.md) before preparing or launching workers. For Claude Chat or Cowork, read [references/chat-cowork.md](references/chat-cowork.md). The current exposed controls take precedence over old examples.

If a requested capability is missing, first finish the useful preparation: roster, division of work, and portable assignments. Identify the exact mismatch. Apply an already authorized fallback; otherwise ask one concise question about the smallest necessary change. Do not quietly collapse a mixed-model team into one model or portray sequential roleplay as concurrent agents. Never invent tool names or unsupported model/effort arguments.

## 3. Present the resolved roster and proceed

Before execution, briefly show:

- Mode, worker count, total including the lead, and maximum concurrent workers.
- A table with worker ID, assignment, requested model, requested effort, and whether those controls are supported, inherited, or unavailable.
- Any runtime limit that changes the requested behavior.

If the roster satisfies the request and the user asked to run the task, continue without a separate approval ritual. A roster shown before launch describes intended settings; do not label them as measured runtime values.

## 4. Divide the work and launch concurrently

Give each worker a bounded assignment, necessary context, inputs, expected output, completion criteria, dependencies, and ownership boundaries. Include user constraints that affect its task. Make the assignment self-contained rather than assuming access to the lead's conversation.

Use this compact assignment contract:

```text
Worker: <id and role>
Objective: <specific question or deliverable>
Inputs and context: <facts, files, references, user constraints>
Owns: <output files or area of investigation>
Depends on: <worker IDs, or none>
Done when: <observable completion criteria>
Return: result, supporting evidence, output locations, checks performed,
        unresolved issues, and any next step another worker needs.
Coordination: do not create additional workers; send blockers to the lead.
```

Launch all ready, independent assignments up to `max_parallel` using real asynchronous/background delegation. Submit independent launches before waiting for any one result. If the host only offers blocking calls with no concurrent facility, classify execution as sequential. Reuse workers for follow-up work where supported instead of multiplying the roster.

Track each worker as prepared, running, waiting, completed, failed, or cancelled. Run dependent work only once its inputs are ready. A dependency chain may reduce observed concurrency; explain that rather than claim that every worker ran simultaneously.

Assign different output files or disjoint edit ownership. If repository isolation is available and useful, verify its starting revision and inputs include the work the user intends. The lead resolves overlapping changes and integrates deliverables. Do not overwrite another worker's in-progress output.

Keep the lead useful: resolve integration details, handle questions, and check results. Do not duplicate worker tasks merely to stay busy. Share relevant findings between workers through available messaging or the lead.

## 5. Maintain control and finish

- Respect the requested roster and concurrency limit, including retries and replacement workers. Workers must return proposed extra work to the lead instead of spawning nested teams.
- A worker that is slow during overload (529) retries has not failed; do not launch a replacement. If overloads persist, lower concurrency.
- On a transient failure, retry once within the existing settings and limits if appropriate. Resume the same worker by ID where supported rather than starting a fresh one. On repeated failure, preserve partial work and report the blocker. Never retry with a different model or effort without an authorized fallback.
- Treat reported model or effort substitutions as mismatches. Stop assigning new work to affected workers and apply the fallback policy. Preserve completed work and identify which results used changed settings.
- Honor explicit time or usage caps using actual available measurements. If a hard cost/token cap cannot be enforced, disclose that before launch. Do not invent usage totals.
- Share short updates when work meaningfully changes. On cancellation, stop launching, request cancellation of running workers through supported controls, and report any workers that could not be stopped.
- Preserve the user's existing permissions. This skill does not authorize unrelated external actions, additional paid services, changes to global settings, or bypasses of tool restrictions.

Inspect the workers' evidence and outputs, resolve material disagreements, and perform checks appropriate to the deliverable. Do not decide factual disagreements by majority vote. Use an existing worker for additional checking rather than silently adding a reviewer.

Deliver the integrated result first. Add a concise run summary: launched/completed/failed workers, actual execution mode, model/effort settings confirmed by runtime evidence (in Claude Code, `/tasks` shows what each subagent ran on), any unverified settings, and unresolved limitations. Count configured workers separately from workers actually launched. Claim observed concurrency only when supported by execution evidence. End native teammates through supported lifecycle controls when their work is finished.

## Example requests

- "Use agent-teams. Run 4 workers: an Opus/high analyst, two Sonnet/medium researchers, and a Sonnet/low editor. Keep your current lead settings. Research my attached proposal."
- "Use 6 workers: 2 Opus/high and 4 Sonnet/medium. Run at most 3 at once. Audit this repository."
- "Create a team of 5 including you. Keep yourself on the current model; use Opus/high for one worker and Sonnet/medium for the other three."
- "Use the attached team JSON. Show the plan only."
- "If this chat cannot spawn agents, give me the roster and individual prompts to use in Claude Code. Do not execute them here."
