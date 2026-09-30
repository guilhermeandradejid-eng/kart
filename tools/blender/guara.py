"""Guará — the maned-wolf driver, Turbo Turma's first racer.

Design notes (appeal first):
  * Big head (~40 % of height), huge cupped ears, long black-tipped snout,
    amber eyes with two catch-lights, black "stockings" on the legs and the
    black mane crest of the real lobo-guará, bushy tail with a white tip.
  * Racing outfit: teal vest with a white stripe and number patch, gloves,
    red sneakers, aviator goggles on the forehead and a long green-yellow
    scarf whose tails carry the follow-through.
  * Everything is SDF-modelled (smooth unions = sculpted look), skinned with
    Blender's bone-heat weights, and animated in anim.py/guara_anim.py.

Model is built standing in an A-pose, facing +Y, feet on z = 0.
"""

import math
import os

import numpy as np

from tt import core as C
from tt import sdf as S

# ---- palette ---------------------------------------------------------------
FUR = "#d9602a"        # red-orange coat
FUR_LIGHT = "#f0a35e"  # cheeks / belly blend
CREAM = "#f6e2c0"
EAR_IN = "#f0c3a0"
SHORTS = "#24305e"      # throat, inner ears, muzzle sides
BLACK = "#2a2322"      # muzzle, legs, mane
TAIL_TIP = "#f7f2e8"
VEST = "#1aa6b7"
VEST_STRIPE = "#f5f5ef"
GLOVE = "#f2f2ec"
GLOVE_CUFF = "#e0342c"
SHOE = "#e0342c"
SOLE = "#f5f1e6"
SCARF = "#ffcc1f"
SCARF_STRIPE = "#1f9e4a"

# ---- anatomy (A-pose) ------------------------------------------------------
HEAD_C = np.array([0.0, 0.0, 0.905])
EYE_L = np.array([-0.067, 0.113, 0.932])
EYE_R = EYE_L * np.array([-1, 1, 1])
EYE_R_RAD = 0.05
SHOULDER = np.array([0.135, -0.005, 0.665])
ELBOW = np.array([0.245, 0.0, 0.545])
WRIST = np.array([0.315, 0.025, 0.435])
HAND_TIP = np.array([0.36, 0.04, 0.35])
HIP = np.array([0.085, -0.005, 0.385])
KNEE = np.array([0.095, 0.012, 0.215])
ANKLE = np.array([0.10, 0.0, 0.085])
TOE = np.array([0.105, 0.12, 0.035])
TAIL = [np.array(p) for p in [(0, -0.115, 0.405), (0, -0.23, 0.37), (0, -0.345, 0.41), (0, -0.425, 0.52), (0, -0.46, 0.65)]]
TAIL_R = [0.035, 0.062, 0.074, 0.066, 0.028]
EAR_BASE = np.array([0.078, -0.025, 1.005])
EAR_TIP = np.array([0.175, -0.06, 1.285])
JAW_PIVOT = np.array([0.0, 0.07, 0.838])


def mats():
    return dict(
        fur=C.material("Fur", "#ffffff", rough=0.75, use_vcol=True),
        cloth=C.material("Cloth", "#ffffff", rough=0.8, use_vcol=True),
        scarf=C.material("Scarf", "#ffffff", rough=0.85, use_vcol=True),
        nose=C.material("Nose", "#1b1717", rough=0.18),
        eye=C.material("EyeWhite", "#fbfaf6", rough=0.12),
        iris=C.material("Iris", "#e89a2c", rough=0.2),
        pupil=C.material("Pupil", "#120c0a", rough=0.1),
        glint=C.material("Glint", "#ffffff", rough=0.1, emit="#ffffff", emit_strength=3.0),
        mouth=C.material("Mouth", "#5a1d22", rough=0.6),
        tongue=C.material("Tongue", "#e8707a", rough=0.45),
        teeth=C.material("Teeth", "#fbf7ee", rough=0.3),
        lens=C.material("Lens", "#6fd6ff", rough=0.05, metal=0.3),
        brass=C.material("Brass", "#c8913a", rough=0.3, metal=0.9),
        strap=C.material("Strap", "#6b3d24", rough=0.7),
    )


