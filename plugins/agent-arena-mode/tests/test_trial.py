from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import trial  # noqa: E402


class ArmTrial(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.tasks = self.dir / "tasks.json"
        self.tasks.write_text(json.dumps([{"id": "t1", "brief": "b", "rubric": "r", "pass": "p"},
                                          {"id": "t2", "brief": "b", "rubric": "r", "pass": "p"}]))

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = trial.main(list(args))
        return code, out.getvalue()

    def test_plan_prints_cost_and_refuses_over_cap(self):
        code, out = self.run_cli("plan", "--arms", "solo,council", "--tasks", str(self.tasks), "--out", str(self.dir),
                                 "--repeats", "2", "--seed", "1")
        self.assertEqual(code, 0)
        self.assertIn("8 runs", out)
        self.assertIn("240,000 tokens", out)
        labels = [c["label"] for c in json.loads((self.dir / "trials.json").read_text())["cells"]]
        self.assertEqual(len(set(labels)), 8)
        with self.assertRaises(SystemExit):
            self.run_cli("plan", "--arms", "solo,council", "--tasks", str(self.tasks), "--out", str(self.dir),
                         "--repeats", "3", "--max-runs", "10")
        with self.assertRaises(SystemExit):
            self.run_cli("plan", "--arms", "solo", "--tasks", str(self.tasks), "--out", str(self.dir))

    def test_summary_scores_arms_and_finds_flips(self):
        self.run_cli("plan", "--arms", "claude,codex", "--tasks", str(self.tasks), "--out", str(self.dir), "--seed", "2")
        cells = json.loads((self.dir / "trials.json").read_text())["cells"]
        for c in cells:
            passed = c["arm"] == "claude" or c["task"] == "t1"  # codex fails t2 only
            self.run_cli("record", "--dir", str(self.dir), "--cell", c["id"], "--score", "90" if passed else "30",
                         "--tokens", "1000", *(["--passed"] if passed else []))
        arms, flips = trial.summarize(json.loads((self.dir / "trials.json").read_text()))
        self.assertEqual(arms["claude"]["pass_rate"], 1.0)
        self.assertEqual(arms["codex"]["pass_rate"], 0.5)
        self.assertEqual([f[0] for f in flips], ["t2"])

    def test_cost_per_success_and_percentiles(self):
        self.run_cli("plan", "--arms", "cheap,dear", "--tasks", str(self.tasks), "--out", str(self.dir), "--seed", "3")
        for c in json.loads((self.dir / "trials.json").read_text())["cells"]:
            cheap = c["arm"] == "cheap"
            passed = not cheap or c["task"] == "t1"  # cheap passes half
            self.run_cli("record", "--dir", str(self.dir), "--cell", c["id"], "--score", "80",
                         "--cost", "0.10" if cheap else "0.25", "--seconds", "10" if cheap else "30",
                         "--retries", "1" if cheap else "0", *(["--passed"] if passed else []))
        arms, _ = trial.summarize(json.loads((self.dir / "trials.json").read_text()))
        self.assertAlmostEqual(arms["cheap"]["cost_per_success"], 0.20)  # 0.20 spent / 1 success
        self.assertAlmostEqual(arms["dear"]["cost_per_success"], 0.25)
        self.assertEqual((arms["dear"]["p50_s"], arms["cheap"]["retries"]), (30, 2))


if __name__ == "__main__":
    unittest.main()
