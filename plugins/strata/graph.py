#!/usr/bin/env python3
"""Strata graph: a Karpathy-style LLM Wiki and a typed findings graph, with deterministic checks.

Wiki (pages are nodes, [[links]] are edges; the LLM writes the pages, these commands keep it honest):
  python graph.py init DIR [--title T]     raw/, wiki/, index.md, log.md, CLAUDE.md (schema), graph/
  python graph.py log DIR TEXT             append a dated line to log.md (ingest, query, lint)
  python graph.py lint DIR [--json]        broken links, orphan pages, pages missing from index.md, hubs,
                                           raw sources no page cites; exit 1 on broken links. `[[Page]]` resolves
                                           by file name anywhere under wiki/ (Obsidian); a DIR without wiki/
                                           holds the pages itself (a vault's wiki/ folder)

Second-brain vault (its path comes from strata: STRATA_VAULT or `strata.py vault`):
  python graph.py capture TEXT [--project P]   append `- HH:MM [project] TEXT` to <vault>/inbox/<date>.md
  python graph.py archive VAULT [FILES...]     move distilled inbox files (default all) to inbox/archive/

Findings graph (graph engineering: agents record claims with their sources instead of transcripts):
  python graph.py node DIR ID TYPE TEXT [--ref URL_OR_PATH]   TYPE: claim, source, entity, decision, task
  python graph.py edge DIR SRC REL DST                         REL: supports, cites, contradicts, depends_on,
                                                               derived_from, about
  python graph.py check DIR [--json]       grounding evaluator: every claim needs a supports/cites edge to a
                                           source with a ref; dangling edges, contradictions; exit 1 on failures
  python graph.py export DIR               wiki/graph.md with a Mermaid diagram of the findings graph

Several agents may append nodes and edges at once (one line each, append-only JSONL; the latest line per id wins).
Standard library only.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time

NODE_TYPES = ("claim", "source", "entity", "decision", "task")
EDGE_TYPES = ("supports", "cites", "contradicts", "depends_on", "derived_from", "about")
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MDLINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")
RAWREF = re.compile(r"(raw/[^\s)\]>\"'`]+)")

SCHEMA = """# {title}: wiki schema

