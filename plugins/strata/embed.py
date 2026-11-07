#!/usr/bin/env python3
"""Meaning-based search for strata: L1 notes and L2 scenes get embeddings from a local Ollama model, and
`strata.py search` blends them with the keyword (BM25) results, so "car broke down" finds a note about a "vehicle
failure". Standard library only: Ollama is called over HTTP on this machine, nothing leaves it.

On by default and silent without Ollama: search stays keyword-only. Off with `embed off` or STRATA_SEMANTIC=off.
STRATA_OLLAMA_URL moves the server (default http://127.0.0.1:11434); `embed model NAME` picks the model
(default nomic-embed-text, pulled with `ollama pull nomic-embed-text`).

  python embed.py status | on | off | model NAME | index [--limit N] | reindex
"""
import argparse
from array import array
import json
import math
import os
import sys
import time
import urllib.request

import strata

TABLE = """CREATE TABLE IF NOT EXISTS vec (layer TEXT, id INTEGER, model TEXT, v BLOB, PRIMARY KEY(layer, id))"""
RRF_K = 60  # reciprocal rank fusion: a result's score is the sum of 1/(K + rank) over the lists it appears in


def settings():
    cfg = strata.config()
    on = cfg["semantic"] and os.environ.get("STRATA_SEMANTIC", "").lower() not in strata.OFF
    return on, cfg["embed_model"], os.environ.get("STRATA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


def embed(texts, model, url, timeout=60):  # a cold model takes ~20 s to load
    """Vectors for texts, or None when Ollama is not running or lacks the model. nomic-style models want a task prefix."""
    try:
        body = json.dumps({"model": model, "input": texts, "truncate": True}).encode()
        req = urllib.request.Request(url + "/api/embed", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read())["embeddings"]
        return out if len(out) == len(texts) else None
    except (OSError, ValueError, KeyError):
        return None


def prefixed(text, model, kind):
    return f"search_{kind}: {text}" if "nomic" in model else text


def ensure(db, model, url, limit=64):
    """Embed up to `limit` live notes and scenes that have no vector for this model yet. Returns how many."""
    db.execute(TABLE)
    todo = db.execute(
        "SELECT 'L1', a.id, a.text FROM atoms a LEFT JOIN vec v ON v.layer='L1' AND v.id=a.id AND v.model=? "
        "WHERE a.superseded_by IS NULL AND v.id IS NULL UNION ALL "
        "SELECT 'L2', s.id, s.title || ': ' || s.body FROM scenes s LEFT JOIN vec v ON v.layer='L2' AND v.id=s.id "
        "AND v.model=? WHERE v.id IS NULL LIMIT ?", (model, model, limit)).fetchall()
    done = 0
    for i in range(0, len(todo), 16):
        batch = todo[i:i + 16]
        vecs = embed([prefixed(t[2], model, "document") for t in batch], model, url)
        if vecs is None:
            break
        with db:
            db.executemany("INSERT OR REPLACE INTO vec VALUES (?,?,?,?)",
                           [(t[0], t[1], model, unit(v).tobytes()) for t, v in zip(batch, vecs)])
        done += len(batch)
    return done


def unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return array("f", (x / n for x in v))


def nearest(db, qv, model, project, limit):
    """(layer, id, similarity) of the closest live notes and scenes in scope.
    ponytail: a linear scan in Python, fine for a few thousand notes; an ANN index if memory grows past ~50k."""
    scope = "" if project is None else " AND (t.project=? OR t.project='')"
    args = [model] + ([] if project is None else [project])
    rows = db.execute(
        "SELECT 'L1' AS layer, t.id, v.v FROM vec v JOIN atoms t ON v.layer='L1' AND t.id=v.id "
        "WHERE v.model=? AND t.superseded_by IS NULL" + scope, args).fetchall()
    rows += db.execute(
        "SELECT 'L2' AS layer, t.id, v.v FROM vec v JOIN scenes t ON v.layer='L2' AND t.id=v.id WHERE v.model=?"
        + scope.replace(" OR t.project=''", ""), args).fetchall()
    q = unit(qv)
    scored = []
    for layer, rid, blob in rows:
        v = array("f")
        v.frombytes(blob)
        if len(v) == len(q):
            scored.append((layer, rid, sum(a * b for a, b in zip(q, v))))
    scored.sort(key=lambda r: -r[2])
    return scored[:limit]


def blend(db, query, project, keyword_rows, limit, min_sim=0.5):
    """Keyword rows fused with meaning matches (reciprocal rank fusion). Keyword rows alone when search is off,
    Ollama is down or the model is missing."""
    on, model, url = settings()
    if not on:
        return keyword_rows[:limit]
    try:
        qv = embed([prefixed(query, model, "query")], model, url, timeout=30)  # fails at once without Ollama
        if not qv:
            return keyword_rows[:limit]
        ensure(db, model, url)
        near = [n for n in nearest(db, qv[0], model, project, limit * 2) if n[2] >= min_sim]
    except Exception:  # meaning search is an extra; a fault in it never costs the keyword results
        return keyword_rows[:limit]
    score, row = {}, {}
    for rank, r in enumerate(keyword_rows):
        key = (r["layer"], r["id"])
        score[key] = score.get(key, 0) + 1 / (RRF_K + rank)
        row[key] = r
    for rank, (layer, rid, sim) in enumerate(near):
        key = (layer, rid)
        score[key] = score.get(key, 0) + 1 / (RRF_K + rank)
        if key not in row:
            sql = ("SELECT id, project, kind AS label, text FROM atoms WHERE id=?" if layer == "L1" else
                   "SELECT id, project, title AS label, body AS text FROM scenes WHERE id=?")
            got = db.execute(sql, (rid,)).fetchone()
            if got:
                row[key] = {"layer": layer, **dict(got), "rank": 0.0, "similarity": round(sim, 3)}
    return [row[k] for k in sorted(row, key=lambda k: -score[k])][:limit]


def status(db):
    on, model, url = settings()
    db.execute(TABLE)
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=3) as r:
            names = [m["name"] for m in json.loads(r.read()).get("models", [])]
        server = "running"
    except (OSError, ValueError):
        names, server = [], "not reachable"
    has = any(n == model or n.split(":")[0] == model for n in names)
    count = lambda sql: db.execute(sql, (model,)).fetchone()[0]  # noqa: E731
    return {"semantic": on, "model": model, "ollama": f"{server} at {url}", "model_installed": has,
            "embedded_notes": count("SELECT COUNT(*) FROM vec WHERE layer='L1' AND model=?"),
            "embedded_scenes": count("SELECT COUNT(*) FROM vec WHERE layer='L2' AND model=?"),
            "hint": None if has else f"ollama pull {model}   (until then search stays keyword-only)"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=("status", "on", "off", "model", "index", "reindex"))
    p.add_argument("value", nargs="?")
    p.add_argument("--limit", type=int, default=100000)
    a = p.parse_args(argv)
    db = strata.connect()
    cfg = strata.config()
    if a.cmd in ("on", "off"):
        cfg["semantic"] = a.cmd == "on"
        strata.save_config(cfg)
    elif a.cmd == "model":
        if not a.value:
            p.error("model NAME")
        cfg["embed_model"] = a.value
        strata.save_config(cfg)
    elif a.cmd in ("index", "reindex"):
        _, model, url = settings()
        if a.cmd == "reindex":
            db.execute(TABLE)
            with db:
                db.execute("DELETE FROM vec WHERE model=?", (model,))
        t = time.time()
        n = ensure(db, model, url, a.limit)
        print(json.dumps({"embedded": n, "seconds": round(time.time() - t, 1)}))
        return 0
    print(json.dumps(status(db), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
