"""Live end-to-end check of the strata context handoff with headless Claude Code. Costs a few Sonnet calls.

    py tests/e2e/run_e2e.py WORKDIR       (WORKDIR: an empty throwaway folder outside any git repository)

1. trigger  STRATA_HANDOFF_THRESHOLD=1 forces the handoff prompt after the first tool call; Claude must write
            HANDOFF.md, CONTEXT.md and `latest`.
2. resume   a second session in the same folder (default threshold) must get the handoff at SessionStart and say so.
3. off      STRATA_HANDOFF=off with the forcing threshold: no new handoff folder and no injection, though the handoff
            was made unconsumed again.
4. compact  `/compact` on a session that wrote no handoff: PreCompact writes the automatic snapshot.
Raw stream-json output of every run is saved next to this script; summary.json holds the checks.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]


def trim(stdout):
    """The saved stream without the init event and other plugins' hook output: they list the local setup, not the
    test. Strata's own hook responses stay, as evidence."""
    keep = []
    for line in stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("subtype") in ("init", "commands_changed") or (e.get("subtype") in ("hook_started", "hook_response")
                                          and "Strata" not in line):
            continue
        keep.append(line)
    return "\n".join(keep) + "\n"


def scrub_evidence():
    """Replace the home folder with ~ in every saved file, in each spelling a JSON or Windows path can take."""
    home = str(Path.home())
    short = os.environ.get("TEMP", "").split("\\AppData")[0] if os.name == "nt" else ""
    spellings = {s for h in (home, short) if h for s in (h, h.replace("\\", "\\" * 2), h.replace("\\", "\\" * 4), h.replace("\\", "/"))}
    for f in HERE.iterdir():
        if f.suffix in (".jsonl", ".json", ".md"):
            text = f.read_text(encoding="utf-8")
            for s in sorted(spellings, key=len, reverse=True):
                text = text.replace(s, "~")
            f.write_text(text, encoding="utf-8")


def run(name, workdir, prompt, env_extra, extra=()):
    env = {**os.environ, **env_extra}
    argv = [shutil.which("claude"), "-p", prompt, "--plugin-dir", str(PLUGIN), "--model", "sonnet",
            "--permission-mode", "bypassPermissions", "--output-format", "stream-json", "--verbose", *extra]
    t0 = time.time()
    out = subprocess.run(argv, cwd=workdir, env=env, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=900)
    (HERE / f"{name}.stream.jsonl").write_text(trim(out.stdout), encoding="utf-8")
    if out.stderr.strip():
        (HERE / f"{name}.stderr.txt").write_text(out.stderr, encoding="utf-8")
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


def transcript_hits(name, session, marker="Strata context handoff"):
    """Transcript records holding the marker, saved as evidence. stream-json does not echo what PostToolUse and
    UserPromptSubmit hooks add, but the session transcript records it as an attachment."""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    hits = [line for t in home.glob(f"projects/*/{session}.jsonl")
            for line in t.read_text(encoding="utf-8", errors="replace").splitlines() if marker in line]
    (HERE / f"{name}.transcript-hits.jsonl").write_text("\n".join(hits) + "\n", encoding="utf-8")
    return hits


def dirs(base):
    return sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []


def main(workdir):
    work = Path(workdir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    data = work.parent / (work.name + "-strata-data")  # keeps the user's real strata memory out of the test
    data.mkdir(exist_ok=True)
    (data / "config.json").write_text(json.dumps({"auto": False}), encoding="utf-8")
    base = work / ".claude" / "handoff"
    env = {"MOAA_STRATA_DIR": str(data)}
    checks = {}

    r1 = run("1-trigger", work, "Create a file plan.md with a five-step plan for a tiny Python CLI that counts words "
             "in a file, then run `ls` to show the folder. Follow any instructions that hooks give you.",
             {**env, "STRATA_HANDOFF_THRESHOLD": "1"})
    latest = (base / "latest").read_text(encoding="utf-8").strip() if (base / "latest").exists() else ""
    d = base / latest
    checks["trigger: hook prompt reached Claude"] = bool(transcript_hits("1-trigger", r1["session"]))
    checks["trigger: systemMessage shown"] = "Strata: context is" in r1["stdout"]
    checks["trigger: HANDOFF.md written"] = (d / "HANDOFF.md").is_file() and bool(latest)
    checks["trigger: CONTEXT.md written"] = (d / "CONTEXT.md").is_file() and bool(latest)
    checks["trigger: user told to open a new chat"] = "new chat" in r1["result"].lower()

    r2 = run("2-resume", work, "Hi. What should we do next?", env)
    checks["resume: handoff injected at SessionStart"] = "an earlier chat in this project saved its state" in r2["stdout"]
    checks["resume: Claude confirms it resumed"] = "handoff" in r2["result"].lower()
    checks["resume: marked consumed"] = (d / ".consumed").is_file()
    checks["resume: different session ids"] = r1["session"] != r2["session"]

    before = dirs(base)
    later = time.time() + 2
    os.utime(d / "HANDOFF.md", (later, later))  # unconsumed again, so `off` must be what stops the injection
    r3 = run("3-off", work, "Run `ls` and say done.", {**env, "STRATA_HANDOFF": "off", "STRATA_HANDOFF_THRESHOLD": "1"})
    checks["off: no new handoff folder"] = dirs(base) == before
    checks["off: no hook prompt and no injection"] = ("Strata context handoff" not in r3["stdout"]
                                                      and not transcript_hits("3-off", r3["session"]))

    work4 = work.parent / (work.name + "-compact")
    work4.mkdir(exist_ok=True)
    r4a = run("4a-compact-setup", work4, "Create notes.txt saying 'alpha beta', then reply OK.", env)
    r4b = run("4b-compact", work4, "/compact", env, ("--resume", r4a["session"]))
    snaps = list((work4 / ".claude" / "handoff").glob("*/HANDOFF.md"))
    text = snaps[0].read_text(encoding="utf-8") if snaps else ""
    checks["compact: automatic snapshot written"] = "automatic snapshot" in text
    checks["compact: snapshot holds the last request"] = "alpha beta" in text
    if snaps:
        shutil.copy(snaps[0], HERE / "4-snapshot-HANDOFF.md")
    if latest:
        for f in ("HANDOFF.md", "CONTEXT.md"):
            if (d / f).is_file():
                shutil.copy(d / f, HERE / f"1-written-{f}")

    summary = {"workdir": str(work), "handoff_dir": str(d), "runs": {k: {"exit": v["exit"], "session": v["session"],
               "result": v["result"]} for k, v in (("1-trigger", r1), ("2-resume", r2), ("3-off", r3),
                                                    ("4a-compact-setup", r4a), ("4b-compact", r4b))},
               "checks": checks, "passed": all(checks.values())}
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    scrub_evidence()
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
