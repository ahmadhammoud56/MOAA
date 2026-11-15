#!/usr/bin/env python3
"""Self-improve loop: set up the data folder and the weekly schedule.

Usage: python selfimprove.py init | schedule [--day SUN] [--time 10:00] | status | stop | remove | on | off | where

The data folder is $SELF_IMPROVE_HOME, or ~/self-improve. `init` creates it with a run script; `schedule` is the only
command that creates a weekly job (a weekly unattended run spends your Claude usage). `off` (or SELF_IMPROVE=off)
makes every run exit at once; `stop` disables the job and `remove` deletes it. Standard library only.
"""
import argparse
import base64
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

TASK = "Claude Self-Improve"
MARK = "# claude-self-improve"
PROMPT = "/self-improve:self-improve-run then /self-improve:improve-system"
DAYS = {"SUN": ("Sunday", 0), "MON": ("Monday", 1), "TUE": ("Tuesday", 2), "WED": ("Wednesday", 3),
        "THU": ("Thursday", 4), "FRI": ("Friday", 5), "SAT": ("Saturday", 6)}
WINDOWS = os.name == "nt"
REPOS_TXT = """# One git repo per line (`~` allowed). The git collector only reads history (git log).
# Example:
# ~/code/my-project
"""
SOURCES_TXT = """# Extra outside feeds for the outside collector, one `name|url` per line (Atom/RSS, or a raw CHANGELOG.md).
# The Claude Code changelog and the Python announcements are always read. Redirects may only stay on these hosts.
# Example:
# superpowers releases|https://github.com/obra/superpowers/releases.atom
"""
CHANGE_LOG = """# Self-improve change log

| date | file | change | reason / finding | backup |
|---|---|---|---|---|
"""


def data_home():
    return Path(os.environ.get("SELF_IMPROVE_HOME") or Path.home() / "self-improve").expanduser()


def run_script(data):
    return data / ("run.cmd" if WINDOWS else "run.sh")


def edit_rule(data):
    """An Edit(...) permission rule for the data folder: `~/` when under home, `//` (absolute) otherwise."""
    try:
        return f"Edit(~/{data.resolve().relative_to(Path.home().resolve()).as_posix()}/**)"
    except ValueError:
        return f"Edit(//{data.resolve().as_posix().lstrip('/')}/**)"


def allowed_tools(data):
    return ["Read", "Write", "Edit", edit_rule(data), "Glob", "Grep", "Skill", "Bash(python *)", "Bash(py *)",
            "PowerShell(python *)", "PowerShell(py *)"]


def render_cmd(data, claude):
    tools = " ".join(f'"{t}"' if " " in t or "(" in t else t for t in allowed_tools(data))
    return f"""@echo off
rem Self-improve loop (MOAA self-improve plugin), written by `selfimprove.py init`. See STOP.md to stop it.
setlocal
if /i "%SELF_IMPROVE%"=="off" exit /b 0
cd /d "{data}"
if exist OFF exit /b 0
if not exist logs mkdir logs
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%d
echo === %TODAY% %TIME% start >> "logs\\%TODAY%.log"
call "{claude}" -p "{PROMPT}" --add-dir "{data}" --add-dir "%USERPROFILE%\\.claude" --allowedTools {tools} >> "logs\\%TODAY%.log" 2>&1
echo === %TODAY% %TIME% exit %ERRORLEVEL% >> "logs\\%TODAY%.log"
endlocal
"""


def render_sh(data, claude):
    q = shlex.quote
    tools = " ".join(q(t) for t in allowed_tools(data))
    return f"""#!/bin/sh
# Self-improve loop (MOAA self-improve plugin), written by `selfimprove.py init`. See STOP.md to stop it.
[ "$SELF_IMPROVE" = off ] && exit 0
cd {q(str(data))} || exit 1
[ -e OFF ] && exit 0
export PATH={q(os.environ.get("PATH", "/usr/bin:/bin"))}
mkdir -p logs
TODAY=$(date +%F)
echo "=== $TODAY $(date +%T) start" >> "logs/$TODAY.log"
{q(claude)} -p {q(PROMPT)} --add-dir {q(str(data))} --add-dir "$HOME/.claude" --allowedTools {tools} >> "logs/$TODAY.log" 2>&1
code=$?
echo "=== $TODAY $(date +%T) exit $code" >> "logs/$TODAY.log"
exit $code
"""


