"""install.py to_release: a clone moves only to the newest release tag, never over local work."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import install  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class ToRelease(unittest.TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp())
        self.origin = root / "origin"
        self.origin.mkdir()
        git(self.origin, "init", "-q", "-b", "main")
        for v in ("0.1.0", "0.2.0"):
            (self.origin / "f.txt").write_text(v)
            git(self.origin, "add", "f.txt")
            git(self.origin, "commit", "-q", "-m", v)
            git(self.origin, "tag", f"v{v}")
        (self.origin / "f.txt").write_text("unreleased")
        git(self.origin, "commit", "-q", "-am", "unreleased")
        subprocess.run(["git", "clone", "-q", str(self.origin), str(root / "clone")], check=True)
        self.clone = root / "clone"
        git(self.clone, "reset", "-q", "--hard", "v0.1.0")

    def test_moves_to_the_newest_tag_not_unreleased_main(self):
        self.assertEqual(install.to_release(self.clone), "v0.2.0")
        self.assertEqual((self.clone / "f.txt").read_text(), "0.2.0")
        self.assertEqual(install.to_release(self.clone), "")  # already there

    def test_refuses_local_changes_and_local_commits(self):
        (self.clone / "f.txt").write_text("mine")
        with self.assertRaises(SystemExit):
            install.to_release(self.clone)
        git(self.clone, "commit", "-q", "-am", "local work")
        with self.assertRaises(SystemExit):
            install.to_release(self.clone)
        self.assertEqual((self.clone / "f.txt").read_text(), "mine")


if __name__ == "__main__":
    unittest.main()
