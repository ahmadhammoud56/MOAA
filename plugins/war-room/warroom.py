"""War Room conductor: plan, launch, watch, wake, tile, serve and stop a team of real `claude` workers.

Workers are native Claude Code background sessions (`claude --bg`), each with a curated plugin set, its own
permission profile, the War Room bus (MCP) and hooks. The conductor never types into a terminal: it talks
to workers through the bus, and restarts idle ones with `claude --resume`. Standard library only.

  python warroom.py toggle on|off|status       war mode switch (launch refuses while off)
  python warroom.py plan PLAN.json             resolve roles, curate plugins, estimate cost, print preview
  python warroom.py launch RUN --confirm CODE  start the workers (CODE comes from the preview)
  python warroom.py status RUN [--json]        workers, meter, tasks, recent events
  python warroom.py post RUN TITLE [--detail D] [--to WORKER]
  python warroom.py send RUN WORKER MESSAGE    message a worker (a parked worker wakes on it)
  python warroom.py wake RUN WORKER [MESSAGE]  message + restart the worker if it is not parked
  python warroom.py pause|unpause RUN          stop/allow new task claims (usage guard)
  python warroom.py stop RUN                   panic stop: every worker, conversations kept
  python warroom.py resume RUN [WORKER...]     resume stopped workers with full context
  python warroom.py watch RUN [--schedule]     conductor loop: usage guard, auto-wake, watchdog
  python warroom.py tile RUN                   one console per worker, grid on the primary screen
  python warroom.py serve RUN [--port N]       live dashboard on 127.0.0.1
  python warroom.py list                       runs on this machine
"""
import argparse
import glob
import hashlib
import hmac
import shlex
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bus import Bus  # noqa: E402

HOME = os.path.join(os.path.expanduser("~"), ".claude", "war-room")
RUNS = os.path.join(HOME, "runs")
CONFIG = os.path.join(HOME, "config.json")
CALIBRATION = os.path.join(HOME, "calibration.json")
HUB = os.path.join(HOME, "hub.json")
HARD_DEFAULTS = {"max_workers": 3, "pause_at": 85, "stop_at": 95, "max_hours": 4, "wait_seconds": 570,
                 "gates": True, "gate_score": 85, "max_fails": 2, "auto_finish": True, "auto_integrate": False}
SETTING_LIMITS = {"max_workers": (1, 8), "pause_at": (10, 99), "stop_at": (11, 100), "max_hours": (0.25, 72),
                  "wait_seconds": (60, 7200), "gate_score": (50, 100), "max_fails": (1, 5)}
DEFAULT_PER_WORKER_TASK = 12 * 70_000  # tokens processed per worker per task before any run is measured
IS_WIN = os.name == "nt"
NL = "\n"
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,23}$")
HARD_MAX_WORKERS = 8
RESUME_PROMPT = ("You were resumed by the War Room conductor (after a stop or usage reset). Call last_checkpoint and "
                 "inbox, re-check any task you still own with board, then continue the protocol.")
WAKE_PROMPT = "Woken by the War Room orchestrator: call inbox, act on the messages, checkpoint, then continue the protocol."
WARNING = """\
WARNING - WAR MODE uses real, parallel Claude Code sessions.
  * Every worker counts against the same plan limits (5-hour and weekly) as your own session.
  * Each worker loads ~40-60k tokens of context before doing anything, then re-reads its context every turn.
  * Long runs can exhaust the 5-hour window. The usage guard pauses claims at the pause threshold and stops
    every worker at the stop threshold; conversations are kept and resume after the reset.
  * Workers run unattended with a narrow allow-list (dontAsk). Push, publish, delete and spend are denied."""


# ---------------------------------------------------------------- small helpers
def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def run_dir(run):
    path = os.path.join(RUNS, run)
    if not os.path.isdir(path):
        die(f"no such run: {run} (see `warroom.py list`)")
    return path


def open_bus(run, agent="orchestrator"):
    return Bus(os.path.join(run_dir(run), "bus.sqlite3"), agent)


