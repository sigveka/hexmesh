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

``CATEGORIES`` lists them in reading order; ``docs/gallery/build.py``
renders them into ``docs/GALLERY.md``.
"""

CATEGORIES: dict[str, list[str]] = {
    "fittings": ["smooth_bend", "miter_bend", "spline_pipe",
                 "reducer_network", "tee", "wye", "junction_walls", "loop"],
    "sections": ["insulated_pipe", "insulated_route", "graded_bend",
                 "rect_duct", "duct_transition", "layer_outlines", "lagged_duct",
                 "insulated_transition", "insulated_tee"],
    "networks": ["pipe_network", "pipe_rack", "distribution_tree",
                 "bifurcation_tree", "skewed_network"],
    "applications": ["drum_nozzle", "hvac_supply", "cooling_channels"],
}

#: Every example as ``"<category>.<name>"``, in reading order.
ALL: list[str] = [f"{c}.{n}" for c, names in CATEGORIES.items() for n in names]
