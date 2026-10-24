#!/usr/bin/env python3
"""Karpathy loop bookkeeping: a fixed metric decides, not the agent's opinion.

  python loop.py init DIR --metric "CMD" [--direction min|max] [--max-iters N] [--max-minutes M] [--timeout S]
  python loop.py record DIR "what this attempt changed"   run the metric, compare with the best, log the result
  python loop.py status DIR

After autoresearch (github.com/karpathy/autoresearch): edit, measure with a fixed script, keep the change if the
number improved, otherwise discard it, repeat until the budget runs out. `record` prints KEEP, DISCARD or STOP and
exits 0, 3 or 4, so the agent (or a script) knows what to do with the working tree. The metric command must print a
number; the last number in its output is used. DIR holds loop.json (fixed settings), program.md (the human's
instructions) and results.tsv (every attempt).
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

KEEP, DISCARD, STOP = 0, 3, 4
NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
PROGRAM = """# Loop program (written by the human; the agent follows it and does not edit it)

Goal: <what to improve, in one sentence>
Metric: `{metric}` ({direction}imize; the last number it prints). Never edit the metric script or its data.
Editable: <the files the agent may change>
Rules: one idea per attempt; keep attempts small; note what was tried in the record description.
Stop: {stop}.
"""


def init(d, metric, direction, max_iters, max_minutes, timeout):
    d.mkdir(parents=True, exist_ok=True)
    cfg = {"metric": metric, "direction": direction, "max_iters": max_iters, "max_minutes": max_minutes,
           "timeout": timeout, "started": time.time(), "best": None, "iters": 0}
    (d / "loop.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    stop = " or ".join(s for s in (f"{max_iters} attempts" if max_iters else "",
                                   f"{max_minutes} minutes" if max_minutes else "") if s) or "when the user says so"
    if not (d / "program.md").exists():
        (d / "program.md").write_text(PROGRAM.format(metric=metric, direction=direction, stop=stop), encoding="utf-8")
    if not (d / "results.tsv").exists():
        (d / "results.tsv").write_text("iter\ttime\tvalue\tdecision\tdescription\n", encoding="utf-8")
    return cfg


def measure(cfg):
    try:
        out = subprocess.run(cfg["metric"], shell=True, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=cfg["timeout"])
    except subprocess.TimeoutExpired:
        return None, "metric timed out"
    nums = NUMBER.findall(out.stdout) if out.returncode == 0 else []
    if not nums:
        return None, f"metric failed (exit {out.returncode}): {(out.stderr or out.stdout).strip()[-200:]}"
    return float(nums[-1]), ""


def better(value, best, direction):
    return best is None or (value < best if direction == "min" else value > best)


def out_of_budget(cfg):
    return bool((cfg["max_iters"] and cfg["iters"] >= cfg["max_iters"]) or
                (cfg["max_minutes"] and time.time() - cfg["started"] >= cfg["max_minutes"] * 60))


def record(d, description):
    cfg = json.loads((d / "loop.json").read_text(encoding="utf-8"))
    if out_of_budget(cfg):
        return STOP, f"STOP: budget used ({cfg['iters']} attempts); best {cfg['best']}", cfg
    value, err = measure(cfg)
    cfg["iters"] += 1
    if value is not None and better(value, cfg["best"], cfg["direction"]):
        decision, code = "KEEP", KEEP
        cfg["best"] = value
    else:
        decision, code = "DISCARD", DISCARD
    with (d / "results.tsv").open("a", encoding="utf-8") as f:
        f.write(f"{cfg['iters']}\t{time.strftime('%Y-%m-%d %H:%M:%S')}\t{'' if value is None else value}\t"
                f"{decision}\t{(description + (' | ' + err if err else '')).replace(chr(9), ' ')}\n")
    (d / "loop.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    msg = (f"{decision}: {value if value is not None else err} (best {cfg['best']}, attempt {cfg['iters']})" +
           ("; commit this change" if code == KEEP else "; revert this attempt's edits before the next one"))
    if out_of_budget(cfg):
        msg += "\nSTOP after this: budget used"
    return code, msg, cfg


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("init"); a.add_argument("dir"); a.add_argument("--metric", required=True)
    a.add_argument("--direction", choices=("min", "max"), default="min")
    a.add_argument("--max-iters", type=int, default=20); a.add_argument("--max-minutes", type=float, default=0)
    a.add_argument("--timeout", type=int, default=600)
    a = sub.add_parser("record"); a.add_argument("dir"); a.add_argument("description")
    a = sub.add_parser("status"); a.add_argument("dir")
    args = p.parse_args(argv)
    d = Path(args.dir)
    if args.cmd == "init":
        cfg = init(d, args.metric, args.direction, args.max_iters, args.max_minutes, args.timeout)
        value, err = measure(cfg)  # the baseline every attempt has to beat
        if value is not None:
            cfg["best"] = value
            (d / "loop.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print(f"loop ready in {d.as_posix()}: baseline {value if value is not None else err}; edit program.md")
        return 0
    if args.cmd == "record":
        code, msg, _ = record(d, args.description)
        print(msg)
        return code
    cfg = json.loads((d / "loop.json").read_text(encoding="utf-8"))
    rows = (d / "results.tsv").read_text(encoding="utf-8").splitlines()[1:]
    kept = sum(1 for r in rows if "\tKEEP\t" in r)
    print(f"best {cfg['best']} ({cfg['direction']}), {cfg['iters']} attempts, {kept} kept, "
          f"budget {'used' if out_of_budget(cfg) else 'left'}")
    print("\n".join(rows[-5:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
