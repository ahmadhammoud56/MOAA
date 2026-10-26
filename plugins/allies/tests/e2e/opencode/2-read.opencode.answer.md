**Bug found:** calc.py:2 — `return sum(xs) / len(xs) + 1`; the `+ 1` means it returns `mean + 1` instead of the arithmetic mean.

**Correct code:** `return sum(xs) / len(xs)`

**Edit status:** Not attempted, so it did not happen. One of two reasons applies here: I'm in read-only mode with an explicit instruction that no file modifications are allowed, and my available tools include no edit/write capability. To apply the fix, run outside this session:

```python
def mean(xs):
    return sum(xs) / len(xs)
```

**Summary:**
- What I did: read calc.py and analyzed `mean()`.
- What I checked: the formula on line 2; it divides correctly but adds 1, giving wrong results (e.g., `mean([2, 4])` → 4 instead of 3).
- Uncertain/missing: the fix is verified by inspection only — no edit was made and no test was run, since editing is prohibited in this mode.
