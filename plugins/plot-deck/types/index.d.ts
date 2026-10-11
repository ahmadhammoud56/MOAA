export type PlotFile = { path: string; name: string; mtimeMs: number }

declare module 'claude-code' {
  interface PluginState {
    'plot-deck': { page: 'plot' | 'pick'; selected: string | null; tracked: string[]; folder: string | null }
  }
}
