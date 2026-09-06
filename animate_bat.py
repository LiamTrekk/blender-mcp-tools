"""Headless bat flap: geometric armature weights, 3s loop, EEVEE mp4."""
import bpy
import os
import math
from mathutils import Vector

# Output directory: set BAT_OUT_DIR, or it defaults to ./out next to this script.
OUT_DIR = os.environ.get("BAT_OUT_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "out"
)
os.makedirs(os.path.join(OUT_DIR, "frames"), exist_ok=True)

OUT_BLEND = os.path.join(OUT_DIR, "bat_animated.blend")
OUT_MP4 = os.path.join(OUT_DIR, "bat_animated.mp4")
OUT_FRAMES = os.path.join(OUT_DIR, "frames", "frame_")

FPS = 24
FRAME_END = 72  # 3 seconds, 3 flap cycles of 24f
FLAP = 24


def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def vertex_weights(x, y, z):
    """Bone influences for a vertex at (x, y, z), normalised to sum to 1.0.

    Deliberately pure arithmetic with no bpy dependency: the caller cannot see
    the viewport, so weighting must be reproducible and testable rather than
    eyeballed. Blender's heat-map auto-weights were unpredictable on this mesh
    (and hung the GUI), so influence is derived from position instead.

    Kept importable without Blender so tests/test_weights.py can verify the
    determinism and normalisation this script depends on.
    """
    wr = clamp((x - 0.16) / 0.32)
    wl = clamp((-x - 0.16) / 0.32)
    tip_r = clamp((x - 0.50) / 0.28)
    tip_l = clamp((-x - 0.50) / 0.28)
    head_w = (
        clamp((-y - 0.00) / 0.14)
        * clamp(1.0 - abs(x) / 0.24)
        * clamp((z + 0.05) / 0.20)
    )
    body = clamp(1.0 - abs(x) / 0.34) * (1.0 - wr) * (1.0 - wl)
    spine_w = body * (1.0 - head_w * 0.7)
    weights = {
        "wing_R_tip": tip_r,
        "wing_L_tip": tip_l,
        "wing_R": wr * (1.0 - tip_r),
        "wing_L": wl * (1.0 - tip_l),
        "head": head_w * (1.0 - wr) * (1.0 - wl),
        "spine": spine_w,
        "root": 0.08 * (1.0 - wr) * (1.0 - wl),
    }
    total = sum(weights.values()) or 1.0
    return {name: w / total for name, w in weights.items()}


