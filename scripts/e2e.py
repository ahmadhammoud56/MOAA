#!/usr/bin/env python3
"""Run MOAA's live end-to-end checks before a release. They start real headless Claude Code sessions, so they cost
tokens (mostly Haiku, a few Sonnet calls) and take several minutes each.

  python scripts/e2e.py              run every suite
  python scripts/e2e.py strata-rag   run the named suites
  python scripts/e2e.py --list       show the suites and what each costs

Each suite gets fresh empty throwaway folders under the temp folder (WORKDIR, and DATADIR for the strata data folder,
so the real memory is untouched). Evidence is saved by the suite itself in plugins/<name>/tests/e2e/; review the
diff before committing it. Exit 1 if any suite failed. Standard library only.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import time

KIT = Path(__file__).resolve().parents[1]
P = KIT / "plugins"
# name: (script, argument kinds, cost note). Kinds: plugin = the plugin folder, work / data = new empty temp folders.
SUITES = {
    "moaa-core-guard": (P / "moaa-core/tests/e2e/run_e2e.py", [], "1 Haiku session"),
    "prompt-refiner": (P / "prompt-refiner/tests/e2e/run_e2e.py", ["plugin"], "3 sessions; check with summarize.py"),
    "strata-handoff": (P / "strata/tests/e2e/run_e2e.py", ["work"], "a few Sonnet calls"),
    "strata-machine": (P / "strata/tests/e2e/run_machine_e2e.py", ["work"], "3 Haiku sessions"),
    "strata-rag": (P / "strata/tests/e2e/rag/run_rag_e2e.py", ["work", "data"], "4 Haiku sessions"),
    "strata-recall": (P / "strata/tests/e2e/recall/run_recall_e2e.py", ["work", "data"], "1 Sonnet + ~6 Haiku"),
    "strata-canary": (P / "strata/tests/e2e/canary/run_canary_e2e.py", ["work", "data"], "2 Sonnet sessions"),
    "strata-vault": (P / "strata/tests/e2e/vault/run_vault_e2e.py", ["work", "data"], "1 Sonnet + 2 Haiku"),
    "team": (P / "team/tests/e2e/run_team_e2e.py", ["work"], "~5 Haiku sessions"),
}


def run(name, timeout):
    script, kinds, _ = SUITES[name]
    plugin = next(p.parent for p in script.parents if p.name == "tests")
    # Background work the sessions started (strata's index refresh, consolidation) can still hold a folder on Windows.
    with tempfile.TemporaryDirectory(prefix=f"moaa-e2e-{name}-", ignore_cleanup_errors=True) as tmp:
        args = []
        for kind in kinds:
            if kind == "plugin":
                args.append(str(plugin))
            else:
                folder = Path(tmp) / kind
                folder.mkdir()
                args.append(str(folder))
        started = time.time()
        try:
            r = subprocess.run([sys.executable, str(script), *args], cwd=plugin, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=timeout)
            ok, tail = r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()[-15:]
        except subprocess.TimeoutExpired:
            ok, tail = False, [f"timed out after {timeout}s"]
    print(f"  {'PASS' if ok else 'FAIL'}  {name} ({time.time() - started:.0f}s)", flush=True)
    if not ok:
        print("        " + "\n        ".join(tail))
    return ok


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("suites", nargs="*", help="suite names (default: all)")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per suite")
    args = parser.parse_args(argv)
    unknown = [n for n in args.suites if n not in SUITES]
    if args.list or unknown:
        for name, (script, _, cost) in SUITES.items():
            print(f"  {name:16} {script.relative_to(KIT)}  ({cost})")
        return 1 if unknown else 0
    failed = [n for n in args.suites or SUITES if not run(n, args.timeout)]
    print(f"[moaa] e2e: {'all suites pass' if not failed else 'failed: ' + ', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
