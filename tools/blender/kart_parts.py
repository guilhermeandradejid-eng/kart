"""Modular kart parts for Turbo Turma.

Every part is exported to assets/models/karts/<category>/<id>.glb in KART
SPACE (origin = kart origin on the ground between the axles), so the Godot
KartBuilder can drop any body/wing/engine onto any chassis without offsets.
Wheels are the exception: they are centred on their hub, axle along X, rim
facing +X (right side); Godot rotates them 180 degrees for the left side.

Layout (Blender, +Y forward, Z up):
    front axle y=+0.72, rear axle y=-0.55 (wheelbase 1.27 m)
    wheel sockets are at the hub centre for the *reference* radii
    (front 0.20, rear 0.24); the builder lifts the chassis for bigger wheels.
"""

import math
import os

import numpy as np

from tt import core as C
from tt import sdf as S

FRONT_Y = 0.72
REAR_Y = -0.55
FRONT_X = 0.57
REAR_X = 0.63
REF_FRONT_R = 0.20
REF_REAR_R = 0.24

# palette used for Blender review renders only (Godot repaints by name)
PAINT = "#e0342c"
PAINT_ALT = "#ffc93c"


def mats():
    return dict(
        paint=C.material("Paint", PAINT, rough=0.32, coat=0.6),
        alt=C.material("PaintAlt", PAINT_ALT, rough=0.35, coat=0.4),
        rim=C.material("Rim", "#ffd23f", rough=0.3, metal=0.2),
        tire=C.material("Tire", "#3b3b45", rough=0.85),
        chrome=C.material("Chrome", "#d9dde3", rough=0.15, metal=1.0),
        metal=C.material("Metal", "#9aa0aa", rough=0.35, metal=0.9),
        plastic=C.material("Plastic", "#2c2d33", rough=0.55),
        seat=C.material("Seat", "#33343c", rough=0.7),
        light=C.material("Light", "#fff4c8", rough=0.2, emit="#fff0b0", emit_strength=4.0),
        decal=C.material("Decal", "#f4f4f0", rough=0.4),
    )


# ---------------------------------------------------------------------------
# Wheels
# ---------------------------------------------------------------------------

WHEELS = {
    # id: (front r, front width, rear r, rear width, tread, rim style)
    "standard": dict(fr=0.20, fw=0.17, rr=0.24, rw=0.25, tread="grooves", rim="spokes5"),
    "slick": dict(fr=0.19, fw=0.21, rr=0.23, rw=0.31, tread="slick", rim="dish"),
    "monster": dict(fr=0.27, fw=0.22, rr=0.30, rw=0.29, tread="knobs", rim="beadlock"),
    "mini": dict(fr=0.16, fw=0.14, rr=0.18, rw=0.18, tread="whitewall", rim="star"),
}


def _tire(name, r, w, tread, m):
    """Tire around local Z (axle), later rotated to X."""
    r_in = r * 0.56
    rc = (r + r_in) * 0.5
    a = (r - r_in) * 0.5
    b = w * 0.5

    def prof(rad, ax):
        # boxy superellipse cross-section, with a slight sidewall bulge
        return S.superellipse2d(rad - rc, ax, a, b * (1.0 + 0.06 * np.clip(1 - np.abs(rad - rc) / a, 0, 1)), n=3.2)

    base = S.Revolved(prof, color="#3b3b45")
    shape = base
    if tread == "grooves":
        groove = S.Revolved(lambda rad, ax: np.maximum(
            np.minimum(np.abs(ax - b * 0.42), np.abs(ax + b * 0.42)) - w * 0.035,
            -(rad - (r - 0.012))))
        shape = S.Subtract(base, groove, k=0.004)
        # chevron sipes
        sipe = S.Box((0.012, 0.004, b * 0.30), round=0.002).rot(0, 0, 0).at(r, 0, 0)
        shape = S.Subtract(shape, S.PolarRepeat(sipe, 36), k=0.002)
    elif tread == "knobs":
        core = S.Revolved(lambda rad, ax: S.superellipse2d(rad - (rc - 0.02), ax, a - 0.02, b * 0.96, n=3.0))
        knob = S.Box((0.03, 0.035, b * 0.42), round=0.012).at(r - 0.03, 0, b * 0.45)
        knob2 = S.Box((0.03, 0.035, b * 0.42), round=0.012).at(r - 0.03, 0, -b * 0.45)
        knobs = S.Union(S.PolarRepeat(knob, 18), S.PolarRepeat(knob2, 18, phase=10))
        shape = S.Union(core, knobs, k=0.012)
    elif tread == "whitewall":
        pass
    ob = C.sdf_object(name, shape, (-r - 0.05, -r - 0.05, -b - 0.05), (r + 0.05, r + 0.05, b + 0.05),
                      voxel=0.0045, target_faces=9000, materials=[m["tire"]])
    if tread == "whitewall":
        ww = S.Revolved(lambda rad, ax: S.box2d(rad - rc * 1.02, ax - b * 0.93, a * 0.42, 0.012, 0.006))
        ob2 = C.sdf_object(name + "_ww", ww, (-r, -r, 0), (r, r, b + 0.05), voxel=0.003, target_faces=3000,
                           materials=[m["decal"]])
        ob = C.join([ob, ob2], name)
    return ob


