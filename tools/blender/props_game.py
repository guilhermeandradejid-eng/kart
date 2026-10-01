"""Gameplay props: item box, boost pad, ramp, seashell, banana peel,
coconut bomb, chili pepper, crowd member. Kept very clean and readable."""

import colorsys
import math

import numpy as np
from mathutils import Matrix

import props_lib as L
import tt.core as C
from props import prop
from tt import sdf as S


def _recenter(ob, target=(0, 0, 0), axes=(0, 1, 2)):
    V = C.vertex_array(ob)
    c = (V.min(axis=0) + V.max(axis=0)) / 2
    off = np.zeros(3)
    for a in axes:
        off[a] = target[a] - c[a]
    ob.data.transform(Matrix.Translation(off))
    return ob


# ---------------------------------------------------------------------------
# Item box
# ---------------------------------------------------------------------------


@prop("item_box", views=((-35, 20), (35, 20), (0, 0), (90, 50)))
def item_box():
    """1.2 m floating item box. ORIGIN AT ITS CENTRE. Translucent rainbow
    rounded-cube shell (ItemBox), bold glowing "?" (Emissive), soft core (ItemBox)."""
    h = 0.6
    shell = S.Box((h, h, h), round=0.17)

    def rainbow(p):
        hue = np.mod((p[:, 0] * 0.35 + p[:, 1] * 0.25 + p[:, 2] * 0.45) / 1.2 + 0.55, 1.0)
        rgb = np.array([colorsys.hsv_to_rgb(x, 0.42, 1.0) for x in hue])
        # brighter, whiter edges and corners
        q = np.abs(p) / h
        edge = np.sort(q, axis=1)[:, 1]  # second largest -> 1 along edges
        e = L.smooth(0.72, 0.95, edge)
        rgb = rgb * (1 - e[:, None]) + e[:, None]
        return L.S.srgb_to_linear(rgb)

    sh = L.sdf_part("shell", shell.paint(rainbow), (-0.7,) * 3, (0.7,) * 3, 0.012, 1600, L.mat("ItemBox"))
    # soft core: a squashed pale glow disc behind the glyph (keeps the "?" readable)
    core = S.Ellipsoid((0.33, 0.12, 0.33), color="#e6f6ff")
    co = L.sdf_part("core", core, (-0.4,) * 3, (0.4,) * 3, 0.015, 360, L.mat("ItemBox"))
    q = L.text_bold("question", "?", 0.95, 0.09, L.mat("Emissive"), rot=(90, 0, 180), color="#ffe14a", bevel=0.025,
                    res=4)
    _recenter(q)
    L.paint(q, fn=lambda V: L.ramp(V[:, 2], [(-0.4, "#ff9a1a"), (0.0, "#ffd23c"), (0.4, "#fff6b0")]))
    parts = [sh, co, q]
    return parts, []


# ---------------------------------------------------------------------------
# Boost pad
# ---------------------------------------------------------------------------


@prop("boost_pad", views=((-30, 30), (30, 30), (180, 25), (0, 75)))
def boost_pad():
    """Flat 4 m (X) x 5 m (Y) panel, 6 cm thick, bevelled Metal rim; the top
    "BoostPad" surface is a separate grid with UV u = 0..1 across X,
    v = 0..1 along Y (Godot scrolls chevrons). Origin at the base centre."""
    hx, hy, t = 2.0, 2.5, 0.06
    inset = 0.16
    body = S.Box((hx, hy, t / 2), round=0.025).at(0, 0, t / 2)
    recess = S.Box((hx - inset, hy - inset, 0.03), round=0.012).at(0, 0, t + 0.012)
    frame = S.Subtract(body, recess, k=0.008)

    def rim_col(p):
        c = L.ramp(p[:, 2], [(0.0, "#6f7480"), (0.06, "#c9ced8")])
        # orange inner lip
        inner = (np.abs(p[:, 0]) < hx - inset + 0.03) & (np.abs(p[:, 1]) < hy - inset + 0.03) & (p[:, 2] > 0.02)
        c[inner] = L.col("#ff8a1a")
        return c

    rim = L.sdf_part("rim", frame.paint(rim_col), (-hx - 0.05, -hy - 0.05, -0.02), (hx + 0.05, hy + 0.05, 0.08), 0.008,
                     2400, L.mat("Metal"))
    nx, ny = 9, 11
    ix, iy = hx - inset, hy - inset
    us = np.linspace(0, 1, nx)
    vs = np.linspace(0, 1, ny)
    V, UV = [], []
    for u in us:
        for v in vs:
            V.append((-ix + 2 * ix * u, -iy + 2 * iy * v, t - 0.016))
            UV.append((u, v))
    F = L.grid_faces(nx, ny)
    mb = L.MB()
    mb.add(np.array(V), F, color="#ffffff", uv=np.array(UV))
    top = mb.object("boost_surface", L.mat("BoostPad"), smooth=False)
    return [rim, top], []


