#!/usr/bin/env python3
"""Specialist Council vs a single agent, on tasks with fixed answer keys. Standard library only.

  python bench.py run [--runs 3] [--arms solo-sonnet,solo-opus,council] [--cases ...] [--out results/DATE] [-j 3]
  python bench.py score [--out results/DATE]

Each run is a headless `claude -p` session in an empty folder with only project settings, so no user plugins, hooks
or output styles take part. The council arm adds only the specialist-council plugin (`--plugin-dir`). No arm may run
shell commands or write files, so answers come from reasoning and review, not from executing the code. Runs use the
logged-in Claude Code account; nothing needs an API key. Every run is saved as JSON (answer text, tokens, cost,
duration), and `run` skips runs already saved, so an interrupted benchmark resumes.
"""
import argparse
import concurrent.futures
import fractions
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
COUNCIL = HERE.parents[1] / "plugins" / "specialist-council"
ARMS = {
    "solo-sonnet": {"model": "sonnet", "council": False},
    "solo-opus": {"model": "opus", "council": False},
    "council": {"model": "sonnet", "council": True},
}
COUNCIL_PREFIX = ("Use the Specialist Council for this task (the specialist-council skill): dispatch at least two "
                  "independent specialists and cross-check their results before answering.\n\n")
TOOLS = ["--allowedTools", "Read", "Grep", "Glob", "Agent", "Skill",
         "--disallowedTools", "Bash", "PowerShell", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch"]
FORMATS = {
    "review": 'End with a fenced ```json block: {"bugs": [{"line": <line number>, "issue": "<one sentence>"}]}, one '
              "entry per distinct bug.",
    "claims": 'End with a fenced ```json block: {"wrong": ["<claim number>", ...]} listing every incorrect claim.',
    "answers": 'End with a fenced ```json block: {"answers": {"1": "<answer>", ...}} with an answer for every '
               "question.",
}
MARK = re.compile(r"\s*#!(BUG:(\w+)|OK)\s*$")


def load_cases(names=None):
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((HERE / "cases").glob("*.json"))]
    return [c for c in cases if not names or c["id"] in names]


def review_key(case):
    """(numbered code without markers, {bug id: {lines}}, {neutral lines})."""
    bugs, neutral, shown = {}, set(), []
    for n, line in enumerate(case["code"], 1):
        m = MARK.search(line)
        if m and m.group(2):
            bugs.setdefault(m.group(2), set()).add(n)
        elif m:
            neutral.add(n)
        shown.append(f"{n:>2} | {MARK.sub('', line)}")
    return "\n".join(shown), bugs, neutral


def prompt(case):
    if case["kind"] == "review":
        body = "```python\n" + review_key(case)[0] + "\n```"
    else:
        items = case["claims"] if case["kind"] == "claims" else case["questions"]
        body = "\n".join(f"{k}. {v}" for k, v in items.items())
    return f"{case['task']}\n\n{body}\n\n{FORMATS[case['kind']]}"


def run_one(case, arm, i, out):
    path = out / f"{case['id']}__{arm}__{i}.json"
    if path.is_file():
        return path, "skipped"
    spec = ARMS[arm]
    text = (COUNCIL_PREFIX if spec["council"] else "") + prompt(case)
    argv = [shutil.which("claude") or "claude", "-p", "--output-format", "json", "--model", spec["model"],
            "--setting-sources", "project", "--no-session-persistence", *TOOLS]
    if spec["council"]:
        argv += ["--plugin-dir", str(COUNCIL)]
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="moaa-bench-") as cwd:
        try:
            proc = subprocess.run(argv, input=text, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=1800)
            raw, err = proc.stdout, proc.stderr[-2000:]
        except subprocess.TimeoutExpired:
            raw, err = "", "timeout after 1800 s"
    try:
        data = json.loads(raw)
    except ValueError:
        data = {"is_error": True}
    record = {"case": case["id"], "arm": arm, "run": i, "started": round(started), "ended": round(time.time()),
              "model_alias": spec["model"],
              "council": spec["council"], "prompt": text, "result": data.get("result", ""),
              "is_error": bool(data.get("is_error")) or not raw, "error": err if not raw or data.get("is_error") else "",
              "total_cost_usd": data.get("total_cost_usd"), "duration_ms": data.get("duration_ms"),
              "num_turns": data.get("num_turns"), "usage": data.get("usage"), "modelUsage": data.get("modelUsage")}
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    return path, "error" if record["is_error"] else "ok"


def last_json(text):
    blocks = re.findall(r"```json\s*(.*?)```", text or "", re.S)
    for block in reversed(blocks):
        try:
            return json.loads(block)
        except ValueError:
            continue
    return None


