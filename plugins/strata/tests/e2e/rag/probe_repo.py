import json, os, sys, time
os.environ["MOAA_STRATA_DIR"] = sys.argv[1]
sys.path.insert(0, sys.argv[2])
import rag
root = sys.argv[3]
prompts = [
    "how does the strata handoff decide the context window for a model",
    "where does the installer back up settings.json before changing it",
    "fix the War Room dashboard so the timeline shows agent names",
    "yes go ahead",
    "what is the capital of France and the population of Paris",
    "write me a haiku about the ocean waves at sunset",
    "update the moaa-catalog duplicate skill ranking to prefer enabled copies",
    "commit and push",
    "why does the council resolve command fail for forged members",
]
for p in prompts:
    t = time.time()
    out = rag.hook("prompt", json.dumps({"cwd": root, "prompt": p}))
    ms = (time.time() - t) * 1000
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
    heads = [l for l in ctx.splitlines() if l.startswith("### ")]
    print(f"{ms:6.0f} ms | {p[:60]:60} | {heads}")