This folder is an LLM-maintained knowledge base (after Karpathy's LLM Wiki). Claude writes and maintains the pages;
the user curates sources and asks questions.

- `raw/`: original sources. Never edit or delete them. Cite them by path (`raw/...`) in pages.
- `wiki/`: one Markdown page per entity, concept, method, result or comparison. Link related pages with
  `[[Page Name]]` (the file is `wiki/Page Name.md`). Every page starts with a one-line summary and ends with its
  sources.
- `index.md`: catalog of every page by category, one line each. Read it first when answering a question.
- `log.md`: append-only log of ingests, queries and lint passes (`graph.py log`).
- `graph/`: typed findings (claims, sources, decisions) written with `graph.py node` / `edge`; `graph.py check`
  verifies every claim is grounded in a source.

## Operations
- **Ingest** one source at a time: put it in `raw/`, summarize it, create or revise the affected pages (often
  several), add them to `index.md`, record key claims in `graph/` with `supports` edges to the source, then log it.
- **Query:** read `index.md`, then the relevant pages; answer with page and source citations. File a good answer back
  as a page.
- **Lint:** run `graph.py lint` and `graph.py check`; fix broken links, orphans, pages missing from the index,
  ungrounded claims and contradictions; note stale claims. Log the pass.
"""


def page_name(p, wiki):
    return p.relative_to(wiki).with_suffix("").as_posix()


def init(root, title):
    for d in ("raw", "wiki", "graph"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for name, text in (("CLAUDE.md", SCHEMA.format(title=title)),
                       ("index.md", f"# {title}: index\n\nOne line per page, grouped by category.\n"),
                       ("log.md", f"# {title}: log\n\n")):
        if not (root / name).exists():
            (root / name).write_text(text, encoding="utf-8")
    log(root, f"init: {title}")


def log(root, text):
    with (root / "log.md").open("a", encoding="utf-8") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {text}\n")


def lint(root):
    """Link graph of the wiki: {pages, links, broken, orphans, not_in_index, hubs, uncited_raw}. Pages live in
    root/wiki/, or in root itself when it has no wiki/ folder (a vault's wiki/ with its own index.md and log.md).
    `[[Page]]` resolves by path or, as in Obsidian, by file name anywhere under the pages folder."""
    wiki = root / "wiki" if (root / "wiki").is_dir() else root
    pages = {page_name(p, wiki): p for p in sorted(wiki.rglob("*.md")) if wiki != root or
             p.relative_to(root).as_posix() not in ("index.md", "log.md", "CLAUDE.md")}
    lower = {k.lower(): k for k in pages}
    for k in sorted(pages, key=lambda k: (k.count("/"), k)):  # Obsidian: the shortest path wins a name clash
        lower.setdefault(k.rsplit("/", 1)[-1].lower(), k)
    inbound = {k: 0 for k in pages}
    broken, cited, edges = [], set(), 0
    sources = [(name, p.read_text(encoding="utf-8", errors="replace")) for name, p in pages.items()]
    index_text = (root / "index.md").read_text(encoding="utf-8", errors="replace") if (root / "index.md").exists() else ""
    for name, text in sources + [("index.md", index_text)]:
        cited.update(RAWREF.findall(text))
        targets = [t.strip() for t in WIKILINK.findall(text)]
        targets += [Path(m).with_suffix("").as_posix().removeprefix("wiki/") for m in MDLINK.findall(text)]
        for t in targets:
            hit = lower.get(t.lower())
            if hit is None:
                broken.append({"from": name, "to": t})
            else:
                edges += 1
                if name != "index.md" and hit != name:
                    inbound[hit] += 1
    in_index = {lower[t.strip().lower()] for t in WIKILINK.findall(index_text) if t.strip().lower() in lower}
    in_index |= {k for k in pages if f"{k}.md" in index_text}
    raw = sorted(p.relative_to(root).as_posix() for p in (root / "raw").rglob("*") if p.is_file()) \
        if (root / "raw").is_dir() else []
    return {"pages": len(pages), "links": edges, "broken": broken,
            "orphans": sorted(k for k, n in inbound.items() if n == 0),
            "not_in_index": sorted(set(pages) - in_index),
            "hubs": sorted(((n, k) for k, n in inbound.items() if n), reverse=True)[:5],
            "uncited_raw": [r for r in raw if not any(r == c or r.startswith(c.rstrip("/")) for c in cited)]}


def archive(vault, files=()):
    """Move distilled inbox files (default: all of inbox/*.md) to inbox/archive/, appending to a file of the same
    name there. Returns the archived paths."""
    inbox = vault / "inbox"
    todo = [vault / f if not Path(f).is_absolute() else Path(f) for f in files] or sorted(inbox.glob("*.md"))
    (inbox / "archive").mkdir(parents=True, exist_ok=True)
    out = []
    for f in todo:
        if f.parent.resolve() != inbox.resolve() or not f.is_file():
            continue  # only inbox files, never anything else
        dest = inbox / "archive" / f.name
        with dest.open("a", encoding="utf-8") as d:
            d.write(f.read_text(encoding="utf-8"))
        f.unlink()
        out.append(dest.relative_to(vault).as_posix())
    return out


def load(root):
    nodes, edges = {}, []
    for line in (root / "graph" / "nodes.jsonl").read_text(encoding="utf-8").splitlines() \
            if (root / "graph" / "nodes.jsonl").exists() else []:
        if line.strip():
            n = json.loads(line)
            nodes[n["id"]] = n
    for line in (root / "graph" / "edges.jsonl").read_text(encoding="utf-8").splitlines() \
            if (root / "graph" / "edges.jsonl").exists() else []:
        if line.strip():
            edges.append(json.loads(line))
    return nodes, edges


def append(root, name, record):
    (root / "graph").mkdir(parents=True, exist_ok=True)
    with (root / "graph" / name).open("a", encoding="utf-8") as f:  # one write per record: safe for parallel agents
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def check(root):
    """Grounding evaluator: {claims, grounded, score, failures, contradictions}. Failures are specific."""
    nodes, edges = load(root)
    failures, contradictions = [], []
    for e in edges:
        for end in ("src", "dst"):
            if e[end] not in nodes:
                failures.append(f"edge {e['src']} -{e['rel']}-> {e['dst']}: no node {e[end]}")
        if e["rel"] == "contradicts":
            contradictions.append(f"{e['src']} contradicts {e['dst']}")
    claims = [n for n in nodes.values() if n["type"] == "claim"]
    grounded = 0
    for c in claims:
        support = [nodes.get(e["dst"]) for e in edges if e["src"] == c["id"] and e["rel"] in ("supports", "cites")]
        support += [nodes.get(e["src"]) for e in edges if e["dst"] == c["id"] and e["rel"] == "supports"]
        sources = [s for s in support if s and s["type"] == "source"]
        if not sources:
            failures.append(f"claim {c['id']}: no supports/cites edge to a source")
        elif not any(s.get("ref") for s in sources):
            failures.append(f"claim {c['id']}: its sources have no ref (URL or path)")
        else:
            grounded += 1
    return {"claims": len(claims), "grounded": grounded,
            "score": round(grounded / len(claims), 3) if claims else 1.0,
            "failures": failures, "contradictions": contradictions}


def export(root):
    nodes, edges = load(root)
    safe = lambda s: re.sub(r"[^A-Za-z0-9_]", "_", s)  # noqa: E731
    lines = ["# Findings graph", "", "Generated by `graph.py export`; edit the graph, not this page.", "", "```mermaid",
             "graph LR"]
    for n in nodes.values():
        label = (n["text"][:60] + ("..." if len(n["text"]) > 60 else "")).replace('"', "'")
        lines.append(f'  {safe(n["id"])}["{n["type"]}: {label}"]')
    for e in edges:
        lines.append(f"  {safe(e['src'])} -->|{e['rel']}| {safe(e['dst'])}")
    lines.append("```")
    out = root / "wiki" / "graph.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("init"); a.add_argument("dir"); a.add_argument("--title", default="Knowledge base")
    a = sub.add_parser("log"); a.add_argument("dir"); a.add_argument("text", nargs="+")
    for name in ("lint", "check"):
        a = sub.add_parser(name); a.add_argument("dir"); a.add_argument("--json", action="store_true")
    a = sub.add_parser("node"); a.add_argument("dir"); a.add_argument("id"); a.add_argument("type", choices=NODE_TYPES)
    a.add_argument("text"); a.add_argument("--ref", default="")
    a = sub.add_parser("edge"); a.add_argument("dir"); a.add_argument("src"); a.add_argument("rel", choices=EDGE_TYPES)
    a.add_argument("dst")
    a = sub.add_parser("export"); a.add_argument("dir")
    a = sub.add_parser("capture"); a.add_argument("text", nargs="+"); a.add_argument("--project")
    a = sub.add_parser("archive"); a.add_argument("dir"); a.add_argument("files", nargs="*")
    args = p.parse_args(argv)
    if args.cmd == "capture":  # the vault lives in strata's settings
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import strata
        print(f"captured in {strata.capture(' '.join(args.text), args.project)}")
        return 0
    root = Path(args.dir)
    if args.cmd == "archive":
        print("\n".join(archive(root, args.files)) or "nothing to archive")
        return 0
    if args.cmd == "init":
        init(root, args.title)
        print(f"initialized {root.resolve().as_posix()}: raw/, wiki/, graph/, index.md, log.md, CLAUDE.md")
    elif args.cmd == "log":
        log(root, " ".join(args.text))
    elif args.cmd == "node":
        append(root, "nodes.jsonl", {"id": args.id, "type": args.type, "text": args.text, "ref": args.ref,
                                     "by": os.environ.get("WARROOM_AGENT", ""), "ts": time.time()})
    elif args.cmd == "edge":
        append(root, "edges.jsonl", {"src": args.src, "rel": args.rel, "dst": args.dst, "ts": time.time()})
    elif args.cmd == "export":
        print(export(root).as_posix())
    elif args.cmd == "lint":
        r = lint(root)
        if args.json:
            print(json.dumps(r, indent=2))
        else:
            print(f"{r['pages']} pages, {r['links']} links")
            for key in ("broken", "orphans", "not_in_index", "uncited_raw"):
                if r[key]:
                    print(f"{key} ({len(r[key])}): " + ", ".join(
                        f"{b['from']} -> {b['to']}" if isinstance(b, dict) else str(b) for b in r[key][:20]))
            if r["hubs"]:
                print("hubs: " + ", ".join(f"{k} ({n})" for n, k in r["hubs"]))
        return 1 if r["broken"] else 0
    elif args.cmd == "check":
        r = check(root)
        if args.json:
            print(json.dumps(r, indent=2))
        else:
            print(f"grounded {r['grounded']}/{r['claims']} claims (score {r['score']})")
            for f in r["failures"]:
                print("FAIL " + f)
            for c in r["contradictions"]:
                print("CONTRADICTION " + c)
        return 1 if r["failures"] else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
