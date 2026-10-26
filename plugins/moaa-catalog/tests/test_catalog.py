"""moaa-catalog tests with a fake Claude home: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

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
        catalog.load_index(self.home)
        ask = "Set up Stripe subscription webhooks for billing"
        hit = catalog.hook_prompt(self.home, {"prompt": ask})
        self.assertIn("stripe-integration", hit or "")
        self.assertIsNone(catalog.hook_prompt(self.home, {"prompt": "fix the typo in my notes please"}))
        self.assertIsNone(catalog.hook_prompt(self.home, {"prompt": "/stripe-integration now"}))  # slash commands
        notice = "<task-notification>Stripe subscription webhooks billing job completed</task-notification>"
        self.assertIsNone(catalog.hook_prompt(self.home, {"prompt": notice}))  # harness notices
        # the desktop app puts a <system-reminder> before the user's words (first prompt after a restart)
        tagged = "<system-reminder>\nLinked sessions now: x (idle).\n</system-reminder>\n\n" + ask
        self.assertIn("stripe-integration", catalog.hook_prompt(self.home, {"prompt": tagged}) or "")
        self.assertIsNone(catalog.hook_prompt(self.home, {"prompt": "<system-reminder>Stripe webhooks</system-reminder>"}))
        summary = "Below is a conversation log from a Claude Code coding session.\n" + ask  # desktop summary run
        self.assertIsNone(catalog.hook_prompt(self.home, {"prompt": summary}))
        os.environ["MOAA_CATALOG_HINTS"] = "off"  # set on strata's helper processes
        try:
            self.assertIsNone(catalog.hook_prompt(self.home, {"prompt": ask}))
        finally:
            del os.environ["MOAA_CATALOG_HINTS"]

    def test_prompt_hook_never_rebuilds_the_index_inline(self):
        ask = {"prompt": "Set up Stripe subscription webhooks for billing"}
        with mock.patch.object(catalog, "rebuild_in_background") as bg:
            self.assertIsNone(catalog.hook_prompt(self.home, ask))  # no index yet: quiet, rebuild started
            self.assertEqual(bg.call_count, 1)
            self.assertFalse((self.home / "moaa-catalog" / "index.json").exists())
            index = catalog.load_index(self.home)
            settings = self.home / "settings.json"
            os.utime(settings, (index["stamp"][0] + 5,) * 2)  # now stale
            self.assertIn("stripe-integration", catalog.hook_prompt(self.home, ask))  # the stale index still serves
            self.assertEqual(bg.call_count, 2)
        with mock.patch.object(catalog, "claude_home", return_value=self.home):
            self.assertEqual(catalog.main(["index"]), 0)  # what the background process runs
        self.assertEqual(catalog.load_index(self.home, wait=False)["stamp"], catalog.stamp(self.home))

    def test_background_rebuild_starts_at_most_once_a_minute(self):
        with mock.patch("subprocess.Popen") as popen:
            catalog.rebuild_in_background(self.home)
            catalog.rebuild_in_background(self.home)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(popen.call_args.args[0][-1], "index")

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
        catalog.load_index(self.home)  # the prompt hook only reads it
        r = subprocess.run([bash, "-c", command["command"]], input=json.dumps({"prompt": "stripe webhooks payments"}),
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stripe-integration", r.stdout)

    def test_duplicates_prefer_the_enabled_copy_in_all_on_mode(self):
        skill(self.home / "cache" / "on", "stripe-integration", "Stripe payments, subscriptions and webhooks")
        settings = self.home / "settings.json"
        settings.write_text(json.dumps({"enabledPlugins": {"off@m": False, "on@m": True}, "skillListingMaxDescChars": 200}))
        os.utime(settings, (settings.stat().st_mtime + 5,) * 2)
        hits = [r[2] for r in catalog.search(self.home, "stripe webhooks") if r[2]["name"] == "stripe-integration"]
        self.assertEqual([(h["pid"], h["on"]) for h in hits], [("on@m", True)])


class Ruflo(unittest.TestCase):
    """The daily check of the global ruflo CLI that ruflo-core's hooks need (without it they run npx)."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        (self.home / "plugins").mkdir()
        (self.home / "plugins" / "installed_plugins.json").write_text(json.dumps({"plugins": {}}))

    def enable_ruflo(self, on=True):
        (self.home / "plugins" / "installed_plugins.json").write_text(json.dumps({"plugins": {
            "ruflo-core@ruflo": [{"installPath": str(self.home)}]}}))
        (self.home / "settings.json").write_text(json.dumps({"enabledPlugins": {"ruflo-core@ruflo": on}}))

    def wanted(self, now=None, env=None):
        clean = {k: v for k, v in os.environ.items()
                 if k not in ("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "MOAA_NO_UPDATE_CHECK", "MOAA_RUFLO_UPDATE")}
        with mock.patch.dict(os.environ, {**clean, **(env or {})}, clear=True), \
                mock.patch("shutil.which", return_value="npm"):
            return catalog.ruflo_wanted(self.home, now)

    def test_due_once_a_day_only_while_a_ruflo_plugin_is_enabled(self):
        self.assertFalse(self.wanted())  # no ruflo plugin
        self.enable_ruflo(on=False)
        self.assertFalse(self.wanted())  # installed but disabled
        self.enable_ruflo()
        self.assertTrue(self.wanted())
        stamp = self.home / "moaa-catalog" / "ruflo.json"
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(json.dumps({"checked": 1000.0}))
        self.assertFalse(self.wanted(now=1000.0 + catalog.RUFLO_EVERY - 1))
        self.assertTrue(self.wanted(now=1000.0 + catalog.RUFLO_EVERY))
        for env in ({"MOAA_RUFLO_UPDATE": "off"}, {"MOAA_NO_UPDATE_CHECK": "1"},
                    {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}):
            self.assertFalse(self.wanted(now=10 ** 10, env=env))

    def fake_npm(self, installed, latest, install_ok=True, bin_entry="bin/ruflo.js"):
        """A fake npm over a real folder: <home>/npm/node_modules is the global root, and an install with --prefix
        writes the staged package the way npm does on Windows (<prefix>/node_modules/ruflo)."""
        calls, root = [], self.home / "npm" / "node_modules"

        def package(where, version, entry="bin/ruflo.js"):
            where.mkdir(parents=True, exist_ok=True)
            (where / "package.json").write_text(json.dumps({"version": version, "bin": {"ruflo": entry}}))

        if installed:
            package(root / "ruflo", installed)

        def run(argv):
            calls.append(argv[1:])
            out = ""
            if argv[1] == "ls":
                out = json.dumps({"dependencies": {"ruflo": {"version": installed}}} if installed else {})
            elif argv[1] == "view":
                out = latest + "\n"
            elif argv[1] == "root":
                out = str(root) + "\n"
            elif argv[1] == "install" and install_ok:
                if "--prefix" in argv:
                    package(Path(argv[argv.index("--prefix") + 1]) / "node_modules" / "ruflo", latest, bin_entry)
                else:
                    package(root / "ruflo", latest, bin_entry)
            return mock.Mock(stdout=out, stderr="", returncode=0 if install_ok or argv[1] != "install" else 1)
        return calls, run, root

    def version_at(self, root):
        return json.loads((root / "ruflo" / "package.json").read_text())["version"]

    def test_update_installs_when_missing_or_older_and_skips_when_current(self):
        with mock.patch("shutil.which", return_value="npm"):
            calls, run, root = self.fake_npm("", "3.63.1")
            self.assertEqual(catalog.ruflo_update(self.home, run), "ruflo none -> 3.63.1")
            self.assertIn(["install", "-g", "ruflo@3.63.1"], calls)  # first install: plain, npm writes the shims
            calls, run, root = self.fake_npm("3.63.1", "3.63.1")
            self.assertEqual(catalog.ruflo_update(self.home, run), "ruflo 3.63.1 is current")
            self.assertNotIn("install", [c[0] for c in calls])
            calls, run, root = self.fake_npm("3.63.1", "")  # offline: nothing installed or removed
            self.assertIn("npm view failed", catalog.ruflo_update(self.home, run))
        log = (self.home / "moaa-catalog" / "ruflo.log").read_text(encoding="utf-8")
        self.assertEqual(len(log.splitlines()), 3)

    def test_an_update_is_staged_and_swapped_in_so_the_cli_never_goes_missing(self):
        with mock.patch("shutil.which", return_value="npm"):
            calls, run, root = self.fake_npm("3.62.0", "3.63.1")
            self.assertEqual(catalog.ruflo_update(self.home, run), "ruflo 3.62.0 -> 3.63.1")
        self.assertEqual(self.version_at(root), "3.63.1")
        self.assertNotIn(["install", "-g", "ruflo@3.63.1"], calls)  # never the plain in-place install
        self.assertTrue(any("--prefix" in c for c in calls))
        self.assertEqual(sorted(x.name for x in root.parent.iterdir()), ["node_modules"])  # stage cleaned up
        self.assertEqual([x.name for x in root.iterdir()], ["ruflo"])  # old copy removed

    def test_a_failed_or_blocked_swap_keeps_the_old_cli(self):
        with mock.patch("shutil.which", return_value="npm"):
            calls, run, root = self.fake_npm("3.62.0", "3.63.1", install_ok=False)
            self.assertIn("ruflo stays at 3.62.0", catalog.ruflo_update(self.home, run))
            self.assertEqual(self.version_at(root), "3.62.0")
            calls, run, root = self.fake_npm("3.62.0", "3.63.1")
            real = os.replace
            moves = []

            def locked(src, dst):  # the second rename fails, as a held file would on Windows
                moves.append(dst)
                if len(moves) == 2:
                    raise PermissionError("in use")
                return real(src, dst)
            with mock.patch("os.replace", side_effect=locked):
                self.assertIn("ruflo stays at 3.62.0", catalog.ruflo_update(self.home, run))
            self.assertEqual(self.version_at(root), "3.62.0")

    def test_a_changed_bin_entry_gets_a_plain_install(self):
        with mock.patch("shutil.which", return_value="npm"):
            calls, run, root = self.fake_npm("3.62.0", "4.0.0", bin_entry="dist/cli.js")
            self.assertIn("plain install", catalog.ruflo_update(self.home, run))
        self.assertIn(["install", "-g", "ruflo@4.0.0"], calls)
        self.assertEqual(self.version_at(root), "4.0.0")


if __name__ == "__main__":
    unittest.main()
