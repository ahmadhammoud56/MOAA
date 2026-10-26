#!/usr/bin/env python3
"""Inline-Python guard: a note to Claude when a Bash or PowerShell command runs long or multi-line `python -c` code.

  python guard.py on | off | status     turn the guard on or off for every session
  python guard.py hook pre-tool         PreToolUse hook: tool call JSON on stdin, additionalContext on stdout

On Windows, the quoting of multi-line or long `python -c` / `py -c` / `python3 -c` code breaks often in Bash and
PowerShell. The guard never blocks, denies or asks: it adds a note next to the tool result telling Claude to write
the code to a .py file in its scratchpad and run that instead. MOAA_GUARD=off skips it for a whole process.
State: ~/.claude/moaa-core/config.json (CLAUDE_CONFIG_DIR respected). Standard library only.
"""
import json
import os
from pathlib import Path
import re
import sys

MAX_CHARS = 150  # inline code longer than this gets the note, even on one line
TOOLS = ("Bash", "PowerShell")
# py / python / python3 / python3.12 (optionally .exe or a full path), any flags such as -3 or -I, then -c
INLINE = re.compile(r"""(?:^|[\s;&|(/\\"'`])(?:py|python(?:3(?:\.\d+)?)?)(?:\.exe)?["']?(?:\s+-(?!c\b)\S+)*\s+-c\b""",
                    re.IGNORECASE)
NOTE = ("moaa-core guard: this command runs inline Python (`python -c`) that is multi-line or longer than "
        f"{MAX_CHARS} characters. On Windows, Bash and PowerShell quoting often breaks such code. The call was not "
        "blocked. If it failed, and from now on, write the code to a .py file in your scratchpad directory (or a "
        "temp folder) and run that file instead; use `py` if `python` exits 49. Off switch: MOAA_GUARD=off or "
        "`guard.py off`.")


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()


def config_path(home):
    return home / "moaa-core" / "config.json"


def enabled(home):
    try:
        return json.loads(config_path(home).read_text(encoding="utf-8")).get("guard", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def save(home, on):
    path = config_path(home)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**data, "guard": on}, indent=2) + "\n", encoding="utf-8")


def env_off():
    return os.environ.get("MOAA_GUARD", "").strip().lower() in ("off", "0", "false", "no")


def risky(command):
    """True when the command runs inline Python whose code has a newline or is longer than MAX_CHARS."""
    m = INLINE.search(command or "")
    if not m:
        return False
    code = command[m.end():].strip()
    return "\n" in code or len(code) > MAX_CHARS


def hook_pre_tool(home, payload):
    """additionalContext for a tool call, or None when the guard stays silent."""
    if env_off() or not enabled(home):
        return None
    payload = payload or {}
    if payload.get("tool_name") not in TOOLS:
        return None
    return NOTE if risky((payload.get("tool_input") or {}).get("command")) else None


def status(home):
    state = "on" if enabled(home) else "off"
    extra = " (but MOAA_GUARD=off in this environment)" if env_off() else ""
    return f"moaa-core guard: {state}{extra}; config {config_path(home).as_posix()}"


def main(argv):
    home = claude_home()
    if argv == ["hook", "pre-tool"]:
        try:
            ctx = hook_pre_tool(home, json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}"))
        except Exception:  # a hook must never break the tool call
            ctx = None
        if ctx:
            # no permissionDecision: the call goes through the normal permission flow untouched
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ctx}}))
        return 0
    if argv in (["on"], ["off"]):
        save(home, argv[0] == "on")
    elif argv != ["status"]:
        print(__doc__)
        return 2
    print(status(home))
    return 0


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        sys.exit(3)  # the hook command then tries the next interpreter on PATH
    sys.exit(main(sys.argv[1:]))
