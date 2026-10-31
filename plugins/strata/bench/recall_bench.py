#!/usr/bin/env python3
"""Recall benchmark for strata search, in the LongMemEval format (Wu et al. 2024; the method mempalace reports).

  python bench/recall_bench.py --data longmemeval_s.json [--limit N] [--k 5,10] [--out results.json]

Retrieval only: no model is called, so it costs nothing. For each question, its haystack sessions go into a fresh
strata database as L0 messages (one session per haystack session), `strata.search` runs the question, and a hit counts
when one of the top k rows comes from an evidence session (`answer_session_ids`). It prints recall@k per question type
and overall. The dataset is not shipped: download LongMemEval (MIT) yourself and pass the JSON file.

Each item: {"question_id", "question_type", "question", "haystack_session_ids": [...],
            "haystack_sessions": [[{"role", "content"}, ...], ...], "answer_session_ids": [...]}
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(items, ks=(5, 10)):
    import strata
    per_type, rows = {}, []
    for item in items:
        with tempfile.TemporaryDirectory() as d:
            os.environ["MOAA_STRATA_DIR"] = d
            db = strata.connect()
            with db:
                for n, (sid, turns) in enumerate(zip(item["haystack_session_ids"], item["haystack_sessions"])):
                    db.execute("INSERT INTO sessions(id, project, ended, chars) VALUES (?, 'bench', ?, 0)", (sid, n))
                    db.executemany("INSERT OR IGNORE INTO l0(session, project, ts, role, text) VALUES (?, 'bench', ?, ?, ?)",
                                   [(sid, n + i / 1000, t["role"], t["content"]) for i, t in enumerate(turns)])
            hits = strata.search(db, item["question"], "bench", limit=max(ks))
            found = [db.execute("SELECT session FROM l0 WHERE id=?", (h["id"],)).fetchone()[0]
                     for h in hits if h["layer"] == "L0"]
            db.close()
        gold = set(item["answer_session_ids"])
        row = {"id": item["question_id"], "type": item.get("question_type", "all"),
               **{f"r@{k}": int(bool(gold & set(found[:k]))) for k in ks}}
        rows.append(row)
        per_type.setdefault(row["type"], []).append(row)
    summary = {t: {f"r@{k}": round(sum(r[f"r@{k}"] for r in rs) / len(rs), 3) for k in ks} | {"n": len(rs)}
               for t, rs in sorted(per_type.items())}
    summary["overall"] = {f"r@{k}": round(sum(r[f"r@{k}"] for r in rows) / max(len(rows), 1), 3) for k in ks} | \
        {"n": len(rows)}
    return summary, rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", required=True); p.add_argument("--limit", type=int, default=0)
    p.add_argument("--k", default="5,10"); p.add_argument("--out")
    a = p.parse_args(argv)
    items = json.loads(Path(a.data).read_text(encoding="utf-8"))
    items = [i for i in items if i.get("answer_session_ids")][: a.limit or None]  # abstention items have no evidence
    summary, rows = run(items, tuple(int(k) for k in a.k.split(",")))
    for t, s in summary.items():
        print(f"{t:<28} n={s['n']:<4} " + "  ".join(f"{k} {v:.3f}" for k, v in s.items() if k != "n"))
    if a.out:
        Path(a.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