def _v(a):
    return tuple(float(x) for x in a)


# ---------------------------------------------------------------------------
# Body (single skinned mesh, vertex coloured)
# ---------------------------------------------------------------------------

def head_node():
    cranium = S.Ellipsoid((0.165, 0.152, 0.155), color=FUR).at(*HEAD_C)
    brow = S.Ellipsoid((0.13, 0.07, 0.05), color=FUR).at(0, 0.075, 0.975)
    cheeks = S.Ellipsoid((0.075, 0.065, 0.058), color=FUR_LIGHT).at(0.098, 0.052, 0.842).mirror_x()
    # cheek fur tufts: small cones sweeping out and down
    tufts = S.Union(
        S.RoundCone((0.14, 0.02, 0.85), (0.205, -0.005, 0.80), 0.035, 0.008, color=FUR_LIGHT),
        S.RoundCone((0.13, 0.00, 0.80), (0.18, -0.02, 0.755), 0.03, 0.007, color=CREAM),
        k=0.02).mirror_x()
    snout = S.RoundCone((0, 0.075, 0.878), (0, 0.255, 0.853), 0.078, 0.043, color=FUR)
    bridge = S.Capsule((0, 0.06, 0.93), (0, 0.23, 0.875), 0.03, color=FUR)
    head = S.Union(cranium, brow, cheeks, tufts, snout, bridge, k=0.05)
    # black muzzle tip, cream muzzle sides / chin
    head = S.ColorRegion(head, S.Sphere(0.105).at(0, 0.29, 0.86), BLACK, soft=0.02)
    head = S.ColorRegion(head, S.Ellipsoid((0.10, 0.12, 0.05)).at(0, 0.12, 0.80), CREAM, soft=0.025)
    # mouth line: a shallow groove under the snout
    mouth = S.Capsule((-0.045, 0.2, 0.832), (0.045, 0.2, 0.832), 0.008).rot(0, 0, 0)
    head = S.Subtract(head, S.Union(mouth, S.Capsule((0, 0.215, 0.832), (0, 0.25, 0.836), 0.006)), k=0.006)
    # eye sockets so the eyeballs sit snugly
    head = S.Subtract(head, S.Sphere(EYE_R_RAD + 0.004).at(*EYE_R).mirror_x(), k=0.02)
    return head


def ear_node():
    # built at the origin pointing up, flattened, cupped, then placed
    L = np.linalg.norm(EAR_TIP - EAR_BASE)
    outer = S.RoundCone((0, 0, 0), (0, 0, L), 0.074, 0.013, color=FUR).stretch(1.0, 0.42, 1.0)
    cup = S.RoundCone((0, 0.022, 0.03), (0, 0.022, L * 0.9), 0.05, 0.006).stretch(1.0, 0.38, 1.0)
    ear = S.Subtract(outer, cup.paint(EAR_IN), k=0.012, carve=True)
    ear = S.ColorRegion(ear, S.Sphere(0.065).at(0, 0, L), BLACK, soft=0.035)  # dark tips
    d = (EAR_TIP - EAR_BASE) / L
    tilt_x = math.degrees(math.atan2(-d[1], d[2]))   # lean back
    tilt_y = math.degrees(math.atan2(d[0], d[2]))    # splay out
    return ear.rot(tilt_x, tilt_y, -12).at(*EAR_BASE).mirror_x()


def mane_node():
    return S.Union(
        S.RoundCone((0, -0.12, 0.96), (0, -0.19, 1.0), 0.05, 0.018, color=BLACK),
        S.RoundCone((0, -0.13, 0.88), (0, -0.215, 0.895), 0.052, 0.018, color=BLACK),
        S.RoundCone((0, -0.115, 0.80), (0, -0.20, 0.78), 0.048, 0.016, color=BLACK),
        k=0.045)


