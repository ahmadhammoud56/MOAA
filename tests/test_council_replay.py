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


if __name__ == "__main__":
    unittest.main()
