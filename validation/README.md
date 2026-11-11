# Validation cases

One directory per case: `README.md` (the case), `case.json` (title,
status, gates), `run.py` (the driver), `results.json` (every level's
numbers) and `RESULTS.md` (the tables, gates and graphs).  The gallery's
Validation page (`docs/gallery/VALIDATION.md`) lists them.

From the repository root, with no OpenFOAM and no GMSH:

```bash
python3 -m validation.tools.recheck [case …]   # Richardson rows and gates from results.json
python3 -m validation.tools.plots [case …]     # figure.png, img/*.png and RESULTS.md's graphs
```

Regenerate the graphs whenever a case's `results.json` changes, then
commit them; `tests/test_validation_meta.py` fails on a stale one and
names the command.  Then rebuild the gallery's text:
`python3 docs/gallery/build.py --markdown-only`.