def torso_node():
    chest = S.Ellipsoid((0.148, 0.118, 0.12), color=FUR).at(0, 0.0, 0.628)
    belly = S.Ellipsoid((0.158, 0.138, 0.15), color=CREAM).at(0, 0.012, 0.50)
    hips = S.Ellipsoid((0.15, 0.12, 0.09), color=FUR).at(0, -0.01, 0.415)
    neck = S.Capsule((0, 0, 0.69), (0, 0.01, 0.80), 0.07, color=FUR)
    return S.Union(chest, belly, hips, neck, k=0.06, color_k=0.1)


def arm_node():
    upper = S.RoundCone(_v(SHOULDER), _v(ELBOW), 0.05, 0.04, color=FUR)
    fore = S.RoundCone(_v(ELBOW), _v(WRIST), 0.04, 0.037, color=FUR)
    arm = S.Union(upper, fore, k=0.02)
    # glove cuff region on the forearm
    arm = S.ColorRegion(arm, S.Sphere(0.06).at(*(WRIST * 0.75 + ELBOW * 0.25)), GLOVE_CUFF, soft=0.01)
    return arm.mirror_x()


def hand_node():
    # local frame: +Z = along forearm (wrist -> fingertips), +X = back of hand,
    # palm faces -X (toward the body in A-pose, which is +X side mirrored)
    palm = S.Ellipsoid((0.036, 0.048, 0.05), color=GLOVE).at(0, 0, 0.045)
    fingers = S.Union(*[S.Capsule((0, y, 0.07), (-0.012, y * 1.1, 0.115), 0.019, color=GLOVE) for y in (-0.025, 0.0, 0.025)],
                      k=0.01)
    thumb = S.Capsule((-0.02, 0.035, 0.03), (-0.04, 0.06, 0.07), 0.018, color=GLOVE)
    hand = S.Union(palm, fingers, thumb, k=0.015)
    d = HAND_TIP - WRIST
    d /= np.linalg.norm(d)
    R = S.look_rotation(d, up=(0, 1, 0))
    return S.Transform(hand, offset=WRIST, rotation=R).mirror_x()


def leg_node():
    thigh = S.RoundCone(_v(HIP), _v(KNEE), 0.064, 0.05, color=FUR)
    shin = S.RoundCone(_v(KNEE), _v(ANKLE), 0.045, 0.036, color=BLACK)
    leg = S.Union(thigh, shin, k=0.025, color_k=0.02)
    leg = S.ColorRegion(leg, S.Field(lambda p: p[:, 2] - 0.30), BLACK, soft=0.01)  # stockings
    return leg.mirror_x()


def shoe_node():
    shoe = S.Union(
        S.Ellipsoid((0.052, 0.085, 0.045), color=SHOE).at(0.102, 0.045, 0.05),
        S.Ellipsoid((0.045, 0.05, 0.05), color=SHOE).at(0.10, -0.005, 0.07),
        k=0.03)
    sole = S.Box((0.056, 0.095, 0.014), round=0.013, color=SOLE).at(0.102, 0.04, 0.014)
    toecap = S.Ellipsoid((0.04, 0.03, 0.025), color=SOLE).at(0.104, 0.115, 0.03)
    return S.Union(shoe, sole, toecap, k=0.008).mirror_x()


def tail_node():
    tail = S.Tube(TAIL, TAIL_R, k=0.03, color=FUR)
    tail = S.ColorRegion(tail, S.Sphere(0.1).at(*TAIL[-1]), TAIL_TIP, soft=0.035)
    # fluffy clumps
    tail = tail.displace(lambda p: 0.006 * S.fbm(p, 22.0, 2, seed=5))
    return tail


