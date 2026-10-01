"""Environment props for Turbo Turma - track 1 "Baia dos Coqueiros".

    bpython tools/blender/build.py props                 # export every prop
    bpython tools/blender/build.py props --preview       # + review sheets and catalog
    bpython tools/blender/build.py props --only=palm_a,rock_a --preview

Every prop is exported to assets/models/props/<name>.glb as ONE joined mesh
("<name>_mesh", one surface per material) parented to a root empty "<name>",
plus marker empties where noted (tiki_torch "flame", coconut_bomb "fuse").
Metres, Z up, props face +Y, origin at the base centre on the ground unless the
prop says otherwise. Colours live in the vertex "Color" attribute (linear);
foliage / cloth carry a wind weight in its alpha. Material names select the
Godot shader (see props_lib._SPEC).

The actual modelling lives in props_veg / props_rocks / props_beach /
props_race / props_game; each registers its builders with @prop.
"""

import json
import math
import os
import sys
import time

import numpy as np

from tt import core as C

REGISTRY = {}


def prop(name, **review):
    """Register `fn() -> (parts, empties)`; `review` tweaks the preview camera."""
    def deco(fn):
        REGISTRY[name] = (fn, review)
        return fn
    return deco


GROUPS = ("props_veg", "props_rocks", "props_beach", "props_race", "props_game")


def _load():
    import importlib
    for g in GROUPS:
        importlib.import_module(g)


def _only_from_argv():
    for a in sys.argv:
        if a.startswith("--only="):
            return [x for x in a.split("=", 1)[1].split(",") if x]
    return None


def build(out_models_root, preview=None, only=None):
    import props_lib as L
    _load()
    only = only or _only_from_argv()
    out_dir = os.path.join(out_models_root, "props")
    os.makedirs(out_dir, exist_ok=True)
    names = [n for n in REGISTRY if not only or n in only]
    stats_path = os.path.join(os.path.dirname(preview) if preview else out_dir, "props_stats.json")
    all_stats = {}
    if os.path.exists(stats_path):
        try:
            all_stats = json.load(open(stats_path))
        except Exception:
            all_stats = {}
    for name in names:
        fn, rv = REGISTRY[name]
        t0 = time.time()
        C.reset()
        parts, empties = fn()
        root, ob, st = L.finish(name, parts, out_dir, empties)
        st["seconds"] = round(time.time() - t0, 1)
        all_stats[name] = st
        print(f"[props] {name}: {st['tris']} tris, bbox {st['lo']} .. {st['hi']} ({st['seconds']} s)")
        if preview:
            os.makedirs(preview, exist_ok=True)
            review(ob, os.path.join(preview, name), rv)
    if preview:
        with open(stats_path, "w") as f:
            json.dump(all_stats, f, indent=1)
        if not only:
            catalog(preview)
    return all_stats


# ---------------------------------------------------------------------------
# Review renders
# ---------------------------------------------------------------------------


def _frame(ob, rv):
    V = C.vertex_array(ob)
    lo, hi = V.min(axis=0), V.max(axis=0)
    ctr = (lo + hi) / 2
    radius = 0.5 * float(np.linalg.norm(hi - lo))
    return lo, hi, ctr, radius


def outdoor(floor_z=0.0):
    """Sunny review lighting: warm sun + cool sky fill + neutral ground."""
    import bpy
    from tt import render as R
    from tt import sdf as S
    created = []
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy = 3.2
    sd.angle = math.radians(4)
    sd.color = S.hexrgb("#fff2dc")
    so = bpy.data.objects.new("Sun", sd)
    bpy.context.scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(42), 0, math.radians(-38))
    created.append(so)
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, floor_z))
    fl = bpy.context.active_object
    m = bpy.data.materials.new("ReviewFloorMat")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*S.hexrgb("#6b675c"), 1)
    b.inputs["Roughness"].default_value = 0.8
    fl.data.materials.append(m)
    created.append(fl)
    R._world("#9cc4ea", 0.9)
    return created


def review(ob, prefix, rv, size=(480, 400), samples=18):
    """Four-view sheet `<prefix>_sheet.png` + a catalog thumb `<prefix>_thumb.png`."""
    import bpy
    from tt import render as R
    lo, hi, ctr, radius = _frame(ob, rv)
    target = rv.get("target", tuple(ctr))
    lens = 50
    dist = rv.get("dist", radius / math.sin(math.radians(15.0)) * 1.02)
    floor_z = rv.get("floor_z", min(0.0, float(lo[2])))
    views = rv.get("views", ((-35, 18), (35, 18), (180, 20), (90, 6)))
    lights = outdoor(floor_z)
    paths = []
    for i, v in enumerate(views):
        az, el = v[0], v[1]
        tg = v[2] if len(v) > 2 else target
        if isinstance(tg, str):  # "top": upper part of the bbox (palm crowns etc.)
            tg = (float(ctr[0]), float(ctr[1]), float(hi[2] - 0.2 * (hi[2] - lo[2])))
        ds = v[3] if len(v) > 3 and v[3] else (dist * 0.42 if len(v) > 2 else dist)
        cam = R.camera(tg, ds, az, el, lens)
        p = f"{prefix}_{i}.png"
        R.render(p, size, samples)
        paths.append(p)
        bpy.data.objects.remove(cam, do_unlink=True)
    for o in lights:
        bpy.data.objects.remove(o, do_unlink=True)
    R.contact_sheet(paths, prefix + "_sheet.png")
    os.replace(paths[0], prefix + "_thumb.png")
    for p in paths[1:]:
        os.remove(p)
    return prefix + "_sheet.png"


def catalog(preview_dir, out=None, cols=8, tile=240):
    from PIL import Image, ImageDraw
    out = out or os.path.join(os.path.dirname(preview_dir), "props_catalog.png")
    names = [n for n in REGISTRY if os.path.exists(os.path.join(preview_dir, n + "_thumb.png"))]
    rows = (len(names) + cols - 1) // cols
    th = int(tile * 400 / 480)
    sheet = Image.new("RGB", (cols * tile, rows * (th + 18)), (24, 26, 30))
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        im = Image.open(os.path.join(preview_dir, n + "_thumb.png")).convert("RGB").resize((tile, th))
        x, y = (i % cols) * tile, (i // cols) * (th + 18)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + th + 3), n, fill=(235, 235, 235))
    sheet.save(out)
    print("catalog", out)
    return out