def score(case, record):
    """{'score': 0..1, ...details} for one saved run."""
    parsed = last_json(record["result"])
    if record["is_error"] or not isinstance(parsed, dict):
        return {"score": 0.0, "parsed": False}
    if case["kind"] == "review":
        _, bugs, neutral = review_key(case)
        lines = set()
        for b in parsed.get("bugs", []):
            try:
                lines.add(int(b["line"]))
            except (KeyError, TypeError, ValueError):
                pass
        found = sorted(b for b, ls in bugs.items() if ls & lines)
        planted = set().union(*bugs.values())
        false_pos = sorted(lines - planted - neutral)
        return {"score": len(found) / len(bugs), "parsed": True, "found": found,
                "missed": sorted(set(bugs) - set(found)), "false_positive_lines": false_pos}
    if case["kind"] == "claims":
        said = {str(x) for x in parsed.get("wrong", [])}
        truth = set(case["wrong"])
        right = sum(1 for c in case["claims"] if (c in said) == (c in truth))
        return {"score": right / len(case["claims"]), "parsed": True, "said_wrong": sorted(said)}
    answers = parsed.get("answers", {})

    def value(s):  # equal values count, whatever the format: '147/10' == '14.7', '$1,401' == '1401'
        s = re.sub(r"[\s,$¢°]|cents?|degrees?", "", str(s)).lower()
        try:
            return fractions.Fraction(s)
        except (ValueError, ZeroDivisionError):
            return s
    right = [q for q, a in case["answers"].items() if q in answers and value(answers[q]) == value(a)]
    return {"score": len(right) / len(case["answers"]), "parsed": True,
            "wrong_questions": sorted(set(case["answers"]) - set(right))}


def summarize(out):
    cases = {c["id"]: c for c in load_cases()}
    rows = []
    for path in sorted(out.glob("*__*__*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        s = score(cases[rec["case"]], rec)
        # wall time: claude -p's duration_ms leaves out subagent work; runs saved before `ended` existed use the
        # file's write time, which is when the run finished
        ended = rec.get("ended") or path.stat().st_mtime
        rows.append({"case": rec["case"], "arm": rec["arm"], "run": rec["run"], **s,
                     "cost_usd": rec.get("total_cost_usd") or 0.0, "seconds": ended - rec["started"],
                     "error": rec["is_error"]})
    (out / "scores.json").write_text(json.dumps(rows, indent=2), encoding="utf-8", newline="\n")
    arms = [a for a in ARMS if any(r["arm"] == a for r in rows)]
    mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")  # noqa: E731
    lines = ["| Case | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
    for cid in sorted({r["case"] for r in rows}):
        cells = []
        for a in arms:
            rs = [r for r in rows if r["case"] == cid and r["arm"] == a]
            cells.append(f"{mean([r['score'] for r in rs]):.0%} (n={len(rs)})" if rs else "–")
        lines.append(f"| {cid} | " + " | ".join(cells) + " |")
    lines.append("| **Mean score** | " + " | ".join(f"**{mean([r['score'] for r in rows if r['arm'] == a]):.0%}**"
                                                 for a in arms) + " |")
    lines.append("| Mean cost per run (USD, API-equivalent) | " +
                 " | ".join(f"{mean([r['cost_usd'] for r in rows if r['arm'] == a]):.2f}" for a in arms) + " |")
    lines.append("| Mean wall time per run (s) | " +
                 " | ".join(f"{mean([r['seconds'] for r in rows if r['arm'] == a]):.0f}" for a in arms) + " |")
    fps = {a: sum(len(r.get("false_positive_lines", [])) for r in rows if r["arm"] == a) for a in arms}
    lines.append("| False-positive bug reports (all review runs) | " + " | ".join(str(fps[a]) for a in arms) + " |")
    errors = sum(r["error"] for r in rows)
    table = "\n".join(lines) + (f"\n\n{errors} run(s) ended in an error and scored 0." if errors else "")
    (out / "summary.md").write_text(table + "\n", encoding="utf-8", newline="\n")
    return table


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=("run", "score", "prompt"))
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--arms", default=",".join(ARMS))
    p.add_argument("--cases", default="")
    p.add_argument("--out", default=str(HERE / "results" / time.strftime("%Y-%m-%d")))
    p.add_argument("-j", "--jobs", type=int, default=3)
    a = p.parse_args(argv)
    out = Path(a.out)
    cases = load_cases([c for c in a.cases.split(",") if c])
    if a.command == "prompt":
        for c in cases:
            print(f"===== {c['id']}\n{prompt(c)}\n")
        return 0
    if a.command == "run":
        out.mkdir(parents=True, exist_ok=True)
        jobs = [(c, arm, i) for i in range(1, a.runs + 1) for c in cases for arm in a.arms.split(",")]
        with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
            for path, status in pool.map(lambda j: run_one(*j, out), jobs):
                print(f"{status:7} {path.name}", flush=True)
    print(summarize(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
