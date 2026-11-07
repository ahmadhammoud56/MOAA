"""Meaning search (embed.py) against a fake Ollama server: python -m unittest discover -s tests"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import embed  # noqa: E402
import strata as memory  # noqa: E402

# Each concept is one axis; synonyms land on the same axis, so a fake model "understands" them.
CONCEPTS = [("car", "vehicle", "truck"), ("broke", "failure", "broken", "crash"), ("pizza", "lunch", "food"),
            ("deploy", "release", "ship")]


def vector(text):
    words = text.lower().replace(":", " ").split()
    return [float(sum(w.strip(".,") in group for w in words)) + 0.01 for group in CONCEPTS]


class Fake(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Fake.calls.append(body)
        out = json.dumps({"embeddings": [vector(t) for t in body["input"]]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        out = json.dumps({"models": [{"name": "nomic-embed-text:latest"}]}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


class Semantic(unittest.TestCase):
    def setUp(self):
        Fake.calls = []
        self.server = HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.dir = tempfile.mkdtemp()
        env = mock.patch.dict(os.environ, {"MOAA_STRATA_DIR": self.dir, "STRATA_VAULT": "off",
                                           "STRATA_OLLAMA_URL": f"http://127.0.0.1:{self.server.server_port}"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("STRATA_SEMANTIC", None)
        self.db = memory.connect()
        self.addCleanup(self.db.close)
        with self.db:
            for text in ("The vehicle had a failure on the highway", "Team ordered pizza for lunch",
                         "Release goes out on Friday"):
                self.db.execute("INSERT INTO atoms(project, kind, text, session, created) VALUES ('p','fact',?,'s',0)",
                                (text,))

    def test_meaning_match_without_shared_words(self):
        rows = memory.search(self.db, "my car broke down", "p", limit=3)
        self.assertTrue(rows, "keyword search alone finds nothing here")
        self.assertIn("vehicle", rows[0]["text"])
        self.assertEqual(rows[0]["layer"], "L1")

    def test_notes_are_embedded_once_with_the_document_prefix(self):
        memory.search(self.db, "car broke", "p")
        memory.search(self.db, "car broke", "p")
        docs = [t for c in Fake.calls for t in c["input"] if t.startswith("search_document: ")]
        self.assertEqual(len(docs), 3)
        self.assertEqual(embed.status(self.db)["embedded_notes"], 3)

    def test_keyword_only_when_ollama_is_down_or_off(self):
        with mock.patch.dict(os.environ, {"STRATA_OLLAMA_URL": "http://127.0.0.1:9"}):
            self.assertEqual(memory.search(self.db, "my car broke down", "p"), [])
            self.assertEqual(memory.search(self.db, "pizza", "p")[0]["text"], "Team ordered pizza for lunch")
        with mock.patch.dict(os.environ, {"STRATA_SEMANTIC": "off"}):
            self.assertEqual(memory.search(self.db, "my car broke down", "p"), [])

    def test_superseded_and_other_projects_are_left_out(self):
        with self.db:
            self.db.execute("UPDATE atoms SET superseded_by=99 WHERE text LIKE 'The vehicle%'")
            self.db.execute("INSERT INTO atoms(project, kind, text, session, created) VALUES "
                            "('other','fact','Truck crash report','s',0)")
        rows = memory.search(self.db, "my car broke down", "p")
        self.assertFalse(any("vehicle" in r["text"] or "Truck" in r["text"] for r in rows))


if __name__ == "__main__":
    unittest.main()
