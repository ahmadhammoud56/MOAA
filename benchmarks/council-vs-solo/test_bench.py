"""Scoring checks for bench.py: python -m unittest test_bench (from this folder)."""
import unittest

import bench


def rec(text, error=False):
    return {"result": text, "is_error": error}


class Scoring(unittest.TestCase):
    def setUp(self):
        self.cases = {c["id"]: c for c in bench.load_cases()}

    def test_review_counts_bug_ids_any_marked_line_and_false_positives(self):
        case = self.cases["review-utils"]
        _, bugs, neutral = bench.review_key(case)
        self.assertEqual(len(bugs), 5)
        self.assertEqual(bugs["default"], {5, 7})  # either line of a multi-line bug counts
        text = 'x ```json\n{"bugs": [{"line": 3}, {"line": 7}, {"line": 31}, {"line": 2}]}\n```'
        s = bench.score(case, rec(text))
        self.assertEqual(s["found"], ["chunk", "default"])
        self.assertEqual(s["false_positive_lines"], [2])  # 31 is the neutral percent() line
        self.assertAlmostEqual(s["score"], 0.4)

    def test_claims_and_answers_and_failures(self):
        s = bench.score(self.cases["claims"], rec('```json\n{"wrong": [2, "3", "7"]}\n```'))
        self.assertAlmostEqual(s["score"], 6 / 10)  # 2 wrongly flagged; 4, 6 and 9 missed
        s = bench.score(self.cases["math-traps"], rec('```json\n{"answers": {"1": "49", "2": "$505", '
                                                      '"3": 31, "4": "8,9", "6": "14.7"}}\n```'))
        self.assertEqual(s["wrong_questions"], ["10", "5", "7", "8", "9"])  # 14.7 == 147/10; 5 and 7+ unanswered
        self.assertEqual(bench.score(self.cases["claims"], rec("no json")), {"score": 0.0, "parsed": False})
        self.assertEqual(bench.score(self.cases["claims"], rec('```json\n{"wrong": []}\n```', error=True))["score"], 0)


if __name__ == "__main__":
    unittest.main()
