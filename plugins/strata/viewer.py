#!/usr/bin/env python3
"""A read-only web page for strata's memory: profile, projects, notes, scenes and search (meaning search too when
embed.py is on). Standard library only; it listens on this machine only (127.0.0.1) and changes nothing.

  python viewer.py [--port 37778] [--open]        then browse http://127.0.0.1:37778
"""
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
import time
from urllib.parse import parse_qs, quote, urlparse
import webbrowser

import strata

STYLE = """
:root{--bg:#fbfaf7;--fg:#1f1d1a;--dim:#6b665e;--card:#fff;--line:#e4e0d8;--acc:#b4532a}
@media (prefers-color-scheme:dark){:root{--bg:#171614;--fg:#ece8e1;--dim:#9b958b;--card:#201f1c;--line:#34312c;--acc:#e0875a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px}a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:16px}
h1{font-size:20px;margin:0}h2{font-size:16px;margin:24px 0 8px}
form{display:flex;gap:8px;flex:1;min-width:240px;max-width:520px}
input{flex:1;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}
button{padding:8px 14px;border:0;border-radius:8px;background:var(--acc);color:#fff;cursor:pointer}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:6px 0}
.meta{color:var(--dim);font-size:13px}.tag{display:inline-block;padding:0 6px;border-radius:6px;border:1px solid var(--line);
font-size:12px;margin-right:6px;color:var(--dim)}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px}
.num{font-size:22px;font-weight:600}pre{white-space:pre-wrap;margin:4px 0 0;font:inherit}
"""


def page(title, body, q=""):
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'><title>{escape(title)}</title><style>{STYLE}</style></head><body><main><header>"
            f"<h1><a href='/'>Strata memory</a></h1><form action='/search'><input name=q value='{escape(q)}' "
            f"placeholder='Search notes, scenes and messages' aria-label=Search><button>Search</button></form></header>"
            f"{body}</main></body></html>")


def card(label, text, meta=""):
    return (f"<div class=card><span class=tag>{escape(str(label))}</span><span class=meta>{escape(meta)}</span>"
            f"<pre>{escape(text)}</pre></div>")


def when(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts)) if ts else ""


def home(db):
    n = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731
    stats = [("sessions", n("SELECT COUNT(*) FROM sessions")), ("notes", n("SELECT COUNT(*) FROM atoms WHERE superseded_by IS NULL")),
             ("scenes", n("SELECT COUNT(*) FROM scenes")), ("messages", n("SELECT COUNT(*) FROM l0")),
             ("profile traits", n("SELECT COUNT(*) FROM profile"))]
    body = "<div class=grid>" + "".join(f"<div class=card><div class=num>{v}</div><div class=meta>{k}</div></div>"
                                        for k, v in stats) + "</div>"
    projects = db.execute("SELECT project, COUNT(*) c, MAX(created) t FROM atoms WHERE superseded_by IS NULL "
                          "GROUP BY project ORDER BY t DESC").fetchall()
    body += "<h2>Projects</h2>" + "".join(
        f"<div class=card><a href='/project?p={quote(r['project'])}'>{escape(r['project'] or '(all projects)')}</a>"
        f" <span class=meta>{r['c']} notes, last {when(r['t'])}</span></div>" for r in projects)
    body += "<h2>Profile</h2>" + "".join(card(r["key"], r["text"], when(r["updated"]))
                                         for r in db.execute("SELECT * FROM profile ORDER BY updated DESC"))
    return page("Strata memory", body)


def project(db, p):
    body = f"<h2>{escape(p or '(all projects)')}</h2><h2>Scenes</h2>" + "".join(
        card(r["title"], r["body"], when(r["updated"]))
        for r in db.execute("SELECT * FROM scenes WHERE project=? ORDER BY updated DESC", (p,)))
    body += "<h2>Notes</h2>" + "".join(
        card(r["kind"], r["text"], f"#{r['id']} · {when(r['created'])}")
        for r in db.execute("SELECT * FROM atoms WHERE project=? AND superseded_by IS NULL ORDER BY created DESC "
                            "LIMIT 500", (p,)))
    return page(p or "Strata", body)


def search(db, q):
    rows = strata.search(db, q, None, limit=30) if q.strip() else []
    body = f"<h2>{len(rows)} result(s)</h2>" + "".join(
        card(f"{r['layer']} {r['label']}", r["text"][:2000],
             f"#{r['id']} · {r['project'] or 'all projects'}" + (f" · meaning {r['similarity']}" if "similarity" in r else ""))
        for r in rows)
    return page(f"Search: {q}", body, q)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        args = {k: v[0] for k, v in parse_qs(url.query).items()}
        db = strata.connect()
        try:
            if url.path == "/":
                html = home(db)
            elif url.path == "/project":
                html = project(db, args.get("p", ""))
            elif url.path == "/search":
                html = search(db, args.get("q", ""))
            else:
                self.send_error(404)
                return
        finally:
            db.close()
        out = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")  # no scripts at all
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def serve(port, host="127.0.0.1"):
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("viewer: memory holds your chats; it only listens on this machine")
    return ThreadingHTTPServer((host, port), Handler)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=37778)
    p.add_argument("--open", action="store_true", help="open it in the browser")
    a = p.parse_args(argv)
    server = serve(a.port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"strata viewer: {url}  (Ctrl+C stops it)")
    if a.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
