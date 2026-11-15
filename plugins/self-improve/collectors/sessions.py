#!/usr/bin/env python3
"""Compact facts from recent Claude Code sessions, for the self-improve loop.

Usage: python sessions.py [--days 7] [--root ~/.claude/projects]

Reads main session transcripts (not subagent files) changed in the last N days and prints
Markdown: per project, the session goals, recurring tool errors, permission denials,
interruptions, and instructions the user had to repeat. Each of those counts only when its own event
timestamp is inside the window, so long continued sessions do not bring old events along. Secrets, e-mails and home paths are
redacted before anything is printed. Read-only; standard library only.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time

HOME = str(Path.home())
REDACT = [(re.compile(re.escape(h), re.I), "~") for h in sorted(
    {HOME, HOME.replace("\\", "/"), HOME.replace("\\", "\\\\"), re.sub(r"[^A-Za-z0-9]", "-", HOME)}, key=len, reverse=True)] + [
    (re.compile(r"(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\n\"'<>]{1,40}?(?=[\\/])"), "~"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "[key]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"), "[key]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[key]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "[key]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{16,}"), "Bearer [key]"),
    (re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)(\s*[:=]\s*)\S+"), r"\1\2[redacted]"),
    (re.compile(r"\b[A-Za-z0-9_-]{40,}\b"), "[long-token]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
]
# Machine-generated sessions (memory observers, summarizers, probes) are not the user's own work.
SKIP_PROJECT = re.compile(r"[\\/]\.claude-mem[\\/]", re.I)
# Live e2e test runs (MOAA plugin tests, throwaway scratchpad folders) run under the temp folder.
TEST_PROJECT = re.compile(r"[\\/]AppData[\\/]Local[\\/]Temp([\\/]|$)|^/tmp(/|$)", re.I)
SKIP_PROMPT = re.compile(r"^(condense the tool payload|below is a conversation log from a claude code|reply with exactly)", re.I)
DENIED = re.compile(r"requires approval|permission for this action was denied|user (doesn't|does not) want|denied by", re.I)


def redact(text):
    for pattern, repl in REDACT:
        text = pattern.sub(repl, text)
    return text


def short(text, n=140):
    text = redact(" ".join(text.split()))
    return text if len(text) <= n else text[: n - 1] + "…"


def prompt_text(row):
    """The user's own words in a user row, or None for tool results, reminders and notifications."""
    content = (row.get("message") or {}).get("content")
    parts = [content] if isinstance(content, str) else [b.get("text", "") for b in content or [] if b.get("type") == "text"]
    for text in parts:
        args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
        name = re.search(r"<command-name>(.*?)</command-name>", text)
        if name:
            return f"{name.group(1)} {args.group(1) if args else ''}".strip()
        if text.startswith(("<", "Base directory for this skill", "Caveat:", "Another Claude session sent a message")) \
                or "[Request interrupted" in text:
            continue
        if text.strip():
            return text
    return None


def epoch(stamp):
    """Seconds since the epoch for an ISO timestamp like 2026-10-19T08:00:00.000Z, or None."""
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def session_facts(path, cutoff=None):
    """Facts from one transcript. With a cutoff (epoch seconds), errors, denials, interruptions and
    prompts count only when their own event timestamp is at or after it: a continued session that
    started before the window must not bring its old errors along. Rows without a timestamp count."""
    facts = {"prompts": [], "errors": [], "denials": Counter(), "interrupts": 0, "models": set(), "cwd": None,
             "start": None, "end": None}
    tools = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        facts["cwd"] = facts["cwd"] or row.get("cwd")
        stamp = row.get("timestamp")
        if stamp:
            facts["start"] = facts["start"] or stamp
            facts["end"] = stamp
        message = row.get("message") or {}
        if row.get("type") == "assistant":
            if message.get("model") and message["model"] != "<synthetic>":
                facts["models"].add(message["model"])
            for b in message.get("content") or []:
                if b.get("type") == "tool_use":
                    tools[b.get("id")] = b.get("name")
        elif row.get("type") == "user":
            when = epoch(stamp)
            if cutoff is not None and when is not None and when < cutoff:
                continue
            content = message.get("content")
            if isinstance(content, list):
                for b in content:
                    if b.get("type") != "tool_result":
                        continue
                    body = b.get("content")
                    body = body if isinstance(body, str) else " ".join(
                        c.get("text", "") for c in body or [] if isinstance(c, dict))
                    tool = tools.get(b.get("tool_use_id"), "?")
                    if DENIED.search(body):
                        facts["denials"][tool] += 1
                    elif b.get("is_error"):
                        facts["errors"].append(f"{tool}: {short(body, 110)}")
            text = json.dumps(content) if content else ""
            if "[Request interrupted by user" in text:
                facts["interrupts"] += 1
            prompt = prompt_text(row)
            if prompt:
                facts["prompts"].append(prompt)
    return facts


