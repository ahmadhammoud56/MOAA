#!/usr/bin/env python3
"""MOAA (Mother of All Agents) installer. Standard library only; safe to rerun.

  python scripts/install.py                 core profile: 15 plugins, council, arena, allies, strata, skills, rea MCP
  python scripts/install.py --full          everything: 98 plugins (100 with --with-claude-mem) + ansys MCP; the big
                                            skill packs (agentic-awesome-skills, ruflo extras) install disabled
  python scripts/install.py --profile web   core plus the packs for one kind of work (web, data, devops, research,
                                            science; comma-separated for several), installed and enabled
  python scripts/install.py --prune [--days N] [--yes]  list (and with --yes disable) plugins unused for N days
  python scripts/install.py --mode all-on   every pack enabled; skill listing cut to names + short descriptions
  python scripts/install.py --mode lean     big packs disabled, listing limits restored (moaa-catalog serves them)
  python scripts/install.py --report      local summary: listed skills and tokens, usage, catalog hits, pruned
  python scripts/install.py --lean         on an existing install, disable the packs the catalog ships disabled
  python scripts/install.py --restore       re-enable what --prune or --lean disabled
  python scripts/install.py --with-omniroute  also the OmniRoute gateway (npm), for the allies' free-tier fallback
  python scripts/install.py --with-claude-mem
  python scripts/install.py --skip-mcp      no rea/ansys MCP servers
  python scripts/install.py --skip-ansys    keep rea, skip the ansys MCP server
  python scripts/install.py --dry-run       print what would run, change nothing
  python scripts/install.py --uninstall     reverse what the kit recorded in its manifest
  python scripts/install.py --status        compare the install with this repo: versions, drift, edited copies
  python scripts/install.py --doctor        run every pre-commit check (all test suites, scans, validation)

The Claude config dir is $CLAUDE_CONFIG_DIR or ~/.claude. Existing settings are backed up and merged,
never overwritten: lists are unioned, and env keys and other defaults are only added when absent.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "scripts"))
from sync_catalog import ALIASES  # noqa: E402  reserved upstream names and their moaa catalog aliases
WINDOWS = platform.system() == "Windows"
MANIFEST = ".moaa-manifest.json"
LEGACY_MANIFEST = ".claude-kit-manifest.json"  # pre-rename name; read once, then replaced


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()


def log(msg):
    print(f"[moaa] {msg}", flush=True)


class Runner:
    def __init__(self, dry):
        self.dry = dry
        self.claude = shutil.which("claude")

    def run(self, args, check=False):
        if args[0] == "claude":
            args = [self.claude or "claude"] + args[1:]
        if self.dry:
            log("would run: " + " ".join(args))
            return subprocess.CompletedProcess(args, 0, "", "")
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode:
            raise RuntimeError(f"{' '.join(args)} failed: {(result.stderr or result.stdout).strip()[-500:]}")
        return result


# Subcommands that run without a permission prompt. War Room's toggle, launch, integrate, finish, shutdown and approve,
# allies' run/ask (they spend other services' quotas and can write) and strata's remember/forget/consolidate are left
# out on purpose: those stay the user's own decision. "*" means every subcommand (the council's resolve/check/...).
ALLOWED = {"specialist-council": ("council.py", ("*",)),
           "war-room": ("warroom.py", ("plan", "status", "post", "send", "wake", "app", "list", "measure", "tile",
                                       "merge", "pause", "unpause", "stop", "resume", "demo", "template")),
           "allies": ("allies.py", ("doctor", "runs", "show", "pick")),
           "strata": ("strata.py", ("search", "show", "stats")),
           "moaa-catalog": ("catalog.py", ("search", "use", "packs"))}  # read-only; `use` only serves indexed skills
BARE = {"app", "list", "demo", "template", "doctor", "runs", "stats", "show", "packs"}  # also run with no arguments


def plugin_root(home, plugin):
    """The installed moaa plugin's folder, from Claude Code's own record, or None."""
    entries = (read_json(home / "plugins" / "installed_plugins.json", {}) or {}).get("plugins", {}).get(f"{plugin}@moaa")
    path = (entries or [{}])[0].get("installPath")
    return Path(path) if path else None


def council_permissions(home):
    """Allow rules pinned to each installed script's exact path, as Claude calls it (forward slashes, quoted), with the
    subcommand right after it and only arguments after that. No wildcard comes before the subcommand, so
    `python -c ... warroom.py list` or `allies.py run --task "... allies.py doctor"` never match. When Claude Code updates a
    plugin outside the installer, the path changes and the rules simply stop matching (prompts come back) until the
    installer runs again and replaces them."""
    rules = []
    for plugin, (script, subs) in ALLOWED.items():
        root = plugin_root(home, plugin)
        if not root:
            continue
        path = (root / script).as_posix()
        spellings = [f'"{path}"'] + ([path] if " " not in path else [])
        for spelled in spellings:
            for sub in subs:
                tails = [" *"] if sub == "*" else [f" {sub} *"] + ([f" {sub}"] if sub in BARE else [])
                for tail in tails:
                    rules += [f"Bash({py} {spelled}{tail})" for py in ("python", "python3", "py")]
                    rules += [f"PowerShell({py} {spelled}{tail})" for py in ("python", "py")]
    return rules


def merge_settings(current, kit_settings, allow, plugins):
    """Return (merged, added) without mutating current. `added` lists exactly what uninstall must remove."""
    merged = copy.deepcopy(current)
    added = {"allow": [], "deny": [], "env": [], "defaults": [], "enabledPlugins": []}
    perms = merged.setdefault("permissions", {})
    for key, rules in (("allow", allow), ("deny", kit_settings.get("permissions_deny", []))):
        existing = perms.setdefault(key, [])
        for rule in rules:
            if rule not in existing:
                existing.append(rule)
                added[key].append(rule)
    env = merged.setdefault("env", {})
    for key, value in kit_settings.get("env", {}).items():
        if key not in env:
            env[key] = value
            added["env"].append(key)
    for key, value in kit_settings.get("defaults", {}).items():
        if key not in merged:
            merged[key] = copy.deepcopy(value)
            added["defaults"].append(key)
    enabled = merged.setdefault("enabledPlugins", {})
    for pid, on in plugins.items():
        if pid not in enabled:
            enabled[pid] = on
            added["enabledPlugins"].append(pid)
    return merged, added


def retire_rules(current, added, allow):
    """Drop allow rules MOAA added in an earlier install (recorded in the manifest) that it no longer ships, e.g. the
    pre-0.7 War Room rules whose `app*` also matched `approve`. Rules the user added themselves are never touched."""
    stale = [r for r in added.get("allow", []) if r not in allow]
    if not stale:
        return current, []
    out = copy.deepcopy(current)
    perms = out.get("permissions", {})
    perms["allow"] = [r for r in perms.get("allow", []) if r not in stale]
    added["allow"] = [r for r in added.get("allow", []) if r not in stale]
    return out, stale


def unmerge_settings(current, added):
    merged = copy.deepcopy(current)
    perms = merged.get("permissions", {})
    for key in ("allow", "deny"):
        perms[key] = [r for r in perms.get(key, []) if r not in added.get(key, [])]
    for key in added.get("env", []):
        merged.get("env", {}).pop(key, None)
    for key in added.get("defaults", []):
        merged.pop(key, None)
    for pid in added.get("enabledPlugins", []):
        merged.get("enabledPlugins", {}).pop(pid, None)
    return merged


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path, data, dry):
    if dry:
        log(f"would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def preflight(args):
    problems = []
    if sys.version_info < (3, 10):
        problems.append("Python 3.10+ required")
    for tool in ("claude", "git"):
        if not shutil.which(tool):
            problems.append(f"`{tool}` not found on PATH")
    if not args.skip_mcp and not shutil.which("npx"):
        problems.append("`npx` (Node 20+) not found; install Node or pass --skip-mcp")
    if problems:
        raise SystemExit("[moaa] preflight failed:\n  - " + "\n  - ".join(problems))


def marketplace_names(r):
    out = r.run(["claude", "plugin", "marketplace", "list", "--json"])
    try:
        return {m["name"] for m in json.loads(out.stdout or "[]")}
    except ValueError:
        return set()


def installed_plugins(home):
    return set(read_json(home / "plugins" / "installed_plugins.json", {}).get("plugins", {}))


def parse_profiles(kit, value):
    """['web', 'data'] from '--profile web,data'; unknown names stop the install with the list of valid ones."""
    names = [n.strip() for n in (value or "").split(",") if n.strip()]
    unknown = [n for n in names if n not in kit["work_profiles"]]
    if unknown:
        raise SystemExit(f"[moaa] unknown profile {', '.join(unknown)}; choose from: " + ", ".join(
            f"{k} ({v['summary']})" for k, v in kit["work_profiles"].items()))
    return names


def select_plugins(kit, full, work, with_claude_mem):
    """Catalog entries to install: core (or everything with full), plus each work profile's packs, which are also
    enabled even where the catalog ships them disabled. Copies, so kit stays untouched."""
    wanted = {pid for w in work for pid in kit["work_profiles"][w]["plugins"]}
    out = []
    for p in kit["plugins"]:
        if p.get("optional") and not (with_claude_mem and p["optional"] == "claude-mem"):
            continue
        if full or p.get("profile") == "core" or p["id"] in wanted:
            out.append(dict(p, enabled=True, work=True) if p["id"] in wanted else dict(p))
    return out


def install(args):
    preflight(args)
    home = claude_home()
    r = Runner(args.dry_run)
    kit = read_json(KIT / "config" / "kit.json", None)
    manifest = read_json(home / MANIFEST, None) or read_json(home / LEGACY_MANIFEST, {})
    record = {"kit_version": kit["version"], "kit_dir": str(KIT), "installed": time.time(),
              "marketplaces": manifest.get("marketplaces", []), "plugins": manifest.get("plugins", []),
              "skills": manifest.get("skills", []), "agents": manifest.get("agents", []),
              "mcp": manifest.get("mcp", []), "tools": manifest.get("tools", []),
              "settings_added": manifest.get("settings_added", {}),
              **{k: manifest[k] for k in ("pruned", "mode", "mode_prev", "budget_history") if k in manifest}}
    work = parse_profiles(kit, args.profile)
    plugins = select_plugins(kit, args.full, work, args.with_claude_mem)
    log(f"profile: {'full' if args.full else 'core'}{' + ' + ', '.join(work) if work else ''} ({len(plugins)} plugins)")
    before = installed_plugins(home)

    def target(p):
        """Install id: the pinned moaa catalog entry by default; upstream marketplace with --upstream, or when the
        plugin is already installed from its upstream marketplace (keeps that install and its data untouched)."""
        name, market = p["id"].split("@")
        if market == kit["name"] or args.upstream or p["id"] in before:
            return p["id"]
        return f"{ALIASES.get(name, name)}@{kit['name']}"

    for p in plugins:
        p["target"] = target(p)
    needed = {p["target"].split("@")[1] for p in plugins}

    log(f"Claude home: {home}")
    have = marketplace_names(r)
    sources = dict(kit["marketplaces"], **{kit["name"]: str(KIT)})
    for name, source in sources.items():
        if name not in needed or name in have:
            continue
        log(f"adding marketplace {name}")
        r.run(["claude", "plugin", "marketplace", "add", source, "--scope", "user"], check=True)
        if name not in record["marketplaces"]:
            record["marketplaces"].append(name)
    if kit["name"] in have:  # pick up local edits to the vendored plugins
        r.run(["claude", "plugin", "marketplace", "update", kit["name"]])

    failed = []
    for p in plugins:
        pid = p["target"]
        if pid in before:
            if pid.endswith("@" + kit["name"]) and pid == p["id"]:  # vendored plugins: pick up new versions from this repo
                r.run(["claude", "plugin", "update", pid, "--scope", "user"])
            continue
        log(f"installing {pid}")
        result = r.run(["claude", "plugin", "install", pid, "--scope", "user"])
        if result.returncode:
            failed.append(pid)
            log(f"  FAILED: {(result.stderr or result.stdout).strip()[-300:]}")
            continue
        if pid not in record["plugins"]:
            record["plugins"].append(pid)
        if not p["enabled"]:
            r.run(["claude", "plugin", "disable", pid, "--scope", "user"])
    for p in plugins:  # a profile asked for these: switch them on even if an earlier install or --lean turned them off
        if p.get("work") and p["target"] not in failed:
            r.run(["claude", "plugin", "enable", p["target"], "--scope", "user"])

    skills_dir = home / "skills"
    for name in kit["skills"]:
        target = skills_dir / name
        if target.exists() and name not in record["skills"]:
            if not shipped_by_moaa(name, target):
                log(f"skill {name} already present and not kit-managed; leaving it")
                continue
            log(f"skill {name}: an unmodified earlier MOAA copy; updating")
        log(f"skill {name}")
        if not args.dry_run:
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(KIT / "skills" / name, target, ignore=shutil.ignore_patterns("__pycache__"))
        if name not in record["skills"]:
            record["skills"].append(name)

    council = KIT / "plugins" / "specialist-council" / "council.py"
    log("specialist council: plugin specialist-council@moaa; moving any pre-plugin standalone install")
    if not args.dry_run:
        migrated = r.run([sys.executable, str(council), "migrate", "--home", str(home)], check=True)
        log("  " + " ".join(migrated.stdout.split()))
    if "specialist-council" in record["skills"]:  # now a plugin, no longer a kit-copied skill
        record["skills"].remove("specialist-council")
    for name in kit["agents"]:
        target = home / "agents" / name
        if target.exists() and name not in record["agents"]:
            continue
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(KIT / "agents" / name, target)
        if name not in record["agents"]:
            record["agents"].append(name)

    settings_path = home / "settings.json"
    current = read_json(settings_path, {})
    if settings_path.is_file() and not args.dry_run:
        shutil.copy2(settings_path, settings_path.with_name(f"settings.json.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
    allow = council_permissions(home)
    current, retired = retire_rules(current, record["settings_added"], allow)
    if retired:
        log(f"{'would remove' if args.dry_run else 'removed'} {len(retired)} allow rule(s) an earlier MOAA install "
            "added and no longer uses")
    merged, added = merge_settings(current, kit["settings"], allow, {p["target"]: p["enabled"] for p in plugins})
    for key, values in added.items():
        prior = record["settings_added"].setdefault(key, [])
        prior += [v for v in values if v not in prior]
    write_json(settings_path, merged, args.dry_run)
    log("settings merged (backup written next to settings.json)")

    if not args.skip_mcp:
        wants_ansys = args.full or any(kit["work_profiles"][w].get("ansys") for w in work)
        install_mcp(r, kit["mcp"], record, home, skip_ansys=args.skip_ansys or not wants_ansys, dry=args.dry_run)
    if args.with_omniroute:
        install_omniroute(r, kit["tools"]["omniroute"], record)

    write_json(home / MANIFEST, record, args.dry_run)
    if not args.dry_run:
        (home / LEGACY_MANIFEST).unlink(missing_ok=True)
    check = r.run([sys.executable, str(council), "check"])
    log("council check: " + ("ok" if check.returncode == 0 else check.stderr.strip()))
    if failed:
        log("plugins that failed to install (rerun to retry): " + ", ".join(failed))
    log("done. Restart Claude Code to load new plugins.")
    return 1 if failed or check.returncode else 0


def tree_text(files):
    """{relative posix path: content without CRs}, so a CRLF checkout and an LF copy compare equal."""
    return {k: v.replace(b"\r\n", b"\n") for k, v in files.items()}


def shipped_by_moaa(name, target):
    """True when an installed skill is byte-identical (line endings aside) to a version this repo shipped: an
    install made before the manifest tracked skills. A copy the user edited never matches, so it is left alone."""
    installed = tree_of(target)
    git =lambda *a: subprocess.run(["git", "-C", str(KIT), *a], capture_output=True)  # noqa: E731
    log_ = git("log", "--format=%H", "--", f"skills/{name}")
    for commit in (log_.stdout.decode().split() if log_.returncode == 0 else []):
        paths = git("ls-tree", "-r", "--name-only", commit, f"skills/{name}/").stdout.decode().split("\n")
        shipped = {p[len(f"skills/{name}/"):]: git("show", f"{commit}:{p}").stdout for p in paths if p}
        if tree_text(shipped) == installed:
            return True
    return False


def mcp_outdated(name, spec, record, home):
    """True when MOAA added this MCP server (it is in the manifest) and its configured command or args differ from the
    pinned spec. A server the user configured themselves is never touched."""
    current = (read_json(home.parent / ".claude.json", {}) or {}).get("mcpServers", {}).get(name)
    if not current or (current.get("command"), current.get("args")) == (spec.get("command"), spec.get("args")):
        return False
    if name in record.get("mcp", []):
        return True
    # Installed before the manifest tracked MCP servers: still ours when only the pinned version differs.
    unpin = lambda c: (c.get("command"), [re.sub(r"@\d+(\.\d+)*$", "@*", str(a)) for a in c.get("args") or []])  # noqa: E731
    return unpin(current) == unpin(spec)


def rea_spec(mcp):
    rea = mcp["rea"]
    command, args = (("cmd", ["/c", rea["command"]] + rea["args"]) if WINDOWS else (rea["command"], rea["args"]))
    return {"type": "stdio", "command": command, "args": args, "env": {}}


def install_mcp(r, mcp, record, home, skip_ansys, dry):
    def add(name, spec):
        if r.run(["claude", "mcp", "get", name]).returncode == 0 and not dry:
            if not mcp_outdated(name, spec, record, home):
                log(f"MCP {name} already configured; leaving it")
                return
            log(f"MCP {name}: MOAA installed it at an older pin; updating")  # e.g. rea-agents@6.3.0 -> 6.4.0
            r.run(["claude", "mcp", "remove", "--scope", "user", name])
        log(f"MCP {name}")
        r.run(["claude", "mcp", "add-json", "--scope", "user", name, json.dumps(spec)], check=True)
        if name not in record["mcp"]:
            record["mcp"].append(name)

    add("rea", rea_spec(mcp))
    if skip_ansys:
        return
    spec = mcp["ansys"]
    root = home / "kit-tools" / "ansys-mcp-server"
    log(f"ansys MCP server in {root} (needs a local Ansys install to do real work)")
    if not dry:
        if not (root / ".git").is_dir():
            root.parent.mkdir(parents=True, exist_ok=True)
            r.run(["git", "clone", spec["repo"], str(root)], check=True)
            r.run(["git", "-C", str(root), "checkout", "--quiet", spec["commit"]], check=True)
            r.run(["git", "-C", str(root), "apply", str(KIT / spec["patch"])], check=True)
        venv = root / ".venv"
        if not venv.is_dir():
            r.run([sys.executable, "-m", "venv", str(venv)], check=True)
        python = venv / ("Scripts/python.exe" if WINDOWS else "bin/python")
        pip = r.run([str(python), "-m", "pip", "install", "--quiet", "-r", str(KIT / spec["lock"])])  # tested versions
        if pip.returncode == 0:
            pip = r.run([str(python), "-m", "pip", "install", "--quiet", "--no-deps", "-e", str(root)])
        if pip.returncode:
            log("  ansys pip install failed; skipping ansys MCP: " + pip.stderr.strip()[-300:])
            return
    else:
        python = root / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
    add("ansys", {"type": "stdio", "command": python.as_posix(), "args": ["-m", spec["module"]], "env": {}})


def tree_of(root):
    return tree_text({p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts})


def copy_state(name, repo_path, target, recorded, is_skill):
    """State of an installed skill or agent against this repo's copy, and what the installer would do with it."""
    if not target.exists():
        return "missing", "rerun the installer"
    same = tree_of(target) == tree_of(repo_path) if is_skill else \
        target.read_bytes().replace(b"\r\n", b"\n") == repo_path.read_bytes().replace(b"\r\n", b"\n")
    if same:
        return "ok", ""
    if is_skill and shipped_by_moaa(name, target):
        return "outdated", "an unmodified older MOAA copy; rerun the installer"
    if recorded:
        return "modified", "edited; MOAA recorded it, so the installer will overwrite it"
    return "modified", "edited or your own; the installer leaves it alone"


