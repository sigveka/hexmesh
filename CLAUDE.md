# hexmesh — Claude context

## Project overview

Structured all-hex mesh generator for CFD pipe networks using GMSH. Pipes are built as transfinite hex blocks using an OH (O-grid + H-block) cross-section topology. Designed for OpenFOAM simulations; tet elements in junction zones are not acceptable.

**Read `DESIGN.md` first.** It defines the design principles and assembly rules (interfaces first-class, fittings are fills, conformal by construction). New code must follow it and must not add to its "Current deviations" table.

For fitting mathematics (frames, bend/miter geometry, tee/lateral intersection
curves, published bifurcation block topologies) see `docs/RESEARCH.md`;
citations in `docs/references.bib`, papers in `docs/papers/`.

---

## Cross-section topology: `n_outer` design

### Parameter separation

Two distinct kinds of parameters govern the OH cross-section:

**Topology** — structural decisions that fix where conformal interfaces land.
Cannot be changed without rebuilding geometry:
- `n_outer` — number of outer structural corners (4, 8, 16, …)
- `rot` — rotation of the outer corner frame
- layer structure (which materials, in what order)

**Density** — purely resolution; can be scaled without changing topology:
- `nang` — divisions per 90° arc
- `nrad` — nodes across each radial layer
- `n_layers` — nodes along the pipe axis (per connector)

### `n_outer` — the key parameter

`n_outer` controls how many structural corners sit on the outer circle.  Each
corner is separated by `360° / n_outer`.  The number of inner centre patches
is `(n_outer / 4)²` (a square grid sharing a centre node).

| `n_outer` | outer arc angle | centre patches | total surfaces (core) |
|-----------|-----------------|----------------|-----------------------|
| 4         | 90°             | 1              | 5                     |
| 8         | 45°             | 4              | 12                    |
| 16        | 22.5°           | 16             | 32                    |

**Constraint** — `nang` must be divisible by `n_outer / 4` so that each outer
arc gets a whole number of divisions:

```
nang % (n_outer // 4) == 0
```

Enforced in `PipeSpec.__post_init__`.  `n_outer` must itself be a multiple of 4.

### Why `n_outer=8` is the target

With `n_outer=4` (current), structural corners sit at ±45° and ±135°.  Two
junction types need corners at different positions:

- **T-junction**: saddle `tip_dn`/`tip_up` are at 0°/180° (along branch_dir) —
  currently arc midpoints.  The T-zone inlet cannot be a shared OCC surface;
  `removeDuplicateNodes()` is used as a workaround.
- **Y-junction**: bifurcation split plane runs through 90°/270° — currently arc
  midpoints.  `rot=-π/4` rotates corners there; `occ.fragment()` handles the
  resulting geometric overlap; SICN≈0 seam results.

With `n_outer=8`, corners sit at every 45° — including 0°, 90°, 180°, 270°.
Both junction problems become structurally correct:

- T-zone inlet IS a shared OCC surface → no `removeDuplicateNodes()`
- Y-junction split plane passes through corners naturally → no `rot=-π/4`,
  no `occ.fragment()`, no SICN seam

### `refinement` on `Network`

A single integer multiplier applied to all density parameters at mesh-generation
time:

```python
net = Network(PIPE, refinement=1)   # nang=6, nrad=4, n_layers as specified
net = Network(PIPE, refinement=2)   # nang=12, nrad=8, n_layers×2
net = Network(PIPE, refinement=4)   # nang=24, nrad=16, n_layers×4
```

`refinement` scales **node counts**, not element sizes.  Doubling `refinement`
gives 2× nodes in every direction → **8× cell count** in 3-D.  Document this
prominently; users from unstructured meshing expect a linear relationship.

Validation: `refinement` must be a positive integer.  Since `nang` is already
validated as divisible by `n_outer // 4` at `PipeSpec` construction, `nang ×
refinement` is guaranteed compatible for any positive integer `refinement`.

### Staged implementation plan

