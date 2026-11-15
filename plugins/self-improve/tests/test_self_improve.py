"""self-improve tests, no network and no real scheduled tasks: python -m unittest discover -s tests"""
import base64
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "collectors")]
import outside  # noqa: E402
import selfimprove  # noqa: E402
from sessions import epoch, session_facts  # noqa: E402


def tool_rows(stamp, tool_id, text):
    return [
        {"type": "assistant", "timestamp": stamp,
         "message": {"content": [{"type": "tool_use", "id": tool_id, "name": "Write"}]}},
        {"type": "user", "timestamp": stamp,
         "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "is_error": True, "content": text}]}},
    ]


class Sessions(unittest.TestCase):
    def test_only_errors_inside_the_window_count(self):
        rows = tool_rows("2026-10-05T09:00:00.000Z", "old", "old gate error") + \
            tool_rows("2026-10-18T09:00:00.000Z", "new", "new error")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            facts = session_facts(path, cutoff=epoch("2026-10-12T00:00:00Z"))
            self.assertEqual(facts["errors"], ["Write: new error"])
            self.assertEqual(len(session_facts(path)["errors"]), 2)  # no cutoff: everything counts


class Init(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "data with spaces"
        self.env = mock.patch.dict(os.environ, {"SELF_IMPROVE_HOME": str(self.tmp)})
        self.env.start()
        os.environ.pop("SELF_IMPROVE", None)

    def tearDown(self):
        self.env.stop()

    def test_init_creates_the_folder_and_keeps_user_files(self):
        self.assertEqual(selfimprove.data_home(), self.tmp)
        script = selfimprove.init(self.tmp, claude="claude")
        for sub in ("digests", "reviews", "backups", "logs"):
            self.assertTrue((self.tmp / sub).is_dir())
        self.assertTrue(script.is_file())
        self.assertIn(selfimprove.PROMPT, script.read_text(encoding="utf-8"))
        (self.tmp / "repos.txt").write_text("~/mine\n", encoding="utf-8")
        selfimprove.init(self.tmp, claude="claude")
        self.assertEqual((self.tmp / "repos.txt").read_text(encoding="utf-8"), "~/mine\n")
        self.assertTrue((self.tmp / "change-log.md").read_text(encoding="utf-8").startswith("# Self-improve"))

    def test_on_off_flag(self):
        selfimprove.main(["off"])
        self.assertTrue((self.tmp / "OFF").exists())
        selfimprove.main(["on"])
        self.assertFalse((self.tmp / "OFF").exists())

    def fake_claude(self, marker):
        if os.name == "nt":
            fake = self.tmp.parent / "fake claude.cmd"
            fake.write_text(f'@echo called> "{marker}"\r\n', encoding="utf-8")
        else:
            fake = self.tmp.parent / "fake claude.sh"
            fake.write_text(f"#!/bin/sh\necho called > {shlex.quote(str(marker))}\n", encoding="utf-8")
            fake.chmod(0o755)
        return str(fake)

    def run_script(self, script, **env):
        argv = ["cmd", "/c", str(script)] if os.name == "nt" else ["sh", str(script)]
        full = {k: v for k, v in os.environ.items() if k != "SELF_IMPROVE"}
        subprocess.run(argv, env={**full, **env}, capture_output=True, timeout=60)

    def test_run_script_honours_off_switches(self):
        marker = self.tmp.parent / "called.txt"
        script = selfimprove.init(self.tmp, claude=self.fake_claude(marker))
        self.run_script(script, SELF_IMPROVE="off")
        self.assertFalse(marker.exists(), "SELF_IMPROVE=off must skip the run")
        (self.tmp / "OFF").write_text("off", encoding="utf-8")
        self.run_script(script)
        self.assertFalse(marker.exists(), "the OFF flag must skip the run")
        (self.tmp / "OFF").unlink()
        self.run_script(script)
        self.assertTrue(marker.exists(), "with both switches on, the run calls claude")
        self.assertTrue(list((self.tmp / "logs").glob("*.log")))

    def test_schedule_needs_init(self):
        with mock.patch.object(selfimprove.subprocess, "run") as run:
            self.assertEqual(selfimprove.main(["schedule"]), 1)
            run.assert_not_called()

    def test_schedule_rejects_bad_day_and_time(self):
        self.assertEqual(selfimprove.main(["schedule", "--day", "XYZ"]), 2)
        self.assertEqual(selfimprove.main(["schedule", "--time", "25:00"]), 2)


class Schedulers(unittest.TestCase):
    def test_check_when(self):
        self.assertEqual(selfimprove.check_when("sunday", "9:05"), ("SUN", "09:05"))
        for bad in (("SUN", "10"), ("SUN", "10:5"), ("SUN", "24:00"), ("XX", "10:00")):
            with self.assertRaises(ValueError):
                selfimprove.check_when(*bad)

    def test_cron_line_quotes_spaces(self):
        line = selfimprove.cron_line(PurePosixPath("/home/u/my data/run.sh"), "SUN", "10:00")
        self.assertEqual(line, "0 10 * * 0 /bin/sh '/home/u/my data/run.sh' " + selfimprove.MARK)

    def test_cron_update_is_idempotent(self):
        line = selfimprove.cron_line(Path("/x/run.sh"), "MON", "07:30")
        start = "MAILTO=\"\"\n5 * * * * other-job\n"
        once = selfimprove.cron_update(start, line)
        twice = selfimprove.cron_update(once, line)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(selfimprove.MARK), 1)
        self.assertIn("other-job", once)
        disabled = selfimprove.cron_update(once, mode="disable")
        self.assertIn("# " + line, disabled)
        self.assertEqual(selfimprove.cron_update(disabled, mode="disable"), disabled)
        self.assertNotIn(selfimprove.MARK, selfimprove.cron_update(disabled, mode="remove"))
        self.assertIn("other-job", selfimprove.cron_update(disabled, mode="remove"))

    def test_windows_argv_handles_spaces_and_quotes(self):
        script = PureWindowsPath(r"C:\Users\you\O'Brien data\run.cmd")  # Windows rules on every CI runner
        argv = selfimprove.windows_schedule_argv(script, script.parent, "SUN", "10:00")
        self.assertEqual(argv[:4], ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand"])
        ps = base64.b64decode(argv[4]).decode("utf-16-le")
        self.assertIn(r"""-Argument '/c "C:\Users\you\O''Brien data\run.cmd"'""", ps)
        self.assertIn(r"-WorkingDirectory 'C:\Users\you\O''Brien data'", ps)
        self.assertIn("-Weekly -DaysOfWeek Sunday -At '10:00'", ps)
        self.assertIn("-TaskName 'Claude Self-Improve'", ps)
        self.assertIn("-Force", ps)  # replaces an existing task
        self.assertNotIn("EndBoundary", ps)


class Outside(unittest.TestCase):
    def test_sources_txt_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.txt"
            path.write_text("# comment|https://skip.example/feed\n"
                            "My feed | https://feeds.example.org/a.atom\n"
                            "no pipe here\n"
                            "bad scheme|ftp://x.example/feed\n"
                            "|https://noname.example/feed\n"
                            "dup|https://blog.python.org/feeds/posts/default\n", encoding="utf-8")
            sources = outside.load_sources(path)
        self.assertEqual(sources[:2], outside.SOURCES)
        self.assertEqual(sources[2:], [("My feed", "https://feeds.example.org/a.atom")])
        self.assertEqual(outside.load_sources(Path(tmp) / "missing.txt"), outside.SOURCES)

    def test_redirect_guard(self):
        handler = outside.SameHostsRedirect(["feeds.example.org"])
        req = urllib.request.Request("https://feeds.example.org/a.atom")
        with self.assertRaises(urllib.error.HTTPError) as refused:
            handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example.net/x")
        refused.exception.close()
        ok = handler.redirect_request(req, None, 302, "Found", {}, "https://feeds.example.org/b.atom")
        self.assertEqual(ok.full_url, "https://feeds.example.org/b.atom")

    def test_opener_allows_configured_hosts(self):
        built = outside.opener(outside.SOURCES + [("x", "https://feeds.example.org/a")])
        guard = next(h for h in built.handlers if isinstance(h, outside.SameHostsRedirect))
        self.assertEqual(guard.hosts, {"raw.githubusercontent.com", "blog.python.org", "feeds.example.org"})


class GitCollector(unittest.TestCase):
    def test_missing_repo_list_prints_a_hint(self):
        sys.path.insert(0, str(ROOT / "collectors"))
        import git as git_collector
        with tempfile.TemporaryDirectory() as tmp, mock.patch("sys.stdout") as out:
            self.assertEqual(git_collector.main(["--repos", str(Path(tmp) / "repos.txt")]), 0)
        printed = "".join(c.args[0] for c in out.write.call_args_list)
        self.assertIn("no repo list", printed)


if __name__ == "__main__":
    unittest.main()
