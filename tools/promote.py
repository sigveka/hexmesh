#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
Move ``main`` to a commit CI has passed (decision 0052; task 0156).
From the repository root::

    git push origin HEAD:next                 # CI runs on next
    gh run watch                              # wait for it
    python3 tools/promote.py <sha>            # main moves to <sha>
    python3 tools/promote.py <sha> --dry-run  # the checks only

It refuses, and says why, unless:
- the newest ``tests`` run on *sha* is completed and every one of its
  jobs succeeded;
- *sha* is ``origin/main`` or a descendant of it (a fast-forward).

Then it runs ``git push origin <sha>:refs/heads/main``.  It needs ``git``
and ``gh`` (logged in); it never forces a push.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

WORKFLOW = "tests.yml"


class Refused(Exception):
    """A check failed: the message says which and what to do."""


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")


def _out(run, argv: list[str]) -> str:
    r = run(argv)
    if r.returncode != 0:
        raise Refused(f"{' '.join(argv[:3])} failed: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def resolve(sha: str, run=_run) -> str:
    """*sha* as a full commit hash."""
    r = run(["git", "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"])
    if r.returncode != 0 or not r.stdout.strip():
        raise Refused(f"{sha!r} isn't a commit here; git fetch first?")
    return r.stdout.strip()


def newest_run(sha: str, run=_run) -> dict:
    """The newest ``tests`` run on *sha*, completed, with every job green."""
    runs = json.loads(_out(run, ["gh", "run", "list", "--workflow", WORKFLOW, "--commit", sha,
                                 "--limit", "20", "--json",
                                 "databaseId,status,conclusion,createdAt,headBranch,event"]))
    if not runs:
        raise Refused(f"no {WORKFLOW} run on {sha[:7]}: push it to next first "
                      f"(git push origin {sha[:7]}:next), then gh run watch")
    latest = max(runs, key=lambda r: r["createdAt"])
    rid = latest["databaseId"]
    if latest["status"] != "completed":
        raise Refused(f"run {rid} on {sha[:7]} is {latest['status']}: gh run watch {rid}, "
                      "then promote again")
    jobs = json.loads(_out(run, ["gh", "run", "view", str(rid), "--json", "jobs"]))["jobs"]
    bad = [f"{j['name']}: {j['conclusion'] or j['status']}" for j in jobs
           if j["conclusion"] != "success"]
    if not jobs or bad or latest["conclusion"] != "success":
        raise Refused(f"run {rid} on {sha[:7]} isn't green ({latest['conclusion']}): "
                      + ("; ".join(bad) or "no jobs") + f".  See gh run view {rid}")
    return {**latest, "jobs": len(jobs)}


def fast_forward(sha: str, run=_run) -> str:
    """``origin/main`` (fetched now), if *sha* is it or descends from it."""
    _out(run, ["git", "fetch", "--quiet", "origin", "main"])
    main = _out(run, ["git", "rev-parse", "origin/main"])
    if run(["git", "merge-base", "--is-ancestor", main, sha]).returncode != 0:
        raise Refused(f"{sha[:7]} doesn't descend from origin/main ({main[:7]}): "
                      "rebase it on origin/main and push it to next again")
    return main


def promote(sha: str, dry_run: bool = False, run=_run) -> list[str]:
    """Check *sha* and, unless *dry_run*, push it to ``main``.  Returns
    what was found and done; raises :class:`Refused`."""
    full = resolve(sha, run)
    green = newest_run(full, run)
    main = fast_forward(full, run)
    lines = [f"{full[:7]}: run {green['databaseId']} ({green['headBranch']}, "
             f"{green['event']}) green, {green['jobs']} jobs",
             f"origin/main {main[:7]} -> {full[:7]}: "
             + ("already there" if main == full else "a fast-forward")]
    if main == full:
        return lines
    if dry_run:
        return lines + [f"dry run: would git push origin {full[:7]}:refs/heads/main"]
    _out(run, ["git", "push", "origin", f"{full}:refs/heads/main"])
    return lines + [f"pushed: main is {full[:7]}"]


def main(argv=None, run=_run) -> int:
    ap = argparse.ArgumentParser(prog="python3 tools/promote.py",
                                 description="Move main to a commit CI has passed.",
                                 epilog=__doc__.split("::\n\n", 1)[1].split("\n\n", 1)[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sha", help="the commit, as CI ran it on next")
    ap.add_argument("--dry-run", action="store_true", help="check only; don't push")
    args = ap.parse_args(argv)
    try:
        print("\n".join(promote(args.sha, args.dry_run, run)))
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
