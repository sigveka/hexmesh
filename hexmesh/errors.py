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
Structured errors (decision 0040, foundation A; task 0094), a shared leaf:
every package may import it, and it imports nothing from hexmesh.

Every error a user's input can cause is a :class:`HexmeshError`, a
``ValueError`` that also carries:

- ``code``: the rule that failed, a stable ``snake_case`` key of
  :data:`CODES` (a code never changes once released; a new rule gets a new
  code);
- ``where``: any of ``fitting`` (the index), ``label``, ``interface``,
  ``field``, ``part``, ``source`` (provenance: file, line, …);
- ``value`` and ``limit``: the offending value and the bound it broke (a
  number, a range such as ``{"min_exclusive": 0.1}``, or the name of a
  ``limits.py`` constant);
- ``hint``: a fix, when there is one.

``str(err)`` is the message alone, and ``err.to_dict()`` gives every
field as JSON-safe data.  Warnings are :class:`HexmeshWarning` with the
same fields.  Each layer raises its own subclass: :class:`SpecError` in
``core`` and ``sections``, ``AssemblyError`` in ``assembly`` and the
builder, :class:`ReaderError` in ``interchange.importers``, ``LayoutError`` for block
layouts, ``EquipmentError``,
``StudyError``.  A former ``TypeError`` stays one (``SpecTypeError``,
``AssemblyTypeError``), and so does a former ``RuntimeError``
(``SpecUsageError``, ``study.openfoam.FoamCommandFailed``) or
``FileNotFoundError`` (``ReaderFileNotFound``; task 0106).

An internal invariant that fails is an :class:`InternalError` (code
``internal_invariant``): a bug in hexmesh, not the user's input.  It is a
``RuntimeError``, not a ``HexmeshError``, and its message asks for a
report.
"""

from __future__ import annotations

import math

__all__ = ["HexmeshError", "HexmeshWarning", "SpecError", "SpecTypeError", "SpecUsageError",
           "ReaderError", "ReaderFileNotFound", "GmshUnavailable", "InternalError", "CODES",
           "jsonable"]

#: where an :class:`InternalError` asks to be reported
ISSUES = "https://github.com/sigveka/hexmesh/issues"


def jsonable(x):
    """*x* as JSON-safe data: numbers, strings, lists and dicts (numpy
    scalars and arrays, tuples and sets converted; anything else as its
    ``repr``).  A non-finite float becomes its string ("inf", "nan")."""
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, int):
        return int(x)
    if isinstance(x, float):
        return x if math.isfinite(x) else str(x)
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in x]
    tolist = getattr(x, "tolist", None)              # numpy scalars and arrays
    if callable(tolist):
        return jsonable(tolist())
    return repr(x)


class _Fields:
    """The fields :class:`HexmeshError` and :class:`HexmeshWarning` share."""

    def _set(self, code, where, value, limit, hint):
        if code not in CODES:
            raise KeyError(f"{code!r} is not a registered error code (hexmesh.errors.CODES)")
        self.code = code
        self.where = dict(where or {})
        self.value, self.limit, self.hint = value, limit, hint

    def to_dict(self) -> dict:
        """Every field as JSON-safe data; ``type`` is the class name."""
        return {"type": type(self).__name__, "code": self.code, "message": str(self),
                "where": jsonable(self.where), "value": jsonable(self.value),
                "limit": jsonable(self.limit), "hint": self.hint}

    def __reduce__(self):
        # keyword fields survive pickling (the study runner's worker processes)
        return (_rebuild, (type(self), self.args, self.__dict__.copy()))


def _rebuild(cls, args, state):
    err = cls.__new__(cls)
    Exception.__init__(err, *args)
    err.__dict__.update(state)
    return err


class HexmeshError(_Fields, ValueError):
    """An error a user's input caused: the message, plus ``code``, ``where``,
    ``value``, ``limit`` and ``hint`` (module docstring)."""

    def __init__(self, message: str, *, code: str, where: dict | None = None,
                 value=None, limit=None, hint: str | None = None):
        super().__init__(message)
        self._set(code, where, value, limit, hint)

    @classmethod
    def wrap(cls, err: BaseException, message: str, *, code: str, **where):
        """A *cls* error with *message* (which quotes *err*), keeping *err*'s
        code, value, limit and hint when it is a :class:`HexmeshError`, else
        taking *code*; *where* adds to *err*'s location."""
        if isinstance(err, _Fields):
            return cls(message, code=err.code, where={**err.where, **where},
                       value=err.value, limit=err.limit, hint=err.hint)
        return cls(message, code=code, where=where)


