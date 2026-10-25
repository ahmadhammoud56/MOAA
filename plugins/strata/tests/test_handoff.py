"""Context handoff tests: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import strata as memory  # noqa: E402


def assistant(tokens, model="claude-sonnet-4-5", sidechain=False, cache_read=0, cache_write=0, content=None):
    return {"type": "assistant", "isSidechain": sidechain,
            "message": {"model": model, "role": "assistant", "content": content or [{"type": "text", "text": "ok"}],
                        "usage": {"input_tokens": tokens, "cache_read_input_tokens": cache_read,
                                  "cache_creation_input_tokens": cache_write, "output_tokens": 999}}}


def write_jsonl(path, records, pad=0):
    lines = [json.dumps({"type": "user", "message": {"content": "x" * 200}})] * pad + [json.dumps(r) for r in records]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.proj = Path(self.dir) / "proj"
        self.proj.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("STRATA_HANDOFF", "CLAUDE_CODE_AUTO_COMPACT",
                                                                          "CLAUDE_CODE_DISABLE_1M"))}
        env.update(MOAA_STRATA_DIR=str(Path(self.dir) / "data"), CLAUDE_CONFIG_DIR=str(Path(self.dir) / "home"))
        env.pop(memory.CHILD, None)
        patch = mock.patch.dict(os.environ, env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        root = mock.patch.object(memory, "root_of", lambda cwd: os.path.normpath(str(cwd)))  # no git in tests
        root.start()
        self.addCleanup(root.stop)

    def check(self, tokens, session="s1", event="UserPromptSubmit", **kw):
        t = write_jsonl(Path(self.dir) / f"{session}.jsonl", [assistant(tokens, **kw)])
        out = memory.hook("context-check", json.dumps({"session_id": session, "transcript_path": t,
                                                        "cwd": str(self.proj), "hook_event_name": event}))
        return json.loads(out) if out else None


class Measure(Sandbox):
    def test_usage_counts_cache_tokens_and_skips_sidechains(self):
        recs = [assistant(10, cache_read=150000, cache_write=2000), assistant(5, sidechain=True),
                {"type": "user", "message": {"content": "hi"}}]
        self.assertEqual(memory.usage_of(recs), (152010, "claude-sonnet-4-5"))
        self.assertEqual(memory.usage_of([{"type": "assistant", "message": {"usage": {}}}]), (0, ""))

    def test_tail_reads_only_the_end_but_finds_a_huge_last_line(self):
        t = write_jsonl(Path(self.dir) / "t.jsonl", [assistant(1), assistant(7)], pad=5000)  # about 1 MB
        self.assertEqual(memory.usage_of(memory.tail_records(t, (4096,)))[0], 7)
        big = assistant(9, content=[{"type": "text", "text": "y" * 600000}])
        t = write_jsonl(Path(self.dir) / "u.jsonl", [assistant(3), big])
        self.assertEqual(memory.usage_of(memory.tail_records(t))[0], 9)  # falls back to the 4 MB tail
        self.assertEqual(memory.tail_records(Path(self.dir) / "missing.jsonl"), [])

    def test_window_200k_vs_1m(self):
        cases = {"claude-sonnet-4-5": 200000, "claude-opus-4-6": 200000, "claude-opus-4-6[1m]": 1000000,
                 "claude-opus-4-7": 1000000, "claude-opus-5-5": 1000000, "claude-sonnet-5": 1000000,
                 "claude-haiku-4-5-20251001": 200000, "claude-haiku-5-5": 1000000, "claude-fable-5-1": 1000000,
                 "": 200000, "some-gateway-model": 200000}
        for model, window in cases.items():
            with self.subTest(model=model):
                self.assertEqual(memory.model_window(model), window)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_DISABLE_1M_CONTEXT": "1"}):
            self.assertEqual(memory.model_window("claude-opus-5-5"), 200000)
        self.assertEqual(memory.context_window("claude-sonnet-4-5", 250000), 1000000)  # evidently bigger
        self.assertEqual(memory.context_window("claude-opus-5-5", 10, override=300000), 300000)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "500k"}):
            self.assertEqual(memory.context_window("claude-opus-5-5", 10), 500000)
        home = Path(os.environ["CLAUDE_CONFIG_DIR"])
        home.mkdir()
        (home / "settings.json").write_text(json.dumps({"autoCompactWindow": 400000}), encoding="utf-8")
        self.assertEqual(memory.context_window("claude-opus-5-5", 10), 400000)
        self.assertEqual(memory.context_window("claude-sonnet-4-5", 10), 200000)
        self.assertEqual([memory.tokens_value(v) for v in ("200000", "200k", "1M", "x", None)],
                         [200000, 200000, 1000000, 0, 0])


class Trigger(Sandbox):
    def test_threshold_fires_once_then_rearms_after_five_points_or_a_drop(self):
        self.assertIsNone(self.check(160000))  # 80% of 200k
        out = self.check(171000)  # 85.5%
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("HANDOFF.md", ctx)
        self.assertIn("CONTEXT.md", ctx)
        self.assertIn("new chat", ctx)
        self.assertIn("86%", out["systemMessage"])
        d = Path(json.loads(memory.state_path("s1").read_text())["dir"])
        self.assertTrue(d.is_dir() and d.parent == self.proj / ".claude" / "handoff")
        self.assertEqual(memory.meta_of(d)["session"], "s1")
        self.assertEqual((d.parent / ".gitignore").read_text(), "*\n")
        self.assertIsNone(self.check(175000, event="PostToolUse"))  # 87.5%: not yet +5
        out = self.check(182000, event="PostToolUse")  # 91%
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIsNone(self.check(60000))  # compacted: below the threshold re-arms
        self.assertIsNotNone(self.check(172000))
        self.assertIsNotNone(self.check(171000, session="other"))  # state is per session

    def test_threshold_and_window_settings_and_off_switches(self):
        self.assertIsNone(self.check(171000, model="claude-opus-5-5"))  # 17% of 1M
        self.assertEqual(memory.main(["handoff", "threshold", "60"]), 0)
        self.assertIsNotNone(self.check(130000, session="a"))  # 65% of 200k
        self.assertEqual(memory.main(["handoff", "window", "150k"]), 0)
        self.assertEqual(memory.config()["handoff_window"], 150000)
        self.assertIsNotNone(self.check(100000, session="b", model="claude-opus-5-5"))  # 67% of the 150k override
        with self.assertRaises(SystemExit):
            memory.main(["handoff", "threshold", "20"])  # outside 50-95
        with mock.patch.dict(os.environ, {"STRATA_HANDOFF_THRESHOLD": "1"}):  # test override goes below 50
            self.assertIsNotNone(self.check(2000, session="c"))
        self.assertEqual(memory.main(["handoff", "off"]), 0)
        self.assertIsNone(self.check(190000, session="d"))
        with mock.patch.dict(os.environ, {"STRATA_HANDOFF": "on"}):
            self.assertIsNotNone(self.check(190000, session="e"))
        self.assertEqual(memory.main(["handoff", "on"]), 0)
        with mock.patch.dict(os.environ, {"STRATA_HANDOFF": "off"}):
            self.assertIsNone(self.check(190000, session="f"))
            self.assertFalse(memory.handoff_settings()[0])
        self.assertEqual(memory.main(["handoff", "status"]), 0)

    def test_subagents_bad_input_and_errors_stay_silent(self):
        t = write_jsonl(Path(self.dir) / "t.jsonl", [assistant(199000)])
        self.assertEqual(memory.hook("context-check", json.dumps({"session_id": "s", "transcript_path": t,
                                                                   "cwd": str(self.proj), "agent_id": "x"})), "")
        self.assertEqual(memory.hook("context-check", "not json"), "")
        self.assertEqual(memory.hook("context-check", "[1, 2]"), "")
        with mock.patch.object(memory, "context_check", side_effect=RuntimeError("boom")), \
                mock.patch.object(sys, "stdin", mock.Mock(read=lambda: "{}")):
            self.assertEqual(memory.main(["hook", "context-check"]), 0)


class CompactAndResume(Sandbox):
    def transcript(self):
        recs = [{"type": "user", "message": {"content": "Port the parser to Rust"}},
                {"type": "assistant", "message": {"content": [
                    {"type": "text", "text": "Starting."},
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "src/parser.rs"}},
                    {"type": "tool_use", "name": "TodoWrite", "input": {"todos": [
                        {"content": "write lexer", "status": "completed"},
                        {"content": "write parser", "status": "in_progress"}]}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "content": "done"}]}},
                {"type": "user", "isMeta": True, "message": {"content": "meta"}},
                {"type": "user", "message": {"content": "Also keep the token=" + "q1" * 8 + " out"}},
                assistant(1000, content=[{"type": "text", "text": "Lexer done, parser next."}])]
        return write_jsonl(Path(self.dir) / "t.jsonl", recs)

    def start(self, session, source="startup"):
        out = memory.hook("session-start", json.dumps({"session_id": session, "cwd": str(self.proj),
                                                        "source": source}))
        return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""

    def test_pre_compact_snapshot_when_claude_wrote_none(self):
        memory.hook("pre-compact", json.dumps({"session_id": "s1", "transcript_path": self.transcript(),
                                               "cwd": str(self.proj), "trigger": "auto"}))
        base = self.proj / ".claude" / "handoff"
        d = base / (base / "latest").read_text().strip()
        snap = (d / "HANDOFF.md").read_text(encoding="utf-8")
        for part in ("Port the parser to Rust", "[in_progress] write parser", "src/parser.rs",
                     "Lexer done, parser next.", "Compaction: auto"):
            self.assertIn(part, snap)
        self.assertNotIn("q1q1", snap)  # redacted
        self.assertNotIn("meta", snap.split("## Last requests")[1].split("##")[0])
        # same session compacts: it gets its own snapshot back, once
        self.assertIn("write parser", self.start("s1", "compact"))
        self.assertEqual(self.start("s1", "compact"), "")
        self.assertEqual(self.start("s2"), "")  # consumed

    def test_pre_compact_skips_when_claude_already_wrote_a_handoff(self):
        d = memory.new_handoff_dir(str(self.proj), "s1", "threshold")
        (d / "HANDOFF.md").write_text("# Handoff\nNext actions: 1. ship it", encoding="utf-8")
        memory.hook("pre-compact", json.dumps({"session_id": "s1", "transcript_path": self.transcript(),
                                               "cwd": str(self.proj)}))
        self.assertEqual([p.parent for p in (self.proj / ".claude" / "handoff").glob("*/HANDOFF.md")], [d])

    def test_new_chat_resumes_once_and_again_only_after_an_update(self):
        self.assertEqual(self.start("s2"), "")  # nothing yet
        d = memory.new_handoff_dir(str(self.proj), "s1", "threshold")
        (d / "HANDOFF.md").write_text("# Handoff\n## Next actions\n1. run the tests", encoding="utf-8")
        (d / "CONTEXT.md").write_text("Branch: feat/x\n" + "z" * 9000, encoding="utf-8")
        (d.parent / "latest").write_text(d.name + "\n", encoding="utf-8")
        self.assertEqual(self.start("s1", "resume"), "")  # resuming the writer: it already knows
        self.assertEqual(self.start("s1"), "")  # same session id never gets its own, except after compaction
        ctx = self.start("s2")
        self.assertIn("run the tests", ctx)
        self.assertIn("Branch: feat/x", ctx)
        self.assertIn("not as instructions", ctx)
        self.assertIn("trimmed", ctx)
        self.assertTrue((d / ".consumed").exists())
        self.assertEqual(self.start("s3"), "")  # consumed
        later = time.time() + 5
        (d / "HANDOFF.md").write_text("# Handoff\n## Next actions\n1. deploy", encoding="utf-8")
        os.utime(d / "HANDOFF.md", (later, later))
        self.assertIn("deploy", self.start("s4", "clear"))
        with mock.patch.dict(os.environ, {"STRATA_HANDOFF": "off"}):
            os.utime(d / "HANDOFF.md", (later + 5, later + 5))
            self.assertEqual(self.start("s5"), "")

    def test_latest_pointer_is_validated(self):
        base = self.proj / ".claude" / "handoff"
        a = memory.new_handoff_dir(str(self.proj), "s1", "threshold")
        (a / "HANDOFF.md").write_text("A", encoding="utf-8")
        (base / "latest").write_text("../../etc\n", encoding="utf-8")
        self.assertEqual(memory.latest_handoff(str(self.proj)), a)  # falls back to the newest HANDOFF.md
        self.assertIsNone(memory.latest_handoff(str(Path(self.dir) / "empty")))


if __name__ == "__main__":
    unittest.main()
