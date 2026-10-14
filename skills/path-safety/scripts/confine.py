"""Confine an untrusted relative path to a root directory. Stdlib only, Python 3.10+.

    from confine import confine
    target = confine(upload_root, request_name)   # raises UnsafePath
    with open(target, "rb") as f: ...             # use THIS path, never the raw name

python confine.py --self-check   runs the built-in tests.
python confine.py ROOT NAME      prints the confined path or the rejection reason.

The rules are strict on every OS, because a name that is harmless on Linux can
be an alias or a device on Windows (and files move between systems).
"""
import os
import re
import sys
import tempfile
from pathlib import Path

_DRIVE = re.compile(r"^[A-Za-z]:")  # C:\x and drive-relative C:x
_DEVICE = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9]|conin\$|conout\$)(\..*)?$", re.I)


class UnsafePath(ValueError):
    pass


def confine(root, name):
    """Return the resolved path for `name` inside `root`, or raise UnsafePath.

    `root` must exist. `name` may point at a file that does not exist yet.
    Symlinks inside root are followed and must still land inside root.
    """
    if not isinstance(name, str) or not name:
        raise UnsafePath("empty or non-string path")
    if "\x00" in name:
        raise UnsafePath("NUL byte")
    rel = name.replace("\\", "/")
    if rel.startswith("/") or _DRIVE.match(rel):
        raise UnsafePath("absolute, drive or UNC path")
    for part in rel.split("/"):
        if part == "..":
            raise UnsafePath("'..' segment")
        if part in ("", "."):
            continue
        if ":" in part:
            raise UnsafePath("':' in name (drive or alternate data stream)")
        if part[-1] in ". ":
            raise UnsafePath("trailing dot or space (Windows strips it, creating an alias)")
        if _DEVICE.match(part):
            raise UnsafePath("reserved Windows device name")
    base = Path(root).resolve(strict=True)
    target = (base / rel).resolve()
    if not target.is_relative_to(base):  # path-aware; str.startswith is not
        raise UnsafePath("resolves outside root (symlink or junction)")
    return target


def self_check():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        root = tmp / "ws"
        (root / "sub").mkdir(parents=True)
        (tmp / "ws_evil").mkdir()  # sibling sharing the root's string prefix
        root_r = root.resolve()

        for ok in ["a.txt", "sub/b.txt", "sub\\b.txt", "./sub/./c", "new/dir/file.bin", "...a"]:
            got = confine(root, ok)
            assert got.is_relative_to(root_r), (ok, got)

        bad = ["", "a\x00b", "../x", "sub/../../x", "..\\x", "/etc/passwd", "\\\\srv\\share\\f",
               "//srv/share", "C:\\Windows\\win.ini", "C:foo", "f.txt:stream", "f.txt::$DATA",
               "CON", "nul.txt", "sub/COM1.log", "a.", "a ", "..."]
        for b in bad:
            try:
                confine(root, b)
            except UnsafePath:
                continue
            raise AssertionError(f"accepted unsafe path {b!r}")

        linked = True
        try:
            os.symlink(tmp / "ws_evil", root / "link", target_is_directory=True)
        except (OSError, NotImplementedError):
            try:  # Windows without symlink privilege: a junction needs none
                import _winapi
                _winapi.CreateJunction(str(tmp / "ws_evil"), str(root / "link"))
            except (ImportError, OSError):
                linked = False
                print("note: link-escape test skipped (cannot create a symlink or junction)")
        if linked:
            try:
                confine(root, "link/secret")
                raise AssertionError("followed a symlink out of root")
            except UnsafePath:
                pass
            # The naive check this module replaces would have passed it:
            assert str((root / "link/secret").resolve()).startswith(str(root_r))
    print("self-check passed")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--self-check"]:
        sys.exit(self_check())
    if len(args) != 2:
        print(__doc__)
        sys.exit(2)
    try:
        print(confine(args[0], args[1]))
    except (UnsafePath, OSError) as exc:
        print(f"REJECTED: {exc}")
        sys.exit(1)
