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

    def test_update_notice_checks_once_a_day_and_names_the_right_command(self):
        kit = self.home / "kit"
        (kit / "config").mkdir(parents=True)
        (kit / "config" / "kit.json").write_text(json.dumps({"version": "0.13.0"}))
        (self.home / "plugins" / "known_marketplaces.json").write_text(json.dumps({"moaa": {
            "source": {"source": "directory", "path": str(kit)}, "installLocation": str(kit)}}))
        calls = []

        def fetch(repo):
            calls.append(repo)
            return "0.14.0"
        notice = catalog.update_notice(self.home, fetch, now=1000.0)
        self.assertIn("MOAA 0.14.0 is available (installed 0.13.0)", notice)
        self.assertIn("install.py\" --update", notice)
        catalog.update_notice(self.home, fetch, now=1000.0 + 3600)
        self.assertEqual(len(calls), 1)  # cached for a day
        (kit / "config" / "kit.json").write_text(json.dumps({"version": "0.14.0"}))
        self.assertIsNone(catalog.update_notice(self.home, fetch, now=1000.0 + 7200))  # up to date: silent
        os.environ["MOAA_NO_UPDATE_CHECK"] = "1"
        try:
            (kit / "config" / "kit.json").write_text(json.dumps({"version": "0.1.0"}))
            self.assertIsNone(catalog.update_notice(self.home, fetch, now=1000.0))
        finally:
            del os.environ["MOAA_NO_UPDATE_CHECK"]

        def offline(repo):
            raise OSError("no network")
        self.assertIsNone(catalog.update_notice(Path(tempfile.mkdtemp()), offline))  # nothing known: silent

    def test_use_serves_indexed_skills_logs_and_suggests_enabling(self):
        for _ in range(catalog.PROMOTE_USES):
            self.assertEqual(catalog.use(self.home, str(self.stripe)), 0)
        self.assertEqual(catalog.uses(self.home), {"off@m": catalog.PROMOTE_USES})
        self.assertIn("claude plugin enable off@m", catalog.promote_hint(self.home, "off@m"))
        self.assertEqual(catalog.use(self.home, str(self.home / "settings.json")), 1)  # not in the index: refused

    def test_hook_command_skips_interpreters_that_exit_3_and_runs_the_next(self):
        import shutil, subprocess
        # the full path: on Windows a bare "bash" finds System32's WSL launcher before Git Bash on PATH
        bash = shutil.which("bash")
        if not bash or "system32" in bash.lower():
            self.skipTest("needs Git Bash or a POSIX bash, as Claude Code's hook runner does")
        root = Path(__file__).resolve().parents[1]
        command = json.loads((root / "hooks" / "hooks.json").read_text())["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        fake = self.home / "bin"
        fake.mkdir()
        (fake / "py").write_text("#!/bin/sh\nexit 3\n")  # an interpreter older than 3.10
        (fake / "py").chmod(0o755)
        (fake / "python3").write_text(f"#!/bin/sh\nexec \"{Path(sys.executable).as_posix()}\" \"$@\"\n")
        (fake / "python3").chmod(0o755)
        env = {**os.environ, "CLAUDE_PLUGIN_ROOT": root.as_posix(), "CLAUDE_CONFIG_DIR": str(self.home),
               "PATH": fake.as_posix() + os.pathsep + os.environ["PATH"]}
        r = subprocess.run([bash, "-c", command["command"]], input=json.dumps({"prompt": "stripe webhooks payments"}),
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stripe-integration", r.stdout)


if __name__ == "__main__":
    unittest.main()
