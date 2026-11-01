export type Tick = number

declare module 'claude-code' {
  interface PluginState {
    'collision-guard': { tick: Tick }
  }
}
