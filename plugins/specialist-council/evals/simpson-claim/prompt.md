---
description: A statistics claim that hides Simpson's paradox; a statistician should overturn the naive reading.
tags: [stats, review]
runs: 1
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

Use the Specialist Council (a statistician and a challenger) to check this claim and say whether it holds.

"Treatment A is better than treatment B. Overall, A cured 78% of patients (273 of 350) and B cured 83%
(289 of 350), but that's only because B got the easy cases: for small stones A cured 81 of 87 and B 234 of 270;
for large stones A cured 192 of 263 and B 55 of 80. So A is better in both groups."

Check the arithmetic and the conclusion.
