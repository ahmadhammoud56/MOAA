from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import install  # noqa: E402

KIT_SETTINGS = {"env": {"ECC_GATEGUARD": "off"}, "permissions_deny": ["Skill(x)"],
                "defaults": {"model": "sonnet", "theme": "dark"}}


class MergeTests(unittest.TestCase):
    def test_merge_never_overwrites_and_unmerge_restores(self):
        current = {"model": "opus", "env": {"ECC_GATEGUARD": "on", "MINE": "1"},
                   "permissions": {"allow": ["Bash(ls)", "Bash(a)"]}, "enabledPlugins": {"p@m": False}}
        merged, added = install.merge_settings(current, KIT_SETTINGS, ["Bash(a)", "Bash(b)"], {"p@m": True, "q@m": True})
        self.assertEqual(merged["model"], "opus")  # user value kept
        self.assertEqual(merged["theme"], "dark")
        self.assertEqual(merged["env"], {"ECC_GATEGUARD": "on", "MINE": "1"})
        self.assertEqual(merged["permissions"]["allow"], ["Bash(ls)", "Bash(a)", "Bash(b)"])
        self.assertEqual(merged["enabledPlugins"], {"p@m": False, "q@m": True})  # user's disable respected
        self.assertEqual(current["permissions"]["allow"], ["Bash(ls)", "Bash(a)"])  # input untouched
        again, added2 = install.merge_settings(merged, KIT_SETTINGS, ["Bash(a)", "Bash(b)"], {"q@m": True})
        self.assertEqual(again, merged)  # idempotent
        self.assertFalse(any(added2.values()))
        restored = install.unmerge_settings(merged, added)
        restored["permissions"].pop("deny")
        self.assertEqual(restored, current)

    def test_council_permissions_cover_home_spelling(self):
        rules = install.council_permissions(Path("/home/u/.claude"))
        self.assertIn("Bash(python *specialist-council*council.py *)", rules)
        self.assertIn("PowerShell(python *specialist-council*council.py *)", rules)

    def test_kit_config_is_consistent(self):
        kit = install.read_json(install.KIT / "config" / "kit.json", None)
        markets = set(kit["marketplaces"]) | {kit["name"]}
        for p in kit["plugins"]:
            self.assertIn(p["id"].split("@")[1], markets, p["id"])
        for name in kit["skills"]:
            self.assertTrue((install.KIT / "skills" / name / "SKILL.md").is_file(), name)
        listed = {e["source"].split("/")[-1] for e in install.read_json(
            install.KIT / ".claude-plugin" / "marketplace.json", None)["plugins"]}
        vendored = {p["id"].split("@")[0] for p in kit["plugins"] if p["id"].endswith("@" + kit["name"])}
        self.assertEqual(listed, vendored)
        self.assertFalse(list(install.KIT.rglob("forged/registry.json")))  # no forged members shipped
        self.assertFalse((install.KIT / "specialist-council").exists())  # council lives only in plugins/


if __name__ == "__main__":
    unittest.main()