def _rim(name, r, w, style, m):
    r_rim = r * 0.60
    b = w * 0.5
    # barrel sits inside the tire, face on +Z (outer side)
    barrel = S.Revolved(lambda rad, ax: S.box2d(rad - r_rim * 0.93, ax, r_rim * 0.09, b * 0.88, 0.01))
    lip = S.Revolved(lambda rad, ax: S.box2d(rad - r_rim, ax - b * 0.80, 0.018, 0.012, 0.008))
    face_z = b * 0.55
    hub = S.Revolved(lambda rad, ax: S.box2d(rad, ax - face_z, r_rim * 0.26, 0.03, 0.012))
    parts = [barrel, lip, hub]
    if style == "spokes5":
        spoke = S.Box((r_rim * 0.40, 0.022, 0.018), round=0.012).at(r_rim * 0.52, 0, face_z)
        parts.append(S.PolarRepeat(spoke, 5, phase=90))
    elif style == "dish":
        disc = S.Revolved(lambda rad, ax: S.box2d(rad, ax - face_z, r_rim * 0.9, 0.016, 0.008))
        hole = S.Cylinder(r_rim * 0.13, 0.1).at(r_rim * 0.58, 0, face_z)
        parts.append(S.Subtract(disc, S.PolarRepeat(hole, 8), k=0.006))
    elif style == "beadlock":
        disc = S.Revolved(lambda rad, ax: S.box2d(rad, ax - face_z, r_rim * 0.9, 0.018, 0.008))
        slot = S.Box((r_rim * 0.22, r_rim * 0.1, 0.1), round=0.02).at(r_rim * 0.55, 0, face_z)
        parts.append(S.Subtract(disc, S.PolarRepeat(slot, 6), k=0.006))
        ring = S.Revolved(lambda rad, ax: S.box2d(rad - r_rim * 0.95, ax - b * 0.85, 0.03, 0.018, 0.008))
        parts.append(ring)
    elif style == "star":
        arm = S.Capsule((r_rim * 0.2, 0, face_z), (r_rim * 0.88, 0, face_z), 0.02)
        parts.append(S.PolarRepeat(arm, 6))
    rim = S.Union(*parts, k=0.008)
    ob = C.sdf_object(name, rim, (-r_rim - 0.03,) * 2 + (-b - 0.03,), (r_rim + 0.03,) * 2 + (b + 0.05,),
                      voxel=0.003, target_faces=9000, materials=[m["rim"]])
    # chrome hub cap + lug nuts
    cap = S.Union(
        S.Revolved(lambda rad, ax: S.superellipse2d(rad, ax - face_z - 0.03, r_rim * 0.17, 0.035, n=2.4)),
        S.PolarRepeat(S.Cylinder(0.011, 0.012, round=0.004).at(r_rim * 0.24, 0, face_z + 0.03), 5, phase=54),
        k=0.003)
    ob2 = C.sdf_object(name + "_cap", cap, (-r_rim * 0.4,) * 2 + (face_z - 0.02,), (r_rim * 0.4,) * 2 + (face_z + 0.08,),
                       voxel=0.002, target_faces=2500, materials=[m["chrome"]])
    return C.join([ob, ob2], name)


