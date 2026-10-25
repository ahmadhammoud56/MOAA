# 0.15.1 hook fixes: findings and evidence

Investigated on 2026-10-25 on the maintainer machine (Windows 11, Claude Code 2.1.302 CLI and 2.1.308 in the
desktop app). "Fact" means read directly from a transcript, a debug log or a measurement. "Inference" means a
conclusion drawn from facts and not observed directly.

## 1. A pending handoff was used up without a new chat

- **Fact.** Handoff `20261025-131619-a4bf0ddc` showed `latest_consumed: true` while no interactive chat had been
  opened. Its `.consumed` names session `d03d773d-...`.
- **Fact.** That session's transcript has `entrypoint: claude-desktop`, model `claude-haiku-5-5`, and a first
  prompt of "Below is a conversation log from a Claude Code coding session. Create a summary to help the next
  session quickly understand the context. ..." Its SessionStart records hold "Strata: resumed from the handoff".
- **Fact.** The same project folder holds eleven such summary transcripts (2026-10-24 and 2026-10-25). Two of them
  (`b98c9252` at 13:18 and `d03d773d` at 13:22) took the handoff: the first took the first version, and the second
  took it again after Claude rewrote `HANDOFF.md` at 13:22:44.
- **Fact.** The summary text in `602fc8a2` ends with the parent chat starting a side session. That summary runs as
  part of starting a side session.
- **Fact.** This is not strata's own extraction run. Strata's prompt starts "You maintain a layered long-term
  memory", runs with `--no-session-persistence` (so it leaves no transcript), and always ran with
  `MOAA_STRATA_CHILD=1`, which makes every strata hook return early.
- **Fact.** That child run was still exposed to prompt-refiner and moaa-catalog: neither hook checked that marker.
- **Fix.** For startup and `/clear`, SessionStart now only records the handoff in the session state. The first
  `UserPromptSubmit` takes it unless the prompt is a machine prompt (the summary prompt above, also after a leading
  `<system-reminder>`). A session that never sends a prompt never takes it. Compaction is unchanged: the same session
  gets its own handoff at SessionStart, because no prompt comes next. Strata's helper processes now set
  `PROMPT_REFINER=off`, `MOAA_CATALOG_HINTS=off` and `MOAA_NO_UPDATE_CHECK=1` as well as `MOAA_STRATA_CHILD=1`.
- **Not done.** Skipping non-interactive sessions in general was considered and rejected. The hook payload has no
  reliable flag for it: desktop chats and the hidden summary run both report `entrypoint: claude-desktop` and the
  SDK prompt path, and headless `claude -p` is a legitimate way to continue work.

## 2. The first prompt after a restart got caveman's context but not the refiner's or the catalog's

- **Fact.** In the parent chat (`a4bf0ddc`), the first prompt after the restart (11:26:09Z) was stored as two text
  blocks. The first block is a `<system-reminder>` with the "Linked sessions now ..." status, which the desktop app
  adds. The second block is the user's words ("Is the new updates running after restarting"). The next prompt
  (11:44:03Z) had no such block and got both contexts.
- **Fact.** prompt-refiner 0.1.0 (`is_notice`) and moaa-catalog 0.4.0 (`hook_prompt`) treated every prompt whose text
  starts with `<` as a harness notice and added nothing. Run on that exact prompt, `refiner.py` 0.1.0 (git HEAD
  before the fix) returns nothing and 0.1.1 returns the brief context. The old catalog check is the same `<` test.
  Regression tests: `test_desktop_reminders_and_machine_prompts` (refiner) and
  `test_hook_fires_on_a_strong_match_and_stays_quiet_otherwise` (catalog).
- **Fact.** This side session's own first prompt also started with that `<system-reminder>` and also got caveman's
  context only.
- **Inference.** In the desktop chat, both hooks ran and returned nothing. That chat has no debug log, so their
  runs were not observed directly. The headless runs here do show both hooks running for every prompt.
- **Hypothesis (c), the cc-plugin-sec-default notice: refuted for our hooks.** Fact: the debug log of every
  headless run has `flightdeck: classic.UserPromptSubmit bypassed by cc-plugin-sec-default (tier user); beneath
  runs`, followed by the classic command hooks running (ours included) and `cc-plugin-sec-default@builtin
  classic.UserPromptSubmit settled in ~180ms (native link, next() included)`. The built-in mod skips only
  flightdeck's mod handler. Classic hooks still run beneath it. See `*.debug-hooks.log`.
- **Hypothesis (b), late loading of directory-source plugins: no evidence.** Fact: the hooks of all three plugins
  are registered before SessionStart in the debug logs, and strata's SessionStart hook did run in the restarted
  chat.
- **Hypothesis (a), first-run cost: not the cause of this miss, but a real risk, now fixed.** Fact: on the C-user
  payload, the hook commands take about 0.08 to 0.14 s each, measured through the bash launcher loop
  (`summary.json`, `hook_wall_times_s`), and about 0.13 to 0.17 s inside Claude Code (debug logs). Fact: rebuilding
  the catalog skill index takes 4.98 s warm for 3,645 skills. Fact: on 2026-10-22 the catalog prompt hook was
  cancelled after 10,207 ms (`timedOut: true`, transcript `a4bf0ddc`, line 5434). Inference: that timeout was a
  rebuild on a cold disk. The index is rebuilt whenever `settings.json` changes, which happens often. Fix: hooks
  never rebuild the index inline. SessionStart and a stale prompt start a detached `catalog.py index`, and the
  prompt uses the previous index in the meantime.

## Live evidence (run_machine_e2e.py, Haiku, throwaway folder, plugins loaded from this checkout)

| Run | What it is | Expected |
| --- | --- | --- |
| A-summary | the desktop app's summary prompt | handoff stays unconsumed; no handoff, refiner or catalog context |
| B-child | an ordinary prompt with strata's helper environment | the same |
| C-user | a first prompt with a leading `<system-reminder>` | handoff consumed and given; refiner and catalog context; Claude says it resumed |

The results are in `summary.json`. Each run's hook-context attachments from the transcript are in
`*.transcript-hits.jsonl`, the hook lines of the debug log are in `*.debug-hooks.log`, and the reply is in
`*.result.txt`. The installed copies of the three plugins were switched off for these runs with `--settings`, so
only this checkout's code ran.
