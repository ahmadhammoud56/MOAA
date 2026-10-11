#!/usr/bin/env python3
"""Specialist Council model/effort profile tool. Standard library only.

Commands:
  check    --agents DIR             verify every council agent matches profile.json
  apply    --agents DIR             write model/effort frontmatter from profile.json
  resolve  --role ID [--style S1,S2]  print model/effort for one (role, personality) pair
  render   --out FILE               write the generated model-profile reference
  install  --home ~/.claude         apply + render, then copy skill and agents (keeps forged members)
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
TIERS = ("haiku", "sonnet", "opus", "fable")
SKILL = ROOT / "skill" if (ROOT / "skill").is_dir() else ROOT  # source package vs installed skill folder
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


def check(agents_dir, profile, skill_dir=SKILL):
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
    return {"agents": len(files), "forged": check_forged(agents_dir, profile, skill_dir), "ok": True}


def check_forged(agents_dir, profile, skill_dir=SKILL):
    """Arena-forged members: only active registry entries may have a registered agent card, and it must match."""
    forged = Path(skill_dir) / "forged"
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
           "Each registered `council-<role>` agent carries this model and effort in its frontmatter. "
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


def install(home, profile):
    home = Path(home).expanduser().resolve()
    apply(ROOT / "agents", profile)
    (ROOT / "skill" / "references" / "model-profile.md").write_text(render(profile), encoding="utf-8", newline="\n")
    check(ROOT / "agents", profile)
    skill_target = home / "skills" / "specialist-council"
    forged = skill_target / "forged"
    keep = None
    if forged.is_dir():  # forged members come from the arena; never discard them on reinstall
        keep = home / "skills" / ".specialist-council-forged.keep"
        shutil.rmtree(keep, ignore_errors=True)
        shutil.copytree(forged, keep)
    if skill_target.exists():
        shutil.rmtree(skill_target)
    shutil.copytree(ROOT / "skill", skill_target)
    shutil.copy2(ROOT / "profile.json", skill_target / "profile.json")
    shutil.copy2(ROOT / "council.py", skill_target / "council.py")
    if keep:
        shutil.copytree(keep, forged)
        shutil.rmtree(keep)
    (home / "agents").mkdir(parents=True, exist_ok=True)
    for path in agent_files(ROOT / "agents").values():
        shutil.copy2(path, home / "agents" / path.name)
    return check(home / "agents", profile, skill_target)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=("check", "apply", "resolve", "render", "install"))
    p.add_argument("--agents", default=str(ROOT / "agents"))
    p.add_argument("--profile", default=str(ROOT / "profile.json"))
    p.add_argument("--role")
    p.add_argument("--style", default="")
    p.add_argument("--out")
    p.add_argument("--home", default="~/.claude")
    a = p.parse_args(argv)
    try:
        profile = load_profile(a.profile)
        if a.command == "check":
            result = check(a.agents, profile)
        elif a.command == "apply":
            validate(profile, agent_files(a.agents), personality_ids())
            result = {"changed": apply(a.agents, profile)}
        elif a.command == "resolve":
            result = resolve(profile, a.role, [s for s in a.style.split(",") if s])
        elif a.command == "render":
            text = render(profile)
            if a.out:
                Path(a.out).write_text(text, encoding="utf-8", newline="\n")
            result = {"written": a.out} if a.out else text
        else:
            result = install(a.home, profile)
        print(result if isinstance(result, str) else json.dumps(result, indent=2))
        return 0
    except (CouncilError, KeyError, OSError, ValueError) as exc:
        print(f"council: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
