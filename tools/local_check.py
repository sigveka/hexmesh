#!/usr/bin/env python3
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
The local check (decision 0055 rules 3 and 4; task 0178): what CI doesn't
run because it needs OpenFOAM, in about five minutes.  From the
repository root::

    python3 tools/local_check.py              # every step
    python3 tools/local_check.py --order      # and the MMS k = 2 levels
    python3 tools/local_check.py --require    # no OpenFOAM runner is a failure

``tools/hooks/pre-push`` (opt-in) runs it before a push whose commits
touch :data:`WATCHED`: ``git config core.hooksPath tools/hooks``.

Steps:

a. the ``openfoam``-marked runner and recipe tests (what CI's OpenFOAM
   job ran);
b. the volunteer try-out end to end: ``prepare``, ``run``, ``collect``
   and ``check`` on ``poiseuille try_np2``, in a temporary directory;
c. every fitting: the MMS case's 16 ``<fitting>_k1`` levels, each
   compared with its stored values, in parallel;
d. every volunteer card valid, and its levels known to its driver (no
   solving);
e. every export check's coarsest level, compared with its stored values,
   when its image is on this machine (``--no-exports`` leaves them out).

The runner is ``HEXMESH_OPENFOAM`` if set, else Docker's
``opencfd/openfoam-default:2406`` when ``docker`` answers.  Without one,
the steps that need OpenFOAM say "skipped: no OpenFOAM runner".  Nothing
is written to the cases' ``results.json``.  Exit status 0 when nothing
failed.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKER_RUNNER = "docker:opencfd/openfoam-default:2406"
TESTS = ("tests/test_openfoam_runner.py", "tests/test_msh_recipe.py")
TRY = ("poiseuille", "try_np2")
#: the MMS levels of decision 0055's note of 2026-11-18: one per fitting
FITTINGS = ("straight", "bend", "miter", "spline", "reducer", "transition", "tee",
            "tee_shells", "stack_change", "wye60", "wye90", "wye60_shell", "wye90_shell",
            "duct", "duct_tap_rect", "duct_tap_round")
#: each export check's coarsest level, as its driver's options
EXPORT_ARGS = {"fenicsx_second_order": ["--levels", "1"],
               "su2_poiseuille": ["--levels", "1"],
               "code_saturne_poiseuille": ["--levels", "1", "--mms-levels", "1"]}
#: a stored value and a new one agree within this, relative
REL_TOL = 1e-6
#: what a run records about itself, not about the mesh or the answer; and a
#: converged solve's last residual, round-off (about 1e-15) that differs run to run
NOT_COMPARED = {"environment", "name", "precision", "wall_s", "solve_s", "cores",
                "bend_wall_s", "contributed", "seconds", "peak_rss_gb",
                "last_initial_residual"}
PASS, FAIL, SKIP = "pass", "FAIL", "skipped"
#: a push touching these runs the check (the pre-push hook; decision 0055)
WATCHED = ("hexmesh/study/", "hexmesh/assembly/_output.py", "validation/")
#: what the hook passes when it can't list the pushed files: check anyway
UNKNOWN = "?"


def touched(files) -> list[str]:
    """The pushed *files* (repository paths, ``/``-separated) that the
    check covers; :data:`UNKNOWN` among them counts as one."""
    return [f for f in (x.strip() for x in files)
            if f == UNKNOWN or any(f == w or f.startswith(w) for w in WATCHED)]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exe(argv: list[str]) -> list[str]:
    """*argv* with its program resolved on ``PATH`` first (task 0173)."""
    found = shutil.which(argv[0])
    return [found, *argv[1:]] if found else list(argv)


