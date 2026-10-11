import { expect, test } from 'claude-code/testing'

import { PRESETS } from '../hooks/presets'

const BACKGROUNDS: Record<string, string> = {
  'catppuccin-mocha': '#1e1e2e',
  'catppuccin-latte': '#eff1f5',
  dracula: '#282a36',
  nord: '#2e3440',
  'tokyo-night': '#1a1b26',
  'gruvbox-dark': '#282828',
  'gruvbox-light': '#fbf1c7',
  'rose-pine': '#191724',
  'rose-pine-dawn': '#faf4ed',
  everforest: '#2d353b',
  'github-dark': '#0d1117',
  'github-light': '#ffffff',
  'one-dark': '#282c34',
  'solarized-dark': '#002b36',
  'solarized-light': '#fdf6e3',
}

const luminance = (hex: string) => {
  const channel = (i: number) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)
}

const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}

const FLOOR: Record<string, number> = { rule: 1.05, tableRule: 1.05, codeComment: 1.5, quote: 1.5 }

test('every preset stays readable on its own background', async () => {
  const failures: string[] = []
  for (const [name, theme] of Object.entries(PRESETS)) {
    if (name === 'mono') continue
    const bg = BACKGROUNDS[name]
    if (!bg) throw new Error(`no background for ${name}`)
    for (const [token, color] of Object.entries(theme)) {
      const ratio = contrast(color as string, bg)
      if (ratio < (FLOOR[token] ?? 2)) failures.push(`${name}.${token} ${ratio.toFixed(2)}`)
    }
  }
  expect(failures).toEqual([])
})
