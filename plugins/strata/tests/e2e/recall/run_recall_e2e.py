"""Live end-to-end check of strata's virtual context (recall of evicted turns) with headless Claude Code and the
installed plugin. One Sonnet call (it writes the handoff) and about six Haiku calls.

    py tests/e2e/recall/run_recall_e2e.py WORKDIR DATADIR     (both empty throwaway folders)

WORKDIR holds rig.cfg, 119 settings of a print rig; one of them, purge_dwell_s on line 91, is the needle. DATADIR is the strata
data folder for these runs (MOAA_STRATA_DIR), so the real memory is untouched.
Handoff path
  1-read    Claude reads rig.cfg; STRATA_HANDOFF_THRESHOLD=1 makes it write a handoff right after.
  2-off     a new chat takes the handoff with STRATA_RECALL=off and is asked the needle with every tool denied.
  3-recall  the handoff is made pending again; a new chat (recall on) is asked the same: it must answer from the
            recalled tool result, and the transcript must show "Strata recall".
Compaction path
  4a-read   Claude reads rig.cfg (no handoff).   4b-compact  /compact on that session.
  4c-ask    the same session is asked the needle with tools denied: "Strata recall" must hold it.
summary.json records each check and whether the handoff files or the compaction summary held the needle themselves
(then the answer alone would not prove recall).
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
NEEDLE, VALUE = "purge_dwell_s", "37"
SETTINGS = ["nozzle_diameter_mm = 25", "layer_height_mm = 12", "print_speed_mm_s = 80", "pump_rpm = 140",
            "hose_length_m = 9", "accelerator_dose_pct = 1.8", "bed_temp_c = 22", "travel_speed_mm_s = 150",
            "retract_mm = 4", "z_offset_mm = 0.6", "sensor_rate_hz = 250", "gateway_port = 48213",
            f"{NEEDLE} = {VALUE}", "mixer_rpm = 300", "batch_size_l = 40", "cleaning_interval_min = 90",
            "max_layers = 220", "camera_fps = 15", "camera_exposure_ms = 8", "pressure_limit_bar = 18",
            "flow_target_l_min = 6", "slump_target_mm = 55", "open_time_min = 45", "cure_hold_h = 24",
            "robot_payload_kg = 30", "tcp_offset_mm = 140", "spiral_pitch_mm = 10", "infill_pct = 0",
            "wall_count = 2", "log_level = info"]
SETTINGS = [s for s in SETTINGS if not s.startswith(NEEDLE)]
SETTINGS += [f"axis_{a}_{k}_{i} = {(i * 7 + len(k)) % 97}" for i in range(1, 16) for a in "xyz"
             for k in ("gain", "limit")][:89]  # 119 settings, so a handoff or a summary does not copy them all
SETTINGS.insert(89, f"{NEEDLE} = {VALUE}")  # line 91 of the file
QUESTION = (f"What value of {NEEDLE} did the rig.cfg file set? Do not use any tools; answer in one sentence from "
            "what you already have, or say you do not know.")


def run(name, workdir, prompt, env_extra, extra=(), model="haiku"):
    env = {**os.environ, **env_extra}
    argv = [shutil.which("claude"), "-p", prompt, "--model", model, "--output-format", "stream-json", "--verbose",
            *extra]
    t0 = time.time()
    out = subprocess.run(argv, cwd=workdir, env=env, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=900)
    keep = [line for line in out.stdout.splitlines()  # the init and command lists show the local setup
            if not any(f'"subtype":"{s}"' in line.replace(" ", "") for s in ("init", "commands_changed"))
            and not ('"hook_' in line and "Strata" not in line)]
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


def transcript(session):
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return [line for t in home.glob(f"projects/*/{session}.jsonl")
            for line in t.read_text(encoding="utf-8", errors="replace").splitlines()]


def hits(name, session, marker="Strata recall"):
    """Hook attachments holding the marker (not the whole request blob, which holds the local setup)."""
    found = [line for line in transcript(session) if marker in line and '"type":"attachment"' in line.replace(" ", "")]
    (HERE / f"{name}.transcript-hits.jsonl").write_text("\n".join(found) + ("\n" if found else ""), encoding="utf-8")
    return found


def scrub():
    home = str(Path.home())
    spellings = {home, home.replace("\\", "\\\\"), home.replace("\\", "\\\\\\\\"), home.replace("\\", "/")}
    for f in HERE.iterdir():
        if f.suffix in (".jsonl", ".json", ".md"):
            text = f.read_text(encoding="utf-8")
            for s in sorted(spellings, key=len, reverse=True):
                text = text.replace(s, "~")
            f.write_text(text, encoding="utf-8")


def main():
    work, data = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    (work / "rig.cfg").write_text("# print rig settings\n" + "\n".join(SETTINGS) + "\n", encoding="utf-8")
    env = {"MOAA_STRATA_DIR": str(data), "STRATA_RAG": "off"}  # RAG off: it would find rig.cfg on its own
    deny = ("--permission-mode", "dontAsk")
    checks, notes = {}, {}

    read = run("1-read", work, "Read rig.cfg and tell me in one sentence what kind of machine it configures.",
               {**env, "STRATA_HANDOFF_THRESHOLD": "1"}, ("--permission-mode", "bypassPermissions"),
               model="sonnet")  # Haiku answered without writing the handoff in the first run
    base = work / ".claude" / "handoff"
    handoffs = sorted(base.glob("*/HANDOFF.md"))
    checks["handoff written"] = bool(handoffs)
    d = handoffs[-1].parent if handoffs else None
    held = "".join((d / f).read_text(encoding="utf-8") for f in ("HANDOFF.md", "CONTEXT.md") if d and (d / f).exists())
    notes["handoff files hold the needle"] = NEEDLE in held or f"= {VALUE}" in held
    for f in ("HANDOFF.md", "CONTEXT.md"):
        if d and (d / f).exists():
            shutil.copy(d / f, HERE / f"1-written-{f}")

    off = run("2-off", work, QUESTION, {**env, "STRATA_RECALL": "off"}, deny)
    checks["off: handoff taken"] = any("Strata context handoff" in line for line in transcript(off["session"]))
    checks["off: no recall"] = not hits("2-off", off["session"])
    notes["off answer names the value"] = VALUE in off["result"]

    if d:
        os.utime(d / "HANDOFF.md", (time.time() + 5, time.time() + 5))  # pending again for the next chat
    rec = run("3-recall", work, QUESTION, env, deny)
    found = hits("3-recall", rec["session"])
    checks["recall: evicted tool result injected"] = any(f"{NEEDLE} = {VALUE}" in h for h in found)
    checks["recall: answer names the value"] = VALUE in rec["result"]

    a = run("4a-read", work, "Read rig.cfg and tell me how many settings it has.", {**env, "STRATA_HANDOFF": "off"},
            ("--permission-mode", "bypassPermissions"))
    run("4b-compact", work, "/compact", {**env, "STRATA_HANDOFF": "off"}, ("--resume", a["session"]))
    summary_lines = [line for line in transcript(a["session"]) if "isCompactSummary" in line]
    notes["compaction summary holds the needle"] = any(NEEDLE in line for line in summary_lines)
    c = run("4c-ask", work, QUESTION, {**env, "STRATA_HANDOFF": "off"}, ("--resume", a["session"], *deny))
    found = hits("4c-ask", c["session"])
    checks["compact: evicted tool result injected"] = any(f"{NEEDLE} = {VALUE}" in h for h in found)
    checks["compact: answer names the value"] = VALUE in c["result"]

    summary = {"checks": checks, "passed": all(checks.values()), "notes": notes,
               "answers": {"off": off["result"], "recall": rec["result"], "compact": c["result"]},
               "date": time.strftime("%Y-%m-%d %H:%M")}
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    scrub()
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