def claude_bin():
    exe = shutil.which("claude")
    if not exe:
        die("claude CLI not found on PATH")
    if IS_WIN and exe.lower().endswith((".cmd", ".bat")):
        native = os.path.join(os.path.dirname(exe), "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
        if os.path.isfile(native):
            return native
        die(f"claude resolves to a {exe[-4:]} shim; cmd.exe would interpret the worker prompts. Install the native "
            "claude.exe (claude install) or put it first on PATH.")
    return exe


def claude(*args, cwd=None, timeout=120):
    try:
        p = subprocess.run([claude_bin(), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"claude {' '.join(args[:2])} timed out after {timeout}s"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


_agents_cache = {"t": 0, "v": [], "ok": False}
_agents_lock = threading.Lock()


def sessions(max_age=3.0):
    """`claude agents --json --all`, cached briefly. On failure the last good list is kept and ok turns False."""
    with _agents_lock:
        if time.time() - _agents_cache["t"] > max_age:
            code, out = claude("agents", "--json", "--all", timeout=30)
            try:
                if code != 0:
                    raise ValueError(out[-200:])
                _agents_cache.update(v=json.loads(out[out.index("["):]), ok=True)
            except ValueError:
                _agents_cache["ok"] = False
            _agents_cache["t"] = time.time()
        return _agents_cache["v"]


def sessions_ok():
    return _agents_cache["ok"]


def session_of(session_id, max_age=0):
    return next((s for s in sessions(max_age) if s.get("sessionId") == session_id), None)


def pid_alive(pid):
    if not pid:
        return False
    if IS_WIN:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def pid_cmdline(pid):
    if IS_WIN:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                           capture_output=True, text=True)
        return r.stdout.strip()
    r = subprocess.run(["ps", "-o", "command=", "-p", str(int(pid))], capture_output=True, text=True)
    return r.stdout.strip()


def parse_bg_id(out):
    """Short id from `claude --bg` output: 'backgrounded · ba9eedb9 · name' (or a 'started a copy as X' note)."""
    m = re.search(r"started a copy as ([0-9a-f]{8})", out) or re.search(r"backgrounded\W+([0-9a-f]{8})", out)
    return m.group(1) if m else None


# ---------------------------------------------------------------- installed plugins, MCP servers, council
def installed_plugins():
    data = load_json(os.path.join(os.path.expanduser("~"), ".claude", "plugins", "installed_plugins.json"), {})
    return {k: v[0]["installPath"] for k, v in (data.get("plugins") or {}).items() if v}


def user_mcp_servers():
    return (load_json(os.path.join(os.path.expanduser("~"), ".claude.json"), {}) or {}).get("mcpServers", {})


def council_py():
    path = installed_plugins().get("specialist-council@moaa")
    for root in filter(None, [path, os.path.join(HERE, "..", "..", "plugins", "specialist-council")]):
        if os.path.isfile(os.path.join(root, "council.py")):
            return os.path.join(root, "council.py")
    die("specialist-council not found (install specialist-council@moaa)")


def resolve_role(role, styles=None):
    args = [sys.executable, council_py(), "resolve", "--role", role] + (["--style", styles] if styles else [])
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        die(f"council resolve failed for role {role!r}: {p.stdout.strip()} {p.stderr.strip()}")
    return json.loads(p.stdout)


# ---------------------------------------------------------------- plan
def kind_for(role, profiles):
    for kind, spec in profiles["kinds"].items():
        if role in spec["roles"]:
            return kind
    return profiles["default_kind"]


def calibration_values(calibration):
    return sorted(r["per_worker_task"] for r in (calibration or {}).get("runs", {}).values() if r.get("per_worker_task"))


def per_worker_task(calibration):
    """Median tokens processed per worker per finished task over measured runs (falls back to the spike figure)."""
    vals = calibration_values(calibration)
    return (vals[len(vals) // 2], len(vals)) if vals else (DEFAULT_PER_WORKER_TASK, 0)


def estimate(workers, n_tasks, per_task=DEFAULT_PER_WORKER_TASK, spread=None):
    """Token estimate (cache-read dominated): slim base per worker plus measured cost per worker-task. With measured
    runs, the range spans the cheapest to the dearest run (plus 25%); without, it is 0.6x to 1.6x of the guess."""
    tasks_each = math.ceil(max(n_tasks, 1) / max(len(workers), 1)) + 1  # +1: reviews and hand-offs
    base = sum(42_000 + 8_000 * len(w["plugins"]) for w in workers)
    if spread:
        lo, hi = min(spread), max(spread)
        return int(base + len(workers) * tasks_each * lo * 0.9), int(base + len(workers) * tasks_each * hi * 1.25)
    total = base + len(workers) * tasks_each * per_task
    return int(total * 0.6), int(total * 1.6)


def settings():
    """War Room defaults for new plans: built-in values overlaid with what the user saved in the app."""
    return {**HARD_DEFAULTS, **((load_json(CONFIG, {}) or {}).get("defaults") or {})}


def validate_settings(raw):
    """Clean a settings dict from the UI: known keys only, right types, within limits, pause below stop."""
    out = {}
    for k, default in HARD_DEFAULTS.items():
        if k not in raw:
            continue
        v = raw[k]
        if isinstance(default, bool):
            out[k] = bool(v)
            continue
        v = float(v) if isinstance(default, float) or k == "max_hours" else int(float(v))
        lo, hi = SETTING_LIMITS[k]
        if not lo <= v <= hi:
            raise ValueError(f"{k} must be between {lo} and {hi}")
        out[k] = v
    merged = {**settings(), **out}
    if merged["pause_at"] >= merged["stop_at"]:
        raise ValueError("pause_at must be below stop_at")
    return out


def resolve_plan(plan, profiles, plugins_index, mcp_index, defaults=None):
    if not plan.get("workers"):
        die("plan has no workers")
    budget = {**HARD_DEFAULTS, **(defaults or {}), **(plan.get("budget") or {})}
    if len(plan["workers"]) > min(budget["max_workers"], HARD_MAX_WORKERS):
        die(f"{len(plan['workers'])} workers exceeds max_workers={budget['max_workers']} (hard cap {HARD_MAX_WORKERS})")
    names, out = set(), []
    for w in plan["workers"]:
        name, role = w.get("name", ""), w.get("role", "")
        if not NAME_RE.match(name) or name in names or name == "orchestrator":
            die(f"bad or duplicate worker name {name!r} (lowercase, digits, dashes, max 24)")
        names.add(name)
        kind = w.get("kind") or kind_for(role, profiles)
        if kind not in profiles["kinds"]:
            die(f"unknown kind {kind!r} for worker {name}")
        spec = profiles["kinds"][kind]
        resolved = resolve_role(role, w.get("style")) if not (w.get("model") and w.get("effort")) else {}
        plugin_keys = list(dict.fromkeys(spec["plugins"] + w.get("plugins", [])))
        missing = [k for k in plugin_keys if k not in plugins_index]
        if missing:
            die(f"worker {name}: plugins not installed: {missing}")
        mcp_names = list(dict.fromkeys([m for t in w.get("tags", []) for m in profiles["mcp_by_tag"].get(t, [])]
                                       + w.get("mcp", [])))
        missing = [m for m in mcp_names if m not in mcp_index]
        if missing:
            die(f"worker {name}: MCP servers not configured: {missing}")
        out.append({"name": name, "role": role, "kind": kind,
                    "model": w.get("model") or resolved["model"], "effort": w.get("effort") or resolved["effort"],
                    "write": bool(w.get("write", spec["write"])), "brief": w.get("brief", ""),
                    "plugins": plugin_keys, "plugin_dirs": [plugins_index[k] for k in plugin_keys],
                    "mcp": mcp_names, "permission_mode": spec["permission_mode"],
                    "allow": spec["allow"] + w.get("allow", []), "deny": profiles["deny"]})
    project = os.path.abspath(plan.get("project", "."))
    return {"name": plan.get("name", "run"), "goal": plan.get("goal", ""),
            "project": project, "worktrees": worktrees_dir(project), "workers": out,
            "tasks": plan.get("tasks", []), "budget": budget}


def trusted(path):
    """True when Claude Code's workspace trust covers path (it or an ancestor accepted the trust prompt).
    `claude --bg` refuses untrusted folders, and War Room never bypasses that prompt."""
    projects = (load_json(os.path.join(os.path.expanduser("~"), ".claude.json"), {}) or {}).get("projects", {})
    norm = lambda p: os.path.normcase(os.path.normpath(p))  # noqa: E731
    ok = {norm(k) for k, v in projects.items() if v.get("hasTrustDialogAccepted")}
    top = subprocess.run(["git", "-C", path, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode == 0:  # trust is keyed to the repository root: a nested repo is a new project
        return norm(top.stdout.strip()) in ok
    cur = norm(path)
    while True:
        if cur in ok:
            return True
        parent = os.path.dirname(cur)
        if parent == cur:
            return False
        cur = parent


def worktrees_dir(project):
    """`claude --worktree` creates worktrees under the main repository's .claude/worktrees, even from a linked worktree."""
    p = subprocess.run(["git", "-C", project, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                       capture_output=True, text=True)
    root = os.path.dirname(p.stdout.strip()) if p.returncode == 0 else project
    return os.path.normpath(os.path.join(root, ".claude", "worktrees"))


def confirm_code(resolved):
    return hashlib.sha256(json.dumps(resolved, sort_keys=True).encode()).hexdigest()[:6]


def cmd_plan(a):
    plan = load_json(a.plan) or die(f"cannot read {a.plan}")
    profiles = load_json(os.path.join(HERE, "profiles.json"))
    resolved = resolve_plan(plan, profiles, installed_plugins(), user_mcp_servers(), settings())
    if not trusted(resolved["project"]):
        die(f"Claude Code does not trust {resolved['project']} yet. Run `claude` there once, accept the trust prompt, "
            "then plan again.")
    run = f"{re.sub(r'[^a-z0-9]+', '-', resolved['name'].lower()).strip('-')[:20]}-{time.strftime('%Y%m%d-%H%M%S')}"
    save_json(os.path.join(RUNS, run, "plan.json"), resolved)
    cal = load_json(CALIBRATION, {})
    per_task, n_runs = per_worker_task(cal)
    lo, hi = estimate(resolved["workers"], len(resolved["tasks"]), per_task, calibration_values(cal))
    meter = last_meter()
    print(f"WAR ROOM PLAN  run={run}\nproject: {resolved['project']}\ngoal: {resolved['goal']}\n")
    print(f"{'worker':<14}{'role':<22}{'kind':<10}{'model':<20}{'effort':<8}{'write':<7}plugins / mcp")
    for w in resolved["workers"]:
        extras = ", ".join([k.split('@')[0] for k in w["plugins"]] + [f"mcp:{m}" for m in w["mcp"]])
        print(f"{w['name']:<14}{w['role']:<22}{w['kind']:<10}{w['model']:<20}{w['effort']:<8}"
              f"{'yes' if w['write'] else 'no':<7}{extras}")
    b = resolved["budget"]
    print(f"\ntasks seeded: {len(resolved['tasks'])}   budget: pause claims at {b['pause_at']}% / stop at {b['stop_at']}% "
          f"of the 5-hour window, max {b['max_hours']} h")
    basis = f"calibrated on {n_runs} measured run(s)" if n_runs else "uncalibrated: no measured runs yet"
    print(f"estimated tokens processed: {lo/1e6:.1f}M - {hi/1e6:.1f}M (mostly cache reads; {basis})")
    print(f"review gates: {'on' if b['gates'] else 'off'} (pass score {b['gate_score']}, arbitration after "
          f"{b['max_fails']} failed reviews); approved commits merge into branch war-room/{run}")
    print(f"last known plan meter: {meter}\n")
    print(WARNING)
    print(f"\nTo launch:  python warroom.py launch {run} --confirm {confirm_code(resolved)}")


def last_meter():
    best = None
    for run in os.listdir(RUNS) if os.path.isdir(RUNS) else []:
        db = os.path.join(RUNS, run, "bus.sqlite3")
        if os.path.exists(db):
            row = Bus(db, "orchestrator").db.execute(
                "SELECT ts, five_pct, week_pct FROM meter WHERE five_pct IS NOT NULL ORDER BY ts DESC LIMIT 1").fetchone()
            if row and (best is None or row["ts"] > best["ts"]):
                best = dict(row)
    if not best:
        return "unknown (no worker has reported yet)"
    return f"5-hour {best['five_pct']}%, weekly {best['week_pct']}% ({int((time.time() - best['ts']) / 60)} min ago)"


# ---------------------------------------------------------------- launch
def protocol_prompt(w, resolved, run):
    roster = ", ".join(x["name"] for x in resolved["workers"] if x["name"] != w["name"]) or "none"
    b = {"gate_score": 85, **resolved.get("budget", {})}
    if w["write"]:
        write = (f"You work in your own git worktree. Finish each task as its own commit, then call "
                 f"complete_task(id, result, commit=<full hash from `git rev-parse HEAD`>). Never push.\n"
                 f"- Your work is reviewed by another worker before it counts. A failed review puts the task back on "
                 f"the board for you with notes. Approved commits are merged by the conductor into branch war-room/{run}; "
                 f"on a merge conflict the task comes back: run `git merge war-room/{run}` in your worktree, resolve, "
                 f"commit, and complete it again with the new hash.")
    elif w.get("kind") == "reviewer":
        write = (f"You are read-only: never edit files. Review tasks ('Review #N', 'Arbitrate #N') are assigned to "
                 f"you: inspect the commit (`git -C <worktree> show <commit>`), run the tests against that worktree, "
                 f"and for non-trivial work have the agent-arena-mode:agent-arena-judge subagent score it against the "
                 f"task. Then call verdict(review task id, pass|fail, score 0-100, notes). Pass needs score >= "
                 f"{b['gate_score']}. Notes must say exactly what to fix.")
    else:
        write = ("You are read-only: do not edit files. Post work for others with post_task (assignee = worker "
                 "name); use gate 0 only for coordination tasks that need no review.")
    return f"""You are War Room worker "{w['name']}" (Specialist Council role: {w['role']}) in run {run}.
Run goal: {resolved['goal']}
Your brief: {w['brief'] or 'Take tasks from the board that fit your role.'}
Protocol:
- Coordinate only through the bus MCP tools (mcp__bus__*). Start with claim_task.
- For each task: do the work, complete_task with a concise result, then checkpoint (done / next / open questions).
- Hand-offs and findings go to other workers with send(to, body). Other workers: {roster}. The human orchestrator is "orchestrator".
- When claim_task returns no task, stop. You are woken automatically when a message or a task arrives.
- If claim_task reports paused, checkpoint at once and stop (usage-limit guard).
- Never push, publish, delete branches or tags, or spend money. Ask the orchestrator with send() instead.
- Shell commands run unattended against an allow-list: run them from your working directory, one command per call,
  with no `cd`, `&&`, `;` or pipes (e.g. `python -m unittest discover -s tests`, `git -C <path> diff`).
  A denied command is final: report it with send() to the orchestrator instead of retrying variants.
- {write}"""


def worker_files(rdir, w, run):
    wdir = os.path.join(rdir, "workers", w["name"])
    py = sys.executable.replace("\\", "/")
    hooks = os.path.join(HERE, "hooks.py").replace("\\", "/")
    env = {"WARROOM_DB": os.path.join(rdir, "bus.sqlite3").replace("\\", "/"), "WARROOM_AGENT": w["name"],
           "WARROOM_RUN": run, "WARROOM_WAIT": str(w.get("wait_seconds", 570)), "CLAUDE_CODE_STOP_HOOK_BLOCK_CAP": "50"}

    def hook(event, timeout=30):
        return [{"hooks": [{"type": "command", "command": f'"{py}" "{hooks}" {event}', "timeout": timeout}]}]

    settings = {"env": env,
                "permissions": {"allow": w["allow"], "deny": w["deny"]},
                "statusLine": {"type": "command", "command": f'"{py}" "{hooks}" statusline'},
                "hooks": {"Stop": hook("stop", int(w.get("wait_seconds", 570)) + 60), "PostToolUse": hook("posttool"),
                          "SessionStart": hook("sessionstart")}}
    servers = {"bus": {"command": py, "args": [os.path.join(HERE, "bus.py").replace("\\", "/")], "env": env}}
    all_mcp = user_mcp_servers()
    servers.update({m: all_mcp[m] for m in w["mcp"]})
    save_json(os.path.join(wdir, "settings.json"), settings)
    save_json(os.path.join(wdir, "mcp.json"), {"mcpServers": servers})
    return wdir


def run_tag(run):
    return hashlib.sha256(run.encode()).hexdigest()[:6]


def worktree_name(run, w):
    return f"wr-{run_tag(run)}-{w['name']}"


def build_argv(w, resolved, run, wdir):
    argv = ["--bg", "--model", w["model"], "--effort", w["effort"], "-n", f"wr-{w['name']}",
            "--permission-mode", w["permission_mode"], "--setting-sources", "project,local",
            "--strict-mcp-config", "--mcp-config", os.path.join(wdir, "mcp.json"),
            "--settings", os.path.join(wdir, "settings.json"),
            "--append-system-prompt", protocol_prompt(w, resolved, run)]
    for d in w["plugin_dirs"]:
        argv += ["--plugin-dir", d]
    if w["write"]:
        argv += ["--worktree", worktree_name(run, w)]
    else:  # readers may inspect writers' worktrees
        argv += ["--add-dir", resolved.get("worktrees") or os.path.join(resolved["project"], ".claude", "worktrees")]
    return argv + ["--", "Begin: call claim_task."]  # '--': variadic flags like --add-dir would swallow the prompt


def resume_argv(argv, session_id, prompt):
    """Launch flags are not restored by --resume, so replay them: drop --worktree (it exists) and the old prompt."""
    out, skip = [], False
    for a in argv[:-1]:
        if skip:
            skip = False
            continue
        if a == "--worktree":
            skip = True
            continue
        if a != "--":
            out.append(a)
    return out + ["--resume", session_id, "--", prompt]


def start_session(argv, cwd):
    code, out = claude(*argv, cwd=cwd)
    short = parse_bg_id(out)
    if not short:
        raise RuntimeError(f"claude --bg failed: {out.strip()[-400:]}")
    for _ in range(40):  # wait until `claude agents` knows the full id
        s = next((s for s in sessions(0) if s.get("sessionId", "").startswith(short)), None)
        if s:
            return s
        time.sleep(0.5)
    raise RuntimeError(f"session {short} never appeared in `claude agents`")


def cmd_launch(a):
    if not (load_json(CONFIG, {}) or {}).get("enabled"):
        die("war mode is off. Turn it on with: python warroom.py toggle on")
    rdir = run_dir(a.run)
    resolved = load_json(os.path.join(rdir, "plan.json"))
    if a.confirm != confirm_code(resolved):
        die("confirmation code does not match this plan; re-run `warroom.py plan` and read the preview")
    bus = open_bus(a.run)
    if bus.workers() or bus.db.execute("INSERT OR IGNORE INTO control VALUES ('launching', ?)", (str(os.getpid()),)).rowcount == 0:
        die("run already launched (or launching); use resume or wake")
    bus.control("worktrees", resolved["worktrees"])
    bus.control("started", time.time())
    bus.control("run_id", a.run)
    bus.control("project", resolved["project"])
    bus.control("budget", json.dumps(resolved["budget"]))
    for t in resolved["tasks"]:
        bus.post_task(t["title"], t.get("detail", ""), t.get("assignee"), t.get("gate", 1))
    for w in resolved["workers"]:
        w["wait_seconds"] = resolved["budget"]["wait_seconds"]
        wdir = worker_files(rdir, w, a.run)
        argv = build_argv(w, resolved, a.run, wdir)
        s = start_session(argv, resolved["project"])
        # A writer runs in its own worktree; record that folder so restarts and transcript lookups land there.
        cwd = os.path.join(resolved["worktrees"], worktree_name(a.run, w)) if w["write"] else resolved["project"]
        bus.put_worker(name=w["name"], role=w["role"], kind=w["kind"], model=w["model"], effort=w["effort"],
                       session_id=s["sessionId"], cwd=cwd, argv=json.dumps(argv),
                       resume_argv=None, state="running")
        bus.event("launch", f"{w['name']} {s['sessionId'][:8]} {w['model']}/{w['effort']}")
        print(f"launched {w['name']:<14} {s['sessionId'][:8]}  {w['model']}/{w['effort']}  plugins={len(w['plugin_dirs'])}")
    setup_integration(bus, resolved, a.run, base=writer_base(bus))
    if not a.no_console:
        bus.control("daemons", json.dumps({"watch": spawn_daemon(a.run, "watch")}))
        url = ensure_hub() + f"run/{a.run}"
        tile(bus)
        if not a.from_app:
            open_app(url)
        place_app(bus, a.run)
    print(f"\nrun {a.run} launched: the conductor runs in the background; the War Room app shows it.\n"
          f"Panic stop: python warroom.py stop {a.run}    Close everything: python warroom.py shutdown {a.run}")


def place_app(bus, run, wait=20):
    """Once the app window shows this run (its title), lay it out next to the consoles."""
    if not IS_WIN:
        return
    for _ in range(wait * 2):
        if top_windows(app_title(run)):
            return tile(bus, spawn=False)
        time.sleep(0.5)


def git(*args, cwd):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")


def writer_base(bus, timeout=30):
    """The commit writers' worktrees start from. `claude --worktree` branches from the default branch, which can be
    ahead of the project checkout, so the integration branch must start there too or it would absorb those commits."""
    deadline = time.time() + timeout
    for w in (w for w in bus.workers() if w["kind"] == "builder"):
        while time.time() < deadline:
            r = git("rev-parse", "HEAD", cwd=w["cwd"]) if os.path.isdir(w["cwd"]) else None
            if r is not None and r.returncode == 0:
                return r.stdout.strip()
            time.sleep(1)
    return None


def setup_integration(bus, resolved, run, base=None):
    """Per-run integration branch in its own worktree; the conductor merges approved commits into it."""
    head = git("rev-parse", base or "HEAD", cwd=resolved["project"])
    if head.returncode:
        bus.event("merge", "project is not a git repository: review gates without a merge queue")
        return None
    branch, path = f"war-room/{run}", os.path.join(resolved["worktrees"], f"wr-{run_tag(run)}-integration")
    r = git("worktree", "add", "-b", branch, path, head.stdout.strip(), cwd=resolved["project"])
    if r.returncode:
        bus.event("merge", f"integration worktree failed: {r.stderr.strip()[-200:]}")
        return None
    integ = {"path": path, "branch": branch, "base": head.stdout.strip()}
    bus.control("integration", json.dumps(integ))
    bus.event("merge", f"integration branch {branch} at {integ['base'][:8]}")
    return integ


def process_merges(bus):
    """Merge approved commits, oldest approval first. A conflict aborts the merge and reopens the task for its author."""
    integ = json.loads(bus.control("integration") or "null")
    if not integ or not os.path.isdir(integ["path"]):
        return 0
    bus.db.execute("UPDATE merges SET status='queued' WHERE status='merging' AND ts < ?", (time.time() - 300,))  # crashed merger
    merged = 0
    for m in bus.db.execute("SELECT * FROM merges WHERE status='queued' ORDER BY id").fetchall():
        if bus.db.execute("UPDATE merges SET status='merging', ts=? WHERE id=? AND status='queued'",
                          (time.time(), m["id"])).rowcount == 0:
            continue  # another merger (conductor, approve, merge) took it
        t = bus._task(m["task_id"])
        if git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=integ["path"]).returncode == 0:
            git("merge", "--abort", cwd=integ["path"])  # left over from a merger that was killed mid-merge
        exists = bool(re.fullmatch(r"[0-9a-f]{40}", m["commit_ref"] or "")) and \
            git("cat-file", "-e", f"{m['commit_ref']}^{{commit}}", cwd=integ["path"]).returncode == 0
        r = git("merge", "--no-ff", "-m", f"War Room: task #{t['id']} {t['title']} ({m['worker']})", m["commit_ref"],
                cwd=integ["path"]) if exists else None
        if r is not None and r.returncode != 0 and not git("diff", "--name-only", "--diff-filter=U", cwd=integ["path"]).stdout.strip():
            git("merge", "--abort", cwd=integ["path"])  # not a conflict (index.lock, I/O, ...): try again next tick
            bus.db.execute("UPDATE merges SET status='queued', detail=? WHERE id=?", ((r.stdout + r.stderr).strip()[-300:], m["id"]))
            bus.event("merge", f"#{t['id']} merge deferred: {(r.stdout + r.stderr).strip()[-120:]}")
            continue
        if r is not None and r.returncode == 0:
            head = git("rev-parse", "HEAD", cwd=integ["path"]).stdout.strip()
            bus.db.execute("UPDATE merges SET status='merged', detail=?, ts=? WHERE id=?", (head, time.time(), m["id"]))
            bus.db.execute("UPDATE tasks SET status='merged', updated=? WHERE id=?", (time.time(), t["id"]))
            bus.event("merge", f"#{t['id']} {m['commit_ref'][:8]} merged into {integ['branch']} ({head[:8]})")
            merged += 1
            continue
        if r is not None:
            git("merge", "--abort", cwd=integ["path"])
        why = "commit not found" if r is None else (r.stdout + r.stderr).strip()[-300:]
        bus.db.execute("UPDATE merges SET status='conflict', detail=?, ts=? WHERE id=?", (why, time.time(), m["id"]))
        bus.db.execute("UPDATE tasks SET status='open', owner=NULL, assignee=?, updated=? WHERE id=?",
                       (t["author"], time.time(), t["id"]))
        bus.agent, sender = "conductor", bus.agent
        bus.send(t["author"], f"Task #{t['id']} could not merge into {integ['branch']} ({why[:160]}). In your worktree run "
                              f"`git merge {integ['branch']}`, resolve, commit, and complete the task again with the new hash.")
        bus.agent = sender
        bus.event("merge-conflict", f"#{t['id']} {m['commit_ref'][:8]}: {why[:120]}")
    return merged


# ---------------------------------------------------------------- restart / wake / resume / stop
def stop_session(session_id, timeout=40):
    s = session_of(session_id)
    if not sessions_ok():
        return False  # cannot see sessions right now: never report "stopped" on a guess
    if s and s.get("status"):
        claude("stop", session_id[:8])
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = session_of(session_id)
        if sessions_ok() and (not s or (not s.get("status") and not pid_alive(s.get("pid")))):
            return True
        time.sleep(1)
    return False


def transcript_path(cwd, session_id):
    slug = re.sub(r"[^A-Za-z0-9]", "-", cwd)
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", slug, f"{session_id}.jsonl")


def restart(bus, w, prompt):
    """Stop (if needed), wait for the process to exit, then resume with the stored launch flags.
    A worker that never finished a turn has no conversation to resume: relaunch it fresh instead."""
    if not stop_session(w["session_id"]):
        raise RuntimeError(f"{w['name']}: session did not stop in time")
    argv = resume_argv(json.loads(w["argv"]), w["session_id"], prompt)
    if not os.path.exists(transcript_path(w["cwd"], w["session_id"])):
        argv = argv[:argv.index("--resume")] + ["--", json.loads(w["argv"])[-1]]
        bus.event("relaunch", f"{w['name']} had no conversation yet: fresh start")
    s = start_session(argv, w["cwd"])
    time.sleep(6)
    if not (session_of(s["sessionId"]) or {}).get("status"):
        raise RuntimeError(f"{w['name']}: restarted session {s['sessionId'][:8]} exited at once")
    if s["sessionId"] != w["session_id"]:
        bus.event("fork", f"{w['name']} resumed as copy {s['sessionId'][:8]}")
    bus.update_worker(w["name"], session_id=s["sessionId"], state="running", resume_argv=json.dumps(argv))
    bus.event("resume", f"{w['name']} {s['sessionId'][:8]}")
    if IS_WIN and bus.control("tiles"):
        tile(bus)  # the old attach console closed with the old process: put the new session back in the grid
    return s


def worker(bus, name):
    w = next((w for w in bus.workers() if w["name"] == name), None)
    return w or die(f"no worker {name!r}")


def heartbeat(bus, name):
    row = bus.db.execute("SELECT ts, note FROM heartbeats WHERE agent=?", (name,)).fetchone()
    return (row["note"], time.time() - row["ts"]) if row else ("", 1e9)


def is_parked(bus, w):
    note, _ = heartbeat(bus, w["name"])
    s = session_of(w["session_id"])
    return note.startswith("parked") and bool(s and s.get("status"))


def cmd_send(a):
    bus = open_bus(a.run)
    worker(bus, a.worker)
    bus.send(a.worker, a.message)
    print(f"sent to {a.worker}")


def cmd_wake(a):
    bus = open_bus(a.run)
    w = worker(bus, a.worker)
    if a.message:
        bus.send(a.worker, a.message)
    if is_parked(bus, w):
        print(f"{a.worker} is parked in its Stop hook: the inbox wakes it within ~2 s")
        return
    s = restart(bus, w, WAKE_PROMPT)
    print(f"{a.worker} was idle; restarted as {s['sessionId'][:8]} (conversation resumed when one existed)")


def resume_all(bus, names=None):
    """Restart every (or the named) worker with its conversation; one failure does not stop the others."""
    failed = []
    for w in bus.workers():
        if names and w["name"] not in names:
            continue
        try:
            s = restart(bus, w, RESUME_PROMPT)
            print(f"resumed {w['name']:<14} {s['sessionId'][:8]}")
        except Exception as e:
            failed.append(w["name"])
            bus.event("conductor-error", f"resume {w['name']}: {str(e)[:200]}")
            print(f"resume {w['name']} FAILED: {e}")
    return failed


def cmd_resume(a):
    bus = open_bus(a.run)
    bus.control("run", clear=True)
    resume_all(bus, a.workers)


def stop_all(bus, reason):
    bus.control("run", "stop")  # releases workers parked in their Stop hook
    bus.event("stop", reason)
    for w in bus.workers():
        ok = stop_session(w["session_id"])
        bus.update_worker(w["name"], state="stopped" if ok else "stop-failed")
        print(f"stopped {w['name']:<14} {'ok' if ok else 'TIMEOUT'}")


def cmd_stop(a):
    stop_all(open_bus(a.run), "panic stop by orchestrator")


def cmd_pause(a, on=True):
    bus = open_bus(a.run)
    bus.control("claims", "paused" if on else None, clear=not on)
    bus.control("paused_by", "orchestrator" if on else None, clear=not on)
    bus.event("pause" if on else "unpause", "orchestrator")
    print("claims paused" if on else "claims open")


def cmd_post(a):
    print(open_bus(a.run).post_task(a.title, a.detail or "", a.to))


# ---------------------------------------------------------------- watch: usage guard, auto-wake, watchdog
def decide(five_pct, budget, paused, stopped, limit_hit, paused_by_guard=True):
    """Usage guard policy. Returns 'stop', 'pause', 'unpause' or None. Only a guard pause is lifted automatically."""
    if stopped:
        return None
    if limit_hit or (five_pct is not None and five_pct >= budget["stop_at"]):
        return "stop"
    if five_pct is not None and five_pct >= budget["pause_at"] and not paused:
        return "pause"
    if paused and paused_by_guard and five_pct is not None and five_pct < budget["pause_at"] - 10:
        return "unpause"
    return None


LIMIT_RE = re.compile(r"You've hit your (session|weekly|Opus|Sonnet|Fable)? ?limit")


def limit_in_transcript(path, after=0):
    """True when a usage-limit message appears in the transcript after byte offset `after` (last 64 KB scanned)."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(after, size - 65536, 0))
            return bool(LIMIT_RE.search(f.read().decode("utf-8", "replace")))
    except OSError:
        return False


def schedule_resume(run, when):
    """Register a one-shot OS task that resumes the run, so a reset survives a dead conductor or a reboot."""
    script = os.path.join(HERE, "warroom.py")
    at = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(when))
    if IS_WIN:
        q = lambda s: "'" + str(s).replace("'", "''") + "'"  # noqa: E731  PowerShell single-quoted literal
        ps = (f"Register-ScheduledTask -TaskName {q('WarRoom-' + run)} -Force "
              f"-Trigger (New-ScheduledTaskTrigger -Once -At {q(at)}) "
              f"-Action (New-ScheduledTaskAction -Execute {q(sys.executable)} -Argument {q(subprocess.list2cmdline([script, 'resume', run]))})")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    else:
        job = " ".join(shlex.quote(x) for x in (sys.executable, script, "resume", run))
        r = subprocess.run(["at", "-t", time.strftime("%Y%m%d%H%M", time.localtime(when))], input=job.encode(),
                           capture_output=True)
    return at, r.returncode == 0


def watch_tick(bus, run, schedule, last_wake):
    if bus.control("finished"):
        return "finished"
    budget = json.loads(bus.control("budget") or "{}") or {"pause_at": 85, "stop_at": 95, "max_hours": 4}
    rows = bus.db.execute("SELECT * FROM meter WHERE ts > ?", (time.time() - 900,)).fetchall()
    five = max((r["five_pct"] for r in rows if r["five_pct"] is not None), default=None)
    reset = max((r["five_reset"] for r in rows if r["five_reset"]), default=None)
    seen = json.loads(bus.control("limit_offsets") or "{}")
    limit_hit = any(limit_in_transcript(r["transcript"], seen.get(r["transcript"], 0)) for r in rows if r["transcript"])
    stopped = bus.control("run") == "stop"
    action = decide(five, budget, bus.control("claims") == "paused", stopped, limit_hit,
                    paused_by_guard=bus.control("paused_by") == "guard")
    started = float(bus.control("started") or time.time())
    if not stopped and time.time() - started > budget["max_hours"] * 3600:
        stop_all(bus, f"max_hours={budget['max_hours']} reached")
        return "max hours reached: stopped"
    if action == "pause":
        bus.control("claims", "paused")
        bus.control("paused_by", "guard")
        bus.event("guard", f"5-hour window at {five}%: claims paused")
    elif action == "unpause":
        bus.control("claims", clear=True)
        bus.event("guard", f"5-hour window at {five}%: claims reopened")
    elif action == "stop":
        stop_all(bus, f"usage guard: 5-hour {five}%{' (limit hit)' if limit_hit else ''}")
        offsets = {r["transcript"]: os.path.getsize(r["transcript"]) for r in rows
                   if r["transcript"] and os.path.exists(r["transcript"])}
        bus.control("limit_offsets", json.dumps(offsets))  # old limit messages never trigger a stop again
        when = (reset or time.time() + 3600) + 120
        bus.control("resume_at", when)
        if schedule:
            at, ok = schedule_resume(run, when)
            bus.event("guard", f"resume scheduled with the OS for {at}" if ok else "OS resume task could not be registered")
    resume_at = bus.control("resume_at")
    if stopped and resume_at and time.time() >= float(resume_at):
        bus.control("run", clear=True)  # lets the resumed workers' Stop hooks park again
        failed = resume_all(bus)
        bus.control("resume_at", clear=True)
        bus.control("claims", clear=True)
        bus.event("guard", "usage window reset: run resumed" + (f" ({', '.join(failed)} failed)" if failed else ""))
    sessions(0)
    if not stopped and sessions_ok():  # auto-wake idle workers with work waiting (never on a failed listing); watchdog
        paused = bus.control("claims") == "paused"
        for w in bus.workers():
            s = session_of(w["session_id"])
            note, age = heartbeat(bus, w["name"])
            waiting = bus.unread(w["name"]) or (not paused and bus.open_tasks(w["name"]))
            gone = not s or not s.get("status")                       # process ended (crash or external stop)
            timed_out = note.startswith("idle") and s and s.get("status") == "idle"  # keep-alive wait expired
            settled = time.time() - (w["updated"] or 0) > 120          # never during launch or a fresh resume
            if waiting and settled and (gone or timed_out) and time.time() - last_wake.get(w["name"], 0) > 300:
                last_wake[w["name"]] = time.time()
                bus.event("auto-wake", w["name"])
                try:
                    restart(bus, w, WAKE_PROMPT)
                except Exception as e:
                    bus.event("conductor-error", f"auto-wake {w['name']}: {str(e)[:200]}")
            elif note.startswith("working") and age > 1200:
                bus.event("watchdog", f"{w['name']} silent for {int(age / 60)} min while working")
    merged = process_merges(bus) if not stopped else 0
    if not stopped and budget.get("auto_finish", True):
        if is_complete(bus):
            since = float(bus.control("complete_since") or 0) or time.time()
            bus.control("complete_since", since)
            if time.time() - since > 90:  # stable for 90 s: no worker is about to post more work
                finish(run, "all work merged")
                return "finished"
        else:
            bus.control("complete_since", clear=True)
    if IS_WIN and not stopped and bus.control("tiles"):
        tile(bus, only_missing=True)  # self-heal: a worker whose console never appeared or was closed gets one
    line = f"5h={five}% paused={bus.control('claims') == 'paused'} stopped={bus.control('run') == 'stop'} merged={merged}"
    bus.heartbeat(line)  # the dashboard shows the conductor's pulse from this
    return line


def cmd_watch(a):
    bus, last_wake = open_bus(a.run, "conductor"), {}
    print(f"War Room conductor watching {a.run} (Ctrl+C to leave; workers keep running)")
    while True:
        try:
            line = watch_tick(bus, a.run, a.schedule, last_wake)
        except Exception as e:  # keep watching; record the failure
            bus.event("conductor-error", str(e)[:300])
            line = f"error: {e}"
        print(time.strftime("%H:%M:%S"), line, flush=True)
        if a.once or line == "finished":
            return
        time.sleep(a.interval)


# ---------------------------------------------------------------- daemons and the dashboard app window
def spawn_daemon(run, role):
    """Run the conductor (watch) or dashboard (serve) in the background, without a console window."""
    log = open(os.path.join(run_dir(run), f"{role}.log"), "a", encoding="utf-8")
    kw = {"creationflags": 0x08000000 | 0x00000200} if IS_WIN else {"start_new_session": True}  # NO_WINDOW | NEW_GROUP
    p = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "warroom.py"), role, run], stdout=log,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
    return p.pid


def kill_pid(pid, must_contain="warroom.py"):
    """Kill one of War Room's own background processes; a reused pid that belongs to something else is left alone."""
    if not pid or pid == os.getpid() or not pid_alive(pid) or must_contain not in pid_cmdline(pid):
        return
    if IS_WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def app_browser():
    """A Chromium browser that supports --app (a chromeless window that looks like a desktop app)."""
    if IS_WIN:
        roots = [os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        rel = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
               r"BraveSoftware\Brave-Browser\Application\brave.exe"]
        cands = [os.path.join(r, x) for x in rel for r in roots if r]
    elif sys.platform == "darwin":
        cands = [f"/Applications/{a}.app/Contents/MacOS/{a}" for a in ("Google Chrome", "Microsoft Edge", "Chromium", "Brave Browser")]
    else:
        cands = [shutil.which(x) or "" for x in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "brave-browser")]
    return next((c for c in cands if c and os.path.isfile(c)), None)


def open_app(url):
    exe = app_browser()
    if not exe:
        webbrowser.open(url)
        return None
    profile = os.path.join(HOME, "app-profile")  # separate profile: its own process, no tabs, no sign-in prompts
    return subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run",
                             "--no-default-browser-check", "--disable-features=Translate", "--window-size=1400,900"])


def top_windows(prefix):
    """Visible top-level windows whose title starts with prefix (Windows only)."""
    import ctypes
    from ctypes import wintypes
    user32, found = ctypes.windll.user32, []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        if buf.value.startswith(prefix) and user32.IsWindowVisible(h):
            found.append(h)
        return True
    user32.EnumWindows(proc(cb), 0)
    return found


def app_title(run):
    return f"War Room \u00b7 {run}"


def layout(n, area, has_app):
    """Dashboard app on the left 56% of the screen, worker consoles gridded on the right (or everywhere)."""
    x, y, w, h = area
    if not has_app:
        return None, grid(n, area)
    if n == 0:
        return area, []
    aw = int(w * 0.56)
    return (x, y, aw, h), grid(n, (x + aw, y, w - aw, h))


def tmux_plan(session, attach_ids, exists):
    """tmux commands that put one `claude attach` pane per worker into a tiled session (macOS / Linux)."""
    cmds, ids = [], list(attach_ids)
    if not exists and ids:
        cmds.append(["tmux", "new-session", "-d", "-s", session, "-x", "240", "-y", "64", f"claude attach {ids.pop(0)}"])
    for i in ids:
        cmds.append(["tmux", "split-window", "-t", session, f"claude attach {i}"])
        cmds.append(["tmux", "select-layout", "-t", session, "tiled"])
    return cmds


def open_terminal(cmd):
    """Open a terminal window running cmd (macOS Terminal, or the first Linux terminal found)."""
    if sys.platform == "darwin":
        script = f'tell application "Terminal" to do script "{cmd}"'
        return subprocess.Popen(["osascript", "-e", script, "-e", 'tell application "Terminal" to activate'])
    for term, flag in (("x-terminal-emulator", "-e"), ("gnome-terminal", "--"), ("konsole", "-e"), ("xterm", "-e")):
        if shutil.which(term):
            return subprocess.Popen([term, flag, *cmd.split()])
    print("open a terminal and run:", cmd)


def tile_tmux(bus, live, spawn):
    session = f"wr-{bus.control('run_id') or 'run'}"[-30:]
    if not shutil.which("tmux"):
        for w in live:
            print(f"(no tmux) run in a terminal: claude attach {w['session_id'][:8]}")
        return
    tiles = json.loads(bus.control("tiles") or '{"extra": [], "workers": {}}')
    exists = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True).returncode == 0
    todo = [w for w in live if tiles["workers"].get(w["name"], {}).get("session") != w["session_id"]] if spawn else []
    for c in tmux_plan(session, [w["session_id"][:8] for w in todo], exists):
        subprocess.run(c, capture_output=True)
    for w in todo:
        tiles["workers"][w["name"]] = {"hwnd": 0, "session": w["session_id"]}
    bus.control("tiles", json.dumps(tiles))
    if todo and not exists:
        open_terminal(f"tmux attach -t {session}")


# ---------------------------------------------------------------- tiling (Windows: one console per worker)
def spawn_console(cmd):
    if IS_WIN:
        return subprocess.Popen(["conhost.exe", *cmd])
    print("run in a terminal:", subprocess.list2cmdline(cmd))


def console_windows():
    import ctypes
    from ctypes import wintypes
    user32, found = ctypes.windll.user32, []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, buf, 64)
        if buf.value == "ConsoleWindowClass" and user32.IsWindowVisible(h):
            found.append(h)
        return True
    user32.EnumWindows(proc(cb), 0)
    return found


def grid(n, area):
    x0, y0, width, height = area
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = max(1, math.ceil(n / cols))
    w, h = width // cols, height // rows
    cells = []
    for i in range(n):
        r, c = divmod(i, cols)
        in_row = min(cols, n - r * cols)  # the last row stretches so the area has no dead cell
        cw = width // in_row
        cells.append((x0 + c * cw, y0 + r * h, cw, h))
    return cells


def tile(bus, extra=(), spawn=True, only_missing=False):
    """Give every live worker an attached console and lay out the dashboard app plus all consoles on the primary
    screen. Console handles are kept in the bus, so a restarted worker (wake, auto-wake, usage-reset resume) gets a
    new console in the layout while consoles that are still open are reused. spawn=False only re-lays out."""
    live = [w for w in bus.workers() if (session_of(w["session_id"]) or {}).get("status")]
    if not IS_WIN:
        return tile_tmux(bus, live, spawn)
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    tiles = json.loads(bus.control("tiles") or '{"extra": [], "workers": {}}')
    tiles["extra"] = list(dict.fromkeys(h for h in tiles["extra"] + list(extra) if user32.IsWindow(h)))

    def has_console(w):
        cur = tiles["workers"].get(w["name"])
        return cur and cur["session"] == w["session_id"] and user32.IsWindow(cur["hwnd"])
    missing = [w for w in live if not has_console(w)]
    if only_missing and not missing:
        return  # nothing to fix: leave the user's window arrangement alone
    for w in (missing if spawn else []):
        before = set(console_windows())
        spawn_console([claude_bin(), "attach", w["session_id"][:8]])
        for _ in range(40):  # one console at a time, so each new window maps to its worker
            time.sleep(0.5)
            new = [h for h in console_windows() if h not in before]
            if new:
                tiles["workers"][w["name"]] = {"hwnd": new[0], "session": w["session_id"]}
                break
    wins = [t["hwnd"] for t in tiles["workers"].values() if user32.IsWindow(t["hwnd"])] + tiles["extra"]
    work = wintypes.RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)  # SPI_GETWORKAREA: primary screen minus taskbar
    area = (work.left, work.top, work.right - work.left, work.bottom - work.top)
    flags = 0x4000 | 0x0004 | 0x0040  # SWP_ASYNCWINDOWPOS | SWP_NOZORDER | SWP_SHOWWINDOW: a hung window can't block us
    app = top_windows(app_title(bus.control("run_id") or ""))[:1]
    app_cell, cells = layout(len(wins), area, bool(app))
    for h, (x, y, cw, ch) in list(zip(wins, cells)) + ([(app[0], app_cell)] if app else []):
        user32.ShowWindow(h, 9)
        user32.SetWindowPos(h, 0, x, y, cw, ch, flags)
    bus.control("tiles", json.dumps(tiles))
    print(f"laid out {len(wins)} consoles{' and the dashboard' if app else ''} on the primary screen ({area[2]}x{area[3]})")