def init(data, claude=None):
    """Create the data folder. Never overwrites repos.txt, sources.txt or change-log.md; rewrites the run script."""
    claude = claude or shutil.which("claude") or "claude"
    for sub in ("digests", "reviews", "backups", "logs"):
        (data / sub).mkdir(parents=True, exist_ok=True)
    for name, body in (("repos.txt", REPOS_TXT), ("sources.txt", SOURCES_TXT), ("change-log.md", CHANGE_LOG)):
        if not (data / name).exists():
            (data / name).write_text(body, encoding="utf-8")
    script = run_script(data)
    if WINDOWS:
        script.write_text(render_cmd(data, claude), encoding="utf-8", newline="\r\n")
    else:
        script.write_text(render_sh(data, claude), encoding="utf-8")
        script.chmod(0o755)
    return script


def check_when(day, time):
    day = day.upper()[:3]
    if day not in DAYS:
        raise ValueError(f"unknown day {day!r}; use one of {', '.join(DAYS)}")
    hour, _, minute = time.partition(":")
    if not (hour.isdigit() and minute.isdigit() and int(hour) < 24 and int(minute) < 60 and len(minute) == 2):
        raise ValueError(f"time must be HH:MM, got {time!r}")
    return day, f"{int(hour):02d}:{minute}"


def ps_quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def windows_schedule_argv(script, data, day, time):
    """powershell argv that creates or replaces the weekly task (no end date). -EncodedCommand avoids every
    quoting problem with spaces or quotes in the paths."""
    argument = ps_quote('/c "' + str(script) + '"')
    ps = "\n".join([
        f"$a = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument {argument}"
        f" -WorkingDirectory {ps_quote(data)}",
        f"$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek {DAYS[day][0]} -At {ps_quote(time)}",
        "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)",
        f"Register-ScheduledTask -TaskName {ps_quote(TASK)} -Action $a -Trigger $t -Settings $s"
        " -Description 'MOAA self-improve loop. Stop: selfimprove.py stop' -Force | Out-Null",
    ])
    encoded = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
    return ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


def cron_line(script, day, time):
    hour, minute = time.split(":")
    return f"{int(minute)} {int(hour)} * * {DAYS[day][1]} /bin/sh {shlex.quote(str(script))} {MARK}"


def cron_update(existing, line=None, mode="set"):
    """New crontab text: drop our old line, then add `line` (set), keep it commented out (disable) or drop it (remove)."""
    keep, ours = [], []
    for row in existing.splitlines():
        (ours if row.rstrip().endswith(MARK) else keep).append(row)
    if mode == "set":
        keep.append(line)
    elif mode == "disable":
        keep += ["# " + row.lstrip("# ") for row in ours]
    return "\n".join(keep) + "\n" if keep else ""


def crontab_read():
    run = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return run.stdout if run.returncode == 0 else ""


def crontab_write(text):
    return subprocess.run(["crontab", "-"], input=text, text=True).returncode


