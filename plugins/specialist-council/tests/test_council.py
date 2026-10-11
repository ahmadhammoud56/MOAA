import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import os  # noqa: E402
os.environ["CLAUDE_CONFIG_DIR"] = tempfile.mkdtemp(prefix="council-test-home-")  # never read a real home
os.environ.pop("COUNCIL_FORGED_DIR", None)
import council  # noqa: E402


class CouncilTests(unittest.TestCase):
    def setUp(self):
        self.profile = council.load_profile()
        self.temp = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_profile_covers_every_agent_personality_and_team(self):
        agents = council.agent_files(ROOT / "agents")
        self.assertEqual(len(agents), 60)
        council.validate(self.profile, agents, council.personality_ids())
        tiers = {r["tier"] for r in self.profile["roles"].values()}
        self.assertEqual(tiers, set(council.TIERS))  # all four models are used
        self.assertEqual(self.profile["models"]["opus"], "claude-opus-5-5")
        self.assertEqual(self.profile["models"]["fable"], "claude-fable-5-1")

    def test_shipped_agents_match_profile(self):
        self.assertTrue(council.check(ROOT / "agents", self.profile)["ok"])

    def test_apply_is_idempotent_and_check_detects_drift(self):
        agents = self.tmp / "agents"
        shutil.copytree(ROOT / "agents", agents)
        self.assertEqual(council.apply(agents, self.profile), [])
        path = agents / "council-scout.md"
        path.write_text(path.read_text(encoding="utf-8").replace("claude-haiku-5-5", "inherit"), encoding="utf-8")
        with self.assertRaises(council.CouncilError):
            council.check(agents, self.profile)
        self.assertEqual(council.apply(agents, self.profile), ["scout"])
        self.assertTrue(council.check(agents, self.profile)["ok"])

    def test_personality_shifts_effort_not_model_and_clamps(self):
        base = council.resolve(self.profile, "validation-auditor")
        skeptic = council.resolve(self.profile, "validation-auditor", ["skeptic"])
        self.assertEqual((base["effort"], skeptic["effort"]), ("high", "xhigh"))
        self.assertEqual(base["model"], skeptic["model"])
        self.assertEqual(council.resolve(self.profile, "challenger", ["skeptic", "perfectionist"])["effort"], "xhigh")
        self.assertEqual(council.resolve(self.profile, "scout", ["pragmatist", "minimalist"])["effort"], "low")
        with self.assertRaises(council.CouncilError):
            council.resolve(self.profile, "scout", ["skeptic", "pragmatist", "teacher"])
        with self.assertRaises(council.CouncilError):
            council.resolve(self.profile, "nonexistent")

    def test_render_lists_every_role_and_team(self):
        text = council.render(self.profile)
        for rid in self.profile["roles"]:
            self.assertIn(f"| {rid} |", text)
        for team in self.profile["teams"]:
            self.assertIn(f"**{team}**", text)
        shipped = (council.SKILL / "references" / "model-profile.md").read_text(encoding="utf-8")
        self.assertEqual(shipped, text)  # generated reference is current

    def test_validate_rejects_bad_profiles(self):
        agents = council.agent_files(ROOT / "agents")
        styles = council.personality_ids()
        for mutate in (lambda p: p["roles"]["scout"].update(tier="gpt"),
                       lambda p: p["roles"]["scout"].update(effort="extreme"),
                       lambda p: p["roles"].pop("scout"),
                       lambda p: p["teams"]["Bug Clinic"].append(["nobody"]),
                       lambda p: p["personality_effort_shift"].update(skeptic=5)):
            bad = json.loads(json.dumps(self.profile))
            mutate(bad)
            with self.assertRaises(council.CouncilError):
                council.validate(bad, agents, styles)

    def forged_member(self, home, slug="keep", status="active", card=True, legacy=False):
        forged = home / "skills" / "specialist-council" / "forged" if legacy else council.forged_home(home)
        (forged / slug).mkdir(parents=True, exist_ok=True)
        (forged / slug / "profile.json").write_text("{}", encoding="utf-8")
        registry = forged / "registry.json"
        data = json.loads(registry.read_text(encoding="utf-8")) if registry.is_file() else {}
        data[slug] = {"status": status, "model": "claude-sonnet-5-5", "effort": "high",
                      "knowledge_base": (forged / slug).as_posix()}
        registry.write_text(json.dumps(data), encoding="utf-8")
        (home / "agents").mkdir(parents=True, exist_ok=True)
        if card:
            (home / "agents" / f"council-forged-{slug}.md").write_text(
                f'---\nname: "council-forged-{slug}"\nmodel: "claude-sonnet-5-5"\neffort: "high"\n---\n'
                f'Knowledge base: `{(forged / slug).as_posix()}`\n', encoding="utf-8")
        return forged

    def test_check_forged_members(self):
        home = self.tmp / "home"
        agents = home / "agents"
        forged = council.forged_home(home)
        self.forged_member(home)
        self.forged_member(home, "parked", status="suspended", card=False)
        self.assertEqual(council.check_forged(agents, self.profile, forged), {"active": 1, "total": 2})
        cases = [
            lambda: (agents / "council-forged-parked.md").write_text("---\nname: x\n---\n", encoding="utf-8"),
            lambda: (agents / "council-forged-keep.md").unlink(),
            lambda: (agents / "council-forged-stray.md").write_text("---\nname: x\n---\n", encoding="utf-8"),
            lambda: shutil.rmtree(forged / "keep"),
            lambda: (agents / "council-forged-keep.md").write_text(
                '---\nname: "council-forged-keep"\nmodel: "claude-opus-5-5"\neffort: "high"\n---\n', encoding="utf-8"),
        ]
        for i, break_it in enumerate(cases):
            shutil.rmtree(home)
            self.forged_member(home)
            self.forged_member(home, "parked", status="suspended", card=False)
            break_it()
            with self.subTest(case=i), self.assertRaises(council.CouncilError):
                council.check_forged(agents, self.profile, forged)

    def test_resolve_forged_member_and_refuse_suspended(self):
        home = self.tmp / "home"
        forged = council.forged_home(home)
        self.forged_member(home)
        self.forged_member(home, "parked", status="suspended", card=False)
        for name in ("keep", "forged-keep", "council-forged-keep"):
            member = council.forged_member(name, forged)
            r = council.resolve_forged(self.profile, name, member, ["skeptic"])
            self.assertEqual((r["model"], r["base_effort"], r["effort"]), ("claude-sonnet-5-5", "high", "xhigh"))
        with self.assertRaises(council.CouncilError):
            council.resolve_forged(self.profile, "parked", council.forged_member("parked", forged))
        self.assertIsNone(council.forged_member("scout", forged))

    def test_migrate_standalone_install_keeps_forged_and_removes_duplicates(self):
        home = self.tmp.resolve() / "home"  # migrate works on resolved paths (Windows 8.3 names differ)
        legacy = home / "skills" / "specialist-council"
        self.forged_member(home, legacy=True)
        (legacy / "SKILL.md").write_text("old", encoding="utf-8")
        for rid in ("scout", "arbiter"):
            shutil.copy2(ROOT / "agents" / f"council-{rid}.md", home / "agents" / f"council-{rid}.md")
        result = council.migrate(home, self.profile)
        self.assertEqual((result["forged"], result["skill"], result["agents"]), (True, True, 2))
        target = council.forged_home(home)
        self.assertEqual(json.loads((target / "registry.json").read_text())["keep"]["knowledge_base"], (target / "keep").as_posix())
        self.assertIn((target / "keep").as_posix(), (home / "agents" / "council-forged-keep.md").read_text(encoding="utf-8"))
        self.assertFalse(legacy.exists())
        self.assertFalse((home / "agents" / "council-scout.md").exists())
        self.assertTrue((Path(result["backup"]) / "skill" / "SKILL.md").is_file())
        checked = council.check(ROOT / "agents", self.profile, user_agents=home / "agents", forged_dir=target)
        self.assertEqual(checked["forged"], {"active": 1, "total": 1})
        self.assertFalse(council.migrate(home, self.profile)["forged"])  # idempotent
        import subprocess
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(home))
        out = subprocess.run([sys.executable, str(ROOT / "council.py"), "check"], capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main()
