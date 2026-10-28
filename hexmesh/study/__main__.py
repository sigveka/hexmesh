"""Command line: ``python3 -m hexmesh.study run|status|export study.json``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import STAGES, PreflightFailed, StudyError, export, load_study, run, status


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_mesh"]:                      # the mesh stage's worker
        from .stages import mesh_worker
        d, fmt, walls = argv[1:4]
        return mesh_worker(Path(d), fmt, walls == "1")
    ap = argparse.ArgumentParser(prog="python3 -m hexmesh.study",
                                 description="Run a hexmesh parameter study (decision 0025).")
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="preflight, then mesh, every variant")
    r.add_argument("study", type=Path)
    r.add_argument("--stage", choices=STAGES, default="mesh",
                   help="the last stage to run (default: mesh)")
    r.add_argument("--jobs", type=int, help="mesh processes at once (default: the study's, 1)")
    r.add_argument("--keep-going", action="store_true",
                   help="mesh the variants that pass preflight even if some fail")
    s = sub.add_parser("status", help="count the variants per status")
    s.add_argument("study", type=Path)
    e = sub.add_parser("export", help="write aligned arrays per topology key")
    e.add_argument("study", type=Path)
    args = ap.parse_args(argv)
    try:
        study = load_study(args.study)
        if args.command == "run":
            if args.jobs is not None and args.jobs < 1:
                ap.error("--jobs must be >= 1")
            rows = run(study, args.stage, args.jobs, args.keep_going, log=print)
            print(f"manifest: {study.output / 'study.csv'} ({len(rows)} variants)")
        elif args.command == "status":
            for k, n in sorted(status(study).items()):
                print(f"{k}: {n}")
        else:
            for key, path in export(study).items():
                print(f"{key}: {path}")
    except PreflightFailed as e:
        print(e, file=sys.stderr)
        return 2
    except StudyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
