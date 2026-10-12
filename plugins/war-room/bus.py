"""War Room bus: a SQLite-backed task and message board, served as an MCP stdio server.

Each claude worker gets its own server process (via --mcp-config); all of them share one
SQLite file in WAL mode, so claims and inbox reads are atomic across workers. The conductor
(warroom.py) and the hooks use the same Bus class directly.

Env: WARROOM_DB (path to bus.sqlite3), WARROOM_AGENT (this worker's name).
Run `python bus.py` to serve MCP on stdio. Standard library only.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, detail TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open', owner TEXT, result TEXT, assignee TEXT, updated REAL,
  kind TEXT NOT NULL DEFAULT 'work', parent INTEGER, author TEXT, commit_ref TEXT, score REAL,
  fails INTEGER NOT NULL DEFAULT 0, gate INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, sender TEXT, recipient TEXT NOT NULL,
  body TEXT NOT NULL, sent REAL, read REAL);
CREATE TABLE IF NOT EXISTS heartbeats (agent TEXT PRIMARY KEY, ts REAL, note TEXT);
CREATE TABLE IF NOT EXISTS checkpoints (id INTEGER PRIMARY KEY, agent TEXT, ts REAL, summary TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS control (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS workers (name TEXT PRIMARY KEY, role TEXT, kind TEXT, model TEXT, effort TEXT,
  session_id TEXT, cwd TEXT, argv TEXT, resume_argv TEXT, state TEXT, updated REAL);
CREATE TABLE IF NOT EXISTS meter (agent TEXT PRIMARY KEY, ts REAL, five_pct REAL, five_reset REAL,
  week_pct REAL, week_reset REAL, context_pct REAL, cost_usd REAL, transcript TEXT);
CREATE TABLE IF NOT EXISTS meter_log (id INTEGER PRIMARY KEY, agent TEXT, ts REAL, five_pct REAL, context_pct REAL,
  cost_usd REAL);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts REAL, agent TEXT, kind TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS merges (id INTEGER PRIMARY KEY, task_id INTEGER, worker TEXT, commit_ref TEXT,
  status TEXT NOT NULL DEFAULT 'queued', detail TEXT, ts REAL);
"""

# Task lifecycle with review gates:
#   open -> claimed -> (complete_task) -> review -> (verdict pass) -> approved -> (merge) -> merged
#                                        review -> (verdict fail) -> open again, assigned to the author
#   after max_fails failed reviews: arbitration by an arbiter worker, then blocked for the human orchestrator.
# A task with gate=0, or any task while gates are off, goes straight to done.
TIERS = ("haiku", "sonnet", "opus", "fable")


def tier(model):
    return next((t for t in TIERS if t in (model or "")), "opus")


def connect(path):
    db = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    db.executescript(SCHEMA)
    migrate(db)
    return db


# Columns added after the first release; a run created by an older War Room gains them on open.
MIGRATIONS = {"tasks": {"kind": "TEXT NOT NULL DEFAULT 'work'", "parent": "INTEGER", "author": "TEXT", "commit_ref": "TEXT",
                        "score": "REAL", "fails": "INTEGER NOT NULL DEFAULT 0", "gate": "INTEGER NOT NULL DEFAULT 1"}}


def migrate(db):
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols.items():
            if col not in have:
                try:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                except sqlite3.OperationalError as e:  # another process added it first
                    if "duplicate column" not in str(e):
                        raise


