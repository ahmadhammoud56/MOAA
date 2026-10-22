---
description: Smoke test. The council should dispatch at least two specialists and agree on 221 = 13 × 17.
tags: [smoke, math]
runs: 1
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

Use the Specialist Council with two independent specialists: is 221 prime? If not, give its prime factorization.