# ---------------------------------------------------------------------------
# Ramp
# ---------------------------------------------------------------------------


@prop("ramp", views=((-40, 18), (40, 18), (150, 20), (90, 4)))
def ramp():
    """Jump ramp 8 m wide (X) x 6 m long (Y): rises from 0 at y = -3 to 1.4 m
    at y = +3 on a gentle kicker curve. Orange/white striped deck (Paint),
    steel side trusses (Metal). Origin at the base centre."""
    W, Lh, H = 4.0, 3.0, 1.4
    th = 0.1

    def zf(y):
        t = np.clip((y + Lh) / (2 * Lh), 0, 1)
        return H * (0.35 * t + 0.65 * t ** 2)

    bands = 10
    rows_per = 3
    ny = bands * rows_per + 1
    ys = np.linspace(-Lh, Lh, ny)
    xs = np.linspace(-W, W, 9)
    mb = L.MB()
    # deck top
    V = np.array([(x, y, zf(y) + (0.0 if y > -Lh + 0.01 else 0.0)) for y in ys for x in xs])
    F = L.grid_faces(ny, len(xs))
    band_col = ["#ff7a1a", "#fff7ea"]
    fcol = []
    for f in range(len(F)):
        row = f // (len(xs) - 1)
        col_i = f % (len(xs) - 1)
        c = band_col[(row // rows_per) % 2]
        if col_i in (0, len(xs) - 2):
            c = "#2b2d35" if (row // rows_per) % 2 else "#ffd23c"
        fcol.append(L.col(c))
    mb.add(V, F, fcol=np.array(fcol))
    # underside + sides + lip (thickness)
    Vb = V.copy()
    Vb[:, 2] = np.maximum(V[:, 2] - th, 0.0)
    mb.add(Vb, [f[::-1] for f in F], color="#7a7f88")
    for sx in (-1, 1):
        side = []
        for y in ys:
            side.append((sx * W, y, zf(y)))
            side.append((sx * W, y, max(zf(y) - th, 0.0)))
        side = np.array(side)
        Fs = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(ny - 1)]
        if sx > 0:
            Fs = [f[::-1] for f in Fs]
        mb.add(side, Fs, color="#2b2d35")
    # front lip edge (thick rounded nose bar)
    V2, F2 = L.sweep(np.array([(-W, Lh, H - 0.03), (W, Lh, H - 0.03)]), 0.09, seg=10)
    mb.add(V2, F2, color="#ffd23c")
    deck = mb.object("deck", L.mat("Paint"), angle=35)
    # side trusses: posts, top/bottom chords and diagonals
    mt = L.MB()
    for sx in (-1, 1):
        x = sx * (W - 0.15)
        post_ys = np.linspace(-Lh + 1.0, Lh - 0.05, 6)
        prev = None
        for i, y in enumerate(post_ys):
            ztop = zf(y) - th
            mt.add(*L.sweep(np.array([(x, y, 0.0), (x, y, ztop)]), 0.05, seg=8), color="#9aa0aa")
            if prev is not None:
                py, pz = prev
                mt.add(*L.sweep(np.array([(x, py, 0.08), (x, y, ztop - 0.04)]), 0.03, seg=6), color="#9aa0aa")
            prev = (y, ztop)
        mt.add(*L.sweep(np.array([(x, -Lh + 0.5, 0.04), (x, Lh, 0.04)]), 0.05, seg=8), color="#80868f")
    for y in (0.0, 1.6, Lh - 0.05):
        z = zf(y) - th - 0.06
        mt.add(*L.sweep(np.array([(-W + 0.15, y, z), (W - 0.15, y, z)]), 0.04, seg=6), color="#80868f")
    return [deck, mt.object("truss", L.mat("Metal"))], []


# ---------------------------------------------------------------------------
# Collectibles and items
# ---------------------------------------------------------------------------


@prop("seashell", views=((-30, 10), (30, 10), (180, 10), (0, 0)))
def seashell():
    """Golden scallop collectible ~0.62 m wide, faces +Y. ORIGIN AT ITS CENTRE. Material Gold."""
    hinge = np.array([0.0, 0.0, -0.27])
    R = 0.5
    N = 11
    th_max = math.radians(70)

    def fn(p):
        q = p - hinge
        r = np.hypot(q[:, 0], q[:, 2])
        th = np.arctan2(q[:, 0], q[:, 2])
        rib = np.cos(th * N / th_max * math.pi / 2 * 1.0)
        Rt = R * (1 + 0.025 * rib) * (1 - 0.06 * (th / th_max) ** 2)
        d_r = r - Rt
        d_a = (np.abs(th) - th_max) * np.maximum(r, 0.05)
        tr = np.clip(r / R, 0, 1)
        bulge = 0.105 * np.sqrt(np.clip(1 - tr ** 2.2, 0, 1)) * (0.25 + 0.75 * np.sqrt(tr)) + 0.012
        bulge = bulge + 0.014 * rib * tr ** 0.7
        d_y = np.abs(q[:, 1]) - bulge
        return np.maximum.reduce([d_r * 0.8, d_a, d_y * 0.8])

    body = S.Field(fn)
    ears = S.Union(S.Box((0.075, 0.03, 0.045), round=0.025).rot(0, -18, 0).at(-0.07, 0, -0.245),
                   S.Box((0.075, 0.03, 0.045), round=0.025).rot(0, 18, 0).at(0.07, 0, -0.245), k=0.02)
    node = S.Union(body, ears, k=0.03)

    def col(p):
        q = p - hinge
        r = np.hypot(q[:, 0], q[:, 2])
        th = np.arctan2(q[:, 0], q[:, 2])
        rib = np.cos(th * N / th_max * math.pi / 2)
        c = L.ramp(r / R, [(0.0, "#c98a14"), (0.5, "#f0b628"), (0.86, "#ffd84a"), (0.95, "#fff3b0"), (1.1, "#fff8d0")])
        return c * (0.88 + 0.12 * rib)[:, None]

    ob = L.sdf_part("shell", node.paint(col), (-0.45, -0.2, -0.36), (0.45, 0.2, 0.3), 0.005, 3800, L.mat("Gold"))
    _recenter(ob)
    return [ob], []


@prop("banana_peel", views=((-35, 35), (35, 35), (180, 35), (0, 75)))
def banana_peel():
    """Banana peel item lying on the ground (~0.5 m across), yellow with brown tips."""
    pieces = []
    for i in range(4):
        a = i * math.tau / 4 + 0.4
        d = np.array([math.cos(a), math.sin(a), 0])
        pts = [(0, 0, 0.12), d * 0.09 + [0, 0, 0.06], d * 0.18 + [0, 0, 0.03], d * 0.24 + [0, 0, 0.035],
               d * 0.27 + [0, 0, 0.075]]
        pieces.append(S.Tube(pts, [0.055, 0.06, 0.055, 0.045, 0.028], k=0.02))
    petals = S.Stretch(S.Union(*pieces, k=0.02), 1.0, 1.0, 0.55)
    nub = S.RoundCone((0, 0, 0.04), (0.01, 0.0, 0.2), 0.06, 0.03)
    stem = S.RoundCone((0.01, 0.0, 0.19), (0.04, 0.0, 0.26), 0.026, 0.02)
    node = S.Intersect(S.Union(petals, nub, stem, k=0.04), S.Plane((0, 0, -1), 0.0))

    def col(p):
        r = np.hypot(p[:, 0], p[:, 1])
        c = np.tile(L.col("#ffd62a"), (len(p), 1))
        c = c * (1 + 0.1 * L.smooth(0.0, 0.15, p[:, 2] - 0.02))[:, None]
        tip = L.smooth(0.22, 0.27, r)
        c = c * (1 - tip[:, None]) + L.col("#6a4a22")[None, :] * tip[:, None]
        st = L.smooth(0.18, 0.22, p[:, 2])
        c = c * (1 - st[:, None]) + L.col("#5a3c1c")[None, :] * st[:, None]
        # green-ish stem end + a couple of brown spots
        spots = L.smooth(0.25, 0.5, S.value_noise(p, 14, 3)) * (1 - tip)
        return c * (1 - 0.45 * spots)[:, None]

    ob = L.sdf_part("peel", node.paint(col), (-0.35, -0.35, -0.02), (0.35, 0.35, 0.3), 0.007, 2200, L.mat("Paint"))
    return [ob], []


@prop("coconut_bomb", views=((-35, 15), (35, 15), (180, 15), (0, 60)))
def coconut_bomb():
    """Coconut bomb item (~0.56 m), resting on the ground (origin at the base).
    Metal cap + rope fuse; empty "fuse" at the fuse tip (Godot spawns sparks)."""
    R = 0.28
    c = np.array([0, 0, R])
    nut = S.Ellipsoid((R, R, R * 0.96)).at(*c)
    nut = nut.displace(lambda p: 0.006 * np.sin(np.arctan2(p[:, 1], p[:, 0]) * 26 + 6 * p[:, 2]))

    def col(p):
        q = p - c
        fib = 0.5 + 0.5 * np.sin(np.arctan2(q[:, 1], q[:, 0]) * 26 + 6 * p[:, 2])
        base = L.lerp("#6b4224", "#8d5a30", fib * 0.7 + 0.3 * (0.5 + 0.5 * S.value_noise(p, 9, 2)))
        # the three "eyes" on the front-ish upper face + a cheeky red band
        out = base
        for a in (-0.35, 0.35, 0.0):
            e = np.array([math.sin(a) * 0.55, 0.62, 0.55 + (0.2 if a == 0 else 0.0)])
            e = e / np.linalg.norm(e) * R
            dd = np.linalg.norm(q - e, axis=1)
            w = 1 - L.smooth(0.04, 0.055, dd)
            out = out * (1 - w[:, None]) + L.col("#2a1a10")[None, :] * w[:, None]
        return out

    nut_ob = L.sdf_part("nut", nut.paint(col), (-0.35, -0.35, -0.02), (0.35, 0.35, 0.62), 0.01, 2400, L.mat("Wood"))
    cap = S.Revolved(lambda r, z: S.box2d(r, z - (2 * R * 0.96 - 0.005), 0.075, 0.035, 0.02))
    cap = S.Union(cap, S.Revolved(lambda r, z: S.box2d(r, z - (2 * R * 0.96 + 0.045), 0.035, 0.03, 0.012)), k=0.01)
    cap_ob = L.sdf_part("cap", cap.paint("#5a5f6a"), (-0.12, -0.12, 0.45), (0.12, 0.12, 0.66), 0.006, 700,
                        L.mat("Metal"))
    top = np.array([0, 0, 2 * R * 0.96 + 0.07])
    fuse_pts = L.bezier([top, top + [0.02, -0.02, 0.1], top + [0.12, -0.05, 0.14], top + [0.16, -0.04, 0.08]], 10)
    mb = L.MB()
    V, F = L.sweep(fuse_pts, np.linspace(0.016, 0.012, 10), seg=6)
    mb.add(V, F, color="#d8c08a", alpha=np.r_[np.repeat(np.linspace(0, 1, 10), 6), [0, 1]][:len(V)])
    fuse = mb.object("fuse_rope", L.mat("Rope"))
    marker = C.empty("fuse", tuple(fuse_pts[-1]))
    return [nut_ob, cap_ob, fuse], [marker]


@prop("chili_pepper", views=((-35, 15), (35, 15), (180, 15), (0, 0)))
def chili_pepper():
    """Big glossy red chili item (~0.62 m long). ORIGIN AT ITS CENTRE."""
    pts = L.bezier([(-0.26, 0, 0.06), (-0.05, 0, 0.1), (0.15, 0, 0.02), (0.3, 0, -0.18)], 12)
    t = np.linspace(0, 1, 12)
    radii = 0.095 * np.sin(np.pi * np.clip(0.18 + 0.82 * t, 0, 1)) ** 0.55 + 0.008
    body = S.Tube(pts, radii, k=0.03)
    body = body.displace(lambda p: 0.006 * np.cos(np.arctan2(p[:, 2] - 0.05, p[:, 1]) * 3))
    calyx = S.Union(S.Ellipsoid((0.045, 0.1, 0.1)).at(-0.28, 0, 0.065),
                    *[S.Ellipsoid((0.025, 0.045, 0.06)).rot(a, 0, 0).at(-0.25, 0.08 * math.cos(math.radians(a + 90)),
                                                                       0.065 + 0.08 * math.sin(math.radians(a + 90)))
                      for a in (0, 72, 144, 216, 288)], k=0.02)
    stem = S.Tube([(-0.3, 0, 0.065), (-0.38, 0, 0.09), (-0.42, 0, 0.17), (-0.4, 0, 0.21)],
                  [0.03, 0.026, 0.022, 0.024], k=0.01)
    green = S.Union(calyx, stem, k=0.02).paint("#3e9a2c")

    def red(p):
        c = L.ramp(p[:, 2], [(-0.2, "#a8121e"), (0.0, "#e0202a"), (0.14, "#ff5a3a")])
        return c

    node = S.Union(body.paint(red), green, k=0.02, color_k=0.006)
    ob = L.sdf_part("chili", node, (-0.45, -0.15, -0.25), (0.4, 0.15, 0.25), 0.006, 2600, L.mat("Plastic"))
    _recenter(ob)
    return [ob], []


# ---------------------------------------------------------------------------
# Crowd
# ---------------------------------------------------------------------------


@prop("crowd_member", views=((-30, 8), (30, 8), (180, 10), (0, 3)))
def crowd_member():
    """Cute ~0.9 m spectator critter: blob body, round ears, stubby feet, arms
    raised half-way (cheer-ready). Neutral light-grey vertex colour (darker
    eyes, lighter belly) for per-instance tinting. Material Crowd, < 1500 tris."""
    body = S.Ellipsoid((0.27, 0.24, 0.32)).at(0, 0, 0.36)
    head = S.Sphere(0.24).at(0, 0.01, 0.66)
    ears = S.Union(S.Ellipsoid((0.08, 0.05, 0.11)).rot(0, -22, 0).at(-0.16, -0.02, 0.88),
                   S.Ellipsoid((0.08, 0.05, 0.11)).rot(0, 22, 0).at(0.16, -0.02, 0.88))
    arms = S.Union(S.RoundCone((-0.22, 0.02, 0.48), (-0.4, 0.05, 0.72), 0.065, 0.055),
                   S.RoundCone((0.22, 0.02, 0.48), (0.4, 0.05, 0.72), 0.065, 0.055))
    feet = S.Union(S.Ellipsoid((0.08, 0.11, 0.06)).at(-0.11, 0.04, 0.05),
                   S.Ellipsoid((0.08, 0.11, 0.06)).at(0.11, 0.04, 0.05))
    node = S.Union(body, head, k=0.12)
    node = S.Union(node, ears, k=0.04)
    node = S.Union(node, arms, k=0.05)
    node = S.Union(node, feet, k=0.04)
    node = S.Intersect(node, S.Plane((0, 0, -1), 0.0))
    eye_l = np.array([-0.085, 0.215, 0.69])
    eye_r = np.array([0.085, 0.215, 0.69])

    def col(p):
        c = np.tile(L.col("#d4d4d4"), (len(p), 1))
        belly = 1 - L.smooth(0.0, 0.03, S.Ellipsoid((0.17, 0.2, 0.2)).at(0, 0.12, 0.34).dist(p))
        c = c * (1 - belly[:, None]) + L.col("#f2f2f2")[None, :] * belly[:, None]
        for e in (eye_l, eye_r):
            d = np.linalg.norm((p - e) * np.array([1.0, 1.0, 0.7]), axis=1)
            w = 1 - L.smooth(0.042, 0.052, d)
            c = c * (1 - w[:, None]) + L.col("#3a3a3a")[None, :] * w[:, None]
        cheek = 1 - L.smooth(0.025, 0.04, np.minimum(np.linalg.norm(p - [-0.15, 0.19, 0.62], axis=1),
                                                    np.linalg.norm(p - [0.15, 0.19, 0.62], axis=1)))
        c = c * (1 - 0.15 * cheek[:, None])
        return c

    ob = L.sdf_part("critter", node.paint(col), (-0.5, -0.3, -0.02), (0.5, 0.3, 1.02), 0.012, 1400, L.mat("Crowd"))
    return [ob], []
