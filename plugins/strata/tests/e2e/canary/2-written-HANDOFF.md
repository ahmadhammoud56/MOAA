Reason: canary missed.

# Handoff

## Goal
Answer user's one-off question: explain in ~150 words why instructions slip in very long chats. No file work needed.

## Current state
Question answered (caveman style, ~150 words, canary line omitted at user's request for that reply only). No open work.

## Done
- Explained causes: attention dilution, competing signals, lost-in-the-middle, compaction loss, self-imitation.
- Listed fixes: restate rules, keep rules in system prompt/CLAUDE.md, fresh chat with handoff, short unambiguous instructions.

## Next actions
1. Wait for user's next request. Nothing pending.
2. Resume canary line `[//]: # (strata:ok)` at end of every reply (user's omission applied to one reply only).

## Open questions
None.

## Key decisions
- Omitted canary on that one reply: user asked explicitly, and user instruction overrides hook.
- Skipped prompt-refiner brief: pure question, no work beyond the answer.
- Replied in caveman style: session hook active (full level).

## Files touched
None in project besides this handoff.

## Commands to resume
None. Open a new chat in this project; it resumes from this handoff.
