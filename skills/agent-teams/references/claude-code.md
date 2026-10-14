# Claude Code adapter

Checked against the Claude Code changelog through 2.1.296 (October 2026). Verify the installed version and exposed controls when using this adapter.

## Mixed models and thinking levels

**Preferred: per-call settings.** Since 2.1.292 the Agent tool takes an `effort` parameter next to `model`. Give each worker its own `model` and `effort` on its Agent call. No agent files, no restart. Check the live Agent schema first; if `effort` is absent, the CLI is older and you need the definition route below.

- The per-call `model` takes tier aliases only (`haiku`, `sonnet`, `opus`, `fable`). A full ID such as `claude-opus-5-5` fails validation. To pin a full ID, use a definition's frontmatter `model:`.
- Effort values are `low`, `medium`, `high`, `xhigh`, `max`. Leave the field out to inherit.
- For a role-based roster in MOAA, take each worker's model and effort from the Specialist Council: `python "<specialist-council plugin dir>/council.py" resolve --role ROLE`, run as one standalone command. Dispatch `specialist-council:council-<role>` agents directly when a role fits; their frontmatter already carries the preset. The table is in `MODELS.md`.

**Overrides that silently defeat per-worker settings.** Check the `env` block of the user, project and local settings files before promising a mixed roster:

| Variable | Effect on the roster |
| --- | --- |
| `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` | Forces one model on every subagent, ignoring per-call and definition models. A mixed-model roster is impossible while it is set. |
| `CLAUDE_CODE_SUBAGENT_MODEL` | Only the default. Per-call and definition models still win. |
| `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` | Puts every Workflow tool agent on one model. Ordinary Agent calls keep their own. |
| `CLAUDE_CODE_EFFORT_LEVEL` | Can override effort settings. Report it as a mismatch if it differs from the roster. |

**Long-running workers.** A definition (or `--agents` entry) can set `autoCompactWindow` so that worker compacts earlier than the main conversation. Use it for workers that read many files over a long run; leave it out for short jobs.

**Fallback: one definition per worker.** On older CLIs, or to pin full model IDs, create a uniquely named definition under the project's `.claude/agents/` from the resolved settings. Confirm it loads before dispatch; a new agents directory may need a restart. Use supported tool restrictions without inventing tool names, and keep unrelated definitions intact. [Subagent documentation](https://code.claude.com/docs/en/sub-agents). A minimal example:

```markdown
---
name: team-proposal-analyst
description: Analyze the assigned proposal and return evidence and open questions.
model: opus
effort: high
---

Complete the bounded assignment supplied by the lead. Return your result,
evidence, unresolved issues, and relevant output locations. Do not delegate
to additional agents. Send requests for further work to the lead.
```

Omit `effort` for inheritance. Use `model: inherit` for inherited models. Invoke the loaded worker type with its assignment and real background/concurrent controls.

**Confirm what actually ran.** `/tasks` and the agent detail dialog show the model and effort each subagent ran on. Use that as the runtime evidence in the run summary; never ask a worker to guess its own model. Accepted effort levels depend on the model and organization policy, and the runtime may lower an unsupported level. A prompt asking a worker to think harder does not set effort. [Model and effort configuration](https://code.claude.com/docs/en/model-config).

Do not change one process-wide effort variable between concurrent launches: it cannot express separate worker settings. Preserve the lead's configuration. If the host cannot honor explicit settings, return to the skill's fallback procedure.

## Failure modes in wide fan-outs

- **Overloaded (529) errors.** Many parallel workers can hit 529s. The runtime retries with backoff, so a slow worker is not a failed one. `CLAUDE_CODE_OVERLOADED_RETRY_BASE_DELAY_MS` and `CLAUDE_CODE_OVERLOADED_RETRY_MAX_DELAY_MS` lengthen that backoff; the MOAA installer sets the maximum to 60000. If 529s persist, lower `max_parallel` rather than retrying more.
- **Workflow tool cap.** Agents inside one Workflow run share a concurrency limit; `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` (1–256) raises it. This does not apply to ordinary Agent calls.
- **Resuming a worker.** Background subagents can be resumed with `SendMessage` by agent ID, including after a session restart. Reuse a worker that way instead of spawning a replacement that loses its context.

## Native Claude Code teams

Native teammates can use different models, but inherit the lead's effort. Their documented application of custom subagent definitions does not provide independent effort settings. They require an interactive session with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. [Agent-team documentation](https://code.claude.com/docs/en/agent-teams).

For a native-team roster that requires different effort values, explain the mismatch and propose ordinary parallel subagents. In `auto`, select subagents directly when supported. Do not temporarily switch the lead's effort to try to assign permanent effort levels to native teammates.

An optional settings merge to enable native teams is:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

Prepare this change only when native teams are selected. Preserve existing settings; apply changes within the user's authorization. Independent-effort subagents do not need this flag. When the flag is active, named agent launches can become teammates, so verify the launch mode before relying on per-subagent effort. Current versions manage team setup and cleanup automatically; do not assume legacy TeamCreate/TeamDelete tools exist, or edit runtime team-state JSON. [Native team behavior](https://code.claude.com/docs/en/agent-teams).

The lead must remain in control until results are collected. If registration or a restart blocks launch, leave prepared definitions and an exact resume instruction; report zero launched workers. Never present file creation as proof that a team ran.