def cmd_tile(a):
    tile(open_bus(a.run), getattr(a, "extra_hwnds", ()))


# ---------------------------------------------------------------- status and dashboard
def redact(text):
    home = os.path.expanduser("~")
    return (text or "").replace(home, "~").replace(home.replace("\\", "/"), "~")


def state(run):
    bus = open_bus(run)
    now = time.time()
    workers = []
    for w in bus.workers():
        s = session_of(w["session_id"], max_age=3) or {}
        note, age = heartbeat(bus, w["name"])
        m = bus.db.execute("SELECT * FROM meter WHERE agent=?", (w["name"],)).fetchone()
        ck = bus.last_checkpoint(w["name"])["checkpoint"]
        task = bus.claimed_by(w["name"])
        workers.append({"name": w["name"], "role": w["role"], "kind": w["kind"], "model": w["model"],
                        "effort": w["effort"], "session": w["session_id"][:8], "status": s.get("status") or "stopped",
                        "note": note, "hb_age": int(age) if age < 1e8 else None,
                        "context_pct": m["context_pct"] if m else None, "cost_usd": m["cost_usd"] if m else None,
                        "checkpoint": redact(ck["summary"]) if ck else "", "task": task[0]["title"] if task else "",
                        "unread": bus.unread(w["name"])})
    plan_workers = {w["name"]: w for w in (load_json(os.path.join(run_dir(run), "plan.json"), {}) or {}).get("workers", [])}
    for w in workers:
        pw = plan_workers.get(w["name"], {})
        w["plugins"] = [x.split("@")[0] for x in pw.get("plugins", [])]
        w["mcp"] = pw.get("mcp", [])
        w["write"] = pw.get("write", False)
    meter = bus.db.execute("SELECT max(five_pct) f, max(week_pct) w, max(five_reset) r FROM meter WHERE ts > ?",
                           (now - 900,)).fetchone()
    q = lambda sql, n: [dict(r) for r in bus.db.execute(sql, (n,))]  # noqa: E731
    return {"run": run, "now": now, "goal": redact(load_json(os.path.join(run_dir(run), "plan.json"), {}).get("goal", "")),
            "budget": json.loads(bus.control("budget") or "{}"),
            "control": {k: bus.control(k) for k in ("run", "claims", "resume_at", "started", "finished", "complete_since")},
            "integrated": json.loads(bus.control("integrated") or "null"),
            "report": open(os.path.join(run_dir(run), "report.md"), encoding="utf-8").read()
            if os.path.exists(os.path.join(run_dir(run), "report.md")) else None,
            "meter": {"five": meter["f"], "week": meter["w"], "reset": meter["r"]},
            "workers": workers,
            "tasks": [dict(r) | {"result": redact(r["result"])} for r in bus.db.execute(
                "SELECT id, title, kind, parent, status, owner, assignee, author, commit_ref, score, fails, result "
                "FROM tasks ORDER BY id")],
            "merges": [dict(r) | {"detail": redact(r["detail"])} for r in bus.db.execute(
                "SELECT id, task_id, worker, commit_ref, status, detail, ts FROM merges ORDER BY id")],
            "integration": {k: redact(v) for k, v in (json.loads(bus.control("integration") or "null") or {}).items()},
            "conductor": dict(zip(("note", "age"), heartbeat(bus, "conductor"))),
            "messages": [m | {"body": redact(m["body"])} for m in q(
                "SELECT id, sender, recipient, body, sent, read FROM messages ORDER BY id DESC LIMIT ?", 80)][::-1],
            "events": [e | {"detail": redact(e["detail"])} for e in q(
                "SELECT ts, agent, kind, detail FROM events ORDER BY id DESC LIMIT ?", 200)][::-1]}


