#!/usr/bin/env python3
"""Rebuild the upstream part of .claude-plugin/marketplace.json from this machine's installed plugins.

Every upstream plugin listed in config/kit.json is referenced (never copied) at the exact commit it is
installed at here: `github` source for plugins at a repo root, `git-subdir` for plugins in a subfolder.
Vendored MOAA plugins (relative ./plugins/... sources) are kept as they are. Standard library only.

  python scripts/sync_catalog.py            write the marketplace
  python scripts/sync_catalog.py --check    exit 1 if the marketplace is out of date
"""
import json
import os
from pathlib import Path
import re
import sys

KIT = Path(__file__).resolve().parents[1]
MARKET = KIT / ".claude-plugin" / "marketplace.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
# Names reserved for Anthropic's own plugins may not appear in a third-party marketplace; list them under an alias.
ALIASES = {"claude-api": "llm-api-reference", "claude-mem": "persistent-memory", "claude-mem-cowork": "persistent-memory-cowork"}


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()


def repo_slug(url):
    match = re.match(r"(?:https://github\.com/)?([^/]+/[^/]+?)(?:\.git)?/?$", url)
    if not match:
        raise ValueError(f"not a GitHub repo: {url}")
    return match.group(1)


def upstream_entries(home, kit):
    plugins_dir = home / "plugins"
    installed = json.loads((plugins_dir / "installed_plugins.json").read_text(encoding="utf-8"))["plugins"]
    entries = []
    for item in kit["plugins"]:
        name, market = item["id"].split("@")
        if market == kit["name"]:
            continue
        catalog = json.loads((plugins_dir / "marketplaces" / market / ".claude-plugin" / "marketplace.json")
                             .read_text(encoding="utf-8"))
        upstream = next(p for p in catalog["plugins"] if p["name"] == name)
        record = installed[item["id"]][0]
        sha = record.get("gitCommitSha")
        if not (sha and SHA.match(sha)):
            raise ValueError(f"{item['id']}: no full commit SHA recorded in installed_plugins.json")
        repo = repo_slug(kit["marketplaces"][market])
        rel = str(upstream["source"]).removeprefix("./").strip("/")
        source = ({"source": "github", "repo": repo, "sha": sha} if rel in ("", ".") else
                  {"source": "git-subdir", "url": f"https://github.com/{repo}.git", "path": rel, "sha": sha})
        entry = {k: v for k, v in upstream.items() if k not in ("source", "name")}
        alias = ALIASES.get(name)
        if alias:
            entry["description"] = f"{entry.get('description', '').rstrip('.')}. Upstream plugin `{name}` from {market}; listed as `{alias}` because `{name}` is a reserved name."
        entry = {"name": alias or name, "source": source, **entry}
        entry.setdefault("homepage", f"https://github.com/{repo}")
        entry["category"] = entry.get("category") or "upstream"
        entry["tags"] = sorted(set(entry.get("tags", [])) | {f"upstream:{market}"} |
                               ({"optional"} if item.get("optional") else set()))
        entries.append(entry)
    return sorted(entries, key=lambda e: e["name"])


def build(home=None):
    kit = json.loads((KIT / "config" / "kit.json").read_text(encoding="utf-8"))
    market = json.loads(MARKET.read_text(encoding="utf-8"))
    vendored = [p for p in market["plugins"] if isinstance(p["source"], str)]
    market["plugins"] = vendored + upstream_entries(home or claude_home(), kit)
    return market


if __name__ == "__main__":
    market = build()
    text = json.dumps(market, indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        current = MARKET.read_text(encoding="utf-8")
        print("catalog up to date" if current == text else "catalog out of date: run scripts/sync_catalog.py")
        sys.exit(0 if current == text else 1)
    MARKET.write_text(text, encoding="utf-8", newline="\n")
    upstream = sum(1 for p in market["plugins"] if isinstance(p["source"], dict))
    print(f"marketplace: {len(market['plugins'])} plugins ({len(market['plugins']) - upstream} vendored, {upstream} upstream, pinned)")
