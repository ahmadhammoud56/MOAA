"""Context canary tests: python -m unittest discover -s tests"""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import strata as memory  # noqa: E402
from test_handoff import Sandbox, assistant, write_jsonl  # noqa: E402

LONG = "Here is the plan for the parser port, step by step. " * 6  # well over CANARY_MIN
HIT = LONG + "\n\n" + memory.CANARY
MISS = LONG


class Canary(Sandbox):
    def setUp(self):
        super().setUp()
        os.environ["STRATA_CANARY"] = "on"

    def stop(self, reply, tokens=120000, session="s1", given_rule=True, **kw):
        """One Stop hook call after a reply; the transcript's newest usage sets the context (120k = 60% of 200k).
        given_rule: the chat's SessionStart injected the canary rule (as it does in every chat since strata 0.6)."""
        if given_rule:
            st = memory.load_state(session)
            st["canary_rule"] = True
            memory.save_state(session, st)
        t = write_jsonl(Path(self.dir) / f"{session}.jsonl", [assistant(tokens)])
        data = {"session_id": session, "transcript_path": t, "cwd": str(self.proj), "hook_event_name": "Stop",
                "stop_hook_active": False, **kw}
        if reply is not None:
            data["last_assistant_message"] = reply
        out = memory.hook("stop", json.dumps(data))
        return json.loads(out) if out else None

    def test_rule_is_injected_at_session_start_and_renders_as_nothing(self):
        out = json.loads(memory.hook("session-start", json.dumps({"session_id": "s1", "cwd": str(self.proj)})))
        self.assertIn(memory.CANARY, out["hookSpecificOutput"]["additionalContext"])
        self.assertTrue(memory.CANARY.startswith("[//]: # ("))  # a link reference definition, not an HTML comment
        with mock.patch.dict(os.environ, {"STRATA_CANARY": "off"}):
            self.assertEqual(memory.hook("session-start", json.dumps({"session_id": "s1", "cwd": str(self.proj)})), "")

    def test_two_misses_in_a_row_start_the_handoff_with_the_reason(self):
        self.assertIsNone(self.stop(MISS))
        self.assertEqual(memory.load_state("s1")["canary_misses"], 1)
        out = self.stop(MISS)
        self.assertEqual(out["decision"], "block")
        self.assertIn("canary missed", out["reason"])
        self.assertIn("Reason: canary missed.", out["reason"])
        self.assertIn("HANDOFF.md", out["reason"])
        self.assertIn("Strata canary", out["systemMessage"])
        d = Path(memory.load_state("s1")["dir"])
        self.assertEqual(memory.meta_of(d)["reason"], "canary missed")
        self.assertIsNone(self.stop(MISS))  # once per session: the handoff turn itself is not judged

    def test_a_chat_never_given_the_rule_never_misses(self):
        """A chat opened before strata 0.6 was installed got no rule at SessionStart: its replies are no evidence."""
        for _ in range(3):
            self.assertIsNone(self.stop(MISS, session="old", given_rule=False))
        self.assertNotIn("canary_misses", memory.load_state("old"))
        memory.hook("session-start", json.dumps({"session_id": "old", "cwd": str(self.proj)}))  # resumed after update
        self.assertTrue(memory.load_state("old")["canary_rule"])
        self.assertIsNone(self.stop(MISS, session="old", given_rule=False))
        self.assertIsNotNone(self.stop(MISS, session="old", given_rule=False))

    def test_a_hit_resets_the_count(self):
        self.assertIsNone(self.stop(MISS))
        self.assertIsNone(self.stop(HIT))
        self.assertEqual((memory.load_state("s1")["canary_misses"], memory.load_state("s1")["canary_hits"]), (0, 1))
        self.assertIsNone(self.stop(MISS))
        self.assertIsNotNone(self.stop(MISS))

    def test_short_and_tool_only_replies_are_no_evidence(self):
        for reply in ("Done.", "", "Fixed the typo in README.md and ran the tests; all 45 pass."):
            self.assertIsNone(self.stop(reply))
        self.assertIsNone(self.stop(MISS))
        self.assertIsNone(self.stop("OK"))  # does not break the run of misses either
        self.assertIsNotNone(self.stop(MISS))

    def test_below_the_floor_misses_count_but_do_not_fire(self):
        self.assertIsNone(self.stop(MISS, tokens=20000))  # 10%
        self.assertIsNone(self.stop(MISS, tokens=20000))
        self.assertEqual(memory.load_state("s1")["canary_misses"], 2)
        self.assertIsNotNone(self.stop(MISS, tokens=70000))  # 35%: the third miss fires

    def test_settings_and_switches(self):
        self.assertEqual(memory.main(["canary", "misses", "3"]), 0)
        self.assertEqual(memory.main(["canary", "floor", "0"]), 0)
        for _ in range(2):
            self.assertIsNone(self.stop(MISS, session="a"))
        self.assertIsNotNone(self.stop(MISS, session="a"))
        with mock.patch.dict(os.environ, {"STRATA_CANARY_MISSES": "1"}):
            self.assertIsNotNone(self.stop(MISS, session="b"))
        with self.assertRaises(SystemExit):
            memory.main(["canary", "misses", "0"])
        self.assertEqual(memory.main(["canary", "off"]), 0)
        os.environ.pop("STRATA_CANARY")
        self.assertFalse(memory.canary_settings()[0])
        self.assertIsNone(self.stop(MISS, session="c"))
        self.assertNotIn("canary_misses", memory.load_state("c"))
        with mock.patch.dict(os.environ, {"STRATA_CANARY": "on", "STRATA_CANARY_MISSES": "1"}):
            self.assertIsNotNone(self.stop(MISS, session="d"))
        self.assertEqual(memory.main(["canary", "status"]), 0)

    def test_without_a_handoff_it_only_tells_the_user(self):
        os.environ["STRATA_CANARY_MISSES"] = "1"
        with mock.patch.dict(os.environ, {"STRATA_HANDOFF": "off"}):
            out = self.stop(MISS, session="a")
        self.assertEqual(set(out), {"systemMessage"})
        out = self.stop(MISS, session="b", stop_hook_active=True)  # another Stop hook already made Claude go on
        self.assertEqual(set(out), {"systemMessage"})
        self.assertIsNone(self.stop(MISS, session="c", agent_id="x"))  # sub-agents are not judged

    def test_reply_falls_back_to_the_transcript_tail(self):
        t = write_jsonl(Path(self.dir) / "t.jsonl", [
            {"type": "user", "message": {"content": "go"}},
            assistant(1000, content=[{"type": "text", "text": LONG}]),
            assistant(1000, content=[{"type": "tool_use", "name": "Read", "input": {}}]),
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}},
            assistant(1000, content=[{"type": "text", "text": "All done."}]),
            assistant(1000, content=[{"type": "text", "text": memory.CANARY}])])
        self.assertIn(memory.CANARY, memory.last_reply({"transcript_path": t}))
        self.assertNotIn("parser port", memory.last_reply({"transcript_path": t}))  # only the last reply
        self.assertEqual(memory.last_reply({}), "")


if __name__ == "__main__":
    unittest.main()
