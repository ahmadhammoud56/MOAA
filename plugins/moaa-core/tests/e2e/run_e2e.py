"""Live checks for the guard: py tests/e2e/run_e2e.py [pipe|claude]   (both when no argument)

pipe:   pipes two PreToolUse payloads into guard.py and writes pipe.txt.
claude: one headless `claude -p` run (haiku) from a throwaway folder with --plugin-dir <this plugin>, asking for a
        two-line `py -c`; keeps the PreToolUse hook events, messages and result in claude-p.jsonl (init and other
        events dropped, home paths redacted to ~) and writes claude-p.summary.json.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PLUGIN = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REDACT = re.compile(r"[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/)[^\\/\"']+", re.IGNORECASE)  # any user folder, 8.3 too


def pipe():
    lines = []
    for name, cmd in (("multi-line", "py -c \"import math\nprint(math.factorial(20))\""),
                      ("short", "py -c \"print(1+1)\"")):
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}})
        r = subprocess.run([sys.executable, str(PLUGIN / "guard.py"), "hook", "pre-tool"], input=payload.encode(),
                           capture_output=True)
        lines += [f"## {name}", f"stdin: {payload}", f"exit: {r.returncode}", f"stdout: {r.stdout.decode()!r}", ""]
    (OUT / "pipe.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def claude():
    work = Path(tempfile.mkdtemp(prefix="moaa-guard-e2e-"))
    prompt = ("Use the Bash tool exactly once to run this command; keep the Python code on two separate lines inside "
              "the quotes (a real newline, not \\n):\npy -c \"import math\nprint(math.factorial(20))\"\n"
              "Then reply with: the printed number, and, quoted verbatim, any note starting with 'moaa-core guard' "
              "that you received with the tool result (or the words NO NOTE if there was none).")
    env = {**os.environ, "PROMPT_REFINER": "off"}
    env.pop("MOAA_GUARD", None)
    cmd = [shutil.which("claude"), "-p", prompt, "--plugin-dir", str(PLUGIN), "--model", "haiku",
           "--output-format", "stream-json", "--verbose", "--include-hook-events", "--allowedTools", "Bash(py:*)",
           "--max-turns", "4"]
    r = subprocess.run(cmd, cwd=work, capture_output=True, env=env, timeout=300)
    shutil.rmtree(work, ignore_errors=True)
    keep, final = [], ""
    for ln in r.stdout.decode("utf-8", "replace").splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        t = e.get("type")
        if t in ("assistant", "user", "result") or (t == "system" and e.get("hook_event") == "PreToolUse"):
            keep.append(REDACT.sub("~", ln))
        if t == "result":
            final = e.get("result", "")
    (OUT / "claude-p.jsonl").write_text("\n".join(keep) + "\n", encoding="utf-8")
    summary = {"exit": r.returncode, "events_mentioning_guard": sum("moaa-core guard" in k for k in keep),
               "final_reply": REDACT.sub("~", final)}
    (OUT / "claude-p.summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return r.returncode == 0 and summary["events_mentioning_guard"] > 0


if __name__ == "__main__":
    which = sys.argv[1:] or ["pipe", "claude"]
    results = [{"pipe": pipe, "claude": claude}[step]() for step in which]
    sys.exit(0 if all(r is not False for r in results) else 1)
