"""War Room crew workers (codex, gemini, ... driven by the conductor) with a fake crew engine: no agent is called."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warroom  # noqa: E402
from test_app import Sandbox  # noqa: E402

PROFILES = json.load(open(os.path.join(HERE, "profiles.json")))
IDX = {"specialist-council@moaa": "/c", "agent-arena-mode@moaa": "/a"}


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class FakeCrew:
    """Stands in for crew.py: a writer commits a file in its worktree; a reviewer answers with a scripted verdict."""
    def __init__(self, tmp, verdicts):
        self.tmp, self.verdicts, self.calls, self.before = Path(tmp), list(verdicts), [], None

    def load_members(self):
        return {"codex": {}, "gemini": {}}

    def run(self, member, task, cwd=".", write=False, model=None, timeout=1200, run_id=None, workdir=None, on_start=None):
        if on_start:
            on_start(999999)  # a pid no real process has
        if self.before:
            self.before()
        self.calls.append({"member": member, "task": task, "cwd": str(cwd), "write": write, "workdir": workdir})
        answer = self.tmp / f"answer-{len(self.calls)}.md"
        if write:
            (Path(workdir) / f"f{len(self.calls)}.txt").write_text("x\n")
            git(workdir, "add", "-A")
            git(workdir, "commit", "-qm", "crew work")
            answer.write_text("Implemented it.")
            return {"ok": True, "answer": str(answer), "commits": "1", "head": git(workdir, "rev-parse", "HEAD")}
        answer.write_text(self.verdicts.pop(0) if self.verdicts else "Looked fine.")
        return {"ok": True, "answer": str(answer)}


class CrewWorkers(Sandbox):
    def plan(self):
        project = Path(tempfile.mkdtemp()) / "proj"
        project.mkdir()
        git(project, "init", "-q")
        (project / "a.txt").write_text("a\n")
        git(project, "add", "-A")
        git(project, "commit", "-qm", "init")
        return {"name": "t", "goal": "g", "project": str(project), "workers": [
            {"name": "forge", "role": "builder", "engine": "codex", "brief": "build"},
            {"name": "judge", "role": "test-engineer", "engine": "gemini", "brief": "review"}],
            "tasks": [{"title": "Add a feature", "assignee": "forge"}]}

    def setUp(self):
        super().setUp()
        self.fake = FakeCrew(tempfile.mkdtemp(), ['Checked.\nVERDICT {"decision": "pass", "score": 91, "notes": "ok {fine}"}'])
        p = mock.patch.object(warroom, "crew_mod", lambda: self.fake)
        p.start()
        self.addCleanup(p.stop)

    def launch(self):
        resolved = warroom.resolve_plan(self.plan(), PROFILES, IDX, {})
        run = "crewtest"
        warroom.save_json(os.path.join(warroom.RUNS, run, "plan.json"), resolved)
        bus = warroom.open_bus(run)
        bus.control("budget", json.dumps(resolved["budget"]))
        bus.control("run_id", run)
        for t in resolved["tasks"]:
            bus.post_task(t["title"], t.get("detail", ""), t.get("assignee"), t.get("gate", 1))
        for w in resolved["workers"]:
            warroom.launch_crew_worker(bus, w, resolved, run)
        return run, bus, resolved

    def drain(self, bus, run):
        for _ in range(6):  # tick, then wait for the job threads, as the conductor would across ticks
            warroom.crew_tick(bus, run)
            for t in list(warroom.CREW_JOBS.values()):
                t.join(30)

    def test_resolve_marks_engine_workers_and_rejects_unknown_engines(self):
        resolved = warroom.resolve_plan(self.plan(), PROFILES, IDX, {})
        forge = resolved["workers"][0]
        self.assertEqual((forge["model"], forge["engine"], forge["plugin_dirs"], forge["write"]), ("crew:codex", "codex", [], True))
        self.assertFalse(resolved["workers"][1]["write"])
        bad = self.plan()
        bad["workers"][0]["engine"] = "nope"
        with self.assertRaises(SystemExit):
            warroom.resolve_plan(bad, PROFILES, IDX, {})
        self.assertEqual(warroom.clean_plan(self.plan(), "p")["workers"][0]["engine"], "codex")

    def test_build_then_cross_family_review_then_merge_queue(self):
        run, bus, _ = self.launch()
        forge = next(w for w in bus.workers() if w["name"] == "forge")
        self.assertTrue(warroom.is_crew(forge) and os.path.isdir(forge["cwd"]))
        self.drain(bus, run)
        task = bus.db.execute("SELECT * FROM tasks WHERE title='Add a feature'").fetchone()
        self.assertEqual(task["status"], "approved")
        self.assertEqual(task["score"], 91)
        self.assertEqual(bus.db.execute("SELECT COUNT(*) FROM merges").fetchone()[0], 1)
        writer, reviewer = self.fake.calls[0], self.fake.calls[1]
        self.assertEqual((writer["member"], writer["write"], writer["workdir"]), ("codex", True, forge["cwd"]))
        self.assertEqual((reviewer["member"], reviewer["write"], reviewer["cwd"]), ("gemini", False, forge["cwd"]))
        self.assertIn("VERDICT", reviewer["task"])
        st = warroom.state(run)
        self.assertTrue(all(w["status"] == "busy" for w in st["workers"]))  # parked crew workers read as live
        self.assertEqual(warroom.focus_console(run, "forge")["ok"], False)

    def test_reviewer_without_a_verdict_is_retried_once_then_blocked(self):
        self.fake.verdicts = ["no verdict here", "still none"]
        run, bus, _ = self.launch()
        self.drain(bus, run)
        review = bus.db.execute("SELECT * FROM tasks WHERE kind='review'").fetchone()
        self.assertEqual(review["status"], "blocked")
        last = bus.db.execute("SELECT body FROM messages WHERE recipient='orchestrator' ORDER BY id DESC").fetchone()
        self.assertIn("failed twice", last["body"])

    def test_uppercase_verdicts_count_and_a_stop_mid_job_requeues_without_reporting(self):
        self.fake.verdicts = ['VERDICT {"decision": "PASS", "score": 88, "notes": ""}']
        run, bus, _ = self.launch()
        self.drain(bus, run)
        self.assertEqual(bus.db.execute("SELECT status FROM tasks WHERE title='Add a feature'").fetchone()[0], "approved")
        bus.post_task("Second feature", "", "forge")
        self.fake.before = lambda: bus.control("run", "stop")  # the user stops the run while the member works
        warroom.crew_tick(bus, run)
        for t in list(warroom.CREW_JOBS.values()):
            t.join(30)
        row = bus.db.execute("SELECT status, owner FROM tasks WHERE title='Second feature'").fetchone()
        self.assertEqual((row["status"], row["owner"]), ("open", None))
        self.assertIsNone(bus.control("crew_retry_" + str(bus.db.execute("SELECT id FROM tasks WHERE title='Second feature'").fetchone()[0])))

    def test_a_task_held_by_a_dead_job_is_reclaimed_and_its_process_killed(self):
        run, bus, _ = self.launch()
        tid = warroom.bus_as(bus, "forge").claim_task()["task"]["id"]
        bus.control("crew_job_forge", '{"member_pid": 4242, "hint": "codex"}')  # left by a conductor that died
        warroom.CREW_JOBS.pop("forge", None)
        with mock.patch.object(warroom, "kill_pid") as kill, mock.patch.object(warroom, "crew_job"):
            warroom.crew_tick(bus, run)
        kill.assert_called_once_with(4242, must_contain="codex")
        self.assertEqual(bus.db.execute("SELECT owner FROM tasks WHERE id=?", (tid,)).fetchone()[0], "forge")  # re-claimed
        self.assertIsNone(bus.control("crew_job_forge"))

    def test_stop_and_resume_never_touch_claude_sessions(self):
        run, bus, _ = self.launch()
        with mock.patch.object(warroom, "stop_session", side_effect=AssertionError("no session")):
            warroom.stop_all(bus, "test")
        self.assertTrue(all(w["state"] == "stopped" for w in bus.workers()))
        bus.control("run", clear=True)
        with mock.patch.object(warroom, "start_session", side_effect=AssertionError("no session")):
            self.assertEqual(warroom.resume_all(bus), [])


if __name__ == "__main__":
    unittest.main()