def body_node():
    body = S.Union(head_node(), ear_node(), mane_node(), torso_node(), arm_node(), hand_node(),
                   leg_node(), shoe_node(), tail_node(), k=0.018)
    # racing shorts: pelvis + upper thighs only (not hands, not the tail)
    region = S.Box((0.19, 0.14, 0.075)).at(0, 0.015, 0.372)
    return S.ColorRegion(body, region, SHORTS, soft=0.006)


# ---------------------------------------------------------------------------
# Accessory meshes
# ---------------------------------------------------------------------------

def vest_node():
    t = torso_node().inflate(0.014)
    region = S.Box((0.3, 0.3, 0.14)).at(0, 0, 0.568)
    vest = S.Intersect(t, region)
    # open collar at the front / arm holes
    vest = S.Subtract(vest, S.Sphere(0.075).at(0, 0.12, 0.70), k=0.02)
    vest = S.Subtract(vest, S.Sphere(0.062).at(*SHOULDER).mirror_x(), k=0.01)

    def col(p):
        c = np.tile(np.asarray(S.hexrgb(VEST)), (len(p), 1))
        stripe = (np.abs(p[:, 0] - 0.055) < 0.018) & (p[:, 1] > 0)
        hem = p[:, 2] < 0.442
        c[stripe | hem] = S.hexrgb(VEST_STRIPE)
        badge = np.linalg.norm(p - np.array([-0.07, 0.12, 0.61]), axis=1) < 0.03
        c[badge] = S.hexrgb("#ffcc1f")
        return c
    return vest.paint(col)


def scarf_node():
    collar = S.Torus(0.083, 0.034).stretch(1.0, 1.0, 0.75).rot(-8, 0, 0).at(0, 0.0, 0.735)
    knot = S.Sphere(0.036).at(0, -0.095, 0.728)
    tails = []
    for sx in (-1, 1):
        pts = [(sx * 0.012, -0.10, 0.725), (sx * 0.035, -0.19, 0.705), (sx * 0.055, -0.285, 0.672), (sx * 0.07, -0.38, 0.64)]
        tube = S.Tube(pts, [0.03, 0.032, 0.03, 0.026], k=0.01)
        c = np.mean(np.array(pts), axis=0)
        tails.append(S.Transform(S.Stretch(S.Transform(tube, offset=-c), 0.35, 1.0, 1.0), offset=c))
    scarf = S.Union(collar, knot, *tails, k=0.015)

    def col(p):
        c = np.tile(np.asarray(S.hexrgb(SCARF)), (len(p), 1))
        band = (np.mod(p[:, 1] * 11.0, 1.0) < 0.32) & (p[:, 1] < -0.14)
        ring = (np.abs(p[:, 2] - 0.735) < 0.007) & (p[:, 1] > -0.09)
        c[band | ring] = S.hexrgb(SCARF_STRIPE)
        return c
    return scarf.paint(col)


def goggles_nodes():
    strap = S.Torus(0.152, 0.011).stretch(1.0, 1.02, 1.0).rot(-18, 0, 0).at(0, -0.005, 0.975)
    frames = []
    lenses = []
    for sx in (-1, 1):
        c = np.array([sx * 0.058, 0.128, 1.02])
        rimT = S.Torus(0.036, 0.011).rot(-62, 0, 0).at(*c)
        cup = S.Cylinder(0.036, 0.016, round=0.008).rot(-62, 0, 0).at(*(c - np.array([0, 0.012, -0.004])))
        frames += [rimT, cup]
        lenses.append(S.Ellipsoid((0.03, 0.03, 0.009)).rot(-62, 0, 0).at(*(c + np.array([0, 0.004, 0.004]))))
    bridge = S.Capsule((-0.025, 0.138, 1.02), (0.025, 0.138, 1.02), 0.009)
    return strap, S.Union(*frames, bridge, k=0.006), S.Union(*lenses)


