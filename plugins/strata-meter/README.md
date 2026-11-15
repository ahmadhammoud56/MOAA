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

| Chats | live chats on this machine (from Collision Guard) |

**Where it shows (0.2.0):** by default a one-row band above the prompt (context, canary, memory queue, open chats),
next to Cache Keeper's and Goal Meter's bands, and no panel at start. The desktop app gives every mod panel its own
column beside the background-tasks column, so a band keeps the window to one side column. `/strata-meter` opens the
full Meters panel at any time. `MOAA_METERS=pane` opens the panel at start with no band (the 0.1.0 behaviour), and
`MOAA_METERS=both` shows both.

The status line carries the same in one line. `MOAA_STRATA_METER=off` turns it all off.
