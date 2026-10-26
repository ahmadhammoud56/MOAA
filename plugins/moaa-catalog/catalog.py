#!/usr/bin/env python3
"""MOAA catalog: skills from installed but disabled plugins, found and used on demand instead of listed in every session.

  python catalog.py search <words...>   best-matching disabled skills: name, plugin, path
  python catalog.py use <SKILL.md path>  print that skill (and log the use; suggests enabling a pack used often)
  python catalog.py packs               disabled plugins and their skill counts
  python catalog.py hook prompt         UserPromptSubmit hook: suggest up to 3 strong matches for the prompt on stdin
  python catalog.py hook session        SessionStart hook: once a day, say if a newer MOAA release exists; warms the index
  python catalog.py index               rebuild the index now if it is stale
  python catalog.py ruflo-update        install or update the global ruflo CLI (the hooks run this every 3 hours, in
                                        the background, while a ruflo plugin is enabled; MOAA_RUFLO_UPDATE=off stops it)

The index (~/.claude/moaa-catalog/index.json) is rebuilt only when the plugin record or settings change, so a search
or a hook call reads one small file; the hooks never rebuild it inline but start a background rebuild.
MOAA_CATALOG_HINTS=off silences the prompt hook for a process. Never changes settings or plugins. Standard library only.
"""
import json
import math
import os
from pathlib import Path
import re
import sys
import time

STOP = set("""a an and are as at be by can do for from get how i in into is it its me my of on or our please that the
their them then this to use using want we what when where which will with you your make need help new add file files
code project task work like just also some any all not""".split())
# Short forms people type -> the words skill descriptions use. Applied to queries and prompts, not to the index.
SYNONYMS = {"k8s": "kubernetes", "tf": "terraform", "js": "javascript", "ts": "typescript", "py": "python",
            "postgres": "postgresql", "pg": "postgresql", "db": "database",
            "ml": "machine-learning", "llm": "language-model", "ui": "interface", "ux": "usability",
            "docs": "documentation", "doc": "documentation", "xlsx": "excel", "spreadsheet": "excel",
            "docx": "word", "pptx": "powerpoint", "slides": "powerpoint", "deck": "powerpoint", "ci": "pipeline",
            "e2e": "end-to-end", "auth": "authentication", "a11y": "accessibility", "i18n": "localization",
            "rn": "react-native", "gha": "github-actions", "regex": "regular-expression", "sql": "database"}
# Files that tell what a project is; their words boost (never trigger) matches in that project.
PROJECT_HINTS = {"package.json": "javascript node", "tsconfig.json": "typescript", "pyproject.toml": "python",
                 "requirements.txt": "python", "Cargo.toml": "rust", "go.mod": "go", "pom.xml": "java",
                 "build.gradle": "java kotlin", "Gemfile": "ruby", "composer.json": "php", "Dockerfile": "docker",
                 "next.config.js": "nextjs react", "vite.config.ts": "vite", "pubspec.yaml": "flutter dart",
                 "main.tf": "terraform", "Chart.yaml": "helm kubernetes", "manage.py": "django python"}
HOOK_MIN, HOOK_MAX = 2.0, 3  # hook: minimum score in units of one unique-word hit (tuned on 2,500 skills so generic
#                              prompts stay quiet), and at most this many lines
PROMOTE_USES, PROMOTE_DAYS = 3, 30  # suggest enabling a pack used this often


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def words(text):
    """Lower-case tokens without stop words; a trailing plural s is dropped so 'charts' finds 'chart'."""
    out = []
    for w in re.findall(r"[a-z0-9][a-z0-9+#.-]*[a-z0-9+#]|[a-z0-9]", text.lower()):
        w = w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
        if w not in STOP:
            out.append(w)
    return out


def expand(tokens):
    """Query tokens plus the long form of any short form (k8s -> kubernetes), order kept, no duplicates."""
    out = []
    for w in tokens:
        long = SYNONYMS.get(w)
        out += [w] + (words(long.replace("-", " ")) + [long] if long else [])
    return list(dict.fromkeys(out))


