#!/usr/bin/env python3
"""Specialist Council model/effort profile tool. Standard library only.

Ships as the `specialist-council` Claude Code plugin (agents/, skills/specialist-council/, this file, profile.json).
Arena-forged members live outside the plugin, in ~/.claude/specialist-council/forged/ (registry + knowledge bases)
and ~/.claude/agents/council-forged-<slug>.md, so plugin updates never touch them.

Commands:
  check    [--agents DIR]             verify the 60 role agents match profile.json, plus every forged member
  apply    [--agents DIR]             write model/effort frontmatter from profile.json
  resolve  --role ID [--style S1,S2]  print model/effort for a role or a forged member (forged-<slug>)
  render   --out FILE                 write the generated model-profile reference
  diff     [--against REF|FILE]       role, team and tier-mix changes against a git ref (default HEAD) or a file
  migrate  [--home ~/.claude]         move a pre-plugin standalone install (skill, 60 user agents, forged/) to the plugin layout
"""
import argparse
import json
from pathlib import Path
import re
import os
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parent
TIERS = ("haiku", "sonnet", "opus", "fable")
SKILL = ROOT / "skills" / "specialist-council"
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


class CouncilError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise CouncilError(message)


def load_profile(path=ROOT / "profile.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def personality_ids(skill_dir=SKILL):
    text = (Path(skill_dir) / "references" / "personalities.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| [^|]+ / ([a-z-]+) \|", text, re.M))


def validate(profile, agent_ids, styles):
    levels = profile["effort_levels"]
    require(set(profile["models"]) == set(TIERS), "models must map exactly haiku, sonnet, opus, fable")
    require(profile["effort_ceiling"] in levels, "effort_ceiling must be a known level")
    roles = profile["roles"]
    require(set(roles) == set(agent_ids), "profile roles and agent files differ: " +
            ", ".join(sorted(set(roles) ^ set(agent_ids))))
    for rid, role in roles.items():
        require(role["tier"] in TIERS, f"{rid}: unknown tier {role['tier']}")
        require(role["effort"] in levels, f"{rid}: unknown effort {role['effort']}")
        require(role.get("why", "").strip(), f"{rid}: rationale required")
    shifts = profile["personality_effort_shift"]
    require(set(shifts) == set(styles), "personality shifts and personalities.md differ: " +
            ", ".join(sorted(set(shifts) ^ set(styles))))
    require(all(type(v) is int and -2 <= v <= 2 for v in shifts.values()), "shifts must be integers in [-2, 2]")
    for team, members in profile["teams"].items():
        for member in members:
            require(member[0] in roles, f"{team}: unknown role {member[0]}")
            require(len(member) <= 3 and all(s in shifts for s in member[1:]), f"{team}: bad personalities {member[1:]}")


def resolve(profile, role_id, styles=()):
    """Role preset plus personality effort shift; personalities never change the model tier."""
    role = profile["roles"].get(role_id)
    require(role is not None, f"Unknown role {role_id}")
    require(len(styles) <= 2, "Use at most two personalities")
    levels = profile["effort_levels"]
    shift = sum(profile["personality_effort_shift"][s] for s in styles)
    base = levels.index(role["effort"])
    ceiling = max(levels.index(profile["effort_ceiling"]), base)  # never lower an explicit preset
    effort = levels[min(max(base + shift, 0), ceiling)]
    return {"role": role_id, "styles": list(styles), "tier": role["tier"],
            "model": profile["models"][role["tier"]], "effort": effort, "base_effort": role["effort"]}


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()


def forged_home(home=None):
    """Where arena-forged members are registered: $COUNCIL_FORGED_DIR or <claude home>/specialist-council/forged."""
    if os.environ.get("COUNCIL_FORGED_DIR") and home is None:
        return Path(os.environ["COUNCIL_FORGED_DIR"]).expanduser()
    return Path(home or claude_home()) / "specialist-council" / "forged"


def forged_member(role_id, forged_dir=None):
    """Registry entry for a forged role given as `slug`, `forged-<slug>` or `council-forged-<slug>`, else None."""
    registry = Path(forged_dir or forged_home()) / "registry.json"
    if not role_id or not registry.is_file():
        return None
    slug = re.sub(r"^(council-)?forged-", "", role_id)
    return json.loads(registry.read_text(encoding="utf-8")).get(slug)


