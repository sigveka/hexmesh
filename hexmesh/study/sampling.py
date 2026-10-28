"""
Sampling (decision 0025): the same study file always gives the same
variants, in the same order.

* ``table``: ``{"rows": [{...}, ...]}`` or ``{"csv": "path"}`` (a header
  row of parameter names; numbers are read as int or float, anything
  else stays a string);
* ``grid``: ``{"name": [values], ...}``: the Cartesian product, the first
  parameter varying slowest;
* ``lhs``: ``{"ranges": {"name": [lo, hi], ...}, "n": N, "seed": S}``:
  a Latin hypercube, one sample per stratum of each range (numpy's
  ``default_rng(seed)``).

No ``sampling`` gives one variant: the fixed ``parameters``.
"""

from __future__ import annotations

import csv
import itertools

import numpy as np

from .definition import Study, StudyError


def _number(text: str):
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    return text


def samples(study: Study) -> list[dict]:
    """The sampled parameter dicts, without the fixed parameters."""
    s = study.sampling
    if s is None:
        return [{}]
    if not isinstance(s, dict) or len(s) != 1:
        raise StudyError("sampling must have exactly one of 'table', 'grid', 'lhs'")
    (kind, spec), = s.items()
    if kind == "table":
        if "rows" in spec:
            rows = spec["rows"]
            if not all(isinstance(r, dict) for r in rows):
                raise StudyError("sampling.table.rows must be a list of objects")
            return [dict(r) for r in rows]
        if "csv" in spec:
            with open(study.resolve(spec["csv"]), newline="") as f:
                return [{k.strip(): _number(v.strip()) for k, v in row.items()}
                        for row in csv.DictReader(f)]
        raise StudyError("sampling.table needs 'rows' or 'csv'")
    if kind == "grid":
        if not spec or not all(isinstance(v, list) and v for v in spec.values()):
            raise StudyError("sampling.grid needs a non-empty list per parameter")
        names = list(spec)
        return [dict(zip(names, combo)) for combo in itertools.product(*spec.values())]
    if kind == "lhs":
        ranges, n, seed = spec.get("ranges"), spec.get("n"), spec.get("seed")
        if not isinstance(ranges, dict) or not ranges:
            raise StudyError("sampling.lhs needs 'ranges': {name: [lo, hi]}")
        if not isinstance(n, int) or n < 1 or not isinstance(seed, int):
            raise StudyError("sampling.lhs needs an integer 'n' >= 1 and an integer 'seed'")
        rng = np.random.default_rng(seed)
        out = [{} for _ in range(n)]
        for name, (lo, hi) in ranges.items():
            u = (rng.permutation(n) + rng.random(n)) / n
            for row, v in zip(out, lo + (hi - lo) * u):
                row[name] = float(v)
        return out
    raise StudyError(f"unknown sampling {kind!r}; known: 'table', 'grid', 'lhs'")


def variants(study: Study) -> list[dict]:
    """Every variant's resolved parameters: the fixed ones updated by each sample."""
    return [{**study.parameters, **row} for row in samples(study)]
