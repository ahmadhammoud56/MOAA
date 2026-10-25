"""Live e2e for prompt-refiner: headless claude in throwaway folders, raw stream-json saved as evidence.

  py tests/e2e/run_e2e.py <plugin dir> [ambiguous|clear|off-env ...]
  py tests/e2e/run_e2e.py <plugin dir> redact   only replace the user name in saved files with <you>
"""
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PLUGIN = Path(sys.argv[1]).resolve()
OUT = PLUGIN / "tests" / "e2e"
OUT.mkdir(parents=True, exist_ok=True)
CLAUDE = shutil.which("claude")

CASES = {
    "ambiguous": ("make the script better", {}),
    "clear": ("In greet.py, change the greeting from Hello to Hi. Change nothing else.", {}),
    "off-env": ("make the script better", {"PROMPT_REFINER": "off"}),
}

HOME = re.compile(r"(?i)((?:[A-Z]:|/c)[\\/]+Users[\\/]+)(?!<you>)[^\\/\"']+")

for name in [] if sys.argv[2:] == ["redact"] else sys.argv[2:] or CASES:
    prompt, env = CASES[name]
    work = Path(os.path.realpath(tempfile.mkdtemp(prefix=f"refiner-e2e-{name}-")))  # long name: 8.3 paths are refused
    (work / "greet.py").write_text('def greet(n):\n    print("Hello " + n)\n\ngreet("world")\n', encoding="utf-8")
    cmd = [CLAUDE, "-p", prompt, "--plugin-dir", str(PLUGIN), "--output-format", "stream-json", "--verbose",
           "--include-hook-events", "--permission-mode", "acceptEdits", "--max-turns", "12"]
    r = subprocess.run(cmd, cwd=work, capture_output=True, env={**os.environ, **env}, timeout=900)
    (OUT / f"{name}.jsonl").write_bytes(r.stdout)
    briefs = sorted((work / ".briefs").glob("*")) if (work / ".briefs").exists() else []
    with open(OUT / f"{name}.files.txt", "w", encoding="utf-8") as f:
        f.write(f"prompt: {prompt}\nenv: {env}\nexit: {r.returncode}\nworkdir: {work}\nstderr tail: "
                f"{r.stderr.decode(errors='replace')[-800:]}\n\n--- greet.py after run ---\n"
                + (work / "greet.py").read_text(encoding="utf-8"))
        for b in briefs:
            f.write(f"\n--- brief {b.name} ---\n" + b.read_text(encoding="utf-8"))
    print(name, r.returncode, len(r.stdout), "briefs:", [b.name for b in briefs])

for f in list(OUT.glob("*.jsonl")) + list(OUT.glob("*.txt")):  # the repo is public: no user name in evidence
    f.write_text(HOME.sub(r"\1<you>", f.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