def eye_nodes(center):
    c = np.asarray(center)
    ball = S.Sphere(EYE_R_RAD).at(*c)
    # iris / pupil / glints as thin caps on the front of the ball (look = +Y)
    front = np.array([0.0, 1.0, 0.0])
    iris = S.Intersect(S.Sphere(EYE_R_RAD + 0.0016).at(*c), S.Sphere(0.031).at(*(c + front * EYE_R_RAD)))
    pupil = S.Intersect(S.Sphere(EYE_R_RAD + 0.0026).at(*c), S.Sphere(0.019).at(*(c + front * EYE_R_RAD)))
    g1 = S.Sphere(0.0065).at(*(c + np.array([0.012 * np.sign(c[0]) * -1, EYE_R_RAD - 0.004, 0.014])))
    g2 = S.Sphere(0.0035).at(*(c + np.array([-0.004 * np.sign(c[0]) * -1, EYE_R_RAD - 0.001, -0.012])))
    return ball, iris, pupil, S.Union(g1, g2)


def lid_nodes(center):
    """Eyelid shells hinged at the eye centre (bones rotate them to blink)."""
    c = np.asarray(center)
    shell = S.Sphere(EYE_R_RAD + 0.0055).at(*c).shell(0.0025)
    upper = S.Intersect(shell, S.Field(lambda p: (c[2] + 0.034) - p[:, 2]))
    upper = S.Intersect(upper, S.Field(lambda p: (c[1] - 0.03) - p[:, 1]))
    lower = S.Intersect(shell, S.Field(lambda p: p[:, 2] - (c[2] - 0.037)))
    lower = S.Intersect(lower, S.Field(lambda p: (c[1] - 0.02) - p[:, 1]))
    return upper, lower


def brow_node(center):
    c = np.asarray(center) + np.array([0, 0.018, 0.062])
    sx = np.sign(center[0])
    return S.Capsule((c[0] - sx * 0.022, c[1], c[2] - 0.004), (c[0] + sx * 0.022, c[1] - 0.012, c[2] + 0.006), 0.0095)


def jaw_nodes():
    jaw = S.RoundCone((0, 0.075, 0.822), (0, 0.215, 0.822), 0.052, 0.03, color=CREAM).stretch(1.0, 1.0, 1.0)
    jaw = S.Intersect(jaw, S.Field(lambda p: p[:, 2] - 0.838))  # top flat (closes against the snout)
    jaw = S.ColorRegion(jaw, S.Sphere(0.06).at(0, 0.24, 0.82), BLACK, soft=0.02)
    tongue = S.Ellipsoid((0.03, 0.055, 0.012)).at(0, 0.16, 0.838)
    teeth = S.Union(S.RoundCone((0.03, 0.2, 0.832), (0.03, 0.2, 0.85), 0.006, 0.002),
                    S.RoundCone((-0.03, 0.2, 0.832), (-0.03, 0.2, 0.85), 0.006, 0.002))
    cavity = S.Ellipsoid((0.05, 0.09, 0.03)).at(0, 0.16, 0.845)
    return jaw, tongue, teeth, cavity


# ---------------------------------------------------------------------------
# Build meshes
# ---------------------------------------------------------------------------

LO = (-0.45, -0.6, -0.02)
HI = (0.45, 0.45, 1.36)


