"""App-side tests: demo run, drill-down/usage/history data, settings v2 validation. Run: python -m unittest discover -s tests"""
import json
import os
import random
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import warroom  # noqa: E402


class Sandbox(unittest.TestCase):
    """Points War Room's data folder at a temp dir so nothing touches ~/.claude/war-room."""
    def setUp(self):
        home = tempfile.mkdtemp()
        patches = {"HOME": home, "RUNS": os.path.join(home, "runs"), "CONFIG": os.path.join(home, "config.json"),
                   "CALIBRATION": os.path.join(home, "calibration.json"), "USER_PROFILES": os.path.join(home, "profiles.json")}
        for k, v in patches.items():
            p = mock.patch.object(warroom, k, v)
            p.start()
            self.addCleanup(p.stop)


class Demo(Sandbox):
    def test_demo_plays_to_the_end(self):
        run = warroom.make_demo(drive=False)
        bus, mem, rng = warroom.open_bus(run, "conductor"), {}, random.Random(7)
        st = warroom.state(run)
        self.assertTrue(st["demo"])
        self.assertEqual(len(st["workers"]), len(warroom.DEMO_ROSTER))
        with mock.patch.object(warroom.time, "time", side_effect=self.clock()):
            for _ in range(600):
                if warroom.demo_tick(bus, mem, rng) == "finished":
                    break
        st = warroom.state(run)
        self.assertTrue(st["control"]["finished"])
        work = [t for t in st["tasks"] if t["kind"] == "work"]
        self.assertEqual(len(work), len(warroom.DEMO_SEED + warroom.DEMO_PLAN + warroom.DEMO_LATER))
        self.assertTrue(all(t["status"] in ("merged", "done") for t in work), [t["status"] for t in work])
        self.assertTrue(any(t["title"].startswith("Arbitrate") for t in st["tasks"]))  # the scripted double fail
        self.assertTrue(all(w["status"] == "stopped" for w in st["workers"]))
        self.assertIn("(demo)", st["report"])
        self.assertFalse(warroom.integrate_into_project(bus)["ok"])
        d = warroom.worker_detail(run, "swift")
        self.assertTrue(d["tools"] and d["checkpoints"] and d["meter"] and d["tasks"])
        u = warroom.usage(run)
        self.assertEqual(set(u["series"]), {w[0] for w in warroom.DEMO_ROSTER})
        h = warroom.history()
        self.assertEqual([x["run"] for x in h], [run])
        self.assertGreater(h[0]["merged"], 0)
        self.assertIn("(demo)", h[0]["report"])
        self.assertTrue(warroom.last_meter().startswith("unknown"))  # simulated usage never reads as the real meter
        r = warroom.replay(run)  # the replay carries the full logs, not the live 200-event slice
        self.assertEqual(len(r["all_events"]), warroom.open_bus(run).db.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        self.assertTrue(r["all_messages"] and r["all_checkpoints"] and r["meter_log"])

    @staticmethod
    def clock():
        t = 1_800_000_000.0
        while True:  # each call moves time on 0.2 s, so merges and the finish countdown elapse quickly
            t += .2
            yield t

    def test_stop_and_resume_demo(self):
        run = warroom.make_demo(drive=False)
        bus = warroom.open_bus(run)
        warroom.stop_all(bus, "test")
        self.assertTrue(all(w["status"] == "stopped" for w in warroom.state(run)["workers"]))
        bus.control("run", clear=True)
        self.assertEqual(warroom.resume_all(bus), [])
        self.assertTrue(all(w["status"] == "busy" for w in warroom.state(run)["workers"]))


class Consoles(unittest.TestCase):
    def test_console_status(self):
        cs = warroom.console_status
        self.assertEqual(cs("working: Edit"), "working")
        self.assertEqual(cs("woken by inbox"), "working")
        self.assertEqual(cs("parked: waiting for inbox"), "waiting")
        self.assertEqual(cs("idle: wait timed out"), "idle")
        self.assertEqual(cs("working: Edit", stopped=True), "stopped")
        self.assertEqual(cs("parked: waiting for inbox", finished=True), "done")
        self.assertEqual(cs(""), "starting")

    def test_consoles_keep_war_room_title(self):
        with mock.patch.object(warroom, "IS_WIN", True), mock.patch.object(warroom.subprocess, "Popen") as popen:
            warroom.spawn_console(["claude", "attach", "abc"])
        self.assertEqual(popen.call_args.kwargs["env"]["CLAUDE_CODE_DISABLE_TERMINAL_TITLE"], "1")

    def test_workers_get_overload_backoff(self):
        d = tempfile.mkdtemp()
        w = {"name": "b1", "allow": [], "deny": [], "mcp": []}
        with mock.patch.object(warroom, "user_mcp_servers", return_value={}):
            wdir = warroom.worker_files(d, w, "run-1")
        env = json.load(open(os.path.join(wdir, "settings.json")))["env"]
        self.assertGreater(int(env["CLAUDE_CODE_OVERLOADED_RETRY_MAX_DELAY_MS"]), int(env["CLAUDE_CODE_OVERLOADED_RETRY_BASE_DELAY_MS"]))


class SettingsV2(Sandbox):
    def test_profile_overlay_only_changes_plugins(self):
        warroom.save_json(warroom.USER_PROFILES, {"kinds": {"builder": {"plugins": ["a@m", "b@m"], "allow": ["Bash(*)"]},
                                                            "nope": {"plugins": ["x"]}}})
        p = warroom.load_profiles()
        self.assertEqual(p["kinds"]["builder"]["plugins"], ["a@m", "b@m"])
        self.assertNotIn("Bash(*)", p["kinds"]["builder"]["allow"])
        self.assertNotIn("nope", p["kinds"])

    def test_role_models(self):
        roles = ["builder", "arbiter"]
        self.assertEqual(warroom.validate_role_models({"builder": {"tier": "haiku", "effort": "low"}}, roles),
                         {"builder": {"tier": "haiku", "effort": "low"}})
        for bad in ({"wizard": {"tier": "haiku", "effort": "low"}}, {"builder": {"tier": "gpt", "effort": "low"}},
                    {"builder": {"tier": "haiku", "effort": "turbo"}}):
            with self.assertRaises(ValueError):
                warroom.validate_role_models(bad, roles)
        profiles = json.load(open(os.path.join(HERE, "profiles.json")))
        plan = {"workers": [{"name": "b1", "role": "builder"}, {"name": "b2", "role": "builder", "model": "claude-opus-5-5"}]}
        with mock.patch.object(warroom, "resolve_role", side_effect=AssertionError("council not needed")), \
                mock.patch.object(warroom, "worktrees_dir", return_value="/wt"):
            out = warroom.resolve_plan(plan, profiles, {"specialist-council@moaa": "/p"}, {}, None,
                                       {"builder": {"tier": "haiku", "effort": "low"}})
        self.assertEqual((out["workers"][0]["model"], out["workers"][0]["effort"]),
                         (warroom.council_models()["haiku"], "low"))
        self.assertEqual(out["workers"][1]["model"], "claude-opus-5-5")  # the plan wins over the app default


class NewRun(Sandbox):
    def test_clean_plan_keeps_only_safe_fields(self):
        raw = {"name": "Big Job", "goal": "g", "project": "/elsewhere", "budget": {"max_workers": 8},
               "workers": [{"name": "B1", "role": "builder", "brief": "x", "model": "haiku", "effort": "turbo",
                            "plugins": ["evil@m"], "allow": ["Bash(*)"], "kind": "builder", "write": True}],
               "tasks": [{"title": "t", "gate": 0}, {"title": ""}, "junk", {"title": "u", "assignee": "b1"}]}
        out = warroom.clean_plan(raw, "/proj")
        self.assertEqual(out["project"], "/proj")
        self.assertNotIn("budget", out)
        self.assertEqual(out["workers"], [{"name": "b1", "role": "builder", "brief": "x",
                                           "model": warroom.council_models()["haiku"]}])
        self.assertEqual([(t["title"], t["gate"]) for t in out["tasks"]], [("t", 0), ("u", 1)])
        with self.assertRaises(ValueError):
            warroom.clean_plan({"workers": "nope"}, "/proj")

    def test_draft_plan_parses_structured_output(self):
        plan = {"name": "x", "goal": "g", "workers": [{"name": "p", "role": "project-planner", "brief": "b"}], "tasks": []}
        res = {"type": "result", "is_error": False, "structured_output": plan, "total_cost_usd": 0.02,
               "usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 1000}}
        with mock.patch.object(warroom, "claude", return_value=(0, json.dumps(res) + "\nsome stderr")) as c:
            draft, cost = warroom.draft_plan("build it", "/proj")
        args = c.call_args[0]
        self.assertEqual(args[args.index("--tools") + 1], "")  # no tools: the planner cannot touch anything
        self.assertIn("--no-session-persistence", args)
        self.assertEqual((draft["name"], draft["project"], cost["tokens"]), ("x", "/proj", 1150))
        text = dict(res, structured_output=None, result="Here:\n" + json.dumps(plan))  # older CLIs: JSON in the text
        with mock.patch.object(warroom, "claude", return_value=(0, json.dumps(text))):
            self.assertEqual(warroom.draft_plan("build it", "/proj")[0]["workers"][0]["name"], "p")
        for out in ((1, "boom"), (0, json.dumps(dict(res, is_error=True, result="limit")))):
            with mock.patch.object(warroom, "claude", return_value=out), self.assertRaises(ValueError):
                warroom.draft_plan("build it", "/proj")

    def test_draft_refuses_untrusted_folder_before_spending(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(warroom, "trusted", return_value=False), \
                mock.patch.object(warroom, "claude", side_effect=AssertionError("no tokens for an untrusted folder")):
            with self.assertRaisesRegex(ValueError, "does not trust"):
                warroom.start_draft("make the thing work", d)
            with self.assertRaises(ValueError):
                warroom.start_draft("short", d)

    def test_die_carries_its_message(self):
        with self.assertRaises(warroom.Fatal) as e:
            warroom.die("bad plan")
        self.assertEqual((e.exception.code, e.exception.msg), (2, "bad plan"))

    def test_icon_and_launcher(self):
        import zlib
        png = warroom.icon_png(32)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        raw = zlib.decompress(png[png.index(b"IDAT") + 4:png.index(b"IEND") - 8])
        self.assertEqual(len(raw), 32 * (1 + 32 * 3))
        compile(warroom.launcher_source("/somewhere"), "launcher", "exec")


if __name__ == "__main__":
    unittest.main()