class Bus:
    def __init__(self, path, agent):
        self.db, self.agent = connect(path), agent

    def _tx(self, fn):
        # BEGIN IMMEDIATE takes the write lock up front: no lost updates between workers.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            out = fn()
            self.db.execute("COMMIT")
            return out
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    # ---- tools exposed to workers -------------------------------------------------------
    def post_task(self, title, detail="", assignee=None, gate=1):
        gate = 0 if str(gate).lower() in ("0", "false", "no") else 1
        if gate == 0 and (self._worker(self.agent) or {}).get("kind") == "builder":
            gate = 1  # writers cannot skip review by posting ungated work
        cur = self.db.execute("INSERT INTO tasks(title, detail, assignee, updated, gate) VALUES (?,?,?,?,?)",
                              (title, detail, assignee or None, time.time(), gate))
        self.event("task", f"posted #{cur.lastrowid} {title}")
        return {"id": cur.lastrowid}

    def claim_task(self):
        if self.control("claims") == "paused":
            return {"task": None, "paused": True, "note": "Claims are paused (usage limit guard). Checkpoint and stop."}

        def go():
            row = self.db.execute("SELECT * FROM tasks WHERE status='open' AND (assignee IS NULL OR assignee=?) "
                                  "ORDER BY assignee IS NULL, id LIMIT 1", (self.agent,)).fetchone()
            if not row:
                return {"task": None}
            self.db.execute("UPDATE tasks SET status='claimed', owner=?, updated=? WHERE id=?",
                            (self.agent, time.time(), row["id"]))
            return {"task": {"id": row["id"], "title": row["title"], "detail": row["detail"]}}
        out = self._tx(go)
        if out["task"]:
            self.event("claim", f"#{out['task']['id']} {out['task']['title']}")
        return out

    def _task(self, id):
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (id,)).fetchone()
        return dict(row) if row else None

    def _worker(self, name):
        row = self.db.execute("SELECT * FROM workers WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    def _policy(self):
        budget = json.loads(self.control("budget") or "{}")
        return {"gates": budget.get("gates", True), "score": budget.get("gate_score", 85),
                "max_fails": budget.get("max_fails", 2)}

    def pick_reviewer(self, author):
        """A reviewer worker other than the author, on a different model tier when possible; else the human."""
        me = self._worker(author) or {}
        others = [w for w in self.workers() if w["name"] != author and w["kind"] == "reviewer"]
        ranked = sorted(others, key=lambda w: (tier(w["model"]) == tier(me.get("model")), w["role"] == "arbiter"))
        return ranked[0]["name"] if ranked else "orchestrator"

    def complete_task(self, id, result, commit=None):
        t = self._task(id)
        if t and t["status"] == "open" and t["assignee"] == self.agent:  # a reopened task: claim it on the way
            self.db.execute("UPDATE tasks SET status='claimed', owner=? WHERE id=? AND status='open'", (self.agent, id))
            t = self._task(id)
        if not t or t["owner"] != self.agent or t["status"] != "claimed":
            return {"ok": False, "error": f"task #{id} is not claimed by you"}
        if t["kind"] == "review":
            return {"ok": False, "error": "this is a review task: call verdict(id, decision, score, notes) instead"}
        me, policy = self._worker(self.agent) or {}, self._policy()
        if not (policy["gates"] and t["gate"]):
            self.db.execute("UPDATE tasks SET status='done', result=?, author=?, updated=? WHERE id=?",
                            (result, self.agent, time.time(), id))
            self.event("done", f"#{id} {result[:200]}")
            return {"ok": True, "status": "done"}
        if me.get("kind") == "builder":
            commit = (commit or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                return {"ok": False, "error": "commit your work first and pass commit=<the full 40-character hash from: "
                                              "git rev-parse HEAD> (not a branch name or short hash)"}
            if me.get("cwd") and os.path.isdir(me["cwd"]) and subprocess.run(["git", "-C", me["cwd"], "cat-file", "-e", f"{commit}^{{commit}}"],
                                                capture_output=True).returncode != 0:
                return {"ok": False, "error": f"commit {commit[:12]} does not exist in your worktree"}
        reviewer = self.pick_reviewer(self.agent)
        where = f" in worktree {me['cwd']}" if me.get("kind") == "builder" and me.get("cwd") else ""

        def go():
            self.db.execute("UPDATE tasks SET status='review', result=?, author=?, commit_ref=?, updated=? WHERE id=?",
                            (result, self.agent, commit, time.time(), id))
            detail = (f"Review task #{id} '{t['title']}' by {self.agent}{where}.\n"
                      f"Commit: {commit or 'n/a (no code)'}\nAuthor's result: {result}\nTask detail: {t['detail']}\n"
                      f"Check the work against the task and run its tests, then call verdict with this review task's "
                      f"id, pass or fail, a score 0-100 and concrete notes. Pass needs score >= {policy['score']}.")
            cur = self.db.execute("INSERT INTO tasks(title, detail, assignee, kind, parent, updated) VALUES (?,?,?,?,?,?)",
                                  (f"Review #{id}: {t['title']}"[:200], detail, reviewer, "review", id, time.time()))
            return cur.lastrowid
        rid = self._tx(go)
        self.event("review", f"#{id} by {self.agent} -> review #{rid} for {reviewer}")
        if reviewer == "orchestrator":
            self.send("orchestrator", f"No reviewer worker is available: please review task #{id} (review task #{rid}).")
        return {"ok": True, "status": "review", "review_task": rid, "reviewer": reviewer}

    def verdict(self, id, decision, score=None, notes=""):
        """Close a review task. pass (score >= gate score) approves the work; fail sends it back to its author."""
        r = self._task(id)
        if r and r["kind"] != "review":  # also accept the reviewed task's id
            row = self.db.execute("SELECT * FROM tasks WHERE parent=? AND kind='review' AND status='claimed' AND owner=?",
                                  (id, self.agent)).fetchone()
            r = dict(row) if row else None
        if not r or r["owner"] != self.agent or r["status"] != "claimed":
            return {"ok": False, "error": f"no review task #{id} claimed by you"}
        if decision not in ("pass", "fail"):
            return {"ok": False, "error": "decision must be pass or fail"}
        policy, parent = self._policy(), self._task(r["parent"])
        if parent["author"] == self.agent:
            return {"ok": False, "error": "you cannot review your own work"}
        passed = decision == "pass" and (score is None or int(score) >= policy["score"])
        fails = parent["fails"] + (0 if passed else 1)
        arbiter = next((w["name"] for w in self.workers() if w["role"] == "arbiter"
                        and w["name"] not in (self.agent, parent["author"])), None)
        note = f"{decision} score={score} {notes}".strip()

        def go():
            self.db.execute("UPDATE tasks SET status='done', result=?, score=?, updated=? WHERE id=?",
                            (note, score, time.time(), r["id"]))
            if passed:
                self.db.execute("UPDATE tasks SET status=?, score=?, updated=? WHERE id=?",
                                ("approved" if parent["commit_ref"] else "done", score, time.time(), parent["id"]))
                if parent["commit_ref"]:
                    self.db.execute("INSERT INTO merges(task_id, worker, commit_ref, ts) VALUES (?,?,?,?)",
                                    (parent["id"], parent["author"], parent["commit_ref"], time.time()))
                return "approved"
            if fails == policy["max_fails"] and arbiter and not r["title"].startswith("Arbitrate"):
                self.db.execute("UPDATE tasks SET fails=?, updated=? WHERE id=?", (fails, time.time(), parent["id"]))
                self.db.execute("INSERT INTO tasks(title, detail, assignee, kind, parent, updated) VALUES (?,?,?,?,?,?)",
                                (f"Arbitrate #{parent['id']}: {parent['title']}"[:200],
                                 f"Reviews failed task #{parent['id']} {fails} times. Latest notes: {notes}\n{r['detail']}",
                                 arbiter, "review", parent["id"], time.time()))
                return "arbitration"
            if fails >= policy["max_fails"]:
                self.db.execute("UPDATE tasks SET status='blocked', fails=?, updated=? WHERE id=?",
                                (fails, time.time(), parent["id"]))
                return "blocked"
            self.db.execute("UPDATE tasks SET status='open', owner=NULL, assignee=?, fails=?, updated=? WHERE id=?",
                            (parent["author"], fails, time.time(), parent["id"]))
            return "reopened"
        outcome = self._tx(go)
        self.event("verdict", f"#{parent['id']} {outcome} ({note[:150]})")
        if outcome == "reopened":
            self.send(parent["author"], f"Review failed for task #{parent['id']} (attempt {fails}): {notes} "
                                        "It is back on the board for you: fix, commit, complete it again.")
        elif outcome == "blocked":
            self.send("orchestrator", f"Task #{parent['id']} failed review {fails} times and needs your decision "
                                      f"(warroom.py approve <run> {parent['id']}, or --reject). Latest notes: {notes}")
        return {"ok": True, "outcome": outcome}

    def decide(self, id, approve, notes=""):
        """Human orchestrator decision on a blocked (or any) task."""
        t = self._task(id)
        if not t:
            return {"ok": False, "error": f"no task #{id}"}
        if approve:
            self.db.execute("UPDATE tasks SET status=?, updated=? WHERE id=?",
                            ("approved" if t["commit_ref"] else "done", time.time(), id))
            if t["commit_ref"]:
                self.db.execute("INSERT INTO merges(task_id, worker, commit_ref, ts) VALUES (?,?,?,?)",
                                (id, t["author"], t["commit_ref"], time.time()))
        else:
            who = t["author"] or t["assignee"]
            self.db.execute("UPDATE tasks SET status='open', owner=NULL, assignee=?, updated=? WHERE id=?",
                            (who, time.time(), id))
            if who:
                self.send(who, f"The orchestrator rejected task #{id}: {notes} Fix and complete it again.")
        self.event("decision", f"#{id} {'approved' if approve else 'rejected'} by orchestrator {notes[:120]}")
        return {"ok": True}

    def send(self, to, body):
        cur = self.db.execute("INSERT INTO messages(sender, recipient, body, sent) VALUES (?,?,?,?)",
                              (self.agent, to, body, time.time()))
        self.event("message", f"to {to}: {body[:200]}")
        return {"id": cur.lastrowid}

    def inbox(self):
        def go():
            rows = self.db.execute("SELECT id, sender, body FROM messages WHERE recipient=? AND read IS NULL ORDER BY id",
                                   (self.agent,)).fetchall()
            self.db.executemany("UPDATE messages SET read=? WHERE id=?", [(time.time(), r["id"]) for r in rows])
            return {"messages": [dict(r) for r in rows]}
        return self._tx(go)

    def peek_inbox(self):
        rows = self.db.execute("SELECT id, sender, body FROM messages WHERE recipient=? AND read IS NULL ORDER BY id",
                               (self.agent,)).fetchall()
        return [dict(r) for r in rows]

    def mark_read(self, ids):
        self.db.executemany("UPDATE messages SET read=? WHERE id=? AND read IS NULL", [(time.time(), i) for i in ids])

    def heartbeat(self, note=""):
        self.db.execute("INSERT OR REPLACE INTO heartbeats VALUES (?,?,?)", (self.agent, time.time(), note))
        return {"ok": True}

    def checkpoint(self, summary):
        """Durable progress note: done / next / open questions. Survives a usage-limit stop."""
        self.db.execute("INSERT INTO checkpoints(agent, ts, summary) VALUES (?,?,?)", (self.agent, time.time(), summary))
        self.event("checkpoint", summary[:200])
        return {"ok": True}

    def last_checkpoint(self, agent=None):
        row = self.db.execute("SELECT ts, summary FROM checkpoints WHERE agent=? ORDER BY id DESC LIMIT 1",
                              (agent or self.agent,)).fetchone()
        return {"checkpoint": dict(row) if row else None}

    def board(self):
        rows = self.db.execute("SELECT id, title, kind, status, owner, assignee, author, commit_ref, score, result "
                               "FROM tasks ORDER BY id").fetchall()
        return {"tasks": [dict(r) for r in rows]}

    # ---- conductor and hook helpers -----------------------------------------------------
    def control(self, key, value=None, clear=False):
        if clear:
            self.db.execute("DELETE FROM control WHERE key=?", (key,))
        elif value is not None:
            self.db.execute("INSERT OR REPLACE INTO control VALUES (?,?)", (key, str(value)))
        row = self.db.execute("SELECT value FROM control WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def event(self, kind, detail=""):
        self.db.execute("INSERT INTO events(ts, agent, kind, detail) VALUES (?,?,?,?)", (time.time(), self.agent, kind, detail))

    def unread(self, agent):
        return self.db.execute("SELECT COUNT(*) FROM messages WHERE recipient=? AND read IS NULL", (agent,)).fetchone()[0]

    def open_tasks(self, agent):
        return self.db.execute("SELECT COUNT(*) FROM tasks WHERE status='open' AND (assignee IS NULL OR assignee=?)",
                               (agent,)).fetchone()[0]

    def claimed_by(self, agent):
        return [dict(r) for r in self.db.execute(
            "SELECT id, title, detail FROM tasks WHERE status='claimed' AND owner=?", (agent,))]

    def put_worker(self, **w):
        w["updated"] = time.time()
        cols = ",".join(w)
        self.db.execute(f"INSERT OR REPLACE INTO workers({cols}) VALUES ({','.join('?' * len(w))})", list(w.values()))

    def update_worker(self, name, **fields):
        sets = ",".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE workers SET {sets}, updated=? WHERE name=?", [*fields.values(), time.time(), name])

    def workers(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM workers ORDER BY rowid")]

    def put_meter(self, **m):
        m["agent"], m["ts"] = self.agent, time.time()
        cols = ",".join(m)
        self.db.execute(f"INSERT OR REPLACE INTO meter({cols}) VALUES ({','.join('?' * len(m))})", list(m.values()))
        last = self.db.execute("SELECT max(ts) FROM meter_log WHERE agent=?", (self.agent,)).fetchone()[0]
        if not last or m["ts"] - last >= 20:  # usage history for the cost panel, one sample per 20 s per worker
            self.db.execute("INSERT INTO meter_log(agent, ts, five_pct, context_pct, cost_usd) VALUES (?,?,?,?,?)",
                            (self.agent, m["ts"], m.get("five_pct"), m.get("context_pct"), m.get("cost_usd")))


def _schema(props, required=()):
    return {"type": "object", "properties": {k: {"type": "string" if v == "s" else "integer"} for k, v in props.items()},
            "required": list(required)}


TOOLS = {
    "post_task": ("Add a task to the shared board, optionally for a named worker. gate 0 skips review (planning, notes).",
                  _schema({"title": "s", "detail": "s", "assignee": "s", "gate": "i"}, ["title"])),
    "claim_task": ("Atomically claim your next open task (assigned to you first). Returns task null when none, "
                   "or paused true when the usage guard paused claims.", _schema({})),
    "complete_task": ("Finish a task you own with a short result. Writers must commit first and pass commit (from git "
                      "rev-parse HEAD). Gated work goes to review by another worker before it counts as done.",
                      _schema({"id": "i", "result": "s", "commit": "s"}, ["id", "result"])),
    "verdict": ("Close a review task you claimed: decision pass or fail, score 0-100 (pass needs the gate score, "
                "default 85), and concrete notes. A fail sends the work back to its author with your notes.",
                _schema({"id": "i", "decision": "s", "score": "i", "notes": "s"}, ["id", "decision", "notes"])),
    "send": ("Send a message to another worker by name, or to 'orchestrator'.", _schema({"to": "s", "body": "s"}, ["to", "body"])),
    "inbox": ("Read and consume your unread messages.", _schema({})),
    "heartbeat": ("Report that you are alive and what you are doing.", _schema({"note": "s"})),
    "checkpoint": ("Save a durable progress note (done / next / open questions). Call after every meaningful step.",
                   _schema({"summary": "s"}, ["summary"])),
    "last_checkpoint": ("Read your latest checkpoint, e.g. after a resume.", _schema({})),
    "board": ("List every task on the board with status, owner and result.", _schema({})),
}


def serve(bus, stdin=sys.stdin, stdout=sys.stdout):
    def reply(id, result=None, error=None):
        msg = {"jsonrpc": "2.0", "id": id}
        msg.update({"error": error} if error else {"result": result})
        stdout.write(json.dumps(msg) + "\n")
        stdout.flush()

    for line in stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue  # not JSON-RPC: ignore rather than kill the server
        method, id, params = req.get("method"), req.get("id"), req.get("params") or {}
        if id is None:  # notification, e.g. notifications/initialized
            continue
        if method == "initialize":
            reply(id, {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                       "capabilities": {"tools": {}}, "serverInfo": {"name": "war-room-bus", "version": "0.1.0"}})
        elif method == "ping":
            reply(id, {})
        elif method == "tools/list":
            reply(id, {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s) in TOOLS.items()]})
        elif method == "tools/call":
            name, args = params.get("name"), params.get("arguments") or {}
            if name not in TOOLS:
                reply(id, error={"code": -32602, "message": f"unknown tool {name}"})
                continue
            try:
                out = getattr(bus, name)(**args)
                reply(id, {"content": [{"type": "text", "text": json.dumps(out)}]})
            except Exception as e:  # report tool failures to the model instead of crashing the server
                reply(id, {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True})
        else:
            reply(id, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8", errors="replace")  # Windows defaults to the ANSI code page
    serve(Bus(os.environ["WARROOM_DB"], os.environ.get("WARROOM_AGENT", "anonymous")))
