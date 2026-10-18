"""App UI plumbing: shared assets, the task inspector's diff stat, deciding a human gate from the app, ally workers in the
demo. Run: python -m unittest discover -s tests"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import warroom  # noqa: E402


class Sandbox(unittest.TestCase):
    """Points War Room's data folder at a temp dir so nothing touches ~/.claude/war-room."""
    def setUp(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        patches = {"HOME": home, "RUNS": os.path.join(home, "runs"), "CONFIG": os.path.join(home, "config.json"),
                   "CALIBRATION": os.path.join(home, "calibration.json"), "USER_PROFILES": os.path.join(home, "profiles.json"),
                   "HUB": os.path.join(home, "hub.json")}
        for k, v in patches.items():
            p = mock.patch.object(warroom, k, v)
            p.start()
            self.addCleanup(p.stop)


class DemoAllies(Sandbox):
    def test_demo_team_mixes_claude_and_allies(self):
        run = warroom.make_demo(drive=False)
        models = {w["name"]: w["model"] for w in warroom.state(run)["workers"]}
        self.assertEqual((models["forge"], models["judge"]), ("ally:codex", "ally:gemini"))
        self.assertTrue(all(warroom.is_ally(w) == w["model"].startswith("ally:") for w in warroom.open_bus(run).workers()))


class TaskDiff(Sandbox):
    def test_demo_task_has_no_diff(self):
        run = warroom.make_demo(drive=False)
        bus = warroom.open_bus(run)
        tid = bus.post_task("thing", "", "forge")["id"]
        bus.db.execute("UPDATE tasks SET commit_ref=? WHERE id=?", ("a" * 40, tid))
        self.assertEqual(warroom.task_diff(run, tid), {"commit": "a" * 40, "files": None})
        with self.assertRaises(KeyError):
            warroom.task_diff(run, 999)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_real_commit_gives_numstat(self):
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo, True)
        g = lambda *a: subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", *a],  # noqa: E731
                                      check=True, capture_output=True, text=True).stdout.strip()
        g("init", "-q")
        with open(os.path.join(repo, "a.py"), "w") as f:
            f.write("x = 1\ny = 2\n")
        g("add", "a.py")
        g("commit", "-q", "-m", "add a")
        head = g("rev-parse", "HEAD")
        run = warroom.make_demo(drive=False)
        bus = warroom.open_bus(run)
        bus.control("demo", clear=True)
        bus.control("integration", json.dumps({"path": repo, "branch": "war-room/x", "base": head}))
        tid = bus.post_task("thing", "", "forge")["id"]
        bus.db.execute("UPDATE tasks SET commit_ref=? WHERE id=?", (head, tid))
        out = warroom.task_diff(run, tid)
        self.assertEqual(out["subject"], "add a")
        self.assertEqual(out["files"], [{"add": 2, "del": 0, "path": "a.py"}])


class Hub(Sandbox):
    """The hub over HTTP: shared assets, the token on POST, and deciding a human gate."""
    def setUp(self):
        super().setUp()
        threading.Thread(target=warroom.cmd_hub, args=(argparse.Namespace(port=0),), daemon=True).start()
        port = None
        for _ in range(100):
            try:
                with open(warroom.HUB, encoding="utf-8") as f:
                    port = json.load(f)["port"]
                break
            except (OSError, ValueError):
                time.sleep(.05)
        self.base = f"http://127.0.0.1:{port}"
        self.token = re.search(r'const TOKEN = "([^"]+)"', self.get("/").decode()).group(1)

    def get(self, path):
        return urllib.request.urlopen(self.base + path, timeout=10).read()

    def post(self, path, body, token=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"X-War-Room-Token": token or self.token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read() or b"{}")

    def test_pages_load_the_shared_assets(self):
        for page in ("/", "/history"):
            html = self.get(page).decode()
            self.assertIn('href="/ui.css"', html)
            self.assertIn('src="/ui.js"', html)
        self.assertIn(b"--codex", self.get("/ui.css"))
        self.assertIn(b"function shell", self.get("/ui.js"))

    def test_decide_a_human_gate_from_the_app(self):
        run = warroom.make_demo(drive=False)
        bus = warroom.open_bus(run)
        tid = bus.post_task("needs a call", "", "forge")["id"]
        self.assertEqual(self.post(f"/api/run/{run}/decide", {"task": tid, "approve": True})[0], 409)  # not at a gate
        bus.db.execute("UPDATE tasks SET status='blocked' WHERE id=?", (tid,))
        self.assertEqual(self.post(f"/api/run/{run}/decide", {"task": tid, "approve": True}, token="wrong")[0], 403)
        code, out = self.post(f"/api/run/{run}/decide", {"task": tid, "approve": False, "notes": "add a test"})
        self.assertEqual((code, out["ok"]), (200, True))
        t = bus._task(tid)
        self.assertEqual((t["status"], t["assignee"]), ("open", "forge"))
        self.assertIn("add a test", bus.db.execute("SELECT body FROM messages ORDER BY id DESC").fetchone()["body"])
        diff = json.loads(self.get(f"/api/run/{run}/task/{tid}/diff"))
        self.assertIsNone(diff["files"])


if __name__ == "__main__":
    unittest.main()
