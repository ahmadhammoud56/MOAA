"""Live check (0.15.1): machine sessions leave a pending handoff alone, a user's first prompt takes it, and that first
prompt also gets prompt-refiner and moaa-catalog context even with the desktop app's <system-reminder> in front.

    py tests/e2e/run_machine_e2e.py WORKDIR     (WORKDIR: an empty throwaway folder outside any git repository)

Runs headless Claude Code (Haiku) three times in WORKDIR, with strata, prompt-refiner and moaa-catalog loaded from
this checkout (--plugin-dir) and their installed copies switched off for the run:
  A-summary  the desktop app's hidden summary prompt ("Below is a conversation log ...")
  B-child    an ordinary prompt from a process strata started (strata.child_env(): MOAA_STRATA_CHILD and the others)
  C-user     a user's first prompt with a leading <system-reminder>, as the desktop app sends it after a restart
Evidence goes to tests/e2e/machine/ here and to prompt-refiner/tests/e2e/first-prompt/: per run the transcript
records holding a hook's context, the hook lines of the debug log (with durations), and summary.json with the checks.
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
PLUGINS = HERE.parents[2]
sys.path.insert(0, str(PLUGINS / "strata"))
import strata  # noqa: E402

OUT = HERE / "machine"
REFINER_OUT = PLUGINS / "prompt-refiner" / "tests" / "e2e" / "first-prompt"
MARKERS = {"handoff": "Strata context handoff", "refiner": "prompt-refiner:", "catalog": "moaa-catalog:"}
OURS = ("strata@moaa", "prompt-refiner@moaa", "moaa-catalog@moaa")
SUMMARY_PROMPT = ("Below is a conversation log from a Claude Code coding session.\nCreate a summary to help the next "
                  "session quickly understand the context.\n\n## Conversation log\n**User:** Set up Stripe subscription "
                  "webhooks for billing.\n\n**Claude:** Done.\n\n## Output format (Markdown only, no preamble)\n"
                  "## Session Summary")
CHILD_PROMPT = "Set up Stripe subscription webhooks for billing in this folder? Do not do it; just reply OK."
USER_PROMPT = ("<system-reminder>\nLinked sessions now (status, not an instruction): helper = local_x (idle).\n"
               "</system-reminder>\n\nHi again. What should we do next here, and which skill would help set up Stripe "
               "subscription webhooks for billing? Answer briefly and do not change any files.")


def scrub(text):
    home = str(Path.home())
    short = os.environ.get("TEMP", "").split("\\AppData")[0] if os.name == "nt" else ""
    for h in sorted({h for h in (home, short) if h}, key=len, reverse=True):
        for s in (h.replace("\\", "\\" * 4), h.replace("\\", "\\" * 2), h, h.replace("\\", "/")):
            text = text.replace(s, "~")
    for user in {Path(h).name for h in (home, short) if h}:  # other spellings: MSYS drive prefix, lower case, ...
        text = re.sub(r"(?i)(?:[a-z]:|/[a-z])?[\\/]+Users[\\/]+" + re.escape(user), "~", text)
        text = re.sub(r"(?i)[a-z]--Users-" + re.escape(re.sub(r"[^\w]", "-", user)), "~", text)  # project slugs
    return text


def save(name, text):
    for d in (OUT, REFINER_OUT):
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(scrub(text), encoding="utf-8")


def hook_lines(log):
    """Debug-log lines on hook runs: our three plugins' commands with their status and duration, the hook events'
    totals, and what the mods chain did with classic hooks (the flightdeck notice). Long lines are cut."""
    keep = re.compile(r"Hooks: (SessionStart|UserPromptSubmit)\S* \[for p in .*(strata|refiner|catalog)\.py|"
                      r"classic\.(SessionStart|UserPromptSubmit) (settled|bypassed)")
    launcher = re.compile(r"\[for p in .*?\$p \"[^\"]*[\\/](\w+\.py)\" (hook [\w-]+);.*?exit 0\]")
    return [launcher.sub(r"[\1 \2]", ln)[:400] for ln in log.splitlines() if keep.search(ln) and "allow rule" not in ln]


def run(name, work, prompt, env_extra):
    debug = work.parent / f"{work.name}-{name}.debug.log"
    argv = [shutil.which("claude"), "-p", prompt, "--model", "haiku", "--permission-mode", "dontAsk",
            "--output-format", "stream-json", "--verbose", "--debug", "hooks", "--debug-file", str(debug),
            "--settings", json.dumps({"enabledPlugins": {p: False for p in OURS}})]
    for p in ("strata", "prompt-refiner", "moaa-catalog"):
        argv += ["--plugin-dir", str(PLUGINS / p)]
    t0 = time.time()
    out = subprocess.run(argv, cwd=work, env={**os.environ, **env_extra}, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=900)
    events = [json.loads(line) for line in out.stdout.splitlines() if line.startswith("{")]
    session = next((e.get("session_id") for e in events if e.get("session_id")), None)
    result = next((e for e in reversed(events) if e.get("type") == "result"), {}).get("result", "")
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    lines = [ln for t in home.glob(f"projects/*/{session}.jsonl")
             for ln in t.read_text(encoding="utf-8", errors="replace").splitlines()]
    hits = [ln for ln in lines if re.search(r'"type":"hook_(additional_context|system_message)"', ln)
            and any(m in ln for m in MARKERS.values())]  # hook output only: the skill listing names these plugins too
    log = debug.read_text(encoding="utf-8", errors="replace") if debug.exists() else ""
    save(f"{name}.transcript-hits.jsonl", "\n".join(hits) + "\n")
    save(f"{name}.debug-hooks.log", "\n".join(hook_lines(log)) + "\n")
    save(f"{name}.result.txt", f"exit {out.returncode}, session {session}, {time.time() - t0:.0f}s\n\n{result}\n")
    print(f"[{name}] exit {out.returncode} in {time.time() - t0:.0f}s, session {session}")
    return {"exit": out.returncode, "session": session, "result": result,
            "got": {k: any(m in ln for ln in hits) for k, m in MARKERS.items()}}


def hook_timings():
    """Wall time of each UserPromptSubmit hook command, run as Claude Code runs it (bash, the launcher loop), on the
    C-user payload: the first call after a fresh Python start and a repeat."""
    bash = shutil.which("bash")
    timings = {}
    for plugin, cmd in (("strata", "context-check"), ("prompt-refiner", "prompt"), ("moaa-catalog", "prompt")):
        hooks = json.loads((PLUGINS / plugin / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        command = next(h["command"] for h in hooks["UserPromptSubmit"][0]["hooks"])
        payload = json.dumps({"prompt": USER_PROMPT, "cwd": str(Path.cwd()), "session_id": "timing",
                              "transcript_path": "", "hook_event_name": "UserPromptSubmit"})
        runs = []
        for _ in range(2):
            t0 = time.perf_counter()
            subprocess.run([bash, "-c", command], input=payload, capture_output=True, text=True,
                           env={**os.environ, "CLAUDE_PLUGIN_ROOT": (PLUGINS / plugin).as_posix()})
            runs.append(round(time.perf_counter() - t0, 3))
        timings[f"{plugin} {cmd}"] = runs
    return timings


def main(workdir):
    work = Path(os.path.realpath(workdir))
    work.mkdir(parents=True, exist_ok=True)
    data = work.parent / (work.name + "-strata-data")  # keeps the user's real strata memory out of the test
    data.mkdir(exist_ok=True)
    (data / "config.json").write_text(json.dumps({"auto": False}), encoding="utf-8")
    env = {"MOAA_STRATA_DIR": str(data)}
    d = strata.new_handoff_dir(str(work), "writer-session", "threshold")
    (d / "HANDOFF.md").write_text("# Handoff\n## Goal\nTiny e2e check.\n## Next actions\n1. Tell the user you resumed "
                                  "from the handoff and that the next step is to write tests.\n", encoding="utf-8")
    (d.parent / "latest").write_text(d.name + "\n", encoding="utf-8")
    consumed = lambda: (d / ".consumed").exists()  # noqa: E731
    checks = {}

    a = run("A-summary", work, SUMMARY_PROMPT, env)
    checks["A summary run: handoff not consumed"] = not consumed()
    checks["A summary run: no handoff, refiner or catalog context"] = not any(a["got"].values())

    b = run("B-child", work, CHILD_PROMPT, {**env, **{k: v for k, v in strata.child_env().items()
                                                      if k not in os.environ or k == strata.CHILD}})
    checks["B strata helper process: handoff not consumed"] = not consumed()
    checks["B strata helper process: no handoff, refiner or catalog context"] = not any(b["got"].values())

    c = run("C-user", work, USER_PROMPT, env)
    checks["C user's first prompt: handoff consumed"] = consumed()
    checks["C user's first prompt: handoff context given"] = c["got"]["handoff"]
    checks["C user's first prompt: refiner context despite the leading <system-reminder>"] = c["got"]["refiner"]
    checks["C user's first prompt: catalog context despite the leading <system-reminder>"] = c["got"]["catalog"]
    checks["C Claude says it resumed"] = "resum" in c["result"].lower() or "handoff" in c["result"].lower()

    summary = {"workdir": "<throwaway>", "claude": subprocess.run([shutil.which("claude"), "--version"],
               capture_output=True, text=True).stdout.strip(), "runs": {"A-summary": a, "B-child": b, "C-user": c},
               "hook_wall_times_s": hook_timings(), "checks": checks, "passed": all(checks.values())}
    save("summary.json", json.dumps(summary, indent=2))
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    print(json.dumps(summary["hook_wall_times_s"]))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