def stop_md(data, day, time):
    me = f'python "{Path(__file__).resolve()}"'
    if WINDOWS:
        raw = (f'schtasks /Change /TN "{TASK}" /DISABLE\nschtasks /Change /TN "{TASK}" /ENABLE\n'
               f'schtasks /Delete /TN "{TASK}" /F\nschtasks /Query /TN "{TASK}" /V /FO LIST')
        where = f'the Windows scheduled task **{TASK}**, every {DAYS[day][0]} at {time}, with no end date'
    else:
        raw = "crontab -l   # the line ending in " + MARK + "\ncrontab -e   # delete or comment out that line"
        where = f"a crontab line (marked `{MARK}`), every {DAYS[day][0]} at {time}"
    return f"""# Stopping the self-improve loop

The loop runs as {where}, until you stop it. Each run executes `{run_script(data).name}` in this folder and logs to
`logs/<date>.log`. A run spends your Claude usage.

Skip runs but keep the schedule: `{me} off` (back on: `{me} on`), or set the environment variable SELF_IMPROVE=off.

Disable the job: `{me} stop`. Delete it: `{me} remove`. Check it: `{me} status`.

Without the script:

```
{raw}
```

What a run can do: read files, write in this folder, run skills and the `python` collector scripts. No other shell
commands, no git writes and no permission changes. Bigger changes wait in `reviews/<date>-review.md` until you tick
them. To undo a change, restore its backup from `backups/` and see `change-log.md`.
"""


def schedule(data, day, time):
    script = run_script(data)
    if not script.exists():
        print(f"No run script in {data}; run `selfimprove.py init` first.")
        return 1
    if WINDOWS:
        code = subprocess.run(windows_schedule_argv(script, data, day, time)).returncode
    else:
        code = crontab_write(cron_update(crontab_read(), cron_line(script, day, time)))
    if code == 0:
        (data / "STOP.md").write_text(stop_md(data, day, time), encoding="utf-8")
        print(f"Scheduled: every {DAYS[day][0]} at {time}, no end date. How to stop it: {data / 'STOP.md'}")
    return code


def status(data):
    off = os.environ.get("SELF_IMPROVE", "").lower() == "off" or (data / "OFF").exists()
    print(f"data folder: {data}" + ("" if data.exists() else " (missing: run init)"))
    print(f"runs: {'off' if off else 'on'}")
    logs = sorted((data / "logs").glob("*.log")) if data.exists() else []
    print(f"last log: {logs[-1] if logs else 'none'}")
    if WINDOWS:
        run = subprocess.run(["schtasks", "/Query", "/TN", TASK, "/FO", "LIST"], capture_output=True, text=True)
        print(run.stdout.strip() if run.returncode == 0 else "schedule: none")
    else:
        rows = [r for r in crontab_read().splitlines() if r.rstrip().endswith(MARK)]
        print("schedule: " + (rows[0] if rows else "none"))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("init", "status", "stop", "remove", "on", "off", "where"):
        sub.add_parser(name)
    sch = sub.add_parser("schedule")
    sch.add_argument("--day", default="SUN")
    sch.add_argument("--time", default="10:00")
    args = parser.parse_args(argv)
    data = data_home()
    if args.cmd == "where":
        print(data)
    elif args.cmd == "init":
        print(f"Ready: {init(data)}. Add repos to {data / 'repos.txt'}, then `selfimprove.py schedule` when you want"
              " a weekly run.")
    elif args.cmd == "schedule":
        try:
            day, time = check_when(args.day, args.time)
        except ValueError as exc:
            print(exc)
            return 2
        return schedule(data, day, time)
    elif args.cmd == "status":
        return status(data)
    elif args.cmd in ("on", "off"):
        flag = data / "OFF"
        if args.cmd == "off":
            data.mkdir(parents=True, exist_ok=True)
            flag.write_text("Runs are off. `selfimprove.py on` turns them back on.\n", encoding="utf-8")
        else:
            flag.unlink(missing_ok=True)
        print(f"self-improve runs: {args.cmd}")
    elif WINDOWS:
        argv = ["schtasks", "/Change", "/TN", TASK, "/DISABLE"] if args.cmd == "stop" else \
            ["schtasks", "/Delete", "/TN", TASK, "/F"]
        return subprocess.run(argv).returncode
    else:
        return crontab_write(cron_update(crontab_read(), mode="disable" if args.cmd == "stop" else "remove"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