def project_hints(cwd):
    """Words describing the project at `cwd`, from marker files in its top folder."""
    root = Path(cwd) if cwd else None
    if not root or not root.is_dir():
        return []
    return list(dict.fromkeys(w for f, ws in PROJECT_HINTS.items() if (root / f).exists() for w in ws.split()))


def installed_plugins(home):
    """{plugin id: (install path, enabled)} for every installed plugin."""
    on = {k for k, v in read_json(home / "settings.json").get("enabledPlugins", {}).items() if v}
    installed = read_json(home / "plugins" / "installed_plugins.json").get("plugins", {})
    return {pid: (Path((e or [{}])[0].get("installPath", "")), pid in on) for pid, e in sorted(installed.items())}


def disabled_plugins(home):
    """{plugin id: install path} for installed plugins that are not enabled in settings.json."""
    return {pid: path for pid, (path, on) in installed_plugins(home).items() if not on}


def trimmed(home):
    """True when the skill listing is cut short (MOAA's all-on mode: names plus short descriptions), so enabled
    skills are worth suggesting too: Claude no longer sees their full descriptions."""
    return read_json(home / "settings.json").get("skillListingMaxDescChars", 1536) <= 300


def frontmatter(path):
    """(name, description) from a SKILL.md's front matter; single-line values, which is what skills use."""
    text = path.read_text(encoding="utf-8", errors="replace")
    head = text.split("---", 2)[1] if text.startswith("---") else ""
    get = lambda key: (re.search(rf"^{key}:\s*(.+)$", head, re.M) or [None, ""])[1].strip().strip("\"'")  # noqa: E731
    return get("name") or path.parent.name, get("description")


def stamp(home):
    return [f.stat().st_mtime if f.is_file() else 0
            for f in (home / "settings.json", home / "plugins" / "installed_plugins.json")]


def build_index(home):
    skills = []
    for pid, (root, on) in sorted(installed_plugins(home).items(), key=lambda kv: kv[1][1]):  # disabled first
        for md in sorted(root.rglob("SKILL.md")) if root.is_dir() else []:
            name, desc = frontmatter(md)
            skills.append({"pid": pid, "on": on, "name": name, "desc": desc, "path": md.as_posix(),
                           "nw": sorted(set(words(name.replace("-", " ") + " " + name))), "dw": sorted(set(words(desc)))})
    df = {}
    for s in skills:
        for w in set(s["nw"]) | set(s["dw"]):
            df[w] = df.get(w, 0) + 1
    n = max(len(skills), 1)
    return {"stamp": stamp(home), "skills": skills, "idf": {w: round(math.log(1 + n / c), 3) for w, c in df.items()}}


def load_index(home, wait=True):
    """The cached index, rebuilt only when settings.json or the installed-plugin record changed. With wait=False (the
    prompt hook) a stale index is used as it is and the rebuild runs in a detached process: it reads every SKILL.md of
    every plugin, 5 s warm with ~3,600 skills and over the hook's 10 s timeout on a cold disk."""
    path = home / "moaa-catalog" / "index.json"
    index = read_json(path)
    if index.get("stamp") != stamp(home) or "idf" not in index:
        if not wait:
            rebuild_in_background(home)
            return index if "idf" in index else {}
        index = build_index(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(index), encoding="utf-8")
        os.replace(tmp, path)
    return index


def rebuild_in_background(home):
    """Start `catalog.py index` detached, at most once a minute (a marker file holds back the prompts that follow)."""
    mark = home / "moaa-catalog" / "index.building"
    try:
        if time.time() - mark.stat().st_mtime < 60:
            return
    except OSError:
        pass
    import subprocess
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text(str(time.time()), encoding="utf-8")
    argv = [sys.executable, str(Path(__file__).resolve()), "index"]
    quiet = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == "nt":
        subprocess.Popen(argv, creationflags=0x08000000 | 0x00000200, **quiet)  # no window, own process group
    else:
        subprocess.Popen(argv, start_new_session=True, **quiet)