def resolve_forged(profile, role_id, member, styles=()):
    """Forged members keep their validated model; personalities shift effort exactly as for preset roles."""
    require(member.get("status") == "active", f"Forged member {role_id} is {member.get('status')}; do not dispatch it")
    require(len(styles) <= 2, "Use at most two personalities")
    levels = profile["effort_levels"]
    base = levels.index(member["effort"])
    ceiling = max(levels.index(profile["effort_ceiling"]), base)
    effort = levels[min(max(base + sum(profile["personality_effort_shift"][s] for s in styles), 0), ceiling)]
    return {"role": role_id, "agent": member.get("agent") or "council-forged-" + re.sub(r"^(council-)?forged-", "", role_id), "styles": list(styles), "forged": True,
            "model": member["model"], "effort": effort, "base_effort": member["effort"]}


def agent_files(agents_dir):
    return {p.stem[len("council-"):]: p for p in sorted(Path(agents_dir).glob("council-*.md"))
            if not p.stem.startswith("council-forged-")}


def set_frontmatter(text, model, effort):
    match = FRONT.match(text)
    require(match, "Agent file lacks YAML frontmatter")
    lines = [l for l in match.group(1).split("\n") if not re.match(r"(model|effort):", l)]
    lines += [f'model: "{model}"', f'effort: "{effort}"']
    return "---\n" + "\n".join(lines) + "\n---\n" + text[match.end():]


def frontmatter_value(text, key):
    match = re.search(rf'^{key}:\s*"?([^"\n]+)"?\s*$', FRONT.match(text).group(1), re.M)
    return match.group(1) if match else None


def apply(agents_dir, profile):
    changed = []
    for rid, path in agent_files(agents_dir).items():
        role = profile["roles"][rid]
        old = path.read_text(encoding="utf-8")
        new = set_frontmatter(old, profile["models"][role["tier"]], role["effort"])
        if new != old:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(rid)
    return changed


def check(agents_dir, profile, skill_dir=SKILL, user_agents=None, forged_dir=None):
    files = agent_files(agents_dir)
    validate(profile, files, personality_ids(skill_dir))
    wrong = []
    for rid, path in files.items():
        text = path.read_text(encoding="utf-8")
        role = profile["roles"][rid]
        if (frontmatter_value(text, "model"), frontmatter_value(text, "effort")) != \
                (profile["models"][role["tier"]], role["effort"]):
            wrong.append(rid)
    require(not wrong, "Agents not matching profile: " + ", ".join(wrong))
    forged = check_forged(user_agents or claude_home() / "agents", profile, forged_dir)
    return {"agents": len(files), "forged": forged, "ok": True}


def check_forged(agents_dir, profile, forged_dir=None):
    """Arena-forged members: only active registry entries may have a registered agent card, and it must match."""
    forged = Path(forged_dir or forged_home())
    registry_path = forged / "registry.json"
    cards = {p.stem[len("council-forged-"):]: p for p in Path(agents_dir).glob("council-forged-*.md")}
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {}
    problems = []
    for slug, member in registry.items():
        card = cards.pop(slug, None)
        if member.get("status") != "active":
            if card:
                problems.append(f"{slug}: {member.get('status')} but agent card still registered")
            continue
        if not card:
            problems.append(f"{slug}: active but agent card missing")
            continue
        text = card.read_text(encoding="utf-8")
        if not FRONT.match(text):
            problems.append(f"{slug}: agent card lacks frontmatter")
            continue
        if frontmatter_value(text, "name") != f"council-forged-{slug}":
            problems.append(f"{slug}: card name mismatch")
        if member.get("model") not in profile["models"].values():
            problems.append(f"{slug}: unknown model {member.get('model')}")
        if member.get("effort") not in profile["effort_levels"]:
            problems.append(f"{slug}: unknown effort {member.get('effort')}")
        if (frontmatter_value(text, "model"), frontmatter_value(text, "effort")) != (member.get("model"), member.get("effort")):
            problems.append(f"{slug}: card model/effort differ from registry")
        if not (forged / slug / "profile.json").is_file():
            problems.append(f"{slug}: knowledge base missing")
    problems += [f"{slug}: agent card has no registry entry" for slug in cards]
    require(not problems, "Forged members invalid: " + "; ".join(problems))
    return {"active": sum(m.get("status") == "active" for m in registry.values()), "total": len(registry)}


