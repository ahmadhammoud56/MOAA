import json, sys
for path in sys.argv[1:]:
    print("=====", path)
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        t, st = e.get("type"), e.get("subtype")
        if t == "system" and "hook" in str(st):
            if "UserPromptSubmit" in json.dumps(e):
                print("HOOK", st, json.dumps(e)[:700])
        elif t == "assistant":
            for b in e["message"]["content"]:
                if b.get("type") == "text":
                    print("TEXT:", b["text"][:600])
                elif b.get("type") == "tool_use":
                    print("TOOL:", b["name"], json.dumps(b["input"])[:300])
        elif t == "user":
            c = e["message"]["content"]
            if isinstance(c, list):
                for b in c:
                    if b.get("type") == "tool_result":
                        print("RESULT:", str(b.get("content"))[:200])
        elif t == "result":
            print("RESULT-END:", e.get("subtype"), e.get("num_turns"), str(e.get("result"))[:300])
