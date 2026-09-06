# Blender MCP Tools

Blender automation scripts written to be driven by an AI model over the
[Model Context Protocol](https://modelcontextprotocol.io), rather than by hand in the GUI.

![Rendered bat](examples/bat-render.png)

---

## Why this exists

Blender's Python API can build a scene from nothing — mesh, armature, weights, lighting,
camera, render settings. That makes it addressable by a language model: given an MCP server
exposing Blender's scripting interface, a model can construct and render a scene by writing
Python rather than clicking.

The interesting constraint is that a model cannot see the viewport. Everything has to be
deterministic and verifiable from code — which changes how you write the script.

## `animate_bat.py`

Builds a full animated sequence headlessly: rigs an existing mesh, weights it, animates a
wing flap, and renders to MP4 and a PNG frame sequence.

```sh
blender scene.blend --background --python animate_bat.py

# outputs go to ./out by default, or set your own:
BAT_OUT_DIR=/tmp/render blender scene.blend --background --python animate_bat.py
```

Produces `bat_animated.blend`, `bat_animated.mp4`, and `frames/frame_####.png` —
72 frames at 24fps, three flap cycles of a 3-second loop, rendered with EEVEE.

### What it does

**Cleans up before it builds.** A partial GUI run can leave an orphaned rig behind, so the
script removes any existing `BatRig` armature, its armature data, and the mesh's armature
modifier before starting. Re-running is therefore idempotent — the usual failure mode with
generated Blender scripts is a second run silently stacking a second rig on the mesh.

**Weights the armature geometrically.** Rather than relying on automatic weights, which are
unpredictable on generated geometry, vertex influence is computed from position — so the
result is the same every run, which is what you need when the caller cannot look at the
viewport to check.

**Fails loudly on a missing precondition.** If the expected mesh is absent it raises
immediately rather than rendering something empty. A silent empty render is far worse than
an error when nobody is watching the output.

## Writing Blender scripts for a model to run

A few things this script does deliberately, which apply to any headless Blender automation:

- **Never depend on selection state or context.** `bpy.ops` calls that rely on what is
  selected or which area is active behave differently in `--background`. Address objects
  directly via `bpy.data`.
- **Make it idempotent.** Assume it will be run repeatedly against the same file. Clear what
  you are about to create before creating it.
- **Compute, don't guess.** Anything the operator would normally eyeball — weights,
  placement, framing — needs to come out of arithmetic instead.
- **Parameterise output paths.** Hardcoded absolute paths are the first thing that breaks
  when a script leaves the machine it was written on.

## Requirements

Blender 3.x or later with Python scripting (bundled). No third-party packages.

## Licence

© William Ekuadzi. Published for review and demonstration. All rights reserved — not
licensed for reuse or redistribution.
