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

    def test_war_room_permissions_keep_launch_behind_a_prompt(self):
        rules = install.council_permissions(Path("/home/u/.claude"))
        self.assertIn("Bash(python *war-room*warroom.py* status*)", rules)
        self.assertIn("PowerShell(python *war-room*warroom.py* stop*)", rules)
        for gated in ("toggle", "launch", "integrate", "finish", "shutdown", "approve"):
            self.assertFalse(any(f"warroom.py* {gated}" in r for r in rules), gated)

    def test_council_permissions_cover_home_spelling(self):
        rules = install.council_permissions(Path("/home/u/.claude"))
        self.assertIn("Bash(python *specialist-council*council.py*)", rules)
        self.assertIn("PowerShell(python *specialist-council*council.py*)", rules)

    def test_kit_config_is_consistent(self):
        kit = install.read_json(install.KIT / "config" / "kit.json", None)
        markets = set(kit["marketplaces"]) | {kit["name"]}
        for p in kit["plugins"]:
            self.assertIn(p["id"].split("@")[1], markets, p["id"])
        for name in kit["skills"]:
            self.assertTrue((install.KIT / "skills" / name / "SKILL.md").is_file(), name)
        market = install.read_json(install.KIT / ".claude-plugin" / "marketplace.json", None)["plugins"]
        listed = {e["source"].split("/")[-1] for e in market if isinstance(e["source"], str)}
        vendored = {p["id"].split("@")[0] for p in kit["plugins"] if p["id"].endswith("@" + kit["name"])}
        self.assertEqual(listed, vendored)
        sys.path.insert(0, str(install.KIT / "scripts"))
        import sync_catalog
        upstream = {sync_catalog.ALIASES.get(n, n) for n in
                    (p["id"].split("@")[0] for p in kit["plugins"] if not p["id"].endswith("@" + kit["name"]))}
        pinned = {e["name"]: e["source"] for e in market if isinstance(e["source"], dict)}
        self.assertEqual(set(pinned), upstream)  # every upstream plugin of the setup is in the catalog
        for name, source in pinned.items():
            with self.subTest(plugin=name):
                self.assertRegex(source["sha"], r"^[0-9a-f]{40}$")
                self.assertIn(source["source"], ("github", "git-subdir"))
        self.assertFalse(list(install.KIT.rglob("forged/registry.json")))  # no forged members shipped
        self.assertFalse((install.KIT / "specialist-council").exists())  # council lives only in plugins/


if __name__ == "__main__":
    unittest.main()


class ModelPresetTests(unittest.TestCase):
    """Each agent's model and effort live inside the plugins; the generated MODELS.md must match them."""

    def test_models_doc_is_current(self):
        sys.path.insert(0, str(install.KIT / "scripts"))
        import models_doc
        self.assertEqual((install.KIT / "MODELS.md").read_text(encoding="utf-8"), models_doc.build())

    def test_every_plugin_agent_carries_a_valid_model_and_effort(self):
        sys.path.insert(0, str(install.KIT / "scripts"))
        import models_doc
        council = models_doc.load(models_doc.COUNCIL / "council.py", "council_t")
        profile = council.load_profile(models_doc.COUNCIL / "profile.json")
        ids, levels = set(profile["models"].values()), set(profile["effort_levels"])
        agents = sorted((install.KIT / "plugins").glob("*/agents/*.md"))
        self.assertGreaterEqual(len(agents), 61)  # 60 council roles + arena judge
        for path in agents:
            fm = models_doc.frontmatter(path)
            with self.subTest(agent=path.name):
                self.assertIn(fm.get("model"), ids)
                self.assertIn(fm.get("effort"), levels)
        council.check(models_doc.COUNCIL / "agents", profile, user_agents=install.KIT / "missing", forged_dir=install.KIT / "missing")


class ReadmePluginListTests(unittest.TestCase):
    def test_readme_plugin_list_matches_marketplace(self):
        sys.path.insert(0, str(install.KIT / "scripts"))
        import sync_catalog
        market = install.read_json(install.KIT / ".claude-plugin" / "marketplace.json", None)
        readme = (install.KIT / "README.md").read_text(encoding="utf-8")
        self.assertIn(sync_catalog.plugin_table(market), readme)
        self.assertEqual(readme.count("@moaa` |"), len(market["plugins"]))


class ProfileTests(unittest.TestCase):
    def test_core_profile_is_small_and_contains_the_moaa_loop(self):
        kit = install.read_json(install.KIT / "config" / "kit.json", None)
        core = {p["id"] for p in kit["plugins"] if p.get("profile") == "core"}
        self.assertTrue({"specialist-council@moaa", "agent-arena-mode@moaa"} <= core)
        self.assertLessEqual(len(core), 12)
        self.assertTrue(all(p.get("profile") in ("core", "full") for p in kit["plugins"]))
        self.assertFalse(any(p.get("optional") for p in kit["plugins"] if p["id"] in core))