def project_of(cwd, path):
    where = redact(cwd) if cwd else path.parent.name
    return re.split(r"[\\/]\.claude[\\/]worktrees[\\/]", where)[0]  # worktrees belong to their repo


def norm(prompt):
    return re.sub(r"\W+", " ", prompt.lower()).strip()[:90]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--root", default=str(Path.home() / ".claude" / "projects"))
    parser.add_argument("--top", type=int, default=12, help="projects shown in full; the rest get one line")
    args = parser.parse_args(argv)
    cutoff = time.time() - args.days * 86400
    projects = defaultdict(list)
    tests = 0
    for path in Path(args.root).glob("*/*.jsonl"):
        if path.stat().st_mtime >= cutoff:
            facts = session_facts(path, cutoff)
            name = project_of(facts["cwd"], path)
            if facts["prompts"] and not SKIP_PROJECT.search(name) and not SKIP_PROMPT.search(facts["prompts"][0]):
                if TEST_PROJECT.search(name):
                    tests += 1
                else:
                    projects[name].append(facts)

    seen_in = defaultdict(set)  # normalized prompt -> sessions it appears in (repeated instructions)
    for name, sessions in projects.items():
        for i, s in enumerate(sessions):
            for p in s["prompts"]:
                if len(norm(p)) > 12:
                    seen_in[norm(p)].add((name, i))
    repeated = sorted(((len(v), k) for k, v in seen_in.items() if len(v) > 1), reverse=True)[:15]
    all_errors = Counter(re.sub(r"\d+", "#", e)[:90] for s in (x for v in projects.values() for x in v) for e in s["errors"])
    all_denials = Counter()
    for v in projects.values():
        for s in v:
            all_denials.update(s["denials"])

    out = sys.stdout
    out.reconfigure(encoding="utf-8")
    total = sum(len(v) for v in projects.values())
    print(f"# Sessions, last {args.days} days ({datetime.now():%Y-%m-%d})\n", file=out)
    print(f"{total} sessions with prompts in {len(projects)} projects"
          f" ({tests} test sessions under the temp folder left out).\n", file=out)
    print("## Instructions repeated across sessions\n", file=out)
    for n, p in repeated or [(0, "none")]:
        print(f"- ({n}x) {short(p, 120)}" if n else "- none", file=out)
    print("\n## Most frequent tool errors\n", file=out)
    for e, n in all_errors.most_common(12) or [("none", 0)]:
        print(f"- ({n}x) {e}" if n else "- none", file=out)
    print("\n## Permission denials by tool\n", file=out)
    print("- " + (", ".join(f"{t}: {n}" for t, n in all_denials.most_common()) or "none"), file=out)
    ranked = sorted(projects.items(), key=lambda kv: -len(kv[1]))
    print("\n## Projects\n", file=out)
    for name, sessions in ranked[: args.top]:
        errors = sum(len(s["errors"]) for s in sessions)
        denials = sum(sum(s["denials"].values()) for s in sessions)
        interrupts = sum(s["interrupts"] for s in sessions)
        models = sorted(set().union(*(s["models"] for s in sessions)))
        print(f"### {name}\n", file=out)
        print(f"{len(sessions)} sessions · {errors} tool errors · {denials} denials · {interrupts} interruptions"
              f" · models: {', '.join(models) or '?'}\n", file=out)
        goals = list(dict.fromkeys(short(s["prompts"][0], 140) for s in sessions))
        for g in goals[:8]:
            print(f"- goal: {g}", file=out)
        if len(goals) > 8:
            print(f"- … {len(goals) - 8} more goals", file=out)
        for e, n in Counter(e for s in sessions for e in s["errors"]).most_common(3):
            print(f"- error ({n}x): {e}", file=out)
        print("", file=out)
    rest = ranked[args.top:]
    if rest:
        print("### Other projects\n", file=out)
        for name, sessions in rest:
            print(f"- {name}: {len(sessions)} sessions; goal: {short(sessions[0]['prompts'][0], 90)}", file=out)


if __name__ == "__main__":
    main()