def rank(index, query, hints=(), include_on=False):
    """(query words, [(score, matched, skill, name hits)] best first). A query word scores its rarity (idf), doubled
    when it is in the skill's name. Project hint words add half their idf to skills that already match the query."""
    q = expand(dict.fromkeys(words(query)))
    hints = [h for h in hints if h not in q]
    idf, out = index["idf"], []
    pool = [s for s in index["skills"] if include_on or not s.get("on")]  # enabled skills are listed in full otherwise
    # Bundles repeat the same skill. Keep one copy per name: an enabled one when there is one (usable through the
    # Skill tool directly), otherwise the first disabled one.
    pick = {}
    for s in pool:
        if s["name"] not in pick or (s.get("on") and not pick[s["name"]].get("on")):
            pick[s["name"]] = s
    for s in pick.values():
        nw, dw = set(s["nw"]), set(s["dw"])
        hit = [w for w in q if w in nw or w in dw]
        if hit:
            boost = sum(idf.get(h, 1) / 2 for h in hints if h in nw or h in dw)
            out.append((sum(idf.get(w, 1) * (2 if w in nw else 1) for w in hit) + boost, len(hit), s,
                        sum(w in nw for w in hit)))
    out.sort(key=lambda r: (-r[1], -r[0]))
    return q, out


def search(home, query, limit=8, cwd=None):
    """Skills matching the most query words (at least half of the typed ones), best first, boosted for the project."""
    q, ranked = rank(load_index(home), query, project_hints(cwd or os.getcwd()), trimmed(home))
    need = max(1, math.ceil(len(dict.fromkeys(words(query))) / 2))
    return [r for r in ranked if r[1] >= need][:limit]


def uses(home, days=PROMOTE_DAYS):
    cut, counts = time.time() - days * 86400, {}
    log = home / "moaa-catalog" / "usage.jsonl"
    for line in log.read_text(encoding="utf-8").splitlines() if log.is_file() else []:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("ts", 0) >= cut:
            counts[e["pid"]] = counts.get(e["pid"], 0) + 1
    return counts


def promote_hint(home, pid):
    n = uses(home).get(pid, 0)
    if n >= PROMOTE_USES:
        return (f"{pid} was used {n} times in {PROMOTE_DAYS} days: suggest `claude plugin enable {pid}` to the user "
                "(loads from the next session).")
    return ""


def use(home, path):
    """Print a disabled skill's SKILL.md and log the use. Only paths inside the index are served."""
    skill = next((s for s in load_index(home)["skills"] if Path(s["path"]) == Path(path)), None)
    if not skill:
        print("not a disabled-plugin skill from the catalog index; run `catalog.py search` first")
        return 1
    log = home / "moaa-catalog" / "usage.jsonl"
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "pid": skill["pid"], "skill": skill["name"]}) + "\n")
    print(f"# {skill['name']} [{skill['pid']}] (files it mentions are relative to {Path(path).parent.as_posix()})\n")
    print(Path(path).read_text(encoding="utf-8", errors="replace"))
    hint = promote_hint(home, skill["pid"])
    if hint:
        print("\n" + hint)
    return 0


REMINDER = re.compile(r"<system-reminder>[\s\S]*?</system-reminder>")
# Prompts that machines, not the user, send: the Claude desktop app's hidden Haiku run that summarizes a chat.
MACHINE_PROMPTS = ("Below is a conversation log from a Claude Code coding session",)


def hook_prompt(home, payload):
    """additionalContext naming up to HOOK_MAX strong matches, or None. Short prompts and slash commands are skipped.
    The <system-reminder> blocks the desktop app puts in front of the user's words are dropped first."""
    if os.environ.get("MOAA_CATALOG_HINTS", "").strip().lower() in ("off", "0", "false", "no"):
        return None
    prompt = REMINDER.sub("", (payload or {}).get("prompt") or "").strip()
    if prompt.startswith(("/", "[SYSTEM", "<") + MACHINE_PROMPTS) or "<task-notification>" in prompt \
            or len(words(prompt)) < 3:
        return None  # slash commands, harness notices (background tasks, side sessions), machine prompts
    index = load_index(home, wait=False)
    if not index.get("skills"):
        return None
    _, ranked = rank(index, prompt, project_hints(payload.get("cwd")), trimmed(home))
    unit = math.log(1 + len(index["skills"]))  # idf of a word found in one skill only; makes HOOK_MIN corpus-independent
    best = [r for r in ranked if r[0] >= HOOK_MIN * unit and r[1] >= 2 and r[3] >= 1][:HOOK_MAX]  # needs a name hit
    if not best:
        return None
    catalog = Path(__file__).resolve().as_posix()
    lines = [f"- {s['name']} [{s['pid']}]: {s['desc'][:140]}\n  " + how(s, catalog) for _, _, s, _ in best]
    return ("moaa-catalog: skills that may fit this request (use one only if it clearly helps):\n" + "\n".join(lines))


