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

    def test_unmodified_old_skill_copies_are_adopted_edited_ones_kept(self):
        import subprocess, tempfile
        kit = Path(install.KIT)
        files = subprocess.run(["git", "-C", str(kit), "ls-tree", "-r", "--name-only", "HEAD", "skills/path-safety/"],
                               capture_output=True, text=True).stdout.split()
        if not files:
            self.skipTest("no git history")
        target = Path(tempfile.mkdtemp()) / "path-safety"
        for f in files:  # the copy an earlier install would have made: the skill as committed
            out = target / f[len("skills/path-safety/"):]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(subprocess.run(["git", "-C", str(kit), "show", f"HEAD:{f}"], capture_output=True).stdout)
        self.assertTrue(install.shipped_by_moaa("path-safety", target))
        (target / "SKILL.md").write_text("my own edits")
        self.assertFalse(install.shipped_by_moaa("path-safety", target))

    def test_mcp_repin_only_touches_moaa_servers(self):
        import json, tempfile
        home = Path(tempfile.mkdtemp()) / ".claude"
        home.mkdir()
        pin = {"command": "cmd", "args": ["/c", "npx", "-y", "rea-agents@6.4.0", "mcp"]}
        def cfg(args):
            (home.parent / ".claude.json").write_text(json.dumps({"mcpServers": {"rea": {"command": "cmd", "args": args}}}))
        cfg(["/c", "npx", "-y", "rea-agents@6.3.0", "mcp"])
        self.assertTrue(install.mcp_outdated("rea", pin, {"mcp": []}, home))   # MOAA's shape, older pin
        cfg(pin["args"])
        self.assertFalse(install.mcp_outdated("rea", pin, {"mcp": []}, home))  # already current
        cfg(["/c", "node", "my-own-rea.js"])
        self.assertFalse(install.mcp_outdated("rea", pin, {"mcp": []}, home))  # the user's own setup
        self.assertTrue(install.mcp_outdated("rea", pin, {"mcp": ["rea"]}, home))  # unless MOAA recorded adding it

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


class StatusTests(unittest.TestCase):
    def test_status_tells_outdated_drift_modified_and_missing_apart(self):
        import json, shutil, tempfile
        kit = install.read_json(install.KIT / "config" / "kit.json", None)
        home = Path(tempfile.mkdtemp()) / ".claude"
        (home / "plugins" / "cache" / "moaa" / "war-room" / "0.0.9").mkdir(parents=True)
        third = next(p for p in kit["plugins"] if p["profile"] == "full" and not p["id"].endswith("@moaa"))
        (home / "plugins" / "installed_plugins.json").write_text(json.dumps({"plugins": {
            "war-room@moaa": [{"version": "0.0.1"}], third["id"]: [{"version": "0.0.0-other"}]}}))
        (home / ".moaa-manifest.json").write_text(json.dumps({"kit_version": "0.0.1", "skills": ["agent-teams"]}))
        shutil.copytree(install.KIT / "skills" / "path-safety", home / "skills" / "path-safety")
        shutil.copytree(install.KIT / "skills" / "agent-teams", home / "skills" / "agent-teams")
        (home / "skills" / "agent-teams" / "SKILL.md").write_text("my edits")
        old = install.rea_spec(kit["mcp"])
        old["args"] = [a.replace(kit["mcp"]["rea"]["args"][1], "rea-agents@1.0.0") for a in old["args"]]
        (home.parent / ".claude.json").write_text(json.dumps({"mcpServers": {"rea": old}}))
        rows = {(kind, name): (state, detail) for kind, name, state, detail in install.status_rows(home, kit)}
        self.assertEqual(rows[("moaa", "kit")][0], "outdated")
        self.assertEqual(rows[("plugin", "war-room@moaa")][0], "outdated")
        self.assertIn("0.0.9", rows[("cache", "war-room@moaa")][1])
        self.assertEqual(rows[("plugin", third["id"])][0], "drift")
        self.assertEqual(rows[("plugin", "specialist-council@moaa")][0], "missing")  # core, absent
        self.assertEqual(rows[("skill", "path-safety")][0], "ok")
        self.assertEqual(rows[("skill", "agent-teams")], ("modified", "edited; MOAA recorded it, so the installer will overwrite it"))
        self.assertEqual(rows[("skill", "networkx")][0], "missing")
        self.assertEqual(rows[("mcp", "rea")][0], "outdated")
        self.assertTrue(any(k == "plugin" and v[0] == "missing" and k2 != "specialist-council@moaa"
                            for (k, k2), v in rows.items()))  # a full install was inferred, so other full plugins count

    def test_status_reports_a_corrupt_file_instead_of_crashing(self):
        import tempfile
        kit = install.read_json(install.KIT / "config" / "kit.json", None)
        home = Path(tempfile.mkdtemp()) / ".claude"
        (home / "plugins").mkdir(parents=True)
        (home / "plugins" / "installed_plugins.json").write_text("{not json")
        rows = install.status_rows(home, kit)
        self.assertIn(("file", "installed_plugins.json"), [(k, n) for k, n, s, _ in rows if s == "corrupt"])

    def test_doctor_covers_every_suite_and_plugin(self):
        labels = [label for label, _, _ in install.doctor_checks()]
        for name in ("installer tests", "war-room bus test", "public-release scan", "MODELS.md matches the plugins",
                     "catalog matches installed plugins", "validate marketplace", "validate war-room"):
            self.assertIn(name, labels)


class ProfileTests(unittest.TestCase):
    def test_core_profile_is_small_and_contains_the_moaa_loop(self):
        kit = install.read_json(install.KIT / "config" / "kit.json", None)
        core = {p["id"] for p in kit["plugins"] if p.get("profile") == "core"}
        self.assertTrue({"specialist-council@moaa", "agent-arena-mode@moaa"} <= core)
        self.assertLessEqual(len(core), 12)
        self.assertTrue(all(p.get("profile") in ("core", "full") for p in kit["plugins"]))
        self.assertFalse(any(p.get("optional") for p in kit["plugins"] if p["id"] in core))
