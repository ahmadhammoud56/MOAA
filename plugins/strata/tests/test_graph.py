"""Strata graph tests: python -m unittest discover -s tests"""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import graph  # noqa: E402


class Wiki(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        graph.init(self.root, "Test KB")
        w = self.root / "wiki"
        (self.root / "raw" / "paper.pdf").write_text("x")
        (self.root / "raw" / "unused.txt").write_text("y")
        (w / "Buildability.md").write_text("Summary. See [[Yield Stress]] and [[Missing Page]]. Source: raw/paper.pdf\n")
        (w / "Yield Stress.md").write_text("Summary. Back to [[buildability|the hub]].\n")
        (w / "Lonely.md").write_text("Nobody links here.\n")
        (self.root / "index.md").write_text("# index\n- [[Buildability]]\n- [[Yield Stress]]\n")

    def test_init_creates_the_layout_and_logs(self):
        for name in ("raw", "wiki", "graph", "index.md", "log.md", "CLAUDE.md"):
            self.assertTrue((self.root / name).exists(), name)
        self.assertIn("init: Test KB", (self.root / "log.md").read_text())

    def test_lint_reports_the_link_graph(self):
        r = graph.lint(self.root)
        self.assertEqual(r["pages"], 3)
        self.assertEqual(r["broken"], [{"from": "Buildability", "to": "Missing Page"}])
        self.assertEqual(r["orphans"], ["Lonely"])  # links are case-insensitive, aliases resolve
        self.assertEqual(r["not_in_index"], ["Lonely"])
        self.assertEqual(r["uncited_raw"], ["raw/unused.txt"])
        self.assertEqual(graph.main(["lint", str(self.root)]), 1)  # broken link fails the lint


class Findings(unittest.TestCase):
    def test_check_grounds_claims_in_sources(self):
        root = Path(tempfile.mkdtemp())
        graph.main(["node", str(root), "s1", "source", "Suiker 2018", "--ref", "doi:10.1016/x"])
        graph.main(["node", str(root), "s2", "source", "a remark", ])
        graph.main(["node", str(root), "c1", "claim", "E grows linearly early"])
        graph.main(["node", str(root), "c2", "claim", "R_E is identifiable"])
        graph.main(["node", str(root), "c3", "claim", "tau0 is a lower bound"])
        graph.main(["edge", str(root), "c1", "supports", "s1"])
        graph.main(["edge", str(root), "c3", "cites", "s2"])
        graph.main(["edge", str(root), "c2", "contradicts", "c3"])
        graph.main(["edge", str(root), "c1", "about", "ghost"])
        r = graph.check(root)
        self.assertEqual((r["claims"], r["grounded"]), (3, 1))
        self.assertIn("claim c2: no supports/cites edge to a source", r["failures"])
        self.assertIn("claim c3: its sources have no ref (URL or path)", r["failures"])
        self.assertIn("edge c1 -about-> ghost: no node ghost", r["failures"])
        self.assertEqual(r["contradictions"], ["c2 contradicts c3"])
        self.assertEqual(graph.main(["check", str(root)]), 1)
        self.assertIn("graph LR", graph.export(root).read_text())

    def test_latest_node_line_wins(self):
        root = Path(tempfile.mkdtemp())
        graph.main(["node", str(root), "c1", "claim", "old"])
        graph.main(["node", str(root), "c1", "claim", "new"])
        self.assertEqual(graph.load(root)[0]["c1"]["text"], "new")


if __name__ == "__main__":
    unittest.main()
