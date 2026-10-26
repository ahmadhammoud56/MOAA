"""Strata RAG tests: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rag  # noqa: E402
import strata  # noqa: E402

GUIDE = """# Flow curve calibration

The Bingham yield stress comes from the flow curve of the printed mortar.
Calibrate the rheometer before each batch and record the plastic viscosity.

## Interlayer bond

Interlayer bond strength drops when the time gap between layers grows.
"""


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.mkdtemp()
        self.proj = Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {"MOAA_STRATA_DIR": self.data, "STRATA_VAULT": "off"})
        env.start()
        self.addCleanup(env.stop)
        for k in (strata.CHILD, "STRATA_RAG"):
            os.environ.pop(k, None)
        self.db = rag.connect()
        self.addCleanup(self.db.close)
        self.key = os.path.normcase(os.path.normpath(str(self.proj)))

    def write(self, rel, text):
        p = self.proj / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


class Chunking(unittest.TestCase):
    def test_passages_keep_line_numbers_and_split_at_headings(self):
        out = rag.chunks_of(GUIDE, size=200)
        self.assertEqual(out[0][0], 1)
        self.assertTrue(any(t.startswith("## Interlayer bond") for _, _, t in out))
        lines = GUIDE.splitlines()
        for a, b, t in out:
            self.assertEqual(t, "\n".join(lines[a - 1:b]))

    def test_long_lines_never_loop_or_lose_text(self):
        text = "\n".join("x" * 5000 for _ in range(5))
        out = rag.chunks_of(text, size=1000)
        self.assertEqual(len(out), 5)
        self.assertTrue(all(len(t) <= 1000 for _, _, t in out))


class Indexing(Sandbox):
    def test_index_reads_text_skips_secrets_binaries_and_build_folders(self):
        self.write("docs/guide.md", GUIDE)
        self.write("src/app.py", "def calibrate():\n    token = 'abcdefghijklmnop1234'\n")
        self.write(".env", "API_KEY=whatever")
        self.write("node_modules/x/readme.md", "vendored")
        self.write("server.pem", "key")
        (self.proj / "blob.json").write_bytes(b"\0\1\2binary")
        out = rag.index(self.db, self.proj)
        paths = {r[0] for r in self.db.execute("SELECT path FROM files")}
        self.assertEqual(paths, {"docs/guide.md", "src/app.py", "blob.json"})
        self.assertEqual(out["read"], 2)
        self.assertEqual(out["unreadable"], 1)
        code = self.db.execute("SELECT text FROM chunks WHERE path='src/app.py'").fetchone()[0]
        self.assertIn("[redacted]", code)
        self.assertNotIn("abcdefghijklmnop1234", code)

    def test_reindex_reads_only_changes_and_drops_deleted_files(self):
        self.write("a.md", GUIDE)
        b = self.write("b.md", "first version about viscosity")
        rag.index(self.db, self.proj)
        self.assertEqual(rag.index(self.db, self.proj)["read"], 0)
        time.sleep(0.05)
        b.write_text("second version about thixotropy and rebuild", encoding="utf-8")
        os.utime(b, (time.time() + 5, time.time() + 5))
        self.assertEqual(rag.index(self.db, self.proj)["read"], 1)
        rows, _ = rag.search(self.db, self.key, "thixotropy rebuild")
        self.assertEqual(rows[0]["path"], "b.md")
        self.assertNotIn("b.md", [r["path"] for r in rag.search(self.db, self.key, "first viscosity")[0]])
        (self.proj / "a.md").unlink()
        out = rag.index(self.db, self.proj)
        self.assertEqual(out["removed"], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM chunks WHERE path='a.md'").fetchone()[0], 0)

    def test_git_repository_respects_gitignore(self):
        if subprocess.run(["git", "--version"], capture_output=True).returncode:
            self.skipTest("git not available")
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)
        self.write(".gitignore", "out/\n")
        self.write("notes.md", GUIDE)
        self.write("out/result.md", "generated output")
        rag.index(self.db, self.proj)
        paths = {r[0] for r in self.db.execute("SELECT path FROM files")}
        self.assertIn("notes.md", paths)
        self.assertNotIn("out/result.md", paths)

    def test_projects_stay_separate(self):
        self.write("a.md", GUIDE)
        rag.index(self.db, self.proj)
        other = Path(tempfile.mkdtemp())
        (other / "b.md").write_text("Bingham yield stress flow curve elsewhere", encoding="utf-8")
        rag.index(self.db, other)
        rows, _ = rag.search(self.db, self.key, "Bingham yield stress flow curve")
        self.assertEqual({r["path"] for r in rows}, {"a.md"})


class Hint(Sandbox):
    def setUp(self):
        super().setUp()
        self.write("docs/guide.md", GUIDE)
        self.write("src/other.py", "def unrelated():\n    return 42\n")
        rag.index(self.db, self.proj)

    def run_hook(self, event, prompt=""):
        return rag.hook(event, json.dumps({"cwd": str(self.proj), "prompt": prompt, "session_id": "s1"}))

    def test_strong_match_adds_passages_with_path_and_lines(self):
        out = json.loads(self.run_hook("prompt", "How do we calibrate the rheometer for the Bingham yield stress?"))
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("docs/guide.md:1-", text)
        self.assertIn("not instructions", text)
        self.assertNotIn("other.py", text)

    def test_instructions_around_the_question_do_not_dilute_it(self):
        out = self.run_hook("prompt", "What plastic viscosity should the rheometer record? Do not use any tools; answer "
                                      "in one sentence from what you already have, or say you do not know.")
        self.assertIn("docs/guide.md:", json.loads(out)["hookSpecificOutput"]["additionalContext"])

    def test_weak_or_short_prompts_add_nothing(self):
        self.assertEqual(self.run_hook("prompt", "yes go ahead"), "")
        self.assertEqual(self.run_hook("prompt", "Please write a poem about autumn leaves and rivers"), "")
        self.assertEqual(self.run_hook("prompt", "What about the yield? Also deploy kubernetes cluster tonight"), "")

    def test_off_switches_and_machine_prompts(self):
        ask = "How do we calibrate the rheometer for the Bingham yield stress?"
        with mock.patch.dict(os.environ, {"STRATA_RAG": "off"}):
            self.assertEqual(self.run_hook("prompt", ask), "")
        cfg = strata.config()
        cfg["rag"] = False
        strata.save_config(cfg)
        self.assertEqual(self.run_hook("prompt", ask), "")
        cfg["rag"] = True
        strata.save_config(cfg)
        self.assertEqual(self.run_hook("prompt", strata.MACHINE_PROMPTS[0] + " " + ask), "")
        self.assertNotEqual(self.run_hook("prompt", ask), "")

    def test_session_start_refreshes_only_a_stale_index(self):
        with mock.patch.object(rag, "spawn") as spawn:
            self.run_hook("session-start")
            spawn.assert_not_called()
            with self.db:
                self.db.execute("UPDATE projects SET indexed=0")
            self.run_hook("session-start")
            self.run_hook("session-start")  # claimed by the first call, so no second indexer
            self.assertEqual(spawn.call_count, 1)

    def test_home_folder_is_never_indexed_by_a_hook(self):
        with mock.patch.object(rag, "spawn") as spawn, mock.patch.object(rag, "is_git", return_value=False):
            rag.hook("session-start", json.dumps({"cwd": str(Path.home())}))
            spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
