---
name: wiki
description: Build and maintain a Karpathy-style LLM Wiki - compile papers, notes and project sources once into linked Markdown pages (index, log, schema) that Claude writes and keeps current, answer from the pages instead of re-reading raw sources, and lint the link graph. Use when the user wants a knowledge base, a literature wiki, project notes that compound, or invokes /strata:wiki.
argument-hint: "init [DIR] | ingest SOURCE | query QUESTION | lint"
---

# Strata wiki: an LLM-maintained knowledge base

Request: `$ARGUMENTS`. `G` means `python "${CLAUDE_PLUGIN_ROOT}/graph.py"` (`py` on Windows), run as one standalone
command. Default folder: `kb/` in the project, unless the user names one.

After Karpathy's LLM Wiki (April 2026): rather than retrieving from raw documents at every question, you compile each
source once into a wiki of linked pages. **You write and maintain the pages; the user curates sources and asks
questions.** The links between pages are the knowledge graph (open the folder in Obsidian to see it).

Layout (`G init DIR --title "..."` creates it): `raw/` (sources, never edited), `wiki/` (pages), `index.md` (catalog,
read first), `log.md` (append-only), `CLAUDE.md` (the schema; refine it with the user), `graph/` (typed claims, see
`/strata:graph`).

## Ingest: one source at a time
1. The source goes in `raw/` (copy it there, or save a web page as Markdown). Read it fully.
2. Create or revise every page it touches: one page per entity, concept, method, result or comparison. Each page
   starts with a one-line summary, links related pages as `[[Page Name]]` (file `wiki/Page Name.md`), and ends with
   its sources as `raw/...` paths. Update existing pages instead of duplicating; a real source often touches 5-15.
   Where it disagrees with what a page says, keep both views with their sources and flag the conflict.
3. Add new pages to `index.md` under a category, one line each.
4. Record its key claims in the findings graph (`G node` / `G edge ... supports`, see `/strata:graph`).
5. `G log DIR "ingest: <source> -> <pages touched>"`.

## Query
Read `index.md`, then only the pages it points to; answer with page names and `raw/` sources. Never answer from
memory when the wiki has a page on it. If the answer is useful beyond this question, file it as a new page, link it,
index it and log the query.

## Lint: after every few ingests and before relying on the wiki
- `G lint DIR`: broken links, orphan pages, pages missing from the index, raw sources no page cites, hub pages.
- `G check DIR`: claims without a grounded source, and contradictions.
Fix them, note stale claims (with the date checked), add missing cross-links between related pages, then log the pass.
Report what changed in a few lines.

## Notes
- Strata's automatic memory (profile, scenes, notes) stays separate: it remembers how you work; the wiki holds what you
  know about a subject.
- Git the folder for history. Keep secrets and private data out of `raw/` unless the folder stays private.
