import { build } from 'esbuild'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

export const ROOT = fileURLToPath(new URL('..', import.meta.url))

export const load = async () => {
  const out = join(mkdtempSync(join(tmpdir(), 'prismantis-')), 'bundle.js')
  await build({
    stdin: {
      contents: [
        "export { parse } from './hooks/markdown.ts'",
        "export { renderBlocks } from './hooks/render.tsx'",
        "export { mermaidText, boxArt } from './hooks/mermaid.tsx'",
        "export { resolveStyle } from './hooks/theme.ts'",
      ].join('\n'),
      resolveDir: ROOT,
      loader: 'ts',
    },
    bundle: true,
    format: 'esm',
    platform: 'node',
    jsx: 'transform',
    jsxFactory: 'h',
    jsxFragment: 'Fragment',
    outfile: out,
    logLevel: 'error',
  })
  globalThis.h = (type, props, ...children) => ({ type, props, children })
  globalThis.Fragment = 'Fragment'
  const lib = await import(pathToFileURL(out).href)
  const el = { Box: 'Box', Text: 'Text', Button: 'Button', Link: 'Link' }
  const reply = (text, style, columns = 200) => {
    const blocks = lib.parse(text, { numbers: style.highlightNumbers, paths: style.highlightPaths })
    const drawn = new Map()
    for (const [i, block] of blocks.entries()) {
      if (block.kind !== 'code' || block.lang !== 'mermaid') continue
      const art = lib.mermaidText(block.lines.join('\n'), style.mermaidAscii, columns)
      if (art !== null) drawn.set(i, { element: lib.boxArt(el, style, art, `b${i}`), art })
    }
    return lib.renderBlocks(el, style, blocks, columns, drawn, () => null)
  }
  return { ...lib, el, reply }
}