def build_meshes(m, quality=1.0):
    vox = 0.0055 / quality
    objs = {}
    objs["Body"] = C.sdf_object("Body", body_node(), LO, HI, voxel=vox, target_faces=int(26000 * quality),
                                materials=[m["fur"]])
    objs["Vest"] = C.sdf_object("Vest", vest_node(), (-0.3, -0.3, 0.38), (0.3, 0.3, 0.75), voxel=vox,
                                target_faces=int(7000 * quality), materials=[m["cloth"]])
    objs["Scarf"] = C.sdf_object("Scarf", scarf_node(), (-0.2, -0.5, 0.55), (0.2, 0.2, 0.85), voxel=vox * 0.8,
                                 target_faces=int(10000 * quality), materials=[m["scarf"]])
    strap, frames, lenses = goggles_nodes()
    g = [C.sdf_object("GStrap", strap, (-0.25, -0.25, 0.85), (0.25, 0.25, 1.12), voxel=0.003, target_faces=3000,
                      materials=[m["strap"]]),
         C.sdf_object("GFrame", frames, (-0.15, 0.05, 0.95), (0.15, 0.2, 1.1), voxel=0.0025, target_faces=3500,
                      materials=[m["brass"]]),
         C.sdf_object("GLens", lenses, (-0.15, 0.05, 0.95), (0.15, 0.2, 1.1), voxel=0.002, target_faces=1200,
                      materials=[m["lens"]])]
    objs["Goggles"] = C.join(g, "Goggles")
    for side, c in (("L", EYE_L), ("R", EYE_R)):
        ball, iris, pupil, glint = eye_nodes(c)
        lo = c - 0.06
        hi = c + 0.06
        parts = [C.sdf_object(f"EyeBall.{side}", ball, lo, hi, voxel=0.002, target_faces=1600, materials=[m["eye"]]),
                 C.sdf_object(f"Iris.{side}", iris, lo, hi, voxel=0.0012, target_faces=900, materials=[m["iris"]]),
                 C.sdf_object(f"Pupil.{side}", pupil, lo, hi, voxel=0.001, target_faces=600, materials=[m["pupil"]]),
                 C.sdf_object(f"Glint.{side}", glint, lo, hi, voxel=0.001, target_faces=300, materials=[m["glint"]])]
        objs[f"Eye.{side}"] = C.join(parts, f"Eye.{side}")
        up, low = lid_nodes(c)
        objs[f"LidUp.{side}"] = C.sdf_object(f"LidUp.{side}", up.paint(FUR), lo, hi, voxel=0.0015, target_faces=1500,
                                             materials=[m["fur"]])
        objs[f"LidLo.{side}"] = C.sdf_object(f"LidLo.{side}", low.paint(FUR_LIGHT), lo, hi, voxel=0.0015,
                                             target_faces=1000, materials=[m["fur"]])
        objs[f"Brow.{side}"] = C.sdf_object(f"Brow.{side}", brow_node(c).paint(BLACK), lo, hi + 0.05, voxel=0.0015,
                                            target_faces=600, materials=[m["fur"]])
    jaw, tongue, teeth, cavity = jaw_nodes()
    jparts = [C.sdf_object("JawMesh", jaw, (-0.1, 0.0, 0.75), (0.1, 0.3, 0.87), voxel=0.003, target_faces=3000,
                           materials=[m["fur"]]),
              C.sdf_object("Tongue", tongue, (-0.1, 0.05, 0.8), (0.1, 0.25, 0.87), voxel=0.002, target_faces=800,
                           materials=[m["tongue"]]),
              C.sdf_object("Teeth", teeth, (-0.1, 0.15, 0.8), (0.1, 0.25, 0.87), voxel=0.0012, target_faces=500,
                           materials=[m["teeth"]])]
    objs["Jaw"] = C.join(jparts, "Jaw")
    objs["MouthCavity"] = C.sdf_object("MouthCavity", cavity, (-0.1, 0.0, 0.78), (0.1, 0.3, 0.9), voxel=0.003,
                                       target_faces=800, materials=[m["mouth"]])
    nose = S.Ellipsoid((0.034, 0.026, 0.024)).at(0, 0.288, 0.868)
    objs["Nose"] = C.sdf_object("NoseMesh", nose, (-0.06, 0.24, 0.83), (0.06, 0.33, 0.91), voxel=0.0015,
                                target_faces=800, materials=[m["nose"]])
    return objs


def review_model(prefix):
    from tt import render as R
    C.reset()
    m = mats()
    build_meshes(m, quality=0.8)
    return R.turntable(prefix, target=(0, 0, 0.62), dist=2.6, views=((-30, 8), (0, 5), (90, 5), (200, 12)),
                       size=(480, 520), samples=20, lens=60, radius=2.0)