def build_wheels(out, m, wid):
    spec = WHEELS[wid]
    objs = []
    for pos, r, w in (("front", spec["fr"], spec["fw"]), ("rear", spec["rr"], spec["rw"])):
        t = _tire(f"{pos}_tire", r, w, spec["tread"], m)
        rim = _rim(f"{pos}_rim", r, w, spec["rim"], m)
        wheel = C.join([t, rim], f"wheel_{pos}")
        # axle Z -> X, rim face (+Z) -> +X
        from mathutils import Matrix
        wheel.data.transform(Matrix.Rotation(math.radians(90), 4, "Y"))
        wheel["radius"] = r
        wheel["width"] = w
        wheel.location = (0, 0, 0)
        objs.append(wheel)
    # side by side for review, reset before export
    return objs


# ---------------------------------------------------------------------------
# Chassis: frame, floor, seat, steering, sockets
# ---------------------------------------------------------------------------

def build_chassis(m):
    objs = []
    tube_r = 0.021
    rails = []
    for sx in (-1, 1):
        rails.append(C.tube(f"rail{sx}", [
            (sx * 0.20, 0.98, 0.10), (sx * 0.24, 0.62, 0.10), (sx * 0.30, 0.30, 0.10),
            (sx * 0.30, -0.35, 0.10), (sx * 0.26, -0.78, 0.13)], radius=tube_r, corner=0.12, mat=m["metal"]))
        # side nerf bar
        rails.append(C.tube(f"nerf{sx}", [
            (sx * 0.30, 0.38, 0.10), (sx * 0.48, 0.30, 0.13), (sx * 0.50, -0.25, 0.13), (sx * 0.30, -0.33, 0.10)],
            radius=tube_r * 0.85, corner=0.08, mat=m["metal"]))
        # seat hoop support
        rails.append(C.tube(f"hoop{sx}", [
            (sx * 0.30, -0.30, 0.10), (sx * 0.24, -0.34, 0.50), (sx * 0.08, -0.36, 0.62)],
            radius=tube_r * 0.8, corner=0.1, mat=m["metal"]))
        # knuckle arms
        rails.append(C.tube(f"knuckle{sx}", [(sx * 0.22, FRONT_Y, 0.12), (sx * (FRONT_X - 0.1), FRONT_Y, REF_FRONT_R)],
                            radius=tube_r * 0.9, mat=m["metal"]))
        # rear bumper bars
        rails.append(C.tube(f"rbump{sx}", [(sx * 0.26, -0.78, 0.13), (sx * 0.60, -0.86, 0.16), (sx * 0.78, -0.80, 0.18)],
                            radius=tube_r, corner=0.08, mat=m["metal"]))
    rails.append(C.tube("front_cross", [(-0.22, 0.62, 0.10), (0.22, 0.62, 0.10)], radius=tube_r, mat=m["metal"]))
    rails.append(C.tube("mid_cross", [(-0.30, -0.10, 0.10), (0.30, -0.10, 0.10)], radius=tube_r, mat=m["metal"]))
    rails.append(C.tube("rear_bump", [(-0.60, -0.86, 0.16), (0.60, -0.86, 0.16)], radius=tube_r, mat=m["metal"]))
    rails.append(C.tube("front_axle", [(-(FRONT_X - 0.1), FRONT_Y, REF_FRONT_R - 0.04), (FRONT_X - 0.1, FRONT_Y, REF_FRONT_R - 0.04)],
                        radius=0.016, mat=m["metal"]))
    rails.append(C.tube("rear_axle", [(-REAR_X + 0.08, REAR_Y, REF_REAR_R), (REAR_X - 0.08, REAR_Y, REF_REAR_R)],
                        radius=0.028, mat=m["chrome"]))
    # bearing blocks / hubs on the rear axle
    for sx in (-1, 1):
        rails.append(C.cylinder(f"bearing{sx}", r=0.045, depth=0.06, loc=(sx * 0.34, REAR_Y, REF_REAR_R), rot=(0, 90, 0),
                                mat=m["plastic"], bevel=0.01))
    # steering column
    rails.append(C.tube("column", [(0, 0.66, 0.14), (0, 0.50, 0.30), (0, 0.33, 0.47)], radius=0.018, corner=0.05,
                        mat=m["chrome"]))
    frame = C.join(rails, "Frame")
    objs.append(frame)

    # floor pan
    floor = S.Box((0.27, 0.62, 0.012), round=0.010).at(0, 0.30, 0.075)
    floor_ob = C.sdf_object("FloorPan", floor, (-0.4, -0.5, 0.0), (0.4, 1.0, 0.15), voxel=0.006, target_faces=2500,
                            materials=[m["plastic"]])
    objs.append(floor_ob)
    # pedals
    for sx, col in ((-0.08, "plastic"), (0.08, "chrome")):
        objs.append(C.box(f"pedal{sx}", size=(0.05, 0.02, 0.09), loc=(sx, 0.86, 0.13), rot=(-30, 0, 0), mat=m[col], bevel=0.008))

    # bucket seat
    outer = S.Box((0.22, 0.20, 0.30), round=0.11).at(0, -0.18, 0.40)
    inner = S.Box((0.17, 0.22, 0.30), round=0.09).at(0, -0.06, 0.48)
    seat = S.Subtract(outer, inner, k=0.04)
    seat = S.Intersect(seat, S.Plane((0, 0, -1), -0.11))
    bolster = S.Capsule((-0.2, -0.05, 0.22), (0.2, -0.05, 0.22), 0.05)
    seat = S.Union(seat, S.Intersect(bolster, S.Box((0.3, 0.3, 0.3)).at(0, -0.2, 0.3)), k=0.03)
    headrest = S.Ellipsoid((0.13, 0.05, 0.09)).at(0, -0.32, 0.70)
    seat = S.Union(seat, headrest, k=0.05)
    # tilt seat back a little
    seat = seat.rot(-8, 0, 0).at(0, 0.0, 0.03)
    seat_ob = C.sdf_object("Seat", seat, (-0.3, -0.5, 0.05), (0.3, 0.2, 0.85), voxel=0.006, target_faces=9000,
                           materials=[m["seat"]])
    objs.append(seat_ob)

    # steering wheel (separate object, origin at its centre, normal along column)
    col_dir = np.array([0, 0.33 - 0.50, 0.47 - 0.30])
    col_dir /= np.linalg.norm(col_dir)
    wheel_c = np.array([0, 0.30, 0.50])
    rimT = S.Torus(0.13, 0.018)
    spokes = S.Union(S.Capsule((0, 0, -0.01), (0.12, 0, 0.0), 0.014), S.Capsule((0, 0, -0.01), (-0.12, 0, 0.0), 0.014),
                     S.Capsule((0, 0, -0.01), (0, -0.12, 0.0), 0.014))
    grips = S.Union(S.Capsule((0.13, -0.03, 0), (0.13, 0.05, 0), 0.026), S.Capsule((-0.13, -0.03, 0), (-0.13, 0.05, 0), 0.026))
    sw = S.Union(rimT, spokes, grips, k=0.01)
    sw_ob = C.sdf_object("SteeringWheel", sw, (-0.2, -0.2, -0.06), (0.2, 0.2, 0.06), voxel=0.003, target_faces=5000,
                         materials=[m["plastic"]])
    hub = S.Cylinder(0.045, 0.022, round=0.012).at(0, 0, -0.02)
    hub_ob = C.sdf_object("SteeringHub", hub, (-0.08, -0.08, -0.06), (0.08, 0.08, 0.03), voxel=0.002, target_faces=1500,
                          materials=[m["alt"]])
    sw_ob = C.join([sw_ob, hub_ob], "SteeringWheel")
    # orient: local +Z (wheel normal) toward the driver = -column direction
    from mathutils import Matrix, Vector
    R = S.look_rotation(-col_dir, up=(0, 1, 0))
    M = Matrix(((R[0][0], R[0][1], R[0][2], 0), (R[1][0], R[1][1], R[1][2], 0), (R[2][0], R[2][1], R[2][2], 0), (0, 0, 0, 1)))
    sw_ob.data.transform(M)
    sw_ob.location = Vector(wheel_c)
    sw_ob["axis"] = list(-col_dir)
    objs.append(sw_ob)

    # sockets
    sockets = [
        C.empty("socket_wheel_fl", (-FRONT_X, FRONT_Y, REF_FRONT_R)),
        C.empty("socket_wheel_fr", (FRONT_X, FRONT_Y, REF_FRONT_R)),
        C.empty("socket_wheel_rl", (-REAR_X, REAR_Y, REF_REAR_R)),
        C.empty("socket_wheel_rr", (REAR_X, REAR_Y, REF_REAR_R)),
        C.empty("socket_driver", (0, -0.14, 0.20)),
        C.empty("socket_hand_l", (-0.13, 0.30, 0.50)),
        C.empty("socket_hand_r", (0.13, 0.30, 0.50)),
        C.empty("socket_camera", (0, -0.6, 0.9)),
    ]
    return objs, sockets


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------

