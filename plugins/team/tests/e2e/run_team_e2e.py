"""Live end-to-end check of the team board with headless Claude Code (installed plugin) in two clones of one remote.
About five Haiku sessions. Both clones run on this machine's account here; on a real team each clone is a
different person on their own account, which changes nothing in the board protocol.

    py tests/e2e/run_team_e2e.py WORKDIR      (an empty throwaway folder)

Setup (CLI): a bare remote, clones alice and bob; alice creates the board, adds a task assigned to bob and a shared
task, and messages bob; bob joins.
1-bob      bob's session starts: the SessionStart hook must brief it ("you are bob", the assigned task, the message).
           Asked to claim its assigned task and tell alice, it must claim it on the board and send the message.
2-alice    alice's next session must be briefed with bob's message.
3-race     two sessions (alice, bob) are started at the same moment, each told to claim the shared task: exactly
           one must own it, and the other must report that it was taken.
Raw stream-json, hook attachments and the final board are saved next to this script; summary.json holds the checks.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
TEAM = HERE.parents[1] / "team.py"
ENV = {"GIT_AUTHOR_NAME": "e2e", "GIT_AUTHOR_EMAIL": "e2e@example.invalid", "GIT_COMMITTER_NAME": "e2e",
       "GIT_COMMITTER_EMAIL": "e2e@example.invalid"}


def sh(argv, cwd):
    out = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env={**os.environ, **ENV})
    if out.returncode:
        raise SystemExit(f"{argv} failed: {out.stderr}")
    return out.stdout


def team(cwd, *args):
    return sh([sys.executable, str(TEAM), *args], cwd)


def start(name, cwd, prompt):
    argv = [shutil.which("claude"), "-p", prompt, "--model", "haiku", "--permission-mode", "bypassPermissions",
            "--output-format", "stream-json", "--verbose"]
    return name, time.time(), subprocess.Popen(argv, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               text=True, encoding="utf-8", errors="replace", env={**os.environ, **ENV})


def finish(job):
    name, t0, p = job
    stdout, _ = p.communicate(timeout=900)
    keep = [line for line in stdout.splitlines()
            if not any(f'"subtype":"{s}"' in line.replace(" ", "") for s in ("init", "commands_changed"))
            and not ('"hook_' in line and "Team board" not in line)]
    (HERE / f"{name}.stream.jsonl").write_text("\n".join(keep) + "\n", encoding="utf-8")
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    session = next((e.get("session_id") for e in events if e.get("session_id")), None)
    print(f"[{name}] exit {p.returncode} in {time.time() - t0:.0f}s, session {session}")
    return {"exit": p.returncode, "session": session, "result": result.get("result", "")}


def hits(name, session, marker="Team board"):
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    found = [line for t in home.glob(f"projects/*/{session}.jsonl")
             for line in t.read_text(encoding="utf-8", errors="replace").splitlines()
             if marker in line and '"type":"attachment"' in line.replace(" ", "")]
    (HERE / f"{name}.transcript-hits.jsonl").write_text("\n".join(found) + ("\n" if found else ""), encoding="utf-8")
    return "\n".join(found)


def board(cwd):
    team(cwd, "sync", "--quiet")
    return json.loads(team(cwd, "board", "--json"))


def scrub():
    home = str(Path.home())
    spellings = {home, home.replace("\\", "\\\\"), home.replace("\\", "\\\\\\\\"), home.replace("\\", "/")}
    for f in HERE.iterdir():
        if f.suffix in (".jsonl", ".json"):
            text = f.read_text(encoding="utf-8")
            for s in sorted(spellings, key=len, reverse=True):
                text = text.replace(s, "~")
            text = re.sub(r"(?i)[A-Z]:(?:\\+|/)Users(?:\\+|/)[^\\/\"']+", "~", text)  # 8.3 short names too
            text = re.sub(r"[\w.+\-]+@[\w\-]+(\.[\w\-]+)+", "member@example.invalid", text)  # git user.email
            f.write_text(text, encoding="utf-8")


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    sh(["git", "init", "-q", "--bare", "remote.git"], root)
    sh(["git", "clone", "-q", "remote.git", "alice"], root)
    alice, bob = root / "alice", root / "bob"
    (alice / "README.md").write_text("# Solver project\n", encoding="utf-8")
    sh(["git", "add", "-A"], alice)
    sh(["git", "commit", "-q", "-m", "first"], alice)
    sh(["git", "push", "-q", "origin", "HEAD"], alice)
    team(alice, "init")
    team(alice, "join", "alice", "--role", "lead")
    sh(["git", "clone", "-q", "remote.git", "bob"], root)
    team(bob, "init")
    team(bob, "join", "bob", "--role", "docs")
    docs = json.loads(team(alice, "add", "Write the solver docs", "--paths", "docs", "--assign", "bob"))["added"]
    shared = json.loads(team(alice, "add", "Profile the mesh step", "--paths", "src/mesh"))["added"]
    team(alice, "send", "bob", "Docs first please; the mesh profiling can wait.")
    checks = {}

    b1 = finish(start("1-bob", bob, f"Use the team board in this repository: claim the task assigned to me ({docs}) "
                                    "with team.py, then send alice a message that I am on the docs. Reply with the "
                                    "branch name the claim printed."))
    brief = hits("1-bob", b1["session"])
    checks["bob: briefed at session start"] = "you are bob" in brief and docs in brief and "Docs first" in brief
    t = next(x for x in board(alice)["tasks"] if x["id"] == docs)
    checks["bob: claimed his task on the board"] = (t["status"], t["owner"]) == ("claimed", "bob")
    checks["bob: reply names the branch"] = f"team/{docs}" in b1["result"]

    a2 = finish(start("2-alice", alice, "What is new on the team board for me? Answer in two sentences."))
    checks["alice: briefed with bob's message"] = "message from bob" in hits("2-alice", a2["session"])

    ask = (f"Claim task {shared} on the team board with team.py claim {shared}. If the claim fails because someone "
           "else has it, say TAKEN and the owner's name; if it succeeds, say MINE.")
    jobs = [start("3-race-alice", alice, ask), start("3-race-bob", bob, ask)]
    ra, rb = finish(jobs[0]), finish(jobs[1])
    t = next(x for x in board(alice)["tasks"] if x["id"] == shared)
    claims = [x for x in t["log"] if x["what"] in ("claimed", "took over a stale claim")]
    checks["race: exactly one claim on the board"] = len(claims) == 1 and t["owner"] in ("alice", "bob")
    winner, loser = (ra, rb) if t["owner"] == "alice" else (rb, ra)
    checks["race: winner says MINE, loser says TAKEN"] = "MINE" in winner["result"] and "TAKEN" in loser["result"]

    final = board(alice)
    (HERE / "board.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    summary = {"checks": checks, "passed": all(checks.values()), "race_owner": t["owner"],
               "answers": {"bob": b1["result"], "alice": a2["result"], "race_alice": ra["result"],
                           "race_bob": rb["result"]},
               "date": time.strftime("%Y-%m-%d %H:%M")}
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    scrub()
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
