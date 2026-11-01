export type CacheInfo = {
  /** When the main thread last sent a request (ms since epoch), 0 before the first. */
  lastCallAt: number
  /** Prompt tokens of that request: input + cache read + cache write. */
  tokens: number
  model: string
}

export type Warmth = {
  on: boolean
  /** When the person last sent a prompt; keep-warm stops after the idle cap. */
  lastPromptAt: number
  pings: number
  usd: number
}

declare module 'claude-code' {
  interface PluginState {
    'cache-keeper': { info: CacheInfo; warmth: Warmth; tick: number; isHidden: boolean }
  }
}