def _flat_bottom(node, z=0.06):
    return S.Intersect(node, S.Plane((0, 0, -1), -z))


def body_classic(m):
    objs = []
    nose = S.Union(
        S.Box((0.44, 0.13, 0.10), round=0.09).at(0, 0.98, 0.16),
        S.RoundCone((0, 0.95, 0.20), (0, 0.42, 0.37), 0.12, 0.085),
        S.Ellipsoid((0.30, 0.26, 0.11)).at(0, 0.72, 0.21),
        k=0.13)
    nose = _flat_bottom(nose, 0.075)
    objs.append(C.sdf_object("Nose", nose, (-0.6, 0.2, 0.0), (0.6, 1.25, 0.6), voxel=0.006, target_faces=14000,
                             materials=[m["paint"]]))
    pod = S.Union(
        S.Box((0.085, 0.38, 0.095), round=0.075).at(0.43, 0.02, 0.20),
        S.Box((0.06, 0.2, 0.05), round=0.045).at(0.43, 0.30, 0.25),
        k=0.08).mirror_x()
    objs.append(C.sdf_object("SidePods", _flat_bottom(pod, 0.09), (-0.6, -0.5, 0.0), (0.6, 0.6, 0.4), voxel=0.006,
                             target_faces=9000, materials=[m["paint"]]))
    skirt = S.Box((0.40, 0.05, 0.03), round=0.025).at(0, 1.07, 0.075)
    objs.append(C.sdf_object("Splitter", skirt, (-0.5, 0.9, 0.0), (0.5, 1.2, 0.15), voxel=0.005, target_faces=1500,
                             materials=[m["plastic"]]))
    plate = S.Box((0.12, 0.012, 0.075), round=0.01).rot(-35, 0, 0).at(0, 1.075, 0.225)
    objs.append(C.sdf_object("NumberPlate", plate, (-0.2, 0.95, 0.1), (0.2, 1.2, 0.35), voxel=0.003, target_faces=1200,
                             materials=[m["decal"]]))
    return objs


