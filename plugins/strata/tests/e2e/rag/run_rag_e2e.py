"""Live end-to-end check of strata's project RAG with headless Claude Code and the installed plugin. A few Haiku calls.

    py tests/e2e/rag/run_rag_e2e.py WORKDIR DATADIR     (both empty throwaway folders)

WORKDIR becomes a git repository holding lab notes with a fact no model can know, plus decoy files. DATADIR is the
strata data folder for these runs (MOAA_STRATA_DIR), so the real memory and index are untouched.
0. warm    one short session: its SessionStart starts the background index; the script waits for it.
1. hint    a question answered only in the notes, with every tool denied: the answer must name the fact, and the
           transcript must show the "Strata RAG" passage with its path:lines.
2. off     the same question with STRATA_RAG=off: no passage, and the answer must not know the fact.
3. chat    an unrelated request: no passage.
Raw stream-json output and the matching transcript records are saved next to this script; summary.json holds the
checks.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
NOTES = """# Lab notes, mix design

## Rest time
The Qanat-7 mortar reaches its printable window after a rest of 23 minutes; we call this the Qanat delay.
Printing earlier gives slumping layers, printing after 41 minutes gives cold joints.

## Equipment
Rheometer calibration happens every Monday with the reference oil.
"""
QUESTION = ("How many minutes of rest does the Qanat-7 mortar need before it is printable? Do not use any tools; "
            "answer in one sentence from what you already have, or say you do not know.")


def run(name, workdir, prompt, env_extra):
    env = {**os.environ, **env_extra}
    argv = [shutil.which("claude"), "-p", prompt, "--model", "haiku", "--permission-mode", "dontAsk",
            "--output-format", "stream-json", "--verbose"]
    t0 = time.time()
    out = subprocess.run(argv, cwd=workdir, env=env, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=600)
    keep = [line for line in out.stdout.splitlines()
            if '"subtype":"init"' not in line.replace(" ", "")
            and not ('"hook_' in line and "Strata RAG" not in line)]
    (HERE / f"{name}.stream.jsonl").write_text("\n".join(keep) + "\n", encoding="utf-8")
    events = []
    for line in out.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    session = next((e.get("session_id") for e in events if e.get("session_id")), None)
    print(f"[{name}] exit {out.returncode} in {time.time() - t0:.0f}s, session {session}")
    return {"exit": out.returncode, "session": session, "result": result.get("result", "")}


def transcript_hits(name, session, marker="Strata RAG"):
    """Transcript records holding the marker: stream-json does not echo what a UserPromptSubmit hook adds, but the
    session transcript records it as an attachment."""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    hits = [line for t in home.glob(f"projects/*/{session}.jsonl")
            for line in t.read_text(encoding="utf-8", errors="replace").splitlines()
            if marker in line and '"type":"attachment"' in line.replace(" ", "")]  # not the whole request blob
    (HERE / f"{name}.transcript-hits.jsonl").write_text("\n".join(hits) + ("\n" if hits else ""), encoding="utf-8")
    return hits


def scrub():
    home = str(Path.home())
    spellings = {home, home.replace("\\", "\\\\"), home.replace("\\", "\\\\\\\\"), home.replace("\\", "/")}
    short = os.environ.get("TEMP", "").split("\\AppData")[0] if os.name == "nt" else ""
    if short:
        spellings |= {short, short.replace("\\", "\\\\"), short.replace("\\", "/")}
    for f in HERE.iterdir():
        if f.suffix in (".jsonl", ".json"):
            text = f.read_text(encoding="utf-8")
            for s in sorted(spellings, key=len, reverse=True):
                text = text.replace(s, "~")
            f.write_text(text, encoding="utf-8")


def main():
    work, data = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    (work / "docs").mkdir(exist_ok=True)
    (work / "docs" / "lab-notes.md").write_text(NOTES, encoding="utf-8")
    (work / "src").mkdir(exist_ok=True)
    (work / "src" / "plot.py").write_text("def plot(curve):\n    return sorted(curve)\n", encoding="utf-8")
    (work / "README.md").write_text("# Print trials\nScripts and notes for the print trials.\n", encoding="utf-8")
    env = {"MOAA_STRATA_DIR": str(data)}
    checks = {}

    warm = run("0-warm", work, "Reply with the single word ready.", env)
    db = data / "rag.sqlite3"
    import sqlite3
    for _ in range(60):  # the indexer runs in the background after SessionStart
        try:
            n = sqlite3.connect(str(db)).execute("SELECT COALESCE(SUM(chunks),0) FROM projects").fetchone()[0]
        except sqlite3.Error:
            n = 0
        if n:
            break
        time.sleep(1)
    checks["warm: background index built"] = bool(n)

    hint = run("1-hint", work, QUESTION, env)
    hits = transcript_hits("1-hint", hint["session"])
    checks["hint: passage injected with path:lines"] = any("docs/lab-notes.md:" in h for h in hits)
    checks["hint: answer names 23 minutes"] = "23" in hint["result"]

    off = run("2-off", work, QUESTION, {**env, "STRATA_RAG": "off"})
    checks["off: no passage"] = not transcript_hits("2-off", off["session"])
    checks["off: answer does not know 23"] = "23" not in off["result"]

    chat = run("3-chat", work, "Write one sentence about gardens blooming in spring.", env)
    checks["chat: no passage"] = not transcript_hits("3-chat", chat["session"])

    summary = {"checks": checks, "passed": all(checks.values()),
               "answers": {k: v["result"] for k, v in (("hint", hint), ("off", off), ("chat", chat))},
               "exits": {k: v["exit"] for k, v in (("warm", warm), ("hint", hint), ("off", off), ("chat", chat))},
               "date": time.strftime("%Y-%m-%d %H:%M")}
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    scrub()
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
