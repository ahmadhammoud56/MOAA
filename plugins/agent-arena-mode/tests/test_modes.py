"""Synthetic, deterministic mode simulations. No model calls: answers and judge reports are fixtures."""
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

os.environ.pop("CLAUDE_PLUGIN_DATA", None)  # never touch a real library from tests
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import arena  # noqa: E402
import library  # noqa: E402


class Sim(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.task = self.root / "task.md"
        self.task.write_text("Synthetic task with a checkable answer.", encoding="utf-8")
        self.rubric = self.root / "rubric.json"
        self.rubric.write_text(json.dumps({"weights": arena.WEIGHTS, "gates": {"check": "Observed passing check"}}))
        self.db = self.root / "lib" / "library.sqlite3"
        self.n = 0

    def tearDown(self):
        self.temp.cleanup()

    def start(self, mode, agents, **kw):
        self.run = self.root / f"run-{mode}-{self.n}"
        self.n += 1
        kw.setdefault("database", self.db)
        self.state = arena.init_run(self.run, self.task, self.rubric, mode=mode, agents=agents, **kw)
        return self.state

    def work(self, cid, parents=(), role="worker"):
        job = arena.reserve(self.state, role, cid)["job"]
        source = self.root / f"{self.run.name}-{cid}.md"
        source.write_text(f"Answer {cid}", encoding="utf-8")
        arena.finish(self.state, job, "done", f"synthetic runtime id for {cid}")
        return arena.add_candidate(self.run, self.state, cid, source, parents)

    def judge(self, cid, score, final=False, gate="pass", judge="judge-1"):
        job = arena.reserve(self.state, "validator" if final else "judge", "assess " + cid)["job"]
        report = {"candidate": cid, "sha256": self.state["candidates"][cid]["sha256"], "judge": judge,
                  "scores": {k: score for k in arena.WEIGHTS},
                  "gates": {"check": {"status": gate, "evidence": "synthetic check log"}},
                  "fatal": False, "findings": [], "rationale": "synthetic"}
        arena.finish(self.state, job, "done", "synthetic judge")
        return arena.assess(self.run, self.state, report, final)

    def retire(self, cid, reason="superseded"):
        self.state["candidates"][cid].update(active=False, retired_reason=reason)

    def finalize(self, cid, score=9):
        self.judge(cid, score, final=True, judge="fresh-validator")
        return arena.conclude(self.run, self.state, cid, "synthetic stop", True)

    # --- mode simulations -------------------------------------------------
    def test_judge_mode_every_submission_scored_then_validated(self):
        self.start("judge", 4)
        for i in range(4):
            self.work(f"a{i}")
            self.judge(f"a{i}", 6 + i)
        self.assertEqual(len(self.state["assessments"]), 4)
        best = arena.ranking(self.run, self.state)[0]["candidate"]
        self.assertEqual(best, "a3")
        self.assertTrue(self.finalize(best)["accepted"])

    def test_tournament_revisions_byes_and_single_survivor(self):
        self.start("tournament", 5)
        current = {}  # entrant -> current immutable version
        for i in range(5):
            self.work(f"e{i}")
            self.judge(f"e{i}", 5 + i)
            current[f"e{i}"] = f"e{i}"
        rnd = matches = 0
        while len(current) > 1:
            rnd += 1
            preview = arena.pair(self.run, self.state, f"r{rnd}", [current[e] for e in sorted(current)], dry_run=True)
            self.assertNotIn(f"r{rnd}", self.state["rounds"])  # attack-phase preview opens nothing
            self.assertTrue(preview["dry_run"])
            entrants = sorted(current)
            pairs = [entrants[i:i + 2] for i in range(0, len(entrants) - 1, 2)]
            bye = entrants[-1] if len(entrants) % 2 else None
            for a, b in pairs:  # critique, then both sides revise into new versions
                for entrant in (a, b):
                    old, new = current[entrant], f"{entrant}-r{rnd}"
                    self.work(new, parents=[old])
                    self.judge(new, self.state["assessments"][old]["scores"]["correctness"])
                    self.retire(old)
                    current[entrant] = new
            fixed = [[current[a], current[b]] for a, b in pairs]
            ids = [x for p in fixed for x in p] + ([current[bye]] if bye else [])
            rd = arena.pair(self.run, self.state, f"r{rnd}", ids, fixed)
            self.assertEqual(rd["bye"], current[bye] if bye else None)
            for m in rd["matches"]:
                won = arena.record_match(self.run, self.state, f"r{rnd}", m["a"], m["b"], "synthetic verdict")["result"]
                lost = m["b"] if won == m["a"] else m["a"]
                self.retire(lost, "lost")
                del current[lost.split("-")[0]]
                matches += 1
        self.assertEqual(matches, 4)
        champion = next(iter(current.values()))
        self.assertTrue(champion.startswith("e4"))
        self.assertTrue(self.finalize(champion)["competition_complete"])

    def test_swarm_private_drafts_bounded_exchange_and_halving(self):
        self.start("swarm", 6)
        ids = [f"s{i}" for i in range(6)]
        for cid in ids:
            self.work(cid)
        with self.assertRaises(arena.ArenaError):  # no sharing before private drafts are frozen and assessed
            arena.exchange(self.run, self.state, "x1", ids, 3)
        for i, cid in enumerate(ids):
            self.judge(cid, 5 + i * .5)
        ex = arena.exchange(self.run, self.state, "x1", ids, 3)
        self.assertIn("not live", ex["backend"])
        self.assertEqual(sorted(sum(ex["groups"], [])), sorted(ids))
        for group in ex["groups"]:
            for cid in group:
                inbox = sorted(p.stem for p in (self.run / "exchange" / "x1" / cid).iterdir())
                self.assertEqual(inbox, sorted(set(group) - {cid}))  # only own group's peers, never self
        with self.assertRaises(arena.ArenaError):
            arena.exchange(self.run, self.state, "x1", ids, 3)  # a round opens once
        for cid in ids:
            self.work(cid + "-r1", parents=[cid])
            self.retire(cid)
            self.judge(cid + "-r1", self.state["assessments"][cid]["scores"]["correctness"] + .5)
        kept = arena.cull(self.run, self.state, fraction=.5, minimum=2)
        self.assertEqual(len(kept["kept"]), 3)
        kept = arena.cull(self.run, self.state, fraction=.1, minimum=2)
        self.assertEqual(len(kept["kept"]), 2)
        self.assertTrue(all((self.run / "artifacts" / f"{c}.md").exists() for c in kept["retired"]))

    def test_league_season_ratings_conserved_and_frozen(self):
        self.start("league", 4, rounds=3)
        ids = [f"l{i}" for i in range(4)]
        for i, cid in enumerate(ids):
            self.work(cid)
            self.judge(cid, 6 + i)
        for r in range(3):
            rd = arena.pair(self.run, self.state, f"r{r}", ids)
            for m in rd["matches"]:
                arena.record_match(self.run, self.state, f"r{r}", m["a"], m["b"], "synthetic")
        self.assertAlmostEqual(sum(self.state["candidates"][c]["rating"] for c in ids), 6000)
        self.assertEqual(arena.ranking(self.run, self.state, elo=True)[0]["candidate"], "l3")
        self.work("l3-r1", parents=["l3"])
        self.assertEqual(self.state["candidates"]["l3-r1"]["rating"], 1500.0)  # revisions never inherit Elo

    def test_evolution_elites_descendants_plateau_and_regressed_synthesis(self):
        self.start("evolution", 8, rounds=4, patience=2, max_calls=200)
        for i in range(8):
            self.work(f"g0-{i}")
            self.judge(f"g0-{i}", 5 + i * .25)
        self.assertIsNone(arena.progress(self.state, 0)["stop"])
        elites = arena.cull(self.run, self.state, keep=math.ceil(8 / 4))["kept"]
        self.assertEqual(elites, ["g0-7", "g0-6"])
        hashes = {e: self.state["candidates"][e]["sha256"] for e in elites}
        for gen in (1, 2):
            for j in range(6):
                parents = elites if j < 5 else []  # last slot is an exploratory immigrant
                cid = f"g{gen}-{j}"
                self.work(cid, parents=parents)
                self.judge(cid, 5)
            self.assertEqual(arena.cull(self.run, self.state, keep=2)["kept"], elites)
            record = arena.progress(self.state, gen)
            self.assertFalse(record["improved"])
        self.assertEqual(record["stop"], "plateau")
        self.assertEqual(self.state["candidates"]["g1-0"]["parents"], elites)
        self.assertEqual({e: self.state["candidates"][e]["sha256"] for e in elites}, hashes)
        self.judge("g0-7", 8, final=True, judge="validator-a")
        with self.assertRaises(arena.ArenaError):  # synthesis is mandatory before claiming coverage
            arena.conclude(self.run, self.state, "g0-7", "skip synthesis", True)
        self.work("synth", parents=elites, role="synthesizer")
        self.judge("synth", 7.5)
        self.judge("synth", 7, final=True, judge="validator-b")
        with self.assertRaises(arena.ArenaError):  # regressed synthesis cannot be delivered
            arena.conclude(self.run, self.state, "synth", "synthesis done", True)
        self.assertFalse(arena.conclude(self.run, self.state, "g0-7", "plateau; synthesis rejected", True)["accepted"])

    def test_progress_detects_improvement_and_target(self):
        self.start("evolution", 2, rounds=5)
        self.work("a")
        self.judge("a", 7)
        self.assertTrue(arena.progress(self.state, 0)["improved"])
        self.work("b")
        self.judge("b", 9)
        record = arena.progress(self.state, 1)
        self.assertEqual((record["improved"], record["plateau"]), (True, 0))
        self.assertTrue(record["stop"].startswith("target-candidate"))
        self.assertEqual(arena.progress(self.state, 1), record)  # idempotent re-record
        with self.assertRaises(arena.ArenaError):
            arena.progress(self.state, 3)  # generations recorded in order

    def test_synthesis_specialists_and_integrated_artifact(self):
        self.start("synthesis", 4)
        for cid in ("full-a", "full-b", "spec-perf", "spec-tests"):
            self.work(cid)
        self.judge("full-a", 7)
        self.judge("full-b", 7.5)
        self.judge("spec-perf", 6, gate="unverified")  # partial scope cannot pass whole-task gates
        self.judge("spec-tests", 6, gate="unverified")
        eligible = [r["candidate"] for r in arena.ranking(self.run, self.state) if r["eligible"]]
        self.assertEqual(eligible, ["full-b", "full-a"])
        self.work("combined", parents=["full-a", "full-b", "spec-perf", "spec-tests"], role="synthesizer")
        self.judge("combined", 9)
        self.assertTrue(self.finalize("combined")["accepted"])

    def test_redteam_builders_fix_findings_until_round_limit(self):
        self.start("redteam", 4, rounds=2)
        builders = ["b0", "b1"]
        for cid in builders:
            self.work(cid)
            self.judge(cid, 6)
        for r in (1, 2):
            for i, cid in enumerate(list(builders)):
                critic = arena.reserve(self.state, "critic", f"attack {cid}")["job"]  # critics consume budget
                arena.finish(self.state, critic, "done", "synthetic counterexample")
                new = f"b{i}-v{r}"
                self.work(new, parents=[cid])
                self.judge(new, 6 + r)
                self.retire(cid)
                builders[i] = new
            record = arena.progress(self.state, r - 1)
        self.assertEqual(record["stop"], "round-limit")
        self.assertTrue(self.finalize("b0-v2")["accepted"])

    def test_cascade_halving_then_complete_answers(self):
        self.start("cascade", 8)
        for i in range(8):
            self.work(f"p{i}")
            self.judge(f"p{i}", 4 + i * .5, gate="unverified")  # proposals: completion checks unverified
        self.assertEqual(len(arena.cull(self.run, self.state, fraction=.5)["kept"]), 4)
        self.assertEqual(len(arena.cull(self.run, self.state, fraction=.5)["kept"]), 2)
        for cid in [r["candidate"] for r in arena.ranking(self.run, self.state)]:
            self.work(cid + "-full", parents=[cid])
            self.judge(cid + "-full", 9 if cid == "p7" else 8)
        self.assertTrue(self.finalize("p7-full")["accepted"])
        self.assertEqual(sum(1 for c in self.state["candidates"] if c.endswith("-full")), 2)

    # --- options, budget, reuse, concurrency --------------------------------
    def test_quick_patience_and_model_options(self):
        state = self.start("judge", None, quick=True, patience=3, judge_model="opus", judge_effort="high")
        self.assertEqual(state["config"]["agents"], 8)
        self.assertEqual(state["config"]["patience"], 3)
        self.assertEqual(state["config"]["models"]["roles"]["judge"], {"model": "claude-opus-5-5", "effort": "high"})
        with self.assertRaises(arena.ArenaError):
            self.start("judge", 12, quick=True)
        self.assertEqual(self.start("judge", None)["config"]["agents"], 100)

    def test_model_assignment_is_exact_deterministic_and_difficulty_aware(self):
        for difficulty, agents in (("low", 7), ("medium", 8), ("high", 24), ("critical", 100)):
            a = arena.assign(agents, difficulty, seed=42)
            self.assertEqual(len(a["slots"]), agents)
            self.assertEqual(sum(a["summary"].values()), agents)
            self.assertEqual(a, arena.assign(agents, difficulty, seed=42))
        low, crit = arena.assign(8, "low"), arena.assign(8, "critical")
        self.assertEqual(low["roles"]["judge"]["model"], "claude-opus-5-5")
        self.assertEqual(crit["roles"]["judge"], {"model": "claude-fable-5-1", "effort": "xhigh"})
        self.assertNotIn("claude-fable-5-1", {s["model"] for s in low["slots"]})
        self.assertIn("claude-fable-5-1", {s["model"] for s in crit["slots"]})
        cascade = arena.assign(8, "high", mode="cascade")  # proposals one step cheaper
        self.assertNotIn("claude-opus-5-5", {s["model"] for s in cascade["slots"]})
        forced = arena.assign(6, "high", worker_model="haiku", judge_model="sonnet", judge_effort="low")
        self.assertEqual({s["model"] for s in forced["slots"]}, {"claude-haiku-5-5"})
        self.assertEqual(forced["roles"]["validator"], {"model": "claude-sonnet-5-5", "effort": "low"})
        with self.assertRaises(arena.ArenaError):
            arena.assign(4, "extreme")

    def test_init_records_slot_models_and_reserve_records_dispatch_settings(self):
        state = self.start("evolution", 8, difficulty="high")
        self.assertTrue(all(s["model"] in arena.MODEL_IDS.values() and s["effort"] in arena.EFFORTS
                            for s in state["roster"]))
        job = arena.reserve(self.state, "judge", "j", "fable", "high")
        self.assertEqual((job["model"], job["effort"]), ("claude-fable-5-1", "high"))
        with self.assertRaises(arena.ArenaError):
            arena.reserve(self.state, "judge", "j2", "opus", "extreme")

    def test_budget_exhaustion_stops_dispatch(self):
        self.start("judge", 2, max_calls=3)
        self.work("a")
        self.work("b")
        arena.reserve(self.state, "judge", "j")
        with self.assertRaises(arena.ArenaError):
            arena.reserve(self.state, "judge", "over budget")

    def test_reuse_seeds_slots_and_rejects_invalid_ids(self):
        self.start("judge", 2)
        first_run, first_state = self.run, self.state
        self.work("a")
        self.judge("a", 9)
        saved = library.sync_run(self.run, self.state)["champion"]
        state = self.start("evolution", 4, reuse=saved)
        self.assertEqual(state["roster"][0]["reuse"], saved)
        self.assertEqual(sum(state["config"]["models"]["workers"].values()), 4)
        self.assertIn(state["roster"][0]["model"], arena.MODEL_IDS.values())  # no recorded model: keep assigned slot model
        self.assertNotIn("reuse", state["roster"][1])
        self.assertEqual(len(state["roster"]), 4)  # reuse counts toward N, not on top of it
        with self.assertRaises(ValueError):
            self.start("judge", 2, reuse="ag_" + "0" * 24)  # unknown ID is rejected, not substituted
        self.run, self.state = first_run, first_state
        self.judge("a", 9, final=True, gate="fail", judge="fresh")
        library.sync_run(self.run, self.state)
        with self.assertRaises(arena.ArenaError):
            self.start("judge", 2, reuse=saved)  # invalidated after failed revalidation

    def test_parallel_cli_mutations_do_not_lose_jobs(self):
        self.start("judge", 20, concurrency=20)

        def reserve(i):
            cmd = [sys.executable, str(SCRIPTS / "arena.py"), "reserve", "--dir", str(self.run),
                   "--role", "w", "--label", str(i)]
            return subprocess.run(cmd, capture_output=True, text=True).returncode
        with ThreadPoolExecutor(8) as pool:
            codes = list(pool.map(reserve, range(16)))
        self.assertEqual(codes, [0] * 16)
        self.assertEqual(len(arena.load(self.run)["jobs"]), 16)
        self.assertFalse((self.run / "state.lock").exists())

    def test_checkpoint_persists_phase_and_next_action(self):
        self.start("evolution", 4)
        arena.checkpoint(self.state, "evaluate", 1, "Assess generation 1")
        point = self.state["checkpoint"]
        self.assertEqual((point["phase"], point["generation"]), ("evaluate", 1))
        self.assertEqual(point["database"], str(self.db.resolve()))
        with self.assertRaises(arena.ArenaError):
            arena.checkpoint(self.state, generation=0)


if __name__ == "__main__":
    unittest.main()
