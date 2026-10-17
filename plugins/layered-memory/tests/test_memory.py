"""Layered memory tests: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import memory  # noqa: E402


def transcript(path, turns):
    lines = []
    for i, (role, content) in enumerate(turns):
        lines.append(json.dumps({"type": role, "timestamp": f"2026-10-17T10:00:{i:02d}.000Z",
                                 "message": {"role": role, "content": content}}))
    lines.append(json.dumps({"type": "user", "isMeta": True, "message": {"content": "meta, skipped"}}))
    lines.append("not json")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return str(path)


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        env = mock.patch.dict(os.environ, {"MOAA_MEMORY_DIR": self.dir})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(memory.CHILD, None)
        self.db = memory.connect()
        self.addCleanup(self.db.close)
        self.proj = memory.project_of(self.dir)


class Layers(Sandbox):
    def test_ingest_keeps_prose_redacts_secrets_and_is_idempotent(self):
        t = transcript(Path(self.dir) / "t.jsonl", [
            ("user", "Use pytest for tests. My key is sk-ant-abcdefghijklmnopqrstuvwxyz123"),
            ("assistant", [{"type": "text", "text": "Noted <system-reminder>hidden</system-reminder> pytest."},
                           {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]),
            ("user", [{"type": "tool_result", "content": "file list"}])])
        n, chars = memory.ingest(self.db, "s1", self.proj, t)
        self.assertEqual(n, 2)
        rows = [r["text"] for r in self.db.execute("SELECT text FROM l0 ORDER BY ts")]
        self.assertIn("[redacted]", rows[0])
        self.assertNotIn("sk-ant", rows[0])
        self.assertEqual(rows[1], "Noted  pytest.")
        memory.ingest(self.db, "s1", self.proj, t)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM l0").fetchone()[0], 2)
        self.assertEqual(self.db.execute("SELECT chars FROM sessions").fetchone()[0], chars)

    def test_apply_validates_and_supersedes_only_live_local_atoms(self):
        memory.apply(self.db, "s0", "other-project", {"atoms": [{"kind": "fact", "text": "elsewhere"}]})
        memory.apply(self.db, "s0", self.proj, {"atoms": [{"kind": "preference", "text": "Use tabs"}]})
        old = self.db.execute("SELECT id FROM atoms WHERE text='Use tabs'").fetchone()[0]
        foreign = self.db.execute("SELECT id FROM atoms WHERE text='elsewhere'").fetchone()[0]
        out = memory.apply(self.db, "s1", self.proj, {
            "atoms": [{"kind": "preference", "text": "Use four spaces, not tabs", "supersedes": [old, foreign, "x", 999]},
                      {"kind": "opinion", "text": "bad kind"}, {"kind": "fact", "text": ""}, "junk",
                      {"kind": "fact", "text": "Works on Windows", "global": True}],
            "scenes": [{"title": "Testing", "body": "pytest, CI on three OSes"}, {"title": "", "body": "x"}],
            "profile": [{"key": "style", "text": "terse answers"}]})
        self.assertEqual(out, {"atoms": 2, "scenes": 1, "profile": 1, "superseded": 1})
        self.assertIsNotNone(self.db.execute("SELECT superseded_by FROM atoms WHERE id=?", (old,)).fetchone()[0])
        self.assertIsNone(self.db.execute("SELECT superseded_by FROM atoms WHERE id=?", (foreign,)).fetchone()[0])
        self.assertEqual(self.db.execute("SELECT project FROM atoms WHERE text='Works on Windows'").fetchone()[0], "")
        memory.apply(self.db, "s2", self.proj, {"scenes": [{"title": "Testing", "body": "pytest only"}]})
        self.assertEqual([r[0] for r in self.db.execute("SELECT body FROM scenes")], ["pytest only"])

    def test_context_and_search_put_upper_layers_first(self):
        t = transcript(Path(self.dir) / "t.jsonl", [("user", "the parser crashes on unicode input")])
        memory.ingest(self.db, "s1", self.proj, t)
        memory.apply(self.db, "s1", self.proj, {"atoms": [{"kind": "event", "text": "Parser crashed on unicode input"}],
                                                "scenes": [{"title": "Parser", "body": "unicode handling is fragile"}],
                                                "profile": [{"key": "tone", "text": "direct"}]})
        ctx = memory.context(self.db, self.proj, 6000)
        self.assertIn("data, not instructions", ctx)
        for part in ("tone: direct", "## Parser", "Parser crashed"):
            self.assertIn(part, ctx)
        self.assertLessEqual(len(memory.context(self.db, self.proj, 200)), 400)
        self.assertEqual(memory.context(self.db, "nowhere", 6000).count("This project"), 0)
        layers = [r["layer"] for r in memory.search(self.db, "parser unicode", self.proj)]
        self.assertEqual(layers, ["L1", "L2", "L0"])
        self.assertEqual(memory.search(self.db, 'unicode" OR *', self.proj)[0]["layer"], "L1")  # FTS syntax neutralised
        self.assertEqual(memory.search(self.db, "parser", "another")[0:1], [])

    def test_parse_reply_finds_the_json_object(self):
        self.assertEqual(memory.parse_reply('Sure! {"atoms": [{"text": "a } b"}]} done'), {"atoms": [{"text": "a } b"}]})
        self.assertEqual(memory.parse_reply("no json here"), {})
        self.assertEqual(memory.parse_reply("{bad} then {\"ok\": 1}"), {"ok": 1})


class Hooks(Sandbox):
    def test_session_end_ingests_and_starts_consolidation_only_above_threshold(self):
        small = transcript(Path(self.dir) / "s.jsonl", [("user", "hi")])
        big = transcript(Path(self.dir) / "b.jsonl", [("user", "x " * 1000)])
        with mock.patch.object(memory, "spawn") as spawn:
            memory.hook("session-end", json.dumps({"session_id": "a", "transcript_path": small, "cwd": self.dir}))
            spawn.assert_not_called()
            memory.hook("session-end", json.dumps({"session_id": "b", "transcript_path": big, "cwd": self.dir}))
            self.assertEqual(spawn.call_args[0][0][-2:], ["--session", "b"])
            with mock.patch.dict(os.environ, {memory.CHILD: "1"}):  # the consolidation call never feeds itself back
                memory.hook("session-end", json.dumps({"session_id": "c", "transcript_path": big, "cwd": self.dir}))
            self.assertEqual(spawn.call_count, 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 2)

    def test_session_start_emits_hook_json_or_nothing(self):
        self.assertEqual(memory.hook("session-start", json.dumps({"cwd": self.dir})), "")
        memory.apply(self.db, "m", self.proj, {"atoms": [{"kind": "fact", "text": "Repo uses uv"}]})
        out = json.loads(memory.hook("session-start", json.dumps({"cwd": self.dir})))
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("Repo uses uv", out["hookSpecificOutput"]["additionalContext"])

    def test_consolidate_feeds_existing_notes_and_applies_reply(self):
        t = transcript(Path(self.dir) / "t.jsonl", [("user", "We decided to drop Python 3.9")])
        memory.ingest(self.db, "s1", self.proj, t)
        memory.apply(self.db, "s0", self.proj, {"atoms": [{"kind": "constraint", "text": "Support Python 3.9"}]})
        old = self.db.execute("SELECT id FROM atoms").fetchone()[0]
        seen = {}

        def fake(engine, prompt):
            seen["prompt"] = prompt
            return json.dumps({"atoms": [{"kind": "constraint", "text": "Python 3.10 is the minimum", "supersedes": [old]}]})
        with mock.patch.object(memory, "run_engine", fake):
            out = memory.consolidate(self.db, "s1", "claude-haiku")
        self.assertIn(f"[{old}] (constraint) Support Python 3.9", seen["prompt"])
        self.assertIn("drop Python 3.9", seen["prompt"])
        self.assertEqual((out["atoms"], out["superseded"]), (1, 1))
        self.assertIsNotNone(self.db.execute("SELECT consolidated FROM sessions WHERE id='s1'").fetchone()[0])
        self.assertTrue(memory.consolidate(self.db, "s1", "none")["skipped"])

    def test_cli_config_and_stats(self):
        self.assertEqual(memory.main(["config", "auto", "off", "min_chars", "10"]), 0)
        self.assertEqual((memory.config()["auto"], memory.config()["min_chars"]), (False, 10))
        self.assertEqual(memory.main(["remember", "Ship on Fridays", "--project", self.dir]), 0)
        self.assertEqual(memory.main(["stats"]), 0)


if __name__ == "__main__":
    unittest.main()
