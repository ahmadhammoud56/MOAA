**Cannot complete the task.** `calc.py` does not exist.

What I checked:
- Searched the current working directory (`plugins/allies`) and the whole `claude-kit` workspace for `calc.py` — no matches.
- Grepped all `*.py` files for `def mean` and `mean` — no `mean()` function exists anywhere (`allies.py` only uses the English word "means" in comments).
- Listed `plugins/allies/` contents: only `allies.py`, `members.json`, `README.md`, `LICENSE`, `skills/`, `tests/`, plugin metadata.

What is missing:
1. The file `calc.py` — so I can neither review `mean()`, name a bug, nor attempt a fix.
2. Even if it existed, I am in read-only (plan) mode, so I could not edit the file in this phase. **The edit was not attempted and did not happen.**

Plan if you proceed: confirm the correct path to `calc.py` (perhaps it was meant to be created or lives elsewhere), then exit plan mode so I can read it, analyze `mean()` for arithmetic-mean correctness (common bugs: `sum/n` vs integer division, empty-list ZeroDivisionError, floating-point accumulation error), propose/apply a fix, and verify with a quick test.
