"""Blender helpers shared by every Turbo Turma asset script.

Runs both with the `bpy` pip module (python3 tools/blender/build.py) and inside
a real Blender (blender -b -P tools/blender/build.py).

Conventions
-----------
* 1 unit = 1 metre. Z up. Assets face **+Y** in Blender, which the glTF
  exporter turns into **-Z** in Godot (Godot's forward), +X is right in both.
* Material names are contracts with Godot (scripts/kart/kart_paint.gd and
  scripts/character/driver_look.gd replace them by name):
    Paint, PaintAlt, Rim, Tire, Chrome, Metal, Plastic, Seat, Light, Glass,
    Decal, Fur, Eye, Nose, Mouth, Tongue, Teeth, Cloth, Scarf, Lens, Strap,
    Glove, Leaf, Bark, Rock, Sand, Wood, Straw, Rope, Water ...
* Vertex colours are linear floats in the "Color" attribute (glTF COLOR_0).
"""

import math
import os

import bpy  # noqa: F401  (must be imported before bmesh/mathutils with the pip module)
import bmesh
import numpy as np
from mathutils import Matrix, Vector

from . import sdf as S

FPS = 30

# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    scn.render.fps = FPS
    scn.frame_start = 0
    scn.unit_settings.system = "METRIC"
    return scn


def link(ob, collection=None):
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def empty(name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, size=0.1, kind="PLAIN_AXES"):
    """Sockets/markers. Exported as glTF nodes -> Node3D in Godot."""
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = kind
    ob.empty_display_size = size
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def deselect_all():
    for o in bpy.context.view_layer.objects:
        o.select_set(False)


def activate(ob):
    deselect_all()
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

_MAT_CACHE = {}


def material(name, color="#cccccc", rough=0.5, metal=0.0, emit=None, emit_strength=0.0,
             alpha=1.0, coat=0.0, use_vcol=False):
    """Principled material. `use_vcol` multiplies base colour by the "Color"
    attribute (so the glTF exporter writes COLOR_0 and Godot sees it)."""
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    col = S.hexrgb(color)
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*S.hexrgb(emit), 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    if use_vcol:
        # glTF semantics: COLOR_0 multiplies baseColorFactor, so a direct link
        # (factor = white) round-trips exactly.
        attr = nt.nodes.new("ShaderNodeVertexColor")
        attr.layer_name = "Color"
        nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    m.diffuse_color = (*col, 1.0)
    m.roughness = rough
    m.metallic = metal
    _MAT_CACHE[name] = m
    return m


def set_materials(ob, mats):
    ob.data.materials.clear()
    for m in mats:
        ob.data.materials.append(m)


# ---------------------------------------------------------------------------
# Mesh construction
# ---------------------------------------------------------------------------