def cmd_status(a):
    st = state(a.run)
    if a.json:
        print(json.dumps(st, indent=1))
        return
    print(f"run {st['run']}  5h={st['meter']['five']}%  7d={st['meter']['week']}%  claims={st['control']['claims'] or 'open'}"
          f"  run={st['control']['run'] or 'live'}")
    for w in st["workers"]:
        print(f"  {w['name']:<12}{w['session']:<10}{w['status']:<9}{w['model']:<20}{w['note'][:34]:<36}"
              f"unread={w['unread']} task={w['task'][:30]}")
    for t in st["tasks"]:
        print(f"  #{t['id']:<3}{t['status']:<8}{(t['owner'] or t['assignee'] or '-'):<12}{t['title'][:50]}  {(t['result'] or '')[:40]}")
    for e in st["events"][-8:]:
        print(f"  {time.strftime('%H:%M:%S', time.localtime(e['ts']))} {e['agent']:<12}{e['kind']:<11}{e['detail'][:70]}")


def runs_summary():
    """Every run on this machine, newest first, with what the home screen needs (planned runs carry their preview)."""
    out, per_task = [], per_worker_task(load_json(CALIBRATION, {}))[0]
    for run in sorted(os.listdir(RUNS) if os.path.isdir(RUNS) else [], reverse=True):
        rdir, plan = os.path.join(RUNS, run), load_json(os.path.join(RUNS, run, "plan.json"), None)
        if not plan:
            continue
        item = {"run": run, "goal": redact(plan.get("goal", "")), "project": redact(plan.get("project", "")),
                "workers": [{k: w[k] for k in ("name", "role", "kind", "model", "effort", "write", "mcp")}
                            | {"plugins": [x.split("@")[0] for x in w["plugins"]]} for w in plan["workers"]],
                "budget": plan.get("budget", {})}
        db = os.path.join(rdir, "bus.sqlite3")
        bus = Bus(db, "hub") if os.path.exists(db) else None
        launched = bool(bus and bus.workers())
        if not launched:
            lo, hi = estimate(plan["workers"], len(plan.get("tasks", [])), per_task)
            item.update(status="planned", estimate=[lo, hi], confirm=confirm_code(plan), tasks=len(plan.get("tasks", [])))
        else:
            c = {k: bus.control(k) for k in ("finished", "run", "started", "integrated")}
            n = bus.db.execute("SELECT COUNT(*), SUM(status IN ('merged','done')) FROM tasks WHERE kind='work'").fetchone()
            item.update(status="finished" if c["finished"] else "stopped" if c["run"] == "stop" else "live",
                        started=float(c["started"] or 0), tasks=n[0], finished_tasks=n[1] or 0,
                        integrated=bool(c["integrated"]))
        out.append(item)
    return out