def how(skill, catalog):
    """How to use a hit: an enabled plugin's skill through the Skill tool, a disabled one through `catalog.py use`."""
    if skill.get("on"):
        return f"enabled: Skill tool, skill \"{skill['pid'].split('@')[0]}:{skill['name']}\""
    return f"disabled, load it with: python \"{catalog}\" use \"{skill['path']}\""


UPDATE_REPO = "ahmadhammoud56/MOAA"
UPDATE_EVERY = 86400  # seconds between checks of the latest release


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def latest_release(repo, timeout=2):
    import urllib.request
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "moaa-catalog"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310  fixed GitHub API URL
        return json.loads(r.read().decode("utf-8")).get("tag_name", "").lstrip("v")


def update_notice(home, fetch=latest_release, now=None):
    """A one-line notice when a newer MOAA release exists than the installed marketplace copy, else None. Checks
    GitHub at most once a day (cached), never blocks a session for more than a couple of seconds, stays silent offline
    and when non-essential traffic or the check is turned off."""
    if os.environ.get("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC") or os.environ.get("MOAA_NO_UPDATE_CHECK"):
        return None
    entry = read_json(home / "plugins" / "known_marketplaces.json").get("moaa") or {}
    where = Path(entry.get("installLocation", ""))
    installed = read_json(where / "config" / "kit.json").get("version") if entry else None
    if not installed:
        return None
    now = now or time.time()
    cache_path = home / "moaa-catalog" / "update.json"
    cache = read_json(cache_path)
    if "checked" not in cache or now - cache["checked"] >= UPDATE_EVERY:
        try:
            cache = {"checked": now, "latest": fetch(UPDATE_REPO)}
        except Exception:  # offline, rate-limited: try again tomorrow, say nothing
            cache = {"checked": now, "latest": cache.get("latest", "")}
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    latest = cache.get("latest", "")
    if version_tuple(latest) <= version_tuple(installed):
        return None
    if entry.get("source", {}).get("source") == "directory":
        how = f'run `py "{(where / "scripts" / "install.py").as_posix()}" --update` (pulls and reinstalls)'
    else:
        how = ("run `claude plugin marketplace update moaa`, or /plugin > Marketplaces > moaa > Update marketplace, "
               "then /reload-plugins")
    return (f"MOAA {latest} is available (installed {installed}): {how}. "
            f"Changes: https://github.com/{UPDATE_REPO}/releases/tag/v{latest}")


RUFLO_EVERY = 3 * 3600  # seconds between checks of the global ruflo CLI (ruflo ships several releases a week)
RUFLO_RETRY = 600  # seconds between install attempts while `ruflo` is missing from PATH
RUFLO_LOCK_AGE = 1800  # an update lock older than this belongs to a run that died
# ruflo's dependencies that have install scripts (npm's own list for ruflo 3.63). npm 11 still runs them but warns that
# a coming release will block them; ruflo would then ship without the native binaries of better-sqlite3, argon2,
# hnswlib-node, onnxruntime-node and sharp, and its memory features would break. A fixed, reviewed list: a dependency
# that is not on it is logged, never allowed automatically.
RUFLO_SCRIPTS = ("agentdb,agentic-flow,better-sqlite3,argon2,hnswlib-node,onnxruntime-node,protobufjs,@google/genai,"
                 "sharp,tldjs,@claude-flow/cli")


