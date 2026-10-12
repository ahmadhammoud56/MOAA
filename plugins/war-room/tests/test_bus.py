"""Spike (d): three bus.py MCP server processes hammer one SQLite file concurrently.

Checks: every task claimed exactly once, every message delivered exactly once. Stdlib only.
Run: python test_bus.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from bus import Bus  # noqa: E402

N_AGENTS, N_TASKS, N_MSGS = 3, 300, 40


class Client:
    def __init__(self, db, agent):
        env = dict(os.environ, WARROOM_DB=db, WARROOM_AGENT=agent)
        self.p = subprocess.Popen([sys.executable, os.path.join(HERE, "bus.py")], env=env, text=True,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.n = 0
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

    def rpc(self, method, params=None):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}) + "\n")
        self.p.stdin.flush()
        msg = json.loads(self.p.stdout.readline())
        assert msg["id"] == self.n and "error" not in msg, msg
        return msg["result"]

    def call(self, tool, **args):
        res = self.rpc("tools/call", {"name": tool, "arguments": args})
        assert not res.get("isError"), res
        return json.loads(res["content"][0]["text"])


def main():
    db = os.path.join(tempfile.mkdtemp(), "bus.sqlite3")
    seed = Bus(db, "orchestrator")
    for i in range(N_TASKS):
        seed.post_task(f"task {i}")
    clients = [Client(db, f"w{i}") for i in range(N_AGENTS)]
    assert len(clients[0].rpc("tools/list")["tools"]) == 10
    claimed, received = {}, {}
    gate = threading.Barrier(N_AGENTS)

    def work(c, name):
        mine = []
        gate.wait()  # start all claimers together so claims really contend
        while (t := c.call("claim_task")["task"]):
            mine.append(t["id"])
            assert c.call("complete_task", id=t["id"], result="ok")["ok"]
        claimed[name] = mine
        for j in range(N_MSGS):  # each agent messages the next one
            c.call("send", to=f"w{(int(name[1:]) + 1) % N_AGENTS}", body=f"{name}-{j}")
        c.call("checkpoint", summary=f"{name} done {len(mine)} tasks")

    threads = [threading.Thread(target=work, args=(c, f"w{i}")) for i, c in enumerate(clients)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    for i, c in enumerate(clients):
        got = []
        while (msgs := c.call("inbox")["messages"]):
            got += [m["body"] for m in msgs]
        received[f"w{i}"] = got
        assert c.call("last_checkpoint")["checkpoint"]["summary"].startswith(f"w{i} done")
        c.p.stdin.close()
        c.p.wait(timeout=10)

    all_claims = [t for ids in claimed.values() for t in ids]
    assert sorted(all_claims) == list(range(1, N_TASKS + 1)), "duplicate or missing claims"
    for i in range(N_AGENTS):
        sender = f"w{(i - 1) % N_AGENTS}"
        assert received[f"w{i}"] == [f"{sender}-{j}" for j in range(N_MSGS)], f"w{i} lost or duplicated messages"
    print("PASS", {k: len(v) for k, v in claimed.items()}, "claims;", {k: len(v) for k, v in received.items()}, "msgs")


if __name__ == "__main__":
    main()
