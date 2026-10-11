export const showcaseText = (themes: readonly string[]): string => `
# prismantis

Colored markdown for Claude Code replies: **bold**, *italic*, ~~struck~~, \`inline code\`, a [link](https://github.com/NahumLitvin/prismantis) and a bare URL https://github.com/NahumLitvin/prismantis/issues, both clickable, numbers like 99.9% and 250ms, paths like ~/src/app.ts.

## Commands

| Command | Does |
|---------|------|
| \`/prismantis\` | This screen |
| \`/prismantis theme <name>\` | Switch theme on the spot |
| \`/prismantis copy\` | Copy the last reply, or \`copy code\` for its last code block |
| \`/config\` | Edit any option |

> [!NOTE]
> ${themes.length} themes ship with it. \`mono\` uses no color, only bold and dim.

### Pick a theme

\`\`\`bash
/prismantis theme nord
/prismantis theme github-light
\`\`\`

1. Dark: ${themes.filter(t => !/latte|light|dawn/.test(t) && t !== 'mono').join(', ')}
2. Light: ${themes.filter(t => /latte|light|dawn/.test(t)).join(', ')}
3. Plain
   - mono

> [!TIP]
> Any color slot beats the theme. Set \`headingColor\` or \`numberColor\` to a hex value in \`/config\`.

## Everything it draws

### Alerts

> [!IMPORTANT]
> After updating the plugin, open sessions need \`/reload\`.

> [!WARNING]
> Terminals that copy on select (Warp) can turn a click on a copy button into a selection. Use the keyboard shortcut.

> [!CAUTION]
> Claude Code refuses trees over 20000 nodes. A code block past about 500 highlighted lines falls back to plain text.

### Task lists

- [x] Parse the reply
- [x] Draw it
  - [x] Tables and code
  - [ ] Diagrams on the desktop app
- [ ] Ship the next release

### Your prompts

Scroll up: what you typed draws in a bubble. \`promptStyle\` switches to \`bar\`, \`chevron\` or \`off\` in \`/config\`.

### Tool rows

Tool calls draw as one line, dimmed on the right by default. Set \`toolStyle\` in \`/config\` to \`chat\`, \`tree-dim\`, \`tree-bold\` or \`classic\`.

### Quotes and rules

> A quote keeps its text when you copy it, without the \`> \` markers.

---

### Code

\`\`\`json
{ "theme": "dracula", "headingStyle": "banner", "mermaid": true }
\`\`\`

#### Diagrams

\`\`\`mermaid
flowchart LR
    R[Reply] --> P[Parse]
    P --> D[Draw]
    D --> S[Screen]
\`\`\`

\`\`\`mermaid
sequenceDiagram
    participant U as You
    participant C as Claude
    participant P as prismantis
    U->>C: prompt
    C->>P: markdown
    P-->>U: colored reply
\`\`\`

\`\`\`mermaid
xychart-beta
    title "Color options per group"
    x-axis [text, head, num, code, diag]
    y-axis "options" 0 --> 8
    bar [7, 3, 2, 6, 2]
\`\`\`
`

export const helpText = (themes: readonly string[]): string => `
## Commands

| Command | Does |
|---------|------|
| \`/prismantis theme <name>\` | Switch theme on the spot |
| \`/prismantis copy\` | Copy the last reply, or \`copy code\` for its last code block |
| \`/prismantis demo\` | Full showcase, every element and diagram |
| \`/prismantis demo-rtl\` | Hebrew right-to-left showcase |

### ${themes.length} themes

- Dark: ${themes.filter(t => !/latte|light|dawn/.test(t) && t !== 'mono').join(', ')}
- Light: ${themes.filter(t => /latte|light|dawn/.test(t)).join(', ')}
- Plain: mono, no color, only bold and dim

Docs and issues: https://github.com/NahumLitvin/prismantis

> [!TIP]
> Any color slot beats the theme. Set \`headingColor\` or \`numberColor\` to a hex value in \`/config\`.

### Task lists

- [x] Tables, diagrams and charts drawn in the terminal
- [x] A copy button on every block
- [ ] Pick a \`taskStyle\` in \`/config\`: checks, ticks, box or progress

\`\`\`mermaid
flowchart LR
    R[Reply] --> P[Parse]
    P --> D[Draw]
    D --> S[Screen]
\`\`\`

\`\`\`mermaid
xychart-beta
    title "Color options per group"
    x-axis [text, head, num, code, diag]
    y-axis "options" 0 --> 8
    bar [7, 3, 2, 6, 2]
\`\`\`

> [!CAUTION]
> Claude Code refuses trees over 20000 nodes. A code block past about 500 highlighted lines falls back to plain text.
`

export const rtlShowcaseText = (): string => `
# עברית מימין לשמאל

**שלום חברים**, זו הדגמה של עברית עם מונחים באנגלית כמו \`kubectl\`, מספרים כמו 99.9% ו-250ms, נתיב כמו ~/src/app.ts וגם [קישור](https://github.com/NahumLitvin/prismantis).

## רשימות

- פרוסים בשני אזורים (us-east ו-eu-west)
- מחליפים ערכת נושא עם \`/prismantis theme nord\`

1. מתקינים את התוסף
2. שואלים שאלה בעברית

> עברית נקראת מימין לשמאל, גם בטרמינל בלי תמיכה בכיווניות

> [!TIP]
> כל ערכת נושא עובדת גם בעברית

| שירות | אזור | גרסה |
| :--- | :--- | ---: |
| שער | us-east | 2.14.0 |
| חיוב | eu-west | 1.8.3 |

\`\`\`bash
ls -la # רשימת הקבצים בתיקייה
\`\`\`
`