def body_bolt(m):
    """Low wedge with a front wing, F1-ish."""
    objs = []
    nose = S.Union(
        S.RoundCone((0, 1.10, 0.13), (0, 0.40, 0.33), 0.06, 0.12),
        S.Ellipsoid((0.20, 0.34, 0.10)).at(0, 0.55, 0.22),
        k=0.10)
    nose = _flat_bottom(nose, 0.08)
    objs.append(C.sdf_object("Nose", nose, (-0.5, 0.2, 0.0), (0.5, 1.3, 0.6), voxel=0.006, target_faces=12000,
                             materials=[m["paint"]]))
    wing = S.Union(
        S.Box((0.50, 0.09, 0.018), round=0.016).rot(-6, 0, 0).at(0, 1.08, 0.10),
        S.Box((0.015, 0.12, 0.07), round=0.012).at(0.50, 1.07, 0.13).mirror_x(),
        k=0.02)
    objs.append(C.sdf_object("FrontWing", wing, (-0.6, 0.9, 0.0), (0.6, 1.25, 0.25), voxel=0.004, target_faces=5000,
                             materials=[m["alt"]]))
    pod = S.Union(
        S.RoundCone((0.40, 0.35, 0.17), (0.44, -0.30, 0.24), 0.06, 0.10),
        S.Box((0.02, 0.25, 0.08), round=0.015).at(0.52, -0.2, 0.25),
        k=0.05).mirror_x()
    objs.append(C.sdf_object("SidePods", _flat_bottom(pod, 0.09), (-0.7, -0.5, 0.0), (0.7, 0.6, 0.45), voxel=0.006,
                             target_faces=9000, materials=[m["paint"]]))
    plate = S.Box((0.08, 0.01, 0.05), round=0.008).rot(-60, 0, 0).at(0, 0.9, 0.23)
    objs.append(C.sdf_object("NumberPlate", plate, (-0.2, 0.8, 0.1), (0.2, 1.0, 0.35), voxel=0.003, target_faces=1000,
                             materials=[m["decal"]]))
    return objs


