export type Reading = {
  /** Context use of this chat, percent. */
  pct: number
  threshold: number
  handoffOn: boolean
  canaryHits: number
  canaryMisses: number
  /** Sessions waiting for extraction, from `strata.py stats`; -1 when unknown. */
  pending: number
  atoms: number
  /** Minutes left in the engine pause after a quota or login error; 0 when none. */
  pausedMin: number
  fallback: string
  vault: string
  vaultOk: boolean
  /** Lines in today's daily note. */
  today: number
  /** Cache Keeper's snapshot for this chat, or null. */
  cache: { leftMs: number; ttlMs: number; tokens: number; rewarm: number; keepWarm: boolean } | null
  /** Goal Meter's snapshot for this chat, or null. */
  goal: { text: string; turns: number; limit: number; done: number; total: number; label: string } | null
}

declare module 'claude-code' {
  interface PluginState {
    'strata-meter': { reading: Reading | null }
  }
}
