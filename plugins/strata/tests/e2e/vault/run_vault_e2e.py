"""Live end-to-end check of strata's second-brain vault with headless Claude Code and the plugin from this repo
(--plugin-dir). One Sonnet session (distill) and two Haiku sessions.

    py tests/e2e/vault/run_vault_e2e.py WORKDIR DATADIR     (both empty throwaway folders, outside any repo)

DATADIR is the strata data folder (MOAA_STRATA_DIR); the vault is DATADIR/brain via STRATA_VAULT, never ~/code/brain.
0. init     `strata.py vault init`: layout and `git init`, no commit.
1. capture  `graph.py capture` and `strata.py capture` append to inbox/<date>.md with time and project.
2. daily    a short chat in WORKDIR: its SessionEnd adds one line to daily/<date>.md.
3. distill  `/strata:wiki distill` in the vault: at least one new wiki page holding a captured fact, the inbox
            archived, log.md appended, lint clean.
4. rag      after `rag.py index` of the vault, a question answered only by the vault, with every tool denied: the
            transcript must show the "second-brain vault" passage.
Raw output is saved next to this script; summary.json holds the checks.
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
import graph  # noqa: E402
import strata  # noqa: E402

CAPTURES = ["Decided: the Qanat-9 mix prints with a 28 mm nozzle; 25 mm clogged twice.",
            "Idea: try the FTS5 trigram tokenizer for strata RAG on code identifiers.",
            "Todo: book the vane rheometer for Thursday's calibration run."]


def scrub(text):
    home = str(Path.home())
    short = os.environ.get("TEMP", "").split("\\AppData")[0] if os.name == "nt" else ""
    for h in sorted({s for h in (home, short) if h
                     for s in (h, h.replace("\\", "\\" * 2), h.replace("\\", "\\" * 4), h.replace("\\", "/"))},
                    key=len, reverse=True):
        text = text.replace(h, "~")
    return strata.redact(text)


def save(name, text):
    (HERE / name).write_text(scrub(text), encoding="utf-8")


def cli(name, argv, env, cwd=None):
    out = subprocess.run([sys.executable, *argv], env=env, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    save(f"{name}.txt", f"$ {' '.join(Path(a).name if a.endswith('.py') else a for a in argv)}\n{out.stdout}{out.stderr}")
    return out


def run(name, workdir, prompt, env, model="haiku", mode="dontAsk"):
    argv = [shutil.which("claude"), "-p", prompt, "--plugin-dir", str(PLUGIN), "--model", model,
            "--permission-mode", mode, "--output-format", "stream-json", "--verbose"]
    t0 = time.time()
    out = subprocess.run(argv, cwd=workdir, env=env, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=900)
    keep = [line for line in out.stdout.splitlines() if '"subtype":"init"' not in line.replace(" ", "")
            and not ('"hook_' in line and "Strata" not in line)]
    save(f"{name}.stream.jsonl", "\n".join(keep) + "\n")
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


def transcript_hits(name, session, marker):
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    hits = [line for t in home.glob(f"projects/*/{session}.jsonl")
            for line in t.read_text(encoding="utf-8", errors="replace").splitlines() if marker in line]
    save(f"{name}.transcript-hits.jsonl", "\n".join(hits) + "\n")
    return hits


def main(workdir, datadir):
    work, data = Path(workdir).resolve(), Path(datadir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    (data / "config.json").write_text(json.dumps({"auto": False}), encoding="utf-8")
    vault = data / "brain"
    env = {**os.environ, "MOAA_STRATA_DIR": str(data), "STRATA_VAULT": str(vault), "STRATA_CANARY": "off"}
    today = time.strftime("%Y-%m-%d")
    checks = {}

    cli("0-init", [str(PLUGIN / "strata.py"), "vault", "init"], env)
    checks["init: layout"] = all((vault / p).exists() for p in ("README.md", "inbox", "daily", "wiki/index.md",
                                                                 "wiki/log.md", ".git"))
    checks["init: no commit"] = subprocess.run(["git", "-C", str(vault), "log"], capture_output=True).returncode != 0

    cli("1-capture-a", [str(PLUGIN / "graph.py"), "capture", CAPTURES[0], "--project", str(work)], env)
    cli("1-capture-b", [str(PLUGIN / "strata.py"), "capture", CAPTURES[1], "--project", str(work)], env)
    cli("1-capture-c", [str(PLUGIN / "graph.py"), "capture", CAPTURES[2]], env, cwd=work)
    inbox = (vault / "inbox" / f"{today}.md").read_text(encoding="utf-8")
    save("1-inbox.md", inbox)
    checks["capture: three lines with time and project"] = (
        sum(1 for line in inbox.splitlines() if line.startswith("- ")) == 3 and f"[{work.name}] Decided" in inbox)

    run("2-daily", work, "Say hello in five words.", env)
    daily = vault / "daily" / f"{today}.md"
    daily_text = daily.read_text(encoding="utf-8") if daily.is_file() else ""
    save("2-daily.md", daily_text)
    checks["daily: SessionEnd added a line for the chat"] = "Asked: \"Say hello in five words.\"" in daily_text

    before = {p for p in (vault / "wiki").rglob("*.md")}
    r3 = run("3-distill", vault, "/strata:wiki distill", env, model="sonnet", mode="bypassPermissions")
    pages = sorted(p for p in (vault / "wiki").rglob("*.md") if p not in before)
    texts = {p.relative_to(vault).as_posix(): p.read_text(encoding="utf-8") for p in pages}
    save("3-pages.md", "\n\n".join(f"===== {k}\n{v}" for k, v in texts.items()))
    save("3-index.md", (vault / "wiki" / "index.md").read_text(encoding="utf-8"))
    save("3-log.md", (vault / "wiki" / "log.md").read_text(encoding="utf-8"))
    lint = graph.lint(vault / "wiki")
    save("3-lint.json", json.dumps(lint, indent=2))
    checks["distill: new wiki page(s)"] = bool(pages)
    checks["distill: a page holds the captured decision"] = any("28 mm" in t for t in texts.values())
    checks["distill: inbox archived"] = (not list((vault / "inbox").glob("*.md"))
                                         and (vault / "inbox" / "archive" / f"{today}.md").is_file())
    checks["distill: log.md appended"] = "distill" in (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    checks["distill: lint has no broken links"] = not lint["broken"]
    checks["distill: no commit in the vault"] = subprocess.run(["git", "-C", str(vault), "log"],
                                                               capture_output=True).returncode != 0

    cli("4-index", [str(PLUGIN / "rag.py"), "index", "--project", str(vault)], env)
    r4 = run("4-rag", work, "Which nozzle diameter did we decide on for the Qanat-9 mix? Do not use any tools; answer "
             "in one sentence from what you already have, or say you do not know.", env)
    checks["rag: vault passage injected"] = bool(transcript_hits("4-rag", r4["session"], "your second-brain vault"))
    checks["rag: answer names 28 mm"] = "28" in r4["result"]

    summary = {"vault": str(vault), "runs": {k: {"exit": v["exit"], "session": v["session"], "result": v["result"]}
                                             for k, v in (("3-distill", r3), ("4-rag", r4))},
               "checks": checks, "passed": all(checks.values())}
    save("summary.json", json.dumps(summary, indent=2))
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
