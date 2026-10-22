"""moaa-catalog tests with a fake Claude home: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog  # noqa: E402


def skill(root, name, desc):
    d = root / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\nBody of {name}.\n", encoding="utf-8")
    return d / "SKILL.md"


class Catalog(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        off, on = self.home / "cache" / "off", self.home / "cache" / "on"
        self.stripe = skill(off, "stripe-integration", "Stripe payments, subscriptions and webhooks")
        skill(off, "terraform-aws-modules", "Terraform modules for AWS Lambda and API Gateway")
        skill(off, "readme", "Write a README")
        skill(on, "stripe-listed", "Stripe skill that is already enabled")
        (self.home / "plugins").mkdir()
        (self.home / "plugins" / "installed_plugins.json").write_text(json.dumps({"plugins": {
            "off@m": [{"installPath": str(off)}], "on@m": [{"installPath": str(on)}]}}))
        (self.home / "settings.json").write_text(json.dumps({"enabledPlugins": {"off@m": False, "on@m": True}}))

    def test_search_covers_only_disabled_plugins_and_ranks_name_hits(self):
        found = catalog.search(self.home, "stripe webhooks")
        self.assertEqual([r[2]["name"] for r in found], ["stripe-integration"])
        self.assertEqual(catalog.search(self.home, "kubernetes"), [])

    def test_index_is_cached_until_settings_change(self):
        index = catalog.load_index(self.home)
        path = self.home / "moaa-catalog" / "index.json"
        before = path.stat().st_mtime_ns
        catalog.load_index(self.home)
        self.assertEqual(path.stat().st_mtime_ns, before)  # unchanged inputs: not rebuilt
        settings = self.home / "settings.json"
        settings.write_text(json.dumps({"enabledPlugins": {"off@m": True, "on@m": True}}))
        os.utime(settings, (index["stamp"][0] + 5, index["stamp"][0] + 5))
        rebuilt = catalog.load_index(self.home)["skills"]
        self.assertTrue(rebuilt and all(s["on"] for s in rebuilt))  # rebuilt: everything is enabled now
        self.assertEqual(catalog.search(self.home, "stripe"), [])  # and listed in full, so nothing to suggest

    def test_hook_fires_on_a_strong_match_and_stays_quiet_otherwise(self):
        hit = catalog.hook_prompt(self.home, {"prompt": "Set up Stripe subscription webhooks for billing"})
        self.assertIn("stripe-integration", hit or "")
        self.assertIsNone(catalog.hook_prompt(self.home, {"prompt": "fix the typo in my notes please"}))
        self.assertIsNone(catalog.hook_prompt(self.home, {"prompt": "/stripe-integration now"}))  # slash commands
        notice = "<task-notification>Stripe subscription webhooks billing job completed</task-notification>"
        self.assertIsNone(catalog.hook_prompt(self.home, {"prompt": notice}))  # harness notices

    def test_short_forms_expand_and_project_files_boost_but_never_trigger(self):
        self.assertEqual([r[2]["name"] for r in catalog.search(self.home, "tf aws")], ["terraform-aws-modules"])
        proj = Path(tempfile.mkdtemp())
        (proj / "main.tf").write_text("")
        self.assertEqual(catalog.project_hints(proj), ["terraform"])
        self.assertEqual(catalog.search(self.home, "readme", cwd=proj)[0][2]["name"], "readme")  # hint alone: no match
        plain = catalog.search(self.home, "aws lambda", cwd=Path(tempfile.mkdtemp()))[0][0]
        boosted = catalog.search(self.home, "aws lambda", cwd=proj)[0][0]
        self.assertGreater(boosted, plain)

    def test_all_on_mode_also_suggests_enabled_skills_through_the_skill_tool(self):
        self.assertEqual([r[2]["name"] for r in catalog.search(self.home, "stripe")], ["stripe-integration"])
        settings = self.home / "settings.json"
        settings.write_text(json.dumps({"enabledPlugins": {"off@m": False, "on@m": True}, "skillListingMaxDescChars": 200}))
        os.utime(settings, (settings.stat().st_mtime + 5,) * 2)
        names = {r[2]["name"]: r[2] for r in catalog.search(self.home, "stripe")}
        self.assertEqual(set(names), {"stripe-integration", "stripe-listed"})
        self.assertIn('Skill tool, skill "on:stripe-listed"', catalog.how(names["stripe-listed"], "catalog.py"))
        self.assertIn("catalog.py\" use", catalog.how(names["stripe-integration"], "catalog.py"))

    def test_use_serves_indexed_skills_logs_and_suggests_enabling(self):
        for _ in range(catalog.PROMOTE_USES):
            self.assertEqual(catalog.use(self.home, str(self.stripe)), 0)
        self.assertEqual(catalog.uses(self.home), {"off@m": catalog.PROMOTE_USES})
        self.assertIn("claude plugin enable off@m", catalog.promote_hint(self.home, "off@m"))
        self.assertEqual(catalog.use(self.home, str(self.home / "settings.json")), 1)  # not in the index: refused


if __name__ == "__main__":
    unittest.main()