def status_rows(home, kit):
    """[(kind, name, state, detail)] comparing the install in `home` with this repo. States: ok, outdated (a MOAA
    item older than the repo; rerun the installer), drift (a third-party plugin at another version than the tested
    one), modified (edited after install), missing, info."""
    rows = []

    def read_json(path, default):  # noqa: F811  status reports a corrupt file instead of crashing
        try:
            return globals()["read_json"](path, default)
        except ValueError:
            rows.append(("file", path.name, "corrupt", f"{path} is not valid JSON"))
            return default
    record = read_json(home / MANIFEST, None) or read_json(home / LEGACY_MANIFEST, {})
    if record.get("kit_version") and record["kit_version"] != kit["version"]:
        rows.append(("moaa", "kit", "outdated", f"installed from {record['kit_version']}; repo is {kit['version']}"))
    elif record:
        rows.append(("moaa", "kit", "ok", kit["version"]))
    else:
        rows.append(("moaa", "kit", "missing", f"no {MANIFEST}; the installer has not run for this Claude home"))

    installed = read_json(home / "plugins" / "installed_plugins.json", {}).get("plugins", {})
    by_name = {}
    for p in kit["plugins"]:
        name, market = p["id"].split("@")
        for key in (p["id"], f"{ALIASES.get(name, name)}@{kit['name']}"):
            if key in installed:
                by_name[p["id"]] = (key, (installed[key] or [{}])[0])
                break
    # The profile is not recorded, so a full install is inferred from any full-profile plugin being present.
    full = any(p.get("profile") == "full" and p["id"] in by_name for p in kit["plugins"])
    for p in kit["plugins"]:
        if p["id"] not in by_name:
            if (p.get("profile") == "core" or full) and not p.get("optional"):
                rows.append(("plugin", p["id"], "missing", "rerun the installer"))
            continue
        key, entry = by_name[p["id"]]
        have = entry.get("version", "?")
        if p["id"].endswith("@" + kit["name"]):
            want = read_json(KIT / "plugins" / p["id"].split("@")[0] / ".claude-plugin" / "plugin.json", {}).get("version")
            rows.append(("plugin", key, "ok" if have == want else "outdated",
                         have if have == want else f"installed {have}; repo has {want}"))
            cache = home / "plugins" / "cache" / kit["name"] / p["id"].split("@")[0]
            stale = sorted(d.name for d in cache.iterdir() if d.is_dir() and d.name != have) if cache.is_dir() else []
            if stale:
                rows.append(("cache", key, "info", "old versions left for Claude Code to prune: " + ", ".join(stale)))
        elif have != p["tested_version"]:
            rows.append(("plugin", key, "drift", f"installed {have}; tested {p['tested_version']}"))
        else:
            rows.append(("plugin", key, "ok", have))

    for name in kit["skills"]:
        state, detail = copy_state(name, KIT / "skills" / name, home / "skills" / name, name in record.get("skills", []), True)
        rows.append(("skill", name, state, detail))
    for name in kit["agents"]:
        state, detail = copy_state(name, KIT / "agents" / name, home / "agents" / name, name in record.get("agents", []), False)
        rows.append(("agent", name, state, detail))

    servers = (read_json(home.parent / ".claude.json", {}) or {}).get("mcpServers", {})
    spec = rea_spec(kit["mcp"])
    current = servers.get("rea")
    if not current:
        rows.append(("mcp", "rea", "missing", "rerun the installer (or it was skipped with --skip-mcp)"))
    elif (current.get("command"), current.get("args")) == (spec["command"], spec["args"]):
        rows.append(("mcp", "rea", "ok", kit["mcp"]["rea"]["args"][1]))
    elif mcp_outdated("rea", spec, record, home):
        rows.append(("mcp", "rea", "outdated", f"MOAA's setup at another pin; repo pins {kit['mcp']['rea']['args'][1]}"))
    else:
        rows.append(("mcp", "rea", "modified", "your own setup; the installer leaves it alone"))
    if "ansys" in servers:
        ours = str(home / "kit-tools" / "ansys-mcp-server").replace("\\", "/") in servers["ansys"].get("command", "")
        rows.append(("mcp", "ansys", "ok" if ours else "modified",
                     "" if ours else "configured outside MOAA; the installer leaves it alone"))
    rows.append(context_row(home))
    return rows


