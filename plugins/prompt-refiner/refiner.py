#!/usr/bin/env python3
"""Prompt refiner: before Claude works on a prompt, it restates it as a brief, asks about open points, and hands
the brief (not the raw prompt) to every subagent.

  python refiner.py on | off            turn the refiner on or off for every session
  python refiner.py mode ask|silent     ask: ask about material ambiguity (default); silent: write the brief, never ask
  python refiner.py status              show the state
  python refiner.py hook prompt         UserPromptSubmit hook: prompt JSON on stdin, additionalContext on stdout

A hook cannot rewrite the user's text, so the refiner injects instructions as context. It stays silent for slash
commands, harness notices, short replies and answers to a question Claude just asked. Long, structured prompts get a
one-line restatement instead of a full brief. Start a prompt with `raw:` to skip it once; PROMPT_REFINER=off skips it
for a whole process. State: ~/.claude/prompt-refiner/config.json (CLAUDE_CONFIG_DIR respected). Standard library only.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys

BYPASS = "raw:"
BRIEFS = ".briefs"
MODES = ("ask", "silent")
SHORT_WORDS = 4  # replies this short are confirmations or option picks, never new requests
ANSWER_WORDS = 40  # a reply up to this long right after Claude asked a question is treated as the answer
DETAILED_WORDS = 120  # prompts this long, or structured ones, already are a brief
TAIL_BYTES = 65536  # how much of the transcript to read to find Claude's last message


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()


def config_path(home):
    return home / "prompt-refiner" / "config.json"


def load_config(home):
    try:
        data = json.loads(config_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    mode = data.get("mode") if data.get("mode") in MODES else "ask"
    return {"enabled": data.get("enabled", True) is not False, "mode": mode}


def save_config(home, **changes):
    cfg = {**load_config(home), **changes}
    path = config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return cfg


def env_off():
    return os.environ.get("PROMPT_REFINER", "").strip().lower() in ("off", "0", "false", "no")


def words(text):
    return re.findall(r"[\w'-]+", text)


def is_notice(prompt):
    """Slash commands and messages the harness sends on its own (task notifications, side-session events)."""
    head = prompt.lstrip()
    return head.startswith(("/", "[SYSTEM", "<")) or "<task-notification>" in prompt


def is_structured(prompt):
    lines = [ln.strip() for ln in prompt.splitlines() if ln.strip()]
    marked = [ln for ln in lines if re.match(r"([-*#>]|\d+[.)])\s", ln)]
    return len(marked) >= 4


def last_assistant_asked(transcript_path):
    """True when Claude's last message ended with a question or an AskUserQuestion call. Reads only the file tail."""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - TAIL_BYTES))
            tail = f.read().decode("utf-8", errors="replace").splitlines()
    except (OSError, TypeError, ValueError):
        return False
    for line in reversed(tail):
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # the first line of the tail is usually cut
        if entry.get("type") == "user" and not entry.get("isMeta"):
            content = (entry.get("message") or {}).get("content")
            if isinstance(content, list) and any(c.get("type") == "tool_result" for c in content if isinstance(c, dict)):
                continue  # tool results sit between Claude's messages
        if entry.get("type") != "assistant":
            continue
        for block in reversed((entry.get("message") or {}).get("content") or []):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                return block.get("name") == "AskUserQuestion"
            if block.get("type") == "text" and block.get("text", "").strip():
                return block["text"].rstrip().rstrip("*_`)").endswith("?")
        return False
    return False


def slug(prompt):
    return "-".join(w.lower() for w in words(prompt)[:6])[:48].strip("-") or "brief"


def brief_path(cwd, prompt, now=None):
    """<project>/.briefs/<stamp>-<slug>.md. Not under .claude/: Claude Code asks before every write there, even in
    acceptEdits mode and even when a PreToolUse hook allows it (tests/e2e/README.md)."""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return (Path(cwd or ".") / BRIEFS / f"{stamp}-{slug(prompt)}.md").as_posix()


