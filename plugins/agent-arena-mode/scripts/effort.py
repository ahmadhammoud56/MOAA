#!/usr/bin/env python3
"""Effort trial: does a council role find more at high effort than at medium, per unit of cost?

  python effort.py plan --roles analyst,debugger --efforts medium,high --tasks tasks.json --out DIR [--repeats N]
  python effort.py record --dir DIR --cell ID --score S --findings N --tokens T [--seconds S]
  python effort.py summary --dir DIR

tasks.json: [{"id": "...", "brief": "...", "rubric": "...", "expected_findings": N}]. `plan` writes DIR/trials.json
with every (role, effort, task, repeat) cell in shuffled order and a blind label per cell, so the judge never sees the
effort. The coordinator dispatches each cell with the same brief and the cell's per-call effort, has the arena judge
score the answer blind, and records it. `summary` compares efforts per role on mean score, findings and tokens and
suggests a preset; it never edits profile.json (that change is the user's).

Rule (after the Cloudflare reviewer study, where medium effort lost real findings in some roles): keep the cheaper
effort unless the dearer one adds at least MIN_SCORE_GAIN points of mean score or MIN_FINDINGS_GAIN more findings.
"""
import argparse
import json
from pathlib import Path
import random
import statistics
import sys
import time

ORDER = ["low", "medium", "high", "xhigh", "max"]
MIN_SCORE_GAIN, MIN_FINDINGS_GAIN = 5.0, 0.25  # points of judge score; relative increase in findings


def plan(roles, efforts, tasks, repeats=1, seed=None):
    rnd = random.Random(seed)
    cells = [{"role": r, "effort": e, "task": t["id"], "repeat": k}
             for r in roles for e in efforts for t in tasks for k in range(repeats)]
    rnd.shuffle(cells)
    for i, c in enumerate(cells):
        c["id"] = f"c{i:03d}"
        c["label"] = f"candidate-{rnd.randrange(16 ** 6):06x}"  # what the judge sees instead of role and effort
    return {"created": time.time(), "roles": roles, "efforts": efforts, "tasks": tasks, "cells": cells, "results": {}}


def summarize(trial):
    """{role: {effort: {"n", "score", "findings", "tokens"}, "pick": effort, "why": text}} over recorded cells."""
    out = {}
    for role in trial["roles"]:
        stats = {}
        for effort in trial["efforts"]:
            rows = [trial["results"][c["id"]] for c in trial["cells"]
                    if c["role"] == role and c["effort"] == effort and c["id"] in trial["results"]]
            if rows:
                stats[effort] = {"n": len(rows), "score": statistics.mean(r["score"] for r in rows),
                                 "findings": statistics.mean(r["findings"] for r in rows),
                                 "tokens": statistics.mean(r["tokens"] for r in rows)}
        done = sorted(stats, key=ORDER.index)
        if not done:
            out[role] = {"pick": None, "why": "no results yet"}
            continue
        pick, why = done[0], "cheapest effort measured"
        for dearer in done[1:]:
            base, up = stats[pick], stats[dearer]
            more_found = base["findings"] and (up["findings"] - base["findings"]) / base["findings"] >= MIN_FINDINGS_GAIN
            if up["score"] - base["score"] >= MIN_SCORE_GAIN or more_found or (not base["findings"] and up["findings"]):
                pick = dearer
                why = (f"{dearer} adds {up['score'] - base['score']:+.1f} score and "
                       f"{up['findings'] - base['findings']:+.1f} findings for {up['tokens'] / max(base['tokens'], 1):.1f}x tokens")
            else:
                why = f"{dearer} adds too little ({up['score'] - base['score']:+.1f} score) for {up['tokens'] / max(base['tokens'], 1):.1f}x tokens"
        out[role] = {**stats, "pick": pick, "why": why}
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--roles", required=True); a.add_argument("--efforts", default="medium,high")
    a.add_argument("--tasks", required=True); a.add_argument("--out", required=True)
    a.add_argument("--repeats", type=int, default=1); a.add_argument("--seed", type=int)
    b = sub.add_parser("record")
    b.add_argument("--dir", required=True); b.add_argument("--cell", required=True)
    b.add_argument("--score", type=float, required=True); b.add_argument("--findings", type=float, default=0)
    b.add_argument("--tokens", type=float, default=0); b.add_argument("--seconds", type=float, default=0)
    c = sub.add_parser("summary")
    c.add_argument("--dir", required=True)
    args = p.parse_args(argv)
    if args.cmd == "plan":
        efforts = [e for e in args.efforts.split(",") if e]
        bad = [e for e in efforts if e not in ORDER]
        if bad:
            raise SystemExit(f"effort: unknown effort {bad}; one of {ORDER}")
        tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
        trial = plan([r for r in args.roles.split(",") if r], efforts, tasks, args.repeats, args.seed)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "trials.json").write_text(json.dumps(trial, indent=2), encoding="utf-8")
        for cell in trial["cells"]:
            print(f"{cell['id']}  {cell['label']}  role={cell['role']}  effort={cell['effort']}  task={cell['task']}")
        return 0
    path = Path(args.dir) / "trials.json"
    trial = json.loads(path.read_text(encoding="utf-8"))
    if args.cmd == "record":
        if args.cell not in {c["id"] for c in trial["cells"]}:
            raise SystemExit(f"effort: no cell {args.cell} in {path}")
        trial["results"][args.cell] = {"score": args.score, "findings": args.findings, "tokens": args.tokens,
                                       "seconds": args.seconds, "recorded": time.time()}
        path.write_text(json.dumps(trial, indent=2), encoding="utf-8")
        print(f"recorded {args.cell}: {len(trial['results'])}/{len(trial['cells'])} cells done")
        return 0
    for role, s in summarize(trial).items():
        cols = "  ".join(f"{e}: score {s[e]['score']:.1f}, findings {s[e]['findings']:.1f}, tokens {s[e]['tokens']:.0f} "
                         f"(n={s[e]['n']})" for e in trial["efforts"] if e in s)
        print(f"{role}\n  {cols}\n  suggest: {s['pick']} ({s['why']})")
    print("Suggestions only: change a role's preset in specialist-council/profile.json after the user agrees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
