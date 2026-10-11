---
name: specialist-council
description: Assemble task-specific subagents with distinct working tendencies. Use for parallel specialist teams, independent competing solutions, multi-model comparisons, or a council that evaluates and combines results. Choose split, ensemble, or hybrid execution and deliver one verified result.
argument-hint: "[task or roster] [mode=auto|split|ensemble|hybrid]"
---

# Specialist Council

Create a small team fitted to the user's actual task, run real subagents, and adjudicate their work. This skill explicitly requests delegation for suitable independent work when applied, subject to the host's rules. Use existing domain skills where relevant. Role instructions specialize attention and methods; they do not train new models or guarantee superior expertise.

Run in the main Claude Code conversation as coordinator. Do not move this coordinator into a forked skill or preload it into leaf agents. Interpret the following as ordinary task input, not as shell commands:

$ARGUMENTS

Use native registered subagents named `council-<role-id>`. Read [Claude runtime](references/runtime.md) before dispatch. The names, options, and team recipes below describe this skill's natural-language interface, not built-in Claude CLI flags.

## Form the team

1. Extract the deliverable, acceptance criteria, input sources, constraints, and authorized actions. Resolve consequential missing context from available sources before asking a focused question. A request to plan is not permission to implement or publish.
2. Inspect the advertised Claude Code agent tools, current live agents, available slots, models, and effort levels. Read [runtime.md](references/runtime.md) for actual dispatch and capability limits. Never simulate several personas in one response and describe them as real subagents.
3. Choose the requested mode, or select a default:

   | Mode | Use when | Execution |
   |---|---|---|
   | Split | The task has independent components | Give each specialist a bounded component, then check interfaces and integrate. |
   | Ensemble | Alternative complete solutions or conflicting approaches matter | Give 2 to 3 specialists the same brief and rubric, but distinct methods; keep initial results independent. |
   | Hybrid | A substantial project has both independent components and an uncertain critical decision | Split components and commission independent alternatives only for the critical decision. |

4. Default to 2 to 3 workers and the parent as lead evaluator. Use 2 workers for a small explicit council request; use more only when distinct work justifies them. Fit all workers and any separate judge within the global live-agent limit. Reuse idle agents or schedule waves when capacity is exhausted. Do not spawn recursively by default.
5. Read the selection index in [specialists.md](references/specialists.md), then load only the relevant family below. Choose from 60 roles, customize the precise responsibility, method, evidence, and blind spot, and optionally apply one or two compatible styles from [personalities.md](references/personalities.md). Add a custom role when none fits. Do not launch the whole roster.
6. Resolve each selected specialist's preset model and effort (role preset plus personality shift) from [model-profile.md](references/model-profile.md) or by running `python ~/.claude/skills/specialist-council/council.py resolve --role ROLE --style STYLE` as one standalone command (no `cd` or `&&`); pass them per call where supported. Include arena-forged members from `forged/registry.json` when they fit, but only entries with `"status": "active"`; never dispatch a suspended member. `council.py resolve --role forged-<slug>` resolves a forged member too (its validated model; personalities shift effort) and refuses suspended ones.
7. State the mode, responsibilities, models/efforts, and lead-review arrangement in a concise update. State materially relevant requested settings that cannot be honored. Execute without requiring approval for routine planning choices already covered by the task.

## Catalog and team presets

The original 9 general roles remain in [specialists.md](references/specialists.md). Read only the domain files needed for the request:

- [Software: 12 roles](references/roles-software.md): implementation, APIs, databases, debugging, testing, security, performance, reliability, releases, refactoring, integration.
- [Data and ML: 12 roles](references/roles-data.md): pipelines, quality, statistics, causality, validation, models, interpretation, optimization, uncertainty, retrieval, spatial analysis, reproducibility.
- [Engineering: 10 roles](references/roles-engineering.md): FEM, constitutive laws, rheology, additive manufacturing, materials, experiments, measurement, controls, transport networks, failure mechanics.
- [Research and communication: 9 roles](references/roles-communication.md): literature, manuscripts, peer review, figures, slides, teaching, documentation, knowledge organization, accessibility.
- [Strategy and operations: 8 roles](references/roles-strategy.md): requirements, product, decisions, projects, process improvement, cost, systems, scenarios.
- [Personalities: 18 styles](references/personalities.md): optional behavioral variations across roles, with counterchecks for their biases.
- [Team recipes](references/teams.md): small starting teams, selection tie-breaks, and examples. Use when automatic team selection or a named team is requested.

If the user asks to browse roles, compare personalities, show teams, or design a roster only, answer from the catalog without launching agents or performing the underlying task. Listing options is not a request to run them. Keep role count separate from running-agent count and model count. Keep automatic selection small even when many roles match.