def main():
    scene = bpy.context.scene
    bat = bpy.data.objects.get("PhotorealBat")
    if bat is None:
        raise RuntimeError("PhotorealBat missing")

    # Clear leftover rigs from a partial GUI run (file on disk shouldn't have one)
    for name in list(bpy.data.objects.keys()):
        if name.startswith("BatRig"):
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    for arm in list(bpy.data.armatures):
        if arm.name.startswith("BatRig"):
            bpy.data.armatures.remove(arm)
    for mod in list(bat.modifiers):
        if mod.type == "ARMATURE":
            bat.modifiers.remove(mod)
    bat.parent = None

    arm_data = bpy.data.armatures.new("BatRig")
    rig = bpy.data.objects.new("BatRig", arm_data)
    bpy.context.collection.objects.link(rig)
    rig.show_in_front = True

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    def bone(name, head, tail, parent=None):
        b = eb.new(name)
        b.head = Vector(head)
        b.tail = Vector(tail)
        b.use_deform = name != "root"
        if parent:
            b.parent = eb[parent]
            b.use_connect = False
        return b

    bone("root", (0, 0, -0.12), (0, 0, 0.02))
    bone("spine", (0, 0.02, 0.02), (0, -0.02, 0.16), "root")
    bone("head", (0, -0.04, 0.16), (0, -0.18, 0.26), "spine")
    bone("wing_R", (0.14, 0.0, 0.12), (0.58, 0.02, 0.16), "spine")
    bone("wing_R_tip", (0.58, 0.02, 0.16), (0.92, 0.04, 0.10), "wing_R")
    bone("wing_L", (-0.14, 0.0, 0.12), (-0.58, 0.02, 0.16), "spine")
    bone("wing_L_tip", (-0.58, 0.02, 0.16), (-0.92, 0.04, 0.10), "wing_L")
    bpy.ops.object.mode_set(mode="OBJECT")

    # Geometric weights — no heat auto-weights (that hung the GUI on this mesh)
    keep = {"fur"}
    for vg in list(bat.vertex_groups):
        if vg.name not in keep:
            bat.vertex_groups.remove(vg)
    groups = {n: bat.vertex_groups.new(name=n) for n in (
        "root", "spine", "head", "wing_R", "wing_R_tip", "wing_L", "wing_L_tip"
    )}
    mesh = bat.data
    for v in mesh.vertices:
        x, y, z = v.co
        for name, nw in vertex_weights(x, y, z).items():
            if nw > 0.02:
                groups[name].add([v.index], nw, "REPLACE")

    arm_mod = bat.modifiers.new(name="Armature", type="ARMATURE")
    arm_mod.object = rig
    arm_mod.use_vertex_groups = True
    # Armature first, hair second
    while bat.modifiers.find(arm_mod.name) > 0:
        bpy.context.view_layer.objects.active = bat
        bpy.ops.object.modifier_move_up(modifier=arm_mod.name)
    if bat.particle_systems:
        bat.particle_systems[0].settings.use_modifier_stack = True
    bat.parent = rig
    bat.parent_type = "OBJECT"

    # Pose: rotation mode XYZ so we can key world-like eulers on local bones
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"

    def key(pb, frame, loc=None, rot=None):
        if loc is not None:
            pb.location = loc
            pb.keyframe_insert("location", frame=frame)
        if rot is not None:
            pb.rotation_euler = rot
            pb.keyframe_insert("rotation_euler", frame=frame)

    root = rig.pose.bones["root"]
    spine = rig.pose.bones["spine"]
    head = rig.pose.bones["head"]
    wrb = rig.pose.bones["wing_R"]
    wlb = rig.pose.bones["wing_L"]
    wrt = rig.pose.bones["wing_R_tip"]
    wlt = rig.pose.bones["wing_L_tip"]

    # 24-frame flap: +Y rot on right wing goes DOWN (Ry: z' = -x sin θ).
    # Right wing flap UP = negative Y. Left wing flap UP = positive Y.
    up_r = (0.0, math.radians(-28), math.radians(-6))
    down_r = (0.0, math.radians(22), math.radians(8))
    rest_r = (0.0, math.radians(-4), 0.0)
    up_l = (0.0, math.radians(28), math.radians(6))
    down_l = (0.0, math.radians(-22), math.radians(-8))
    rest_l = (0.0, math.radians(4), 0.0)
    tip_up_r = (0.0, math.radians(-18), 0.0)
    tip_down_r = (0.0, math.radians(14), 0.0)
    tip_up_l = (0.0, math.radians(18), 0.0)
    tip_down_l = (0.0, math.radians(-14), 0.0)

    # Three identical cycles so the clip loops
    for cycle in range(4):  # keys at 1, 25, 49, 73
        base = 1 + cycle * FLAP
        # hover: up on downstroke
        key(root, base, loc=(0, 0, 0.04), rot=(0, 0, 0))
        key(root, base + 6, loc=(0, 0, 0.02), rot=(math.radians(-2), 0, 0))
        key(root, base + 12, loc=(0, 0, 0.10), rot=(math.radians(4), 0, 0))
        key(root, base + 18, loc=(0, 0, 0.06), rot=(0, 0, 0))

        key(spine, base, rot=(math.radians(-2), 0, 0))
        key(spine, base + 12, rot=(math.radians(6), 0, 0))
        key(spine, base + FLAP, rot=(math.radians(-2), 0, 0))

        key(head, base, rot=(math.radians(4), 0, 0))
        key(head, base + 8, rot=(math.radians(-6), 0, 0))
        key(head, base + 16, rot=(math.radians(2), 0, 0))
        key(head, base + FLAP, rot=(math.radians(4), 0, 0))

        key(wrb, base, rot=rest_r)
        key(wrb, base + 6, rot=up_r)
        key(wrb, base + 12, rot=down_r)
        key(wrb, base + 18, rot=rest_r)
        key(wrb, base + FLAP, rot=rest_r)

        key(wlb, base, rot=rest_l)
        key(wlb, base + 6, rot=up_l)
        key(wlb, base + 12, rot=down_l)
        key(wlb, base + 18, rot=rest_l)
        key(wlb, base + FLAP, rot=rest_l)

        key(wrt, base, rot=(0, 0, 0))
        key(wrt, base + 6, rot=tip_up_r)
        key(wrt, base + 12, rot=tip_down_r)
        key(wrt, base + FLAP, rot=(0, 0, 0))
        key(wlt, base, rot=(0, 0, 0))
        key(wlt, base + 6, rot=tip_up_l)
        key(wlt, base + 12, rot=tip_down_l)
        key(wlt, base + FLAP, rot=(0, 0, 0))

    bpy.ops.object.mode_set(mode="OBJECT")

    # Blender 5.2 actions are layered (no action.fcurves). Cyclic flag is enough.
    if rig.animation_data and rig.animation_data.action:
        action = rig.animation_data.action
        if hasattr(action, "use_cyclic"):
            action.use_cyclic = True
        if hasattr(action, "use_frame_range"):
            action.use_frame_range = True
            action.frame_start = 1
            action.frame_end = FRAME_END + 1

    # Camera: slow 3/4 arc, always looking at the bat
    cam = bpy.data.objects.get("BatCam")
    if cam:
        target = bpy.data.objects.get("BatLook")
        if target is None:
            target = bpy.data.objects.new("BatLook", None)
            bpy.context.collection.objects.link(target)
        target.empty_display_size = 0.1
        target.location = (0.0, 0.0, 0.12)
        con = next((c for c in cam.constraints if c.type == "TRACK_TO"), None)
        if con is None:
            con = cam.constraints.new("TRACK_TO")
        con.target = target
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        cam.animation_data_clear()
        for f, ang in ((1, -18.0), (FRAME_END, 22.0)):
            r = 2.55
            a = math.radians(ang)
            cam.location = (math.sin(a) * r, -math.cos(a) * r, 0.42)
            cam.keyframe_insert("location", frame=f)

    scene.frame_start = 1
    scene.frame_end = FRAME_END
    scene.frame_current = 1
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False

    # EEVEE — Cycles at 3 min/frame would take ~4 hours
    engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    if "BLENDER_EEVEE_NEXT" in engines:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in engines:
        scene.render.engine = "BLENDER_EEVEE"
    eevee = getattr(scene, "eevee", None)
    if eevee:
        if hasattr(eevee, "taa_render_samples"):
            eevee.taa_render_samples = 32
        if hasattr(eevee, "use_raytracing"):
            eevee.use_raytracing = False

    import os
    os.makedirs(os.path.dirname(OUT_FRAMES), exist_ok=True)
    scene.render.filepath = OUT_FRAMES
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print("SAVED", OUT_BLEND)
    print("RENDER", scene.render.engine, "frames", scene.frame_start, scene.frame_end)
    bpy.ops.render.render(animation=True)
    print("DONE render")

    # This Blender build has no FFMPEG output; stitch with system ffmpeg if present.
    import glob
    import shutil
    import subprocess
    frames = sorted(glob.glob(os.path.dirname(OUT_FRAMES) + "/frame_*.png"))
    print("FRAME_COUNT", len(frames))
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and frames:
        subprocess.check_call([
            ffmpeg, "-y", "-framerate", str(FPS),
            "-i", os.path.dirname(OUT_FRAMES) + "/frame_%04d.png",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            OUT_MP4,
        ])
        print("MP4", OUT_MP4)
    else:
        print("NO_FFMPEG")


if __name__ == "__main__":
    main()
