"""Review gates, arbitration, human decisions and the merge queue (real git, temp repo). Stdlib only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import warroom  # noqa: E402
from bus import Bus  # noqa: E402


def board(db):
    return {t["id"]: t for t in Bus(db, "x").board()["tasks"]}


class Gates(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "bus.sqlite3")
        o = Bus(self.db, "orchestrator")
        o.control("budget", json.dumps({"gates": True, "gate_score": 85, "max_fails": 2}))
        for name, kind, model, role in (("builder", "builder", "claude-haiku-5-5", "builder"),
                                        ("rev", "reviewer", "claude-sonnet-5-5", "challenger"),
                                        ("rev2", "reviewer", "claude-haiku-5-5", "test-engineer"),
                                        ("arb", "reviewer", "claude-opus-5-5", "arbiter")):
            o.put_worker(name=name, role=role, kind=kind, model=model, effort="low", session_id=name, cwd=f"/wt/{name}",
                         argv="[]", resume_argv=None, state="running")
        self.o, self.b, self.r, self.a = o, Bus(self.db, "builder"), Bus(self.db, "rev"), Bus(self.db, "arb")
        self.tid = o.post_task("build x")["id"]

    def submit(self, commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"):
        self.assertEqual(self.b.claim_task()["task"]["id"], self.tid)
        return self.b.complete_task(self.tid, "built x", commit=commit)

    def review(self, who, decision, score):
        rid = who.claim_task()["task"]["id"]
        return who.verdict(rid, decision, score, f"{decision} notes")

    def test_writer_must_commit_and_reviewer_differs_in_tier(self):
        self.b.claim_task()
        self.assertFalse(self.b.complete_task(self.tid, "built")["ok"])  # no commit hash
        self.assertFalse(self.b.complete_task(self.tid, "built", commit="main")["ok"])  # a moving ref is refused
        self.assertFalse(self.b.complete_task(self.tid, "built", commit="abc1234")["ok"])  # so is a short hash
        out = self.b.complete_task(self.tid, "built", commit="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        self.assertEqual(out["status"], "review")
        self.assertEqual(out["reviewer"], "rev")  # sonnet reviewer preferred over haiku (author's tier), not the arbiter
        self.assertEqual(board(self.db)[self.tid]["status"], "review")

    def test_pass_approves_and_queues_merge(self):
        self.submit()
        self.assertEqual(self.review(self.r, "pass", 92)["outcome"], "approved")
        self.assertEqual(board(self.db)[self.tid]["status"], "approved")
        q = self.o.db.execute("SELECT task_id, commit_ref, status FROM merges").fetchall()
        self.assertEqual([tuple(x) for x in q], [(self.tid, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "queued")])

    def test_low_score_pass_counts_as_fail_and_reopens_for_author(self):
        self.submit()
        self.assertEqual(self.review(self.r, "pass", 70)["outcome"], "reopened")
        t = board(self.db)[self.tid]
        self.assertEqual((t["status"], t["assignee"]), ("open", "builder"))
        self.assertIn("Review failed", self.b.inbox()["messages"][0]["body"])
        self.assertEqual(self.b.complete_task(self.tid, "fixed", commit="cccccccccccccccccccccccccccccccccccccccc")["status"], "review")  # no re-claim needed

    def test_two_fails_go_to_arbiter_then_human(self):
        self.submit()
        self.review(self.r, "fail", 40)
        self.submit("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        self.assertEqual(self.review(self.r, "fail", 50)["outcome"], "arbitration")
        arb_task = self.a.claim_task()["task"]
        self.assertTrue(arb_task["title"].startswith("Arbitrate"))
        self.assertEqual(self.a.verdict(arb_task["id"], "fail", 30, "still wrong")["outcome"], "blocked")
        self.assertEqual(board(self.db)[self.tid]["status"], "blocked")
        self.assertIn("needs your decision", self.o.inbox()["messages"][-1]["body"])
        self.o.decide(self.tid, approve=True)
        self.assertEqual(board(self.db)[self.tid]["status"], "approved")

    def test_no_self_review_and_ungated_tasks(self):
        self.o.put_worker(name="solo", role="builder", kind="builder", model="claude-haiku-5-5", effort="low",
                          session_id="s", cwd="/wt/s", argv="[]", resume_argv=None, state="running")
        t2 = self.o.post_task("notes only", gate=0)["id"]
        self.o.db.execute("UPDATE tasks SET status='claimed', owner='solo' WHERE id=?", (t2,))
        self.assertEqual(Bus(self.db, "solo").complete_task(t2, "noted")["status"], "done")
        self.submit()
        rid = self.r.claim_task()["task"]["id"]
        self.o.db.execute("UPDATE tasks SET owner='builder' WHERE id=?", (rid,))
        self.assertFalse(self.b.verdict(rid, "pass", 99)["ok"])  # the author cannot pass their own work

    def test_reviewed_non_code_task_is_done_not_stuck(self):
        self.o.put_worker(name="writer", role="technical-documentarian", kind="planner", model="claude-haiku-5-5",
                          effort="low", session_id="w", cwd="/x", argv="[]", resume_argv=None, state="running")
        t = self.o.post_task("write notes")["id"]
        self.o.db.execute("UPDATE tasks SET status='claimed', owner='writer' WHERE id=?", (t,))
        self.assertEqual(Bus(self.db, "writer").complete_task(t, "notes")["status"], "review")
        rid = self.r.claim_task()["task"]["id"]
        self.assertEqual(self.r.verdict(rid, "pass", 90, "fine")["outcome"], "approved")
        self.assertEqual(board(self.db)[t]["status"], "done")  # nothing to merge, so it must not wait for the queue
        self.assertEqual(self.o.db.execute("SELECT COUNT(*) FROM merges").fetchone()[0], 0)

    def test_builders_cannot_post_ungated_work(self):
        t = self.b.post_task("sneaky", gate=0)["id"]
        self.assertEqual(self.o.db.execute("SELECT gate FROM tasks WHERE id=?", (t,)).fetchone()[0], 1)

    def test_no_reviewer_falls_back_to_human(self):
        self.o.db.execute("DELETE FROM workers WHERE kind='reviewer'")
        self.assertEqual(self.submit()["reviewer"], "orchestrator")


class MergeQueue(unittest.TestCase):
    def git(self, *a, cwd=None):
        return subprocess.run(["git", "-C", cwd or self.repo, "-c", "user.name=t", "-c", "user.email=t@localhost", *a],
                              capture_output=True, text=True, check=True).stdout.strip()

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.git("init", "-q", "-b", "main")
        Path(os.path.join(self.repo, "a.txt")).write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.db = os.path.join(tempfile.mkdtemp(), "bus.sqlite3")
        self.bus = Bus(self.db, "orchestrator")
        resolved = {"project": self.repo, "worktrees": os.path.join(self.repo, ".claude", "worktrees")}
        self.bus.control("worktrees", resolved["worktrees"])
        self.integ = warroom.setup_integration(self.bus, resolved, "t-20261012-000001",
                                               base=self.git("rev-parse", "HEAD"))
        self.wt = os.path.join(self.repo, ".claude", "worktrees", "w1")
        self.git("worktree", "add", "-q", "-b", "w1", self.wt)

    def commit(self, name, text):
        Path(os.path.join(self.wt, name)).write_text(text)
        self.git("add", ".", cwd=self.wt)
        self.git("commit", "-qm", f"edit {name}", cwd=self.wt)
        return self.git("rev-parse", "HEAD", cwd=self.wt)

    def queue(self, sha):
        tid = self.bus.post_task("t")["id"]
        self.bus.db.execute("UPDATE tasks SET status='approved', author='w1', commit_ref=? WHERE id=?", (sha, tid))
        self.bus.db.execute("INSERT INTO merges(task_id, worker, commit_ref) VALUES (?,?,?)", (tid, "w1", sha))
        return tid

    def test_merge_then_conflict_reopens(self):
        tid = self.queue(self.commit("b.txt", "new\n"))
        self.assertEqual(warroom.process_merges(self.bus), 1)
        self.assertEqual(board(self.db)[tid]["status"], "merged")
        self.assertTrue(os.path.exists(os.path.join(self.integ["path"], "b.txt")))
        # a conflicting change: integration edits a.txt one way, the worker another way
        Path(os.path.join(self.integ["path"], "a.txt")).write_text("integration side\n")
        self.git("commit", "-qam", "integration edit", cwd=self.integ["path"])
        tid2 = self.queue(self.commit("a.txt", "worker side\n"))
        self.assertEqual(warroom.process_merges(self.bus), 0)
        t = board(self.db)[tid2]
        self.assertEqual((t["status"], t["assignee"]), ("open", "w1"))
        self.assertEqual(self.git("status", "--porcelain", cwd=self.integ["path"]), "")  # merge aborted cleanly
        self.assertIn("git merge war-room/", Bus(self.db, "w1").inbox()["messages"][0]["body"])
        bad = self.queue("0" * 40)
        warroom.process_merges(self.bus)
        self.assertEqual(board(self.db)[bad]["status"], "open")  # unknown commit is sent back, not merged


class Finish(MergeQueue):
    def test_complete_cleanup_integrate(self):
        self.bus.control("project", self.repo)
        self.bus.control("run_id", "t-20261012-000001")
        self.bus.put_worker(name="w1", role="builder", kind="builder", model="claude-haiku-5-5", effort="low",
                            session_id="s1", cwd=self.wt, argv="[]", resume_argv=None, state="running")
        tid = self.queue(self.commit("b.txt", "new" + chr(10)))
        Bus(self.db, "w1").heartbeat("working: Edit")
        self.assertFalse(warroom.is_complete(self.bus))  # approved, not merged yet; worker busy
        warroom.process_merges(self.bus)
        self.assertFalse(warroom.is_complete(self.bus))  # worker still working
        Bus(self.db, "w1").heartbeat("parked: waiting for inbox")
        self.assertTrue(warroom.is_complete(self.bus))
        self.assertIn(f"#{tid} merged", warroom.integration_report(self.bus))
        removed, kept = warroom.cleanup_worktrees(self.bus)
        self.assertEqual(kept, [])
        self.assertFalse(os.path.exists(self.wt))                      # merged writer worktree removed
        self.assertFalse(os.path.exists(self.integ["path"]))           # integration worktree removed ...
        self.assertIn(self.integ["branch"], self.git("branch", "--list", "war-room/*"))  # ... its branch kept
        self.assertEqual(self.git("branch", "--list", "w1"), "")       # fully merged writer branch deleted
        Path(self.repo, "a.txt").write_text("dirty" + chr(10))
        self.assertFalse(warroom.integrate_into_project(self.bus)["ok"])  # refuses a dirty project
        self.git("checkout", "--", "a.txt")
        out = warroom.integrate_into_project(self.bus)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["target"], "main")
        self.assertTrue(Path(self.repo, "b.txt").exists())

    def test_project_checkout_is_never_removed(self):
        self.bus.control("project", self.repo)
        self.bus.put_worker(name="w0", role="builder", kind="builder", model="m", effort="low",
                            session_id="s0", cwd=self.repo, argv="[]", resume_argv=None, state="running")
        warroom.cleanup_worktrees(self.bus)
        self.assertTrue(os.path.isdir(os.path.join(self.repo, ".git")))

    def test_merge_queue_defers_on_git_trouble(self):
        tid = self.queue(self.commit("d.txt", "x" + chr(10)))
        Path(self.integ["path"], ".git").exists()  # linked worktree: .git is a file pointing at the real gitdir
        gitdir = self.git("rev-parse", "--git-dir", cwd=self.integ["path"])
        lock = Path(self.integ["path"], gitdir, "index.lock") if not os.path.isabs(gitdir) else Path(gitdir, "index.lock")
        lock.write_text("")
        self.assertEqual(warroom.process_merges(self.bus), 0)
        self.assertEqual(board(self.db)[tid]["status"], "approved")  # not reopened, not blamed on the author
        self.assertEqual(self.bus.db.execute("SELECT status FROM merges").fetchone()[0], "queued")
        lock.unlink()
        self.assertEqual(warroom.process_merges(self.bus), 1)  # next tick it merges

    def test_unmerged_worktree_is_kept(self):
        self.bus.control("project", self.repo)
        self.bus.put_worker(name="w1", role="builder", kind="builder", model="m", effort="low",
                            session_id="s1", cwd=self.wt, argv="[]", resume_argv=None, state="running")
        self.commit("c.txt", "never reviewed" + chr(10))
        removed, kept = warroom.cleanup_worktrees(self.bus)
        self.assertTrue(os.path.exists(self.wt))
        self.assertIn("commits not merged", kept[0])


class Layout(unittest.TestCase):
    def test_layout_and_tmux(self):
        app, cells = warroom.layout(3, (0, 0, 1920, 1032), True)
        self.assertEqual(app, (0, 0, 1075, 1032))
        self.assertEqual(cells[0][0], 1075)
        self.assertEqual(warroom.layout(2, (0, 0, 100, 100), False)[0], None)
        plan = warroom.tmux_plan("wr-x", ["aaaa1111", "bbbb2222"], exists=False)
        self.assertEqual(plan[0][:5], ["tmux", "new-session", "-d", "-s", "wr-x"])
        self.assertEqual(plan[-1], ["tmux", "select-layout", "-t", "wr-x", "tiled"])
        self.assertEqual(warroom.tmux_plan("wr-x", ["c"], exists=True)[0][1], "split-window")

    def test_calibration(self):
        self.assertEqual(warroom.per_worker_task({}), (warroom.DEFAULT_PER_WORKER_TASK, 0))
        cal = {"runs": {"a": {"per_worker_task": 300_000}, "b": {"per_worker_task": 500_000},
                        "c": {"per_worker_task": 900_000}}}
        self.assertEqual(warroom.per_worker_task(cal), (500_000, 3))
        lo, hi = warroom.estimate([{"plugins": ["x"]}], 1, per_task=500_000)
        self.assertEqual((lo, hi), (int((50_000 + 2 * 500_000) * 0.6), int((50_000 + 2 * 500_000) * 1.6)))


if __name__ == "__main__":
    unittest.main()
