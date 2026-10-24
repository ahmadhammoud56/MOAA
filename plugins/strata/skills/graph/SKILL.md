---
name: graph
description: Record findings as a typed graph (claims, sources, decisions, with supports, cites, contradicts and depends_on edges) that parallel agents share, and verify with a deterministic grounding check that every claim traces to a source. Use for multi-agent research, deliverables whose claims must be traceable, or /strata:graph. For a linked knowledge base of pages, use /strata:wiki.
argument-hint: "add | check | export [DIR]"
---

# Strata graph: findings with their sources

Request: `$ARGUMENTS`. `G` means `python "${CLAUDE_PLUGIN_ROOT}/graph.py"` (`py` on Windows), run as one standalone
command. Default folder: `kb/` (shared with `/strata:wiki`; `G init DIR` creates it).

"Graph engineering": once several agents work in parallel, findings must live in shared, typed state instead of
transcripts, and a script, not a model's impression, decides what is grounded. Each agent stays a loop; the graph is
the wiring and the evidence between them.

## Record
- Source: `G node DIR s-<slug> source "<title>" --ref <path or URL>` (a ref is required for grounding).
- Claim: `G node DIR c-<slug> claim "<one checkable statement>"`, then `G edge DIR c-<slug> supports s-<slug>`.
- Other types: `entity`, `decision`, `task`. Other edges: `cites`, `contradicts` (never overwrite a disagreeing claim;
  link it), `depends_on`, `derived_from`, `about`.
- Writing a node again with the same id replaces it (latest line wins). Each command appends one line, so parallel
  writers do not clash.

## Verify
`G check DIR` prints grounded/all claims (the score to drive to 1.0) and one specific failure per problem: a claim
with no source edge, a source with no ref, an edge to a missing node. It lists contradictions for a human or the
council to settle. Exit code 1 while anything fails, so it can gate a loop or a review.

## Use with agents
Put the folder path and the two record commands in each worker's brief (council workers, War Room workers, allies).
Before integrating results run `G check DIR`; send ungrounded claims back, or to the council's claim-table evidence
review, instead of accepting them. `G export DIR` writes `wiki/graph.md`, a Mermaid diagram of the graph.
