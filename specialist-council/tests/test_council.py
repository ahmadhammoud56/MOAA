import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
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
        shipped = (ROOT / "skill" / "references" / "model-profile.md").read_text(encoding="utf-8")
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

    def forged_member(self, home, slug="keep", status="active", card=True):
        forged = home / "skills" / "specialist-council" / "forged"
        (forged / slug).mkdir(parents=True, exist_ok=True)
        (forged / slug / "profile.json").write_text("{}", encoding="utf-8")
        registry = forged / "registry.json"
        data = json.loads(registry.read_text(encoding="utf-8")) if registry.is_file() else {}
        data[slug] = {"status": status, "model": "claude-sonnet-5-5", "effort": "high"}
        registry.write_text(json.dumps(data), encoding="utf-8")
        (home / "agents").mkdir(parents=True, exist_ok=True)
        if card:
            (home / "agents" / f"council-forged-{slug}.md").write_text(
                f'---\nname: "council-forged-{slug}"\nmodel: "claude-sonnet-5-5"\neffort: "high"\n---\n', encoding="utf-8")
        return forged

    def test_check_forged_members(self):
        home = self.tmp / "home"
        skill = home / "skills" / "specialist-council"
        agents = home / "agents"
        self.forged_member(home)
        self.forged_member(home, "parked", status="suspended", card=False)
        self.assertEqual(council.check_forged(agents, self.profile, skill), {"active": 1, "total": 2})
        cases = [
            lambda: (agents / "council-forged-parked.md").write_text("---\nname: x\n---\n", encoding="utf-8"),
            lambda: (agents / "council-forged-keep.md").unlink(),
            lambda: (agents / "council-forged-stray.md").write_text("---\nname: x\n---\n", encoding="utf-8"),
            lambda: shutil.rmtree(skill / "forged" / "keep"),
            lambda: (agents / "council-forged-keep.md").write_text(
                '---\nname: "council-forged-keep"\nmodel: "claude-opus-5-5"\neffort: "high"\n---\n', encoding="utf-8"),
        ]
        for i, break_it in enumerate(cases):
            shutil.rmtree(home)
            self.forged_member(home)
            self.forged_member(home, "parked", status="suspended", card=False)
            break_it()
            with self.subTest(case=i), self.assertRaises(council.CouncilError):
                council.check_forged(agents, self.profile, skill)

    def test_install_into_fresh_home_and_preserve_forged_members(self):
        home = self.tmp / "home"
        forged = self.forged_member(home)
        result = council.install(home, self.profile)
        self.assertEqual(result["forged"], {"active": 1, "total": 1})
        self.assertEqual(result["agents"], 60)
        self.assertTrue((forged / "registry.json").is_file())
        self.assertTrue((home / "agents" / "council-forged-keep.md").is_file())
        self.assertTrue((home / "skills" / "specialist-council" / "profile.json").is_file())
        self.assertTrue((home / "skills" / "specialist-council" / "references" / "model-profile.md").is_file())
        installed = home / "skills" / "specialist-council" / "council.py"  # installed tool works from its own folder
        import subprocess
        out = subprocess.run([sys.executable, str(installed), "check", "--agents", str(home / "agents")],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main()