def hub_url():
    h = load_json(HUB, None)
    if not h or not pid_alive(h.get("pid")):
        return None
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{h['port']}/api/ping", timeout=2).read()
        return f"http://127.0.0.1:{h['port']}/"
    except OSError:
        return None


def ensure_hub():
    """Start the War Room hub in the background unless it is already running; return its URL."""
    url = hub_url()
    if url:
        return url
    log = open(os.path.join(HOME, "hub.log"), "a", encoding="utf-8")
    kw = {"creationflags": 0x08000000 | 0x00000200} if IS_WIN else {"start_new_session": True}
    subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "warroom.py"), "hub"], stdout=log, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, **kw)
    for _ in range(40):
        time.sleep(0.25)
        url = hub_url()
        if url:
            return url
    die("the War Room hub did not start (see ~/.claude/war-room/hub.log)")


def cmd_app(a):
    if a.quit:
        h = load_json(HUB, None)
        kill_pid((h or {}).get("pid"))
        print("hub stopped")
        return
    url = ensure_hub() + (f"run/{a.run}" if a.run else "")
    open_app(url)
    print(f"War Room app: {url}")


def cmd_serve(a):  # kept for compatibility: the hub now serves every run
    cmd_app(argparse.Namespace(run=a.run, quit=False))