def body_buggy(m):
    """Chunky off-road shell with a big bumper and lamps."""
    objs = []
    shell = S.Union(
        S.Box((0.40, 0.30, 0.13), round=0.12).at(0, 0.80, 0.22),
        S.RoundCone((0, 0.80, 0.26), (0, 0.40, 0.40), 0.16, 0.10),
        k=0.12)
    shell = _flat_bottom(shell, 0.10)
    grill = S.Box((0.25, 0.1, 0.06), round=0.03).at(0, 1.10, 0.22)
    shell = S.Subtract(shell, grill, k=0.02)
    objs.append(C.sdf_object("Nose", shell, (-0.6, 0.2, 0.0), (0.6, 1.25, 0.7), voxel=0.006, target_faces=14000,
                             materials=[m["paint"]]))
    bumper = S.Union(
        S.Capsule((-0.42, 1.12, 0.13), (0.42, 1.12, 0.13), 0.045),
        S.Capsule((-0.2, 1.12, 0.13), (-0.2, 1.0, 0.3), 0.03),
        S.Capsule((0.2, 1.12, 0.13), (0.2, 1.0, 0.3), 0.03),
        k=0.03)
    objs.append(C.sdf_object("Bumper", bumper, (-0.6, 0.9, 0.0), (0.6, 1.25, 0.4), voxel=0.004, target_faces=5000,
                             materials=[m["plastic"]]))
    lamps = S.Union(S.Cylinder(0.05, 0.02, round=0.012).rot(-90, 0, 0).at(0.26, 1.07, 0.30),
                    S.Cylinder(0.05, 0.02, round=0.012).rot(-90, 0, 0).at(-0.26, 1.07, 0.30))
    objs.append(C.sdf_object("Lamps", lamps, (-0.4, 1.0, 0.2), (0.4, 1.15, 0.4), voxel=0.003, target_faces=2000,
                             materials=[m["light"]]))
    pod = S.Union(
        S.Box((0.10, 0.36, 0.11), round=0.10).at(0.44, 0.02, 0.22),
        S.Capsule((0.52, 0.35, 0.16), (0.52, -0.3, 0.16), 0.03),
        k=0.03).mirror_x()
    objs.append(C.sdf_object("SidePods", _flat_bottom(pod, 0.1), (-0.7, -0.5, 0.0), (0.7, 0.6, 0.45), voxel=0.006,
                             target_faces=9000, materials=[m["paint"]]))
    return objs


BODIES = {"classic": body_classic, "bolt": body_bolt, "buggy": body_buggy}


# ---------------------------------------------------------------------------
# Wings (rear spoilers)
# ---------------------------------------------------------------------------

def wing_classic(m):
    blade = S.Union(
        S.Box((0.56, 0.15, 0.032), round=0.03).rot(-12, 0, 0).at(0, -0.86, 0.86),
        S.Box((0.02, 0.18, 0.10), round=0.018).at(0.56, -0.86, 0.84).mirror_x(),
        k=0.02)
    struts = S.Union(S.Capsule((0.22, -0.72, 0.22), (0.26, -0.86, 0.84), 0.022).mirror_x())
    return [
        C.sdf_object("Wing", blade, (-0.7, -1.1, 0.6), (0.7, -0.6, 1.05), voxel=0.004, target_faces=6000,
                     materials=[m["paint"]]),
        C.sdf_object("WingStruts", struts, (-0.4, -1.0, 0.1), (0.4, -0.6, 0.9), voxel=0.004, target_faces=2500,
                     materials=[m["metal"]]),
    ]