| Stage | What | Touches | Risk |
|-------|------|---------|------|
| 1 | `OHCircle8` face builder — 8-corner OH (isolated, no existing changes) | `faces/oh_circle.py` | Zero |
| 2 | `CrossSection` + `Annulus` support `n_outer ∈ {4,8,…}`; add explicit `n_outer` field; relax validation | `core/cross_section.py`, `faces/annulus.py` | Low |
| 3 | `fittings.py` generalisation — `range(4)` → `range(n_outer)` throughout | `connectors/fittings.py` | Medium |
| 4 | `Straight`, `Bend`, `MiterBend` — topology detection via `cs.n_outer` not surface count | `connectors/straight.py`, `bend.py` | Medium |
| 5 | `PipeSpec` `n_outer` kwarg + `Network` `refinement` kwarg | `core/pipe_spec.py`, `network.py` | Low |
| 6 | Y-junction redesign — remove `_ROT`, explicit bifurcation surface, eliminate `occ.fragment()` | `connectors/y_block.py`, `connectors/junction.py` | High |
| 7 | T-junction T-zone redesign — shared OCC surfaces at tips, eliminate `removeDuplicateNodes()` | `connectors/junction.py`, `connectors/t_block.py` | Medium |
| 8 | Make `n_outer=8` the default; deprecate `n_outer=4`; update all tests and examples | All | Low |

Gate for each stage: all existing tests still pass on the 4-corner path.

---

## Y-junction constraints (current, pre-Stage 6)

Stage 6 background (separation-plane and Hermite-butterfly bifurcation
templates, and whether `n_outer = 8` is required): `docs/RESEARCH.md` §4.

These constraints apply to the current `n_outer=4` implementation and will be
removed by Stage 6:

- Y-junction pipe specs **must** use `rot=-π/4` (inner square corners must land
  at E/N/W/S so the N-S split falls on boundaries, not arc midpoints)
- Without `rot=-π/4`, quality degrades to SICN ≈ 0 near split seams
- `y_block.py` hardcodes `_ROT = -math.pi/4`; do not remove without Stage 6
- `occ.fragment()` resolves geometric overlaps between primary and fill volumes;
  post-fragment surface recovery uses spatial bbox queries (fragile)
- Y-junction outlets have 6 patches (`[rc, lc, NE, NW, SW, SE]`); detected
  downstream via `is_split_core = (len(cs.surfaces) == 6)` in `straight.py`
  and `bend.py` — replace with `cs.n_outer` field in Stage 4

## Reducer/Expander constraints

- `Straight`, `Bend`, `MiterBend` must use a **single combined extrude/revolve call** for all layers; per-layer calls create duplicate coincident OCC corner points at layer interfaces → 5-edge surfaces → transfinite meshing failure
- See `fittings.py` `_connect_layer`: uses `all_inlet_set` (union of all layers) for end-face filtering

## nang semantics

- `nang` = divisions per 90° arc; same parameter reused for annular layers
- Constraint: `nang % (n_outer // 4) == 0` (each outer arc gets whole divisions)
- `nang=3` is valid only with `n_outer=4`; becomes invalid with `n_outer=8`

---

## T-junction implementation (staged fix)

### Why the current implementation is wrong

`TJunction.connect()` does two full-diameter extrusions both starting at `cursor.position` — overlapping volumes → duplicate CFD cells. No `occ.fragment()` is called.

### Side-tap architecture (small branch, r ≤ R)

1. **Main pipe**: two separate `Straight` extrusions (upstream half, downstream half) — no shared origin.
2. **Branch stub**: 5 hex volumes from the main pipe outer surface (saddle curve opening) to the branch OH inlet face.
3. **Branch**: normal `Straight` from the stub outlet.

For equal-diameter (r = R) the "main pipe passes through" shortcut breaks down — deferred as a separate case.

### Stage completion

| Stage | What | Status |
|-------|------|--------|
| 1 | `saddle_curve()`, `saddle_corners()` in `t_block.py` — pure math, no GMSH | ✅ Done |
| 2 | `build_stub_block()` in `t_block.py` — standalone 5-volume OH hex stub | ✅ Done |
| 3 | `outer_point_tags` parameter on `build_stub_block` — reuse pre-existing saddle corner point tags | ✅ Done |
| 4 | `spec` parameter on `build_stub_block` — PipeSpec multi-layer (fluid + pipe_wall shells) | ✅ Done |
| 5 | `branch_r` parameter on `TJunction` — side-tap stub block; non-overlapping geometry | ✅ Done |
| 6 | Roll angle generalisation (arbitrary φ) — already supported via `roll`/`branch_direction` | ✅ Done |
| 7 | T-zone conformality (step-cursor split, symmetric) — 268/268 tests | ✅ Done |
| 8 | `approach_length`/`departure_length` configurable; m_inner projection fix; T-zone E outer wall removed from physical groups — 271/271 tests | ✅ Done |