def build(out_root, preview=None, quality=1.0):
    import bpy
    import guara_anim as GA
    from tt import rig as RG
    C.reset()
    m = mats()
    arm, objs, ik = build_rig(m, quality)
    baker = RG.Baker(arm, ik)
    for clip in GA.all_clips():
        baker.bake(clip)
        print("baked", clip.name, clip.frames, "frames")
    # IK helpers are authoring-only
    for pb in arm.pose.bones:
        for con in list(pb.constraints):
            pb.constraints.remove(con)
    for name, (tgt, pole, con) in ik.items():
        bpy.data.objects.remove(tgt, do_unlink=True)
        if pole:
            bpy.data.objects.remove(pole, do_unlink=True)
    C.export_glb(os.path.join(out_root, "characters", "guara.glb"), [arm], animations=True)
    if preview:
        review_model(preview + "_model")


# ---------------------------------------------------------------------------
# Rig
# ---------------------------------------------------------------------------

def _mx(p, side):
    p = np.asarray(p, float).copy()
    p[0] = abs(p[0]) * (-1 if side == "L" else 1)
    return tuple(p)


FACE_BONES = ["jaw", "eye.L", "eye.R", "lid_up.L", "lid_up.R", "lid_lo.L", "lid_lo.R", "brow.L", "brow.R"]
SCARF_BONES = [f"scarf.{s}.{i}" for s in "LR" for i in range(3)]
TAIL_BONES = [f"tail.{i}" for i in range(4)]


def bone_specs():
    b = [
        ("root", (0, 0, 0), (0, 0.15, 0), None, False),
        ("hips", (0, -0.01, 0.40), (0, -0.01, 0.49), "root"),
        ("spine", (0, -0.01, 0.49), (0, 0.0, 0.60), "hips"),
        ("chest", (0, 0.0, 0.60), (0, 0.0, 0.70), "spine"),
        ("neck", (0, 0.0, 0.70), (0, 0.01, 0.80), "chest"),
        ("head", (0, 0.01, 0.80), (0, 0.01, 1.04), "neck"),
        ("jaw", tuple(JAW_PIVOT), (0, 0.22, 0.822), "head"),
    ]
    for s in "LR":
        e = _mx(EYE_L, s)
        b += [
            (f"eye.{s}", e, (e[0], e[1] + 0.08, e[2]), "head"),
            (f"lid_up.{s}", e, (e[0], e[1] + 0.06, e[2]), "head"),
            (f"lid_lo.{s}", e, (e[0], e[1] + 0.06, e[2]), "head"),
            (f"brow.{s}", (e[0], e[1] + 0.02, e[2] + 0.062), (e[0], e[1] + 0.07, e[2] + 0.062), "head"),
        ]
        base = np.array(_mx(EAR_BASE, s))
        tip = np.array(_mx(EAR_TIP, s))
        mid = base * 0.5 + tip * 0.5
        b += [(f"ear.{s}.0", tuple(base), tuple(mid), "head"), (f"ear.{s}.1", tuple(mid), tuple(tip), f"ear.{s}.0")]
        b += [
            (f"shoulder.{s}", _mx((0.04, -0.005, 0.665), s), _mx(SHOULDER, s), "chest"),
            (f"upper_arm.{s}", _mx(SHOULDER, s), _mx(ELBOW, s), f"shoulder.{s}"),
            (f"forearm.{s}", _mx(ELBOW, s), _mx(WRIST, s), f"upper_arm.{s}"),
            (f"hand.{s}", _mx(WRIST, s), _mx(HAND_TIP, s), f"forearm.{s}"),
            (f"thigh.{s}", _mx(HIP, s), _mx(KNEE, s), "hips"),
            (f"shin.{s}", _mx(KNEE, s), _mx(ANKLE, s), f"thigh.{s}"),
            (f"foot.{s}", _mx(ANKLE, s), _mx(TOE, s), f"shin.{s}"),
        ]
        sx = -1 if s == "L" else 1
        pts = [(sx * 0.012, -0.10, 0.725), (sx * 0.035, -0.19, 0.705), (sx * 0.055, -0.285, 0.672), (sx * 0.07, -0.38, 0.64)]
        for i in range(3):
            b.append((f"scarf.{s}.{i}", pts[i], pts[i + 1], "neck" if i == 0 else f"scarf.{s}.{i - 1}"))
    for i in range(4):
        b.append((f"tail.{i}", tuple(TAIL[i]), tuple(TAIL[i + 1]), "hips" if i == 0 else f"tail.{i - 1}"))
    return b


