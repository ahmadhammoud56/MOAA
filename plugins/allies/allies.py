#!/usr/bin/env python3
"""Allies: hand bounded tasks from Claude Code to other agent CLIs (Codex, Gemini, Kimi, DeepSeek, an OmniRoute
gateway), each signed in with its own account. Standard library only.

Claude Code stays in charge: it writes the brief, a member works headless, and the answer comes back as a file for
Claude to check. Read-only by default. With --write the member works in a fresh git worktree on its own branch, never
in your checkout, and you merge what you accept.

  python allies.py doctor [--json]                         which members are installed and signed in
  python allies.py run MEMBER --task TEXT|--task-file F [--cwd DIR] [--write] [--model M] [--timeout S]
  python allies.py ask MEMBER[,MEMBER...] --task ...        the same task to several members in parallel (read-only)
  python allies.py pick --for code|review|research|debug|long-context|bulk [--exclude M,...]
  python allies.py runs [--limit N]        python allies.py show RUN_ID
  python allies.py omniroute start|stop|status              a local OmniRoute gateway with locked-down settings
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
IS_WIN = os.name == "nt"
OMNI_PORT = 20128
# OmniRoute settings MOAA always starts it with: loopback only, API key required, no conversation tracking, no
# browser-cookie providers, no paid-credit fallback. Secrets are generated once and kept in the allies folder.
OMNI_SAFE_ENV = {"PORT": str(OMNI_PORT), "HOST": "127.0.0.1", "HOSTNAME": "127.0.0.1", "OMNIROUTE_SERVER_HOST": "127.0.0.1",
                 "APP_BIND_HOST": "127.0.0.1", "REQUIRE_API_KEY": "true", "OMNIROUTE_DISABLE_CONVERSATION_TRACKING": "1",
                 "WEB_COOKIE_USE_BROWSER": "0", "ANTIGRAVITY_CREDITS": "off", "ALLOW_API_KEY_REVEAL": "false",
                 # pinned so a package update cannot turn them on: no traffic-inspecting proxy, no TLS interception,
                 # no cloud sync, WebSocket only for this machine
                 "INSPECTOR_HTTP_PROXY_AUTOSTART": "false", "INSPECTOR_TLS_INTERCEPT": "false", "CLOUD_URL": "",
                 "NEXT_PUBLIC_CLOUD_URL": "", "LIVE_WS_HOST": "127.0.0.1"}
BRIEF = """You are an ally working for Claude Code, which will check your answer before anyone relies on \
it. Work only on the task below, inside the current working directory. Do not push, publish, delete files outside \
your working directory, spend money, or change system settings. If you cannot finish, say exactly what is missing. \
End with a short summary: what you did, what you checked, and anything uncertain.

{mode}

