#!/usr/bin/env python3
"""Record a council run as a GIF.

Usage: python record.py <session.jsonl | replay.json> [-o council-run.gif] [--fps 15]

Serves replay.html and the replay data on 127.0.0.1, opens it in headless Chrome, Edge or
Chromium with autoexport on, and writes the GIF the page POSTs back. With no browser found
(or --manual) it prints the URL; open it and click "Export GIF". Standard library only.
"""
import argparse
from functools import partial
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from extract import extract  # noqa: E402

BROWSERS = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge"]
BROWSER_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def find_browser():
    for name in BROWSERS:
        if shutil.which(name):
            return shutil.which(name)
    return next((p for p in BROWSER_PATHS if Path(p).is_file()), None)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, data, out, done, **kwargs):
        self.data, self.out, self.done = data, out, done
        super().__init__(*args, directory=str(HERE), **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] != "/replay.json":
            return super().do_GET()
        body = self.data.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/gif":
            return self.send_error(404)
        size = int(self.headers.get("Content-Length", 0))
        Path(self.out).write_bytes(self.rfile.read(size))
        self.send_response(204)
        self.end_headers()
        self.done.set()

    def log_message(self, *args):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="council session .jsonl, or a replay .json from extract.py")
    parser.add_argument("-o", "--out", default="council-run.gif")
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--browser", help="path to a Chromium-based browser")
    parser.add_argument("--manual", action="store_true", help="don't launch a browser; print the URL")
    parser.add_argument("--timeout", type=int, default=300, help="seconds to wait for the GIF")
    args = parser.parse_args(argv)

    src = Path(args.source)
    data = src.read_text(encoding="utf-8") if src.suffix == ".json" else json.dumps(extract(src), ensure_ascii=False)
    done = threading.Event()
    handler = partial(Handler, data=data, out=args.out, done=done)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/replay.html?fps={args.fps}"

    browser = None if args.manual else (args.browser or find_browser())
    proc, profile = None, None
    if browser:
        profile = tempfile.mkdtemp(prefix="council-replay-")
        proc = subprocess.Popen(
            [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             "--hide-scrollbars", f"--user-data-dir={profile}", "--window-size=1000,700", base + "&export=1"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"recording with {Path(browser).name} ...")
    else:
        print(f"No browser launched. Open this URL and click Export GIF:\n  {base}&post=1")
    try:
        ok = done.wait(args.timeout if browser else None)
    except KeyboardInterrupt:
        ok = False
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
            shutil.rmtree(profile, ignore_errors=True)
        server.shutdown()
    if not ok:
        print("no GIF received", file=sys.stderr)
        return 1
    print(f"wrote {args.out} ({os.path.getsize(args.out) / 1048576:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
