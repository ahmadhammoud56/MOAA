import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import package  # noqa: E402


class PackageTests(unittest.TestCase):
    def test_zip_has_required_files_and_no_user_data(self):
        with tempfile.TemporaryDirectory() as temp:
            junk = package.ROOT / ".agent-arena" / "library.sqlite3"
            junk.parent.mkdir(exist_ok=True)
            created = not junk.exists()
            junk.write_bytes(b"user data")
            try:
                out, _ = package.build(Path(temp) / "p.zip")
                names = zipfile.ZipFile(out).namelist()
            finally:
                if created:
                    junk.unlink()
                    junk.parent.rmdir()
        prefix = package.NAME + "/"
        for required in package.REQUIRED:
            self.assertIn(prefix + required, names)
        bad = [n for n in names if any(s in n for s in (".sqlite", "__pycache__", ".pyc", ".agent-arena", ".lock", ".claude-flow"))]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
