# Mode procedures

All modes use the shared evaluation contract and job ledger. N means initial candidates, C means concurrent workers, R means bounded rounds. Every role call, including a resumed agent turn, consumes a job. Save a coordinator checkpoint at each barrier; the helper supplies bookkeeping, not an automatic mode scheduler.

## 1. Judge

1. Generate N independent, complete answers using distinct strategy cards. Workers cannot read other candidates at this stage.
2. Start one strong judge identity. Give it the task/rubric and every anonymous submission, in seeded order. For small answers it may read all in one pass. For large answers use batches of at most eight full answers, resuming the same judge with a durable assessment ledger. Reserve each resumed turn as a new job. Every candidate must be fully read and individually assessed; no preliminary model may filter submissions out.
3. Have that same judge compare the leading complete candidates, revisit close calls, and choose the strongest eligible answer. The helper's rank is an arithmetic aid; record the qualitative rationale too. If the judge was lost, a replacement must revisit the scored evidence and finalists; disclose the replacement instead of claiming one continuous judge.
4. Use a separate fresh validator on the winner. Deliver it unchanged unless the user's task requires integration. Do not merge discarded solutions in this mode.

Plan: N generation calls + ceil(N/8) judge turns + 1 selection turn + 1 final validation. For N=100 this is 115 calls before retries. Actual context size can require more judge turns; stay within the configured budget or stop with incomplete coverage. Never pretend 100 complete long artifacts fit one prompt.

## 2. Tournament

1. Generate N complete independent answers. Seed pairings; an odd participant receives a bye.
2. Per match: two critics attack the opposing answer with checkable counterexamples; each original participant then revises its own answer once; one judge reads both full revisions, attacks, responses, and rubric. This is five calls per contested match, excluding initial generation.
3. Register revisions with new IDs and parent links; replace each entrant's current version in the bracket roster. Use `pair` only after revisions are frozen, then `match` to record the verdict. For the attack phase, get pairs with `pair --dry-run` (opens no round, changes no bye counts) and save them in the coordinator checkpoint and preserve exactly those assignments when opening the adjudication round. Use `pair --fixed` to retain them.
4. Advance the winner, archive the loser, carry byes forward. A bye earns no score or Elo update. Stop when one remains; a missing match verdict prevents advancement. Missing candidates must be reported as failed entrants; never create answers for them.
5. Validate the champion against the original acceptance contract. If the bracket ends with an ineligible answer, report that no acceptable champion was found.

N entrants require N-1 contested matches when all submit, so N + 5(N-1) calls, plus final validation. N=100 means 596 in this implementation. No extra final synthesis. A tied match gets the judge's explicit tie-break reason; if no defensible distinction exists, record a seeded procedural tie-break and disclose it. Never describe a procedural tie-break as evidence of superior quality.

## 3. Swarm (collaborative pressure)

1. Generate all N drafts privately before any cross-reading. This preserves some independent exploration.
2. Open a shared bulletin containing evidence-backed findings, failed approaches, and artifact paths. With the file backend, `exchange --round xR --ids ...` enforces the private-draft barrier and bounded peer groups. Assign rotating peer groups; agents can inspect peers' full outputs and exchange targeted messages within a bounded round. Use the runtime adapter's direct communication or disclose file-exchange fallback.
3. Give each active candidate a revision turn. Require a short change log: which findings were adopted, rejected, or remain unresolved. New revisions are new IDs. Preserve citations to borrowed work; never treat a repeated claim as independent corroboration.
4. Independently assess revisions, then `cull --fraction 0.5 --min 2` retains the top ceil(active/2), minimum two. Archive the others. Keep materially different approaches among exact scoring ties. Do not hide a better candidate to preserve diversity.
5. Repeat until R rounds, target, plateau, or budget. A strong judge selects the final full answer; fresh validation determines acceptance. Do not silently combine parts (choose synthesis if desired).

Competition brief: “Only the strongest verified submissions continue in this run. A failing submission loses its slot. Your saved findings remain available; honest corrections, reproducible evidence, and useful discoveries improve your standing.”

This implements elimination pressure. Do not claim permanent model deletion, threaten harm, or tell agents to hide failures for survival. A skill can retire a session or candidate; it cannot erase an underlying model. There is no promised quality improvement from threats.

## 4. League (Elo)

1. Generate N complete answers and freeze them for the entire season. Judge them against the absolute rubric before matches. No revision is allowed to keep an earlier answer's rating.
2. Run R rounds (default five). Round one uses seeded order. Later rounds prefer opponents with close ratings and no prior meeting; rotate byes toward those with fewer byes. The helper uses a deterministic greedy pairing, not a claim of globally optimal Swiss pairing. Rematches are permitted only when its remaining pairing pool has no fresh opponent, and appear in the ledger.
3. Each pair gets an independent comparative judge who reads both full answers and returns assessments on the same rubric. The helper checks the supplied assessments and derives win/loss/draw. Exact ties are draws. Elo starts at 1500, K=24:
   `E_A = 1 / (1 + 10 ** ((R_B - R_A) / 400))`; `R_A' = R_A + 24 * (S_A - E_A)`, where S is 1, 0.5, or 0. Update both ratings once from their pre-match ratings.