### `build_stub_block` API

**Location**: `hexmesh/connectors/t_block.py`

**Single-layer** (`spec=None`, default): `build_stub_block(origin, main_dir, branch_dir, R, r, branch_length, nang, nrad, n_axial, ratio, lc, outer_point_tags)`
- Returns `{"volumes": [5 tags], "branch_cs": CrossSection, "saddle_surfs": [5 surf tags]}`

**Multi-layer** (`spec=<PipeSpec>`): add `spec=PipeSpec(nang=…).core(…).shell(…)`; `r`/`nrad`/`nang` args ignored.
- Returns `{"volumes": [5+4·n_shells tags], "branch_lcs": LayeredCrossSection, "branch_cs": innermost CrossSection, "saddle_surfs": [5+4·n_shells surf tags]}`

**Common facts:**
- Corner index convention: `[0]=tip_dn, [1]=side_neg, [2]=tip_up, [3]=side_pos`
  (= top/left/bottom/right in the frame h_axis=e2, v_axis=e3).
- Saddle face outer curves are GMSH **splines** (not circle arcs).
- Saddle face inner edges are **straight lines**.
- `branch_length > R` enforced; `r = R` (equal-diameter) raises `ValueError`.
- `outer_point_tags`: optional `list[int | None]` of length 4 in order `[tip_dn, side_neg, tip_up, side_pos]`.
  Applies to the **outermost** saddle corners (r_outer). Pass a pre-existing tag to reuse it; `None` creates a new point.
- 60/60 tests pass (`tests/test_t_block.py` + `tests/test_connectors.py::TestTJunctionStub`).

### `TJunction` API (Stage 5+)

```python
TJunction(
    approach_length  = D,            # cursor-entry to T-point; must be >= branch_r
    departure_length = D,            # T-point to main outlet cursor; default 0
    branch_length    = D/2,          # T-point to branch outlet face (must be > R_outer)
    branch_direction = [1, 0, 0],    # global branch vector (or use roll=)
    roll             = 0.0,          # degrees around main pipe axis
    n_layers         = 2,
    branch_r         = 0.06,         # branch pipe outer radius; enables stub block path
)
```

- `approach_length`: total distance from cursor entry to T-point.  Must be ≥ `branch_r`.
  The last `branch_r` of the approach is the T-zone step (for conformality); if `approach_length > branch_r` a pre-step straight is added before it.
  Typical CFD value: 1–2 × main pipe diameter.
- `departure_length`: straight run from T-point to main outlet cursor (default `0.0`).
  Typical CFD value: 1–2 × main pipe diameter.
- `branch_r=None` (default): legacy overlapping extrusion (backward compat; incorrect for CFD)
- `branch_r<R_outer`: stub block path — non-overlapping all-hex geometry ✅
- `branch_r>=R_outer`: raises `ValueError` (equal-diameter not yet supported)
- `outlets[0]` = "main", `outlets[1]` = "branch"
- Stub volumes tracked in the same region as the inlet's innermost layer name
- Saddle surfaces cancelled (added to both inlets and outlets of stub region → omitted from physical groups)

### Stage 3 conformality note (reference)

The main pipe `Straight` outlet OH face outer arc corners are at angles ±45° and ±135° from
branch_dir. The saddle `tip_up`/`tip_dn` corners are at 0°/180°. The `side_pos`/`side_neg`
corners are at ±θ_max from branch_dir, where θ_max = arcsin(r/R).

For the tip corners: with `rot=π/4` and `h_axis=branch_dir` on the main pipe face,
`outer_points[3]` (at angle 0° from h_axis) = `tip_up` / `tip_dn` — these coincide exactly
and should be passed via `outer_point_tags[2]` / `[0]`.

For the side corners: coincide with a transfinite node only when θ_max is a multiple of 90°/nang.
Full side-corner conformality requires pre-splitting the main pipe outer arc at ±θ_max (future work).
The general intersection curve for any branch angle and axis offset (laterals, off-centre taps) and
the open `nang` sub-arc rule are in `docs/RESEARCH.md` §3.
