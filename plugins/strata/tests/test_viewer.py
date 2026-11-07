"""Read-only memory viewer: python -m unittest discover -s tests"""
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import strata as memory  # noqa: E402
import viewer  # noqa: E402


class Viewer(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        env = mock.patch.dict(os.environ, {"MOAA_STRATA_DIR": self.dir, "STRATA_VAULT": "off", "STRATA_SEMANTIC": "off"})
        env.start()
        self.addCleanup(env.stop)
        db = memory.connect()
        with db:
            db.execute("INSERT INTO atoms(project, kind, text, session, created) VALUES "
                       "('proj-a','fact','Deploys go out on Friday <script>alert(1)</script>','s',0)")
            db.execute("INSERT INTO profile VALUES ('style','short replies',0)")
        db.close()
        self.server = viewer.serve(0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return r.read().decode(), r.headers

    def test_home_project_and_search_render_escaped(self):
        html, headers = self.get("/")
        self.assertIn("proj-a", html)
        self.assertIn("short replies", html)
        self.assertIn("script-src", headers["Content-Security-Policy"].replace("default-src 'none'", "script-src"))
        html, _ = self.get("/project?p=proj-a")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        html, _ = self.get("/search?q=friday+deploys")
        self.assertIn("1 result(s)", html)

    def test_unknown_path_is_404_and_only_local_binds(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/../memory.sqlite3")
        with self.assertRaises(SystemExit):
            viewer.serve(0, host="0.0.0.0")


if __name__ == "__main__":
    unittest.main()
