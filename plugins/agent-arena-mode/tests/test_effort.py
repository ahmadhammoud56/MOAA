from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import effort  # noqa: E402


def trial_with(results):
    t = effort.plan(["a", "b"], ["medium", "high"], [{"id": "t1"}], repeats=1, seed=1)
    by = {(c["role"], c["effort"]): c["id"] for c in t["cells"]}
    for (role, eff), (score, found, tokens) in results.items():
        t["results"][by[(role, eff)]] = {"score": score, "findings": found, "tokens": tokens}
    return t


class EffortTrial(unittest.TestCase):
    def test_plan_covers_every_cell_with_blind_labels(self):
        t = effort.plan(["a", "b"], ["medium", "high"], [{"id": "t1"}, {"id": "t2"}], repeats=2, seed=3)
        self.assertEqual(len(t["cells"]), 16)
        self.assertEqual(len({c["label"] for c in t["cells"]}), 16)
        self.assertTrue(all("medium" not in c["label"] and "high" not in c["label"] for c in t["cells"]))

    def test_dearer_effort_must_earn_its_cost(self):
        s = effort.summarize(trial_with({("a", "medium"): (80, 2, 1000), ("a", "high"): (82, 2, 1800),
                                         ("b", "medium"): (70, 2, 1000), ("b", "high"): (72, 3, 1700)}))
        self.assertEqual(s["a"]["pick"], "medium")  # +2 score, same findings: not worth 1.8x tokens
        self.assertEqual(s["b"]["pick"], "high")    # +50% findings
        self.assertIn("findings", s["b"]["why"])

    def test_roles_without_results_say_so(self):
        self.assertIsNone(effort.summarize(trial_with({}))["a"]["pick"])


if __name__ == "__main__":
    unittest.main()