TASK:
{task}"""
READ_NOTE = "You are in read-only mode: inspect and answer; do not modify files."
WRITE_NOTE = ("You are working in a dedicated git worktree on its own branch. Make the change and run the relevant "
              "checks. Do not commit and do not touch other branches: allies commits your changes when you finish.")


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()


def allies_home():
    return Path(os.environ.get("MOAA_ALLIES_DIR") or claude_home() / "allies").expanduser()


def load_members():
    return json.loads((HERE / "members.json").read_text(encoding="utf-8"))["members"]


def which(name):
    """shutil.which plus the user-level folders npm and uv use, which a fresh PATH may lack."""
    found = shutil.which(name)
    if found:
        return found
    extra = [Path.home() / ".local" / "bin"]
    if IS_WIN and os.environ.get("APPDATA"):
        extra.append(Path(os.environ["APPDATA"]) / "npm")
    for d in extra:
        for ext in ((".cmd", ".exe", ".ps1", "") if IS_WIN else ("",)):
            if (d / (name + ext)).is_file():
                return str(d / (name + ext))
    return None


SHIM_RE = re.compile(r'"%dp0%\\([^"]+\.(?:js|mjs|cjs))"', re.I)
CMD_META = re.compile(r'[\r\n"%&|<>^!]')
MODEL_RE = re.compile(r"^[A-Za-z0-9][\w.:/@-]{0,80}$")
SECRETISH = re.compile(r"(KEY|TOKEN|SECRET|PASSW|CREDENTIAL|^ANTHROPIC_|^CLAUDE|^AWS_|^AZURE_|^GOOGLE_|^GEMINI_|^OPENAI_|"
                       r"^DEEPSEEK_|^OMNIROUTE_|^MOONSHOT_|^KIMI_|^CODEX_)", re.I)


def launcher(exe):
    """argv prefix for a CLI. An npm .cmd shim is bypassed: its node script is run directly, because cmd.exe would
    re-parse the arguments (task text included) and could run commands hidden in them (the BatBadBut issue)."""
    if not (IS_WIN and exe.lower().endswith((".cmd", ".bat"))):
        return [exe], False
    try:
        m = SHIM_RE.search(Path(exe).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        m = None
    if m:
        script = Path(exe).parent.joinpath(*m.group(1).split("\\"))  # the shim spells the path with backslashes
        node = Path(exe).parent / "node.exe"
        node = str(node) if node.is_file() else shutil.which("node")
        if node and script.is_file():
            return [node, str(script)], False
    return [exe], True  # still a shim: the caller must refuse arguments cmd.exe could misread


def child_env(spec, overrides):
    """The environment a member runs with: yours, minus credentials for anything else (Claude, cloud, other
    providers), plus what this member needs. A member only sees its own keys."""
    keep = re.compile(spec["pass_env"]) if spec.get("pass_env") else None
    env = {k: v for k, v in os.environ.items() if not SECRETISH.search(k) or (keep and keep.match(k))}
    if keep:  # this member's own keys kept in keys.env, when the environment does not set them
        env.update({k: v for k, v in read_env_file(allies_home() / "keys.env").items() if keep.match(k) and k not in env})
    env.pop("CLAUDECODE", None)  # a nested headless Claude Code must not think it runs inside this session
    return {**env, **overrides}


def kill_tree(proc):
    if IS_WIN:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            proc.kill()


def run_proc(argv, stdin, cwd, env, timeout, on_start=None):
    """Run a member in its own process group; on timeout kill the whole tree (node children included)."""
    kw = {"creationflags": 0x00000200} if IS_WIN else {"start_new_session": True}
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env, text=True,
                            encoding="utf-8", errors="replace", **kw)
    if on_start:
        on_start(proc.pid)
    try:
        out, err = proc.communicate(stdin, timeout=timeout)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        return "timeout", out or "", err or ""


def long_path(path):
    """Absolute path with Windows 8.3 short names (such as PROGRA~1) expanded: agent sandboxes such as Codex's deny
    access to a workspace given in short form."""
    p = Path(path).resolve()
    if IS_WIN:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.GetLongPathNameW(str(p), buf, len(buf)):
            return Path(buf.value)
    return p


def member_env(spec):
    """(env overrides, missing variable names). '$NAME' values come from the environment or the allies env file."""
    out, missing = {}, []
    saved = read_env_file(allies_home() / "keys.env")
    for k, v in (spec.get("env") or {}).items():
        if v.startswith("$"):
            val = os.environ.get(v[1:]) or saved.get(v[1:])
            if not val:
                missing.append(v[1:])
                continue
            v = val
        out[k] = v.replace("{data}", allies_home().as_posix())
    return out, missing


def read_env_file(path):
    vals = {}
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    except OSError:
        pass
    return vals


def reachable(url, timeout=2, any_status=False):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310  fixed URLs from members.json
            return any_status or r.status < 500
    except urllib.error.HTTPError as e:
        return any_status or e.code < 500  # 401 still means the gateway is up
    except (OSError, ValueError):
        return False


def signed_in(name):
    """Best-effort sign-in check without spending tokens. None = cannot tell."""
    home = Path.home()
    if name == "codex":
        exe = which("codex")
        if not exe:
            return False
        try:
            out = subprocess.run(launcher(exe)[0] + ["login", "status"], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.returncode == 0 and "logged in" in (out.stdout + out.stderr).lower()
    if name == "gemini":  # Google sign-in no longer serves the CLI's free tier ("migrate to Antigravity"): a key is needed
        saved = read_env_file(allies_home() / "keys.env")
        return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                    or saved.get("GEMINI_API_KEY") or saved.get("GOOGLE_API_KEY"))
    if name == "kimi":
        return any((home / d).is_dir() and any((home / d).rglob("*cred*")) for d in (".kimi", ".kimi-code")) or None
    return None


def doctor():
    rows = []
    for name, spec in load_members().items():
        exe = which(spec["bin"])
        env, missing = member_env(spec)
        row = {"member": name, "label": spec["label"], "installed": bool(exe), "missing_env": missing}
        if exe and spec["bin"] != "claude":
            try:
                v = subprocess.run(launcher(exe)[0] + ["--version"], capture_output=True, text=True, timeout=30)
                row["version"] = (v.stdout or v.stderr).strip().splitlines()[0][:60] if (v.stdout or v.stderr).strip() else "?"
            except (OSError, subprocess.SubprocessError):
                row["version"] = "?"
        if spec.get("needs_url"):
            row["reachable"] = reachable(spec["needs_url"])
        elif spec.get("probe"):  # any HTTP answer means the service is reachable; a timeout means a network block
            row["reachable"] = reachable(spec["probe"], timeout=6, any_status=True)
        row["signed_in"] = (not missing) if spec.get("env") else (signed_in(name) if exe else False)
        usable = bool(exe) and not missing and row["signed_in"] is not False and row.get("reachable", True)
        row["ready"] = usable and row["signed_in"] is True
        row["state"] = "ready" if row["ready"] else "unverified" if usable else "not ready"
        row["fix"] = ("" if row["ready"] else "sign-in cannot be checked: " + spec["login"] if usable
                      else spec["install"] if not exe
                      else f"blocked on this network ({spec['probe']} unreachable)" if row.get("reachable") is False
                      and spec.get("probe") else spec["login"])
        if row.get("reachable") is False and spec.get("probe"):
            row["state"] = "blocked"
        rows.append(row)
    return rows


def ready_members():
    return {r["member"] for r in doctor() if r["ready"]}


def pick(purpose, exclude=(), ready=None):
    """First ready member, in members.json order, that lists the purpose as good_for."""
    ready = ready_members() if ready is None else ready
    for name, spec in load_members().items():
        if name in ready and name not in exclude and purpose in spec.get("good_for", []):
            return name
    return None


# ---------------------------------------------------------------- runs
def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def make_worktree(cwd, run_id, member):
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode:
        raise SystemExit("allies: --write needs a git repository (the member works on its own branch)")
    branch = f"ally/{member}-{run_id}"
    path = allies_home() / "worktrees" / f"{Path(top.stdout.strip()).name}-{run_id}"
    path.parent.mkdir(parents=True, exist_ok=True)
    out = git(top.stdout.strip(), "worktree", "add", "-b", branch, str(path), "HEAD")
    if out.returncode:
        raise SystemExit(f"allies: git worktree add failed: {out.stderr.strip()[-300:]}")
    return path, branch, top.stdout.strip()


def commit_worktree(wt, member, task, base):
    """Commit whatever the member left in its worktree (agent sandboxes often cannot write a linked worktree's git
    metadata), then report the branch's change against the base."""
    if git(wt, "status", "--porcelain").stdout.strip():
        git(wt, "add", "-A")
        title = " ".join(task.split())[:60]
        git(wt, "-c", "user.name=MOAA allies", "-c", "user.email=allies@localhost", "commit", "-q", "--no-verify", "-m",
            f"ally({member}): {title}", "-m", "Made by an ally; review before merging.")
    return {"commits": git(wt, "rev-list", "--count", f"{base}..HEAD").stdout.strip(),
            "diffstat": git(wt, "diff", "--stat", f"{base}..HEAD").stdout.strip(),
            "uncommitted": bool(git(wt, "status", "--porcelain").stdout.strip())}


