"""Team board tests with a real bare remote and two clones: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import team  # noqa: E402

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_NOSYSTEM": "1"}


def sh(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, env={**os.environ, **ENV})


class Team(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {"TEAM_BOARD": "", "HOME": str(self.root), "USERPROFILE": str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        sh("init", "-q", "--bare", "remote.git", cwd=self.root)
        sh("clone", "-q", "remote.git", "alice", cwd=self.root)
        (self.root / "alice" / "README.md").write_text("# project\n", encoding="utf-8")
        sh("add", "-A", cwd=self.root / "alice")
        sh("commit", "-q", "-m", "first", cwd=self.root / "alice")
        sh("push", "-q", "origin", "HEAD", cwd=self.root / "alice")
        sh("clone", "-q", "remote.git", "bob", cwd=self.root)
        self.alice, self.bob = self.root / "alice", self.root / "bob"
        team.cmd_init(self.alice, "", "team-board")
        team.cmd_join(self.alice, "alice", "lead", "evenings")
        out = team.cmd_init(self.bob, "", "team-board")
        self.assertTrue(out["joined_existing"])
        team.cmd_join(self.bob, "bob", "", "")

    def board(self, who):
        cfg, wt, common = team.setup(who)
        team.refresh(cfg, wt, common)
        return team.Board(wt)

    def test_board_branch_never_touches_working_files(self):
        self.assertEqual(sorted(p.name for p in self.alice.iterdir() if p.name != ".git"), ["README.md"])
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.alice, capture_output=True, text=True)
        self.assertEqual(status.stdout, "")
        self.assertEqual({m["name"] for m in self.board(self.bob).members()}, {"alice", "bob"})

    def test_a_task_is_claimed_once_even_in_a_push_race(self):
        tid = team.cmd_add(self.alice, "Write the parser", "", [], [], None)["added"]
        real = team.refresh
        raced = {"done": False}

        def race(cfg, wt, common, timeout=60):  # alice claims right after bob fetched, before bob pushes
            real(cfg, wt, common, timeout)
            if cfg.get("name") == "bob" and not raced["done"]:
                raced["done"] = True
                with mock.patch.object(team, "refresh", real):
                    team.cmd_claim(self.alice, tid)
        with mock.patch.object(team, "refresh", race):
            with self.assertRaises(team.TeamError) as e:
                team.cmd_claim(self.bob, tid)
        self.assertIn("claimed by alice", str(e.exception))
        t = self.board(self.bob).task(tid)
        self.assertEqual((t["status"], t["owner"]), ("claimed", "alice"))

    def test_next_free_task_respects_dependencies_assignment_and_path_locks(self):
        a = team.cmd_add(self.alice, "Schema", "", ["src/db"], [], None)["added"]
        b = team.cmd_add(self.alice, "Migrations", "", [], [a], None)["added"]
        c = team.cmd_add(self.alice, "Index tuning", "", ["src/db/index.py"], [], None)["added"]
        d = team.cmd_add(self.alice, "Docs", "", ["docs"], [], "bob")["added"]
        self.assertEqual(team.cmd_claim(self.alice)["claimed"], a)  # d is for bob, b waits for a
        self.assertEqual(team.cmd_claim(self.bob)["claimed"], d)  # assigned to bob comes first
        with self.assertRaises(team.TeamError) as e:
            team.cmd_claim(self.bob, c)
        self.assertIn("alice holds src/db", str(e.exception))
        with self.assertRaises(team.TeamError):
            team.cmd_claim(self.bob, b)
        team.cmd_update(self.alice, a, "done", "merged in #12")
        self.assertEqual(team.cmd_claim(self.bob)["claimed"], b)

    def test_stale_claims_can_be_taken_over_and_others_cannot_edit_a_task(self):
        tid = team.cmd_add(self.alice, "Flaky test", "", [], [], None)["added"]
        team.cmd_claim(self.alice, tid)
        with self.assertRaises(team.TeamError):
            team.cmd_update(self.bob, tid, "done", "")
        team.cmd_update(self.bob, tid, "blocked", "CI is down")  # anyone may flag a blocker
        team.cmd_update(self.alice, tid, "claimed", "back on it")
        with mock.patch.object(team.time, "time", return_value=time.time() + team.LEASE + 60):
            out = team.cmd_claim(self.bob, tid)
        self.assertEqual(out["claimed"], tid)
        self.assertIn("took over a stale claim", [x["what"] for x in self.board(self.alice).task(tid)["log"]])

    def test_handoff_reopens_with_notes_for_the_next_member(self):
        tid = team.cmd_add(self.alice, "Port the solver", "", [], [], None)["added"]
        team.cmd_claim(self.alice, tid)
        team.cmd_handoff(self.alice, tid, "Half done on branch team/x; next: boundary conditions.")
        out = team.cmd_claim(self.bob, tid)
        self.assertEqual(out["handoffs"][0]["from"], "alice")
        self.assertIn("boundary conditions", out["handoffs"][0]["text"])
        self.assertTrue(out["branch"].startswith(f"team/{tid}-port-the-solver"))

    def test_messages_inbox_and_notes(self):
        team.cmd_send(self.alice, "bob", "Please review PR 7")
        team.cmd_send(self.alice, "all", "Freeze on Friday")
        with self.assertRaises(team.TeamError):
            team.cmd_send(self.alice, "carol", "hi")
        self.assertEqual([m["text"] for m in team.cmd_inbox(self.bob)], ["Please review PR 7", "Freeze on Friday"])
        self.assertEqual(team.cmd_inbox(self.bob), [])  # read
        self.assertEqual(len(team.cmd_inbox(self.bob, show_all=True)), 2)
        self.assertEqual(team.cmd_inbox(self.alice), [])  # own messages are not in one's inbox
        team.cmd_note(self.bob, "We use SI units in every output file.")
        self.assertIn("SI units", self.board(self.alice).notes()[-1]["text"])

    def test_hooks_summarize_then_announce_only_new_items(self):
        team.cmd_add(self.alice, "Fix the mesh", "", [], [], "bob")
        team.cmd_send(self.alice, "bob", "Mesh first, please")
        start = json.loads(team.hook("session-start", json.dumps({"cwd": str(self.bob)})))
        text = start["hookSpecificOutput"]["additionalContext"]
        self.assertIn("you are bob", text)
        self.assertIn("Fix the mesh (assigned to you)", text)
        self.assertIn("Mesh first, please", text)
        self.assertIn("not from your user", text)
        with mock.patch.object(team, "spawn"):
            self.assertEqual(team.hook("prompt", json.dumps({"cwd": str(self.bob), "prompt": "go"})), "")
            team.cmd_send(self.alice, "bob", "Also the solver")
            cfg, wt, common = team.setup(self.bob)
            team.refresh(cfg, wt, common)  # what the background sync does
            out = json.loads(team.hook("prompt", json.dumps({"cwd": str(self.bob), "prompt": "go"})))
        self.assertIn("Also the solver", out["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("Mesh first", out["hookSpecificOutput"]["additionalContext"])

    def test_off_switches_and_repositories_without_a_board(self):
        with mock.patch.dict(os.environ, {"TEAM_BOARD": "off"}):
            self.assertEqual(team.hook("session-start", json.dumps({"cwd": str(self.bob)})), "")
        cfg, _, common = team.setup(self.bob)
        cfg["on"] = False
        team.save_local(common, cfg)
        self.assertEqual(team.hook("session-start", json.dumps({"cwd": str(self.bob)})), "")
        self.assertEqual(team.hook("session-start", json.dumps({"cwd": str(self.root)})), "")  # not a repository
        plain = self.root / "plain"
        sh("init", "-q", str(plain), cwd=self.root)
        self.assertEqual(team.hook("session-start", json.dumps({"cwd": str(plain)})), "")

    def test_names_and_local_only_boards(self):
        with self.assertRaises(team.TeamError):
            team.cmd_join(self.alice, "Alice Smith", "", "")
        solo = self.root / "solo"
        sh("init", "-q", str(solo), cwd=self.root)  # no commits and no remote
        out = team.cmd_init(solo, "", "team-board")
        self.assertIsNone(out["remote"])
        team.cmd_join(solo, "me", "", "")
        tid = team.cmd_add(solo, "Local task", "", [], [], None)["added"]
        self.assertEqual(team.cmd_claim(solo)["claimed"], tid)


if __name__ == "__main__":
    unittest.main()
