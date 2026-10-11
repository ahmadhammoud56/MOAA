import importlib.util
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import arena
import library

COUNCIL = next((p / "specialist-council" for p in Path(__file__).resolve().parents[2:4]  # sibling or kit repo root
                if (p / "specialist-council" / "council.py").is_file()), Path("missing"))


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.task = self.root / "task.md"
        self.task.write_text("Solve the benchmark", encoding="utf-8")
        self.rubric = self.root / "rubric.json"
        self.rubric.write_text(json.dumps({"weights": arena.WEIGHTS, "gates": {"check": "Pass the acceptance test"}}))
        self.database = self.root / "persistent" / "library.sqlite3"
        self.run = self.root / "run"
        self.state = arena.init_run(self.run, self.task, self.rubric, agents=4, database=self.database, context_key="benchmark-v1")

    def tearDown(self):
        self.temp.cleanup()

    def candidate(self, cid, parents=(), source_agents=()):
        source = self.root / f"{cid}.md"
        source.write_text(f"Complete answer from {cid}", encoding="utf-8")
        evidence = self.root / f"{cid}.bin"
        evidence.write_bytes(bytes(range(256)))
        profile = {"name": "Parser specialist " + cid, "instructions": "Use concrete counterexamples and minimal patches.",
                   "strategy": "Test edge cases", "model_requested": "sonnet", "model_actual": "unknown",
                   "tags": ["parser", "python"], "source_agents": list(source_agents)}
        arena.add_candidate(self.run, self.state, cid, source, parents, profile, [evidence])

    def assess(self, cid, score=9, final=False, eligible=True, judge="judge"):
        report = {"candidate": cid, "sha256": self.state["candidates"][cid]["sha256"], "judge": judge,
                  "scores": {k: score for k in arena.WEIGHTS},
                  "gates": {"check": {"status": "pass" if eligible else "fail", "evidence": "Observed test output"}},
                  "fatal": False, "findings": [], "rationale": "Verified task evidence"}
        return arena.assess(self.run, self.state, report, final)

    def test_incremental_save_and_champion_replacement_keeps_history(self):
        self.candidate("first")
        self.assess("first", 8)
        first = library.sync_run(self.run, self.state)
        self.assertEqual(first["champion"], library.entry_id(self.state, "first"))
        self.candidate("better", ["first"])
        self.assess("better", 9)
        second = library.sync_run(self.run, self.state)
        self.assertNotEqual(second["champion"], first["champion"])
        rows = library.list_entries(self.database)
        self.assertEqual([r["score"] for r in rows], [90, 80])
        child = library.get_entry(self.database, second["champion"])
        self.assertEqual(child["parents"][0]["library_id"], first["champion"])
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM champions").fetchone()[0], 2)
        library.sync_run(self.run, self.state)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM assessments").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT count(*) FROM champions").fetchone()[0], 2)

    def test_survives_run_deletion_and_exports_binary_evidence_and_profile(self):
        self.candidate("a")
        self.assess("a", final=True)
        result = library.sync_run(self.run, self.state)
        self.assertEqual(self.run.resolve().parent, self.root.resolve())
        shutil.rmtree(self.run)  # verified temporary test fixture only
        destination = self.root / "loaded"
        library.export_entry(self.database, result["champion"], destination)
        self.assertEqual((destination / "answer.md").read_text(), "Complete answer from a")
        self.assertEqual((destination / "evidence" / "000-a.bin").read_bytes(), bytes(range(256)))
        profile = json.loads((destination / "profile.json").read_text())
        self.assertIn("counterexamples", profile["instructions"])
        with self.assertRaises(ValueError):
            library.export_entry(self.database, result["champion"], destination)

    def test_failed_revalidation_revokes_saved_winner(self):
        for cid in ("a", "b"):
            self.candidate(cid)
        self.assess("a", 10)
        self.assess("b", 8)
        saved = library.sync_run(self.run, self.state)
        winner = saved["champion"]
        self.assess("a", 10, final=True, eligible=False, judge="fresh-validator")
        updated = library.sync_run(self.run, self.state)
        self.assertNotEqual(updated["champion"], winner)
        self.assertEqual(library.get_entry(self.database, winner)["validation"], "invalidated")
        self.assertEqual(len(library.list_entries(self.database)), 1)
        self.assertEqual(len(library.list_entries(self.database, all_entries=True)), 2)
        with self.assertRaises(ValueError):
            library.export_entry(self.database, winner, self.root / "invalid")

    def test_final_validation_distinct_from_target_and_provisional(self):
        self.candidate("a")
        self.assess("a", 8)
        result = library.sync_run(self.run, self.state)
        self.assertEqual(library.list_entries(self.database, validated=True), [])
        self.assess("a", 8, final=True, judge="validator")
        library.sync_run(self.run, self.state)
        payload = library.get_entry(self.database, result["champion"])
        self.assertEqual(payload["validation"], "validated")
        self.assertFalse(payload["target_met"])

    def test_validated_entry_outranks_higher_provisional(self):
        for cid in ("a", "b"):
            self.candidate(cid)
        self.assess("a", 10)
        self.assess("b", 8)
        self.assertEqual(library.sync_run(self.run, self.state)["champion"], library.entry_id(self.state, "a"))
        self.assess("b", 8, final=True, judge="validator")
        result = library.sync_run(self.run, self.state)
        self.assertEqual(result["champion"], library.entry_id(self.state, "b"))
        self.assertEqual(library.list_entries(self.database)[0]["id"], library.entry_id(self.state, "b"))

    def test_promote_requires_consistency_and_forges_council_member(self):
        home = self.root / "claude-home"
        self.candidate("a")
        self.assess("a", 9)
        self.assess("a", 9, final=True, judge="validator")
        first = library.entry_id(self.state, "a")
        first_run = (self.run, self.state)
        library.sync_run(self.run, self.state)
        with self.assertRaises(ValueError):  # one run is not evidence of consistency
            library.promote(self.database, first, home)
        self.assertFalse(library.promotion_evidence(self.database, first)["eligible"])
        self.run = self.root / "second"  # reuse the saved agent in an equivalent later run
        self.state = arena.init_run(self.run, self.task, self.rubric, agents=4, database=self.database,
                                    context_key="benchmark-v1", reuse=first)
        self.candidate("b", source_agents=[first])
        self.assess("b", 9.5)
        self.assess("b", 9.5, final=True, judge="validator")
        library.sync_run(self.run, self.state)
        result = library.promote(self.database, first, home)
        self.assertEqual(result["model"], "claude-sonnet-5-5")
        self.assertEqual(len(result["evidence"]["runs"]), 2)
        card = Path(result["agent_file"]).read_text(encoding="utf-8")
        self.assertIn('model: "claude-sonnet-5-5"', card)
        self.assertIn("effort:", card)
        self.assertTrue((Path(result["knowledge_base"]) / "answer.md").is_file())
        registry = json.loads((home / "skills/specialist-council/forged/registry.json").read_text())
        self.assertEqual(registry[result["slug"]]["status"], "active")
        self.assertEqual(library.promote(self.database, first, home)["slug"], result["slug"])  # idempotent
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT status FROM council_members").fetchall(), [("active",)])
        self.assess("b", 3, final=True, eligible=False, judge="late-validator")  # later failure suspends member
        library.sync_run(self.run, self.state)
        registry = json.loads((home / "skills/specialist-council/forged/registry.json").read_text())
        self.assertEqual(registry[result["slug"]]["status"], "active")  # b invalidated, but a itself still valid
        self.run, self.state = first_run
        self.assess("a", 2, final=True, eligible=False, judge="third-validator")
        library.sync_run(self.run, self.state)
        registry = json.loads((home / "skills/specialist-council/forged/registry.json").read_text())
        self.assertEqual(registry[result["slug"]]["status"], "suspended")
        self.assertFalse(Path(result["agent_file"]).exists())  # suspended member is no longer a registered agent
        self.assertTrue((Path(result["knowledge_base"]) / "agent.suspended.md").is_file())

    @unittest.skipUnless(COUNCIL.is_dir(), "specialist-council source not next to the plugin")
    def test_end_to_end_promotion_passes_council_check_and_suspension_unregisters(self):
        spec = importlib.util.spec_from_file_location("council", COUNCIL / "council.py")
        council = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(council)
        self.assertEqual(library.MODEL_IDS, council.load_profile(COUNCIL / "profile.json")["models"])  # one model table
        home = self.root / "claude-home"
        profile = council.load_profile(COUNCIL / "profile.json")
        shutil.copytree(COUNCIL, self.root / "council-src", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        src = self.root / "council-src"
        spec = importlib.util.spec_from_file_location("council_copy", src / "council.py")
        copy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(copy)  # install from a scratch copy so the real source is never rewritten
        copy.install(home, profile)
        self.candidate("a")
        self.assess("a", 9)
        self.assess("a", 9, final=True, judge="validator")
        first = library.entry_id(self.state, "a")
        first_run = (self.run, self.state)
        library.sync_run(self.run, self.state)
        self.run = self.root / "second"
        self.state = arena.init_run(self.run, self.task, self.rubric, agents=4, database=self.database,
                                    context_key="benchmark-v1", reuse=first)
        self.candidate("b", source_agents=[first])
        self.assess("b", 9.5)
        self.assess("b", 9.5, final=True, judge="validator")
        library.sync_run(self.run, self.state)
        result = library.promote(self.database, first, home)
        skill = home / "skills" / "specialist-council"
        check = subprocess.run([sys.executable, str(skill / "council.py"), "check", "--agents", str(home / "agents")],
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(json.loads(check.stdout)["forged"], {"active": 1, "total": 1})
        library.promote(self.database, first, home)  # re-promotion refreshes the knowledge base in place
        self.assertTrue((Path(result["knowledge_base"]) / "answer.md").is_file())
        self.run, self.state = first_run
        self.assess("a", 2, final=True, eligible=False, judge="third-validator")
        library.sync_run(self.run, self.state)
        check = subprocess.run([sys.executable, str(skill / "council.py"), "check", "--agents", str(home / "agents")],
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(json.loads(check.stdout)["forged"], {"active": 0, "total": 1})

    def test_promote_rejects_inconsistent_scores(self):
        self.candidate("a")
        self.assess("a", 10, final=True, judge="validator")
        first = library.entry_id(self.state, "a")
        library.sync_run(self.run, self.state)
        self.run = self.root / "second"
        self.state = arena.init_run(self.run, self.task, self.rubric, agents=4, database=self.database)
        self.candidate("b", source_agents=[first])
        self.assess("b", 8.6, final=True, judge="validator")
        library.sync_run(self.run, self.state)
        evidence = library.promotion_evidence(self.database, first)
        self.assertFalse(evidence["eligible"])
        self.assertTrue(any("spread" in r for r in evidence["reasons"]))

    def test_changed_task_or_rubric_never_shares_leaderboard(self):
        self.candidate("a")
        self.assess("a")
        first = library.sync_run(self.run, self.state)
        self.task.write_text("Different benchmark")
        self.run = self.root / "other"
        self.state = arena.init_run(self.run, self.task, self.rubric, database=self.database, context_key="benchmark-v1")
        self.candidate("a")
        self.assess("a", 10)
        other = library.sync_run(self.run, self.state)
        self.assertNotEqual(first["cohort"], other["cohort"])
        rows = library.list_entries(self.database, limit=1)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["rank_in_cohort"] == 1 for r in rows))

    def test_library_reuse_lineage_and_instructions_are_saved(self):
        self.candidate("a")
        self.assess("a")
        saved = library.sync_run(self.run, self.state)
        self.candidate("b", source_agents=[saved["champion"]])
        self.assess("b", 10)
        evolved = library.sync_run(self.run, self.state)
        self.assertEqual(library.get_entry(self.database, evolved["champion"])["profile"]["source_agents"], [saved["champion"]])

    def test_integrity_failure_rolls_back_entire_sync(self):
        self.candidate("a")
        self.assess("a")
        self.candidate("b")
        self.assess("b", 10)
        (self.run / "artifacts" / "b.md").write_text("changed")
        with self.assertRaises(ValueError):
            library.sync_run(self.run, self.state)
        self.assertEqual(library.list_entries(self.database), [])

    def test_profile_bundle_tamper_rejected(self):
        self.candidate("a")
        self.assess("a")
        (self.run / "artifacts" / "a.bundle.json").write_text("{}")
        with self.assertRaises(ValueError):
            library.sync_run(self.run, self.state)

    def test_stored_payload_tamper_and_sql_query_literal(self):
        self.candidate("a")
        self.assess("a")
        saved = library.sync_run(self.run, self.state)
        self.assertEqual(library.list_entries(self.database, query="' OR 1=1 --"), [])
        with closing(sqlite3.connect(self.database)) as db:
            db.execute("UPDATE entries SET payload='{}'")
            db.commit()
        with self.assertRaises(ValueError):
            library.get_entry(self.database, saved["champion"])

    def test_parallel_sync_is_idempotent(self):
        self.candidate("a")
        self.assess("a")
        # Initialize schema once; each writer opens its own connection.
        library.sync_run(self.run, self.state)
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: library.sync_run(self.run, self.state), range(6)))
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM entries").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM assessments").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM champions").fetchone()[0], 1)

    def test_cli_assess_saves_without_manual_sync(self):
        self.candidate("a")
        arena.atomic_json(self.run / "state.json", self.state)
        report = self.assess("a")
        path = self.root / "report.json"
        path.write_text(json.dumps(report))
        result = subprocess.run([sys.executable, str(SCRIPTS / "arena.py"), "assess", "--dir", str(self.run),
                                 "--report", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(library.list_entries(self.database)), 1)
        self.assertIn("library", json.loads(result.stdout))

    def test_cli_sync_failure_preserves_assessment_and_retry_recovers(self):
        self.candidate("a")
        self.state["config"]["database"] = str(self.root)  # directory cannot be a SQLite file
        arena.atomic_json(self.run / "state.json", self.state)
        report = self.assess("a")
        path = self.root / "report.json"
        path.write_text(json.dumps(report))
        failed = subprocess.run([sys.executable, str(SCRIPTS / "arena.py"), "assess", "--dir", str(self.run),
                                 "--report", str(path)], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("Run state saved", failed.stderr)
        self.assertEqual(len(arena.load(self.run)["assessment_history"]), 1)
        retry = subprocess.run([sys.executable, str(SCRIPTS / "library.py"), "sync", "--dir", str(self.run),
                                "--database", str(self.database)], capture_output=True, text=True)
        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertEqual(len(library.list_entries(self.database)), 1)

    def test_no_library_does_not_write_database(self):
        self.candidate("a")
        self.state["config"]["database"] = None
        arena.atomic_json(self.run / "state.json", self.state)
        path = self.root / "report.json"
        path.write_text(json.dumps(self.assess("a")))
        result = subprocess.run([sys.executable, str(SCRIPTS / "arena.py"), "assess", "--dir", str(self.run),
                                 "--report", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("library", json.loads(result.stdout))
        self.assertFalse(self.database.exists())
        with self.assertRaises(arena.ArenaError):
            arena.init_run(self.root / "conflict", self.task, self.rubric, database=self.database, no_library=True)


if __name__ == "__main__":
    unittest.main()
