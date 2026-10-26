"""moaa-core guard tests with a fake Claude home: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import guard  # noqa: E402

MULTI = 'python -c "import json\nprint(json.dumps({\'a\': 1}))"'
LONG = "py -c \"" + "; ".join(f"x{i} = {i} * {i}" for i in range(20)) + "; print(x19)\""


class Guard(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.env = os.environ.pop("MOAA_GUARD", None)

    def tearDown(self):
        os.environ.pop("MOAA_GUARD", None)
        if self.env is not None:
            os.environ["MOAA_GUARD"] = self.env

    def hook(self, command, tool="Bash"):
        return guard.hook_pre_tool(self.home, {"tool_name": tool, "tool_input": {"command": command}})

    def test_short_one_liner_passes_silently(self):
        for c in ('python -c "print(1+1)"', "py -3 -c 'import sys; print(sys.version)'", "python3 -c 'print(2)'"):
            self.assertIsNone(self.hook(c), c)

    def test_multiline_and_long_code_get_the_note(self):
        self.assertGreater(len(LONG), guard.MAX_CHARS)
        for c in (MULTI, LONG, "cd /tmp && python3.12 -I -c 'a = 1\nprint(a)'",
                  '& "C:\\Python314\\python.exe" -c "x = 1\nprint(x)"', "uv run python -c 'import os\nprint(os.sep)'"):
            for tool in guard.TOOLS:
                ctx = self.hook(c, tool)
                self.assertIn("scratchpad", ctx, c)
                self.assertIn(".py file", ctx)

    def test_non_python_commands_and_tools_ignored(self):
        for c in ("ls -la\nls", "pytest -c setup.cfg " + "x" * 200, "mypy -c 'x'\n" + "y" * 200,
                  "python script.py " + "arg " * 60, "git commit -m 'a\nb'", "", None):
            self.assertIsNone(self.hook(c), c)
        self.assertIsNone(guard.hook_pre_tool(self.home, {"tool_name": "Write", "tool_input": {"command": MULTI}}))
        self.assertIsNone(guard.hook_pre_tool(self.home, {}))
        self.assertIsNone(guard.hook_pre_tool(self.home, None))

    def test_off_switches(self):
        guard.save(self.home, False)
        self.assertIsNone(self.hook(MULTI))
        guard.save(self.home, True)
        self.assertIsNotNone(self.hook(MULTI))
        os.environ["MOAA_GUARD"] = "off"
        self.assertIsNone(self.hook(MULTI))
        self.assertIn("MOAA_GUARD=off", guard.status(self.home))

    def test_bad_config_means_on(self):
        guard.config_path(self.home).parent.mkdir(parents=True)
        guard.config_path(self.home).write_text("{not json", encoding="utf-8")
        self.assertTrue(guard.enabled(self.home))

    def run_cli(self, *args, stdin=b"", env=None):
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(self.home), **(env or {})}
        return subprocess.run([sys.executable, str(ROOT / "guard.py"), *args], input=stdin,
                              capture_output=True, env=env, timeout=30)

    def test_cli_hook_never_denies_and_survives_bad_input(self):
        payload = json.dumps({"tool_name": "PowerShell", "tool_input": {"command": MULTI}}).encode()
        r = self.run_cli("hook", "pre-tool", stdin=payload)
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertNotIn("permissionDecision", out)
        self.assertIn("moaa-core guard", out["additionalContext"])
        short = json.dumps({"tool_name": "Bash", "tool_input": {"command": "python -c 'print(1)'"}}).encode()
        for stdin, env in ((short, None), (b"\xff not json", None), (payload, {"MOAA_GUARD": "off"})):
            r = self.run_cli("hook", "pre-tool", stdin=stdin, env=env)
            self.assertEqual((r.returncode, r.stdout), (0, b""))

    def test_cli_toggle_writes_config_dir(self):
        self.assertIn("off", self.run_cli("off").stdout.decode())
        self.assertFalse(json.loads(guard.config_path(self.home).read_text())["guard"])
        self.assertIn("on", self.run_cli("on").stdout.decode())
        self.assertEqual(self.run_cli("bogus").returncode, 2)


if __name__ == "__main__":
    unittest.main()
