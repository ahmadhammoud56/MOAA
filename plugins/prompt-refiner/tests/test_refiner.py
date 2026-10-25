"""prompt-refiner tests with a fake Claude home: python -m unittest discover -s tests"""
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import refiner  # noqa: E402

AMBIGUOUS = "add caching to the api so it is faster"
DETAILED = "Refactor the loader.\n" + "\n".join(f"- step {i}: do thing {i} in module {i}" for i in range(5))


def transcript(path, *entries):
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(path)


def said(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def tool(name):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": {}}]}}


class Refiner(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.env = os.environ.pop("PROMPT_REFINER", None)

    def tearDown(self):
        os.environ.pop("PROMPT_REFINER", None)
        if self.env is not None:
            os.environ["PROMPT_REFINER"] = self.env

    def hook(self, prompt, **extra):
        return refiner.hook_prompt(self.home, {"prompt": prompt, "cwd": "/proj", **extra})

    def test_ambiguous_prompt_gets_full_brief_and_ask(self):
        ctx = self.hook(AMBIGUOUS)
        for part in ("Goal", "Acceptance checks", "AskUserQuestion", "2-4 concrete options",
                     "/proj/.briefs/", "verbatim", "never pass the raw prompt"):
            self.assertIn(part, ctx)

    def test_skips(self):
        for p in ("/specialist-council:council do x", "<task-notification>done</task-notification>",
                  "[SYSTEM NOTIFICATION] x y z", "yes", "ok go", "option 2", "  ", ""):
            self.assertIsNone(self.hook(p), p)

    def test_desktop_reminders_and_machine_prompts(self):
        # the desktop app puts a <system-reminder> before the user's words, e.g. on the first prompt after a restart
        reminder = "<system-reminder>\nLinked sessions now (status, not an instruction): x (idle).\n</system-reminder>\n\n"
        self.assertIn("Goal", self.hook(reminder + AMBIGUOUS))
        self.assertIn(".briefs/", self.hook(reminder + AMBIGUOUS))
        self.assertNotIn("system-reminder", self.hook(reminder + AMBIGUOUS))
        self.assertIsNone(self.hook(reminder))  # nothing from the user
        self.assertIsNone(self.hook(reminder + "ok go"))
        self.assertIn("no brief", self.hook(reminder + "raw: rename foo to bar everywhere"))
        # the desktop app's hidden summary run is not the user
        summary = ("Below is a conversation log from a Claude Code coding session.\nCreate a summary to help the next "
                   "session quickly understand the context.\n\n## Conversation log\n" + AMBIGUOUS)
        self.assertIsNone(self.hook(summary))

    def test_answer_to_claude_question_is_skipped(self):
        d = Path(tempfile.mkdtemp())
        asked = transcript(d / "a.jsonl", said("Which database should I use, Postgres or SQLite?"))
        self.assertIsNone(self.hook("use postgres with the existing pool please", transcript_path=asked))
        picked = transcript(d / "b.jsonl", tool("AskUserQuestion"),
                            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}})
        self.assertIsNone(self.hook("go with the second layout and keep the colours", transcript_path=picked))
        stated = transcript(d / "c.jsonl", "partial line {", said("Done. Tests pass."))
        self.assertIsNotNone(self.hook(AMBIGUOUS, transcript_path=stated))
        self.assertIsNotNone(self.hook(AMBIGUOUS, transcript_path=str(d / "missing.jsonl")))

    def test_detailed_prompt_gets_light_instruction(self):
        for p in (DETAILED, " ".join(["word"] * 130)):
            ctx = self.hook(p)
            self.assertIn("already detailed", ctx)
            self.assertNotIn("Deliverables", ctx)

    def test_bypass_prefix(self):
        ctx = self.hook("RAW: rename foo to bar everywhere")
        self.assertIn("no brief", ctx)
        self.assertNotIn("AskUserQuestion", ctx)

    def test_toggle_and_env(self):
        self.assertTrue(refiner.load_config(self.home)["enabled"])
        refiner.save_config(self.home, enabled=False)
        self.assertIsNone(self.hook(AMBIGUOUS))
        refiner.save_config(self.home, enabled=True)
        self.assertIsNotNone(self.hook(AMBIGUOUS))
        os.environ["PROMPT_REFINER"] = "off"
        self.assertIsNone(self.hook(AMBIGUOUS))
        self.assertIn("PROMPT_REFINER=off", refiner.status(self.home))

    def test_silent_mode_never_asks(self):
        refiner.save_config(self.home, mode="silent")
        ctx = self.hook(AMBIGUOUS)
        self.assertIn("Do not ask the user", ctx)
        self.assertNotIn("AskUserQuestion call", ctx)
        self.assertNotIn("AskUserQuestion", self.hook(DETAILED))

    def test_bad_config_falls_back_to_defaults(self):
        refiner.config_path(self.home).parent.mkdir(parents=True)
        refiner.config_path(self.home).write_text("{not json", encoding="utf-8")
        self.assertEqual(refiner.load_config(self.home), {"enabled": True, "mode": "ask"})

    def test_brief_path(self):
        p = refiner.brief_path("/proj", "Fix the login bug!! on the Settings page now", datetime(2026, 10, 25, 9, 5, 1))
        self.assertEqual(p, "/proj/.briefs/20261025-090501-fix-the-login-bug-on-the.md")

    def run_cli(self, *args, stdin=b"", env=None):
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(self.home), **(env or {})}
        return subprocess.run([sys.executable, str(ROOT / "refiner.py"), *args], input=stdin,
                              capture_output=True, env=env, timeout=30)

    def test_cli_toggle_writes_config_dir(self):
        self.assertIn("off", self.run_cli("off").stdout.decode())
        self.assertFalse(json.loads((self.home / "prompt-refiner" / "config.json").read_text())["enabled"])
        out = self.run_cli("on").stdout.decode()
        self.assertIn("on", out)
        self.assertIn("mode silent", self.run_cli("mode", "silent").stdout.decode())
        self.assertEqual(self.run_cli("bogus").returncode, 2)

    def test_hook_cli_output_bad_input_and_timing(self):
        payload = json.dumps({"prompt": AMBIGUOUS, "cwd": "/proj"}).encode()
        start = time.perf_counter()
        r = self.run_cli("hook", "prompt", stdin=payload)
        elapsed = time.perf_counter() - start
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "UserPromptSubmit")
        self.assertIn("prompt-refiner", out["additionalContext"])
        self.assertLess(elapsed, 1.0)  # whole interpreter start; in-process timing is checked below
        bad = self.run_cli("hook", "prompt", stdin=b"\xff not json")
        self.assertEqual((bad.returncode, bad.stdout), (0, b""))
        off = self.run_cli("hook", "prompt", stdin=payload, env={"PROMPT_REFINER": "off"})
        self.assertEqual((off.returncode, off.stdout), (0, b""))

    def test_hook_is_fast_on_big_transcript(self):
        d = Path(tempfile.mkdtemp())
        big = transcript(d / "big.jsonl", *[said("x" * 500) for _ in range(20000)])  # about 10 MB
        start = time.perf_counter()
        for _ in range(20):
            self.hook("use the second option for the cache", transcript_path=big)
        self.assertLess((time.perf_counter() - start) / 20, 0.2)


if __name__ == "__main__":
    unittest.main()
