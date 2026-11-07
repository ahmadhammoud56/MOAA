"""scripts/sync_vendored.py without the network: python -m unittest discover -s tests"""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_vendored as sv  # noqa: E402


class SyncVendored(unittest.TestCase):
    def test_newer_by_release_or_by_commit(self):
        self.assertTrue(sv.newer({"version": "0.6.0"}, "0.10.0", "x"))
        self.assertFalse(sv.newer({"version": "0.6.0"}, "0.6.0", "x"))
        self.assertTrue(sv.newer({"version": "", "commit": "a"}, "", "b"))
        self.assertFalse(sv.newer({"version": "", "commit": "a"}, "", "a"))

    def test_copy_skips_excludes_keeps_moaa_files_and_lists_dropped(self):
        src, dst = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        for rel, text in {"hooks/a.ts": "new", "codex/x": "skip", "docs/shot.png": "skip", "docs/guide.md": "doc"}.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(text)
        for rel in ("hooks/a.ts", "hooks/old.ts", "MODIFICATIONS.md", "fix.patch"):
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            (dst / rel).write_text("old")
        copied, gone = sv.copy_over(src, dst, {"exclude": ["codex", "docs/*.png"], "patch": "fix.patch"})
        self.assertEqual(copied, ["docs/guide.md", "hooks/a.ts"])
        self.assertEqual((dst / "hooks/a.ts").read_text(), "new")
        self.assertEqual(gone, ["hooks/old.ts"])  # listed, never deleted
        self.assertTrue((dst / "hooks/old.ts").exists() and (dst / "MODIFICATIONS.md").exists())
        self.assertFalse((dst / "codex").exists())


if __name__ == "__main__":
    unittest.main()