def ruflo_wanted(home, now=None):
    """True when a ruflo CLI check is due: every 3 hours, or every 10 minutes while `ruflo` is missing from PATH
    (ruflo-core's hooks then fall back to `npx ruflo@latest`, which on Windows opens a console window on every tool
    call). Only while a ruflo plugin is enabled, npm is on PATH and the check is not off. Cheap enough for every
    prompt: the stamp's age is read first, the plugin record only when a check is due."""
    import shutil
    if any(os.environ.get(k) for k in ("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "MOAA_NO_UPDATE_CHECK")) \
            or os.environ.get("MOAA_RUFLO_UPDATE", "").lower() in ("off", "0", "false"):
        return False
    age = (now or time.time()) - read_json(home / "moaa-catalog" / "ruflo.json").get("checked", 0)
    if age < RUFLO_RETRY or (age < RUFLO_EVERY and shutil.which("ruflo")):
        return False
    if not shutil.which("npm"):
        return False
    return any(pid.startswith("ruflo-") and on for pid, (_, on) in installed_plugins(home).items())  # @ruflo or @moaa


def ruflo_update_in_background(home):
    """Start `catalog.py ruflo-update` detached with no window. The stamp is written first, so sessions and prompts
    that come in together spawn it once."""
    import subprocess
    path = home / "moaa-catalog" / "ruflo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"checked": time.time()}), encoding="utf-8")
    argv = [sys.executable, str(Path(__file__).resolve()), "ruflo-update"]
    quiet = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == "nt":
        subprocess.Popen(argv, creationflags=0x08000000 | 0x00000200, **quiet)  # no window, own process group
    else:
        subprocess.Popen(argv, start_new_session=True, **quiet)


def npm_install(npm, run, spec, prefix=None):
    """`npm install -g` of ruflo with its install scripts allowed. Returns (ok, packages npm still skipped scripts for:
    a new dependency, logged for review rather than allowed)."""
    done = run([npm, "install", "-g", *(["--prefix", str(prefix)] if prefix else []),
                f"--allow-scripts={RUFLO_SCRIPTS}", spec])
    skipped = re.findall(r"allow-scripts\s+(\S+@\S+) \(", (done.stderr or "") + (done.stdout or ""))
    return done.returncode == 0, skipped


def ruflo_update(home, run=None):
    """Install the ruflo CLI globally, or update it when npm has a newer version. Logs to moaa-catalog/ruflo.log. Runs
    inside the windowless background process, so npm and its cmd.exe children get no window either. A lock file keeps
    two updates from running at once."""
    lock = home / "moaa-catalog" / "ruflo.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        if time.time() - lock.stat().st_mtime < RUFLO_LOCK_AGE:
            return "another ruflo update is running"
        lock.unlink()  # stale: its run died
    except OSError:
        pass
    try:
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError:
        return "another ruflo update is running"
    try:
        note = ruflo_install_or_update(run)
    finally:
        lock.unlink(missing_ok=True)
    with open(home / "moaa-catalog" / "ruflo.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {note}\n")
    return note


def ruflo_install_or_update(run=None):
    import shutil
    import subprocess
    run = run or (lambda argv: subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                                              errors="replace", timeout=900))
    npm = shutil.which("npm")
    if not npm:
        return "npm not found"
    have = run([npm, "ls", "-g", "ruflo", "--depth=0", "--json"])
    try:
        installed = json.loads(have.stdout or "{}").get("dependencies", {}).get("ruflo", {}).get("version", "")
    except ValueError:
        installed = ""
    latest = run([npm, "view", "ruflo", "version"]).stdout.strip()
    if not latest:
        return f"npm view failed; ruflo stays at {installed or 'not installed'}"
    if installed and version_tuple(installed) >= version_tuple(latest):
        return f"ruflo {installed} is current"
    if installed:
        return ruflo_swap(npm, installed, latest, run)
    ok, skipped = npm_install(npm, run, f"ruflo@{latest}")  # first install: npm also writes the shims on PATH
    note = f"ruflo none -> {latest}" if ok else f"npm install -g ruflo@{latest} failed"
    return note + (f"; install scripts still skipped for {', '.join(skipped)}" if skipped else "")


def ruflo_swap(npm, installed, latest, run):
    """Update an installed ruflo with no gap. A plain `npm install -g` removes the old copy first, and for the half
    minute it takes ruflo-core's hooks find no CLI, fall back to npx and flash console windows (seen live). So npm
    installs the new version into a staging prefix, and two folder renames swap it in; the shims on PATH stay valid
    because they name node_modules/ruflo/<bin>. A changed bin entry gets a plain install instead."""
    import shutil
    root = Path(run([npm, "root", "-g"]).stdout.strip())  # .../npm/node_modules, or .../lib/node_modules
    target, old, stage = root / "ruflo", root / ".ruflo-old", root.parent / ".moaa-ruflo-stage"
    shutil.rmtree(stage, ignore_errors=True)
    ok, skipped = npm_install(npm, run, f"ruflo@{latest}", prefix=stage)
    new = next((p for p in (stage / "node_modules" / "ruflo", stage / "lib" / "node_modules" / "ruflo")
                if (p / "package.json").is_file()), None)
    if not ok or new is None:
        shutil.rmtree(stage, ignore_errors=True)
        return f"staged install of ruflo@{latest} failed; ruflo stays at {installed}"
    extra = f"; install scripts still skipped for {', '.join(skipped)}" if skipped else ""
    if read_json(new / "package.json").get("bin") != read_json(target / "package.json").get("bin"):
        shutil.rmtree(stage, ignore_errors=True)
        ok, skipped = npm_install(npm, run, f"ruflo@{latest}")
        return (f"ruflo {installed} -> {latest} (plain install: bin changed)" if ok
                else f"npm install -g ruflo@{latest} failed; ruflo may be missing") + extra
    shutil.rmtree(old, ignore_errors=True)
    try:
        os.replace(target, old)
        os.replace(new, target)
    except OSError as e:  # a running hook can hold a file open on Windows: keep the old copy, try again later
        if not target.exists() and old.exists():
            os.replace(old, target)
        shutil.rmtree(stage, ignore_errors=True)
        return f"swap to ruflo@{latest} failed ({e.__class__.__name__}); ruflo stays at {installed}; retry in 3 hours"
    shutil.rmtree(old, ignore_errors=True)
    shutil.rmtree(stage, ignore_errors=True)
    return f"ruflo {installed} -> {latest}" + extra


def main(argv):
    home = claude_home()
    if argv == ["ruflo-update"]:
        print(ruflo_update(home))
        return 0
    if argv[:1] == ["search"] and len(argv) > 1:
        found = search(home, " ".join(argv[1:]))
        catalog = Path(__file__).resolve().as_posix()
        for score, _, s, _ in found:
            print(f"{s['name']}  [{s['pid']}]  score {score:.1f}\n  {s['desc'][:200]}\n  {how(s, catalog)}")
        if not found:
            print("no disabled-plugin skill matches; try other words")
        return 0
    if argv[:1] == ["use"] and len(argv) == 2:
        return use(home, argv[1])
    if argv == ["index"]:
        n = len(load_index(home)["skills"])
        (home / "moaa-catalog" / "index.building").unlink(missing_ok=True)
        print(f"index up to date: {n} skills")
        return 0
    if argv[:1] == ["packs"]:
        counts = {}
        for s in load_index(home)["skills"]:
            if not s.get("on"):
                counts[s["pid"]] = counts.get(s["pid"], 0) + 1
        for pid, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"{n:5d}  {pid}")
        return 0
    if argv == ["hook", "session"]:
        try:
            if stamp(home) != read_json(home / "moaa-catalog" / "index.json").get("stamp"):
                rebuild_in_background(home)  # so the first prompt finds a fresh index
            notice = update_notice(home)
        except Exception:  # a hook must never block the session
            notice = None
        try:
            if ruflo_wanted(home):
                ruflo_update_in_background(home)
        except Exception:
            pass
        if notice:
            print(json.dumps({"systemMessage": notice, "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": notice + " Mention this to the user once, early, in one line."}}))
        return 0
    if argv == ["hook", "prompt"]:
        try:
            context = hook_prompt(home, json.loads(sys.stdin.read() or "{}"))
        except Exception:  # a hook must never block the user's prompt
            context = None
        try:  # long sessions get the 3-hourly ruflo check too
            if ruflo_wanted(home):
                ruflo_update_in_background(home)
        except Exception:
            pass
        if context:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        sys.exit(3)  # the hook command then tries the next interpreter on PATH
    sys.exit(main(sys.argv[1:]))
