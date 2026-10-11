# Claude Code adapter

Documentation checked September 3, 2026. Verify the installed version and exposed controls when using this adapter.

## Mixed models and thinking levels

Custom subagents accept `model` and `effort` frontmatter; this is the preferred route for workers with different thinking levels. Store definitions under `.claude/agents/` for the chosen project. Confirm they load before dispatch; a newly created agents directory may require restarting Claude Code. [Subagent documentation](https://code.claude.com/docs/en/sub-agents).

For each worker, create a uniquely named definition from its resolved settings. Use supported tool restrictions appropriate to its assignment, without inventing tool names. Keep existing unrelated definitions intact. A minimal example:

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

Omit `effort` for inheritance. Use `model: inherit` for inherited models. Invoke the loaded worker type with its assignment and real background/concurrent controls. Check for precedence overrides and actual substitutions; inspect available runtime status such as `/tasks` rather than asking a worker to guess its own model. [Subagent configuration](https://code.claude.com/docs/en/sub-agents).

The effort environment variable can override frontmatter. Accepted levels depend on the model and organization policy, and unsupported levels may be reduced by the runtime. Validate the requested combination, inspect relevant overrides, and report differences. A prompt asking a worker to think harder does not establish a runtime effort setting. [Model and effort configuration](https://code.claude.com/docs/en/model-config).

Do not change one process-wide effort variable between concurrent launches: it cannot reliably express separate worker settings. Preserve the lead's configuration when preparing workers. If the host cannot honor explicit settings, return to the skill's fallback procedure.

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
