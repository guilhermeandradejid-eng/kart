"""Cycles review renders: studio lighting, turntable views, contact sheets.

Only used for art review while authoring; the game renders in Godot.
"""

import math
import os

import bpy
from mathutils import Vector

from . import sdf as S


def _world(color="#b9c8d8", strength=0.7):
    world = bpy.data.worlds.get("ReviewWorld") or bpy.data.worlds.new("ReviewWorld")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tex = nt.nodes.new("ShaderNodeTexGradient")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    # vertical gradient: warm floor bounce -> cool sky
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (*S.hexrgb("#6d6258"), 1)
    ramp.color_ramp.elements[1].position = 0.65
    ramp.color_ramp.elements[1].color = (*S.hexrgb(color), 1)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    del tex
    bpy.context.scene.world = world


def _area(name, loc, target, energy, size, color="#ffffff"):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    ld.color = S.hexrgb(color)
    lo = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = loc
    d = Vector(target) - Vector(loc)
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return lo


def studio(target=(0, 0, 0.4), radius=3.0, floor=True, floor_z=0.0, floor_color="#3a3d44"):
    """Three point lighting + grey cyclorama floor. Returns created objects."""
    created = []
    t = Vector(target)
    created.append(_area("Key", t + Vector((-1.6, -2.2, 2.4)) * radius / 3, t, 900 * (radius / 3) ** 2, 2.5, "#fff1e0"))
    created.append(_area("Fill", t + Vector((2.6, -1.2, 1.0)) * radius / 3, t, 300 * (radius / 3) ** 2, 3.0, "#dbe8ff"))
    created.append(_area("Rim", t + Vector((0.6, 2.8, 2.0)) * radius / 3, t, 700 * (radius / 3) ** 2, 1.5, "#ffffff"))
    if floor:
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, floor_z))
        fl = bpy.context.active_object
        fl.name = "ReviewFloor"
        m = bpy.data.materials.new("ReviewFloorMat")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*S.hexrgb(floor_color), 1)
        b.inputs["Roughness"].default_value = 0.6
        fl.data.materials.append(m)
        created.append(fl)
    _world()
    return created


def camera(target, dist, azimuth, elevation, lens=50):
    cam_data = bpy.data.cameras.new("ReviewCam")
    cam_data.lens = lens
    cam_data.clip_end = 2000
    cam = bpy.data.objects.new("ReviewCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    az = math.radians(azimuth)
    el = math.radians(elevation)
    t = Vector(target)
    # azimuth 0 = looking from the front (+Y side, since assets face +Y)
    cam.location = t + Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))) * dist
    d = t - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def render(path, size=(640, 480), samples=24, engine="CYCLES"):
    scn = bpy.context.scene
    scn.render.engine = engine
    if engine == "CYCLES":
        scn.cycles.samples = samples
        scn.cycles.device = "CPU"
        scn.cycles.use_denoising = True
        try:
            scn.cycles.denoiser = "OPENIMAGEDENOISE"
        except Exception:
            pass
        scn.cycles.max_bounces = 4
    scn.render.resolution_x, scn.render.resolution_y = size
    scn.render.resolution_percentage = 100
    scn.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in scn.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    try:
        scn.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def turntable(prefix, target=(0, 0, 0.4), dist=4.0, views=((-35, 18), (35, 18), (180, 20), (90, 5)),
              size=(480, 360), samples=20, lens=50, floor_z=0.0, radius=3.0):
    """Render several azimuth/elevation views and stitch a contact sheet."""
    lights = studio(target, radius=radius, floor_z=floor_z)
    paths = []
    for i, (az, el) in enumerate(views):
        cam = camera(target, dist, az, el, lens)
        p = f"{prefix}_{i}.png"
        render(p, size, samples)
        paths.append(p)
        bpy.data.objects.remove(cam, do_unlink=True)
    for o in lights:
        bpy.data.objects.remove(o, do_unlink=True)
    sheet = contact_sheet(paths, prefix + "_sheet.png")
    for p in paths:
        os.remove(p)
    return sheet


def contact_sheet(paths, out, cols=2):
    from PIL import Image

    ims = [Image.open(p) for p in paths]
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), (20, 20, 24))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(out)
    return out
