"""Validate an agent-teams roster JSON and print each worker's resolved settings.

Usage:
    python validate_team.py TEAM.json      # exit 0 valid, 1 invalid
    python validate_team.py --self-check   # run built-in tests

Implements the rules in references/configuration.md. Stdlib only.
"""
import json
import re
import sys

TOP = {"version", "task", "worker_count", "max_parallel", "execution_mode",
       "fallback", "lead", "defaults", "workers"}
WORKER = {"id", "role", "assignment", "model", "effort", "depends_on", "outputs"}
SETTINGS = {"model", "effort"}
MODES = {"auto", "subagents", "native-team", "plan-only", "sequential"}
FALLBACKS = {"ask", "plan-only", "sequential"}
EFFORTS = {"inherit", "low", "medium", "high", "xhigh", "max"}
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,47}$")


def _posint(v):
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def _settings(obj, where, errors):
    if not isinstance(obj, dict):
        errors.append(f"{where}: must be an object")
        return {}
    for k in obj.keys() - SETTINGS:
        errors.append(f"{where}: unknown field '{k}'")
    m, e = obj.get("model", "inherit"), obj.get("effort", "inherit")
    if not isinstance(m, str) or not m.strip():
        errors.append(f"{where}.model: must be a non-blank string")
    if e not in EFFORTS:
        errors.append(f"{where}.effort: must be one of {sorted(EFFORTS)}")
    return obj


def validate(team):
    """Return (errors, warnings, roster). roster is [(id, model, effort)]."""
    errors, warnings = [], []
    if not isinstance(team, dict):
        return ["top level: must be an object"], warnings, []
    for k in team.keys() - TOP:
        errors.append(f"unknown field '{k}'")
    if team.get("version", 1) != 1 or isinstance(team.get("version"), bool):
        errors.append("version: must be 1")
    n = team.get("worker_count")
    if not _posint(n):
        errors.append("worker_count: must be a positive integer")
        n = None
    mp = team.get("max_parallel", n)
    if mp is not None and (not _posint(mp) or (n and mp > n)):
        errors.append("max_parallel: must be a positive integer <= worker_count")
    if team.get("execution_mode", "auto") not in MODES:
        errors.append(f"execution_mode: must be one of {sorted(MODES)}")
    if team.get("fallback", "ask") not in FALLBACKS:
        errors.append(f"fallback: must be one of {sorted(FALLBACKS)}")
    _settings(team.get("lead", {}), "lead", errors)
    defaults = _settings(team.get("defaults", {}), "defaults", errors)

    workers = team.get("workers")
    if workers is None:
        return errors, warnings, []  # lead generates n assignments from the task
    if not isinstance(workers, list):
        return errors + ["workers: must be an array"], warnings, []
    if n is not None and len(workers) != n:
        errors.append(f"workers: has {len(workers)} entries, worker_count is {n}")

    ids, deps, outputs, roster = [], {}, {}, []
    for i, w in enumerate(workers):
        where = f"workers[{i}]"
        if not isinstance(w, dict):
            errors.append(f"{where}: must be an object")
            continue
        for k in w.keys() - WORKER:
            errors.append(f"{where}: unknown field '{k}'")
        wid = w.get("id")
        if not isinstance(wid, str) or not ID_RE.match(wid):
            errors.append(f"{where}.id: need 1-48 chars of a-z, 0-9, '-', starting with a letter")
            continue
        if wid in ids:
            errors.append(f"{where}.id: duplicate '{wid}'")
        ids.append(wid)
        if not isinstance(w.get("role"), str) or not w["role"].strip():
            errors.append(f"{wid}.role: required non-blank string")
        s = _settings({k: w[k] for k in SETTINGS if k in w}, wid, errors)
        roster.append((wid, s.get("model", defaults.get("model", "inherit")),
                       s.get("effort", defaults.get("effort", "inherit"))))
        d = w.get("depends_on", [])
        if not isinstance(d, list) or not all(isinstance(x, str) for x in d):
            errors.append(f"{wid}.depends_on: must be an array of worker ids")
            d = []
        deps[wid] = d
        for out in w.get("outputs", []) if isinstance(w.get("outputs", []), list) else []:
            if out in outputs:
                warnings.append(f"output '{out}' claimed by both {outputs[out]} and {wid}")
            outputs.setdefault(out, wid)

    for wid, d in deps.items():
        for x in d:
            if x == wid:
                errors.append(f"{wid}.depends_on: depends on itself")
            elif x not in deps:
                errors.append(f"{wid}.depends_on: unknown worker '{x}'")
    state = {}  # cycle check: 1 = visiting, 2 = done

    def visit(u, path):
        state[u] = 1
        for v in deps.get(u, []):
            if v not in deps or v == u:
                continue
            if state.get(v) == 1:
                errors.append("dependency cycle: " + " -> ".join(path + [u, v]))
            elif not state.get(v):
                visit(v, path + [u])
        state[u] = 2

    for wid in deps:
        if not state.get(wid):
            visit(wid, [])
    return errors, warnings, roster


def main(argv):
    if argv == ["--self-check"]:
        return self_check()
    if len(argv) != 1:
        print(__doc__)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as f:
            team = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read {argv[0]}: {exc}")
        return 1
    errors, warnings, roster = validate(team)
    for e in errors:
        print("ERROR:", e)
    for w in warnings:
        print("WARN:", w)
    for wid, model, effort in roster:
        print(f"{wid}: model={model} effort={effort}")
    print("invalid" if errors else "valid")
    return 1 if errors else 0


def self_check():
    good = {"version": 1, "worker_count": 2, "max_parallel": 1,
            "defaults": {"model": "sonnet", "effort": "medium"},
            "workers": [{"id": "a", "role": "x", "model": "opus", "effort": "high"},
                        {"id": "b", "role": "y", "depends_on": ["a"]}]}
    e, w, r = validate(good)
    assert not e and not w, (e, w)
    assert r == [("a", "opus", "high"), ("b", "sonnet", "medium")], r

    def errs(**changes):
        t = json.loads(json.dumps(good))
        t.update(changes)
        return validate(t)[0]

    assert errs(worker_count=True), "bool must not pass as int"
    assert errs(worker_count=3), "length mismatch"
    assert errs(max_parallel=5), "max_parallel above worker_count"
    assert errs(colour="red"), "unknown top-level field"
    assert errs(execution_mode="swarm")
    assert errs(defaults={"effort": "ultrathink"})
    assert errs(workers=[{"id": "a", "role": "x"}, {"id": "a", "role": "y"}]), "duplicate id"
    assert errs(workers=[{"id": "A", "role": "x"}, {"id": "b", "role": "y"}]), "bad id"
    assert errs(workers=[{"id": "a", "role": ""}, {"id": "b", "role": "y"}]), "blank role"
    assert errs(workers=[{"id": "a", "role": "x", "depends_on": ["a"]},
                         {"id": "b", "role": "y"}]), "self dependency"
    assert errs(workers=[{"id": "a", "role": "x", "depends_on": ["zz"]},
                         {"id": "b", "role": "y"}]), "missing dependency"
    cyc = errs(workers=[{"id": "a", "role": "x", "depends_on": ["b"]},
                        {"id": "b", "role": "y", "depends_on": ["a"]}])
    assert any("cycle" in x for x in cyc), cyc
    t = json.loads(json.dumps(good))
    t["workers"][0]["outputs"] = ["out.md"]
    t["workers"][1]["outputs"] = ["out.md"]
    assert validate(t)[1], "shared output should warn"
    assert not validate({"worker_count": 3})[0], "workers may be omitted"
    print("self-check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