4. Rank by Elo, then absolute eligibility/score and number of matches for ties. Give the strongest three eligible candidates (or all if fewer) to a strong judge for final selection against the original rubric. Record why an absolute-quality choice differs from the Elo leader.
5. Fresh validation decides acceptance. Rounds, opponents, draws, byes, and small-sample uncertainty belong in the receipt. Five matches are not a precise rating estimate. Never stop solely because an Elo number crosses the 0–100 quality threshold.

If revision is requested, end the season, register new snapshots, reset ratings in a new run, and label results separately.

## 5. Evolution

1. Generate and assess an initial population of N. This is generation zero and counts toward the requested total of R generations (default three).
2. After each complete generation, run `progress --generation G`, then `cull --keep E` to retain the top E=max(1,ceil(N/4)) immutable elites. Archive the other N-E. Build inheritance bundles from selected parents and archived competitors: actual solution, verified findings, failed experiments, test data/results, critique, unresolved questions, artifact hashes, and source IDs. Inheritance is explicit files, not model-weight updates or hidden memory transfer.
3. Fill the N-E vacant slots with fresh descendant agents. Use about 20% exploratory immigrants (at least one when vacancies permit), each with a new strategy and access to the failure archive; the rest inherit one or two parents and receive a concrete mutation objective. Examples: remove a dependency, test a disputed assumption, replace a failing algorithm, combine compatible subcomponents. Every descendant links parent IDs and adopted evidence.
4. Assess descendants using the unchanged rubric; retain elites without rewriting their files. Track the best eligible score, unresolved gates, and diversity. Do not call a generation improved merely because it is longer or more confident.
5. At target, R, plateau, or budget (including an early stop at generation zero), reserve a job with `--role synthesizer` and have the strong synthesizer read the best diverse complete candidates plus a coverage manifest of archived findings. It selects compatible strengths, explicitly resolves contradictions, and creates a new final candidate with a provenance map. Reuse archived results only after checking their evidence.
6. Fresh validation of that synthesis is mandatory. Before synthesis, give the best elite its own fresh final validation so the helper's regression guard has a baseline. If synthesis regresses (`conclude` refuses it), deliver the best independently validated prior candidate and label the synthesis rejected. Budget must reserve synthesis plus validation; reaching the generation limit is not the same as reaching the target.

N is population size, not lifetime spawned count. Three full generations at N=100 with 25 elites produce 250 candidate-generation calls, plus evaluation, synthesis, and validation. Threshold and plateau checks happen after full generations; synthesis still follows an early generation stop.

## 6. Synthesis

1. Allocate N agents across whole-task independent solutions and complementary perspectives identified from the task. At least two agents produce complete solutions. Other agents can focus on evidence, implementation, failure analysis, usability, or performance, but each must connect its contribution to the shared acceptance contract.
2. Evaluate complete answers on the full rubric. Every specialist artifact also gets a recorded `assess` (its whole-task gates normally `unverified`). Assess specialist artifacts for their assigned scope and evidence without treating them as complete solutions; label specialist scope in the checkpoint. Do not count a partial specialist as passing whole-task gates.
3. A strong synthesizer (job reserved with `--role synthesizer`) examines the full contribution manifest and all selected source artifacts, builds a coverage map, and chooses compatible components. It must explain conflicts and specify integration interfaces, not concatenate answers or hold a popularity vote.
4. Register the combined result as a new candidate with all contributor IDs. Fresh validation checks both requirement coverage and integration seams. If it fails, return unmet checks and the best usable validated alternative within budget.

## 7. Red-team repair

1. Split N initial participants: B=max(1,ceil(N/2)) builders and N-B adversarial reviewers. Only builders generate answer candidates; report this difference from N complete answers. Reviewers receive fixed candidate assignments after drafts are frozen. Extra builder coverage comes from the coordinator's validation plan, not an uncounted new agent.
2. Critics target concrete cases: invalid inputs, counterexamples, conflicting evidence, requirement omissions, interface failures. No quota of invented defects. Save reproductions and severity. Red-team agents do not judge their own attacks as proven.
3. Builders reproduce or rebut each claim and repair their answer. Register new versions. Independent judges verify fixes, assess full answers, and keep unresolved findings. Repeat at most R rounds; reassign critics to reduce familiarity bias.
4. Select the strongest answer and run fresh final validation with held-out cases when available. Stop at verified target, plateau, R, or budget; do not suppress failed checks to declare victory.

## 8. Cascade (successive halving)

1. Generate N short proposals under the same declared proposal budget (for example 400 words each), with approach, assumptions, evidence plan, and main risk. These are proposals, not completed answers.
2. Judge all proposals on feasibility, requirement fit, and testability. Mark unexecuted completion gates unverified. Retain ceil(N/2) with `cull --fraction 0.5`, then ask survivors for deeper implementations and supporting evidence. Scores at a proposal stage are selection signals only.
3. Repeat until two or fewer remain or R stages have completed. Increase per-candidate work allowance per stage while keeping global limits. Each survivor writes a new full snapshot; archived proposals stay accessible.
4. Give remaining finalists one complete-answer turn if they still have proposals. A strong judge selects using the full rubric. Fresh validation establishes acceptance. Reserve those final calls before early-stage spending.

Report the number of initial proposals and fully implemented candidates separately. A promising idea eliminated early might have won with more effort; this is a cost/coverage tradeoff, not exhaustive proof.
