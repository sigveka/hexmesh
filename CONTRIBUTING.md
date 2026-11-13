# Contributing to hexmesh

Thank you for looking.  hexmesh builds structured all-hex meshes of pipe
and duct networks for CFD.  It is small and opinionated: everything it
does follows the rules in [DESIGN.md](DESIGN.md), and a change to those
rules is written down before it is coded.  This page says how to report a
problem, how to ask for something, and how changes are made here.

## Reporting a bug

Open an [issue](https://github.com/sigveka/hexmesh/issues) with:

1. **What you ran:** the network, as small as still shows the problem.
   An Assembly description (`asm.save("net.json")`), a PCF file, or the
   Python that builds it.
2. **What happened:** the full error.  hexmesh errors carry a code, a
   location, the offending value and the limit; from the `hexmesh` command,
   paste the whole JSON output.
3. **What you expected.**
4. **Versions:** hexmesh (`python3 -c "import hexmesh; print(hexmesh.__version__)"`),
   gmsh, Python and your OS, and OpenFOAM's if a case is involved.

An error that says *"this is a bug in hexmesh … please report it"* is an
internal check that should never fire.  Those reports are the most
useful of all.

Agents reporting on a user's behalf: the same list applies.  The output
of `hexmesh describe` and `hexmesh validate` on the network is a good
start.

## Asking for a feature

First check whether it exists or is planned:
- `hexmesh manifest` lists what each fitting supports, the limits and
  what has been validated;
- [DESIGN.md](DESIGN.md) lists the known gaps under
  [Current deviations](DESIGN.md#9-current-deviations);
- [docs/decisions/](docs/decisions/README.md) holds what has been decided
  and what is only proposed.

Then open an issue describing the network you want to mesh (a sketch or
a PCF file helps), what the mesh is for, and what fails today.

Out of scope by design: tetrahedra or pyramids anywhere, junctions
included; meshes that aren't conformal; hanging nodes.  A fitting that
can't be filled with structured hexes at acceptable quality is rejected
with an error, not meshed badly.

## How changes are made

hexmesh is developed by its maintainer with AI coding agents, working to
written rules:
- **[DESIGN.md](DESIGN.md)** holds the principles.  It changes only
  through a **decision record** in [docs/decisions/](docs/decisions/README.md):
  the context, the options, the choice and its consequences, and what was
  measured as opposed to assumed.
- **Tasks** in [docs/tasks/](docs/tasks/README.md) turn a decision into
  work: the steps, what counts as done, and the outcome with its numbers.
- **Validation gates are fixed before the runs.**  A case that misses is
  reported as a miss; nothing is tuned to pass.

For a contribution, this means:
- **Small fixes** (a bug, a wrong message, a broken link, a docs error):
  a pull request is welcome directly.
- **Anything that changes behaviour, the API or the design:** open an
  issue first, so it can become a decision before code is written.  A
  pull request that changes DESIGN.md's rules without one can't be merged
  as it is, however good the code.

Contributions written with AI tools are welcome on the same terms: you
are responsible for the change, and it must follow the same rules.

## Working on the code

```bash
pip install -e ".[dev]"     # from a checkout
python3 -m pytest -q        # the suite, in parallel; OpenFOAM and slow tests excluded
python3 -m pytest -q -m openfoam   # needs an installed OpenFOAM: most of these skip with Docker only
python3 -m pytest -q -m slow       # the package installed into a venv; the README example meshed
```

Before a pull request:
- **The suite passes**, including `tests/test_architecture.py`, which
  checks the package layers and that every error a user can meet is a
  coded `HexmeshError`.  A new error needs a registered code in
  `hexmesh/errors.py`, and a hint when there is a fix.
- **Meshes don't change by accident.**  If a change isn't meant to move
  nodes, the examples' meshes stay byte-identical: write them before and
  after (`python3 -m hexmesh.examples.<category>.<name>`) and compare.
- **The docs follow the code:** [API.md](API.md) for the public API, and
  an entry under *Unreleased* in [CHANGELOG.md](CHANGELOG.md).
- **Cell counts stay exact:** `Assembly.cell_count()` must equal the
  meshed count for anything you add.

**An optional pre-commit hook** runs `tests/test_architecture.py`
(about 15 s) before each commit, so a broken layer rule or platform rule
(a POSIX tool without `posix_only`, a bare path in compared text) shows
up before CI.  Opt in, per clone:

```bash
git config core.hooksPath tools/hooks      # opt in
git commit --no-verify                     # skip it once
git config --unset core.hooksPath          # opt out
```

It needs `python3` (or set `PYTHON=python`), and it tests the working
tree, not only what is staged.

Questions about the code are welcome as issues too.

## The docs site

The Markdown files are the docs: GitHub shows them as they are, and a
website is built from them (decision 0049).  Write plain Markdown; the
site needs nothing else.  To build and preview it you need
[Essens](docs/integrations/essens.md) on your `PATH`:

```bash
python3 docs/site.py                        # builds build/site/ (about 20 s)
python3 -m http.server -d build/site 8000   # then open http://localhost:8000
```

The build fails on an Essens error and on a broken relative link or
anchor, so run it after moving or renaming a heading or a file.  Two
things that show in the site but not on GitHub:
- a `<word>` in prose is read as HTML (GitHub hides it): put
  placeholders in a code span, `` `<fitting>` ``, or write *fitting*;
- `[[name]]` is an Essens cross-reference: quote it in a code span.

Layout and styles are in `docs/site/` (`page.html.tmpl`, `site.css`, and
the vendored simple.css and KaTeX); `docs/site.py` holds the sidebar's
order.

## Run a validation case

[validation/README.md](validation/README.md) is the guide: what to
install (OpenFOAM in Docker is enough), what each case costs, how to
run one, read its verdict and send the results back.

Some validation cases need more computing power than we have: a single
level can take hours on several cores.  If you have access to a cluster,
[validation/VOLUNTEERS.md](validation/VOLUNTEERS.md) lists what's on
offer and what each level costs (cores, memory, disk, wall time).  It
takes five commands, and you send back one small file, which we check
mechanically and merge with your credit.  Contributed results are under
the project's BSD-3 licence.

## Making a release

[docs/RELEASING.md](docs/RELEASING.md) is the checklist: CI, the
version, the CHANGELOG, the quick validation checks, the gallery, then
the tag and the GitHub release, which the maintainer approves.

## Licence

hexmesh is under the [BSD 3-Clause licence](LICENSE).  By contributing,
you agree that your contribution is licensed under it as well.
