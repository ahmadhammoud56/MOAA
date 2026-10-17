"""Crew tests with fake member CLIs (no real agent is called): python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import crew  # noqa: E402

FAKE = """import os, sys
prompt = sys.stdin.read()
mode = sys.argv[1]
if mode == "write":
    open("made_by_member.txt", "w").write("hello\\n")
if len(sys.argv) > 2 and sys.argv[2] == "--fail":
    sys.exit(3)
print("ANSWER", mode, "key=" + os.environ.get("FAKE_KEY", "none"), "task-seen=" + str("TASK:" in prompt))
"""


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                   capture_output=True)


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "fake.py").write_text(FAKE, encoding="utf-8")
        fake = str(self.tmp / "fake.py")
        self.members = {
            "alpha": {"label": "a", "bin": "python-fake", "install": "i", "login": "l", "stdin": True,
                      "read": [fake, "read"], "write": [fake, "write"], "model": ["--model", "{model}"],
                      "good_for": ["code"]},
            "beta": {"label": "b", "bin": "python-fake", "install": "i", "login": "set FAKE_KEY", "stdin": True,
                     "env": {"FAKE_KEY": "$FAKE_KEY"}, "read": [fake, "read"], "write": [fake, "write"],
                     "good_for": ["code", "research"]},
            "broken": {"label": "c", "bin": "python-fake", "install": "i", "login": "l", "stdin": True,
                       "read": [fake, "read", "--fail"], "write": [fake, "write", "--fail"], "good_for": []},
        }
        patches = [mock.patch.object(crew, "load_members", lambda: self.members),
                   mock.patch.object(crew, "which", lambda name: sys.executable if name == "python-fake" else None),
                   mock.patch.dict(os.environ, {"MOAA_CREW_DIR": str(self.tmp / "crew")})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("FAKE_KEY", None)

    def repo(self):
        r = self.tmp / "repo"
        r.mkdir()
        git(r, "init", "-q")
        (r / "a.txt").write_text("a\n")
        git(r, "add", "-A")
        git(r, "commit", "-qm", "init")
        return r


class Runs(Sandbox):
    def test_read_run_sends_brief_on_stdin_and_saves_answer(self):
        meta = crew.run("alpha", "count the files", cwd=self.tmp)
        self.assertTrue(meta["ok"])
        answer = Path(meta["answer"]).read_text(encoding="utf-8")
        self.assertIn("ANSWER read", answer)
        self.assertIn("task-seen=True", answer)
        task = (self.tmp / "crew" / "runs" / meta["id"] / "task.md").read_text(encoding="utf-8")
        self.assertIn("read-only mode", task)
        self.assertTrue((self.tmp / "crew" / "runs" / meta["id"] / "meta-alpha.json").is_file())

    def test_env_members_need_their_key_and_get_it(self):
        with self.assertRaises(SystemExit):
            crew.run("beta", "x", cwd=self.tmp)
        os.environ["FAKE_KEY"] = "k123"
        self.assertIn("key=k123", Path(crew.run("beta", "x", cwd=self.tmp)["answer"]).read_text(encoding="utf-8"))

    def test_failures_and_unknowns_are_reported(self):
        self.assertFalse(crew.run("broken", "x", cwd=self.tmp)["ok"])
        with self.assertRaises(SystemExit):
            crew.run("nobody", "x")
        with self.assertRaises(SystemExit):
            crew.run("alpha", "x", cwd=self.tmp, write=True)  # not a git repo

    def test_write_run_lands_on_its_own_branch(self):
        r = self.repo()
        meta = crew.run("alpha", "make a file", cwd=r, write=True)
        self.assertTrue(meta["ok"])
        self.assertEqual(meta["commits"], "1")
        self.assertIn("made_by_member.txt", meta["diffstat"])
        self.assertFalse((r / "made_by_member.txt").exists())  # the user's checkout is untouched
        branches = subprocess.run(["git", "-C", str(r), "branch", "--list"], capture_output=True, text=True).stdout
        self.assertIn(meta["branch"], branches)
        self.assertIn("Do not commit", (self.tmp / "crew" / "runs" / meta["id"] / "task.md").read_text(encoding="utf-8"))

    def test_write_into_an_existing_worktree_commits_there(self):
        r = self.repo()
        wt = self.tmp / "wt"
        git(r, "worktree", "add", "-b", "wr-x", str(wt), "HEAD")
        meta = crew.run("alpha", "make a file", cwd=r, write=True, workdir=wt)
        self.assertEqual((meta["branch"], meta["commits"]), ("wr-x", "1"))
        self.assertTrue((wt / "made_by_member.txt").is_file())
        self.assertRegex(meta["head"], r"^[0-9a-f]{40}$")
        with self.assertRaises(SystemExit):
            crew.run("alpha", "x", cwd=r, write=True, workdir=self.tmp)  # not a worktree

    def test_ask_fans_out_and_keeps_going_when_one_member_is_unavailable(self):
        out = crew.ask(["alpha", "beta"], "review this", cwd=self.tmp)
        by = {o["member"]: o for o in out}
        self.assertTrue(by["alpha"]["ok"])
        self.assertFalse(by["beta"]["ok"])
        self.assertIn("FAKE_KEY", by["beta"]["error"])
        self.assertEqual(len({o["id"] for o in out}), 1)

    def test_argv_substitution_and_pick(self):
        spec = {"read": ["x", "{prompt}", "--out", "{out}"], "write": [], "model": ["-m", "{model}"], "default_model": "d1"}
        self.assertEqual(crew.build_argv(spec, "exe", False, None, "P", "O"), ["exe", "x", "P", "--out", "O", "-m", "d1"])
        self.assertEqual(crew.build_argv(spec, "exe", False, "m2", "P", "O")[-1], "m2")
        ready = {"alpha", "beta"}
        self.assertEqual(crew.pick("code", ready=ready), "alpha")
        self.assertEqual(crew.pick("code", exclude=["alpha"], ready=ready), "beta")
        self.assertEqual(crew.pick("research", ready={"alpha"}), None)

    def test_omniroute_secrets_are_generated_once_and_settings_locked(self):
        first = crew.omni_env()
        second = crew.omni_env()
        self.assertEqual(first["INITIAL_PASSWORD"], second["INITIAL_PASSWORD"])
        self.assertGreater(len(first["JWT_SECRET"]), 40)
        for k, v in (("HOST", "127.0.0.1"), ("REQUIRE_API_KEY", "true"), ("WEB_COOKIE_USE_BROWSER", "0"),
                     ("OMNIROUTE_DISABLE_CONVERSATION_TRACKING", "1")):
            self.assertEqual(first[k], v)
        self.assertNotEqual(first["INITIAL_PASSWORD"], "CHANGEME")


class Hardening(Sandbox):
    def test_cmd_shims_are_unwrapped_and_otherwise_guarded(self):
        shim = self.tmp / "tool.cmd"
        (self.tmp / "node_modules" / "tool").mkdir(parents=True)
        (self.tmp / "node_modules" / "tool" / "cli.js").write_text("")
        shim.write_text('@ECHO off\r\n"%_prog%"  "%dp0%\\node_modules\\tool\\cli.js" %*\r\n')
        with mock.patch.object(crew, "IS_WIN", True), mock.patch.object(crew.shutil, "which", lambda n: "node.exe"):
            argv, via_cmd = crew.launcher(str(shim))
            self.assertEqual((argv, via_cmd), (["node.exe", str(self.tmp / "node_modules" / "tool" / "cli.js")], False))
            shim.write_text("@echo off\r\nsomething else %*\r\n")
            self.assertEqual(crew.launcher(str(shim)), ([str(shim)], True))
        self.assertTrue(crew.CMD_META.search('fix "& calc &"'))
        with self.assertRaises(SystemExit):
            crew.run("alpha", "x", cwd=self.tmp, model="--dangerous-flag")

    def test_members_only_see_their_own_credentials(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "a", "CLAUDE_CODE_OAUTH_TOKEN": "b", "GITHUB_TOKEN": "c",
                                          "OPENAI_API_KEY": "d", "AWS_SECRET_ACCESS_KEY": "e", "PATH": "p"}):
            env = crew.child_env({"pass_env": "^OPENAI_"}, {"X": "1"})
        self.assertEqual({k for k in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY",
                                      "OPENAI_API_KEY", "PATH", "X") if k in env}, {"OPENAI_API_KEY", "PATH", "X"})

    def test_timeout_kills_the_process_tree(self):
        code = ("import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
                " print('started', flush=True); time.sleep(60)")
        t0 = __import__("time").time()
        rc, out, _ = crew.run_proc([sys.executable, "-c", code], None, str(self.tmp), dict(os.environ), 3)
        self.assertEqual(rc, "timeout")
        self.assertLess(__import__("time").time() - t0, 40)  # communicate did not hang on the grandchild's pipes


class ShippedMembers(unittest.TestCase):
    def test_members_file_is_well_formed_and_claude_members_never_use_the_users_login(self):
        members = json.loads((Path(crew.__file__).parent / "members.json").read_text(encoding="utf-8"))["members"]
        self.assertEqual(set(members), {"codex", "gemini", "kimi", "deepseek", "omniroute"})
        for name, spec in members.items():
            with self.subTest(member=name):
                for key in ("label", "bin", "install", "login", "read", "write", "good_for"):
                    self.assertIn(key, spec)
                if spec["bin"] == "claude":
                    self.assertIn("--bare", spec["read"])  # --bare never reads the Claude OAuth login
                    self.assertIn("--bare", spec["write"])
                    self.assertEqual(spec["env"]["ANTHROPIC_API_KEY"][0], "$")
                self.assertTrue(any(x in spec["read"] for x in ("read-only", "plan", "--plan")))  # read stays read-only


if __name__ == "__main__":
    unittest.main()