def _run(argv: list[str], log: Path, env: dict | None = None, timeout: float = 3600) -> int:
    """Run *argv* from the repository root, its output to *log*; the exit
    status (124 on a timeout)."""
    with open(log, "w", encoding="utf-8") as out:
        try:
            return subprocess.run(_exe(argv), cwd=ROOT, stdout=out, stderr=subprocess.STDOUT,
                                  env={**os.environ, **(env or {})}, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            out.write(f"\nlocal_check: timed out after {timeout:.0f} s\n")
            return 124


def docker_answers() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(_exe(["docker", "info"]), stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def pick_runner(env: dict | None = None, docker=None) -> str | None:
    """``HEXMESH_OPENFOAM`` if set, else Docker's OpenFOAM when ``docker``
    answers (*docker*, by default :func:`docker_answers`), else ``None``."""
    env = os.environ if env is None else env
    if env.get("HEXMESH_OPENFOAM"):
        return env["HEXMESH_OPENFOAM"]
    return DOCKER_RUNNER if (docker or docker_answers)() else None


def image_present(image: str) -> bool:
    try:
        return subprocess.run(_exe(["docker", "image", "inspect", image]),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# --- comparing a level with its stored values -------------------------------------------

def differences(new, old, rel: float = REL_TOL, at: str = "") -> list[str]:
    """Where *new* and *old* (a level's values) differ: floats beyond
    *rel*, anything else unequal.  Keys in :data:`NOT_COMPARED` are left
    out; a stored key the new values lack is a difference, a new key isn't
    (a driver that records more)."""
    if isinstance(new, dict) and isinstance(old, dict):
        out = []
        for k in sorted(old):
            if k in NOT_COMPARED:
                continue
            if k not in new:
                out.append(f"{at}{k}: in the stored values only")
            else:
                out += differences(new[k], old[k], rel, f"{at}{k}.")
        return out
    if isinstance(new, list) and isinstance(old, list):
        if len(new) != len(old):
            return [f"{at.rstrip('.')}: {len(new)} items, stored {len(old)}"]
        return [d for i, (a, b) in enumerate(zip(new, old))
                for d in differences(a, b, rel, f"{at}{i}.")]
    if (isinstance(new, float) or isinstance(old, float)) and \
            isinstance(new, (int, float)) and isinstance(old, (int, float)) and \
            not isinstance(new, bool) and not isinstance(old, bool):
        if math.isclose(new, old, rel_tol=rel, abs_tol=1e-300):
            return []
        return [f"{at.rstrip('.')}: {new!r}, stored {old!r} ({new / old - 1:+.1e})"
                if old else f"{at.rstrip('.')}: {new!r}, stored {old!r}"]
    return [] if new == old else [f"{at.rstrip('.')}: {new!r}, stored {old!r}"]


def compare_levels(new_file: Path, stored_file: Path, rel: float = REL_TOL,
                   root: Path = ROOT) -> list[str]:
    """Every level in *new_file* against the level of its name in
    *stored_file* (named relative to *root*): the differences, each
    prefixed by the level's name."""
    new = json.loads(new_file.read_text(encoding="utf-8"))["levels"]
    old = {lv["name"]: lv for lv in json.loads(stored_file.read_text(encoding="utf-8"))["levels"]}
    out = []
    for lv in new:
        if lv["name"] not in old:
            out.append(f"{lv['name']}: not in {stored_file.relative_to(root).as_posix()}")
        else:
            out += [f"{lv['name']}: {d}" for d in differences(lv, old[lv["name"]], rel)]
    return out or ([] if new else [f"{new_file.name}: no levels were written"])


# --- the steps ----------------------------------------------------------------------------

def step_tests(runner: str, tmp: Path, args) -> tuple[str, str]:
    log = tmp / "a-tests.log"
    rc = _run([sys.executable, "-m", "pytest", "-q", "-n", "0", "-p", "no:cacheprovider",
               "-m", "openfoam", *TESTS], log, env={"HEXMESH_OPENFOAM": runner})
    tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1:]
    return (PASS if rc == 0 else FAIL), (tail[0] if tail else f"exit {rc}") + \
        ("" if rc == 0 else f"; log {log}")


def step_try(runner: str, tmp: Path, args) -> tuple[str, str]:
    case, level = TRY
    d, out = tmp / "try", tmp / "try-out"
    out.mkdir()
    vol = [sys.executable, "-m", "validation.volunteer"]
    for name, argv in (("prepare", [*vol, "prepare", case, level, "--dir", str(d),
                                    "--runner", runner]),
                       ("run", [*vol, "run", str(d)]),
                       ("collect", [*vol, "collect", str(d), "--out", str(out), "--delete"]),
                       ("check", [*vol, "check", str(out / f"{case}-{level}.contrib.json")])):
        log = tmp / f"b-{name}.log"
        if _run(argv, log) != 0:
            return FAIL, f"{name} failed; log {log}"
    return PASS, f"{case} {level}: accepted"


def _mms_level(fitting: str, k: int, runner: str, tmp: Path) -> tuple[str, float, list[str] | str]:
    t = time.monotonic()
    work, new = tmp / "mms" / f"{fitting}_k{k}", tmp / "mms" / f"{fitting}_k{k}.json"
    work.mkdir(parents=True)
    log = tmp / "mms" / f"{fitting}_k{k}.log"
    rc = _run([sys.executable, "validation/mms/run.py", "--cases", fitting, "--levels", str(k),
               "--work", str(work), "--json", str(new), "--openfoam", runner], log)
    if rc != 0 or not new.exists():
        return f"{fitting}_k{k}", time.monotonic() - t, f"exit {rc}; log {log}"
    return (f"{fitting}_k{k}", time.monotonic() - t,
            compare_levels(new, ROOT / "validation/mms/results.json"))


def step_fittings(runner: str, tmp: Path, args) -> tuple[str, str]:
    jobs = [(f, k) for f in FITTINGS for k in ((1, 2) if args.order else (1,))]
    bad, times = [], {}
    with cf.ThreadPoolExecutor(args.jobs) as pool:        # each level its own process
        for name, secs, got in pool.map(lambda j: _mms_level(*j, runner, tmp), jobs):
            times[name] = secs
            if got:
                bad.append(f"{name}: {got}" if isinstance(got, str) else
                           f"{name}: {len(got)} differences, first {got[0]}")
            print(f"    {name}: {'ok' if not got else 'FAIL'} ({secs:.0f} s)", flush=True)
    args.record["fitting_s"] = times
    if bad:
        return FAIL, "; ".join(bad)
    return PASS, f"{len(jobs)} levels match their stored values (slowest " \
                 f"{max(times, key=times.get)}, {max(times.values()):.0f} s)"


def step_cards(runner: str | None, tmp: Path, args) -> tuple[str, str]:
    vol = _load("volunteer", "validation/volunteer.py")
    bad, n = [], 0
    for case, card in vol.cards().items():
        drv = vol.driver(case)
        for level in card["levels"]:
            n += 1
            try:
                drv.check_level(level)
            except ValueError as e:
                bad.append(f"{case} {level}: {e}")
    if bad:
        return FAIL, "; ".join(bad)
    return PASS, f"{len(vol.cards())} cards, {n} levels known to their drivers " \
                 "(every case's card comes with task 0179)"


def _export(name: str, tmp: Path) -> tuple[str, float, str, list[str] | str]:
    cases = _load("cases", "validation/tools/cases.py")
    d = cases.path(name)
    drv = _load(f"{name}_run", f"{cases.rel(name)}/run.py")
    if not image_present(drv.IMAGE):
        return name, 0.0, SKIP, f"image {drv.IMAGE.split('@')[0]} not on this machine"
    t = time.monotonic()
    work, new, log = tmp / "exports" / name, tmp / "exports" / f"{name}.json", \
        tmp / "exports" / f"{name}.log"
    work.mkdir(parents=True)
    rc = _run([sys.executable, f"{cases.rel(name)}/run.py", *EXPORT_ARGS.get(name, []),
               "--work", str(work), "--json", str(new)], log)
    if rc != 0 or not new.exists():
        return name, time.monotonic() - t, FAIL, f"exit {rc}; log {log}"
    got = compare_levels(new, d / "results.json")
    return name, time.monotonic() - t, (FAIL if got else PASS), got


def step_exports(runner: str | None, tmp: Path, args) -> tuple[str, str]:
    cases = _load("cases", "validation/tools/cases.py")
    names = cases.names("export")
    if not docker_answers():
        return SKIP, "Docker doesn't answer"
    parts, status = [], PASS
    with cf.ThreadPoolExecutor(len(names) or 1) as pool:
        for name, secs, st, got in pool.map(lambda n: _export(n, tmp), names):
            args.record.setdefault("export_s", {})[name] = secs
            if st == FAIL:
                status = FAIL
                parts.append(f"{name}: " + (got if isinstance(got, str) else
                                            f"{len(got)} differences, first {got[0]}"))
            else:
                parts.append(f"{name}: {'ok' if st == PASS else got} ({secs:.0f} s)")
            print(f"    {name}: {st} ({secs:.0f} s)", flush=True)
    if status == PASS and all("not on this machine" in p for p in parts):
        status = SKIP
    return status, "; ".join(parts)


STEPS = (("a", "OpenFOAM runner and recipe tests", step_tests, True),
         ("b", "volunteer try-out end to end", step_try, True),
         ("c", "every fitting (MMS k = 1)", step_fittings, True),
         ("d", "volunteer cards and levels", step_cards, False),
         ("e", "export checks, coarsest level", step_exports, False))


def main(argv=None) -> int:
    from hexmesh.study.openfoam import physical_cores
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0].strip(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--order", action="store_true",
                    help="also the MMS k = 2 levels, which give an order of convergence")
    ap.add_argument("--require", action="store_true",
                    help="fail, rather than skip, when there is no OpenFOAM runner")
    ap.add_argument("--no-exports", action="store_true", help="leave out step e")
    ap.add_argument("--steps", default="abcde", help="the steps to run (default %(default)s)")
    ap.add_argument("--jobs", type=int, default=physical_cores(),
                    help="levels run at once in step c (default: the physical cores, "
                         "%(default)s); check for other runs first")
    ap.add_argument("--keep", action="store_true", help="keep the temporary directory")
    ap.add_argument("--if-touched", action="store_true",
                    help="read the pushed files from stdin, one per line (the pre-push "
                         "hook), and run only if one is under " + ", ".join(WATCHED))
    args = ap.parse_args(argv)
    args.record = {}
    if args.if_touched:
        hits = touched(sys.stdin.read().splitlines())
        if not hits:
            print("local check: not needed (the push changes nothing under "
                  f"{', '.join(WATCHED)})")
            return 0
        print(f"local check: the push changes {hits[0]}"
              + (f" and {len(hits) - 1} more" if len(hits) > 1 else ""), flush=True)
    runner = pick_runner()
    print(f"OpenFOAM runner: {runner or 'none (set HEXMESH_OPENFOAM, or start Docker)'}",
          flush=True)
    tmp = Path(tempfile.mkdtemp(prefix="hexmesh-local-check-"))
    rows, t0 = [], time.monotonic()
    for key, title, step, needs_openfoam in STEPS:
        if key not in args.steps or (key == "e" and args.no_exports):
            continue
        print(f"{key}. {title} ...", flush=True)
        t = time.monotonic()
        if needs_openfoam and runner is None:
            status, detail = (FAIL if args.require else SKIP), "no OpenFOAM runner"
        else:
            try:
                status, detail = step(runner, tmp, args)
            except Exception as e:                       # the next step still runs
                status, detail = FAIL, f"{type(e).__name__}: {e}"
        rows.append((key, title, status, time.monotonic() - t, detail))
        print(f"   {status}: {detail} ({rows[-1][3]:.0f} s)", flush=True)
    total = time.monotonic() - t0
    print("\nlocal check:")
    for key, title, status, secs, detail in rows:
        print(f"  {status:7} {key}. {title} ({secs:.0f} s)")
    failed = [r for r in rows if r[2] == FAIL]
    print(f"  total {total:.0f} s: {'FAILED' if failed else 'passed'}"
          + (f" ({len([r for r in rows if r[2] == SKIP])} skipped)"
             if any(r[2] == SKIP for r in rows) else ""))
    if args.record:
        (tmp / "times.json").write_text(json.dumps(args.record, indent=1), encoding="utf-8")
    if failed or args.keep:
        print(f"  logs kept in {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