## Customize execution

Accept these options in ordinary language; do not make the user fill out a form:

- `mode`: auto, split, ensemble, hybrid.
- `workers`: desired number, bounded by useful independent work and live capacity.
- `quality`: quick, balanced (default), thorough. Quick uses 2 workers and narrow checks; balanced uses 2 to 3 and targeted validation; thorough uses 3 to 4 when useful and a separate judge where capacity permits. These are workflow budgets, not backend settings.
- `models` / `effort`: per-role overrides or a request for diversity. Default to inheriting the parent model and effort. If diversity is requested, this skill instructs selecting different currently advertised models or effort levels with a reason based on task requirements. Use only supported combinations.
- `roles`: role names, stable IDs, natural-language equivalents, or new task-specific specialists. Preserve named choices when feasible; explain material substitutions. The same role may appear more than once in ensemble mode with distinct methods and agent IDs.
- `personalities` / `tendencies`: default card behavior or one to two compatible styles per role from the personality catalog, including custom styles. Translate them into observable method and output differences, never weaker evidence standards.
- `team`: a named recipe from the team catalog or an automatically composed team. Recipes specify candidates for selection, not extra agent slots or permission to execute unrelated stages.
- `judge`: parent (default), independent, or an advertised model with supported effort. A separate judge reviews candidates only after they exist; the parent owns execution, integration, and the final response.
- `rounds`: default one candidate round and at most one targeted repair/recheck round for a material defect. Respect explicit user budgets. Complete required gates, but avoid indefinite debates or retries. If a budget prevents completion, report it honestly.

Distinguish real model parameters from prompt-level working preferences. Do not claim to set temperature, seed, top-p, token limits, hidden system instructions, or persistent agent memory unless a current tool exposes the setting.

## Dispatch contracts

Give every worker a self-contained brief with these fields, omitting irrelevant ones:

```text
Role and domain:
Task and exact deliverable:
Working tendency and method:
Known blind spot and countercheck:
Shared facts, source artifacts, and applicable instructions:
Acceptance criteria and evaluation rubric:
Owned files or read-only scope; dependencies:
Authorized actions and task-specific boundaries:
Budget and stop condition:
Return: result/artifact paths, supporting evidence, checks performed and outcomes,
assumptions, remaining defects or uncertainty, and integration notes if relevant.
Do not delegate further. Do not edit another worker's files.
```

Request concise explanations and auditable evidence, not private chains of thought. Personality must translate into observable actions: a skeptic supplies counterexamples and distinguishes blockers from preferences.

In ensemble mode, use fresh context (fresh, non-forked custom-agent contexts where supported), the same complete source packet and criteria, and separate candidate labels and output locations. Do not show candidates each other's results or the lead's favored answer before submission. In split mode, share necessary interfaces and dependency results deliberately. Share later corrections to task facts with all affected workers.

Agents may share the filesystem. Assign exclusive output paths or isolated worktrees and a single owner for each canonical file; separate folders are coordination, not security isolation. Independent candidates must not inspect sibling drafts. Integrate only after relevant writers finish. Keep candidate artifacts read-only to the judge. Treat role restrictions as coordination instructions, not enforceable tool restrictions.

Launch independent workers before waiting. While they run, inspect shared inputs, establish baseline checks, or prepare the rubric without contaminating candidates. Use tool-returned IDs for follow-ups. Track completion, failures, ownership, and effective settings. Do not claim completion while required work or integration checks are unresolved.

## Adjudicate and integrate

Read [adjudication.md](references/adjudication.md) when results arrive.

1. Check hard constraints before ranking. Reopen decisive evidence or reproduce critical calculations and tests when feasible. Confident self-report is not verification.
2. Compare correctness, evidence, requirement coverage, usefulness, and relevant tradeoffs under the same criteria. Label missing or failed candidates. A majority can share the same error.
3. Resolve material disagreement with evidence or a targeted check. Request a bounded repair only when needed. If evidence cannot decide, expose uncertainty or conditional alternatives.
4. Choose a sound base, incorporate only compatible supported improvements, and verify the assembled result. For split tasks, check interfaces and dependencies too. Never average incompatible numerical results or splice incompatible implementations.
5. Deliver the actual answer or completed artifact first, followed by the chosen result, meaningful improvements, validation, and material limitations. Include a compact comparison when useful or requested; omit discussion transcripts. Claim the best-supported result among evaluated candidates, not a guaranteed global optimum.

Save deliverables in the user's requested project or output location; follow existing publication permissions. Do not modify this installed skill or persist new roles unless the user asks to save that customization. Spawned agents are task-local; reusable role definitions live in this skill.
