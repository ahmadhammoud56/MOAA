"""Grounded answers (quote-verified citations), the ask evaluation, the raw/ hard lock: python -m unittest"""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import graph  # noqa: E402
import rag  # noqa: E402
import strata  # noqa: E402

PAGE = """# Concrete printing

The **buildability** of a layer depends on the [[Yield stress|yield stress]] at the time of deposition.
Interlayer bond strength drops when the open time exceeds 20 minutes.
"""


class Verify(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "wiki").mkdir()
        (self.root / "wiki" / "Concrete printing.md").write_text(PAGE, encoding="utf-8")

    def test_quotes_must_exist_verbatim_in_a_real_page(self):
        answer = "\n".join([
            "Intro line without a citation.",
            '- Buildability "depends on the yield stress at the time" ([[Concrete printing]])',  # link label normalized
            '- Bond "drops when the open time exceeds 20 minutes" ([[concrete printing]])',  # case-insensitive page
            '- Invented "bond doubles with a retarder added" ([[Concrete printing]])',  # quote not in the page
            '- Made-up page "depends on the yield stress at the time" ([[Rheology handbook]])',
            '- Unquoted claim ([[Concrete printing]])',
        ])
        res = graph.verify(self.root, answer)
        self.assertEqual([r["ok"] for r in res], [True, True, False, False, False])
        self.assertIn("quote not found", res[2]["why"])
        self.assertIn("no page", res[3]["why"])
        self.assertIn("4+ words", res[4]["why"])
        kept = graph.strip(answer, res)
        self.assertIn("Buildability", kept)
        self.assertNotIn("Invented", kept)
        self.assertEqual(graph.strip("- x \"one two three four\" ([[Nope]])",
                                     graph.verify(self.root, '- x "one two three four" ([[Nope]])')), graph.ABSTAIN)

    def test_cli_exit_code(self):
        good = self.root / "a.md"
        good.write_text('- "depends on the yield stress at the time" ([[Concrete printing]])', encoding="utf-8")
        bad = self.root / "b.md"
        bad.write_text('- "the moon is made of cheese" ([[Concrete printing]])', encoding="utf-8")
        self.assertEqual(graph.main(["verify", str(self.root), str(good)]), 0)
        self.assertEqual(graph.main(["verify", str(self.root), str(bad)]), 1)

    def test_eval_counts_refusals_and_fabrications(self):
        cases = [
            {"question": "What controls buildability?", "expected": ["Concrete printing"],
             "answer": '- "depends on the yield stress at the time" ([[Concrete printing]])'},
            {"question": "When does bond drop?", "expected": ["Concrete printing"],
             "answer": '- "bond triples after an hour" ([[Concrete printing]])'},  # fabricated quote
            {"question": "What is the CO2 of geopolymer?", "expected": [], "answer": "Not in the wiki."},
            {"question": "Who invented 3DCP?", "expected": [],
             "answer": '- "invented in 1995 by" ([[History]])'},  # should have refused
        ]
        out = graph.score(self.root, cases)
        self.assertEqual((out["answer_rate"], out["refusal_rate"], out["fabricated"]), (0.5, 0.5, 2))

    def test_shipped_eval_cases_are_well_formed(self):
        d = Path(__file__).resolve().parent / "e2e" / "wiki-ask-eval"
        cases = json.loads((d / "cases.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(1 for c in cases if c["expected"]), 6)
        self.assertEqual(sum(1 for c in cases if not c["expected"]), 4)
        pages = {p.stem.lower() for p in (d / "wiki").rglob("*.md")}
        for c in cases:
            self.assertTrue(all(e.lower() in pages for e in c["expected"]), c["question"])


class RagVerify(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.mkdtemp()
        self.proj = Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {"MOAA_STRATA_DIR": self.data, "STRATA_VAULT": "off"})
        env.start()
        self.addCleanup(env.stop)
        (self.proj / "docs").mkdir()
        (self.proj / "docs" / "guide.md").write_text("line one\nThe mixer runs at 40 rpm for two minutes.\nend\n",
                                                     encoding="utf-8")
        self.db = rag.connect()
        self.addCleanup(self.db.close)
        rag.index(self.db, self.proj)
        self.key = os.path.normcase(os.path.normpath(str(self.proj)))

    def test_path_lines_and_quote_are_checked(self):
        answer = "\n".join([
            '- Speed "runs at 40 rpm for two" (docs/guide.md:2)',
            '- Wrong lines "runs at 40 rpm for two" (docs/guide.md:3-3)',
            '- Invented file "runs at 40 rpm for two" (docs/other.md:2)',
        ])
        res = rag.verify(self.db, self.key, str(self.proj), answer)
        self.assertEqual([r["ok"] for r in res], [True, False, False])
        self.assertIn("not an indexed file", res[2]["why"])


class RawLock(unittest.TestCase):
    def setUp(self):
        self.vault = Path(tempfile.mkdtemp()) / "brain"
        env = mock.patch.dict(os.environ, {"MOAA_STRATA_DIR": tempfile.mkdtemp(), "STRATA_VAULT": str(self.vault)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("STRATA_VAULT_GUARD", None)

    def tearDown(self):
        for p in (self.vault / "raw").rglob("*"):  # let the temp folder be removed
            p.chmod(stat.S_IWRITE | stat.S_IREAD)

    def test_raw_files_become_read_only_and_template_exists(self):
        strata.vault_init(self.vault)
        src = self.vault / "raw" / "paper.md"
        src.write_text("source", encoding="utf-8")
        self.assertEqual(strata.lock_raw(self.vault), 1)
        self.assertFalse(os.access(src, os.W_OK))
        self.assertEqual(strata.lock_raw(self.vault), 0)  # already locked
        self.assertIn("status: unverified", (self.vault / "templates" / "literature-note.md").read_text(encoding="utf-8"))
        self.assertTrue((self.vault / "inbox" / "literature").is_dir())

    def test_off_with_the_guard(self):
        strata.vault_init(self.vault)
        src = self.vault / "raw" / "paper.md"
        src.write_text("source", encoding="utf-8")
        with mock.patch.dict(os.environ, {"STRATA_VAULT_GUARD": "off"}):
            self.assertEqual(strata.lock_raw(self.vault), 0)
        self.assertTrue(os.access(src, os.W_OK))


if __name__ == "__main__":
    unittest.main()