def wing_twin(m):
    fins = S.Union(
        S.Box((0.46, 0.12, 0.025), round=0.022).rot(-10, 0, 0).at(0, -0.88, 0.78),
        S.Box((0.40, 0.10, 0.022), round=0.02).rot(-18, 0, 0).at(0, -0.80, 0.92),
        S.Box((0.018, 0.16, 0.12), round=0.016).at(0.46, -0.85, 0.84).mirror_x(),
        k=0.015)
    struts = S.Capsule((0, -0.70, 0.30), (0, -0.86, 0.80), 0.03)
    return [
        C.sdf_object("Wing", fins, (-0.6, -1.1, 0.6), (0.6, -0.6, 1.05), voxel=0.004, target_faces=7000,
                     materials=[m["alt"]]),
        C.sdf_object("WingStruts", struts, (-0.2, -1.0, 0.2), (0.2, -0.6, 0.9), voxel=0.004, target_faces=1500,
                     materials=[m["metal"]]),
    ]


def wing_duck(m):
    tail = S.Union(
        S.Box((0.42, 0.10, 0.05), round=0.045).rot(15, 0, 0).at(0, -0.90, 0.36),
        S.Box((0.36, 0.14, 0.03), round=0.03).at(0, -0.80, 0.28),
        k=0.05)
    return [C.sdf_object("Wing", tail, (-0.6, -1.1, 0.1), (0.6, -0.6, 0.6), voxel=0.004, target_faces=5000,
                         materials=[m["paint"]])]


WINGS = {"classic": wing_classic, "twin": wing_twin, "duck": wing_duck}


# ---------------------------------------------------------------------------
# Engines (+ exhaust sockets for boost flames)
# ---------------------------------------------------------------------------

def engine_single(m):
    ex = 0.30
    block = S.Union(
        S.Box((0.10, 0.10, 0.10), round=0.03).at(ex, -0.45, 0.30),
        S.Cylinder(0.075, 0.07, round=0.02).at(ex, -0.45, 0.43),
        k=0.02)
    fins = S.Union(*[S.Cylinder(0.095, 0.006, round=0.004).at(ex, -0.45, 0.39 + i * 0.022) for i in range(4)])
    eng = S.Union(block, fins, k=0.005)
    filt = S.Cylinder(0.06, 0.05, round=0.02).rot(0, 90, 0).at(ex - 0.16, -0.40, 0.36)
    objs = [
        C.sdf_object("Engine", eng, (0.1, -0.65, 0.15), (0.5, -0.25, 0.55), voxel=0.004, target_faces=8000,
                     materials=[m["metal"]]),
        C.sdf_object("AirFilter", filt, (-0.0, -0.55, 0.25), (0.25, -0.25, 0.45), voxel=0.003, target_faces=2500,
                     materials=[m["alt"]]),
    ]
    pipe = C.tube("Exhaust", [(ex, -0.38, 0.30), (ex + 0.10, -0.50, 0.24), (ex + 0.12, -0.80, 0.28), (ex + 0.12, -0.98, 0.34)],
                  radius=0.028, corner=0.08, mat=m["chrome"])
    tip = C.cylinder("ExhaustTip", r=0.04, depth=0.09, loc=(ex + 0.12, -1.0, 0.345), rot=(90 - 12, 0, 0), mat=m["chrome"])
    objs += [pipe, tip]
    sockets = [C.empty("socket_exhaust_0", (ex + 0.12, -1.05, 0.355), rot=(90 - 12, 0, 0))]
    return objs, sockets


