# Blender MCP Tools

Blender automation written to be driven by an AI model over the
[Model Context Protocol](https://modelcontextprotocol.io), rather than by hand in the GUI.

![Wing-flap animation generated headlessly by animate_bat.py](examples/bat-animation.gif)

*72 frames at 24fps — armature, vertex weights, keyframes and render, produced entirely from
code with no GUI interaction.*

---

## The idea

```
   LLM  ──►  MCP server  ──►  Blender Python API  ──►  scene graph  ──►  render
                                                            │
                                          no viewport, no selection state,
                                          no visual confirmation available
```

Blender's Python API can build a scene from nothing — mesh, armature, weights, lighting,
camera, render settings. That makes it addressable by a language model: given an MCP server
exposing the scripting interface, a model can construct and render a scene by writing Python
instead of clicking.

The interesting constraint is that **the model cannot see the viewport.** It cannot select an
object and check it looks right, cannot nudge a bone and re-examine the deformation, cannot
tell that automatic weights have produced a mangled mesh. Everything has to be deterministic
and verifiable from code alone. That changes how the script has to be written.

## `animate_bat.py`

Builds a full animated sequence headlessly: rigs an existing mesh, weights it, animates a
wing flap, and renders to MP4 plus a PNG frame sequence.

```sh
blender scene.blend --background --python animate_bat.py

# output goes to ./out by default, or set your own:
BAT_OUT_DIR=/tmp/render blender scene.blend --background --python animate_bat.py
```

Produces `bat_animated.blend`, `bat_animated.mp4`, and `frames/frame_####.png` —
72 frames at 24fps, three flap cycles of a three-second loop, rendered with EEVEE.

### Three decisions that matter

**It cleans up before it builds.** A partial or interrupted run leaves an orphaned rig behind,
so the script removes any existing `BatRig` armature, its armature data, and the mesh's
armature modifier before starting. Re-running is therefore idempotent.

This is the failure mode that bites hardest when a model is driving the tool: the usual
result of a second run is a second rig silently stacked on the same mesh, producing deformation
that is wrong in a way nobody notices until the render comes out. An agent that retries after
a timeout will do this to you every time.

**It weights the armature geometrically.** Blender's automatic weights are unpredictable on
generated geometry and occasionally catastrophic. Vertex influence here is computed from
position instead, so the result is identical on every run — which is what you need when the
caller has no way to look at the mesh and judge.

**It fails loudly on a missing precondition.** If the expected mesh is absent the script
raises immediately rather than rendering an empty scene. A silent empty render is far worse
than an error when nobody is watching the output, because it looks like success.

## Writing Blender scripts for a model to run

Generalising from the above — things worth doing in any headless Blender automation:

- **Never depend on selection state or context.** `bpy.ops` calls that rely on what is
  selected, or which editor area is active, behave differently under `--background`. Address
  objects directly through `bpy.data`.
- **Make it idempotent.** Assume it will be run repeatedly against the same file. Clear what
  you are about to create before creating it.
- **Compute, don't guess.** Anything an operator would normally eyeball — weights, placement,
  framing, lighting — has to come out of arithmetic instead.
- **Fail fast and loudly.** Silent partial success is the expensive failure in an automated
  pipeline.
- **Parameterise output paths.** Hardcoded absolute paths are the first thing that breaks when
  a script leaves the machine it was written on.

## Requirements

Blender 3.x or later with its bundled Python. No third-party packages.

## Scope

This is an extract from a larger private toolchain, published so the approach can be read.
The MCP transport layer and its deployment configuration are deliberately not included.

## Licence

© William Ekuadzi. Published for review and demonstration. All rights reserved — not licensed
for reuse or redistribution.