def cmd_hub(a):
    """One local server for the War Room app: home (war mode, settings, runs) and every run's live view."""
    os.makedirs(HOME, exist_ok=True)
    token = secrets.token_urlsafe(16)
    pages = {name: open(os.path.join(HERE, name), encoding="utf-8").read().replace("__TOKEN__", token)
             for name in ("home.html", "dashboard.html")}
    fonts = os.path.join(HERE, "assets", "fonts")
    run_re = re.compile(r"^/(?:api/)?run/([A-Za-z0-9-]{1,80})(/.*)?$")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, body, ctype="application/json"):
            body = body if isinstance(body, (bytes, str)) else json.dumps(body)
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else body.encode())

        def body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 65536:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def host_ok(self):
            # Only the hub's own origin: a DNS-rebound page carries a foreign Host header.
            port = self.server.server_address[1]
            return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def do_GET(self):
            if not self.host_ok():
                return self.send(403, {"error": "forbidden host"})
            path = self.path.split("?")[0]
            m = run_re.match(path)
            if path == "/api/ping":
                return self.send(200, {"ok": True})
            if path == "/":
                return self.send(200, pages["home.html"], "text/html; charset=utf-8")
            if path == "/api/home":
                cfg = load_json(CONFIG, {}) or {}
                return self.send(200, {"war_mode": bool(cfg.get("enabled")), "settings": settings(),
                                       "defaults": HARD_DEFAULTS, "limits": SETTING_LIMITS, "runs": runs_summary(),
                                       "meter": last_meter(), "warning": WARNING, "now": time.time(),
                                       "calibration": dict(zip(("per_worker_task", "runs"),
                                                               per_worker_task(load_json(CALIBRATION, {}))))})
            if m and not path.startswith("/api/") and os.path.isdir(os.path.join(RUNS, m.group(1))):
                page = pages["dashboard.html"].replace("__TITLE__", app_title(m.group(1))).replace("__RUN__", m.group(1))
                return self.send(200, page, "text/html; charset=utf-8")
            if m and m.group(2) == "/state":
                return self.send(200, state(m.group(1)))
            if path.startswith("/fonts/") and re.match(r"^/fonts/[\w.-]+\.woff2$", path):
                f = os.path.join(fonts, path[7:])
                return self.send(200, open(f, "rb").read(), "font/woff2") if os.path.exists(f) else self.send(404, "")
            self.send(404, {"error": "not found"})

        def do_POST(self):
            # Same-origin pages only: the token is embedded in the served page, never in a URL.
            if not self.host_ok() or not hmac.compare_digest(self.headers.get("X-War-Room-Token", ""), token):
                return self.send(403, {"error": "forbidden"})
            try:
                path, data = self.path.split("?")[0], self.body()
                if path == "/api/toggle":
                    cfg = load_json(CONFIG, {}) or {}
                    cfg["enabled"] = bool(data.get("on"))
                    save_json(CONFIG, cfg)
                    return self.send(200, {"war_mode": cfg["enabled"]})
                if path == "/api/settings":
                    cfg = load_json(CONFIG, {}) or {}
                    cfg["defaults"] = {} if data.get("reset") else {**(cfg.get("defaults") or {}),
                                                                   **validate_settings(data.get("settings") or {})}
                    save_json(CONFIG, cfg)
                    return self.send(200, {"settings": settings()})
                m = run_re.match(path)
                if not m or not os.path.isdir(os.path.join(RUNS, m.group(1))):
                    return self.send(404, {"error": "no such run"})
                run, action = m.group(1), (m.group(2) or "").strip("/")
                if action == "launch":
                    if not (load_json(CONFIG, {}) or {}).get("enabled"):
                        return self.send(409, {"error": "war mode is off"})
                    if data.get("confirm") != confirm_code(load_json(os.path.join(RUNS, run, "plan.json"))):
                        return self.send(409, {"error": "the plan changed since the preview; reload"})
                    kw = {"creationflags": 0x08000000 | 0x00000200} if IS_WIN else {"start_new_session": True}
                    log = open(os.path.join(RUNS, run, "launch.log"), "a", encoding="utf-8")
                    subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "warroom.py"), "launch", run,
                                      "--confirm", data["confirm"], "--from-app"], stdout=log, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, **kw)
                    return self.send(200, {"ok": True, "url": f"/run/{run}"})
                if action == "discard":
                    if os.path.exists(os.path.join(RUNS, run, "bus.sqlite3")):
                        return self.send(409, {"error": "only planned runs that never launched can be discarded"})
                    shutil.rmtree(os.path.join(RUNS, run), ignore_errors=True)
                    return self.send(200, {"ok": True})
                bus = open_bus(run)
                if action == "stop":
                    stop_all(bus, "STOP ALL from the app")
                elif action in ("pause", "unpause"):
                    cmd_pause(argparse.Namespace(run=run), on=action == "pause")
                elif action == "integrate":
                    out = integrate_into_project(bus)
                    return self.send(200 if out["ok"] else 409, out)
                elif action in ("finish", "shutdown"):
                    threading.Thread(target=shutdown, args=(run, f"{action} from the app", False), daemon=True).start()
                elif action == "resume":
                    threading.Thread(target=cmd_resume, args=(argparse.Namespace(run=run, workers=[]),), daemon=True).start()
                else:
                    return self.send(404, {"error": f"unknown action {action}"})
                return self.send(200, {"ok": True})
            except (ValueError, KeyError, TypeError) as e:
                return self.send(400, {"error": str(e)})

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    save_json(HUB, {"pid": os.getpid(), "port": srv.server_address[1], "started": time.time()})
    print(f"War Room hub on http://127.0.0.1:{srv.server_address[1]}/ (127.0.0.1 only)", flush=True)
    srv.serve_forever()


