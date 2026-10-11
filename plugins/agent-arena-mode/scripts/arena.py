#!/usr/bin/env python3
"""Local single-writer arena ledger. No network, model calls, or code execution.

Python 3.9+. Claude drives mode procedures; this helper checks records and limits.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import library

MODES = ("judge", "tournament", "swarm", "league", "evolution", "synthesis", "redteam", "cascade")
WEIGHTS = {"correctness": 35, "coverage": 25, "evidence": 20, "robustness": 10, "clarity": 10}
IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}\Z")


class ArenaError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ArenaError(message)


def number(value, low, high, label):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            f"{label} must be a finite number in [{low}, {high}]")
    return value


def identifier(value):
    require(isinstance(value, str) and IDENTIFIER.fullmatch(value), "Invalid identifier")
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def atomic_json(path, data):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".arena-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class state_lock:
    """Exclusive per-run lock so parallel helper calls cannot lose ledger updates."""
    def __init__(self, directory, timeout=60, stale=300):
        self.path = Path(directory) / "state.lock"
        self.timeout, self.stale = timeout, stale

    def __enter__(self):
        deadline = time.time() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    # ponytail: mtime staleness check; switch to OS file locks if helper calls ever hold it for minutes
                    if time.time() - self.path.stat().st_mtime > self.stale:
                        self.path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                require(time.time() < deadline, "Run is locked by another helper call; retry")
                time.sleep(.05)

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def mode_name(value):
    if value in [str(n) for n in range(1, 9)]:
        return MODES[int(value) - 1]
    require(value in MODES, f"Mode must be one of {', '.join(MODES)}")
    return value


MODEL_IDS = library.MODEL_IDS
EFFORTS = library.EFFORTS
DIFFICULTIES = ("low", "medium", "high", "critical")
# Worker mix per difficulty: (tier, effort, share). Mixed tiers add method diversity at bounded cost.
WORKER_MIX = {
    "low": [("haiku", "medium", .5), ("sonnet", "low", .5)],
    "medium": [("sonnet", "medium", .75), ("haiku", "medium", .25)],
    "high": [("sonnet", "high", .6), ("opus", "high", .4)],
    "critical": [("opus", "high", .6), ("fable", "high", .2), ("sonnet", "high", .2)],
}
ROLE_SETTINGS = {  # role -> difficulty -> (tier, effort)
    "judge": {"low": ("opus", "medium"), "medium": ("opus", "high"), "high": ("fable", "high"), "critical": ("fable", "xhigh")},
    "critic": {"low": ("sonnet", "medium"), "medium": ("sonnet", "high"), "high": ("opus", "high"), "critical": ("opus", "xhigh")},
    "synthesizer": {"low": ("opus", "high"), "medium": ("opus", "high"), "high": ("fable", "high"), "critical": ("fable", "xhigh")},
}
ROLE_SETTINGS["validator"] = ROLE_SETTINGS["judge"]


def model_id(name):
    """Map an alias to the pinned 5.5-generation ID; keep explicit IDs unchanged."""
    return MODEL_IDS.get(name, name)


def assign(agents, difficulty="medium", seed=42, worker_model=None, worker_effort=None,
           judge_model=None, judge_effort=None, mode="judge"):
    """Deterministic model/effort plan for every slot and role, decided before dispatch."""
    require(difficulty in DIFFICULTIES, f"difficulty must be one of {', '.join(DIFFICULTIES)}")
    for effort in (worker_effort, judge_effort):
        require(effort is None or effort in EFFORTS, f"effort must be one of {', '.join(EFFORTS)}")
    mix = WORKER_MIX[difficulty]
    if mode == "cascade":  # short proposals one step cheaper; finalists use the full mix
        mix = WORKER_MIX[DIFFICULTIES[max(0, DIFFICULTIES.index(difficulty) - 1)]]
    raw = [share * agents for _, _, share in mix]
    counts = [int(x) for x in raw]
    for i in sorted(range(len(mix)), key=lambda i: raw[i] - counts[i], reverse=True)[:agents - sum(counts)]:
        counts[i] += 1  # largest remainder keeps the total exact
    slots = [(tier, effort) for (tier, effort, _), n in zip(mix, counts) for _ in range(n)]
    random.Random(f"{seed}:models").shuffle(slots)
    if worker_model or worker_effort:
        slots = [(worker_model or tier, worker_effort or effort) for tier, effort in slots]
    roles = {role: {"model": model_id(t), "effort": e} for role, table in ROLE_SETTINGS.items()
             for t, e in [table[difficulty]]}
    roles["finalist"] = {"model": model_id(WORKER_MIX[difficulty][0][0]), "effort": WORKER_MIX[difficulty][0][1]}
    for role in ("judge", "validator"):
        roles[role] = {"model": model_id(judge_model) if judge_model else roles[role]["model"],
                       "effort": judge_effort or roles[role]["effort"]}
    return {"difficulty": difficulty, "slots": [{"model": model_id(t), "effort": e} for t, e in slots],
            "roles": roles, "summary": {f"{model_id(t)}/{e}": n for (t, e, _), n in zip(mix, counts) if n}}


def plan(mode="judge", agents=100, rounds=None, concurrency=8):
    mode = mode_name(mode)
    require(type(agents) is int and agents >= 2, "agents must be an integer >= 2")
    rounds = (5 if mode == "league" else 3) if rounds is None else rounds
    require(type(rounds) is int and rounds >= 1, "rounds must be an integer >= 1")
    require(type(concurrency) is int and concurrency >= 1, "concurrency must be >= 1")
    batches = lambda n: math.ceil(n / 8)
    if mode == "judge":
        calls = agents + batches(agents) + 2
    elif mode == "tournament":
        calls = agents + 5 * (agents - 1) + 1
    elif mode == "league":
        calls = agents + batches(agents) + rounds * (agents // 2) + 2
    elif mode == "evolution":
        elites = math.ceil(agents / 4)
        births = (rounds - 1) * (agents - elites)
        calls = agents + births + batches(agents) + (rounds - 1) * batches(agents - elites) + 2
    elif mode == "synthesis":
        calls = agents + batches(agents) + 2
    elif mode == "redteam":
        builders = math.ceil(agents / 2)
        critics = agents - builders
        calls = builders + rounds * (critics + builders + batches(builders)) + 2
    else:
        remaining = agents
        calls = agents
        if mode == "swarm":
            for _ in range(rounds):
                calls += remaining + batches(remaining)
                remaining = max(2, math.ceil(remaining / 2))
        else:
            for _ in range(rounds):
                calls += batches(remaining)
                remaining = math.ceil(remaining / 2)
                calls += remaining
                if remaining <= 2:
                    break
            calls += remaining  # complete-answer allowance for remaining proposals
        calls += 2
    return {"mode": mode, "agents": agents, "rounds": rounds,
            "concurrency": min(concurrency, agents), "estimated_calls": calls,
            "suggested_max_calls": calls + max(4, math.ceil(calls * .10)),
            "note": "Planning estimate, not token/cost prediction. Batch size assumes 8 full artifacts fit."}


def validate_rubric(rubric):
    require(isinstance(rubric, dict), "rubric must be an object")
    weights = rubric.get("weights")
    require(isinstance(weights, dict) and weights, "rubric.weights must be nonempty")
    for key, value in weights.items():
        identifier(key)
        number(value, .001, 100, f"weight {key}")
    require(abs(sum(weights.values()) - 100) < 1e-8, "Weights must sum to 100")
    gates = rubric.get("gates")
    require(isinstance(gates, dict) and gates, "Define at least one named hard gate")
    for key, anchor in gates.items():
        identifier(key)
        require(isinstance(anchor, str) and anchor.strip(), "Gate needs a check/acceptance anchor")


def strategy_cards(n, seed):
    lenses = ["first principles", "counterexamples", "minimal solution", "measurement", "constraint analysis",
              "user workflow", "failure analysis", "alternative architecture", "evidence audit", "boundary cases"]
    approaches = ["start with a test", "compare two alternatives", "build the smallest prototype",
                  "work backward from acceptance", "investigate the weakest assumption",
                  "map dependencies", "derive an invariant", "inspect concrete examples",
                  "measure tradeoffs", "test a competing hypothesis"]
    priorities = ["simplicity", "reliability", "traceability", "performance", "maintainability",
                  "usability", "compatibility", "coverage", "reproducibility", "resource economy"]
    cards = [(a, b, c) for a in lenses for b in approaches for c in priorities]
    random.Random(seed).shuffle(cards)
    return [{"slot": f"a{i+1:04d}", "lens": cards[i % len(cards)][0],
             "approach": cards[i % len(cards)][1], "priority": cards[i % len(cards)][2],
             "exploration_seed": seed + i} for i in range(n)]


def init_run(directory, task_file, rubric_file, **options):
    require(not (options.get("no_library") and options.get("database")), "Choose --database or --no-library, not both")
    if options.get("quick"):
        require(options.get("agents") in (None, 8), "--quick conflicts with an explicit --agents count")
        options["agents"] = 8
    elif options.get("agents") is None:
        options["agents"] = 100
    run_id = str(uuid.uuid4())
    config = plan(options.get("mode", "judge"), options["agents"],
                  options.get("rounds"), options.get("concurrency", 8))
    config.update({"seed": options.get("seed", 42), "threshold": options.get("threshold", 85),
                   "max_minutes": options.get("max_minutes", 60),
                   "max_calls": config["suggested_max_calls"] if options.get("max_calls") is None else options["max_calls"]})
    config["context_key"] = options.get("context_key") or run_id
    config["database"] = None if options.get("no_library") else str(Path(
        options.get("database") or library.default_database(directory)).resolve())
    config["patience"] = options.get("patience", 2)
    require(type(config["patience"]) is int and config["patience"] >= 1, "patience must be an integer >= 1")
    assignment = assign(config["agents"], options.get("difficulty") or "medium", config["seed"],
                        options.get("worker_model"), options.get("worker_effort"),
                        options.get("judge_model"), options.get("judge_effort"), config["mode"])
    config["models"] = {"difficulty": assignment["difficulty"], "roles": assignment["roles"],
                        "workers": assignment["summary"], "actual": "unknown until runtime reports it"}
    config["communication"] = options.get("communication") or "auto"
    number(config["threshold"], 0, 100, "threshold")
    number(config["max_minutes"], .001, 100000, "max_minutes")
    require(type(config["max_calls"]) is int and config["max_calls"] >= 1, "max_calls must be >= 1")
    rubric = read_json(rubric_file)
    validate_rubric(rubric)
    task = Path(task_file).read_bytes()
    require(task.strip(), "Task file is empty")
    reuse = [x.strip() for x in (options.get("reuse") or "").split(",") if x.strip()]
    require(len(reuse) == len(set(reuse)) and len(reuse) <= config["agents"],
            "--reuse IDs must be distinct and fit within --agents")
    reuse_db = config["database"] or library.default_database(directory)
    reused = []
    for agent_id in reuse:
        require(re.fullmatch(r"ag_[a-f0-9]{24}", agent_id), f"Invalid saved agent ID {agent_id}")
        entry = library.get_entry(reuse_db, agent_id)  # raises on unknown or corrupt entries
        require(entry["validation"] not in ("invalidated", "ineligible"), f"Saved agent {agent_id} was invalidated; refusing reuse")
        prof = entry["profile"]
        known = [m for m in (prof.get("model_actual"), prof.get("model_requested")) if m and m != "unknown"]
        reused.append({"id": agent_id, "name": prof["name"], "validation": entry["validation"],
                       "model": model_id(known[0]) if known else None,
                       "effort": prof.get("effort_requested") if prof.get("effort_requested") in EFFORTS else None})
    directory = Path(directory).resolve()
    require(not directory.exists(), "Run path already exists; use status to resume, or choose a new path")
    directory.mkdir(parents=True)
    for sub in ("artifacts", "incoming", "briefs", "evidence", "checkpoints", "exchange"):
        (directory / sub).mkdir()
    (directory / "task.md").write_bytes(task)
    atomic_json(directory / "rubric.json", rubric)
    state = {"schema": 1, "run_id": run_id, "config": config, "created": time.time(),
             "task_sha256": digest(task), "rubric_sha256": digest((directory / "rubric.json").read_bytes()),
             "roster": strategy_cards(config["agents"], config["seed"]),
             "jobs": {}, "candidates": {}, "assessments": {}, "final_assessments": {},
             "assessment_history": [], "rounds": {}, "exchanges": {}, "progress": [],
             "checkpoint": {"phase": "generate", "generation": 0, "next_action": "Dispatch initial candidates",
                            "best_eligible": None, "plateau": 0},
             "result": None}
    for slot, setting in zip(state["roster"], assignment["slots"]):
        slot.update(setting)
    for slot, item in zip(state["roster"], reused):  # a reused agent keeps the model it was validated with
        slot.update(reuse=item["id"], reuse_name=item["name"], reuse_validation=item["validation"],
                    model=item["model"] or slot["model"], effort=item["effort"] or slot["effort"])
    summary = {}
    for slot in state["roster"]:  # report the roster actually dispatched, including reused slots
        key = f"{slot['model']}/{slot['effort']}"
        summary[key] = summary.get(key, 0) + 1
    config["models"]["workers"] = summary
    checkpoint(state)
    atomic_json(directory / "state.json", state)
    return state


def load(directory):
    directory = Path(directory).resolve()
    state = read_json(directory / "state.json")
    require(state.get("schema") == 1, "Unsupported state schema")
    require(digest((directory / "task.md").read_bytes()) == state["task_sha256"], "Frozen task changed")
    require(digest((directory / "rubric.json").read_bytes()) == state["rubric_sha256"], "Frozen rubric changed")
    return state


def current_candidate(directory, state, cid):
    identifier(cid)
    require(cid in state["candidates"], f"Unknown candidate {cid}")
    candidate = state["candidates"][cid]
    require(digest((Path(directory) / "artifacts" / f"{cid}.md").read_bytes()) == candidate["sha256"],
            f"Candidate {cid} changed after registration")
    return candidate


def reserve(state, role, label, model=None, effort=None):
    require(state["result"] is None, "Run is concluded; start a new run for more work")
    require(len(state["jobs"]) < state["config"]["max_calls"], "Call budget exhausted")
    require(time.time() - state["created"] < state["config"]["max_minutes"] * 60, "Dispatch deadline exceeded")
    running = sum(j["status"] == "running" for j in state["jobs"].values())
    require(running < state["config"]["concurrency"], "Concurrency limit reached")
    require(role.strip() and label.strip(), "Job needs role and label")
    jid = f"j{len(state['jobs'])+1:05d}"
    require(effort is None or effort in EFFORTS, "Unknown effort level")
    state["jobs"][jid] = {"role": role, "label": label, "status": "running", "reserved": time.time()}
    if model or effort:  # requested settings for this dispatch; actual values go in finish evidence
        state["jobs"][jid].update(model=model_id(model) if model else None, effort=effort)
    return {"job": jid, **state["jobs"][jid]}


def finish(state, jid, status, evidence):
    require(jid in state["jobs"], "Unknown job")
    require(status in ("done", "failed", "cancelled"), "Invalid finish status")
    require(evidence.strip(), "Record runtime ID, outputs, or failure evidence")
    job = state["jobs"][jid]
    if job["status"] != "running":
        require(job["status"] == status and job["evidence"] == evidence, "Job already finished differently")
        return job
    job.update(status=status, evidence=evidence, finished=time.time())
    return job


def add_candidate(directory, state, cid, source, parents=(), profile=None, evidence=()):
    identifier(cid)
    require(state["result"] is None, "Run already concluded")
    require(cid not in state["candidates"], "Use a new ID for every revision")
    require(len(set(parents)) == len(parents), "Duplicate parent")
    for parent in parents:
        current_candidate(directory, state, parent)
    data = Path(source).read_bytes()
    require(data.strip(), "Candidate is empty")
    bundle = library.profile_bundle("", profile, evidence)
    packed = library.canonical(bundle).encode("utf-8")
    target = Path(directory) / "artifacts" / f"{cid}.md"
    with target.open("xb") as handle:
        handle.write(data)
    bundle_path = Path(directory) / "artifacts" / f"{cid}.bundle.json"
    with bundle_path.open("xb") as handle:
        handle.write(packed)
    candidate = {"sha256": digest(data), "parents": list(parents), "active": True,
                 "rating": 1500.0, "games": 0, "byes": 0,
                 "bundle": {"file": bundle_path.name, "sha256": digest(packed)}}
    state["candidates"][cid] = candidate
    return {"candidate": cid, **candidate}


def assess(directory, state, report, final=False):
    require(isinstance(report, dict), "Assessment must be a JSON object")
    cid = report.get("candidate")
    candidate = current_candidate(directory, state, cid)
    require(report.get("sha256") == candidate["sha256"], "Assessment does not match candidate hash")
    rubric = read_json(Path(directory) / "rubric.json")
    weights = rubric["weights"]
    scores = report.get("scores")
    require(isinstance(scores, dict) and set(scores) == set(weights), "Assessment criteria do not match rubric")
    for key, value in scores.items():
        number(value, 0, 10, key)
    gates = report.get("gates")
    require(isinstance(gates, dict) and set(gates) == set(rubric["gates"]), "Assessment must cover exactly all gates")
    for gate in gates.values():
        require(isinstance(gate, dict) and gate.get("status") in ("pass", "fail", "unverified"), "Invalid gate status")
        require(isinstance(gate.get("evidence"), str) and gate["evidence"].strip(), "Gate evidence is required")
    require(type(report.get("fatal")) is bool, "fatal must be a JSON boolean")
    findings = report.get("findings")
    require(isinstance(findings, list) and all(isinstance(x, str) and x.strip() for x in findings), "Invalid findings")
    require(not report["fatal"] or findings, "Fatal defect needs a finding")
    for key in ("judge", "rationale"):
        require(isinstance(report.get(key), str) and report[key].strip(), f"{key} is required")
    if final:
        previous_judges = {r["judge"] for r in state["assessment_history"] if r["candidate"] == cid}
        require(report["judge"] not in previous_judges, "Final validation needs a fresh judge identity")
    checked = dict(report)
    checked["total"] = round(sum(scores[k] * weights[k] / 10 for k in weights), 8)
    checked["eligible"] = not report["fatal"] and all(g["status"] == "pass" for g in gates.values())
    checked["final"] = final
    state["assessment_history"].append(checked)
    state["final_assessments" if final else "assessments"][cid] = checked
    return checked


def quality(report):
    return (report["eligible"], not report["fatal"], report["total"],
            report["scores"].get("correctness", 0), report["scores"].get("clarity", 0))


def ranking(directory, state, include_archived=False, elo=False):
    rows = []
    for cid, candidate in state["candidates"].items():
        if not include_archived and not candidate["active"]:
            continue
        current_candidate(directory, state, cid)
        report = state["assessments"].get(cid)
        if report:
            rows.append({"candidate": cid, "total": report["total"], "eligible": report["eligible"],
                         "rating": candidate["rating"], "games": candidate["games"],
                         "quality": quality(report)})
    rows.sort(key=lambda row: ((row["rating"], row["quality"], row["games"]) if elo else row["quality"]), reverse=True)
    return rows


def pair(directory, state, round_id, ids, fixed=None, dry_run=False):
    identifier(round_id)
    require(round_id not in state["rounds"], "Round already exists; read it instead of rescheduling")
    require(len(ids) >= 2 and len(ids) == len(set(ids)), "Need at least two distinct candidates")
    require(all(all(m["result"] is not None for m in rnd["matches"]) for rnd in state["rounds"].values()),
            "Finish the open adjudication round first")
    for cid in ids:
        require(current_candidate(directory, state, cid)["active"], "Cannot pair an archived candidate")
    rng = random.Random(f"{state['config']['seed']}:{round_id}")
    remaining = list(ids)
    rng.shuffle(remaining)
    previous = {frozenset((m["a"], m["b"])) for rd in state["rounds"].values() for m in rd["matches"]}
    if fixed is not None:
        require(isinstance(fixed, list) and all(isinstance(p, list) and len(p) == 2 for p in fixed), "fixed must be a list of pairs")
        flat = [cid for p in fixed for cid in p]
        require(all(isinstance(cid, str) for cid in flat), "Pair IDs must be strings")
        require(len(flat) == len(set(flat)) and set(flat) <= set(ids) and len(ids)-len(flat) <= 1, "Fixed pairs must cover entrants once (one bye allowed)")
        pairs = fixed
        bye = next((cid for cid in ids if cid not in flat), None)
    else:
        bye = None
        if len(remaining) % 2:
            bye = min(remaining, key=lambda cid: state["candidates"][cid]["byes"])
            remaining.remove(bye)
        if state["config"]["mode"] == "league":
            remaining.sort(key=lambda cid: state["candidates"][cid]["rating"], reverse=True)
        pairs = []
        while remaining:
            a = remaining.pop(0)
            fresh = [b for b in remaining if frozenset((a, b)) not in previous]
            pool = fresh or remaining
            b = min(pool, key=lambda cid: abs(state["candidates"][a]["rating"]-state["candidates"][cid]["rating"]))
            remaining.remove(b)
            pairs.append([a, b])
    if bye and not dry_run:
        state["candidates"][bye]["byes"] += 1
    rd = {"bye": bye, "matches": [{"a": a, "b": b, "a_sha": state["candidates"][a]["sha256"],
            "b_sha": state["candidates"][b]["sha256"], "rematch": frozenset((a, b)) in previous,
            "result": None} for a, b in pairs]}
    if dry_run:  # preview attack-phase pairs without opening a scored round
        return {**rd, "dry_run": True}
    state["rounds"][round_id] = rd
    return rd


def record_match(directory, state, round_id, a, b, reason, tie_winner=None):
    require(reason.strip(), "Match needs judge rationale")
    require(round_id in state["rounds"], "Unknown round")
    matches = [m for m in state["rounds"][round_id]["matches"] if (m["a"], m["b"]) == (a, b)]
    require(len(matches) == 1, "Pair not scheduled in this order")
    match = matches[0]
    if match["result"] is not None:
        require(match["reason"] == reason and match.get("tie_winner") == tie_winner, "Conflicting duplicate verdict")
        return match
    reports = []
    for cid, expected in ((a, match["a_sha"]), (b, match["b_sha"])):
        require(current_candidate(directory, state, cid)["sha256"] == expected, "Scheduled version changed")
        report = state["assessments"].get(cid)
        require(report and report["sha256"] == expected, "Missing assessment of scheduled version")
        reports.append(report)
    qa, qb = map(quality, reports)
    if qa == qb:
        if state["config"]["mode"] == "league":
            require(tie_winner is None, "League ties are draws")
            winner = "draw"
        else:
            require(tie_winner in (a, b), "Exact knockout tie requires an explicit judge tie_winner")
            winner = tie_winner
    else:
        require(tie_winner is None, "tie_winner is only allowed for an exact tie")
        winner = a if qa > qb else b
    ca, cb = state["candidates"][a], state["candidates"][b]
    before = [ca["rating"], cb["rating"]]
    if state["config"]["mode"] == "league":
        expected = 1 / (1 + 10 ** ((cb["rating"] - ca["rating"]) / 400))
        actual = .5 if winner == "draw" else float(winner == a)
        change = 24 * (actual - expected)
        ca["rating"] += change
        cb["rating"] -= change
    ca["games"] += 1
    cb["games"] += 1
    match.update(result=winner, reason=reason, tie_winner=tie_winner,
                 assessments=reports, ratings_before=before, ratings_after=[ca["rating"], cb["rating"]])
    return match


def conclude(directory, state, cid, reason, coverage_complete):
    require(state["result"] is None, "Run already concluded")
    require(not any(j["status"] == "running" for j in state["jobs"].values()), "Reconcile running jobs before concluding")
    require(reason.strip(), "Stopping reason required")
    if coverage_complete and state["config"]["mode"] in ("evolution", "synthesis"):
        require(any(j["role"] == "synthesizer" and j["status"] == "done" for j in state["jobs"].values()),
                "Evolution/synthesis coverage needs a finished synthesizer job (synthesis follows even an early stop)")
    final = None
    if cid:
        current_candidate(directory, state, cid)
        final = state["final_assessments"].get(cid)
        stronger = [other for other, report in state["final_assessments"].items()
                    if other != cid and report["eligible"] and (final is None or quality(report) > quality(final))]
        require(not stronger, "Chosen candidate regresses against independently validated " + ",".join(stronger) +
                "; deliver that candidate and label the regressed one rejected")
    accepted = bool(final and final["eligible"] and final["total"] >= state["config"]["threshold"])
    state["result"] = {"candidate": cid, "accepted": accepted,
                       "coverage_complete": coverage_complete,
                       "competition_complete": coverage_complete and all(
                           m["result"] is not None for rd in state["rounds"].values() for m in rd["matches"]),
                       "reason": reason, "final_total": final["total"] if final else None,
                       "calls_reserved": len(state["jobs"])}
    return state["result"]


def checkpoint(state, phase=None, generation=None, next_action=None):
    point = state["checkpoint"]
    if phase is not None:
        require(phase.strip(), "phase must be nonempty")
        point["phase"] = phase
    if generation is not None:
        require(generation >= point["generation"], "generation cannot move backward")
        point["generation"] = generation
    if next_action is not None:
        require(next_action.strip(), "next_action must be nonempty")
        point["next_action"] = next_action
    point["active"] = [cid for cid, c in state["candidates"].items() if c["active"]]
    point["pending_jobs"] = [j for j, job in state["jobs"].items() if job["status"] == "running"]
    point["calls_used"] = len(state["jobs"])
    point["calls_remaining"] = state["config"]["max_calls"] - len(state["jobs"])
    point["database"] = state["config"].get("database")
    point["updated"] = time.time()
    return point


def progress(state, generation, reserve_calls=2):
    """Record a completed round/generation; return plateau count and stop recommendation."""
    require(type(generation) is int and generation >= 0, "generation must be an integer >= 0")
    done = {p["generation"]: p for p in state["progress"]}
    best = max((r["total"] for r in state["assessments"].values() if r["eligible"]), default=None)
    if generation in done:
        require(done[generation]["best_eligible"] == best, "Generation already recorded with a different best score")
        return done[generation]
    require(not state["progress"] or generation == state["progress"][-1]["generation"] + 1,
            "Record generations in order")
    previous = state["checkpoint"]["best_eligible"]
    improved = best is not None and (previous is None or best >= previous + 1)
    plateau = 0 if improved else state["checkpoint"]["plateau"] + 1
    config = state["config"]
    if best is not None and best >= config["threshold"]:
        stop = "target-candidate (needs fresh final validation)"
    elif plateau >= config["patience"]:
        stop = "plateau"
    elif generation + 1 >= config["rounds"]:
        stop = "round-limit"
    elif config["max_calls"] - len(state["jobs"]) <= reserve_calls:
        stop = "budget"
    elif time.time() - state["created"] >= config["max_minutes"] * 60:
        stop = "deadline"
    else:
        stop = None
    record = {"generation": generation, "best_eligible": best, "improved": improved,
              "plateau": plateau, "stop": stop}
    state["progress"].append(record)
    state["checkpoint"].update(best_eligible=best if improved else previous, plateau=plateau, generation=generation)
    return record


def cull(directory, state, keep=None, fraction=None, minimum=1, reason="Not retained after round"):
    """Retain the strongest active assessed candidates; archive (never delete) the rest."""
    active = [cid for cid, c in state["candidates"].items() if c["active"]]
    missing = [cid for cid in active if cid not in state["assessments"]]
    require(not missing, "Assess or retire these active candidates first: " + ",".join(missing))
    require((keep is None) != (fraction is None), "Give exactly one of --keep or --fraction")
    if fraction is not None:
        number(fraction, .001, 1, "fraction")
        keep = math.ceil(len(active) * fraction)
    require(type(keep) is int and keep >= 1, "keep must be >= 1")
    keep = max(keep, minimum)
    rows = ranking(directory, state)
    kept = [row["candidate"] for row in rows[:keep]]
    retired = [row["candidate"] for row in rows[keep:]]
    for cid in retired:
        state["candidates"][cid].update(active=False, retired_reason=reason)
    return {"kept": kept, "retired": retired}


def exchange(directory, state, round_id, ids, group_size=4):
    """Round-based file exchange: copy frozen peer drafts into per-agent folders after private drafting."""
    identifier(round_id)
    require(round_id not in state["exchanges"], "Exchange round already opened")
    require(type(group_size) is int and group_size >= 2, "group size must be >= 2")
    require(len(ids) >= 2 and len(set(ids)) == len(ids), "Need at least two distinct candidates")
    for cid in ids:
        require(current_candidate(directory, state, cid)["active"], f"{cid} is archived")
        require(cid in state["assessments"], f"{cid} has no assessment; private drafts must be complete and frozen first")
    order = list(ids)
    random.Random(f"{state['config']['seed']}:exchange:{round_id}").shuffle(order)
    groups = [order[i:i + group_size] for i in range(0, len(order), group_size)]
    if len(groups) > 1 and len(groups[-1]) == 1:
        groups[-2].extend(groups.pop())
    root = Path(directory).resolve() / "exchange" / round_id
    root.mkdir(parents=True)
    for group in groups:
        for cid in group:
            inbox = root / cid
            inbox.mkdir()
            for peer in group:
                if peer != cid:
                    (inbox / f"{peer}.md").write_bytes((Path(directory) / "artifacts" / f"{peer}.md").read_bytes())
    (root / "board.md").write_text(f"# Findings board ({round_id})\n\nCoordinator appends evidence-backed findings here.\n",
                                   encoding="utf-8")
    record = {"backend": "round-based file exchange (not live messaging)", "groups": groups,
              "peer_reads_per_agent": max(len(g) for g in groups) - 1, "path": str(root)}
    state["exchanges"][round_id] = record
    return record


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    def sizing(sp):
        sp.add_argument("--mode", default="judge")
        sp.add_argument("--agents", type=int, default=100)
        sp.add_argument("--rounds", type=int)
        sp.add_argument("--concurrency", type=int, default=8)
    sp = sub.add_parser("plan")
    sizing(sp)
    sp.add_argument("--difficulty", default="medium", choices=DIFFICULTIES)
    sp.add_argument("--seed", type=int, default=42)
    sp = sub.add_parser("init")
    sizing(sp)
    sp.set_defaults(agents=None)
    sp.add_argument("--quick", action="store_true")
    sp.add_argument("--patience", type=int, default=2)
    sp.add_argument("--worker-model")
    sp.add_argument("--judge-model")
    sp.add_argument("--judge-effort")
    sp.add_argument("--communication")
    sp.add_argument("--reuse", help="Comma-separated saved library IDs seeding the first roster slots")
    sp.add_argument("--difficulty", choices=DIFFICULTIES, help="Coordinator's task classification; drives model assignment")
    sp.add_argument("--worker-effort", choices=EFFORTS)
    sp.add_argument("--dir", required=True)
    sp.add_argument("--task", required=True)
    sp.add_argument("--rubric", required=True)
    sp.add_argument("--seed", type=int, default=42)
    sp.add_argument("--threshold", type=float, default=85)
    sp.add_argument("--max-calls", type=int)
    sp.add_argument("--max-minutes", type=float, default=60)
    sp.add_argument("--database", help="Persistent SQLite library path; defaults to plugin data or run-parent library")
    sp.add_argument("--no-library", action="store_true", help="Disable persistent library writes for this run")
    sp.add_argument("--context-key", help="Explicit evaluation-baseline fingerprint for comparable runs")
    for cmd in ("status", "reserve", "finish", "add", "assess", "rank", "pair", "match", "retire", "conclude",
                "checkpoint", "progress", "cull", "exchange"):
        sp = sub.add_parser(cmd)
        sp.add_argument("--dir", required=True)
        if cmd == "reserve":
            sp.add_argument("--role", required=True)
            sp.add_argument("--label", required=True)
            sp.add_argument("--model")
            sp.add_argument("--effort", choices=EFFORTS)
        elif cmd == "finish":
            sp.add_argument("--job", required=True)
            sp.add_argument("--status", choices=("done", "failed", "cancelled"), required=True)
            sp.add_argument("--evidence", required=True)
        elif cmd == "add":
            sp.add_argument("--candidate", required=True)
            sp.add_argument("--file", required=True)
            sp.add_argument("--parents", default="")
            sp.add_argument("--profile", help="JSON containing reusable agent instructions and metadata")
            sp.add_argument("--evidence-file", action="append", default=[], help="Explicit file to snapshot into the library; repeatable")
        elif cmd == "assess":
            sp.add_argument("--report", required=True)
            sp.add_argument("--final", action="store_true")
        elif cmd == "rank":
            sp.add_argument("--all", action="store_true")
            sp.add_argument("--elo", action="store_true")
        elif cmd == "pair":
            sp.add_argument("--round", required=True)
            sp.add_argument("--ids", required=True, help="Comma-separated frozen candidate IDs")
            sp.add_argument("--fixed", help="JSON file of exact pairs; optional one unpaired bye")
            sp.add_argument("--dry-run", action="store_true", help="Preview pairs (attack phase) without opening a round")
        elif cmd == "match":
            for flag in ("round", "a", "b", "reason"):
                sp.add_argument("--" + flag, required=True)
            sp.add_argument("--tie-winner")
        elif cmd == "retire":
            sp.add_argument("--candidate", required=True)
            sp.add_argument("--reason", required=True)
        elif cmd == "checkpoint":
            sp.add_argument("--phase")
            sp.add_argument("--generation", type=int)
            sp.add_argument("--next-action")
        elif cmd == "progress":
            sp.add_argument("--generation", type=int, required=True)
            sp.add_argument("--reserve-calls", type=int, default=2)
        elif cmd == "cull":
            sp.add_argument("--keep", type=int)
            sp.add_argument("--fraction", type=float)
            sp.add_argument("--min", type=int, default=1)
            sp.add_argument("--reason", default="Not retained after round")
        elif cmd == "exchange":
            sp.add_argument("--round", required=True)
            sp.add_argument("--ids", required=True)
            sp.add_argument("--group-size", type=int, default=4)
        elif cmd == "conclude":
            sp.add_argument("--candidate")
            sp.add_argument("--reason", required=True)
            sp.add_argument("--coverage-complete", action="store_true")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        cmd = args.command
        if cmd == "plan":
            result = plan(args.mode, args.agents, args.rounds, args.concurrency)
            result["assignment"] = {k: v for k, v in assign(args.agents, args.difficulty, args.seed,
                                                           mode=result["mode"]).items() if k != "slots"}
        elif cmd == "init":
            options = vars(args).copy()
            for key in ("command", "dir", "task", "rubric"):
                options.pop(key)
            result = init_run(args.dir, args.task, args.rubric, **options)
        elif cmd in ("status", "rank"):
            state = load(args.dir)
            result = state if cmd == "status" else ranking(args.dir, state, args.all, args.elo)
        else:
            with state_lock(args.dir):
                result, state = mutate(args)
            if cmd in ("assess", "conclude") and state["config"].get("database"):
                try:
                    result = {**result, "library": library.sync_run(args.dir, state)}
                except (OSError, ValueError, KeyError, TypeError, library.sqlite3.Error) as exc:
                    raise ArenaError("Run state saved, but library sync failed: " + str(exc) +
                                     ". Retry with library.py sync --dir RUN; do not repeat the assessment.") from exc
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ArenaError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"arena: {exc}", file=sys.stderr)
        return 2


def mutate(args):
    """Apply one ledger mutation under the run lock and save it atomically."""
    cmd = args.command
    state = load(args.dir)
    require(state["result"] is None, "Run concluded; only reads allowed")
    if cmd == "reserve":
        result = reserve(state, args.role, args.label, args.model, args.effort)
    elif cmd == "finish":
        result = finish(state, args.job, args.status, args.evidence)
    elif cmd == "add":
        result = add_candidate(args.dir, state, args.candidate, args.file, args.parents.split(",") if args.parents else [],
                               read_json(args.profile) if args.profile else None, args.evidence_file)
    elif cmd == "assess":
        result = assess(args.dir, state, read_json(args.report), args.final)
    elif cmd == "checkpoint":
        result = checkpoint(state, args.phase, args.generation, args.next_action)
    elif cmd == "progress":
        result = progress(state, args.generation, args.reserve_calls)
    elif cmd == "cull":
        result = cull(args.dir, state, args.keep, args.fraction, args.min, args.reason)
    elif cmd == "exchange":
        result = exchange(args.dir, state, args.round, args.ids.split(","), args.group_size)
    elif cmd == "pair":
        result = pair(args.dir, state, args.round, args.ids.split(","), read_json(args.fixed) if args.fixed else None,
                      args.dry_run)
    elif cmd == "match":
        result = record_match(args.dir, state, args.round, args.a, args.b, args.reason, args.tie_winner)
    elif cmd == "retire":
        candidate = current_candidate(args.dir, state, args.candidate)
        require(args.reason.strip(), "Retirement needs a reason")
        candidate.update(active=False, retired_reason=args.reason)
        result = candidate
    elif cmd == "conclude":
        result = conclude(args.dir, state, args.candidate, args.reason, args.coverage_complete)
    checkpoint(state)
    atomic_json(Path(args.dir) / "state.json", state)
    return result, state


if __name__ == "__main__":
    sys.exit(main())
