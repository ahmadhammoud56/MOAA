"""War Room worker hooks. Usage: python hooks.py stop|statusline|posttool|sessionstart  (hook JSON on stdin)

stop          Keep the worker alive: long-poll the inbox (no tokens while waiting). A message, or an open
              task on the board, is fed back as a block reason so the worker carries on by itself.
statusline    Record the usage meter (rate_limits), context and cost for the conductor's limit guard.
posttool      Log each tool call as an event and refresh the heartbeat (dashboard activity feed).
sessionstart  On resume or compaction, re-inject the last checkpoint, claimed tasks and unread count.

A hook must never break the session, so every failure exits 0 silently (and is logged when possible).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bus import Bus  # noqa: E402


def stop(bus, data):
    bus.heartbeat("parked: waiting for inbox")
    deadline = time.time() + float(os.environ.get("WARROOM_WAIT", "570"))
    while time.time() < deadline:
        if bus.control("run") == "stop":
            bus.heartbeat("stopped by conductor")
            return
        msgs = bus.peek_inbox()
        if msgs:
            text = "\n".join(f"- from {m['sender']}: {m['body']}" for m in msgs)
            bus.heartbeat("woken by inbox")
            print(json.dumps({"decision": "block", "reason": f"War Room inbox:\n{text}\nAct on these, checkpoint, then stop again."}),
                  flush=True)
            bus.mark_read([m["id"] for m in msgs])  # only after the reason is handed to Claude Code
            return None
        if bus.control("claims") != "paused" and bus.open_tasks(bus.agent):
            bus.heartbeat("woken by open task")
            return {"decision": "block", "reason": "There are open tasks on the War Room board. Call claim_task and continue."}
        time.sleep(2)
    bus.heartbeat("idle: wait timed out")  # conductor wakes idle workers with a resume


def statusline(bus, data):
    rl = data.get("rate_limits") or {}
    five, week = rl.get("five_hour") or {}, rl.get("seven_day") or {}
    ctx = data.get("context_window") or {}
    cost = data.get("cost") or {}
    bus.put_meter(five_pct=five.get("used_percentage"), five_reset=five.get("resets_at"),
                  week_pct=week.get("used_percentage"), week_reset=week.get("resets_at"),
                  context_pct=ctx.get("used_percentage") if isinstance(ctx, dict) else None,
                  cost_usd=cost.get("total_cost_usd") if isinstance(cost, dict) else None,
                  transcript=data.get("transcript_path"))
    parts = [f"war-room {bus.agent}"]
    if five.get("used_percentage") is not None:
        parts.append(f"5h {five['used_percentage']}%")
    if week.get("used_percentage") is not None:
        parts.append(f"7d {week['used_percentage']}%")
    if bus.control("claims") == "paused":
        parts.append("CLAIMS PAUSED")
    print("  ".join(parts))


def posttool(bus, data):
    name = data.get("tool_name", "?")
    if name.startswith("mcp__bus__"):
        return  # bus tools log their own events
    inp = data.get("tool_input") or {}
    target = inp.get("file_path") or inp.get("command") or inp.get("pattern") or inp.get("description") or ""
    bus.event("tool", f"{name} {str(target)[:120]}")
    bus.heartbeat(f"working: {name}")


def sessionstart(bus, data):
    ck = bus.last_checkpoint()["checkpoint"]
    claimed = bus.claimed_by(bus.agent)
    if not ck and not claimed:
        return
    lines = [f"War Room context restored for {bus.agent} (session {data.get('source', 'start')})."]
    if ck:
        lines.append(f"Last checkpoint: {ck['summary']}")
    for t in claimed:
        lines.append(f"Still claimed by you: #{t['id']} {t['title']} - {t['detail']}")
    lines.append(f"Unread inbox messages: {bus.unread(bus.agent)}. Continue from here.")
    bus.event("restore", data.get("source", "start"))
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(lines)}}


def main():
    event = sys.argv[1]
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
        bus = Bus(os.environ["WARROOM_DB"], os.environ["WARROOM_AGENT"])
    except Exception:
        return
    try:
        out = {"stop": stop, "statusline": statusline, "posttool": posttool, "sessionstart": sessionstart}[event](bus, data)
        if out:
            print(json.dumps(out))
    except Exception as e:
        try:
            bus.event("hook-error", f"{event}: {e}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