# ---------------------------------------------------------------- gates, merges, integration, measuring, shutdown
def cmd_approve(a):
    bus = open_bus(a.run)
    print(bus.decide(a.task, approve=not a.reject, notes=a.reject or ""))
    process_merges(bus)


def cmd_merge(a):
    print(f"merged {process_merges(open_bus(a.run, 'conductor'))} commit(s)")


def cmd_integrate(a):
    """Show what the integration branch holds; with --apply, merge it into the project's current branch."""
    bus = open_bus(a.run)
    if a.apply:
        print(json.dumps(integrate_into_project(bus), indent=1))
        return
    if bus.control("finished"):
        print(integration_report(bus))
        return
    integ = json.loads(bus.control("integration") or "null") or die("this run has no integration branch")
    log = git("log", "--oneline", f"{integ['base']}..{integ['branch']}", cwd=integ["path"]).stdout.strip()
    stat = git("diff", "--stat", integ["base"], integ["branch"], cwd=integ["path"]).stdout.strip()
    open_ = [t for t in bus.db.execute("SELECT id, title, status FROM tasks WHERE kind='work' AND status NOT IN "
                                       "('done','merged')")]
    print(f"integration branch {integ['branch']} (base {integ['base'][:8]})\n{log or '(no merged commits yet)'}\n\n{stat}")
    if open_:
        print("\nnot merged yet:", ", ".join(f"#{t['id']} {t['status']}" for t in open_))
    print(f"\nWhen the run finishes, War Room removes its sessions and merged worktrees by itself. "
          f"Merge with: warroom.py integrate {a.run} --apply")


