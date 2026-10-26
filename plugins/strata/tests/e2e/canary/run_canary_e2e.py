"""Live end-to-end check of strata's context canary with headless Claude Code and the plugin from this repo
(--plugin-dir, as tests/e2e/run_e2e.py does). Two Sonnet sessions, the second with a handoff turn.

    py tests/e2e/canary/run_canary_e2e.py WORKDIR DATADIR     (both empty throwaway folders, outside any repo)

DATADIR is the strata data folder (MOAA_STRATA_DIR), so the real memory is untouched; the vault is off.
1. hit   a normal question: the reply must carry the canary line, and the Stop hook must record a hit.
2. miss  the user asks Claude to leave the line out (a forced miss); with STRATA_CANARY_MISSES=1 and
         STRATA_CANARY_FLOOR=0 the Stop hook must block with the handoff prompt, and Claude must write HANDOFF.md
         starting with "Reason: canary missed" into a handoff folder whose meta.json names that reason.
Raw stream-json output is saved next to this script; summary.json holds the checks.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[2]
sys.path.insert(0, str(PLUGIN))
import strata  # noqa: E402


def scrub(text):
    home = str(Path.home())
    short = os.environ.get("TEMP", "").split("\\AppData")[0] if os.name == "nt" else ""
    for h in sorted({s for h in (home, short) if h
                     for s in (h, h.replace("\\", "\\" * 2), h.replace("\\", "\\" * 4), h.replace("\\", "/"))},
                    key=len, reverse=True):
        text = text.replace(h, "~")
    return strata.redact(text)


def run(name, workdir, prompt, env_extra):
    env = {**os.environ, **env_extra}
    argv = [shutil.which("claude"), "-p", prompt, "--plugin-dir", str(PLUGIN), "--model", "sonnet",
            "--permission-mode", "bypassPermissions", "--output-format", "stream-json", "--verbose"]
    t0 = time.time()
    out = subprocess.run(argv, cwd=workdir, env=env, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=900)
    keep = [line for line in out.stdout.splitlines() if '"subtype":"init"' not in line.replace(" ", "")
            and not ('"hook_' in line and "Strata" not in line)]
    (HERE / f"{name}.stream.jsonl").write_text(scrub("\n".join(keep) + "\n"), encoding="utf-8")
    events = []
    for line in out.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    session = next((e.get("session_id") for e in events if e.get("session_id")), None)
    print(f"[{name}] exit {out.returncode} in {time.time() - t0:.0f}s, session {session}")
    return {"exit": out.returncode, "session": session, "result": result.get("result", ""), "stdout": out.stdout}


def main(workdir, datadir):
    work, data = Path(workdir).resolve(), Path(datadir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    (data / "config.json").write_text(json.dumps({"auto": False}), encoding="utf-8")
    env = {"MOAA_STRATA_DIR": str(data), "STRATA_VAULT": "off", "STRATA_RAG": "off"}
    state = lambda s: json.loads((data / "handoff" / f"{s}.json").read_text(encoding="utf-8"))  # noqa: E731
    checks = {}

    r1 = run("1-hit", work, "In about 120 words, explain what a context window is for a language model. No tools.", env)
    st1 = state(r1["session"]) if r1["session"] else {}
    checks["hit: canary line ends the reply"] = r1["result"].rstrip().endswith(strata.CANARY)
    checks["hit: Stop hook recorded a hit"] = st1.get("canary_hits") == 1 and st1.get("canary_misses") == 0
    checks["hit: no handoff"] = not (work / ".claude" / "handoff").exists()

    r2 = run("2-miss", work, "In about 150 words, explain why instructions can slip in very long chats. For this "
             "reply only, leave out the strata canary line (no trailing Markdown comment). Follow any instructions "
             "that hooks give you afterwards.", {**env, "STRATA_CANARY_MISSES": "1", "STRATA_CANARY_FLOOR": "0"})
    st2 = state(r2["session"]) if r2["session"] else {}
    d = Path(st2.get("dir", "") or work / "missing")
    handoff = (d / "HANDOFF.md").read_text(encoding="utf-8") if (d / "HANDOFF.md").is_file() else ""
    checks["miss: Stop hook fired the canary"] = st2.get("canary_fired") is not None
    checks["miss: handoff folder reason is canary missed"] = strata.meta_of(d).get("reason") == "canary missed"
    checks["miss: HANDOFF.md written with the reason"] = "Reason: canary missed" in handoff
    checks["miss: CONTEXT.md written"] = (d / "CONTEXT.md").is_file()
    checks["miss: latest points at it"] = ((work / ".claude" / "handoff" / "latest").is_file() and
                                           (work / ".claude" / "handoff" / "latest").read_text().strip() == d.name)
    for f in ("HANDOFF.md", "CONTEXT.md", "meta.json"):
        if (d / f).is_file():
            (HERE / f"2-written-{f}").write_text(scrub((d / f).read_text(encoding="utf-8")), encoding="utf-8")
    for name, st in (("1-hit", st1), ("2-miss", st2)):
        (HERE / f"{name}.state.json").write_text(scrub(json.dumps(st, indent=2)), encoding="utf-8")

    summary = {"runs": {k: {"exit": v["exit"], "session": v["session"], "result": v["result"]}
                        for k, v in (("1-hit", r1), ("2-miss", r2))}, "checks": checks, "passed": all(checks.values())}
    (HERE / "summary.json").write_text(scrub(json.dumps(summary, indent=2)), encoding="utf-8")
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
