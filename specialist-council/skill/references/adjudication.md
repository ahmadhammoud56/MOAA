# Evaluation and synthesis

Define success before dispatch. Use a short common rubric for simple work and a requirements/evidence/checks table for complex tasks. Do not let candidates choose different rubrics.

## Evaluate in order

1. Hard validity: explicit constraints, factual or mathematical correctness, and usable deliverables. Style cannot outweigh a hard failure.
2. Evidence: supported sources, reproducible calculations, observed checks, and uncertainty. Verify decisive citations against original sources when accessible. Distinguish reported checks from checks the lead repeated.
3. Coverage: all required outcomes and relevant edge cases.
4. Practical quality: usability, maintainability, feasibility, clarity, and task-specific tradeoffs.

Use pass/partial/fail with concise evidence by default. For requested numeric scoring, set weights before viewing candidates and state that scores are judgments, not calibrated probabilities. Do not average across hard failures.

Give a separate judge neutral candidate labels and omit persona/model labels where practical. Include the full task, rubric, immutable outputs, raw inputs needed for checking, and relevant test access. Do not trust an output merely because an agent produced it.

## Resolve disagreement

- Factual or numerical: inspect sources, recompute, or construct a counterexample.
- Different assumptions: identify them and select those matching user constraints; retain conditional answers if undecidable.
- Tradeoffs or preferences: use the user's priorities and explain compromises.
- Unsupported confidence: require evidence or downgrade the claim.

Default to one targeted repair/recheck round involving only relevant workers. If all candidates fail, repair the most promising one or produce a fresh checked result locally within budget. Do not crown a failing candidate. If still blocked, explain what remains incomplete.

## Synthesize safely

Choose a verified base. Preserve provenance for consequential claims and changes. Adopt only improvements compatible with the base assumptions, interfaces, units, and evidence. Repeat decisive acceptance checks after combination because individually valid pieces can conflict.

For code, inspect the final diff and exercise changed behavior and interfaces. For quantitative work, recompute decisive quantities from original inputs and check units. For research, preserve claim-to-source relationships and unresolved contradictions. For visual artifacts, inspect the assembled output with the applicable rendering workflow. Apply only checks relevant to the task.

## Final response

Lead with the answer or finished deliverable. Briefly state the chosen approach, improvements adopted, checks, and limitations. Include a comparison only when useful or requested:

| Candidate | Outcome | Decisive evidence or defect | Contribution retained |
|---|---|---|---|
| A | Pass / partial / fail | Concrete observation | Specific part or none |

Report required-agent failures, unavailable settings, and sequential waves accurately. Do not invent token totals, costs, timings, consensus, benchmarks, or checks. Describe the best-supported result among evaluated candidates, not guaranteed superiority. Agreement among agents is not independent experimental replication.