def build_rig(m, quality=1.0):
    from tt import rig as RG
    objs = build_meshes(m, quality)
    arm = RG.build_armature("GuaraRig", bone_specs())
    RG.auto_skin([objs["Body"], objs["Vest"]], arm, exclude=set(FACE_BONES + SCARF_BONES + ["root"]))
    RG.auto_skin([objs["Scarf"]], arm, exclude=set(FACE_BONES + TAIL_BONES + ["root", "head"] +
                                                    [n for n in [x[0] for x in bone_specs()] if n.startswith(("ear", "upper", "fore", "hand", "thigh", "shin", "foot"))]))
    for s in "LR":
        RG.rigid_skin(objs[f"Eye.{s}"], arm, f"eye.{s}")
        RG.rigid_skin(objs[f"LidUp.{s}"], arm, f"lid_up.{s}")
        RG.rigid_skin(objs[f"LidLo.{s}"], arm, f"lid_lo.{s}")
        RG.rigid_skin(objs[f"Brow.{s}"], arm, f"brow.{s}")
    RG.rigid_skin(objs["Jaw"], arm, "jaw")
    for k in ("MouthCavity", "Nose", "Goggles"):
        RG.rigid_skin(objs[k], arm, "head")
    for k in ("Body", "Vest", "Scarf"):
        RG.limit_influences(objs[k])
    ik = {}
    for s in "LR":
        ik[f"hand.{s}"] = RG.add_ik(arm, f"forearm.{s}", f"ik_hand.{s}", f"pole_arm.{s}", chain=2, pole_angle=-90)
        ik[f"foot.{s}"] = RG.add_ik(arm, f"shin.{s}", f"ik_foot.{s}", f"pole_leg.{s}", chain=2, pole_angle=-90)
    return arm, objs, ik


# ---------------------------------------------------------------------------
# Review: pose sheets (character seated in the kart)
# ---------------------------------------------------------------------------

def review_poses(prefix, entries, size=(360, 360), kart=True, quality=0.6, cols=4, view=(-32, 20), dist=2.0):
    import bpy
    from PIL import Image, ImageDraw
    import kart_parts as K
    import guara_anim as GA
    from tt import render as R
    from tt import rig as RG
    C.reset()
    m = mats()
    arm, objs, ik = build_rig(m, quality)
    if kart:
        K.assemble()
        arm.location = (0, -0.14, 0.20)
    clips = {c.name: c for c in GA.all_clips()}
    lights = R.studio((0, 0, 0.5), radius=3.0)
    target = (0, -0.1, 0.62) if kart else (0, 0, 0.62)
    cam = R.camera(target, dist, view[0], view[1], lens=55)
    paths = []
    for i, (name, t) in enumerate(entries):
        RG.pose_frame(arm, clips[name], t, ik)
        p = f"{prefix}_{i}.png"
        R.render(p, size, samples=10)
        im = Image.open(p)
        ImageDraw.Draw(im).text((6, 6), f"{name} @{t:.2f}", fill=(255, 255, 255))
        im.save(p)
        paths.append(p)
    sheet = R.contact_sheet(paths, prefix + "_sheet.png", cols=cols)
    import os
    for p in paths:
        os.remove(p)
    return sheet
