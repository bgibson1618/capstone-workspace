#!/usr/bin/env python3
"""scrub_run.py — make a pipeline run dir shareable by removing the runner's host paths.

Interim bridge until the harness redacts paths at the source (team item #1: the
agent bakes its absolute sandbox CWD into memory content + logs transcript_path,
and the existing redactor doesn't cover host paths).

What it does:
  - Copies a run dir to a destination.
  - Drops binary stores (*.db / *.db-wal / *.db-shm) and lock files by default
    (binaries can't be safely text-scrubbed and aren't human-viewable).
  - Scrubs the *runner's own* paths out of every text file:
      <repo-root>/  -> ''        (repo-relative)
      <repo-root>   -> '.'
      $HOME/        -> '<home>/'
      $HOME         -> '<home>'
    Prefixes are derived from the env (git toplevel + $HOME), so it is NOT
    hardcoded to one user and any teammate can run it. Upstream dataset paths
    (e.g. another user's home baked into SWE-bench task data) are preserved.
  - HARD-VERIFIES the output: scans every output file (text AND binary) for any
    runner prefix; if any remains it deletes the output and exits non-zero, so it
    can never silently emit a leaky artifact.

Usage:
  python tools/scrub_run.py <src_run_dir> <dst_dir> [--force]
  python tools/scrub_run.py <src> <dst> --repo-root PATH --home PATH
  python tools/scrub_run.py <src> <dst> --keep-dbs   # copy DBs too (will FAIL
                                                      # verify unless truly clean)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BINARY_SUFFIXES = {".db", ".db-wal", ".db-shm"}
DROP_NAMES = {".dream.lock"}


def derive_subs(repo_root: Path | None, home: Path | None) -> list[tuple[str, str]]:
    subs: list[tuple[str, str]] = []
    if repo_root:
        r = str(repo_root).rstrip("/")
        subs.append((r + "/", ""))   # repo-relative
        subs.append((r, "."))        # bare repo root
    if home:
        h = str(home).rstrip("/")
        subs.append((h + "/", "<home>/"))
        subs.append((h, "<home>"))
    # longest source first so repo-root (under home) wins before home
    subs.sort(key=lambda s: len(s[0]), reverse=True)
    return subs


def is_text(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:8192]
    except OSError:
        return False
    if b"\x00" in chunk:
        return False
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("src", type=Path, help="source run dir (e.g. results/v...)")
    ap.add_argument("dst", type=Path, help="destination dir for the scrubbed copy")
    ap.add_argument("--repo-root", type=Path, default=None,
                    help="repo root to make relative (default: git toplevel of src)")
    ap.add_argument("--home", type=Path, default=None,
                    help="home dir to redact (default: $HOME)")
    ap.add_argument("--keep-locks", action="store_true", help="keep *.lock files")
    ap.add_argument("--keep-dbs", action="store_true",
                    help="copy binary DBs (WARNING: will fail verify if they hold paths)")
    ap.add_argument("--force", action="store_true", help="overwrite dst if it exists")
    args = ap.parse_args()

    src = args.src.resolve()
    if not src.is_dir():
        return _fail(f"src is not a directory: {src}")
    dst = args.dst.resolve()
    if dst == src or src in dst.parents:
        return _fail("dst must be outside src")
    if dst.exists():
        if not args.force:
            return _fail(f"dst exists (use --force): {dst}")
        shutil.rmtree(dst)

    repo_root = args.repo_root
    if repo_root is None:
        try:
            repo_root = Path(subprocess.check_output(
                ["git", "-C", str(src), "rev-parse", "--show-toplevel"],
                text=True, stderr=subprocess.DEVNULL).strip())
        except (subprocess.CalledProcessError, OSError):
            repo_root = None
    home = args.home or Path(os.path.expanduser("~"))
    subs = derive_subs(repo_root, home)
    if not subs:
        return _fail("no scrub prefixes — pass --repo-root and/or --home")

    copied = changed = dropped = 0
    for root, _, files in os.walk(src):
        for name in files:
            sp = Path(root) / name
            if name in DROP_NAMES:
                dropped += 1
                continue
            if sp.suffix in BINARY_SUFFIXES and not args.keep_dbs:
                dropped += 1
                continue
            if sp.suffix == ".lock" and not args.keep_locks:
                dropped += 1
                continue
            dp = dst / sp.relative_to(src)
            dp.parent.mkdir(parents=True, exist_ok=True)
            if is_text(sp):
                text = sp.read_text(encoding="utf-8", errors="surrogateescape")
                new = text
                for needle, repl in subs:
                    new = new.replace(needle, repl)
                dp.write_text(new, encoding="utf-8", errors="surrogateescape")
                changed += new != text
            else:
                shutil.copy2(sp, dp)
            copied += 1

    # HARD VERIFY: no runner prefix remains in ANY output file (text or binary)
    needles = [s.encode() for s, _ in subs]
    leaks: list[tuple[str, str]] = []
    for root, _, files in os.walk(dst):
        for name in files:
            data = (Path(root) / name).read_bytes()
            for nd in needles:
                if nd in data:
                    leaks.append((str(Path(root, name).relative_to(dst)), nd.decode()))
                    break

    print(f"copied {copied} file(s) ({changed} scrubbed), dropped {dropped}")
    print("scrub rules:")
    for needle, repl in subs:
        print(f"  {needle!r} -> {repl!r}")
    if leaks:
        print(f"\n!!! VERIFY FAILED — {len(leaks)} output file(s) still contain a runner path:",
              file=sys.stderr)
        for rel, nd in leaks[:10]:
            print(f"    {rel}: {nd}", file=sys.stderr)
        shutil.rmtree(dst)
        return 2
    print(f"\nOK verified clean — shareable copy ready: {dst}")
    return 0


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
