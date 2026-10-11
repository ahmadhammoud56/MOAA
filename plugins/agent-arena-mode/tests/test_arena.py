import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "arena.py"
spec = importlib.util.spec_from_file_location("arena", SCRIPT)
arena = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arena)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        self.task = self.root / "task.md"
        self.task.write_text("Return a useful answer with checked evidence.", encoding="utf-8")
        self.rubric = self.root / "rubric.json"
        self.rubric.write_text(json.dumps({"weights": arena.WEIGHTS, "gates": {"check": "Observed passing check"}}), encoding="utf-8")
        self.state = arena.init_run(self.run, self.task, self.rubric, agents=4, mode="league")

    def tearDown(self):
        self.temp.cleanup()

    def add(self, cid, parents=()):
        source = self.root / f"{cid}.md"
        source.write_text(f"Answer {cid}", encoding="utf-8")
        return arena.add_candidate(self.run, self.state, cid, source, parents)

    def report(self, cid, value=8, gate="pass", fatal=False, judge="judge-1"):
        return {"candidate": cid, "sha256": self.state["candidates"][cid]["sha256"],
                "judge": judge, "scores": {k: value for k in arena.WEIGHTS},
                "gates": {"check": {"status": gate, "evidence": "Observed check log"}},
                "fatal": fatal, "findings": ["Verified central failure"] if fatal else [],
                "rationale": "The checks support this assessment."}

    def test_all_modes_plan_and_seeded_diversity(self):
        for index, mode in enumerate(arena.MODES, 1):
            p = arena.plan(str(index), 100)
            self.assertEqual(p["mode"], mode)
            self.assertGreater(p["suggested_max_calls"], p["estimated_calls"])
        self.assertEqual(arena.plan("judge")["estimated_calls"], 115)
        self.assertEqual(arena.plan("tournament")["estimated_calls"], 596)
        cards = arena.strategy_cards(100, 42)
        self.assertEqual(cards, arena.strategy_cards(100, 42))
        self.assertEqual(len({(c["lens"], c["approach"], c["priority"]) for c in cards}), 100)

    def test_init_refuses_overwrite_and_invalid_configuration(self):
        with self.assertRaises(arena.ArenaError):
            arena.init_run(self.run, self.task, self.rubric)
        for kwargs in ({"agents": 1}, {"max_calls": 0}, {"threshold": float("nan")}, {"max_minutes": 0}):
            with self.assertRaises(arena.ArenaError):
                arena.init_run(self.root / "bad", self.task, self.rubric, **kwargs)
            self.assertFalse((self.root / "bad").exists())

    def test_budget_concurrency_failure_and_idempotent_finish(self):
        self.state["config"].update(max_calls=2, concurrency=1)
        first = arena.reserve(self.state, "worker", "generate")
        with self.assertRaises(arena.ArenaError):
            arena.reserve(self.state, "worker", "exceeds concurrency")
        arena.finish(self.state, first["job"], "failed", "runtime failure")
        arena.finish(self.state, first["job"], "failed", "runtime failure")
        with self.assertRaises(arena.ArenaError):
            arena.finish(self.state, first["job"], "done", "contradiction")
        second = arena.reserve(self.state, "worker", "retry")
        arena.finish(self.state, second["job"], "done", "runtime ID and output path")
        with self.assertRaises(arena.ArenaError):
            arena.reserve(self.state, "judge", "over budget")

    def test_deadline_survives_reload(self):
        self.state["created"] = 0
        arena.atomic_json(self.run / "state.json", self.state)
        recovered = arena.load(self.run)
        with self.assertRaises(arena.ArenaError):
            arena.reserve(recovered, "worker", "too late")

    def test_snapshots_lineage_and_traversal(self):
        self.add("parent")
        self.add("child", ["parent"])
        self.assertEqual(self.state["candidates"]["child"]["parents"], ["parent"])
        with self.assertRaises(arena.ArenaError):
            self.add("orphan", ["missing"])
        with self.assertRaises(arena.ArenaError):
            arena.add_candidate(self.run, self.state, "../escape", self.task)
        with self.assertRaises(arena.ArenaError):
            self.add("parent")
        (self.run / "artifacts" / "parent.md").write_text("tampered")
        with self.assertRaises(arena.ArenaError):
            arena.current_candidate(self.run, self.state, "parent")

    def test_rubric_and_task_are_frozen(self):
        (self.run / "task.md").write_text("changed")
        with self.assertRaises(arena.ArenaError):
            arena.load(self.run)
        (self.run / "task.md").write_bytes(self.task.read_bytes())
        (self.run / "rubric.json").write_text("{}")
        with self.assertRaises(arena.ArenaError):
            arena.load(self.run)

    def test_invalid_scores_are_rejected_not_clamped(self):
        self.add("a")
        for value in (True, "8", float("nan"), float("inf"), -1, 11):
            report = self.report("a")
            report["scores"]["correctness"] = value
            with self.assertRaises(arena.ArenaError):
                arena.assess(self.run, self.state, report)
        report = self.report("a")
        del report["scores"]["coverage"]
        with self.assertRaises(arena.ArenaError):
            arena.assess(self.run, self.state, report)

    def test_assessments_require_all_gates_evidence_and_current_hash(self):
        self.add("a")
        for field, value in (("gates", {}), ("fatal", "false"), ("sha256", "stale"), ("rationale", "")):
            report = self.report("a")
            report[field] = value
            with self.assertRaises(arena.ArenaError):
                arena.assess(self.run, self.state, report)
        report = self.report("a")
        report["gates"]["check"]["evidence"] = ""
        with self.assertRaises(arena.ArenaError):
            arena.assess(self.run, self.state, report)

    def test_eligibility_outranks_score_and_unverified_is_not_pass(self):
        for cid in ("valid", "fatal", "unknown"):
            self.add(cid)
        arena.assess(self.run, self.state, self.report("valid", 7))
        arena.assess(self.run, self.state, self.report("fatal", 10, fatal=True))
        arena.assess(self.run, self.state, self.report("unknown", 10, gate="unverified"))
        rows = arena.ranking(self.run, self.state)
        self.assertEqual(rows[0]["candidate"], "valid")
        self.assertFalse(rows[1]["eligible"])

    def test_pairing_covers_odd_population_and_rotates_bye(self):
        ids = ["a", "b", "c", "d", "e"]
        for cid in ids:
            self.add(cid)
            arena.assess(self.run, self.state, self.report(cid))
        rd = arena.pair(self.run, self.state, "r1", ids)
        flat = [cid for m in rd["matches"] for cid in (m["a"], m["b"])] + [rd["bye"]]
        self.assertCountEqual(flat, ids)
        with self.assertRaises(arena.ArenaError):
            arena.pair(self.run, self.state, "r2", ids)
        for match in rd["matches"]:
            arena.record_match(self.run, self.state, "r1", match["a"], match["b"], "Equal on rubric")
        nxt = arena.pair(self.run, self.state, "r2", ids)
        self.assertNotEqual(rd["bye"], nxt["bye"])
        self.assertEqual(self.state["candidates"][rd["bye"]]["games"], 0)

    def test_elo_win_draw_and_duplicate_match(self):
        for cid in ("a", "b"):
            self.add(cid)
        arena.assess(self.run, self.state, self.report("a", 9))
        arena.assess(self.run, self.state, self.report("b", 8))
        arena.pair(self.run, self.state, "r1", ["a", "b"], [["a", "b"]])
        match = arena.record_match(self.run, self.state, "r1", "a", "b", "A has better checked coverage")
        self.assertEqual(match["result"], "a")
        self.assertEqual(match["ratings_after"], [1512, 1488])
        arena.record_match(self.run, self.state, "r1", "a", "b", "A has better checked coverage")
        self.assertEqual(self.state["candidates"]["a"]["games"], 1)
        with self.assertRaises(arena.ArenaError):
            arena.record_match(self.run, self.state, "r1", "a", "b", "changed verdict")
        arena.assess(self.run, self.state, self.report("b", 9))
        arena.pair(self.run, self.state, "r2", ["a", "b"], [["a", "b"]])
        draw = arena.record_match(self.run, self.state, "r2", "a", "b", "Equal on rubric")
        self.assertEqual(draw["result"], "draw")
        self.assertAlmostEqual(sum(draw["ratings_after"]), 3000)

    def test_knockout_100_and_non_power_of_two(self):
        for size in (7, 100):
            with self.subTest(size=size):
                self.state["config"]["mode"] = "tournament"
                ids = [f"n{size}_{i}" for i in range(size)]
                for i, cid in enumerate(ids):
                    self.add(cid)
                    arena.assess(self.run, self.state, self.report(cid, 5 + i / size))
                count = 0
                round_no = 0
                while len(ids) > 1:
                    round_no += 1
                    rid = f"n{size}_r{round_no}"
                    rd = arena.pair(self.run, self.state, rid, ids)
                    survivors = [rd["bye"]] if rd["bye"] else []
                    for m in rd["matches"]:
                        result = arena.record_match(self.run, self.state, rid, m["a"], m["b"], "Higher evaluated score")
                        survivors.append(result["result"])
                        count += 1
                    ids = survivors
                self.assertEqual(count, size - 1)
                self.assertEqual(ids, [f"n{size}_{size-1}"])

    def test_tournament_exact_tie_requires_explicit_decision(self):
        self.state["config"]["mode"] = "tournament"
        for cid in ("a", "b"):
            self.add(cid)
            arena.assess(self.run, self.state, self.report(cid))
        arena.pair(self.run, self.state, "r1", ["a", "b"], [["a", "b"]])
        with self.assertRaises(arena.ArenaError):
            arena.record_match(self.run, self.state, "r1", "a", "b", "Equal")
        result = arena.record_match(self.run, self.state, "r1", "a", "b", "Seeded procedural tie-break", "a")
        self.assertEqual(result["result"], "a")

    def test_fresh_final_assessment_and_threshold(self):
        self.add("a")
        arena.assess(self.run, self.state, self.report("a", 9))
        with self.assertRaises(arena.ArenaError):
            arena.assess(self.run, self.state, self.report("a", 9), final=True)
        arena.assess(self.run, self.state, self.report("a", 9, judge="fresh-validator"), final=True)
        result = arena.conclude(self.run, self.state, "a", "target reached", True)
        self.assertTrue(result["accepted"])
        with self.assertRaises(arena.ArenaError):
            arena.reserve(self.state, "worker", "late work")

    def test_selection_alone_and_unverified_final_cannot_accept(self):
        self.add("a")
        arena.assess(self.run, self.state, self.report("a", 10))
        result = arena.conclude(self.run, self.state, "a", "budget exhausted", False)
        self.assertFalse(result["accepted"])
        self.state["result"] = None
        arena.assess(self.run, self.state, self.report("a", 10, gate="unverified", judge="new-validator"), final=True)
        self.assertFalse(arena.conclude(self.run, self.state, "a", "unverified", True)["accepted"])

    def test_atomic_save_keeps_old_file_on_replace_failure(self):
        path = self.root / "atomic.json"
        arena.atomic_json(path, {"old": True})
        with patch.object(arena.os, "replace", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                arena.atomic_json(path, {"new": True})
        self.assertEqual(arena.read_json(path), {"old": True})
        self.assertFalse(list(self.root.glob(".arena-*.tmp")))

    def test_duplicate_json_keys_rejected(self):
        path = self.root / "duplicate.json"
        path.write_text('{"fatal":true,"fatal":false}')
        with self.assertRaises(arena.ArenaError):
            arena.read_json(path)

    def test_cli_disk_roundtrip(self):
        def cli(*args):
            process = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(process.stdout)
        reserved = cli("reserve", "--dir", str(self.run), "--role", "worker", "--label", "integration")
        cli("finish", "--dir", str(self.run), "--job", reserved["job"], "--status", "done", "--evidence", "fixture output")
        cli("add", "--dir", str(self.run), "--candidate", "answer", "--file", str(self.task))
        self.state = arena.load(self.run)
        report = self.root / "report.json"
        report.write_text(json.dumps(self.report("answer", 9)), encoding="utf-8")
        cli("assess", "--dir", str(self.run), "--report", str(report))
        report.write_text(json.dumps(self.report("answer", 9, judge="fresh")), encoding="utf-8")
        cli("assess", "--dir", str(self.run), "--report", str(report), "--final")
        result = cli("conclude", "--dir", str(self.run), "--candidate", "answer", "--reason", "fixture verified")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["competition_complete"])
        self.assertEqual(cli("status", "--dir", str(self.run))["jobs"][reserved["job"]]["status"], "done")


if __name__ == "__main__":
    unittest.main()