def mesh_from_arrays(name, verts, faces, collection=None):
    """Fast mesh creation from numpy arrays (triangles or quads, uniform)."""
    me = bpy.data.meshes.new(name)
    verts = np.asarray(verts, dtype=np.float32)
    faces = np.asarray(faces, dtype=np.int32)
    nv = len(verts)
    nf, k = faces.shape
    me.vertices.add(nv)
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(nf * k)
    me.loops.foreach_set("vertex_index", faces.ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start", np.arange(0, nf * k, k, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, k, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    ob = bpy.data.objects.new(name, me)
    link(ob, collection)
    return ob


def mesh_from_pydata(name, verts, faces, collection=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update(calc_edges=True)
    ob = bpy.data.objects.new(name, me)
    link(ob, collection)
    return ob


def vertex_array(ob):
    me = ob.data
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(np.float64)


def face_centers(ob):
    me = ob.data
    c = np.empty(len(me.polygons) * 3, dtype=np.float32)
    me.polygons.foreach_get("center", c)
    return c.reshape(-1, 3).astype(np.float64)


def set_vertex_colors(ob, cols, name="Color"):
    me = ob.data
    if name in me.color_attributes:
        me.color_attributes.remove(me.color_attributes[name])
    attr = me.color_attributes.new(name=name, type="FLOAT_COLOR", domain="POINT")
    cols = np.asarray(cols, dtype=np.float32)
    rgba = np.ones((len(me.vertices), 4), dtype=np.float32)
    rgba[:, :cols.shape[1]] = cols
    attr.data.foreach_set("color", rgba.ravel())
    me.color_attributes.active_color = attr
    try:
        me.color_attributes.render_color_index = me.color_attributes.find(name)
    except Exception:
        pass


def set_face_materials(ob, mat_ids):
    ob.data.polygons.foreach_set("material_index", np.asarray(mat_ids, dtype=np.int32))


def shade_smooth(ob, smooth=True):
    n = len(ob.data.polygons)
    ob.data.polygons.foreach_set("use_smooth", np.full(n, smooth, dtype=bool))


def set_custom_normals(ob, normals):
    me = ob.data
    me.normals_split_custom_set_from_vertices([tuple(n) for n in normals])


def apply_modifiers(ob):
    activate(ob)
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except RuntimeError as e:
            print("modifier apply failed", ob.name, m.name, e)
            ob.modifiers.remove(m)


def decimate(ob, ratio=None, target_faces=None):
    n = len(ob.data.polygons)
    if target_faces:
        ratio = min(1.0, target_faces / max(n, 1))
    if ratio is None or ratio >= 0.999:
        return
    mod = ob.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    apply_modifiers(ob)


def apply_transform(ob):
    activate(ob)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def join(objs, name):
    objs = [o for o in objs if o is not None]
    deselect_all()
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def sdf_object(name, node, lo, hi, voxel=0.01, target_faces=None, materials=None,
               normals=True, smooth=True, collection=None, color_node=None, auto=True, alpha_fn=None):
    """`alpha_fn(p)` -> (N,) fills vertex-colour alpha (wind weight for foliage,
    flags and cloth: 0 = rigid, 1 = sways fully)."""
    """Polygonise an SDF tree into a Blender object with vertex colours,
    per-face materials (from node mat ids) and SDF-gradient normals."""
    if auto:
        try:
            lo, hi = S.auto_bounds(node, lo, hi, voxel_coarse=max(voxel * 3, 0.006))
        except ValueError:
            pass
    verts, faces = S.polygonise(node, lo, hi, voxel)
    ob = mesh_from_arrays(name, verts, faces, collection)
    if target_faces:
        decimate(ob, target_faces=target_faces)
    v = vertex_array(ob)
    cn = color_node or node
    _d, _m, cols = cn.attrs(v)
    if alpha_fn is not None:
        cols = np.concatenate([cols, np.clip(alpha_fn(v), 0, 1)[:, None]], axis=1)
    set_vertex_colors(ob, cols)
    if materials:
        set_materials(ob, materials)
        if len(materials) > 1:
            fc = face_centers(ob)
            _d, mids, _c = node.attrs(fc)
            set_face_materials(ob, np.clip(mids, 0, len(materials) - 1))
    shade_smooth(ob, smooth)
    if normals and smooth:
        set_custom_normals(ob, S.gradient(node, v))
    return ob


# ---------------------------------------------------------------------------
# Procedural hard-surface helpers
# ---------------------------------------------------------------------------


def lathe(name, profile, segments=48, axis="Z", mat=None, smooth=True, cap=True, collection=None,
          sharp=()):
    """Revolve a 2D profile [(radius, height), ...] around `axis`.

    `sharp` is a list of profile indices whose ring should get a hard edge
    (duplicated ring => split normals), e.g. the lip of a rim."""
    rings = []
    verts = []
    for (r, h) in profile:
        ring = []
        for s in range(segments):
            a = 2 * math.pi * s / segments
            x, y = r * math.cos(a), r * math.sin(a)
            ring.append(len(verts))
            verts.append((x, y, h))
        rings.append(ring)
    faces = []
    for i in range(len(rings) - 1):
        for s in range(segments):
            a = rings[i][s]
            b = rings[i][(s + 1) % segments]
            c = rings[i + 1][(s + 1) % segments]
            d = rings[i + 1][s]
            if profile[i][0] < 1e-6 and profile[i + 1][0] < 1e-6:
                continue
            faces.append((a, b, c, d))
    if cap:
        for ring, flip in ((rings[0], True), (rings[-1], False)):
            r = profile[0][0] if ring is rings[0] else profile[-1][0]
            if r > 1e-6:
                faces.append(tuple(reversed(ring)) if flip else tuple(ring))
    ob = mesh_from_pydata(name, verts, faces, collection)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    if axis == "X":
        ob.data.transform(Matrix.Rotation(math.radians(90), 4, "Y"))
    elif axis == "Y":
        ob.data.transform(Matrix.Rotation(math.radians(-90), 4, "X"))
    if mat:
        set_materials(ob, [mat])
    shade_smooth(ob, smooth)
    if smooth:
        add_smooth_by_angle(ob, 40)
    return ob


def add_smooth_by_angle(ob, angle_deg=35):
    """Hard edges above angle (Blender 4.1+ replaced auto-smooth with this)."""
    try:
        bpy.context.view_layer.objects.active = ob
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob],
                                       selected_editable_objects=[ob]):
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg), keep_sharp_edges=True)
    except Exception as e:  # pragma: no cover - older blender
        print("smooth by angle failed", e)


