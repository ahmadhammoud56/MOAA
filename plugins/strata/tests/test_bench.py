"""Recall benchmark harness test on a two-question fixture: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
import recall_bench  # noqa: E402

ITEMS = [
    {"question_id": "q1", "question_type": "single-session-user", "question": "Which espresso grinder did I buy?",
     "haystack_session_ids": ["a", "b"], "answer_session_ids": ["b"],
     "haystack_sessions": [[{"role": "user", "content": "Plan a hiking trip to Zion for May."}],
                           [{"role": "user", "content": "I bought a Niche Zero espresso grinder yesterday."},
                            {"role": "assistant", "content": "Nice, the Niche Zero grinder suits espresso."}]]},
    {"question_id": "q2", "question_type": "temporal", "question": "What was the name of my cat?",
     "haystack_session_ids": ["c"], "answer_session_ids": ["d"],
     "haystack_sessions": [[{"role": "user", "content": "Help me with a resume."}]]},
]


class Bench(unittest.TestCase):
    def test_recall_at_k_per_type_and_overall(self):
        with mock.patch.dict(os.environ, {"MOAA_STRATA_DIR": tempfile.mkdtemp(), "STRATA_VAULT": "off"}):
            summary, rows = recall_bench.run(ITEMS, ks=(1, 5))
        self.assertEqual([r["r@5"] for r in rows], [1, 0])
        self.assertEqual(summary["overall"], {"r@1": 0.5, "r@5": 0.5, "n": 2})
        self.assertEqual(summary["single-session-user"]["r@1"], 1.0)

    def test_cli_skips_items_without_evidence(self):
        data = Path(tempfile.mkdtemp()) / "d.json"
        data.write_text(json.dumps(ITEMS + [{**ITEMS[0], "question_id": "abs", "answer_session_ids": []}]))
        out = data.with_name("r.json")
        with mock.patch.dict(os.environ, {"MOAA_STRATA_DIR": tempfile.mkdtemp(), "STRATA_VAULT": "off"}):
            self.assertEqual(recall_bench.main(["--data", str(data), "--out", str(out)]), 0)
        self.assertEqual(json.loads(out.read_text())["summary"]["overall"]["n"], 2)


if __name__ == "__main__":
    unittest.main()
