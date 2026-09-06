"""Tests for the geometric vertex weighting in animate_bat.py.

The README claims the weighting is deterministic and reproducible, which is the
whole reason it exists rather than Blender's automatic weights. These tests are
what make that claim checkable instead of merely asserted.

They run without Blender: vertex_weights() is pure arithmetic by design, so it
imports cleanly even though the rest of the module needs bpy.

    python3 -m pytest tests/ -v
"""

import importlib.util
import pathlib
import sys
import types

# animate_bat.py imports bpy and mathutils at module level, neither of which
# exists outside Blender. Stub them so the pure function can be imported; the
# function under test touches neither.
for name in ("bpy", "mathutils"):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        if name == "mathutils":
            stub.Vector = tuple
        sys.modules[name] = stub

_spec = importlib.util.spec_from_file_location(
    "animate_bat", pathlib.Path(__file__).parent.parent / "animate_bat.py"
)
animate_bat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(animate_bat)

vertex_weights = animate_bat.vertex_weights
clamp = animate_bat.clamp

BONES = {"root", "spine", "head", "wing_R", "wing_R_tip", "wing_L", "wing_L_tip"}

# A spread of positions across the mesh: centre, each wing, each wing tip,
# the head, and points above and below the body.
SAMPLES = [
    (0.0, 0.0, 0.0),
    (0.3, 0.0, 0.0),
    (-0.3, 0.0, 0.0),
    (0.7, 0.0, 0.0),
    (-0.7, 0.0, 0.0),
    (0.0, -0.1, 0.1),
    (0.1, 0.2, -0.1),
    (0.55, -0.05, 0.05),
    (-0.55, -0.05, 0.05),
    (1.2, 0.5, 0.5),
    (-1.2, -0.5, -0.5),
]


def test_returns_every_bone():
    """Every bone must be present, or a vertex silently loses its influence."""
    for pos in SAMPLES:
        assert set(vertex_weights(*pos)) == BONES, f"missing bones at {pos}"


def test_weights_sum_to_one():
    """Normalisation invariant. If this drifts, the mesh deforms incorrectly."""
    for pos in SAMPLES:
        total = sum(vertex_weights(*pos).values())
        assert abs(total - 1.0) < 1e-9, f"weights sum to {total} at {pos}"


def test_weights_are_non_negative():
    """A negative influence would invert deformation on that bone."""
    for pos in SAMPLES:
        for bone, w in vertex_weights(*pos).items():
            assert w >= 0.0, f"{bone} = {w} at {pos}"


def test_deterministic():
    """The property the README depends on: identical input, identical output.

    The caller cannot inspect the viewport, so a run that differed between
    invocations would be undetectable until the render came out wrong.
    """
    for pos in SAMPLES:
        first = vertex_weights(*pos)
        for _ in range(50):
            assert vertex_weights(*pos) == first, f"non-deterministic at {pos}"


def test_mirrored_x_swaps_wings():
    """The rig is symmetrical, so mirroring x must swap left and right exactly."""
    for x, y, z in SAMPLES:
        if x == 0.0:
            continue
        right = vertex_weights(x, y, z)
        left = vertex_weights(-x, y, z)
        assert abs(right["wing_R"] - left["wing_L"]) < 1e-9
        assert abs(right["wing_L"] - left["wing_R"]) < 1e-9
        assert abs(right["wing_R_tip"] - left["wing_L_tip"]) < 1e-9
        assert abs(right["spine"] - left["spine"]) < 1e-9


def test_wing_tip_dominates_at_the_extremity():
    """Far out along a wing, the tip bone should carry the most influence."""
    w = vertex_weights(0.9, 0.0, 0.0)
    assert max(w, key=w.get) == "wing_R_tip", w
    w = vertex_weights(-0.9, 0.0, 0.0)
    assert max(w, key=w.get) == "wing_L_tip", w


def test_centre_has_no_wing_influence():
    """A vertex on the centreline must not be pulled by either wing."""
    w = vertex_weights(0.0, 0.0, 0.0)
    for bone in ("wing_R", "wing_L", "wing_R_tip", "wing_L_tip"):
        assert w[bone] == 0.0, f"{bone} = {w[bone]} on the centreline"


def test_clamp_bounds():
    assert clamp(-5.0) == 0.0
    assert clamp(5.0) == 1.0
    assert clamp(0.25) == 0.25
    assert clamp(7.0, 2.0, 4.0) == 4.0