class SpecError(HexmeshError):
    """A cross-section (``core``, ``sections``) that can't be built."""


class SpecTypeError(SpecError, TypeError):
    """A :class:`SpecError` for a wrong combination of arguments: still a
    ``TypeError``, as it was before task 0094."""


class SpecUsageError(SpecError, RuntimeError):
    """A :class:`SpecError` for ``PipeSpec`` methods called out of order
    (``core()`` twice, ``shell()`` first): still a ``RuntimeError``, as it
    was before task 0106."""


class ReaderError(HexmeshError):
    """A file an ``interchange.importers`` reader can't read (its units, its format);
    ``where["source"]`` names the file."""


class ReaderFileNotFound(ReaderError, FileNotFoundError):
    """A reader's input file that does not exist: still a
    ``FileNotFoundError`` (task 0106)."""


class GmshUnavailable(HexmeshError, ImportError):
    """gmsh could not be imported, so this call can't build or mesh: still
    an ``ImportError`` (task 0107).  The commands that only read and
    count work without gmsh."""


class InternalError(_Fields, RuntimeError):
    """An internal invariant that failed: a bug in hexmesh, not the user's
    input (task 0106).  Code ``internal_invariant``; the message asks for a
    report, with the input that caused it."""

    def __init__(self, message: str, *, where: dict | None = None, value=None):
        super().__init__(f"{message} (an internal check failed: this is a bug in hexmesh; "
                         f"please report it, with the input that caused it, at {ISSUES})")
        self._set(code="internal_invariant", where=where, value=value, limit=None, hint=None)


class HexmeshWarning(_Fields, UserWarning):
    """A warning with the fields of :class:`HexmeshError`."""

    def __init__(self, message: str, *, code: str, where: dict | None = None,
                 value=None, limit=None, hint: str | None = None):
        super().__init__(message)
        self._set(code, where, value, limit, hint)


