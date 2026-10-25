"""Virtual context tests (recall of evicted turns): python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import strata as memory  # noqa: E402
from test_handoff import Sandbox, assistant, write_jsonl  # noqa: E402

CONFIG = "[tool result] gateway_port = 48213\nsensor_rate_hz = 250\nnozzle_diameter_mm = 25\nbatch_label = QX-17"


def first_chat(path):
    """A conversation that read a config file (a tool result) and talked about the plan."""
    return write_jsonl(path, [
        {"type": "user", "timestamp": "2026-10-25T10:00:00.000Z", "message": {"content": "Read rig.cfg and plan the test."}},
        {"type": "assistant", "timestamp": "2026-10-25T10:00:01.000Z", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "rig.cfg"}}]}},
        {"type": "user", "timestamp": "2026-10-25T10:00:02.000Z", "message": {"content": [
            {"type": "tool_result", "content": CONFIG.replace("[tool result] ", "")}]}},
        {"type": "assistant", "timestamp": "2026-10-25T10:00:03.000Z",
         "message": {"content": [{"type": "text", "text": "The plan: calibrate first, then print."}]}},
        assistant(1000)])


class Recall(Sandbox):
    def prompt(self, session, text, transcript=None):
        t = transcript or write_jsonl(Path(self.dir) / f"{session}.jsonl", [assistant(1000)])
        out = memory.hook("context-check", json.dumps({
            "session_id": session, "transcript_path": t, "cwd": str(self.proj), "prompt": text,
            "hook_event_name": "UserPromptSubmit"}))
        return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""

    def hand_over(self):
        """s1 wrote a handoff (with its transcript in meta.json); s2 starts and sends its first prompt."""
        t1 = first_chat(Path(self.dir) / "s1.jsonl")
        d = memory.new_handoff_dir(str(self.proj), "s1", "threshold", t1)
        (d / "HANDOFF.md").write_text("# Handoff\nNext: run the rig test.", encoding="utf-8")
        memory.hook("session-start", json.dumps({"session_id": "s2", "cwd": str(self.proj), "source": "startup"}))
        return d

    def test_new_chat_recalls_a_tool_result_the_handoff_left_out(self):
        self.hand_over()
        text = self.prompt("s2", "Which gateway port did the rig config set for the sensor link?")
        self.assertIn("Strata context handoff", text)  # the handoff itself, then the recall
        self.assertIn("Strata recall", text)
        self.assertIn("48213", text)
        self.assertEqual(memory.load_state("s2")["lineage"], ["s1"])
        later = self.prompt("s2", "Remind me of the gateway port in the rig config")
        self.assertNotIn("Strata context handoff", later)  # taken once
        self.assertIn("48213", later)

    def test_unrelated_or_short_prompts_recall_nothing(self):
        self.hand_over()
        self.prompt("s2", "ok continue")
        self.assertEqual(self.prompt("s2", "Write a haiku about autumn leaves and rivers"), "")
        self.assertEqual(self.prompt("s2", "commit and push"), "")

    def test_lineage_chains_across_handoffs(self):
        self.hand_over()
        self.prompt("s2", "ok continue")
        t2 = write_jsonl(Path(self.dir) / "s2.jsonl", [assistant(1000)])
        d = memory.new_handoff_dir(str(self.proj), "s2", "threshold", t2)
        (d / "HANDOFF.md").write_text("# Handoff 2", encoding="utf-8")
        (memory.handoff_root(str(self.proj)) / "latest").write_text(d.name, encoding="utf-8")
        memory.hook("session-start", json.dumps({"session_id": "s3", "cwd": str(self.proj), "source": "startup"}))
        text = self.prompt("s3", "What was the gateway port from the rig config file?")
        self.assertEqual(memory.load_state("s3")["lineage"], ["s2", "s1"])
        self.assertIn("48213", text)

    def test_compaction_makes_own_earlier_turns_recallable(self):
        t = first_chat(Path(self.dir) / "c1.jsonl")
        self.assertEqual(self.prompt("c1", "Which gateway port did the rig config set?", t), "")  # still in context
        memory.hook("pre-compact", json.dumps({"session_id": "c1", "transcript_path": t, "cwd": str(self.proj),
                                               "trigger": "auto"}))
        self.assertIsNotNone(memory.load_state("c1").get("compacted"))
        self.assertIn("48213", self.prompt("c1", "Which gateway port did the rig config set?", t))

    def test_off_switches(self):
        self.hand_over()
        with mock_env(STRATA_RECALL="off"):
            text = self.prompt("s2", "Which gateway port did the rig config set for the sensor link?")
        self.assertIn("Strata context handoff", text)
        self.assertNotIn("Strata recall", text)
        cfg = memory.config()
        cfg["recall"] = False
        memory.save_config(cfg)
        self.assertEqual(self.prompt("s2", "Which gateway port did the rig config set for the sensor link?"), "")

    def test_compact_mode_never_asks_for_a_handoff(self):
        self.assertIsNotNone(self.check(190000))
        cfg = memory.config()
        cfg["handoff_mode"] = "compact"
        memory.save_config(cfg)
        self.assertIsNone(self.check(195000, session="s9"))

    def test_excerpt_centres_on_the_key_word(self):
        text = "a" * 3000 + " purge_dwell_s = 37 " + "b" * 3000
        out = memory.excerpt("rig " + text, ["rig", "purge_dwell_s"], 600)  # the specific word wins over "rig"
        self.assertIn("purge_dwell_s = 37", out)
        self.assertTrue(out.startswith("[...] ") and out.endswith(" [...]"))
        self.assertEqual(memory.excerpt("short", ["x"], 600), "short")
        self.assertTrue(memory.excerpt("c" * 1000, ["missing"], 100).startswith("c" * 100))

    def test_tool_rows_stay_out_of_consolidation(self):
        db = memory.connect()
        self.addCleanup(db.close)
        memory.ingest(db, "s1", "p", first_chat(Path(self.dir) / "s1.jsonl"))
        prompt = memory.build_prompt(db, "s1", memory.config())
        self.assertNotIn("48213", prompt)
        self.assertIn("calibrate first", prompt)


def mock_env(**kw):
    from unittest import mock
    return mock.patch.dict(os.environ, kw)


if __name__ == "__main__":
    unittest.main()
