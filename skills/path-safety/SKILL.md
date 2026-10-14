---
name: path-safety
description: Prevent path traversal (arbitrary file read or write) in server and agent code. Use when writing or reviewing code that turns a client-, user- or LLM-supplied name into a filesystem path - download or upload routes, agent file tools (read, list, write), archive extraction, data loaders and connectors, workspace or sandbox setup. Ships a stdlib confine() helper with tests.
---

# Path safety

Any name that crosses a trust boundary (HTTP parameter, form field, archive entry, blob key, or an argument an LLM wrote for a tool call) is hostile until confined. One rule covers most of it: **resolve once inside a fixed root, check containment with a path-aware test, then use exactly that resolved path.**

`scripts/confine.py` implements that rule with no dependencies. Copy `confine()` into the project or port it; run `python scripts/confine.py --self-check` to see it pass, and `python scripts/confine.py ROOT NAME` to test one name. If the project already has a confinement helper, use that one everywhere instead and check it against the cases below.

## Rules

1. **Confine before every filesystem call.** Never `Path(root) / name` or `os.path.join(root, name)` on raw input. Joining an absolute path discards the root (`Path("/srv") / "/etc/passwd"` is `/etc/passwd`), and `..` walks out.
2. **Check containment on resolved paths, never with string prefixes.** `str(p).startswith(str(root))` accepts `/srv/ws_evil` for root `/srv/ws`. Use `resolved.is_relative_to(root.resolve())` (Python 3.9+); in Node, `path.relative(root, p)` must not start with `..` or be absolute.
3. **Use the path you checked.** Pass the confined path to `open` or `send_file`. A helper that takes the raw name again, such as Flask's `send_from_directory(dir, name)`, parses it a second time with different rules, so your check and the real access can disagree.
4. **LLM tool arguments are user input.** An agent's read, list or write tools get a confined root from the entry point and call `confine()` on every argument. Do not hand-roll a join and `relative_to` inside each tool.
5. **Extract archives entry by entry.** Zip and tar names can be `../x` or absolute ("zip slip"), and tar members can be links. Confine each member name; for tar on Python 3.12+ (and patched older releases) also pass `filter="data"` to `extractall`.
6. **Gate host-filesystem features by deployment.** A loader that reads any local path is fine in a single-user desktop app and is an open file-read on a shared server. Disable such features unless the deployment is single-user, and fail closed when the mode is unknown.
7. **Path checks do not contain generated code.** If LLM-written code runs in the server process, it can open any file. Multi-user deployments need a real sandbox (container or separate user); default to it in deployment templates.

## Failure modes the helper rejects

| Input | Why it is dangerous |
| --- | --- |
| `../x`, `a/../../x`, `..\x` | Walks out of the root. Backslash is a separator on Windows. |
| `/etc/passwd`, `C:\x`, `C:x`, `\\srv\share` | Absolute, drive or UNC path replaces the root. |
| `f.txt:stream`, `f.txt::$DATA` | NTFS alternate data streams. |
| `CON`, `nul.txt`, `COM1.log` | Windows device names, at any depth and with any extension. |
| `a.`, `a ` | Windows strips trailing dots and spaces, so these alias another file and dodge extension checks. |
| A symlink or junction inside the root that points out | Caught because the check runs after `resolve()`. |
| NUL byte, empty string | Truncation tricks and "the root itself". |

## Known limits

- **Link races.** `confine()` checks, then you open. If an untrusted party can create symlinks inside the root, they can swap one in between. Do not let untrusted users create links in served directories; on POSIX, opening with `O_NOFOLLOW` closes the last component.
- **Name policy is separate.** `confine()` decides *where* a file may live, not *which* names are allowed. Add an extension or name allow-list when serving only certain types.

## Quick review check

Search the change for risky patterns, then confirm each hit goes through the confinement helper:

```
rg -n "send_from_directory|startswith\(|os\.path\.join\(|extractall\(|Path\([^)]*\) */" <changed paths>
```

| Writing | Must do |
| --- | --- |
| Download route | `confine()` then `send_file(confined)`. |
| Upload or write | `confine()`, create parents under the confined path, set your own filename policy. |
| Agent file tool | Confined root from the entry point; `confine()` per argument. |
| Archive import | `confine()` per member; tar `filter="data"`. |
| Local-folder loader | Deployment gate; off on shared servers. |
| Deployment config | Sandbox on whenever more than one user shares the server. |