ASK = ("If a material point is ambiguous or missing (scope, target files or data, output format, a choice between "
       "approaches, anything costly to redo), ask before doing any work: one AskUserQuestion call with one question "
       "per open point and 2-4 concrete options each, your recommended option first. Do not ask about what the code, "
       "files or sensible defaults settle; state those as assumptions. If AskUserQuestion is not available (a "
       "headless or delegated session), do not wait: take the recommended options as assumptions and proceed. If "
       "nothing material is open, proceed at once without asking.")
ASK_LIGHT = ("Only if a material point is still ambiguous, ask about it first with AskUserQuestion (2-4 concrete "
             "options, recommended first); in a headless or delegated session, assume the recommended option. ")
SILENT = ("Do not ask the user anything: where a point is open, choose the most sensible option, record it under "
          "Assumptions, and proceed.")


def context(prompt, cwd, mode, now=None):
    """The instruction injected for one prompt."""
    path = brief_path(cwd, prompt, now)
    handoff = ("Whenever you delegate any part of this work (Agent/Task subagents, council or War Room members, "
               "allies, side sessions or workflows), pass the brief verbatim, or its path, as the task; never pass "
               "the raw prompt alone.")
    if len(words(prompt)) >= DETAILED_WORDS or is_structured(prompt):
        return ("prompt-refiner: this prompt is already detailed. Before working, confirm your understanding in one "
                "line (goal and deliverable) and name any assumption you are making. "
                + (ASK_LIGHT if mode == "ask" else "") + "Then proceed. " + handoff)
    return ("prompt-refiner: before acting on this prompt, rewrite it into a brief with these headings: Goal, "
            "Deliverables, Inputs (files, data, context it relies on), Constraints, Acceptance checks (how to tell "
            "it is done), Assumptions, Open points. Fill it from the prompt, the conversation and a quick look at "
            "the project; do not invent requirements the user did not imply. "
            + (ASK if mode == "ask" else SILENT)
            + f" Once settled, update the brief with the answers and save it to {path} (if that folder is new, also "
            f"write {BRIEFS}/.gitignore containing `*`, so briefs stay out of git), show "
            "the user a short version of it, and work from the brief, not the raw prompt. " + handoff
            + " If this message only continues the current task (a follow-up, a small correction) and is clear, "
            "skip the brief and just do it. Skip the brief for pure questions that need no work beyond the answer.")


def hook_prompt(home, payload):
    """additionalContext for a prompt, or None when the refiner should stay silent."""
    if env_off():
        return None
    cfg = load_config(home)
    if not cfg["enabled"]:
        return None
    prompt = (payload or {}).get("prompt") or ""
    if prompt.lstrip().lower().startswith(BYPASS):
        return ("prompt-refiner: the user started this prompt with `raw:`. Treat the rest as the request exactly as "
                "written: no brief, no clarifying round.")
    n = len(words(prompt))
    if is_notice(prompt) or n < SHORT_WORDS:
        return None
    if n <= ANSWER_WORDS and last_assistant_asked(payload.get("transcript_path")):
        return None
    return context(prompt, payload.get("cwd"), cfg["mode"])


def status(home):
    cfg = load_config(home)
    state = "on" if cfg["enabled"] else "off"
    extra = " (but PROMPT_REFINER=off in this environment)" if env_off() else ""
    return f"prompt-refiner: {state}{extra}, mode {cfg['mode']}; config {config_path(home).as_posix()}"


def main(argv):
    home = claude_home()
    if argv == ["hook", "prompt"]:
        try:
            ctx = hook_prompt(home, json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}"))
        except Exception:  # a hook must never block the user's prompt
            ctx = None
        if ctx:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}))
        return 0
    if argv in (["on"], ["off"]):
        save_config(home, enabled=argv[0] == "on")
    elif len(argv) == 2 and argv[0] == "mode" and argv[1] in MODES:
        save_config(home, mode=argv[1])
    elif argv != ["status"]:
        print(__doc__)
        return 2
    print(status(home))
    return 0


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        sys.exit(3)  # the hook command then tries the next interpreter on PATH
    sys.exit(main(sys.argv[1:]))
