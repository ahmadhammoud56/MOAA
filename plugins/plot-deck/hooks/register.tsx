import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { PlotFile } from '../types'

const PANE = 'plot-deck'
const LATEST = 12
const IMAGE = /\.(?:png|jpe?g)$/i
const MENTION = /(?:[A-Za-z]:)?[\\/]?[^\s"'<>|*?`,;()[\]{}]+\.(?:png|jpe?g)/gi
const SUBDIRS = ['figures', 'plots', 'output', 'out', 'results']

const page = atom({ plugin: 'plot-deck', key: 'page' } as const, 'plot' as 'plot' | 'pick')
const selected = atom({ plugin: 'plot-deck', key: 'selected' } as const, null as string | null)
const tracked = atom({ plugin: 'plot-deck', key: 'tracked' } as const, [] as string[])
const folder = atom({ plugin: 'plot-deck', key: 'folder' } as const, null as string | null)

const isAbsolute = (path: string): boolean => /^[A-Za-z]:[\\/]/.test(path) || path.startsWith('/') || path.startsWith('\\\\')
const join = (dir: string, name: string): string => `${dir.replace(/[\\/]$/, '')}/${name}`
const mentioned = (text: string, root: string): string[] =>
  [...text.replace(/\\\\/g, '\\').matchAll(MENTION)].map(m => (isAbsolute(m[0]) ? m[0] : join(root, m[0].replace(/^\.[\\/]/, ''))))

const stat = async ($: EngineInterface, path: string): Promise<PlotFile | undefined> => {
  const s = await $.fs.stat(path).catch(() => undefined)
  return s && s.kind === 'file' ? { path, name: path.split(/[\\/]/).pop() ?? path, mtimeMs: s.mtimeMs } : undefined
}

const gather = async ($: EngineInterface, dirsOption: string, extra: string[], pinned: string | null): Promise<PlotFile[]> => {
  const root = await $.session.root()
  if (pinned) {
    const entries = await $.fs.list(pinned).catch(() => [])
    const fromFolder = entries
      .filter(entry => entry.kind === 'file' && IMAGE.test(entry.name))
      .map(entry => ({ path: join(pinned, entry.name), name: entry.name, mtimeMs: entry.mtimeMs }))
      .sort((a, b) => a.name.localeCompare(b.name))
    const norm = (p: string): string => p.replace(/\\/g, '/').toLowerCase()
    const seen = new Set(fromFolder.map(f => norm(f.path)))
    const fresh: PlotFile[] = []
    for (const path of extra) {
      if (seen.has(norm(path))) continue
      const file = await stat($, path)
      if (file) {
        seen.add(norm(path))
        fresh.push(file)
      }
    }
    return [...fresh, ...fromFolder]
  }
  const dirs = dirsOption.trim()
    ? dirsOption.split(',').map(d => d.trim()).filter(Boolean)
    : [root, ...SUBDIRS.map(d => join(root, d))]
  const found = new Map<string, PlotFile>()
  for (const dir of dirs) {
    const entries = await $.fs.list(dir).catch(() => [])
    for (const entry of entries) {
      if (entry.kind === 'file' && IMAGE.test(entry.name)) {
        const path = join(dir, entry.name)
        found.set(path, { path, name: entry.name, mtimeMs: entry.mtimeMs })
      }
    }
  }
  for (const path of extra) {
    const file = found.has(path) ? undefined : await stat($, path)
    if (file) found.set(path, file)
  }
  return [...found.values()].sort((a, b) => b.mtimeMs - a.mtimeMs).slice(0, LATEST)
}

// Copy the plot to a temp folder, put the image on the clipboard, and open the copy in the default viewer.
const viewCopy = async ($: EngineInterface, path: string): Promise<void> => {
  const temp = ((await $.env.get('TEMP')) ?? 'C:/Windows/Temp').replace(/\\/g, '/')
  const dir = `${temp}/spop`
  const name = path.split(/[\\/]/).pop() ?? 'plot.png'
  const q = (p: string): string => `'${p.replace(/\//g, '\\').replace(/'/g, "''")}'`
  const script = `New-Item -ItemType Directory -Force ${q(dir)} | Out-Null; Copy-Item -LiteralPath ${q(path)} -Destination ${q(`${dir}/${name}`)} -Force; Add-Type -AssemblyName System.Windows.Forms, System.Drawing; $img = [System.Drawing.Image]::FromFile(${q(`${dir}/${name}`)}); [System.Windows.Forms.Clipboard]::SetImage($img); $img.Dispose(); Start-Process ${q(`${dir}/${name}`)}`
  await $.process.run(['powershell', '-NoProfile', '-STA', '-Command', script])
}

export const register: Register = (on, options) => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'plots',
      description: 'Open the plot pane: the latest Python plot, or `pick` to choose among the latest',
      argumentHint: '[pick | <image path> | <folder>]',
    })
    await $.command.register({
      name: 'spop',
      description: 'Same as /plots: open the spop side panel, or pass a folder to list all its plots',
      argumentHint: '[pick | <image path> | <folder>]',
    })
    void $.ui.open({ id: PANE, title: 'spop' })
    return next(e)
  })

  on('command.run', { command: /^(?:plots|spop)$/ }, async ($, e) => {
    const arg = String((e as { args?: string }).args ?? '').trim()
    if (arg && arg !== 'pick') {
      const root = await $.session.root()
      const path = isAbsolute(arg) ? arg : join(root, arg)
      const info = await $.fs.stat(path).catch(() => undefined)
      if (info?.kind === 'dir') {
        const count = (await $.fs.list(path).catch(() => [])).filter(f => f.kind === 'file' && IMAGE.test(f.name)).length
        if (!count) return { text: `No images in ${path}.` }
        await update($, folder, () => path)
        await update($, selected, () => null)
        await $.ui.open({ id: PANE, title: 'spop', focus: true })
        return { text: `Listed ${count} plots from ${path} in the Plots pane.` }
      }
      if (!(await stat($, path))) return { text: `No image at ${path}.` }
      await update($, tracked, list => [path, ...list.filter(p => p !== path)].slice(0, 50))
      await update($, selected, () => path)
    } else {
      await update($, selected, () => null)
      if (!arg) await update($, folder, () => null)
    }
    await update($, page, () => (arg === 'pick' ? 'pick' : 'plot'))
    await $.ui.open({ id: PANE, title: 'spop', focus: true })
    return { text: arg === 'pick' ? 'Plot picker opened.' : 'Plot pane opened.' }
  })

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    if (e.tool !== 'Bash' && e.tool !== 'PowerShell') return ran
    const root = await $.session.root()
    const command = String((e as { command?: string }).command ?? '')
    const output = 'result' in ran && ran.result ? JSON.stringify(ran.result) : ''
    const paths = [...new Set([...mentioned(command, root), ...mentioned(output, root)])]
    const real: string[] = []
    for (const path of paths) if (await stat($, path)) real.push(path)
    if (real.length) {
      await update($, tracked, list => [...real, ...list.filter(p => !real.includes(p))].slice(0, 50))
      void $.ui.invalidate('ui.render')
      $.ui.status(`plot: ${real[0]?.split(/[\\/]/).pop()} (/plots)`)
    }
    return ran
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e) as any
    const files = await gather($, String(options.plotDirs ?? ''), await read($, tracked), await read($, folder))
    if (!files.length) {
      return (
        <Box flexDirection="column">
          <Text bold>No plots yet</Text>
          <Text dimColor>Save one from Python (plt.savefig("plot.png")) or run /spop &lt;folder&gt;.</Text>
        </Box>
      )
    }

    return (
      <Box flexDirection="column">
        {files.map(f => (
          <Button
            key={`plot-${f.path}`}
            label={f.name}
            onPress={() => {
              void viewCopy($, f.path).catch(() => $.ui.toast('Could not open the image'))
            }}
          />
        ))}
      </Box>
    )
  })
}