def usage_of(run):
    """Tokens actually processed by every session the run used (deduplicated across resumed copies)."""
    bus = open_bus(run)
    shorts = {w["session_id"][:8] for w in bus.workers()}
    for (detail,) in bus.db.execute("SELECT detail FROM events WHERE kind IN ('launch','resume','fork')"):
        shorts.update(re.findall(r"\b[0-9a-f]{8}\b", detail))
    roots = {os.path.join(os.path.expanduser("~"), ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", w["cwd"]))
             for w in bus.workers()}
    seen, tot = set(), {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    for root in roots:
        for short in shorts:
            for path in glob.glob(os.path.join(root, f"{short}*.jsonl")):
                for line in open(path, encoding="utf-8", errors="replace"):
                    try:
                        m = json.loads(line).get("message") or {}
                    except ValueError:
                        continue
                    u = m.get("usage") if isinstance(m, dict) else None
                    if not u or m.get("id") in seen:
                        continue
                    seen.add(m.get("id"))
                    tot["input"] += u.get("input_tokens", 0)
                    tot["cache_write"] += u.get("cache_creation_input_tokens", 0)
                    tot["cache_read"] += u.get("cache_read_input_tokens", 0)
                    tot["output"] += u.get("output_tokens", 0)
    tot["total"], tot["api_calls"] = sum(tot.values()), len(seen)
    return tot


def measure(run):
    bus = open_bus(run)
    u = usage_of(run)
    n_workers = len(bus.workers())
    finished = bus.db.execute("SELECT COUNT(*) FROM tasks WHERE kind='work' AND status IN ('done','approved','merged')").fetchone()[0]
    rec = dict(u, workers=n_workers, tasks=finished, measured=time.time(),
               per_worker_task=int(u["total"] / max(1, n_workers * max(1, finished))) if u["total"] else 0)
    cal = load_json(CALIBRATION, {}) or {"runs": {}}
    cal.setdefault("runs", {})[run] = rec
    save_json(CALIBRATION, cal)
    bus.event("measure", f"{u['total'] / 1e6:.2f}M tokens over {u['api_calls']} calls, {finished} tasks")
    return rec


def cmd_measure(a):
    print(json.dumps(measure(a.run), indent=1))


def run_sessions(bus):
    """Every session id the run used: current workers plus the copies left behind by resumes."""
    ids = [w["session_id"][:8] for w in bus.workers()]
    for (detail,) in bus.db.execute("SELECT detail FROM events WHERE kind IN ('launch','resume','fork') ORDER BY id"):
        ids += [x for x in re.findall(r"\b[0-9a-f]{8}\b", detail) if x not in ids]
    return ids


def project_of(bus):
    return bus.control("project") or (load_json(os.path.join(RUNS, bus.control("run_id") or "", "plan.json"), {}) or {}).get("project")


def is_complete(bus):
    """All work is finished and merged, nothing is open or under review, and every worker is parked or idle."""
    tasks = bus.db.execute("SELECT kind, status FROM tasks").fetchall()
    work = [t for t in tasks if t["kind"] == "work"]
    if not work or any(t["status"] in ("open", "claimed", "review", "blocked") for t in tasks):
        return False
    if any(t["status"] == "approved" for t in work) or bus.db.execute(
            "SELECT COUNT(*) FROM merges WHERE status='queued'").fetchone()[0]:
        return False  # approved work still waiting for the merge queue
    return all(heartbeat(bus, w["name"])[0].startswith(("parked", "idle")) for w in bus.workers())


def integration_report(bus):
    integ = json.loads(bus.control("integration") or "null")
    if not integ:
        return "No integration branch (the project is not a git repository)."
    cwd = project_of(bus) or integ["path"]
    log = git("log", "--oneline", f"{integ['base']}..{integ['branch']}", cwd=cwd).stdout.strip()
    stat = git("diff", "--stat", integ["base"], integ["branch"], cwd=cwd).stdout.strip()
    tasks = [dict(t) for t in bus.db.execute("SELECT id, title, status, score, fails FROM tasks WHERE kind='work'")]
    lines = [f"# War Room run {bus.control('run_id')}", "", f"Integration branch `{integ['branch']}` "
             f"(base {integ['base'][:8]})", "", "## Tasks"]
    lines += [f"- #{t['id']} {t['status']}: {t['title']}" + (f" (review {t['score']:.0f}" if t["score"] is not None else "")
              + (f", {t['fails']} failed review(s))" if t["fails"] else (")" if t["score"] is not None else "")) for t in tasks]
    lines += ["", "## Commits", "```", log or "(none)", "```", "", "## Files", "```", stat or "(none)", "```"]
    return NL.join(lines)


def cleanup_worktrees(bus):
    """Remove writer worktrees (and their branches) whose commits are all in the integration branch, then the
    integration worktree itself (its branch stays for the merge). Anything not fully merged is kept and reported."""
    integ = json.loads(bus.control("integration") or "null")
    kept, removed = [], []
    project = project_of(bus)
    root = bus.control("worktrees") or (load_json(os.path.join(RUNS, bus.control("run_id") or "", "plan.json"), {}) or {}).get("worktrees")
    norm = lambda p: os.path.normcase(os.path.realpath(p))  # noqa: E731
    for w in (w for w in bus.workers() if w["kind"] == "builder"):
        wt = w["cwd"]
        if not os.path.isdir(wt) or not root or norm(wt) == norm(project or "") \
                or not norm(wt).startswith(norm(root) + os.sep):
            continue  # only the run's own worktrees, never the project checkout
        branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=wt).stdout.strip()
        clean = git("status", "--porcelain", cwd=wt).stdout.strip() == ""
        merged = bool(integ) and git("merge-base", "--is-ancestor", "HEAD", integ["branch"], cwd=wt).returncode == 0
        if clean and merged and project:
            git("worktree", "unlock", wt, cwd=project)  # claude --worktree locks the worktrees it creates
            git("worktree", "remove", wt, cwd=project)
            git("branch", "-D", branch, cwd=project)  # safe: every commit on it is in the integration branch
            removed.append(wt)
        else:
            kept.append(f"{wt} ({'uncommitted changes' if not clean else 'commits not merged'})")
            bus.control("kept_" + w["name"], "1")
    if integ and project and os.path.isdir(integ["path"]):
        git("worktree", "unlock", integ["path"], cwd=project)
        git("worktree", "remove", integ["path"], cwd=project)
        removed.append(integ["path"])
        if git("rev-list", "--count", f"{integ['base']}..{integ['branch']}", cwd=project).stdout.strip() == "0":
            git("branch", "-D", integ["branch"], cwd=project)  # nothing was merged: no branch to keep
    return removed, kept


def integrate_into_project(bus):
    """Merge the integration branch into the project's current branch (--no-ff, never pushed). Refuses a dirty tree."""
    integ = json.loads(bus.control("integration") or "null")
    project = project_of(bus)
    if not integ or not project:
        return {"ok": False, "error": "no integration branch"}
    if git("status", "--porcelain", "--untracked-files=no", cwd=project).stdout.strip():
        return {"ok": False, "error": "the project has uncommitted changes; commit or stash them, then integrate"}
    target = git("rev-parse", "--abbrev-ref", "HEAD", cwd=project).stdout.strip()
    r = git("merge", "--no-ff", "-m", f"War Room: integrate run {bus.control('run_id')}", integ["branch"], cwd=project)
    if r.returncode:
        git("merge", "--abort", cwd=project)
        bus.event("integrate", f"merge into {target} failed: {(r.stdout + r.stderr).strip()[-160:]}")
        return {"ok": False, "error": (r.stdout + r.stderr).strip()[-300:]}
    head = git("rev-parse", "HEAD", cwd=project).stdout.strip()
    bus.control("integrated", json.dumps({"target": target, "head": head, "ts": time.time()}))
    bus.event("integrate", f"{integ['branch']} merged into {target} ({head[:8]}); nothing pushed")
    return {"ok": True, "target": target, "head": head}


def finish(run, reason):
    """Close out a run: stop workers, record cost, delete every session the run used (resumed copies included,
    since a stopped session cannot be resumed in place), remove fully merged worktrees, write the report, and
    integrate automatically when the plan asked for it. The dashboard stays up to show the result."""
    bus = open_bus(run)
    if bus.control("finished"):
        return
    stop_all(bus, reason)
    try:
        rec = measure(run)
        print(f"measured {rec['total'] / 1e6:.2f}M tokens ({rec['per_worker_task'] / 1e3:.0f}k per worker-task)")
    except Exception as e:  # measuring is best effort
        print(f"measure failed: {e}")
    report = integration_report(bus)
    with open(os.path.join(run_dir(run), "report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    removed, kept = cleanup_worktrees(bus)  # first: `claude rm` keeps a session while its worktree exists
    removed_sessions = []
    keep = {w["session_id"][:8] for w in bus.workers() if bus.control("kept_" + w["name"])}
    for sid in run_sessions(bus):
        if sid in keep:
            continue  # its worktree holds unmerged or uncommitted work: the session stays with it
        code, out = claude("rm", sid, timeout=60)
        removed_sessions.append(f"{sid}: {out.strip().splitlines()[0] if out.strip() else code}")
    bus.event("finish", f"{reason}; {len(removed_sessions)} sessions removed, {len(removed)} worktrees removed"
                        + (f", kept {len(kept)}" if kept else ""))
    for k in kept:
        bus.event("finish", f"kept worktree {k}")
    bus.control("finished", time.time())
    budget = json.loads(bus.control("budget") or "{}")
    integ = json.loads(bus.control("integration") or "null")
    has_commits = bool(integ) and integ["branch"] in git("branch", "--list", integ["branch"], cwd=project_of(bus) or ".").stdout
    if not has_commits:
        msg = "nothing to integrate (no merged commits)"
    elif budget.get("auto_integrate"):
        out = integrate_into_project(bus)
        msg = f"integrated into {out['target']}" if out["ok"] else f"auto-integrate failed: {out['error']}"
    else:
        msg = f"ready to integrate: `warroom.py integrate {run} --apply` or the dashboard's Integrate button"
    bus.agent, prev = "conductor", bus.agent
    if kept:
        msg += (". Kept (not deleted): " + "; ".join(kept) +
                " - unreviewed or uncommitted work stays until you decide; its session stays with it")
    bus.send("orchestrator", f"Run {run} is finished. {msg}. Report: {os.path.join(run_dir(run), 'report.md')}")
    bus.agent = prev
    print(report + NL + NL + msg)


def shutdown(run, reason, close_window=True):
    """Finish the run (if it is not finished yet) and stop its conductor; the app keeps showing the result."""
    bus = open_bus(run)
    finish(run, reason)
    if IS_WIN and close_window:
        import ctypes
        for h in top_windows(app_title(run)):
            ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE the dashboard app window
    for pid in (json.loads(bus.control("daemons") or "{}") or {}).values():
        kill_pid(pid)
    bus.event("shutdown", reason)


def cmd_restart_daemons(a):
    """Restart the background conductor and dashboard (after a crash or a War Room update); workers keep running."""
    bus = open_bus(a.run)
    for pid in (json.loads(bus.control("daemons") or "{}") or {}).values():
        kill_pid(pid)
    if IS_WIN:
        import ctypes
        for h in top_windows(app_title(a.run)):
            ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)
    daemons = {"watch": spawn_daemon(a.run, "watch")}
    bus.control("daemons", json.dumps(daemons))
    url = ensure_hub() + f"run/{a.run}"
    bus.event("daemons", f"restarted conductor {daemons['watch']}")
    print(f"conductor pid {daemons['watch']}; app: {url}")
    if a.open:
        open_app(url)
        place_app(bus, a.run)


def cmd_shutdown(a):
    shutdown(a.run, "shutdown by orchestrator")


# ---------------------------------------------------------------- toggle and list
def cmd_toggle(a):
    cfg = load_json(CONFIG, {}) or {}
    if a.state != "status":
        cfg["enabled"] = a.state == "on"
        save_json(CONFIG, cfg)
        if cfg["enabled"]:
            print(WARNING + "\n")
    print(f"war mode: {'ON' if cfg.get('enabled') else 'off'}")


def cmd_list(a):
    for run in sorted(os.listdir(RUNS)) if os.path.isdir(RUNS) else []:
        db = os.path.join(RUNS, run, "bus.sqlite3")
        n = len(Bus(db, "x").workers()) if os.path.exists(db) else 0
        print(f"{run:<40} workers={n} {'launched' if n else 'planned'}")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("toggle"); s.add_argument("state", choices=["on", "off", "status"]); s.set_defaults(f=cmd_toggle)
    s = sub.add_parser("plan"); s.add_argument("plan"); s.set_defaults(f=cmd_plan)
    s = sub.add_parser("launch"); s.add_argument("run"); s.add_argument("--confirm", required=True)
    s.add_argument("--no-console", action="store_true", help="do not open conductor/dashboard/worker consoles")
    s.add_argument("--from-app", action="store_true", help=argparse.SUPPRESS)
    s.set_defaults(f=cmd_launch)
    s = sub.add_parser("status"); s.add_argument("run"); s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_status)
    s = sub.add_parser("post"); s.add_argument("run"); s.add_argument("title"); s.add_argument("--detail"); s.add_argument("--to")
    s.set_defaults(f=cmd_post)
    s = sub.add_parser("send"); s.add_argument("run"); s.add_argument("worker"); s.add_argument("message"); s.set_defaults(f=cmd_send)
    s = sub.add_parser("wake"); s.add_argument("run"); s.add_argument("worker"); s.add_argument("message", nargs="?")
    s.set_defaults(f=cmd_wake)
    s = sub.add_parser("pause"); s.add_argument("run"); s.set_defaults(f=lambda a: cmd_pause(a, True))
    s = sub.add_parser("unpause"); s.add_argument("run"); s.set_defaults(f=lambda a: cmd_pause(a, False))
    s = sub.add_parser("stop"); s.add_argument("run"); s.set_defaults(f=cmd_stop)
    s = sub.add_parser("resume"); s.add_argument("run"); s.add_argument("workers", nargs="*"); s.set_defaults(f=cmd_resume)
    s = sub.add_parser("watch"); s.add_argument("run"); s.add_argument("--schedule", action="store_true")
    s.add_argument("--interval", type=int, default=15); s.add_argument("--once", action="store_true"); s.set_defaults(f=cmd_watch)
    s = sub.add_parser("tile"); s.add_argument("run"); s.set_defaults(f=cmd_tile)
    s = sub.add_parser("serve"); s.add_argument("run"); s.add_argument("--port", type=int, default=0)
    s.add_argument("--no-browser", action="store_true"); s.add_argument("--browser", action="store_true",
                                                                        help="use the default browser, not an app window")
    s.set_defaults(f=cmd_serve)
    s = sub.add_parser("list"); s.set_defaults(f=cmd_list)
    s = sub.add_parser("approve"); s.add_argument("run"); s.add_argument("task", type=int)
    s.add_argument("--reject", metavar="NOTES"); s.set_defaults(f=cmd_approve)
    s = sub.add_parser("merge"); s.add_argument("run"); s.set_defaults(f=cmd_merge)
    s = sub.add_parser("integrate"); s.add_argument("run")
    s.add_argument("--apply", action="store_true", help="merge into the project's current branch (no push)")
    s.set_defaults(f=cmd_integrate)
    s = sub.add_parser("finish"); s.add_argument("run"); s.set_defaults(f=lambda a: finish(a.run, "finished by orchestrator"))
    s = sub.add_parser("measure"); s.add_argument("run"); s.set_defaults(f=cmd_measure)
    s = sub.add_parser("shutdown"); s.add_argument("run"); s.set_defaults(f=cmd_shutdown)
    s = sub.add_parser("restart-daemons"); s.add_argument("run"); s.add_argument("--open", action="store_true")
    s.set_defaults(f=cmd_restart_daemons)
    s = sub.add_parser("app"); s.add_argument("run", nargs="?"); s.add_argument("--quit", action="store_true")
    s.set_defaults(f=cmd_app)
    s = sub.add_parser("hub"); s.add_argument("--port", type=int, default=0); s.set_defaults(f=cmd_hub)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
