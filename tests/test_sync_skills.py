import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_skills  # noqa: E402


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True)


class SyncSkillsTests(unittest.TestCase):
    def test_kit_and_third_party_agree(self):
        kit = json.loads(sync_skills.KIT_JSON.read_text(encoding="utf-8"))
        third = sync_skills.THIRD_PARTY.read_text(encoding="utf-8")
        for name, spec in kit["vendored_skills"].items():
            with self.subTest(skill=name):
                self.assertIn(name, kit["skills"])
                self.assertRegex(spec["commit"], r"^[0-9a-f]{40}$")
                self.assertIn(f"`{spec['commit'][:7]}`", third)
                self.assertNotIn(f"skills/{name}", kit["own_work"])

    def test_update_and_check_against_a_local_upstream(self):
        root = Path(tempfile.mkdtemp())
        up = root / "up"
        (up / "skills" / "demo" / "references").mkdir(parents=True)
        (up / "skills" / "demo" / "SKILL.md").write_text("v1\n")
        (up / "skills" / "demo" / "references" / "a.md").write_text("a\n")
        (up / "skills" / "demo" / "LICENSE").write_text("upstream licence\n")  # MOAA keeps its own copy
        git(up, "init", "-q")
        git(up, "add", "-A")
        git(up, "commit", "-qm", "v1")
        v1 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=up, capture_output=True, text=True).stdout.strip()
        kit_dir = root / "kit"
        (kit_dir / "config").mkdir(parents=True)
        skill = kit_dir / "skills" / "demo"
        (skill / "old").mkdir(parents=True)
        (skill / "SKILL.md").write_text("v0\n")
        (skill / "old" / "gone.md").write_text("x\n")
        (skill / "LICENSE").write_text("MOAA licence\n")
        kit = {"skills": ["demo"], "own_work": [],
               "vendored_skills": {"demo": {"repo": up.as_uri(), "path": "skills/demo", "commit": "0" * 40}}}
        (kit_dir / "config" / "kit.json").write_text(json.dumps(kit))
        (kit_dir / "THIRD_PARTY.md").write_text("| demo | upstream @ `0000000` |\n")
        with mock.patch.multiple(sync_skills, KIT=kit_dir, KIT_JSON=kit_dir / "config" / "kit.json",
                                 THIRD_PARTY=kit_dir / "THIRD_PARTY.md"):
            self.assertEqual(sync_skills.main(["--check"]), 1)
            self.assertEqual(sync_skills.main([]), 0)
            self.assertEqual(sync_skills.main(["--check"]), 0)
            (up / "skills" / "elsewhere.md").write_text("unrelated\n")
            git(up, "add", "-A")
            git(up, "commit", "-qm", "unrelated")
            self.assertEqual(sync_skills.main([]), 0)  # content unchanged: the recorded commit stays
        self.assertEqual((skill / "SKILL.md").read_text(), "v1\n")
        self.assertEqual((skill / "LICENSE").read_text(), "MOAA licence\n")
        self.assertFalse((skill / "old").exists())
        self.assertTrue((skill / "references" / "a.md").is_file())
        self.assertEqual(json.loads((kit_dir / "config" / "kit.json").read_text())["vendored_skills"]["demo"]["commit"], v1)
        self.assertIn(f"`{v1[:7]}`", (kit_dir / "THIRD_PARTY.md").read_text())


class CatalogDriftTests(unittest.TestCase):
    def test_drift_groups_by_repo_and_skips_current_ones(self):
        import sync_catalog
        sha = lambda c: c * 40  # noqa: E731
        market = {"plugins": [
            {"name": "own", "source": "./plugins/own"},
            {"name": "a1", "source": {"source": "github", "repo": "o/a", "sha": sha("1")}},
            {"name": "b1", "source": {"source": "git-subdir", "url": "https://github.com/o/b.git", "path": "x", "sha": sha("2")}},
            {"name": "b2", "source": {"source": "git-subdir", "url": "https://github.com/o/b.git", "path": "y", "sha": sha("2")}}]}
        heads = {"https://github.com/o/a.git": sha("1"), "https://github.com/o/b.git": sha("3")}
        self.assertEqual(sync_catalog.upstream_drift(market, heads.get), [("o/b", sha("2"), sha("3"), 2)])


if __name__ == "__main__":
    unittest.main()
