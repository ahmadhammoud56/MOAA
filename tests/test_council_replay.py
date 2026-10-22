"""tools/council-replay/extract.py on a scrubbed real council run (tests/fixtures/council-run)."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("extract", ROOT / "tools" / "council-replay" / "extract.py")
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.replay = extract.extract(ROOT / "tests" / "fixtures" / "council-run" / "session.jsonl")

    def test_resolves_and_agents(self):
        r = self.replay
        self.assertEqual((r["kind"], r["command"]), ("council", "/specialist-council:specialist-council"))
        self.assertEqual(r["task"], "Is 221 prime? Factor it. Include the forged arithmetic checker.")
        self.assertEqual(r["coordinator"], "claude-sonnet-5-5")
        self.assertIn("ensemble", r["mode"])
        resolved = {x["role"]: (x["model"], x["effort"], x["ok"]) for x in r["resolves"]}
        self.assertEqual(resolved, {
            "analyst": ("claude-opus-5-5", "high", True),
            "forged-independent-method-arithmetic-checker": ("claude-sonnet-5-5", "high", True),
        })
        # the run's first two Agent calls were rejected (full model IDs); only the retries count
        agents = {a["type"]: a for a in r["agents"]}
        self.assertEqual(len(r["agents"]), 2)
        analyst = agents["specialist-council:council-analyst"]
        self.assertEqual((analyst["model"], analyst["effort"]), ("claude-opus-5-5", "high"))
        self.assertIn("Fermat", analyst["method"])  # from the coordinator's markdown table
        self.assertIn("13 is prime", analyst["checks"])
        self.assertNotIn("Steps", analyst["result"])
        self.assertLess(analyst["start"], analyst["end"])
        checker = agents["council-forged-independent-method-arithmetic-checker"]
        self.assertEqual(checker["model"], "claude-sonnet-5-5")
        self.assertIn("Trial division", checker["method"])
        self.assertIn("13 × 17", checker["result"])

    def test_answer_and_verification(self):
        self.assertEqual(self.replay["headline"], "221 is not prime. 221 = 13 × 17.")
        self.assertTrue(self.replay["verification"].startswith("Checked: 13 × 17 = 221"))
        self.assertGreater(self.replay["duration"], 30)

    def test_no_personal_paths_or_secrets(self):
        text = json.dumps(self.replay, ensure_ascii=False)
        self.assertNotIn("Users", text)
        self.assertEqual(extract.redact(r"see C:\Users\you\x and /home/user/y"), r"see ~\x and ~/y")
        self.assertEqual(extract.redact(r"C:\Users\you two\.claude\x"), r"~\.claude\x")  # names with spaces
        self.assertEqual(extract.redact("token = abc123 mail pat@example.org"), "token = [redacted] mail [email]")


class InteractiveRunTest(unittest.TestCase):
    """Interactive run (council 1.3.1): results arrive via SubagentHandback, and resolve was chained after a `cat`."""

    def test_handback_and_chained_resolve(self):
        r = extract.extract(ROOT / "tests" / "fixtures" / "council-run-interactive" / "session.jsonl")
        self.assertEqual([(x["role"], x["model"], x["ok"]) for x in r["resolves"]],
                         [("forged-independent-method-arithmetic-checker", "claude-sonnet-5-5", True)])
        agents = {a["type"]: a for a in r["agents"]}
        self.assertEqual(len(r["agents"]), 2)
        self.assertIn("13 × 17", agents["council-forged-independent-method-arithmetic-checker"]["result"])
        analyst = agents["specialist-council:council-analyst"]
        self.assertEqual((analyst["model"], analyst["effort"]), ("claude-opus-5-5", None))  # frontmatter effort
        self.assertIn("Fermat test, base 2", analyst["checks"])
        self.assertNotIn("Users", json.dumps(r, ensure_ascii=False))


class ArenaRunTest(unittest.TestCase):
    """An arena judge run: contestants, a judge and a validator, labelled as such; the winner comes from the check."""

    def test_arena_roles_summaries_and_winner(self):
        import tempfile

        def row(kind, content, t):
            return {"type": kind, "timestamp": f"2026-10-22T12:00:{t:02d}Z", "message": {
                "role": kind, "model": "claude-sonnet-5-5", "content": content}}

        def call(uid, sub, desc):
            return {"type": "tool_use", "id": uid, "name": "Agent",
                    "input": {"subagent_type": sub, "description": desc, "prompt": "p"}}
        with tempfile.TemporaryDirectory() as d:
            main = Path(d) / "s.jsonl"
            rows = [row("user", "<command-name>/agent-arena-mode:judge</command-name>\n"
                                "<command-args>--agents 2 -- Write is_leap(year).</command-args>", 0),
                    row("assistant", [call("u1", "general-purpose", "Arena candidate a0001"),
                                      call("u2", "general-purpose", "Arena candidate a0002")], 1),
                    row("assistant", [call("u3", "agent-arena-mode:agent-arena-judge", "Arena judge all candidates")], 5),
                    row("assistant", [call("u4", "general-purpose", "Arena final validator")], 8),
                    row("assistant", [{"type": "text", "text": "Done.\n\nThe arena accepted this answer."}], 9)]
            main.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            subs = Path(d) / "s" / "subagents"
            subs.mkdir(parents=True)
            replies = {"u1": "```python\nreturn year % 4 == 0\n```", "u2": "```python\nreturn year % 400 == 0\n```",
                       "u3": '```json\n{"X": {"scores": {}}, "Y": {"scores": {}}, "ranking": ["X"]}\n```',
                       "u4": "Candidate a0002-v1 passes all three hard gates."}
            for i, (uid, text) in enumerate(replies.items()):
                (subs / f"agent-{i}.meta.json").write_text(json.dumps({"toolUseId": uid}), encoding="utf-8")
                (subs / f"agent-{i}.jsonl").write_text("\n".join(json.dumps(r) for r in [
                    row("user", "brief", 2 + 2 * i), row("assistant", [{"type": "text", "text": text}], 3 + 2 * i)]),
                    encoding="utf-8")
            r = extract.extract(main)
        self.assertEqual((r["kind"], r["task"]), ("arena", "Write is_leap(year)."))
        self.assertEqual([a["role"] for a in r["agents"]], ["contestant", "contestant", "judge", "validator"])
        self.assertEqual(r["agents"][0]["result"], "return year % 4 == 0")
        self.assertEqual(r["agents"][2]["result"], "Scored 2 candidates blind")
        self.assertEqual(r["answer"], "Candidate a0002 wins, validated")
        self.assertTrue(r["mode"].startswith("judge · 2 contestants"))


if __name__ == "__main__":
    unittest.main()