def status(args):
    home = claude_home()
    kit = read_json(KIT / "config" / "kit.json", None)
    rows = status_rows(home, kit)
    counts = {}
    for kind, name, state, detail in rows:
        counts[state] = counts.get(state, 0) + 1
        if state != "ok" or kind != "plugin" or name.endswith("@" + kit["name"]) or args.verbose:
            print(f"  {state:<9} {kind:<7} {name:<45} {detail}".rstrip())
    print(f"[moaa] {home}: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
    if counts.get("drift"):
        print("[moaa] drift is informational: upstream-installed plugins move on their own; "
              "`python scripts/sync_catalog.py` re-pins the catalog to what is installed")
    return 1 if counts.get("missing") or counts.get("outdated") else 0


SKILL_BUDGET = 300  # skills listed in every session's context before --status/--doctor warn


def enabled_plugins(home):
    """{plugin id: install path} for every plugin enabled in settings.json and installed."""
    on = {k for k, v in read_json(home / "settings.json", {}).get("enabledPlugins", {}).items() if v}
    installed = read_json(home / "plugins" / "installed_plugins.json", {}).get("plugins", {})
    return {pid: Path((installed[pid] or [{}])[0].get("installPath", "")) for pid in sorted(on) if pid in installed}


def context_budget(home):
    """(skills, agents) that enabled plugins and the user's own folders add to every session's context."""
    roots = [p for p in enabled_plugins(home).values() if p.is_dir()]
    skills = sum(1 for r in roots for _ in r.rglob("SKILL.md")) + sum(1 for _ in (home / "skills").glob("*/SKILL.md"))
    agents = sum(1 for r in roots for _ in (r / "agents").glob("*.md")) + sum(1 for _ in (home / "agents").glob("*.md"))
    return skills, agents


def context_row(home):
    try:
        skills, agents = context_budget(home)
    except ValueError:  # a corrupt settings or plugin record; status reports the file itself
        return ("context", "every session", "info", "not counted: a Claude config file is not valid JSON")
    if listing_settings(home)["skillListingMaxDescChars"] <= 300:  # all-on: many names, short descriptions, by design
        return ("context", "every session", "ok", f"{skills} skills (names + short descriptions), {agents} agents listed")
    state = "heavy" if skills > SKILL_BUDGET else "ok"
    hint = (f"; over {SKILL_BUDGET}: `--mode all-on` trims the listing, `--prune` lists unused plugins"
            if state == "heavy" else "")
    return ("context", "every session", state, f"{skills} skills, {agents} agents listed{hint}")


def plugin_usage(home, days):
    """{plugin name: uses} from transcripts touched in the last `days`: Skill and Agent tool calls named
    `plugin:...`, plugin MCP tools (`mcp__plugin_<name>_...`) and slash commands typed as `/plugin:skill`."""
    cut, uses = time.time() - days * 86400, {}
    slash = re.compile(r"<command-name>/?([\w.-]+):")
    for f in (home / "projects").glob("**/*.jsonl"):
        if f.stat().st_mtime < cut:
            continue
        for line in f.open(encoding="utf-8", errors="replace"):
            if "<command-name>" not in line and '"tool_use"' not in line:
                continue
            try:
                entry = json.loads(line)
                content = entry.get("message", {}).get("content")
            except (ValueError, AttributeError):
                continue
            # a typed slash command is a user message whose text holds the tag; the same text quoted in code doesn't count
            names = slash.findall(content) if entry.get("type") == "user" and isinstance(content, str) else []
            if '"tool_use"' in line:
                for c in content if isinstance(content, list) else []:
                    if c.get("type") != "tool_use":
                        continue
                    name, args = c.get("name", ""), c.get("input") or {}
                    ref = str(args.get("skill") or args.get("subagent_type") or "") if name in ("Skill", "Agent", "Task") else ""
                    if ":" in ref:
                        names.append(ref.split(":")[0])
                    elif name.startswith("mcp__plugin_"):
                        names.append(name.split("__")[1][len("plugin_"):].rsplit("_", 1)[0])
            for n in names:
                uses[n] = uses.get(n, 0) + 1
    return uses


def passive(path):
    """True when a plugin works without being called by name (hooks, output styles, MCP servers): usage counts miss it."""
    meta = read_json(path / ".claude-plugin" / "plugin.json", {}) if path.is_dir() else {}
    return any((path / d).exists() for d in ("hooks", "output-styles", ".mcp.json")) or \
        any(k in meta for k in ("hooks", "mcpServers", "outputStyles"))


def prune_candidates(enabled, uses, kit_name):
    """Enabled plugins with no recorded use, minus passive ones and MOAA's own (the kit decides those)."""
    return [pid for pid, path in enabled.items()
            if not pid.endswith("@" + kit_name) and not uses.get(pid.split("@")[0]) and not passive(path)]


def prune(args):
    """List enabled plugins unused for --days; with --yes, disable them and record them for --restore."""
    home, r = claude_home(), Runner(args.dry_run)
    kit = read_json(KIT / "config" / "kit.json", None)
    candidates = prune_candidates(enabled_plugins(home), plugin_usage(home, args.days), kit["name"])
    before = context_budget(home)
    log(f"{len(candidates)} enabled plugin(s) unused in {args.days} days (hook/MCP plugins and MOAA's own are kept):")
    for pid in candidates:
        print("  " + pid)
    if not candidates or not args.yes:
        log("nothing changed" + ("; rerun with --yes to disable them (--restore undoes it)" if candidates else ""))
        return 0
    record = read_json(home / MANIFEST, {})
    for pid in candidates:
        r.run(["claude", "plugin", "disable", pid, "--scope", "user"])
        if pid not in record.setdefault("pruned", []):
            record["pruned"].append(pid)
    write_json(home / MANIFEST, record, args.dry_run)
    after = context_budget(home)
    log(f"disabled {len(candidates)}; skills listed per session {before[0]} -> {after[0]}. Restart Claude Code.")
    return 0


LISTING_DEFAULTS = {"skillListingMaxDescChars": 1536, "skillListingBudgetFraction": 0.01}  # Claude Code's defaults
ALL_ON_LISTING = {"skillListingMaxDescChars": 200, "skillListingBudgetFraction": 0.003}  # names + short descriptions


def listing_settings(home):
    """The skill-listing limits in effect: settings.json values over Claude Code's defaults."""
    s = read_json(home / "settings.json", {})
    return {k: s.get(k, v) for k, v in LISTING_DEFAULTS.items()}


def listing_tokens(roots, max_desc=1536, fraction=0.01, window=200_000):
    """(skills, rough tokens) the skill listing of these plugin folders adds to every request. Claude Code always
    lists every name; each description is cut to `max_desc` characters and all descriptions together to `fraction`
    of the context window (least-used dropped first). About four characters per token, two per entry for markup."""
    n = names = descs = 0
    for root in roots:
        for md in root.rglob("SKILL.md") if root.is_dir() else []:
            head = md.read_text(encoding="utf-8", errors="replace").split("---", 2)
            meta = head[1] if len(head) > 2 else ""
            found = re.search(r"^description:\s*(.+)$", meta, re.M)
            n, names = n + 1, names + len(md.parent.name)
            descs += min(len(found.group(1)) if found else 0, max_desc)
    return n, names // 4 + 2 * n + min(descs // 4, int(fraction * window))


def skill_names(home, pid, path):
    """Names of the skills a plugin lists. A marketplace entry with a `skills` list (strict: false) loads only those
    folders even though the whole repository is cached, as anthropics/skills' plugins are."""
    if not path.is_dir():
        return set()
    name, _, market = pid.partition("@")
    catalog = read_json(home / "plugins" / "marketplaces" / market / ".claude-plugin" / "marketplace.json", {})
    entry = next((p for p in catalog.get("plugins", []) if p.get("name") == name), {})
    roots = [path / s for s in entry.get("skills", [])] if isinstance(entry.get("skills"), list) else [path]
    return {md.parent.name for r in roots if r.is_dir() for md in r.rglob("SKILL.md")}


def covered_plugins(home, paths):
    """Plugin ids whose every skill another plugin of the same marketplace in `paths` ({id: install path}) already
    lists, such as the agentic-bundle-* subsets of agentic-awesome-skills. Enabling one only lists the same skills
    twice. Only the same marketplace counts: elsewhere a shared name need not mean the same skill. Of two identical
    sets the first id is kept."""
    names = {pid: skill_names(home, pid, p) for pid, p in paths.items()}
    market = {pid: pid.partition("@")[2] for pid in names}
    covered = []
    for pid, mine in names.items():
        if mine and any(other != pid and other not in covered and market[other] == market[pid] and mine <= theirs
                        and (mine < theirs or other < pid) for other, theirs in names.items()):
            covered.append(pid)
    return covered


def report(args):
    """Local, read-only summary: what every session lists, what is used, what the catalog served, what was pruned.
    Nothing leaves the machine. Each run adds a dated budget line to the manifest so the trend shows over time."""
    home = claude_home()
    kit = read_json(KIT / "config" / "kit.json", None)
    enabled = enabled_plugins(home)
    lim = listing_settings(home)
    cap = (lim["skillListingMaxDescChars"], lim["skillListingBudgetFraction"])
    roots = list(enabled.values()) + [home / "skills"]
    skills, tokens = listing_tokens(roots, *cap)
    big = listing_tokens(roots, *cap, window=1_000_000)[1]
    installed = read_json(home / "plugins" / "installed_plugins.json", {}).get("plugins", {})
    off = [Path((v or [{}])[0].get("installPath", "")) for k, v in installed.items() if k not in enabled]
    kept_out, _ = listing_tokens(off)
    all_on = listing_tokens(roots + off, *cap)[1]
    record = read_json(home / MANIFEST, {})
    history = record.setdefault("budget_history", [])
    history.append({"date": time.strftime("%Y-%m-%d"), "skills": skills, "tokens": tokens})
    del history[:-50]
    write_json(home / MANIFEST, record, False)
    print(f"[moaa] report for {home} (MOAA {kit['version']}, mode {record.get('mode', 'default')}; local only)\n")
    print(f"Every request lists {skills} skills from {len(enabled)} enabled plugins: about {tokens:,} tokens on a "
          f"200k-context model, {big:,} on a 1M one (names always; descriptions capped at "
          f"{cap[0]} characters and {cap[1]:.1%} of the window). Budget warning above {SKILL_BUDGET} skills.")
    print(f"Disabled plugins keep {kept_out} skills out of the listing; enabling everything under the current "
          f"limits would list about {all_on:,} tokens (200k model). moaa-catalog serves disabled skills on demand.")
    covered = covered_plugins(home, enabled)
    if covered:
        dupes = listing_tokens([enabled[pid] for pid in covered], *cap)
        print(f"Listed twice: {len(covered)} enabled plugin(s) only repeat skills another enabled plugin lists "
              f"({dupes[0]} skills, about {dupes[1]:,} tokens); `--mode all-on` leaves them off.")
    print("Exact figures: run /context in a fresh session (the Skills row).")
    if len(history) > 1:
        print("Trend: " + "  ".join(f"{h['date']} {h['skills']}" for h in history[-6:]))
    uses = plugin_usage(home, args.days)
    top = sorted(((n, name) for name, n in uses.items()), reverse=True)[:10]
    print(f"\nMost used in {args.days} days (skill, agent, MCP and slash-command calls):")
    print("\n".join(f"  {n:5d}  {name}" for n, name in top) or "  none recorded")
    log_file = home / "moaa-catalog" / "usage.jsonl"
    served = {}
    for line in log_file.read_text(encoding="utf-8").splitlines() if log_file.is_file() else []:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        served[e.get("skill", "?")] = served.get(e.get("skill", "?"), 0) + 1
    print("\nServed by moaa-catalog: " + (", ".join(f"{k} x{v}" for k, v in sorted(served.items(), key=lambda kv: -kv[1])[:10])
                                         or "nothing yet"))
    pruned = record.get("pruned", [])
    print(f"Disabled by --prune/--lean: {len(pruned)} plugin(s)" + ("; `--restore` re-enables them" if pruned else ""))
    idle = prune_candidates(enabled, uses, kit["name"])
    if idle:
        print(f"Still enabled but unused in {args.days} days: {len(idle)} (`--prune --yes` disables them)")
    return 0


def lean(args):
    """Bring an existing install in line with the catalog: disable every plugin kit.json ships disabled (the big
    skill packs) that is still enabled here. Recorded like --prune, so --restore undoes it."""
    home, r = claude_home(), Runner(args.dry_run)
    kit = read_json(KIT / "config" / "kit.json", None)
    enabled = enabled_plugins(home)
    off = [p["id"] for p in kit["plugins"] if p.get("pack") and p["id"] in enabled]
    before = context_budget(home)
    record = read_json(home / MANIFEST, {})
    if args.dry_run:
        log(f"would disable {len(off)}: " + ", ".join(off))
        return 0
    for pid in off:
        log(f"disabling {pid}")
        r.run(["claude", "plugin", "disable", pid, "--scope", "user"])
        if pid not in record.setdefault("pruned", []):
            record["pruned"].append(pid)
    write_json(home / MANIFEST, record, args.dry_run)
    log(f"disabled {len(off)}; skills listed per session {before[0]} -> {context_budget(home)[0]}. "
        "moaa-catalog still finds their skills. Restart Claude Code.")
    return 0


def mode(args):
    """--mode all-on: every MOAA pack and pruned plugin enabled (hooks, agents, MCP, commands all live) with the skill
    listing cut to names plus short descriptions; moaa-catalog supplies full descriptions on a matching prompt.
    --mode lean: packs disabled, listing limits back to what they were. Settings are backed up first."""
    home, r = claude_home(), Runner(args.dry_run)
    kit = read_json(KIT / "config" / "kit.json", None)
    record = read_json(home / MANIFEST, {})
    settings_path = home / "settings.json"
    settings = read_json(settings_path, {})
    if args.mode == "all-on":
        if record.get("mode") != "all-on":
            record["mode_prev"] = {k: settings.get(k) for k in ALL_ON_LISTING}
        installed, enabled = installed_plugins(home), enabled_plugins(home)
        # every catalog plugin meant to be on (packs included), not optional ones the user opts into (claude-mem)
        turn_on = [p["id"] for p in kit["plugins"] if (p.get("pack") or p["enabled"]) and not p.get("optional")
                   and p["id"] in installed and p["id"] not in enabled]
        turn_on += [pid for pid in record.get("pruned", []) if pid in installed and pid not in turn_on + list(enabled)]
        # a plugin whose skills another one already lists would only repeat them: leave it off (--restore enables it)
        paths = {pid: Path((installed[pid] or [{}])[0].get("installPath", "")) for pid in turn_on}
        covered = covered_plugins(home, {**enabled, **paths})
        turn_on = [pid for pid in turn_on if pid not in covered]
        turn_off = [pid for pid in covered if pid in enabled]
        if args.dry_run:
            log(f"would enable {len(turn_on)} plugin(s), leave off {len(covered)} that repeat other plugins' skills "
                f"and set {ALL_ON_LISTING}")
            return 0
        for pid in turn_on:
            log(f"enabling {pid}")
            r.run(["claude", "plugin", "enable", pid, "--scope", "user"])
        for pid in turn_off:
            log(f"disabling {pid} (its skills are already listed by another plugin)")
            r.run(["claude", "plugin", "disable", pid, "--scope", "user"])
        settings = read_json(settings_path, {})  # the CLI just rewrote enabledPlugins
        shutil.copy2(settings_path, settings_path.with_name(f"settings.json.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
        settings.update(ALL_ON_LISTING)
        record["pruned"], record["mode"] = turn_off, "all-on"
    else:
        lean(args)
        if args.dry_run:
            return 0
        record = read_json(home / MANIFEST, {})  # lean() recorded what it disabled
        settings = read_json(settings_path, {})
        shutil.copy2(settings_path, settings_path.with_name(f"settings.json.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
        for k, v in record.pop("mode_prev", {}).items():
            if v is None:
                settings.pop(k, None)
            else:
                settings[k] = v
        record["mode"] = "lean"
    write_json(settings_path, settings, False)
    write_json(home / MANIFEST, record, False)
    lim = listing_settings(home)
    n, tokens = listing_tokens(list(enabled_plugins(home).values()) + [home / "skills"],
                               lim["skillListingMaxDescChars"], lim["skillListingBudgetFraction"])
    log(f"mode {record['mode']}: {n} skills listed, about {tokens:,} tokens per request (200k model). "
        "Restart Claude Code.")
    return 0


def restore(args):
    """Re-enable every plugin an earlier --prune disabled."""
    home, r = claude_home(), Runner(args.dry_run)
    record = read_json(home / MANIFEST, {})
    for pid in record.get("pruned", []):
        log(f"enabling {pid}")
        r.run(["claude", "plugin", "enable", pid, "--scope", "user"])
    record["pruned"] = []
    write_json(home / MANIFEST, record, args.dry_run)
    return 0


def doctor_checks():
    """(label, argv, cwd) for every check the release routine runs before a commit."""
    py = sys.executable
    plugins = KIT / "plugins"
    checks = [("installer tests", [py, "-m", "unittest", "discover", "-s", "tests"], KIT)]
    for name in ("specialist-council", "agent-arena-mode", "war-room", "allies", "strata", "moaa-catalog"):
        checks.append((f"{name} tests", [py, "-m", "unittest", "discover", "-s", "tests"], plugins / name))
    checks += [
        ("war-room bus test", [py, "tests/test_bus.py"], plugins / "war-room"),
        ("MODELS.md matches the plugins", [py, "scripts/models_doc.py", "--check"], KIT),
        ("catalog matches installed plugins", [py, "scripts/sync_catalog.py", "--check"], KIT),
        ("public-release scan", [py, "scripts/scan.py", "--public"], KIT),
        ("validate marketplace", ["claude", "plugin", "validate", "."], KIT),
    ]
    checks += [(f"validate {d.name}", ["claude", "plugin", "validate", str(d)], KIT)
               for d in sorted(plugins.iterdir()) if (d / ".claude-plugin" / "plugin.json").is_file()]
    return checks


def doctor(args):
    failed = []
    claude = shutil.which("claude")
    for label, argv, cwd in doctor_checks():
        if argv[0] == "claude":
            if not claude:
                print(f"  SKIP  {label} (claude not on PATH)")
                continue
            argv = [claude] + argv[1:]
        started = time.time()
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = result.returncode == 0
        print(f"  {'PASS' if ok else 'FAIL'}  {label} ({time.time() - started:.1f}s)", flush=True)
        if not ok:
            failed.append(label)
            tail = (result.stdout + result.stderr).strip().splitlines()[-15:]
            print("        " + "\n        ".join(tail))
    if (claude_home() / "plugins" / "installed_plugins.json").is_file():  # informational; never fails the doctor
        _, _, state, detail = context_row(claude_home())
        print(f"  {'WARN' if state == 'heavy' else 'INFO'}  context budget: {detail}")
    print(f"[moaa] doctor: {'all checks pass' if not failed else 'failed: ' + ', '.join(failed)}")
    return 1 if failed else 0


def install_omniroute(r, spec, record):
    """npm install of the pinned OmniRoute. It is not started: `allies.py omniroute start` runs it with locked-down
    settings (loopback only, API key required, generated dashboard password)."""
    if not shutil.which("npm"):
        log("omniroute: npm not found; skipped")
        return
    pkg = f"{spec['npm']}@{spec['version']}"
    npm = ["npm"] if not WINDOWS else ["cmd", "/c", "npm"]
    had = r.run(npm + ["ls", "-g", spec["npm"], "--depth=0"]).returncode == 0 and "omniroute" not in record["tools"]
    log(f"omniroute: npm install -g {pkg} (start it with allies.py omniroute start)")
    result = r.run(["npm", "install", "-g", pkg] if not WINDOWS else ["cmd", "/c", "npm", "install", "-g", pkg])
    if result.returncode:
        log("  omniroute install failed: " + (result.stderr or result.stdout).strip()[-300:])
    elif had:
        log("  omniroute was already installed before MOAA; --uninstall will leave it")
    elif "omniroute" not in record["tools"]:
        record["tools"].append("omniroute")


def uninstall(args):
    home = claude_home()
    r = Runner(args.dry_run)
    record = read_json(home / MANIFEST, None) or read_json(home / LEGACY_MANIFEST, None)
    if not record:
        raise SystemExit(f"[moaa] no manifest at {home / MANIFEST}; nothing recorded to undo")
    for name in record.get("mcp", []):
        r.run(["claude", "mcp", "remove", name, "--scope", "user"])
    for name in record.get("tools", []):  # npm tools MOAA installed (omniroute)
        r.run(["npm", "uninstall", "-g", name] if not WINDOWS else ["cmd", "/c", "npm", "uninstall", "-g", name])
    for pid in record.get("plugins", []):
        log(f"uninstalling {pid}")
        r.run(["claude", "plugin", "uninstall", pid, "--scope", "user"])
    for name in record.get("marketplaces", []):
        r.run(["claude", "plugin", "marketplace", "remove", name])
    for name in record.get("skills", []):
        log(f"removing skill {name}")
        target = home / "skills" / name
        if args.dry_run or not target.is_dir():
            continue
        for child in target.iterdir():  # forged council members are user data from the arena; keep them
            if child.name == "forged":
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        if not any(target.iterdir()):
            target.rmdir()
    for path in [Path(a) for a in record.get("agents", [])]:  # council agents leave with the plugin
        target = home / "agents" / path.name
        if target.is_file() and not args.dry_run:
            target.unlink()
    settings_path = home / "settings.json"
    settings = unmerge_settings(read_json(settings_path, {}), record.get("settings_added", {}))
    for k, v in record.get("mode_prev", {}).items():  # undo --mode all-on's listing limits
        settings.pop(k, None) if v is None else settings.__setitem__(k, v)
    write_json(settings_path, settings, args.dry_run)
    if not args.dry_run:
        (home / MANIFEST).unlink(missing_ok=True)
        (home / LEGACY_MANIFEST).unlink(missing_ok=True)
    log("uninstalled. Arena library data and forged council members (if any) were left in place.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--with-claude-mem", action="store_true")
    p.add_argument("--with-omniroute", action="store_true",
                   help="also install the OmniRoute gateway (npm) used by allies for free-tier fallback; not started")
    p.add_argument("--full", action="store_true",
                   help="install all 98 plugins and the ansys MCP server (default: the 15-plugin core profile)")
    p.add_argument("--profile", default="",
                   help="add packs for a kind of work on top of core (or full), enabled: web, data, devops, research, "
                        "science; comma-separated for several")
    p.add_argument("--upstream", action="store_true",
                   help="install third-party plugins from their own marketplaces (latest) instead of the pinned moaa catalog")
    p.add_argument("--skip-mcp", action="store_true")
    p.add_argument("--skip-ansys", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--status", action="store_true",
                   help="compare what is installed with this repo (changes nothing; exit 1 if anything is missing or outdated)")
    p.add_argument("--verbose", action="store_true", help="with --status: also list third-party plugins that match")
    p.add_argument("--doctor", action="store_true", help="run every pre-commit check of the release routine")
    p.add_argument("--prune", action="store_true",
                   help="list enabled plugins unused for --days (changes nothing without --yes)")
    p.add_argument("--days", type=int, default=45, help="with --prune: usage window in days (default 45)")
    p.add_argument("--yes", action="store_true", help="with --prune: disable the listed plugins")
    p.add_argument("--restore", action="store_true", help="re-enable every plugin --prune or --lean disabled")
    p.add_argument("--mode", choices=("all-on", "lean"),
                   help="all-on: every pack enabled, skill listing cut to names + short descriptions; "
                        "lean: big packs disabled, listing limits restored")
    p.add_argument("--report", action="store_true",
                   help="local summary: listed skills and tokens, most used plugins, catalog hits, pruned plugins")
    p.add_argument("--lean", action="store_true",
                   help="disable the plugins the catalog ships disabled (big skill packs) on an existing install")
    a = p.parse_args(argv)
    if a.status:
        return status(a)
    if a.doctor:
        return doctor(a)
    if a.prune:
        return prune(a)
    if a.restore:
        return restore(a)
    if a.mode:
        return mode(a)
    if a.lean:
        return lean(a)
    if a.report:
        return report(a)
    return uninstall(a) if a.uninstall else install(a)


if __name__ == "__main__":
    sys.exit(main())