def render(profile):
    out = ["# Model and effort profile", "",
           "Generated from `profile.json` by `council.py render`. Do not edit by hand.", "",
           "Each `specialist-council:council-<role>` plugin agent carries this model and effort in its frontmatter. "
           "A personality shifts effort only (never the model), clamped to "
           f"`{profile['effort_ceiling']}` unless the role preset is already higher. "
           "Apply the resolved effort through the Agent tool's per-call `effort` field when the host exposes it; "
           "otherwise the frontmatter value applies and the shift is reported as requested only. "
           "An explicit user model or effort request overrides this table.", "",
           "## Tier policy", ""]
    out += [f"- **{t}** (`{profile['models'][t]}`): {profile['policy'][t]}" for t in TIERS]
    out += [f"- **Effort**: {profile['policy']['effort']}", "", "## Roles", "",
            "| Role | Model | Effort | Why |", "|---|---|---|---|"]
    order = {t: i for i, t in enumerate(reversed(TIERS))}
    for rid, r in sorted(profile["roles"].items(), key=lambda kv: (order[kv[1]["tier"]], kv[0])):
        out.append(f"| {rid} | {r['tier']} | {r['effort']} | {r['why']} |")
    out += ["", "## Personality effort shifts", "", "| Personality | Shift |", "|---|---|"]
    out += [f"| {s} | {v:+d} |" for s, v in sorted(profile["personality_effort_shift"].items())]
    out += ["", "## Team presets (resolved)", ""]
    for team, members in profile["teams"].items():
        cells = []
        for m in members:
            r = resolve(profile, m[0], m[1:])
            style = (" + " + " + ".join(m[1:])) if m[1:] else ""
            cells.append(f"{m[0]}{style} → {r['tier']}/{r['effort']}")
        judge = resolve(profile, "arbiter")
        out.append(f"- **{team}**: " + "; ".join(cells) + f"; judge arbiter → {judge['tier']}/{judge['effort']}")
    return "\n".join(out) + "\n"


def base_profile(against):
    """The profile to compare with: a file path, or a git ref (default HEAD) of this plugin's profile.json."""
    if Path(against).is_file():
        profile = load_profile(against)
        require(all(k in profile for k in ("models", "roles", "teams")), f"{against} is not a council profile")
        return profile
    import subprocess
    out = subprocess.run(["git", "-C", str(ROOT), "show", f"{against}:./profile.json"], capture_output=True)
    require(out.returncode == 0, f"cannot read profile.json at {against!r}: "
            + (out.stderr.decode(errors="replace").strip() or "not a git checkout"))
    profile = json.loads(out.stdout.decode("utf-8"))
    require(all(k in profile for k in ("models", "roles", "teams")), f"profile.json at {against} lacks models, roles or teams")
    return profile


def diff(old, new):
    """Role, team and tier-mix changes between two profiles. Tier counts are how the council's work shifts between
    price tiers; actual cost also depends on how often each role is dispatched, so no dollar figure is given."""
    roles = []
    for rid in sorted(set(old["roles"]) | set(new["roles"])):
        a, b = old["roles"].get(rid), new["roles"].get(rid)
        if a is None or b is None or (a["tier"], a["effort"]) != (b["tier"], b["effort"]):
            roles.append({"role": rid, "from": a and f"{a['tier']}/{a['effort']}", "to": b and f"{b['tier']}/{b['effort']}"})
    teams = []
    for team in sorted(set(old["teams"]) | set(new["teams"])):
        def resolved(p):
            if team not in p["teams"]:
                return None
            return [f"{m[0]} {resolve(p, m[0], m[1:])['tier']}/{resolve(p, m[0], m[1:])['effort']}" for m in p["teams"][team]]
        a, b = resolved(old), resolved(new)
        if a != b:
            teams.append({"team": team, "from": a, "to": b})
    count = lambda p: {t: sum(r["tier"] == t for r in p["roles"].values()) for t in TIERS}  # noqa: E731
    models = {t: (old["models"][t], new["models"][t]) for t in TIERS if old["models"][t] != new["models"][t]}
    return {"roles": roles, "teams": teams, "models": models, "tiers": {"from": count(old), "to": count(new)}}