def tube(name, points, radius=0.02, segments=10, mat=None, closed=False, corner=0.0,
         collection=None, taper=None):
    """Round tube through 3D points (frames, handles, exhausts, rails).
    `corner` rounds polyline corners with that radius."""
    pts = [Vector(p) for p in points]
    if corner > 0 and len(pts) > 2:
        pts = _round_corners(pts, corner, closed)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = max(1, segments // 4)
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p.x, p.y, p.z, 1.0)
        if taper:
            sp.points[i].radius = taper(i / max(1, len(pts) - 1))
    sp.use_cyclic_u = closed
    ob = bpy.data.objects.new(name, cu)
    link(ob, collection)
    activate(ob)
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.view_layer.objects.active
    if mat:
        set_materials(ob, [mat])
    shade_smooth(ob, True)
    return ob


def _round_corners(pts, r, closed):
    out = []
    n = len(pts)
    rng = range(n) if closed else range(n)
    for i in rng:
        if not closed and (i == 0 or i == n - 1):
            out.append(pts[i])
            continue
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        a = (p0 - p1)
        b = (p2 - p1)
        la, lb = a.length, b.length
        rr = min(r, la * 0.45, lb * 0.45)
        a.normalize()
        b.normalize()
        s = p1 + a * rr
        e = p1 + b * rr
        for k in range(7):
            t = k / 6
            q = (1 - t) ** 2 * s + 2 * (1 - t) * t * p1 + t * t * e
            out.append(q)
    return out


def box(name, size=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0), mat=None, bevel=0.0, bevel_segments=3,
        collection=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    link(ob, collection)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    if mat:
        set_materials(ob, [mat])
    if bevel > 0:
        bev(ob, bevel, bevel_segments)
    return ob


def bev(ob, width=0.01, segments=3, angle=None, harden=True):
    mod = ob.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE" if angle else "NONE"
    if angle:
        mod.angle_limit = math.radians(angle)
    mod.harden_normals = harden
    shade_smooth(ob, True)
    add_smooth_by_angle(ob, 30)
    return mod


def weighted_normals(ob):
    mod = ob.modifiers.new("WN", "WEIGHTED_NORMAL")
    mod.keep_sharp = True
    return mod


def cylinder(name, r=0.1, depth=0.2, segments=32, loc=(0, 0, 0), rot=(0, 0, 0), mat=None,
             bevel=0.0, collection=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=r, radius2=r, depth=depth)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    link(ob, collection)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    if mat:
        set_materials(ob, [mat])
    if bevel > 0:
        bev(ob, bevel, 3, angle=40)
    else:
        shade_smooth(ob, True)
        add_smooth_by_angle(ob, 40)
    return ob


def array_radial(ob, count, axis="X"):
    """Duplicate `ob` count times around the origin axis and join."""
    objs = [ob]
    for i in range(1, count):
        c = ob.copy()
        c.data = ob.data.copy()
        link(c)
        ang = 2 * math.pi * i / count
        R = Matrix.Rotation(ang, 4, axis)
        c.matrix_world = R @ ob.matrix_world
        objs.append(c)
    for o in objs:
        apply_transform(o)
    return join(objs, ob.name)


def mirror_copy(ob, axis_index=0, name=None):
    c = ob.copy()
    c.data = ob.data.copy()
    link(c)
    s = [1, 1, 1]
    s[axis_index] = -1
    c.matrix_world = Matrix.Diagonal((*s, 1.0)) @ ob.matrix_world
    apply_transform(c)
    # flip normals after negative scale
    bm = bmesh.new()
    bm.from_mesh(c.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(c.data)
    bm.free()
    c.name = name or (ob.name + "_m")
    return c


def curve_text(name, text, size=0.2, depth=0.02, mat=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.size = size
    cu.extrude = depth
    cu.bevel_depth = depth * 0.3
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    link(ob)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    activate(ob)
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.view_layer.objects.active
    if mat:
        set_materials(ob, [mat])
    return ob


def fill_vertex_color(ob, color):
    set_vertex_colors(ob, np.tile(np.asarray(S.hexrgb(color)), (len(ob.data.vertices), 1)))


def recenter_origin(ob, origin=(0, 0, 0)):
    """Keep mesh data in part space: bake transforms, put origin at `origin`."""
    apply_transform(ob)
    ob.data.transform(Matrix.Translation(-Vector(origin)))
    ob.location = origin


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_glb(path, objects, animations=False, morph=False, vcols=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    view = bpy.context.view_layer
    view.update()
    deselect_all()
    for o in objects:
        o.select_set(True)
        for c in o.children_recursive:
            c.select_set(True)
    view.objects.active = objects[0]
    kw = dict(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_animations=animations,
        export_skins=True,
        export_morph=morph,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_extras=True,
        export_vertex_color="ACTIVE" if vcols else "NONE",
        export_all_vertex_colors=False,
    )
    if animations:
        kw.update(export_animation_mode="ACTIONS", export_force_sampling=True,
                  export_optimize_animation_size=False, export_anim_slide_to_zero=True,
                  export_reset_pose_bones=True)
    bpy.ops.export_scene.gltf(**kw)
    print("exported", os.path.relpath(path))