#: Every code, with a one-line description of the rule.  Codes describe the
#: rule, not the fitting, and never change once released.
CODES: dict[str, str] = {
    "advice_budget_unreachable":
        "a cell budget advise can't meet; value is the closest result",
    "advice_calibration_scope":
        "advice is calibrated on developed flow in straight runs (advice note)",
    "advice_eight_x":
        "doubling every count gives 8× the cells (advice note)",
    "advice_fluid_unknown":
        "a fluid name advise has no properties for",
    "advice_input_invalid":
        "advise inputs that are missing or malformed",
    "advice_layout_unsupported":
        "advise on a rectangle in the O-H layout (calibrated for H only)",
    "advice_length_unit_suspect":
        "a geometry that looks like millimetres read as metres (advice note)",
    "advice_not_validated":
        "advice that rests on no validated case (advice note)",
    "advice_regime_transitional":
        "a section in transitional flow, graded as turbulent (advice note)",
    "advice_wall_function_unsupported":
        "wall functions asked of advise (they wait for task 0049)",
    "agent_input_type":
        "an agent function given something other than an Assembly or its description",
    "angle_looks_like_radians":
        "a fitting angle so small it was probably given in radians (warning)",
    "angle_on_duct_tap": "a Tee angle other than 90 on a duct tap",
    "angle_out_of_range": "a bend or wye angle outside its open range",
    "argument_missing": "a required fitting argument is missing",
    "assembly_already_built": "fittings added or changed after the assembly was built",
    "assembly_empty": "an assembly with no fittings",
    "bend_geometry_invalid": "a bend's ports and corner point give no valid bend",
    "bend_leg_not_along_pipe": "a bend's incoming leg does not continue the incoming pipe",
    "bend_radius_below_outer_radius": "a path bends tighter than the section's outer radius",
    "block_inverted": "a block of a layout is inverted or degenerate at a corner",
    "block_layout_invalid": "a fitting's block layout fails its checks",
    "branch_args_conflict": "a tee given both branch_radius and branch",
    "branch_length_too_short": "a tee branch does not reach past the main's wall",
    "branch_radius_out_of_range": "a pipe-tee branch radius not in (0, main radius)",
    "bundle_pipe_has_no_shells": "a bundle pipe with no shell layers",
    "bundle_pipe_outer_not_rectangle": "a bundle pipe whose outermost shell is not rectangular",
    "case_placeholder_unknown": "an OpenFOAM case template uses a placeholder with no parameter",
    "case_template_not_directory": "a study's case template is not a directory",
    "cell_budget_exceeded": "more cells than the budget (max_cells)",
    "chain_gap": "a network component does not start at the previous outlet",
    "chord_turn_above_maximum": "a sweep slab turns more than straight axial edges allow",
    "cli_input_unreadable":
        "a hexmesh CLI input file or argument that is missing or unreadable",
    "cli_spec_size_missing": "a CLI --spec list without an entry for a PCF nominal size",
    "close_onto_itself": "an interface closed onto itself",
    "close_source_not_outlet": "close() from an interface that is not an outlet",
    "close_target_not_inlet": "close() onto an interface that is not an inlet",
    "closure_ends_coincide": "a closure's source and target interfaces coincide",
    "closure_needs_close": "a Closure added directly instead of through Assembly.close()",
    "cores_exceeded": "more parallel ranks or jobs than the machine has cores",
    "corner_correspondence_ambiguous": "a slab twists by half the section's symmetry angle",
    "count_below_minimum": "a count (cells, layers, jobs) below its minimum or not an integer",
    "counts_mismatch": "cell counts that must match between two sections or sides do not",
    "cross_unsupported": "a network cross (four-way junction)",
    "curve_constraint_conflict": "a curve given two different transfinite constraints",
    "cut_names_ambiguous": "cut_at(names=…) on a port that meets more than one port",
    "description_format_invalid": "an assembly description in another format",
    "description_version_unsupported": "an assembly description of an unsupported version",
    "drum_axis_zero": "a drum with a zero axis",
    "drum_head_args_invalid": "a drum head's arguments do not fit its head type",
    "drum_name_invalid": "a drum name not made of letters, digits and _",
    "drum_up_parallel": "a drum whose up vector is parallel to its axis",
    "duct_tap_args_on_pipe": "duct-tap arguments given for a tee on a circular main",
    "duct_tap_needs_branch_shape": "a duct tap without a branch shape",
    "duct_tap_roll_invalid": "a duct tap's roll other than 0 or 180",
    "duct_tap_too_wide": "a duct tap too wide for the face it sits on",
    "elbow_needs_circle": "an ASME Elbow on a non-circular section",
    "equal_tee_unsupported": "an equal tee (branch as large as the main)",
    "extend_args_invalid": "negative extension lengths or cells_per_diameter",
    "faces_antiparallel": "two faces are antiparallel, so their corners can't be matched",
    "fill_failed": "a fitting failed while filling its volume",
    "fill_order_invalid": "a fill order that is not a permutation of the fittings",
    "first_cell_out_of_range": "a first cell not in (0, layer thickness]",
    "first_cell_unsupported": "first_cell= on a core that does not support it",
    "fitting_declares_no_strategies": "a fitting class without strategies (DESIGN A4)",
    "fitting_fields_unknown": "unknown fields in a fitting's description",
    "fitting_invalid": "a fitting fails its checks when added",
    "fitting_names_not_unique": "fitting names that are not unique",
    "fitting_not_resolved": "a fitting used before Assembly.add() resolved it",
    "fitting_not_serialisable": "a fitting type that can't be written to a description",
    "fitting_quality_warning": "a fitting's predicted quality is low (warning)",
    "fitting_type_unknown": "an unknown fitting type in a description",
    "full_width_tap_tunables": "pillowed-tap tunables given to a full-width duct tap",
    "gmsh_unavailable": "gmsh could not be imported: only build and meshing need it",
    "grading_args_conflict": "both mprg= and first_cell= given",
    "grading_unreachable": "no grading coefficient reaches the target with the cell count",
    "h_layout_needs_n_outer_4": "layout='h' with n_outer other than 4",
    "h_layout_needs_rectangle": "layout='h' on a non-rectangular core",
    "inlet_enters_junction_wrongly": "from the chosen inlet a junction is entered by a branch",
    "inlet_not_open_end": "the chosen inlet is not an open end of the network",
    "insulation_change_in_spline": "insulation starts or stops inside a spline run",
    "insulation_change_inside": "insulation thickness changes inside one component",
    "insulation_change_not_straight": "insulation changes where no straight component can hold it",
    "insulation_shell_exists": "insulation=True with a spec that already has an insulation shell",
    "insulation_thickness_change": "insulation changes between two non-zero thicknesses",
    "insulation_thickness_missing": "an insulated part in a network with no insulation thickness",
    "interface_degree": "an interface already used as the inlet or outlet of another fitting",
    "interface_not_in_assembly": "an interface from another assembly",
    "interface_not_open": "an interface that is not an open end",
    "internal_invariant": "an internal check that failed: a bug in hexmesh, to report",
    "join_direction": "join: two ports that don't face each other",
    "join_gap": "join: two ports farther apart than the tolerance",
    "join_port_not_open": "join: a port already connected to another",
    "join_section": "join: two ports with different sections",
    "joint_between_fittings":
        "a joint between two non-straight fittings, with no run to absorb it",
    "junction_degree": "more than two components meet at a point that is not a junction part",
    "junction_insulation_differs": "a junction's legs carry different insulation thicknesses",
    "junction_needs_rot_0_n_outer_4": "a junction on a section with rot != 0 or n_outer != 4",
    "junction_points_missing": "a network junction without its centre or branch points",
    "junction_roll_invalid": "a junction roll not a multiple of the section's period",
    "junction_run_not_along_pipe": "a junction's inlet run does not continue the incoming pipe",
    "junction_shells_not_circular": "non-circular shells through a junction",
    "junction_shells_unsupported": "shells on a junction that does not support them",
    "junction_size_missing": "a network junction without sizes on its ports",
    "kink_without_fitting": "a network changes direction without a fitting",
    "label_duplicate": "a fitting label already used",
    "label_invalid": "a fitting label not made of letters, digits and _",
    "layer_name_invalid": "a layer name not made of letters, digits and _",
    "layer_termination_not_outermost": "a layer that is not outermost stops or starts",
    "layer_termination_not_same_stack":
        "a stack change that is not the same stack with outer layers removed or added",
    "layer_termination_remaining_differ": "the layers that remain across a stack change differ",
    "layout_corners_invalid": "a face whose corners are not one per quadrant",
    "layout_not_supported": "a section layout that this fitting does not support yet",
    "layout_unknown": "an unknown section layout",
    "merge_id_clash": "merge: a port or part id in both models, without prefix=",
    "mesh_not_all_hex": "a mesh with elements other than hexahedra",
    "mesh_order_invalid": "a mesh order other than 1 or 2",
    "mesh_order_needs_volume": "order=2 asked of a surface or line mesh",
    "mesh_sj_not_positive": "a mesh with an inverted hex corner, converted with gmshToFoam's "
                            "orientation test on (warning)",
    "meshed_nonorth_above_maximum": "meshed non-orthogonality above OUTLINE_NONORTH_MAX",
    "meshed_nonorth_high": "meshed non-orthogonality high but allowed (warning)",
    "meshed_sj_below_minimum": "meshed corner scaled Jacobian below PREDICTED_SJ_MIN",
    "meshed_sj_low": "meshed corner scaled Jacobian low but allowed (warning)",
    "miter_cut_above_maximum": "each miter cut turns more than MAX_MITER_CUT",
    "miter_cut_below_minimum": "each miter cut turns less than MIN_MITER_CUT",
    "model_cut_bypassed": "a cut whose ports other ports still join",
    "model_id_duplicate": "a network-model port or part id already used",
    "model_id_unknown": "a port, part or network id not in the network model",
    "model_part_type_unknown": "a class that is not a network-model part type",
    "model_port_already_open": "cut_at on a port that meets no other port",
    "model_ports_not_met": "cut: two ports that aren't connected",
    "model_replay_needs_source": "replay: a log entry no registered importer can re-read",
    "model_undo_empty": "undo with no logged operation",
    "msh_format_invalid": "a file that is not a valid .msh file",
    "msh_has_no_recipe": "a .msh file without a hexmesh recipe",
    "n_layers_unresolvable": "no axial layer count up to the maximum passes the checks",
    "n_layers_unresolved": "n_layers used before Assembly.add() resolved it",
    "n_outer_invalid": "n_outer not a positive multiple of 4",
    "nang_missing": "a core given by size on a spec without nang",
    "nang_not_divisible": "nang not divisible by n_outer // 4",
    "network_disconnected": "a network that is not one connected piece",
    "network_empty": "a network model with no parts",
    "network_loop": "a network with a loop",
    "network_no_open_end": "a network with no open end",
    "network_no_valid_inlet": "no open end enters every junction through its inlet",
    "network_only_joints": "a network model with only joints",
    "network_piece_invalid": "one piece of a multi-piece network fails to build",
    "no_gmsh_session": "a call that needs a GMSH session outside one",
    "no_mesh_yet": "a call that needs the mesh before mesh()",
    "nozzle_footprint_outside": "a nozzle footprint crosses a drum tangent line",
    "nozzle_footprints_overlap": "two nozzle footprints overlap",
    "nozzle_location_unknown": "an unknown nozzle location",
    "nozzle_name_duplicate": "duplicate nozzle names on a drum",
    "nozzle_name_invalid": "a nozzle name not made of letters, digits and _",
    "nozzle_not_circular": "a drum nozzle with a non-circular layer",
    "nozzle_projection_too_short": "a nozzle projection that does not leave the drum shell",
    "nozzle_too_large": "a nozzle as large as the drum",
    "nozzle_unknown": "a drum has no nozzle of that name",
    "nrad_on_h_core": "nrad= on an H core, which has no ring",
    "offset_on_duct_tap": "a Tee offset other than 0 on a duct tap",
    "openfoam_boundary_unparsable": "an OpenFOAM boundary file that can't be parsed",
    "openfoam_command_failed": "an OpenFOAM command that exited with an error",
    "openfoam_needs_order_1": "write_openfoam asked for a second-order mesh",
    "openfoam_patches_unmapped": "OpenFOAM patches not in the role manifest (warning)",
    "openfoam_value_uniform": "an OpenFOAM field read as a list holds a uniform value",
    "option_invalid": "an option outside its allowed values",
    "other_runs_active": "other pytest or OpenFOAM runs are active on the machine",
    "other_runs_unchecked": "other runs on the machine can't be checked (warning)",
    "outlet_frame_mismatch": "an outlet interface that does not match the fitting's geometry",
    "outline_gap_too_small": "a layer outline too close to the outline inside it",
    "parameter_not_finite": "a study parameter value that is not finite",
    "parameter_not_json": "a study parameter value that is not JSON data",
    "part_kind_unsupported": "a network part of a kind the builder can't place",
    "part_rejected": "a network part the importer marked unbuildable",
    "pcf_component_incomplete":
        "a PCF component with fewer than two end points, skipped (warning)",
    "pcf_component_unsupported": "a PCF component type hexmesh does not read, skipped (warning)",
    "pcf_file_not_found": "a PCF path that does not exist",
    "pcf_no_files": "read_pcf given an empty list of files",
    "pcf_type_inferred": "an unknown PCF type read as an inline straight or reducer (warning)",
    "pcf_unit_scale_override": "unit_scale overrides the PCF's units header (warning)",
    "pcf_unit_unknown": "a PCF units header that is not recognised",
    "pcf_units_missing": "a PCF without a units header, read as millimetres (warning)",
    "pipe_tee_needs_circle": "a pipe tee on a non-circular main",
    "port_name_unknown": "an unknown port name for a fitting",
    "port_names_count": "a number of port names that does not match the fitting's outlets",
    "port_placement_mismatch": "a placed port misses the network's port position",
    "port_type_mismatch": "an interface's port type differs from the one the fitting declares",
    "post_result_not_dict": "a study's post-processing returns something other than a dict",
    "predicted_nonorth_above_maximum": "a junction's predicted non-orthogonality above OUTLINE_NONORTH_MAX",
    "predicted_sj_below_minimum": "a fitting's predicted scaled Jacobian below PREDICTED_SJ_MIN",
    "preflight_failed": "study preflight found failing variants",
    "prepend_at_equipment_end": "prepend at an equipment end",
    "prepend_needs_straight": "prepend of a fitting other than a Straight",
    "profile_chords_too_coarse": "a profiled reducer's wall chords too far from its profile",
    "profile_parameter_out_of_range": "a profile parameter outside its range",
    "profile_radii_mismatch": "a profile's end radii differ from the inlet's or outlet's",
    "profile_stations_too_few": "too few stations to resolve a profile's corners",
    "profile_table_invalid": "a profile table that is not a valid list of (s, r) pairs",
    "profile_too_short": "a profiled reducer too short for its profile",
    "profile_unknown": "an unknown profile",
    "quality_mode_unknown": "an unknown aggregation mode for a hex quality metric",
    "reader_format_invalid": "a file whose contents a reader can't use",
    "rect_stack_counts_unequal":
        "a rectangle stack whose outline counts differ from the core's, or unequal per side with a circle",
    "rect_stack_needs_n_outer_4": "a stack with a rectangle and n_outer other than 4",
    "reducer_axis_not_along_pipe": "a network reducer's axis does not continue the incoming pipe",
    "reducer_eccentric": "an eccentric network reducer",
    "reducer_grading_one_end": "a Reducer that grades only one end of an H duct",
    "reducer_layout_change": "a Reducer between different section layouts",
    "reducer_shape_change": "a Reducer between different outline shapes",
    "reducer_sizes_missing": "a network reducer without both sizes",
    "refine_factor_invalid": "a refinement factor that is not an integer >= 1",
    "role_manifest_format_unsupported": "a role manifest in an unsupported format",
    "roll_and_toward_conflict": "both roll and toward given",
    "roll_mismatch_ambiguous": "a roll mismatch of half the section's symmetry period",
    "rot_mismatch": "outlet and inlet sections differ in rot",
    "run_length_too_short": "a junction's run too short for its branch",
    "sampling_invalid": "a study's sampling block that is not valid",
    "section_nonorth_above_maximum":
        "a section's predicted non-orthogonality above OUTLINE_NONORTH_MAX",
    "second_order_inverted": "second-order hexes with a Jacobian determinant <= 0",
    "second_order_unsupported":
        "order=2 on a fitting that can't be raised to second order (the wye)",
    "section_not_supported": "a section (layout, n_outer) the assembly does not support",
    "section_predicted_sj_below_minimum":
        "a section's predicted scaled Jacobian below PREDICTED_SJ_MIN",
    "section_quality_reject": "a section rejected by its quality check",
    "section_quality_warning": "a section's predicted quality is low (warning)",
    "selection_invalid": "select() without exactly one of parts, network and from_port",
    "seton_host_missing": "a set-on with no straight pipe through its centre",
    "seton_host_too_short": "a set-on's host pipe too short around the branch",
    "seton_offset_branch":
        "an offset set-on without a branch straight, or whose branch axis misses its centre",
    "shape_args_conflict": "both shape= and geometry keywords given",
    "shape_args_missing": "neither shape= nor geometry keywords given",
    "shape_counts_mismatch": "a shape's cell counts differ from the spec's",
    "shape_not_serialisable": "a core shape that can't be written to a description",
    "shape_type_unknown": "an unknown shape type in a description",
    "shell_nrad_missing": "a shell without nrad",
    "shell_outline_args": "a shell given both or neither of dR and outer",
    "shell_type_unknown": "an unknown shell type in a description",
    "size_not_positive": "a size or length that must be positive is not",
    "source_not_interface": "a source that is not an Interface",
    "spec_core_twice": "PipeSpec.core() called a second time",
    "spec_no_core": "a PipeSpec used before core() defined its core",
    "spec_shell_before_core": "PipeSpec.shell() called before core()",
    "spline_points_coincide": "consecutive spline points coincide",
    "spline_points_invalid": "spline points that are not at least two 3-vectors",
    "spline_start_mismatch": "a spline that does not start at the inlet",
    "spline_tangent_zero": "a zero spline end tangent",
    "stack_change_inside_slab": "a stack change inside a sweep slab",
    "stack_change_keeps_layers": "a stack change that ends or starts no layer",
    "stack_changes_invalid": "stack_changes not at increasing interior cell boundaries",
    "stack_changes_need_n_layers": "stack_changes without an explicit n_layers",
    "stated_angle_disagrees": "a bend's stated angle disagrees with its geometry",
    "stated_radius_disagrees": "a bend's stated radius disagrees with its geometry",
    "study_block_invalid": "a study block that is not an object with its required key",
    "study_case_needs_openfoam": "a case stage without format openfoam",
    "study_function_invalid": "a study function not given as module:function",
    "study_function_not_found": "a study function that can't be imported",
    "study_key_unknown": "unknown keys in a study file",
    "study_not_json": "a study file that is not JSON",
    "study_not_object": "a study file that is not a JSON object",
    "study_not_run": "a study read before it was run",
    "study_placeholders_mismatch": "study placeholders and parameters that do not match",
    "study_run_needs_case": "a run stage without a case stage",
    "study_stage_missing": "a study run to a stage its file has no block for",
    "study_template_invalid": "a study template that is neither python nor json",
    "switch_changes_rectangle": "a Switch whose outlet rectangle differs from its inlet's",
    "switch_changes_shells": "a Switch whose outlet shells differ from its inlet's",
    "switch_class_not_bridged": "a spec change of a switch class without its bridge",
    "switch_class_not_declared": "a fitting that does not declare the switch class it needs",
    "switch_needed": "a spec change that needs a Switch",
    "switch_needs_oh_and_h": "a Switch that does not join an O-H and an H face",
    "switch_needs_outlet": "a Switch from an H inlet without outlet=",
    "switch_needs_rectangle": "a Switch on a non-rectangular core",
    "switch_too_short": "a switch shorter than its length rule",
    "tail_closed": "add() after the tail was closed, with no interface given",
    "tap_does_not_fit": "a duct tap that does not fit its main",
    "tap_ring_override_on_oh_main": "duct-tap ring overrides on an O-H main",
    "tee_angle_out_of_range":
        "a Tee's angle outside (0, 90] degrees",
    "tee_branch_angled": "a network tee whose branch leans upstream of the build direction",
    "tee_offset_out_of_range":
        "a Tee's offset past the main's wall or TEE_MAX_OFFSET_RATIO",
    "tee_ratio_above_max": "a pipe Tee's branch ratio above TEE_MAX_RATIO",
    "tee_run_asymmetric": "a network tee whose run ports are not symmetric",
    "terminal_end_taken": "an open end attached to two terminals",
    "terminal_name_duplicate": "two network ends with the same name",
    "terminal_no_open_end": "a terminal with no open pipe end at its position",
    "terminal_points_disagree": "a terminal's two positions disagree",
    "terminal_position_missing": "a terminal without a position",
    "topology_key_mismatch": "variants with one topology key but different connectivity",
    "toward_along_axis": "toward too close to the inlet axis",
    "toward_invalid": "toward that is not a nonzero 3-vector",
    "toward_needs_positive_angle": "toward with a negative angle",
    "toward_off_allowed": "toward not on an allowed direction of the section",
    "toward_on_duct_tap": "toward= on a duct tap",
    "transition_both_h": "a Transition with H layouts at both ends",
    "transition_layers_cross": "a Transition whose layer outlines cross",
    "transition_needs_shape_change": "a Transition between circles only",
    "transition_same_rectangle": "a Transition with the same rectangle at both ends",
    "transition_shape_unsupported": "a Transition layer that is neither circle nor rectangle",
    "value_not_positive": "a coefficient or ratio that must be positive is not",
    "variants_duplicate": "two study variants with the same parameters",
    "wall_bump_invalid": "wall_bump that is not two positive coefficients",
    "wall_bump_needs_h_layout": "wall_bump= on a core that is not H",
    "wall_projection_folded": "wall projection folded cells",
    "wall_projection_moves_node": "wall projection moves a node far (warning)",
    "with_radii_needs_dr_shells": "with_radii on a spec whose shells are not dR shells",
    "write_openfoam_needs_msh": "write_openfoam given a path that is not .msh",
    "wye_needs_circle": "a Wye on a non-circular core",
    "wye_shell_angle_below_minimum": "a shelled Wye below WYE_SHELL_MIN_ANGLE",
    "wye_shells_too_thick": "a Wye's shells thicker than its angle allows",
    "ypiece_asymmetric": "a network Y piece that is not symmetric and coplanar",
    "ypiece_daughter_size": "a network Y piece whose daughters differ in size from the stem",
    "ypiece_stem_missing": "a network Y piece without a stem pipe or branch points",
    "ypiece_stem_too_short": "a network Y piece's stem too short for the Wye's inlet run",
}