def diff_text(d):
    out = []
    for t, (a, b) in d["models"].items():
        out.append(f"model {t}: {a} -> {b}")
    out += [f"role {r['role']}: {r['from'] or '(new)'} -> {r['to'] or '(removed)'}" for r in d["roles"]]
    for t in d["teams"]:
        out.append(f"team {t['team']}:")
        a, b = t["from"] or [], t["to"] or []
        out += [f"  {x} -> {y}" for x, y in zip(a, b) if x != y]
        out += [f"  + {y}" for y in b[len(a):]] + [f"  - {x}" for x in a[len(b):]]
    f, t = d["tiers"]["from"], d["tiers"]["to"]
    out.append("roles per tier: " + ", ".join(f"{k} {f[k]}" + (f" -> {t[k]} ({t[k] - f[k]:+d})" if t[k] != f[k] else "")
                                              for k in TIERS))
    return "\n".join(out) if d["roles"] or d["teams"] or d["models"] else "no preset changes\n" + out[-1]


def migrate(home, profile):
    """Move a pre-plugin standalone install to the plugin layout. Forged members are kept; old files are backed up."""
    home = Path(home).expanduser().resolve()
    legacy = home / "skills" / "specialist-council"
    target = forged_home(home)
    moved = {"forged": False, "agents": 0, "skill": False}
    backup = home / "specialist-council" / f"pre-plugin-backup-{time.strftime('%Y%m%d-%H%M%S')}"
    if (legacy / "forged").is_dir() and not (target / "registry.json").is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(legacy / "forged", target, dirs_exist_ok=True)
        moved["forged"] = True
    if (legacy / "SKILL.md").is_file():  # the standalone skill would duplicate the plugin's skill
        backup.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(backup / "skill"))
        moved["skill"] = True
    elif legacy.is_dir() and moved["forged"]:
        shutil.rmtree(legacy)
    for rid in profile["roles"]:  # user-level copies of the 60 role agents would duplicate the plugin agents
        card = home / "agents" / f"council-{rid}.md"
        if card.is_file():
            (backup / "agents").mkdir(parents=True, exist_ok=True)
            shutil.move(str(card), str(backup / "agents" / card.name))
            moved["agents"] += 1
    if moved["forged"]:  # knowledge-base paths recorded in the registry point at the old folder
        registry = target / "registry.json"
        data = json.loads(registry.read_text(encoding="utf-8"))
        for slug, member in data.items():
            member["knowledge_base"] = (target / slug).as_posix()
            card = home / "agents" / f"council-forged-{slug}.md"
            if card.is_file():
                card.write_text(card.read_text(encoding="utf-8").replace((legacy / "forged" / slug).as_posix(),
                                (target / slug).as_posix()), encoding="utf-8", newline=chr(10))
        registry.write_text(json.dumps(data, indent=2), encoding="utf-8")
    moved["backup"] = str(backup) if backup.exists() else None
    moved["forged_home"] = str(target)
    return moved


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=("check", "apply", "resolve", "render", "diff", "migrate"))
    p.add_argument("--agents", default=str(ROOT / "agents"))
    p.add_argument("--profile", default=str(ROOT / "profile.json"))
    p.add_argument("--role")
    p.add_argument("--style", default="")
    p.add_argument("--out")
    p.add_argument("--home", default=str(claude_home()))
    p.add_argument("--against", default="HEAD", help="diff: git ref or profile file to compare with")
    p.add_argument("--json", action="store_true", help="diff: print JSON")
    a = p.parse_args(argv)
    try:
        profile = load_profile(a.profile)
        if a.command == "check":
            result = check(a.agents, profile)
        elif a.command == "apply":
            validate(profile, agent_files(a.agents), personality_ids())
            result = {"changed": apply(a.agents, profile)}
        elif a.command == "resolve":
            styles = [s for s in a.style.split(",") if s]
            forged = forged_member(a.role)
            result = resolve_forged(profile, a.role, forged, styles) if forged else resolve(profile, a.role, styles)
        elif a.command == "render":
            text = render(profile)
            if a.out:
                Path(a.out).write_text(text, encoding="utf-8", newline="\n")
            result = {"written": a.out} if a.out else text
        elif a.command == "diff":
            d = diff(base_profile(a.against), profile)
            result = d if a.json else diff_text(d)
        else:
            result = migrate(a.home, profile)
        print(result if isinstance(result, str) else json.dumps(result, indent=2))
        return 0
    except (CouncilError, KeyError, OSError, ValueError) as exc:
        print(f"council: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
