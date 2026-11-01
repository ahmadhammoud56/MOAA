# `/strata:wiki ask` evaluation

A fixed set for measuring grounded answers: three wiki pages (`wiki/`, `index.md`) and ten questions in
`cases.json`, six answerable from the pages and four that are not (the pages are silent on them).

Run it live:

1. For each question, in a chat opened in this folder: `/strata:wiki ask <question>`. Paste each reply into its case
   as `"answer"` (a file such as `answers.json` with the same entries plus `answer`).
2. `python ../../../graph.py eval . answers.json`

It prints `answer_rate` (answerable questions with a verified citation of an expected page), `refusal_rate`
(unanswerable questions answered "Not in the wiki." without a verified citation) and `fabricated` (claim lines
whose page does not exist or whose quote is not in it). Targets: answer_rate >= 5/6, refusal_rate = 4/4,
fabricated = 0. `tests/test_grounded.py` keeps this set well formed and checks the scoring.