def build_argv(spec, exe, write, model, prompt, out_file):
    argv = [exe] + [a.replace("{out}", str(out_file)).replace("{plugin}", HERE.as_posix()).replace("{prompt}", prompt)
                    for a in spec["write" if write else "read"]]
    model = model or spec.get("default_model")
    if model:
        argv += [a.replace("{model}", model) for a in spec.get("model", [])]
    return argv


def new_run_id():
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def run(member, task, cwd=".", write=False, model=None, timeout=1200, run_id=None, workdir=None, on_start=None,
        title=None):
    """Run one member. With write, it works in a fresh worktree, or in `workdir` (an existing worktree the caller
    owns, such as a War Room writer's); either way allies commits what it leaves behind."""
    members = load_members()
    if member not in members:
        raise SystemExit(f"allies: unknown member {member!r}; one of {', '.join(members)}")
    spec = members[member]
    exe = which(spec["bin"])
    if not exe:
        raise SystemExit(f"allies: {member} is not installed ({spec['install']})")
    env_over, missing = member_env(spec)
    if missing:
        raise SystemExit(f"allies: {member} needs {', '.join(missing)} ({spec['login']})")
    if model and not MODEL_RE.match(model):
        raise SystemExit(f"allies: not a model name: {model!r}")
    if spec.get("needs_url") and not reachable(spec["needs_url"]):
        raise SystemExit(f"allies: {member} is not reachable ({spec['login']})")
    run_id = run_id or new_run_id()
    rdir = allies_home() / "runs" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    cwd = long_path(cwd)
    meta = {"id": run_id, "member": member, "write": write, "model": model or spec.get("default_model"), "cwd": str(cwd),
            "started": time.time()}
    if write and workdir:
        wt = long_path(workdir)
        if git(wt, "rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
            raise SystemExit(f"allies: {wt} is not a git worktree")
        meta.update(worktree=str(wt), branch=git(wt, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(),
                    base=git(wt, "rev-parse", "HEAD").stdout.strip())
        cwd = wt
    elif write:
        wt, branch, repo = make_worktree(cwd, run_id, member)
        meta.update(worktree=str(wt), branch=branch, repo=repo, base=git(wt, "rev-parse", "HEAD").stdout.strip())
        cwd = wt
    prompt = BRIEF.format(mode=WRITE_NOTE if write else READ_NOTE, task=task.strip())
    (rdir / "task.md").write_text(prompt, encoding="utf-8")
    out_file = rdir / f"{member}.answer.md"
    prefix, via_cmd = launcher(exe)
    argv = prefix + build_argv(spec, exe, write, model, prompt if not spec.get("stdin") else "", out_file)[1:]
    if via_cmd and any(CMD_META.search(a) for a in argv[1:]):
        raise SystemExit(f"allies: {member} is a .cmd shim allies could not unwrap, and the task has characters cmd.exe "
                         "would interpret; give it on stdin or simplify it")
    for path, content in (spec.get("files") or {}).items():  # e.g. Gemini's own home, set to API-key sign-in
        f = Path(path.replace("{data}", allies_home().as_posix()))
        if not f.is_file():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    env = child_env(spec, env_over)
    t0 = time.time()
    code, stdout, stderr = run_proc(argv, prompt if spec.get("stdin") else None, str(cwd), env, timeout, on_start)
    answer = out_file.read_text(encoding="utf-8", errors="replace").strip() if out_file.is_file() else ""
    answer = answer or stdout.strip()
    out_file.write_text(answer + "\n", encoding="utf-8")
    (rdir / f"{member}.log").write_text(f"$ {' '.join(argv[:12])} ...\n\n--- stdout\n{stdout}\n--- stderr\n{stderr}",
                                        encoding="utf-8")
    meta.update(exit=code, seconds=round(time.time() - t0, 1), answer=str(out_file), ok=code == 0 and bool(answer))
    if write:
        meta.update(commit_worktree(cwd, member, title or task, meta["base"]), head=git(cwd, "rev-parse", "HEAD").stdout.strip())
    (rdir / f"meta-{member}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def ask(members, task, cwd=".", model=None, timeout=1200):
    run_id = new_run_id()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(members)) as pool:
        futures = {m: pool.submit(run, m, task, cwd, False, model, timeout, run_id) for m in members}
    out = []
    for m, f in futures.items():
        try:
            out.append(f.result())
        except (SystemExit, OSError) as e:
            out.append({"id": run_id, "member": m, "ok": False, "error": str(e)})
    return out


def list_runs(limit=20):
    base = allies_home() / "runs"
    items = []
    for d in sorted(base.iterdir(), reverse=True) if base.is_dir() else []:
        for meta in sorted(d.glob("meta*.json")) or []:
            items.append(json.loads(meta.read_text(encoding="utf-8")))
        if len(items) >= limit:
            break
    return items[:limit]


def cmdline(pid):
    """A process's command line, or '' (used to check a stored pid before killing it)."""
    try:
        if IS_WIN:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                                 capture_output=True, text=True, timeout=20)
            return out.stdout.strip()
        return Path(f"/proc/{int(pid)}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""


# ---------------------------------------------------------------- OmniRoute
def omni_env():
    path = allies_home() / "omniroute.env"
    saved = read_env_file(path)
    if not saved.get("INITIAL_PASSWORD") or not saved.get("JWT_SECRET"):
        saved.update(INITIAL_PASSWORD=secrets.token_urlsafe(18), JWT_SECRET=secrets.token_urlsafe(48))
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # owner-only from the start (POSIX)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("# Generated by MOAA allies. INITIAL_PASSWORD is the OmniRoute dashboard password on first boot.\n"
                    + "".join(f"{k}={v}\n" for k, v in saved.items()))
    return {**saved, **OMNI_SAFE_ENV}


def omniroute(action):
    pid_file = allies_home() / "omniroute.pid"
    url = f"http://127.0.0.1:{OMNI_PORT}/v1/models"
    if action == "status":
        return {"running": reachable(url), "dashboard": f"http://127.0.0.1:{OMNI_PORT}", "secrets": str(allies_home() / "omniroute.env")}
    if action == "stop":
        pid = pid_file.read_text().strip() if pid_file.is_file() else ""
        ok = pid.isdigit() and "omniroute" in cmdline(int(pid)).lower()  # never a reused pid of another program
        if ok:
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"] if IS_WIN else ["kill", pid], capture_output=True)
        pid_file.unlink(missing_ok=True)
        return {"stopped": ok}
    exe = which("omniroute")
    if not exe:
        raise SystemExit("allies: omniroute is not installed (python scripts/install.py --with-omniroute)")
    if reachable(url):
        return {"running": True, "note": "already running; settings are those it was started with"}
    log = open(allies_home() / "omniroute.log", "a", encoding="utf-8")
    kw = {"creationflags": 0x08000000 | 0x00000200} if IS_WIN else {"start_new_session": True}
    argv = [exe]
    proc = subprocess.Popen(argv, env=child_env({}, omni_env()), stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, cwd=str(allies_home()), **kw)
    pid_file.write_text(str(proc.pid))
    for _ in range(60):
        if reachable(url):
            return {"running": True, "dashboard": f"http://127.0.0.1:{OMNI_PORT}",
                    "password_file": str(allies_home() / "omniroute.env")}
        time.sleep(1)
    return {"running": False, "log": str(allies_home() / "omniroute.log")}


# ---------------------------------------------------------------- CLI
def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("doctor"); s.add_argument("--json", action="store_true")
    for name in ("run", "ask"):
        s = sub.add_parser(name)
        s.add_argument("member")
        g = s.add_mutually_exclusive_group(required=True)
        g.add_argument("--task"); g.add_argument("--task-file")
        s.add_argument("--cwd", default="."); s.add_argument("--model"); s.add_argument("--timeout", type=int, default=1200)
        if name == "run":
            s.add_argument("--write", action="store_true")
    s = sub.add_parser("pick"); s.add_argument("--for", dest="purpose", required=True); s.add_argument("--exclude", default="")
    s = sub.add_parser("runs"); s.add_argument("--limit", type=int, default=20)
    s = sub.add_parser("show"); s.add_argument("run_id")
    s = sub.add_parser("omniroute"); s.add_argument("action", choices=("start", "stop", "status"))
    a = p.parse_args(argv)
    if a.cmd == "doctor":
        rows = doctor()
        if a.json:
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"  {r['member']:<10} {r['state']:<10} {r.get('version', '')[:28]:<28} {r['fix']}")
        return 0
    if a.cmd in ("run", "ask"):
        task = a.task if a.task is not None else Path(a.task_file).read_text(encoding="utf-8")
        if a.cmd == "run":
            out = run(a.member, task, a.cwd, a.write, a.model, a.timeout)
        else:
            out = ask([m for m in a.member.split(",") if m], task, a.cwd, a.model, a.timeout)
        print(json.dumps(out, indent=2))
        return 0 if (out["ok"] if isinstance(out, dict) else any(x.get("ok") for x in out)) else 1
    if a.cmd == "pick":
        m = pick(a.purpose, [x for x in a.exclude.split(",") if x])
        print(m or "none ready")
        return 0 if m else 1
    if a.cmd == "runs":
        for r in list_runs(a.limit):
            print(f"{r['id']}  {r['member']:<9} {'write' if r.get('write') else 'read ':<5} "
                  f"{'ok' if r.get('ok') else 'FAILED':<6} {r.get('seconds', '')}s  {r.get('answer', r.get('error', ''))}")
        return 0
    if a.cmd == "show":
        if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{4}", a.run_id):
            p.error("not a run id")
        d = allies_home() / "runs" / a.run_id
        for meta in sorted(d.glob("meta*.json")):
            print(meta.read_text(encoding="utf-8"))
        for ans in sorted(d.glob("*.answer.md")):
            print(f"===== {ans.name}\n{ans.read_text(encoding='utf-8')}")
        return 0
    print(json.dumps(omniroute(a.action), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
