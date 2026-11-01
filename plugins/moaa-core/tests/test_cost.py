"""Cost calculator: python -m unittest discover -s tests"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cost  # noqa: E402


class Cost(unittest.TestCase):
    def test_selftest_matches_the_review(self):
        self.assertEqual(cost.selftest(), "cost.py selftest: ok")
        self.assertEqual(cost.main(["selftest"]), 0)

    def test_rejects_impossible_inputs(self):
        with self.assertRaises(ValueError):
            cost.blended(1, 1, hit=0.7, write_frac=0.5)
        with self.assertRaises(ValueError):
            cost.per_success(1, 0)
        self.assertEqual(cost.main(["success", "--cost", "1", "--rate", "0"]), 2)

    def test_more_credit_does_not_lower_cash_for_the_same_work(self):
        for spend in (20, 100, 150, 200, 300):
            self.assertLessEqual(cost.bundle(100, 100, spend), cost.bundle(200, 200, spend))


if __name__ == "__main__":
    unittest.main()
