"""Unit tests for War Room logic that needs no live claude. Run: python -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import warroom  # noqa: E402
from bus import Bus  # noqa: E402

PROFILES = json.load(open(os.path.join(HERE, "profiles.json")))
BUDGET = {"pause_at": 85, "stop_at": 95, "max_hours": 4}


class Policy(unittest.TestCase):
    def test_thresholds(self):
        d = warroom.decide
        self.assertIsNone(d(40, BUDGET, False, False, False))
        self.assertEqual(d(86, BUDGET, False, False, False), "pause")
        self.assertIsNone(d(88, BUDGET, True, False, False))          # already paused
        self.assertEqual(d(95, BUDGET, True, False, False), "stop")
        self.assertEqual(d(10, BUDGET, False, False, True), "stop")    # limit text seen in a transcript
        self.assertEqual(d(70, BUDGET, True, False, False), "unpause")  # hysteresis: 10 points below pause_at
        self.assertIsNone(d(80, BUDGET, True, False, False))
        self.assertIsNone(d(10, BUDGET, True, False, False, paused_by_guard=False))  # a manual pause stays
        self.assertIsNone(d(99, BUDGET, False, True, True))            # already stopped
        self.assertIsNone(d(None, BUDGET, False, False, False))        # meter unknown

    def test_limit_regex(self):
        self.assertTrue(warroom.LIMIT_RE.search("You've hit your session limit · resets 3:45pm"))
        self.assertTrue(warroom.LIMIT_RE.search("You've hit your Opus limit · resets Mon"))
        self.assertFalse(warroom.LIMIT_RE.search("rate limits are fine"))


class Argv(unittest.TestCase):
    def worker(self, write):
        return {"name": "b1", "role": "builder", "model": "claude-sonnet-5-5", "effort": "medium", "write": write,
                "brief": "", "plugin_dirs": ["/p/council", "/p/arena"], "permission_mode": "dontAsk"}

    def test_build_and_resume(self):
        resolved = {"goal": "g", "project": "/proj", "workers": [self.worker(True), {"name": "r1"}]}
        argv = warroom.build_argv(self.worker(True), resolved, "demo-20261012-010203", "/w")
        self.assertEqual(argv[0], "--bg")
        self.assertEqual(argv.count("--plugin-dir"), 2)
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "project,local")
        self.assertEqual(argv[argv.index("--worktree") + 1], warroom.worktree_name("demo-20261012-010203", {"name": "b1"}))
        self.assertNotEqual(warroom.run_tag("a-20261012-010203"), warroom.run_tag("b-20261013-010203"))  # same time, different run
        self.assertIn("r1", argv[argv.index("--append-system-prompt") + 1])
        res = warroom.resume_argv(argv, "sid-123", "go on")
        self.assertNotIn("--worktree", res)
        self.assertNotIn("Begin: call claim_task.", res)
        self.assertEqual(res[-4:], ["--resume", "sid-123", "--", "go on"])
        self.assertEqual(argv[-2], "--")  # the prompt can't be swallowed by a variadic flag
        self.assertEqual(res.count("--"), 1)
        self.assertIn("--mcp-config", res)  # launch flags are replayed on resume

    def test_reader_gets_worktree_access(self):
        resolved = {"goal": "g", "project": "/proj", "worktrees": "/main/.claude/worktrees", "workers": [self.worker(False)]}
        argv = warroom.build_argv(self.worker(False), resolved, "run-1", "/w")
        self.assertNotIn("--worktree", argv)
        self.assertEqual(argv[argv.index("--add-dir") + 1], "/main/.claude/worktrees")
        self.assertEqual(argv[argv.index("--add-dir") + 2], "--")

    def test_parse_bg_id(self):
        self.assertEqual(warroom.parse_bg_id("backgrounded · ba9eedb9 · wr-x\n  claude agents"), "ba9eedb9")
        self.assertEqual(warroom.parse_bg_id("note: session f0583003 is already running in the background, so this "
                                             "started a copy as bef42f7c.\nbackgrounded · bef42f7c"), "bef42f7c")
        self.assertIsNone(warroom.parse_bg_id("error: nope"))


class Plan(unittest.TestCase):
    def test_curation(self):
        plan = {"name": "t", "goal": "g", "project": ".", "workers": [
            {"name": "planner", "role": "project-planner", "model": "haiku", "effort": "low"},
            {"name": "builder", "role": "builder", "model": "sonnet", "effort": "medium", "tags": ["fem"]},
            {"name": "reviewer", "role": "challenger", "model": "opus", "effort": "high"}]}
        idx = {"specialist-council@moaa": "/c", "agent-arena-mode@moaa": "/a"}
        r = warroom.resolve_plan(plan, PROFILES, idx, {"ansys": {"command": "x"}})
        by = {w["name"]: w for w in r["workers"]}
        self.assertEqual(by["planner"]["kind"], "planner")
        self.assertFalse(by["planner"]["write"])
        self.assertTrue(by["builder"]["write"])
        self.assertEqual(by["builder"]["mcp"], ["ansys"])
        self.assertEqual(by["reviewer"]["plugin_dirs"], ["/c", "/a"])  # reviewers get the arena, others don't
        self.assertNotIn("/a", by["builder"]["plugin_dirs"])
        self.assertIn("Bash(git push*)", by["builder"]["deny"])
        lo, hi = warroom.estimate(r["workers"], 3)
        self.assertLess(lo, hi)

    def test_rejects_bad_plans(self):
        idx = {"specialist-council@moaa": "/c", "agent-arena-mode@moaa": "/a"}
        w = {"role": "builder", "model": "haiku", "effort": "low"}
        for workers in ([], [dict(w, name="Bad Name")], [dict(w, name="a"), dict(w, name="a")],
                        [dict(w, name=f"w{i}") for i in range(4)],  # over default max_workers=3
                        [dict(w, name="x", plugins=["missing@nowhere"])]):
            with self.assertRaises(SystemExit):
                warroom.resolve_plan({"workers": workers}, PROFILES, idx, {})


class Templates(unittest.TestCase):
    def test_every_template_resolves_with_real_roles(self):
        council = json.load(open(os.path.join(os.path.dirname(HERE), "specialist-council", "profile.json"), encoding="utf-8"))
        idx = {"specialist-council@moaa": "/c", "agent-arena-mode@moaa": "/a"}
        for name in warroom.TEMPLATES:
            with self.subTest(template=name):
                plan = warroom.clean_plan(warroom.template_plan(name, ".", "goal"), ".")
                roles = {w["role"]: {"tier": "sonnet", "effort": "medium"} for w in plan["workers"]}
                self.assertTrue(set(roles) <= set(council["roles"]), set(roles) - set(council["roles"]))
                r = warroom.resolve_plan(plan, PROFILES, idx, {}, role_models=roles)
                names = {w["name"] for w in r["workers"]}
                self.assertTrue(all(t["assignee"] in names for t in plan["tasks"]))
                if any(w["write"] for w in r["workers"]):  # whenever a worker writes, someone reviews
                    self.assertTrue(any(w["kind"] == "reviewer" for w in r["workers"]))
        with self.assertRaises(SystemExit):
            warroom.template_plan("nope")


class Hooks(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "bus.sqlite3")
        self.env = dict(os.environ, WARROOM_DB=self.db, WARROOM_AGENT="w1", WARROOM_WAIT="3")
        self.orch = Bus(self.db, "orchestrator")

    def hook(self, event, data=None):
        p = subprocess.run([sys.executable, os.path.join(HERE, "hooks.py"), event], input=json.dumps(data or {}),
                           capture_output=True, text=True, env=self.env, timeout=30)
        return p.stdout.strip()

    def test_stop_hook(self):
        self.assertEqual(self.hook("stop"), "")  # nothing waiting: allowed to stop after WARROOM_WAIT
        self.assertTrue(self.orch.db.execute("SELECT note FROM heartbeats").fetchone()[0].startswith("idle"))
        self.orch.send("w1", "please review #2")
        out = json.loads(self.hook("stop"))
        self.assertEqual(out["decision"], "block")
        self.assertIn("please review #2", out["reason"])
        self.orch.post_task("x", assignee="w2")  # someone else's task does not wake w1
        self.assertEqual(self.hook("stop"), "")
        self.orch.post_task("y")
        self.assertIn("claim_task", json.loads(self.hook("stop"))["reason"])
        self.orch.control("claims", "paused")  # paused claims: open tasks no longer wake it
        self.assertEqual(self.hook("stop"), "")
        self.orch.control("run", "stop")
        self.orch.send("w1", "late")
        self.assertEqual(self.hook("stop"), "")

    def test_statusline_and_sessionstart(self):
        line = self.hook("statusline", {"rate_limits": {"five_hour": {"used_percentage": 42, "resets_at": 1},
                                                        "seven_day": {"used_percentage": 7}}, "transcript_path": "/t"})
        self.assertIn("5h 42%", line)
        row = self.orch.db.execute("SELECT five_pct, week_pct, transcript FROM meter WHERE agent='w1'").fetchone()
        self.assertEqual(tuple(row), (42, 7, "/t"))
        self.assertEqual(self.hook("sessionstart", {"source": "resume"}), "")  # nothing to restore yet
        Bus(self.db, "w1").checkpoint("did A, next B")
        ctx = json.loads(self.hook("sessionstart", {"source": "resume"}))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("did A, next B", ctx)

    def test_pause_blocks_claims(self):
        self.orch.post_task("t")
        self.orch.control("claims", "paused")
        self.assertTrue(Bus(self.db, "w1").claim_task()["paused"])


class Paths(unittest.TestCase):
    def test_transcript_slug(self):
        p = warroom.transcript_path(r"D:\work\My Repo\.claude\worktrees\x", "abc")
        self.assertTrue(p.replace("\\", "/").endswith("projects/D--work-My-Repo--claude-worktrees-x/abc.jsonl"))


class Robustness(unittest.TestCase):
    def test_estimate_spans_measured_runs(self):
        lo, hi = warroom.estimate([{"plugins": []}], 1, spread=[300_000, 400_000])
        self.assertEqual((lo, hi), (int(42_000 + 2 * 300_000 * .9), int(42_000 + 2 * 400_000 * 1.25)))

    def test_limit_only_counts_new_text(self):
        p = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("You've hit your session limit · resets 3pm" + chr(10))
        self.assertTrue(warroom.limit_in_transcript(p))
        self.assertFalse(warroom.limit_in_transcript(p, os.path.getsize(p)))  # already acted on

    def test_sessions_failure_keeps_last_list(self):
        old = warroom.claude
        warroom._agents_cache.update(t=0, v=[{"sessionId": "x", "status": "busy"}], ok=True)
        warroom.claude = lambda *a, **k: (1, "boom")
        try:
            self.assertEqual(warroom.sessions(0), [{"sessionId": "x", "status": "busy"}])
            self.assertFalse(warroom.sessions_ok())
            self.assertFalse(warroom.stop_session("x", timeout=1))  # never "stopped" on a failed listing
        finally:
            warroom.claude = old
            warroom._agents_cache.update(t=0, v=[], ok=False)

    def test_stop_hook_keeps_messages_until_delivered(self):
        db = os.path.join(tempfile.mkdtemp(), "bus.sqlite3")
        Bus(db, "o").send("w1", "hello")
        w = Bus(db, "w1")
        self.assertEqual([m["body"] for m in w.peek_inbox()], ["hello"])
        self.assertEqual(len(w.peek_inbox()), 1)  # peeking does not consume
        w.mark_read([m["id"] for m in w.peek_inbox()])
        self.assertEqual(w.peek_inbox(), [])


class Grid(unittest.TestCase):
    def test_grid(self):
        cells = warroom.grid(5, (0, 0, 1920, 1032))
        self.assertEqual(len(cells), 5)
        self.assertEqual(cells[0], (0, 0, 640, 516))
        self.assertEqual(cells[3], (0, 516, 960, 516))   # last row of 2 stretches across the width
        self.assertEqual(cells[4], (960, 516, 960, 516))
        self.assertEqual(warroom.grid(1, (0, 0, 1920, 1032)), [(0, 0, 1920, 1032)])


if __name__ == "__main__":
    unittest.main()
