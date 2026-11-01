export type Goal = {
  text: string
  /** Turns since the goal was set. */
  turns: number
  /** "Stop after N turns" in the goal text, else 0. */
  limit: number
}

export type Progress = { done: number; total: number; label: string }

declare module 'claude-code' {
  interface PluginState {
    'goal-meter': { goal: Goal | null; progress: Progress | null }
  }
}
