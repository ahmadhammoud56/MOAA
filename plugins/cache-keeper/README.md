# Cache Keeper (mod)

A Claude Code mod that shows when this chat's prompt cache goes cold and what re-warming costs.

- **Status line** (every surface, Remote Control included): `cache warm 52:10 left · 412k tokens`, or when cold the
  cost of the next prompt, or a strata handoff suggestion when the context is past `MOAA_CACHE_HANDOFF_PCT` (60).
- **Band above the prompt** (terminal and desktop) with a **Keep warm** button; `/cache-keeper pane` opens a panel.
- **Keep warm**, per chat (`/cache-keeper on|off`): shortly before the cache lapses it sends `$.model.fork`, which
  re-sends this chat's own cached prefix, so the API reads and refreshes it. Pings and their estimated cost are
  counted; it stops after `MOAA_CACHE_IDLE_CAP_MIN` (30) minutes without a prompt.
- The cost is an estimate from a price table (`MOAA_CACHE_PRICE="write,read"` per million tokens overrides it).
- Cache window: `MOAA_CACHE_TTL_MIN`, 60 by default (Claude Code on a subscription); set 5 with an API key.
- Off: `MOAA_CACHE_KEEPER=off`; `/cache-keeper hide|show` for the status line.

Readings also go to `~/.claude/moaa-mods/meters/<session>.cache.json` for the strata Meters panel.