def engine_twin(m):
    objs = []
    block = S.Union(
        S.Box((0.20, 0.12, 0.10), round=0.035).at(0, -0.62, 0.34),
        S.Cylinder(0.06, 0.06, round=0.02).rot(0, 30, 0).at(0.12, -0.62, 0.46),
        S.Cylinder(0.06, 0.06, round=0.02).rot(0, -30, 0).at(-0.12, -0.62, 0.46),
        k=0.03)
    objs.append(C.sdf_object("Engine", block, (-0.4, -0.85, 0.15), (0.4, -0.4, 0.65), voxel=0.004, target_faces=9000,
                             materials=[m["metal"]]))
    scoop = S.Box((0.08, 0.08, 0.04), round=0.03).at(0, -0.60, 0.48)
    objs.append(C.sdf_object("Scoop", scoop, (-0.2, -0.75, 0.4), (0.2, -0.45, 0.6), voxel=0.003, target_faces=1500,
                             materials=[m["alt"]]))
    sockets = []
    for i, sx in enumerate((-1, 1)):
        pipe = C.tube(f"Exhaust{i}", [(sx * 0.14, -0.70, 0.36), (sx * 0.20, -0.82, 0.40), (sx * 0.20, -1.0, 0.44)],
                      radius=0.026, corner=0.06, mat=m["chrome"])
        tip = C.cylinder(f"ExhaustTip{i}", r=0.036, depth=0.07, loc=(sx * 0.20, -1.01, 0.445), rot=(90 - 8, 0, 0),
                         mat=m["chrome"])
        objs += [pipe, tip]
        sockets.append(C.empty(f"socket_exhaust_{i}", (sx * 0.20, -1.06, 0.45), rot=(90 - 8, 0, 0)))
    return objs, sockets


ENGINES = {"single": engine_single, "twin": engine_twin}


# ---------------------------------------------------------------------------
# Build entry points
# ---------------------------------------------------------------------------

def _export(objs, path):
    C.export_glb(path, objs)


def build(out_root, preview=None, only=None):
    from tt import render as R

    kdir = os.path.join(out_root, "karts")
    todo = only or ["chassis", "bodies", "wings", "engines", "wheels"]

    if "chassis" in todo:
        C.reset(); m = mats()
        objs, sockets = build_chassis(m)
        root = C.empty("Chassis", (0, 0, 0))
        for o in objs + sockets:
            o.parent = root
        _export([root], os.path.join(kdir, "chassis", "standard.glb"))
    for cat, table in (("bodies", BODIES), ("wings", WINGS)):
        if cat not in todo:
            continue
        for pid, fn in table.items():
            C.reset(); m = mats()
            objs = fn(m)
            root = C.empty(pid, (0, 0, 0))
            for o in objs:
                o.parent = root
            _export([root], os.path.join(kdir, cat, pid + ".glb"))
    if "engines" in todo:
        for pid, fn in ENGINES.items():
            C.reset(); m = mats()
            objs, sockets = fn(m)
            root = C.empty(pid, (0, 0, 0))
            for o in objs + sockets:
                o.parent = root
            _export([root], os.path.join(kdir, "engines", pid + ".glb"))
    if "wheels" in todo:
        for wid in WHEELS:
            C.reset(); m = mats()
            objs = build_wheels(kdir, m, wid)
            root = C.empty(wid, (0, 0, 0))
            for o in objs:
                o.parent = root
            _export([root], os.path.join(kdir, "wheels", wid + ".glb"))

    if preview:
        review(out_root, preview)


def assemble(body="classic", wing="classic", engine="single", wheels="standard"):
    """Full kart in one scene, for review renders."""
    from mathutils import Matrix
    m = mats()
    objs, sockets = build_chassis(m)
    objs += BODIES[body](m)
    objs += WINGS[wing](m)
    e, _s = ENGINES[engine](m)
    objs += e
    ws = build_wheels(None, m, wheels)
    spec = WHEELS[wheels]
    lift = spec["rr"] - REF_REAR_R
    for o in objs:
        o.location.z += lift
    for pos, sx, x, y, r in (("front", 1, FRONT_X, FRONT_Y, spec["fr"]), ("rear", 1, REAR_X, REAR_Y, spec["rr"])):
        w = [o for o in ws if o.name == f"wheel_{pos}"][0]
        w2 = w.copy(); w2.data = w.data.copy(); C.link(w2)
        w.location = (x, y, r)
        w2.location = (-x, y, r)
        w2.rotation_euler = (0, 0, math.pi)
        objs += [w, w2]
    return objs


def review(out_root, prefix, **kw):
    from tt import render as R
    C.reset()
    assemble(**kw)
    return R.turntable(prefix, target=(0, 0.1, 0.35), dist=3.6, views=((-40, 22), (40, 22), (160, 18), (90, 60)),
                       size=(560, 420), samples=24, radius=3.0)
