"""Second-brain vault tests: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import graph  # noqa: E402
import rag  # noqa: E402
import strata  # noqa: E402


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.vault = self.dir / "brain"
        env = mock.patch.dict(os.environ, {"MOAA_STRATA_DIR": str(self.dir / "data"), "STRATA_VAULT": str(self.vault),
                                           "STRATA_CANARY": "off"})
        env.start()
        self.addCleanup(env.stop)
        for k in (strata.CHILD, "STRATA_RAG"):
            os.environ.pop(k, None)


class Vault(Sandbox):
    def test_init_creates_the_layout_and_a_git_repo_without_commits(self):
        self.assertEqual(strata.main(["vault", "init"]), 0)
        for name in ("README.md", ".gitignore", "inbox/archive", "daily", "wiki/index.md", "wiki/log.md"):
            self.assertTrue((self.vault / name).exists(), name)
        if shutil.which("git"):
            self.assertTrue((self.vault / ".git").is_dir())
            log = strata.subprocess.run(["git", "-C", str(self.vault), "log"], capture_output=True)
            self.assertNotEqual(log.returncode, 0)  # no commits: strata never commits
        (self.vault / "wiki" / "index.md").write_text("# mine\n", encoding="utf-8")
        strata.vault_init(self.vault)  # again: keeps what is there
        self.assertEqual((self.vault / "wiki" / "index.md").read_text(encoding="utf-8"), "# mine\n")

    def test_vault_path_and_off_switches(self):
        self.assertEqual(strata.vault_dir(), self.vault)
        with mock.patch.dict(os.environ, {"STRATA_VAULT": "off"}):
            self.assertIsNone(strata.vault_dir())
            with self.assertRaises(SystemExit):
                strata.capture("x")
        os.environ.pop("STRATA_VAULT")
        self.assertEqual(strata.vault_dir(), Path("~/code/brain").expanduser())  # the default
        other = self.dir / "elsewhere"
        self.assertEqual(strata.main(["vault", "init", str(other)]), 0)
        self.assertEqual(strata.vault_dir(), other.resolve())
        self.assertEqual(strata.main(["vault", "off"]), 0)
        self.assertIsNone(strata.vault_dir())
        self.assertEqual(strata.main(["vault", "status"]), 0)

    def test_capture_appends_time_project_and_redacts(self):
        proj = self.dir / "my-project"
        proj.mkdir()
        with mock.patch.object(strata, "root_of", lambda cwd: os.path.normpath(str(cwd or proj))):
            self.assertEqual(graph.main(["capture", "try", "FTS5", "trigram", "--project", str(proj)]), 0)
            strata.main(["capture", "rotate", "token=abcdefgh12345678"])
        f = self.vault / "inbox" / time.strftime("%Y-%m-%d.md")
        lines = f.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], f"# Inbox {time.strftime('%Y-%m-%d')}")
        self.assertRegex(lines[2], r"^- \d\d:\d\d \[my-project\] try FTS5 trigram$")
        self.assertIn("[redacted]", lines[3])
        self.assertNotIn("abcdefgh", f.read_text(encoding="utf-8"))

    def test_session_end_adds_one_line_per_chat_to_the_daily_note(self):
        t = self.dir / "t.jsonl"
        recs = [{"type": "user", "message": {"content": "Port the parser to Rust"}},
                {"type": "assistant", "message": {"content": [{"type": "text",
                                                               "text": "Lexer done.\n\n" + strata.CANARY}]}}]
        t.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
        end = lambda s: strata.hook("session-end", json.dumps({"session_id": s, "transcript_path": str(t),  # noqa
                                                                "cwd": str(self.dir)}))
        with mock.patch.object(strata, "spawn"):
            end("aaaaaaaa-1")  # no vault folder yet: nothing is written, nothing is created
            self.assertFalse(self.vault.exists())
            strata.vault_init(self.vault)
            end("aaaaaaaa-1")
            end("aaaaaaaa-1")  # a resumed chat replaces its line
            end("bbbbbbbb-2")
            machine = self.dir / "m.jsonl"
            machine.write_text(json.dumps({"type": "user", "message": {"content": strata.MACHINE_PROMPTS[0] + " x"}}),
                               encoding="utf-8")
            strata.hook("session-end", json.dumps({"session_id": "cccccccc", "transcript_path": str(machine),
                                                   "cwd": str(self.dir)}))
        text = (self.vault / "daily" / time.strftime("%Y-%m-%d.md")).read_text(encoding="utf-8")
        self.assertEqual(text.count("(session aaaaaaaa)"), 1)
        self.assertEqual(text.count("(session bbbbbbbb)"), 1)
        self.assertNotIn("cccccccc", text)
        self.assertIn('Asked: "Port the parser to Rust"', text)
        self.assertIn('Last reply: "Lexer done."', text)  # the canary line is left out
        with mock.patch.dict(os.environ, {"STRATA_VAULT": "off"}), mock.patch.object(strata, "spawn"):
            strata.hook("session-end", json.dumps({"session_id": "dddddddd", "transcript_path": str(t),
                                                   "cwd": str(self.dir)}))
        self.assertNotIn("dddddddd", (self.vault / "daily" / time.strftime("%Y-%m-%d.md")).read_text(encoding="utf-8"))

    def test_archive_moves_only_inbox_files(self):
        strata.vault_init(self.vault)
        (self.vault / "inbox" / "2026-10-25.md").write_text("- a\n", encoding="utf-8")
        (self.vault / "inbox" / "archive" / "2026-10-25.md").write_text("- old\n", encoding="utf-8")
        (self.vault / "inbox" / "2026-10-26.md").write_text("- b\n", encoding="utf-8")
        self.assertEqual(graph.archive(self.vault, ["inbox/2026-10-25.md", "README.md", "../x.md"]),
                         ["inbox/archive/2026-10-25.md"])
        self.assertEqual((self.vault / "inbox" / "archive" / "2026-10-25.md").read_text(), "- old\n- a\n")
        self.assertTrue((self.vault / "README.md").exists())
        self.assertEqual(graph.main(["archive", str(self.vault)]), 0)  # default: everything left in inbox/
        self.assertEqual(list((self.vault / "inbox").glob("*.md")), [])

    def test_wiki_links_resolve_by_file_name_anywhere_under_wiki(self):
        strata.vault_init(self.vault)
        w = self.vault / "wiki"
        (w / "projects").mkdir()
        (w / "projects" / "Strata.md").write_text("Memory plugin. See [[Canary]] and [[resources/Canary|it]].\n")
        (w / "resources").mkdir()
        (w / "resources" / "Canary.md").write_text("Drift check, part of [[Strata]].\n")
        (w / "index.md").write_text("# Index\n- [[Strata]]\n- [[Canary]]\n")
        r = graph.lint(w)
        self.assertEqual((r["pages"], r["broken"], r["orphans"], r["not_in_index"]), (2, [], [], []))
        (w / "projects" / "Loose.md").write_text("Points to [[Nowhere]].\n")
        self.assertEqual(graph.lint(w)["broken"], [{"from": "projects/Loose", "to": "Nowhere"}])
        self.assertEqual(graph.main(["log", str(w), "distill: test"]), 0)
        self.assertIn("distill: test", (w / "log.md").read_text())


class VaultRag(Sandbox):
    def test_vault_is_indexed_and_searched_even_outside_a_project(self):
        strata.vault_init(self.vault)
        (self.vault / "wiki" / "Rheometer.md").write_text(
            "# Rheometer\nCalibrate the vane rheometer with the reference silicone oil before every batch.\n",
            encoding="utf-8")
        home = json.dumps({"cwd": str(Path.home())})
        with mock.patch.object(rag, "spawn") as spawn, mock.patch.object(rag, "is_git", return_value=False):
            rag.hook("session-start", home)  # the home folder is skipped, the vault is not
        self.assertEqual([c.args[0][-2] for c in spawn.call_args_list], [os.path.normpath(str(self.vault))])
        db = rag.connect()
        self.addCleanup(db.close)
        rag.index(db, self.vault)
        with mock.patch.object(rag, "is_git", return_value=False):
            out = rag.hook("prompt", json.dumps({"cwd": str(Path.home()),
                                                 "prompt": "how do I calibrate the vane rheometer with silicone oil?"}))
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("your second-brain vault", ctx)
        self.assertIn("wiki/Rheometer.md", ctx)
        with mock.patch.dict(os.environ, {"STRATA_VAULT": "off"}), mock.patch.object(rag, "is_git", return_value=False):
            self.assertEqual(rag.hook("prompt", json.dumps({"cwd": str(Path.home()), "prompt": "calibrate the vane "
                                                            "rheometer with silicone oil"})), "")


if __name__ == "__main__":
    unittest.main()
