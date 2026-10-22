---
description: Code review. The planted defect is the window loop stopping one window early; a second reviewer should catch what one misses.
tags: [code, review]
runs: 1
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

Use the Specialist Council (a debugger and a test engineer) to review this function and report every defect with
the line it is on and a corrected version. Do not run it.

```python
def moving_average(xs, k):
    """Average of every window of k consecutive values; len(xs) - k + 1 results."""
    if k <= 0:
        raise ValueError("k must be positive")
    out = []
    for i in range(len(xs) - k):
        out.append(sum(xs[i:i + k]) / k)
    return out
```
