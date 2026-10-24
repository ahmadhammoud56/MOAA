from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import loop  # noqa: E402


class KarpathyLoop(unittest.TestCase):
    def test_keeps_improvements_discards_the_rest_and_stops_on_budget(self):
        d = Path(tempfile.mkdtemp())
        score = d / "score.txt"
        score.write_text("10")
        metric = f'"{sys.executable}" -c "print(open(r\'{score}\').read())"'
        self.assertEqual(loop.main(["init", str(d), "--metric", metric, "--max-iters", "3"]), 0)
        self.assertTrue((d / "program.md").exists())
        score.write_text("loss 8.5")
        self.assertEqual(loop.main(["record", str(d), "smaller lr"]), loop.KEEP)
        score.write_text("9")
        self.assertEqual(loop.main(["record", str(d), "bigger batch"]), loop.DISCARD)
        score.write_text("crash")
        self.assertEqual(loop.main(["record", str(d), "broken"]), loop.DISCARD)  # no number: never kept
        self.assertEqual(loop.main(["record", str(d), "one more"]), loop.STOP)
        rows = (d / "results.tsv").read_text().splitlines()
        self.assertEqual([r.split("\t")[3] for r in rows[1:]], ["KEEP", "DISCARD", "DISCARD"])
        self.assertIn('"best": 8.5', (d / "loop.json").read_text())

    def test_max_direction(self):
        self.assertTrue(loop.better(0.9, 0.8, "max"))
        self.assertFalse(loop.better(0.9, 0.8, "min"))


if __name__ == "__main__":
    unittest.main()
