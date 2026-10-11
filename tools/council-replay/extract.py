#!/usr/bin/env python3
"""Turn a Specialist Council session transcript into a compact replay JSON.

Usage: python extract.py <session.jsonl> [-o replay.json]

Reads the main session jsonl plus <session>/subagents/agent-*.jsonl and *.meta.json.
Absolute user paths, e-mail addresses and secret-looking strings are redacted.
Standard library only.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

REDACT = [
    (re.compile(r"(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"'<>]+"), "~"),
    (re.compile(r"/(?:home|Users)/[^/\s\"'<>]+"), "~"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "[redacted]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"), "[redacted]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[redacted]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "[redacted]"),
    (re.compile(r"(?i)\b(api[_-]?key|secret|token|password)(\s*[:=]\s*)\S+"), r"\1\2[redacted]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
]


def redact(text):
    for pattern, repl in REDACT:
        text = pattern.sub(repl, text)
    return text


def ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() if value else None


def load(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def blocks(row):
    content = (row.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content if isinstance(content, list) else []


def texts(row):
    return [b["text"] for b in blocks(row) if b.get("type") == "text"]


def result_text(block):
    content = block.get("content")
    if isinstance(content, list):
        content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return content or ""


def plain(text):
    return re.sub(r"\*\*|`", "", text).strip()


def headline(result, limit=110):
    """First prose lines of a worker result, skipping section headers, until the first list item."""
    out = []
    for line in result.splitlines():
        line = plain(line)
        if not line or line.endswith(":"):
            continue
        if re.match(r"^([-*]|\d+\.)\s", line):
            if out:
                break
            continue
        out.append(line)
        if len(" ".join(out)) >= limit:
            break
    joined = " ".join(out)
    return joined if len(joined) <= limit else joined[: limit - 1].rstrip() + "…"


def checks(result):
    """Bold labels of numbered items, e.g. '1. **Multiplication:** ...' -> 'Multiplication'."""
    found = re.findall(r"(?m)^\s*\d+\.\s+\*\*(.+?)\*\*", result)
    return [plain(c).rstrip(".:") for c in found][:5]


def subagents(session_path):
    folder = session_path.with_suffix("") / "subagents"
    found = {}
    for meta_path in sorted(folder.glob("agent-*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        rows = load(meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl")))
        replies = [r for r in rows if r.get("type") == "assistant"]
        models = [r["message"].get("model") for r in replies if r["message"].get("model")]
        final = next((t for r in reversed(replies) for t in reversed(texts(r))), "")
        found[meta.get("toolUseId")] = {
            "meta": meta,
            "start": ts(rows[0].get("timestamp")) if rows else None,
            "end": ts(replies[-1].get("timestamp")) if replies else None,
            "model": models[-1] if models else None,
            "result": final,
        }
    return found


def extract(session_path):
    session_path = Path(session_path)
    rows = load(session_path)
    t0 = None
    task = ""
    for row in rows:
        if row.get("type") == "user" and not task:
            for text in texts(row):
                args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
                if args or not text.startswith("<"):
                    task = (args.group(1) if args else text).strip()
                    t0 = ts(row.get("timestamp"))
                    break

    def rel(value):
        return round(value - t0, 2) if value is not None and t0 is not None else None

    uses, results, coordinator = {}, {}, None
    for row in rows:
        for b in blocks(row):
            if b.get("type") == "tool_use":
                uses[b["id"]] = (b, ts(row.get("timestamp")))
            elif b.get("type") == "tool_result":
                results[b.get("tool_use_id")] = (b, ts(row.get("timestamp")))
        if row.get("type") == "assistant" and row["message"].get("model") not in (None, "<synthetic>"):
            coordinator = row["message"]["model"]

    resolves, agents = [], []
    subs = subagents(session_path)
    for use_id, (use, when) in uses.items():
        command = use.get("input", {}).get("command", "")
        if use["name"] in ("Bash", "PowerShell") and re.search(r"council\.py\"?\s+resolve", command):
            role = re.search(r"--role\s+(\S+)", command)
            res, res_when = results.get(use_id, ({}, None))
            output = result_text(res)
            try:
                data = json.loads(output)
            except ValueError:
                data = {}
            resolves.append({
                "role": role.group(1).strip("\"'") if role else "?",
                "agent": data.get("agent") or (f"specialist-council:council-{data['role']}" if data.get("role") else None),
                "model": data.get("model"),
                "effort": data.get("effort"),
                "tier": data.get("tier") or ("forged" if data.get("forged") else None),
                "ok": bool(data) and not res.get("is_error"),
                "note": "" if data else redact(output.strip())[:80],
                "t": rel(res_when or when),
            })
        elif use["name"] in ("Agent", "Task"):
            inp = use.get("input", {})
            sub = subs.get(use_id, {})
            agents.append({
                "type": inp.get("subagent_type", "general-purpose"),
                "description": redact(inp.get("description", "")),
                "model": sub.get("model"),
                "effort": inp.get("effort") or sub.get("meta", {}).get("effort"),
                "start": rel(sub.get("start") or when),
                "end": rel(sub.get("end")),
                "result": redact(headline(sub.get("result", ""))),
                "checks": [redact(c) for c in checks(sub.get("result", ""))],
            })

    resolves.sort(key=lambda r: r["t"] or 0)
    agents.sort(key=lambda a: a["start"] or 0)
    for r in resolves:  # a failed resolve has no "agent" field; forged members are user agents
        prefix = "" if r["role"].startswith("forged-") else "specialist-council:"
        r["agent"] = r["agent"] or f"{prefix}council-{r['role']}"

    final_row = next((r for r in reversed(rows) if r.get("type") == "assistant" and texts(r)), None)
    final = "\n".join(texts(final_row)) if final_row else ""
    for a in agents:
        line = next((l for l in final.splitlines() if a["type"] in l and "Method:" in l), "")
        a["method"] = redact(plain(line.split("Method:", 1)[1]).rstrip(".")) if line else a["description"]

    all_text = "\n".join(t for r in rows if r.get("type") == "assistant" for t in texts(r))
    mode = re.search(r"(?i)\bmode:\s*([^)\n.]+)", all_text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", final) if p.strip()]
    answer = re.search(r"COUNCIL_RESULT:\s*(.+)", final)
    return {
        "version": 1,
        "task": redact(task),
        "coordinator": coordinator,
        "mode": plain(mode.group(1)) if mode else "ensemble",
        "resolves": resolves,
        "agents": agents,
        "verification": redact(plain(paragraphs[1])) if len(paragraphs) > 1 else "",
        "headline": redact(plain(paragraphs[0].splitlines()[0])) if paragraphs else "",
        "answer": redact(plain(answer.group(1))) if answer else "",
        "duration": rel(ts(final_row.get("timestamp"))) if final_row else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("session", help="main session .jsonl of a council run")
    parser.add_argument("-o", "--out", help="write here instead of stdout")
    args = parser.parse_args(argv)
    text = json.dumps(extract(args.session), indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
