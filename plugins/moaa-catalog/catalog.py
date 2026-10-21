#!/usr/bin/env python3
"""MOAA catalog: skills from installed but disabled plugins, found and used on demand instead of listed in every session.

  python catalog.py search <words...>   best-matching disabled skills: name, plugin, path
  python catalog.py use <SKILL.md path>  print that skill (and log the use; suggests enabling a pack used often)
  python catalog.py packs               disabled plugins and their skill counts
  python catalog.py hook prompt         UserPromptSubmit hook: suggest up to 3 strong matches for the prompt on stdin

The index (~/.claude/moaa-catalog/index.json) is rebuilt only when the plugin record or settings change, so a search
or a hook call reads one small file. Never changes settings or plugins. Standard library only.
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


def disabled_plugins(home):
    """{plugin id: install path} for installed plugins that are not enabled in settings.json."""
    on = {k for k, v in read_json(home / "settings.json").get("enabledPlugins", {}).items() if v}
    installed = read_json(home / "plugins" / "installed_plugins.json").get("plugins", {})
    return {pid: Path((e or [{}])[0].get("installPath", "")) for pid, e in sorted(installed.items()) if pid not in on}


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
    for pid, root in disabled_plugins(home).items():
        for md in sorted(root.rglob("SKILL.md")) if root.is_dir() else []:
            name, desc = frontmatter(md)
            skills.append({"pid": pid, "name": name, "desc": desc, "path": md.as_posix(),
                           "nw": sorted(set(words(name.replace("-", " ") + " " + name))), "dw": sorted(set(words(desc)))})
    df = {}
    for s in skills:
        for w in set(s["nw"]) | set(s["dw"]):
            df[w] = df.get(w, 0) + 1
    n = max(len(skills), 1)
    return {"stamp": stamp(home), "skills": skills, "idf": {w: round(math.log(1 + n / c), 3) for w, c in df.items()}}


def load_index(home):
    """The cached index, rebuilt only when settings.json or the installed-plugin record changed."""
    path = home / "moaa-catalog" / "index.json"
    index = read_json(path)
    if index.get("stamp") != stamp(home) or "idf" not in index:
        index = build_index(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(index), encoding="utf-8")
        os.replace(tmp, path)
    return index


def rank(index, query):
    """(query words, [(score, matched, skill, name hits)] best first). A query word scores its rarity (idf), doubled
    when it is in the skill's name."""
    q = list(dict.fromkeys(words(query)))
    idf, out, seen = index["idf"], [], set()
    for s in index["skills"]:
        if s["name"] in seen:  # bundles repeat the same skill; keep the first copy
            continue
        seen.add(s["name"])
        nw, dw = set(s["nw"]), set(s["dw"])
        hit = [w for w in q if w in nw or w in dw]
        if hit:
            out.append((sum(idf.get(w, 1) * (2 if w in nw else 1) for w in hit), len(hit), s,
                        sum(w in nw for w in hit)))
    out.sort(key=lambda r: (-r[1], -r[0]))
    return q, out


def search(home, query, limit=8):
    """Skills matching the most query words (at least half of them), best first."""
    q, ranked = rank(load_index(home), query)
    need = max(1, math.ceil(len(q) / 2))
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


def hook_prompt(home, payload):
    """additionalContext naming up to HOOK_MAX strong matches, or None. Short prompts and slash commands are skipped."""
    prompt = (payload or {}).get("prompt") or ""
    if prompt.lstrip().startswith("/") or len(words(prompt)) < 3:
        return None
    index = load_index(home)
    if not index["skills"]:
        return None
    _, ranked = rank(index, prompt)
    unit = math.log(1 + len(index["skills"]))  # idf of a word found in one skill only; makes HOOK_MIN corpus-independent
    best = [r for r in ranked if r[0] >= HOOK_MIN * unit and r[1] >= 2 and r[3] >= 1][:HOOK_MAX]  # needs a name hit
    if not best:
        return None
    catalog = Path(__file__).resolve().as_posix()
    lines = [f"- {s['name']} [{s['pid']}]: {s['desc'][:140]}\n  python \"{catalog}\" use \"{s['path']}\""
             for _, _, s, _ in best]
    return ("moaa-catalog: skills from disabled plugins that may fit this request (not loaded; use one only if it "
            "clearly helps):\n" + "\n".join(lines))


def main(argv):
    home = claude_home()
    if argv[:1] == ["search"] and len(argv) > 1:
        found = search(home, " ".join(argv[1:]))
        for score, _, s, _ in found:
            print(f"{s['name']}  [{s['pid']}]  score {score:.1f}\n  {s['desc'][:200]}\n  {s['path']}")
        if not found:
            print("no disabled-plugin skill matches; try other words")
        return 0
    if argv[:1] == ["use"] and len(argv) == 2:
        return use(home, argv[1])
    if argv[:1] == ["packs"]:
        counts = {}
        for s in load_index(home)["skills"]:
            counts[s["pid"]] = counts.get(s["pid"], 0) + 1
        for pid, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"{n:5d}  {pid}")
        return 0
    if argv == ["hook", "prompt"]:
        try:
            context = hook_prompt(home, json.loads(sys.stdin.read() or "{}"))
        except Exception:  # a hook must never block the user's prompt
            context = None
        if context:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
