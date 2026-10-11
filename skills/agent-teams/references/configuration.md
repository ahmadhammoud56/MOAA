# Team configuration

This JSON format belongs to this skill. Claude interprets it and translates supported choices into actual runtime controls. It is not an Anthropic settings format, API request, or native team-state file. Do not paste it into Claude's settings.json.

Use [../assets/team.example.json](../assets/team.example.json) as an editable starting point. Natural language can supply the same choices without a file.

## Fields

| Field | Meaning and default |
| --- | --- |
| `version` | Format version; currently `1`. |
| `task` | Requested task. May be omitted if supplied in the conversation. |
| `worker_count` | Positive integer; number of spawned workers, excluding the lead. |
| `max_parallel` | Positive integer no greater than `worker_count`; defaults to `worker_count`. Counts running workers, excluding the lead. |
| `execution_mode` | `auto`, `subagents`, `native-team`, `plan-only`, or `sequential`; default `auto`. |
| `fallback` | `ask`, `plan-only`, or `sequential`; default `ask`. Applies when execution cannot meet the requested settings. |
| `lead` | Optional object with `model` and `effort`; each defaults to `inherit`, preserving the current conversation. |
| `defaults` | Worker defaults: `model` and `effort`, each defaulting to `inherit`. |
| `workers` | Array of worker specifications. If provided, its length must equal `worker_count`. If absent, generate exactly that many assignments from the task. |

Worker fields:

| Field | Meaning |
| --- | --- |
| `id` | Required unique lowercase name using letters, numbers, and hyphens; 1-48 characters, starting with a letter. |
| `role` | Required short role description. |
| `assignment` | Optional specific task; infer it from the overall task and role if omitted. |
| `model` | Optional model family alias or exact runtime-supported model ID, or `inherit`. Overrides `defaults.model`. |
| `effort` | Optional `inherit`, `low`, `medium`, `high`, `xhigh`, or `max`. Overrides `defaults.effort`. These are request values, not a claim that every model/host supports them. |
| `depends_on` | Array of other worker IDs; defaults to empty. |
| `outputs` | Optional array of intended output locations. Respect the user's authorized workspace. |

## Resolve and validate

1. Apply the user's latest explicit changes to the JSON, then validate the resulting roster. A partial follow-up changes the named fields and preserves the rest.
2. Reject malformed JSON, unknown fields, wrong types, blank IDs/models, duplicate IDs, non-positive counts, and inconsistent worker counts. An integer field must not accept a boolean.
3. Reject self-dependencies, missing dependency IDs, and cycles. Review duplicate output locations for conflicting ownership.
4. Resolve each worker's settings: its explicit value, otherwise the team default, otherwise `inherit`. Explicit `inherit` means the lead's current effective setting; it does not mean the worker default. Keep inheritance marked as such when the lead's actual setting cannot be inspected.
5. Validate the resolved model/effort combination against the current host. A syntactically valid roster may still be impossible to execute.
6. Do not clamp the user's concurrency setting silently. If an actual host limit is lower, explain the needed batching and follow the fallback policy. A user instruction such as "batch if necessary" is sufficient authorization.

`fallback: plan-only` means finish the roster and portable worker assignments and stop before execution. `fallback: sequential` authorizes the lead to do the work sequentially if delegation or requested controls cannot be provided; make the loss of per-worker model/effort control explicit. `fallback: ask` means ask about the specific mismatch after preparing the useful plan. A fallback never authorizes a paid external runner or changes to unrelated configuration.

When no task is available, produce the requested team configuration and ask for the task only if the user also asked to run it. Do not execute an example task merely because it appears in the sample file.
