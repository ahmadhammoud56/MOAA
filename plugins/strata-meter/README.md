# strata meter (mod)

A Claude Code mod with one **Meters** panel, styled like the desktop app's own cards: each row a label, a value and a
real rounded meter (SVG on the desktop, a text bar elsewhere).

| Row | Value |
|---|---|
| Context | this chat's context use against strata's handoff threshold |
| Cache | time left in the prompt cache, or the re-warm cost (from Cache Keeper) |
| Goal | checks verified or turns (from Goal Meter) |
| Canary | strata canary hits and misses |
| Memory | sessions waiting for extraction (`strata.py stats`) |
| Engine | shown while Haiku is paused after a quota or login error |
| Vault | whether the Obsidian vault exists, and chats logged today |

The status line carries the same in one line. `/strata-meter` reopens the panel; `MOAA_STRATA_METER=off` turns it off.
