#!/usr/bin/env python3
"""Arm trials: the same frozen tasks through different setups ("arms"), judged blind, compared on score and cost.

  python trial.py plan --arms solo,council --tasks tasks.json --out DIR [--repeats K] [--tokens-per-run T]
                       [--max-runs N] [--seed S]
  python trial.py record --dir DIR --cell ID --score S [--passed] [--tokens T] [--seconds S]
  python trial.py summary --dir DIR

Two skills use it. fold-trial: one agent loop (`solo`) against a council (`council`), after Anthropic's guidance on
when subagents earn their cost. harness-league: the same model family through different agent harnesses (`claude`,
`codex`, `gemini`, `opencode` through allies), since one harness can score far higher than another on the same tasks.

tasks.json: [{"id", "brief", "rubric", "pass": "what counts as solved"}]. `plan` writes DIR/trials.json with every
(arm, task, repeat) cell in shuffled order and a blind label, prints the expected token cost first, and refuses a plan
above --max-runs (default 40). `summary` reports per arm the mean score, pass rate, tokens and seconds, and the tasks
whose pass/fail differs between arms (the flips), which are the cases worth reading.
"""
import argparse
import json
from pathlib import Path
import random
import statistics
import sys
import time

MAX_RUNS, TOKENS_PER_RUN = 40, 30000


def plan(arms, tasks, repeats=1, seed=None):
    rnd = random.Random(seed)
    cells = [{"arm": a, "task": t["id"], "repeat": k} for a in arms for t in tasks for k in range(repeats)]
    rnd.shuffle(cells)
    for i, c in enumerate(cells):
        c["id"] = f"c{i:03d}"
        c["label"] = f"candidate-{rnd.randrange(16 ** 6):06x}"  # what the judge sees instead of the arm
    return {"created": time.time(), "arms": arms, "tasks": tasks, "cells": cells, "results": {}}


def summarize(trial):
    """({arm: {n, score, pass_rate, tokens, seconds}}, [(task, {arm: pass rate})] for tasks the arms disagree on)."""
    res, cells = trial["results"], trial["cells"]
    arms = {}
    for arm in trial["arms"]:
        rows = [res[c["id"]] for c in cells if c["arm"] == arm and c["id"] in res]
        if rows:
            arms[arm] = {"n": len(rows), "score": statistics.mean(r["score"] for r in rows),
                         "pass_rate": statistics.mean(1.0 if r["passed"] else 0.0 for r in rows),
                         "tokens": statistics.mean(r["tokens"] for r in rows),
                         "seconds": statistics.mean(r["seconds"] for r in rows)}
    flips = []
    for t in trial["tasks"]:
        rates = {}
        for arm in trial["arms"]:
            rows = [res[c["id"]] for c in cells if c["arm"] == arm and c["task"] == t["id"] and c["id"] in res]
            if rows:
                rates[arm] = statistics.mean(1.0 if r["passed"] else 0.0 for r in rows)
        if len(rates) > 1 and len({round(v, 2) for v in rates.values()}) > 1:
            flips.append((t["id"], rates))
    return arms, flips


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--arms", required=True); a.add_argument("--tasks", required=True); a.add_argument("--out", required=True)
    a.add_argument("--repeats", type=int, default=1); a.add_argument("--seed", type=int)
    a.add_argument("--tokens-per-run", type=int, default=TOKENS_PER_RUN, help="estimate used for the cost line")
    a.add_argument("--max-runs", type=int, default=MAX_RUNS, help="refuse a plan with more runs than this")
    b = sub.add_parser("record")
    b.add_argument("--dir", required=True); b.add_argument("--cell", required=True)
    b.add_argument("--score", type=float, required=True); b.add_argument("--passed", action="store_true")
    b.add_argument("--tokens", type=float, default=0); b.add_argument("--seconds", type=float, default=0)
    c = sub.add_parser("summary")
    c.add_argument("--dir", required=True)
    args = p.parse_args(argv)
    if args.cmd == "plan":
        arms = list(dict.fromkeys(x for x in args.arms.split(",") if x))
        if len(arms) < 2:
            raise SystemExit("trial: give at least two arms")
        tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
        runs = len(arms) * len(tasks) * args.repeats
        print(f"{runs} runs ({len(arms)} arms x {len(tasks)} tasks x {args.repeats}), about "
              f"{runs * args.tokens_per_run:,} tokens at {args.tokens_per_run:,} per run, plus judging")
        if runs > args.max_runs:
            raise SystemExit(f"trial: {runs} runs is over --max-runs {args.max_runs}; cut tasks or repeats, or raise "
                             "the cap after the user agrees to the cost")
        trial = plan(arms, tasks, args.repeats, args.seed)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "trials.json").write_text(json.dumps(trial, indent=2), encoding="utf-8")
        for cell in trial["cells"]:
            print(f"{cell['id']}  {cell['label']}  arm={cell['arm']}  task={cell['task']}")
        return 0
    path = Path(args.dir) / "trials.json"
    trial = json.loads(path.read_text(encoding="utf-8"))
    if args.cmd == "record":
        if args.cell not in {c["id"] for c in trial["cells"]}:
            raise SystemExit(f"trial: no cell {args.cell} in {path}")
        trial["results"][args.cell] = {"score": args.score, "passed": args.passed, "tokens": args.tokens,
                                       "seconds": args.seconds, "recorded": time.time()}
        path.write_text(json.dumps(trial, indent=2), encoding="utf-8")
        print(f"recorded {args.cell}: {len(trial['results'])}/{len(trial['cells'])} cells done")
        return 0
    arms, flips = summarize(trial)
    for arm, s in arms.items():
        print(f"{arm:<10} n={s['n']}  score {s['score']:.1f}  pass {s['pass_rate']:.0%}  tokens {s['tokens']:.0f}  "
              f"{s['seconds']:.0f}s")
    for task, rates in flips:
        print(f"flip {task}: " + ", ".join(f"{a} {r:.0%}" for a, r in rates.items()))
    if not flips and len(arms) > 1:
        print("no flips: the arms pass and fail the same tasks")
    print(f"{len(trial['results'])}/{len(trial['cells'])} cells recorded; small samples decide nothing on their own.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
