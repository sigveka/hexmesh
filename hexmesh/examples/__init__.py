"""
Runnable examples, grouped by what they illustrate.  Each writes
``<name>.msh`` to the current directory::

    python3 -m hexmesh.examples.fittings.smooth_bend

- ``fittings``: one fitting each, the building blocks.
- ``sections``: what runs through the pipe: layer stacks, rectangular
  ducts, transitions, grading.
- ``networks``: composing fittings into routes, branches and trees, in
  any orientation.
- ``applications``: equipment and engineering cases.

``CATEGORIES`` lists them in reading order, by package (the module
paths users run).  ``FAMILIES`` groups the feature examples by what a
reader looks for (bends, junctions, layers …); ``docs/gallery/build.py``
renders them into the gallery's Features and Applications pages.
"""

CATEGORIES: dict[str, list[str]] = {
    "fittings": ["smooth_bend", "miter_bend", "spline_pipe",
                 "reducer_network", "stenosis", "tee", "equal_tee", "wye", "junction_walls", "loop"],
    "sections": ["insulated_pipe", "insulated_route", "graded_bend",
                 "rect_duct", "duct_transition", "layer_outlines", "lagged_duct",
                 "insulated_transition", "insulated_tee", "insulated_network"],
    "networks": ["pipe_network", "pipe_rack", "distribution_tree",
                 "bifurcation_tree", "skewed_network"],
    "applications": ["drum_nozzle", "hvac_supply", "hvac_branched", "cooling_channels",
                     "pcf_line", "idealised_aorta"],
}

#: Every example as ``"<category>.<name>"``, in reading order.
ALL: list[str] = [f"{c}.{n}" for c, names in CATEGORIES.items() for n in names]

#: The feature examples grouped by family (decision 0050, task 0142): the
#: gallery's Features page, and later one ``docs/features/<family>.md``
#: each.  ``fittings`` are the API sections a reader needs for the family;
#: ``tags`` are the validation feature tags (``validation/case.schema.json``)
#: whose cases count as validating it.  Every example outside
#: ``applications`` belongs to exactly one family.
FAMILIES: dict[str, dict] = {
    "bends": {
        "title": "Bends",
        "intro": "A pipe that changes direction: a smooth circular arc, a "
                 "standard butt-weld elbow, a mitred bend of straight pieces, or a "
                 "pipe along a spline through given points.  Every bend carries "
                 "the whole cross-section, layers included.",
        "fittings": ["Bend", "Elbow", "MiterBend", "SplinePipe"],
        "tags": ["bend", "elbow", "miter", "spline"],
        "examples": ["fittings.smooth_bend", "fittings.miter_bend", "fittings.spline_pipe"],
    },
    "reducers": {
        "title": "Reducers and profiles",
        "intro": "A pipe that changes size: a concentric cone, or a profile "
                 "along the axis, such as a smooth constriction (a stenosis) or a "
                 "venturi.  The cell counts stay the same; only the sizes change.",
        "fittings": ["Reducer"],
        "tags": ["reducer", "profiled-reducer"],
        "examples": ["fittings.reducer_network", "fittings.stenosis"],
    },
    "junctions": {
        "title": "Junctions",
        "intro": "Where a network branches: a tee puts a side branch on a "
                 "pipe, a wye splits one pipe into two.  Junctions hold the "
                 "lowest-quality cells of a network, so their limits are checked "
                 "before meshing.",
        "fittings": ["Tee", "Wye"],
        "tags": ["tee", "duct-tap", "wye", "projection"],
        "examples": ["fittings.tee", "fittings.equal_tee", "fittings.wye",
                     "fittings.junction_walls"],
    },
    "sections": {
        "title": "Sections and transitions",
        "intro": "The shape of the pipe: round, or a rectangular duct, and "
                 "the fittings that change one into the other.",
        "fittings": ["PipeSpec", "Transition", "Switch"],
        "tags": ["section:circle", "section:rect", "transition", "switch"],
        "examples": ["sections.rect_duct", "sections.duct_transition"],
    },
    "layers": {
        "title": "Layers",
        "intro": "What surrounds the flow: a pipe wall, insulation, lagging, "
                 "each its own region for conjugate heat transfer.  Every "
                 "fitting carries the whole stack, and a layer can end or start "
                 "along a straight run.",
        "fittings": ["PipeSpec", "Straight"],
        "tags": ["layers", "stack-changes"],
        "examples": ["sections.insulated_pipe", "sections.insulated_route",
                     "sections.layer_outlines", "sections.lagged_duct",
                     "sections.insulated_transition", "sections.insulated_tee",
                     "sections.insulated_network"],
    },
    "grading": {
        "title": "Grading and resolution",
        "intro": "Where the cells go: thin cells at the wall for boundary "
                 "layers, axial cells clustered where the flow changes, and "
                 "straight runs added at the open ends for a CFD case.",
        "fittings": ["PipeSpec", "Assembly"],
        "tags": [],
        "examples": ["sections.graded_bend"],
    },
    "networks": {
        "title": "Building networks",
        "intro": "Fittings join in any order and any orientation: a network "
                 "is a sequence of `add` calls, branching from any open end, and "
                 "`close` joins two ends into a loop.",
        "fittings": ["Assembly", "Straight", "Closure"],
        "tags": ["straight", "closure"],
        "examples": ["fittings.loop", "networks.pipe_network", "networks.pipe_rack",
                     "networks.distribution_tree", "networks.bifurcation_tree",
                     "networks.skewed_network"],
    },
}
