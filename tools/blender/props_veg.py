"""Vegetation props: palms, jungle tree, bushes, fern, flowers, grass, banana."""

import math

import numpy as np

import props_lib as L
from props import prop
from tt import sdf as S

# ---------------------------------------------------------------------------
# Palms
# ---------------------------------------------------------------------------

BARK = "#8a5d3b"
BARK_DARK = "#4f3322"
BARK_LIGHT = "#b58a5c"


def palm_trunk(path, r0, r1, seg_len=0.34, flare=0.12, seed=0, faces=3200):
    P = np.asarray(path, float)
    n = len(P)
    s = np.linspace(0, 1, n)
    radii = r1 + (r0 - r1) * (1 - s) ** 1.6 + flare * np.exp(-s * 18)
    sweep = L.Sweep(P, radii)
    length = sweep.length

    def ring_mod(sv, p):
        f = np.mod(sv / seg_len, 1.0)
        bump = L.smooth(0.0, 0.8, f) * (1 - L.smooth(0.86, 1.0, f))
        base = np.interp(sv / length, s, radii)
        near_ground = L.smooth(0.0, 0.5, sv)  # no rings in the flared foot
        return base * (0.11 * bump - 0.03) * near_ground

    sweep.radius_fn = ring_mod

    def color(p):
        sv = sweep.param(p)
        f = np.mod(sv / seg_len, 1.0)
        t = sv / length
        c = L.ramp(t, [(0, "#6f5a48"), (0.15, BARK), (0.8, "#94653f"), (1.0, "#a07a4a")])
        ring = L.smooth(0.8, 0.95, f) * (1 - L.smooth(0.97, 1.0, f)) + (1 - L.smooth(0.0, 0.08, f)) * 0.6
        ring = ring * L.smooth(0.0, 0.5, sv)
        c = c * (1 - 0.55 * ring[:, None]) + np.asarray(L.col(BARK_DARK))[None, :] * 0.55 * ring[:, None]
        mid = L.smooth(0.2, 0.6, f) * (1 - L.smooth(0.6, 0.8, f))
        c = c * (1 + 0.18 * mid[:, None])
        return c * L.jitter(p, 0.08, 3.0, seed)[:, None]

    node = S.Field(sweep.dist, color=color)
    lo = P.min(axis=0) - r0 - 0.4
    hi = P.max(axis=0) + r0 + 0.4
    lo[2] = -0.05
    hi[2] = P[-1][2] + 0.05
    node = S.Intersect(node, S.Plane((0, 0, -1), 0.0))
    return L.sdf_part("trunk", node, lo, hi, voxel=0.022, faces=faces, mats=L.mat("Bark"),
                      alpha_fn=lambda p: np.zeros(len(p)))


def frond(mb, crown, az, el, length, width, droop, serrate=15, seed=0, age=0.0):
    d = np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)])
    rng = np.random.default_rng(seed)
    wf = lambda u: L.smooth(0.05, 0.3, u) * (1 - u ** 2.4) ** 0.7 * (0.9 + 0.1 * np.sin(u * 9))
    bl = L.blade(crown + d * 0.12, d, length, width, serrate=serrate, rows=3, width_fn=wf, droop=droop,
                 fold=0.18, leaf_droop=0.75, notch=0.1, sweep_fwd=1.5, thick=0.014,
                 twist=rng.uniform(-12, 12))
    old = age

    def top(u, v):
        av = np.abs(v)
        c = L.ramp(u, [(0, "#8a8a2e"), (0.2, "#1f7424"), (0.6, "#2f9a2c"), (1.0, "#6fbf35")])
        c = c * (1 - 0.25 * (1 - L.smooth(0.0, 0.25, av)))[:, None] + \
            L.col("#a8a638")[None, :] * 0.25 * (1 - L.smooth(0.0, 0.25, av))[:, None]
        c = c * (1 + 0.25 * L.smooth(0.5, 1.0, av))[:, None]
        return c * (1 - old) + L.col("#b5a43c")[None, :] * old * (0.7 + 0.3 * u[:, None])

    def bot(u, v):
        return L.ramp(u, [(0, "#7d8a34"), (0.3, "#3f7f2e"), (1.0, "#6fa23c")]) * (1 - old * 0.3)

    alpha = lambda u, v, V: np.clip(u ** 1.25 + 0.12 * np.abs(v) * u, 0, 1)
    L.add_blade(mb, bl, top, bot, alpha=alpha, mi=0)
    # rachis (midrib)
    sp = L.resample(bl["spine"], 14)
    nrm = bl["normal"]
    t = np.linspace(0, 1, len(sp))
    V, F = L.sweep(sp + np.array([0, 0, 0.012]), 0.05 * (1 - t) ** 0.9 + 0.012, seg=6)
    cc = L.ramp(np.r_[np.repeat(t, 6), [0, 1]][:len(V)], [(0, "#a79a45"), (1, "#8fb640")])
    mb.add(V, F, vcol=cc, alpha=np.clip(np.r_[np.repeat(t, 6), [0, 1]][:len(V)] ** 1.25, 0, 1), mi=0)


def palm(height=8.5, bend=1.4, bend2=0.0, lean_az=0.0, r0=0.3, r1=0.18, n_fronds=9, frond_len=3.1,
         frond_w=0.42, n_coconuts=5, seed=1, coco_color="#6c8a2a", old_fronds=2, trunk_faces=3200):
    rng = np.random.default_rng(seed)
    ca, sa = math.cos(lean_az), math.sin(lean_az)

    def rot(p):
        return np.array([p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca, p[2]])

    ctrl = [(0, 0, 0), (bend * 0.05, 0, height * 0.3), (bend * 0.5 + bend2, 0, height * 0.66),
            (bend, 0, height)]
    path = np.array([rot(np.array(c)) for c in L.bezier(ctrl, 34)])
    parts = [palm_trunk(path, r0, r1, seed=seed, faces=trunk_faces)]
    crown = path[-1]
    tdir = path[-1] - path[-3]
    tdir /= np.linalg.norm(tdir)

    # crown bulb + petiole bases + coconuts (rigid, Bark)
    bulb = S.Ellipsoid((r1 * 1.35, r1 * 1.35, r1 * 1.5), color="#7d7a3a").at(*(crown - tdir * 0.12))
    shaft = S.RoundCone(tuple(crown - tdir * 0.5), tuple(crown + tdir * 0.12), r1 * 1.05, r1 * 1.45,
                        color="#6e6a36")
    pieces = [shaft, bulb]
    golden = math.radians(137.5)
    fr = []
    for i in range(n_fronds):
        az = i * golden + rng.uniform(-0.25, 0.25) + lean_az
        # young fronds (last) up, old ones (first) drooping
        k = i / max(1, n_fronds - 1)
        el = math.radians(4 + 56 * k ** 1.2 + rng.uniform(-5, 5))
        fr.append((az, el, k))
        d = np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)])
        pieces.append(S.RoundCone(tuple(crown), tuple(crown + d * 0.38), r1 * 0.7, 0.06, color="#8a8440"))
    nuts = []
    for j in range(n_coconuts):
        a = j * TAU_N(n_coconuts) + rng.uniform(-0.3, 0.3)
        rr = r1 * 1.3 + 0.2
        c = crown - tdir * (0.5 + 0.18 * (j % 2)) + np.array([math.cos(a) * rr, math.sin(a) * rr, 0])
        nuts.append(S.Ellipsoid((0.21, 0.21, 0.23), color=coco_color).at(*c))
    crown_node = S.Union(S.Union(*pieces, k=0.12), S.Union(*nuts), k=0.03)

    def crown_col(p):
        d_c = np.linalg.norm(p - crown, axis=1)
        base = L.ramp(d_c, [(0, "#7a6a36"), (0.5, "#5b4a2c")])
        return base

    lo = crown - 1.3
    hi = crown + 1.3
    parts.append(L.sdf_part("crown", S.Union(S.Union(*pieces, k=0.12).paint(crown_col),
                                             S.Union(*nuts).paint(coco_color), k=0.03),
                            lo, hi, voxel=0.018, faces=1500, mats=L.mat("Bark"),
                            alpha_fn=lambda p: np.zeros(len(p))))
    del crown_node

    mb = L.MB()
    for i, (az, el, k) in enumerate(fr):
        length = frond_len * rng.uniform(0.9, 1.06) * (0.88 + 0.16 * (1 - k))
        droop = 0.42 + 0.38 * (1 - k)
        age = 0.35 if i < old_fronds else 0.0
        frond(mb, crown, az, el, length, frond_w * rng.uniform(0.92, 1.08), droop, serrate=int(rng.integers(10, 13)),
              seed=seed * 31 + i, age=age)
    # young spear leaves closing the top of the crown
    for j in range(2):
        az = lean_az + j * 2.6 + 0.4
        frond(mb, crown, az, math.radians(74 - j * 8), frond_len * (0.5 - j * 0.08), frond_w * 0.55, 0.35,
              serrate=8, seed=seed * 7 + j)
    parts.append(mb.object("fronds", L.mat("Leaf")))
    return parts, []


def TAU_N(n):
    return 2 * math.pi / max(1, n)


PALM_VIEWS = dict(views=((-35, 14), (35, 14), (150, 30, "top", None), (60, 2, "top", None)))


@prop("palm_a", **PALM_VIEWS)
def palm_a():
    return palm(height=8.4, bend=1.6, lean_az=0.3, n_fronds=12, frond_len=3.7, frond_w=0.66, n_coconuts=5, seed=3,
                coco_color="#8d6b2b")


@prop("palm_b", **PALM_VIEWS)
def palm_b():
    return palm(height=6.4, bend=0.8, bend2=-0.55, lean_az=2.2, r0=0.3, r1=0.2, n_fronds=11, frond_len=3.2,
                frond_w=0.7, n_coconuts=4, seed=11, coco_color="#a8a23a", old_fronds=1)


@prop("palm_c", **PALM_VIEWS)
def palm_c():
    return palm(height=9.8, bend=2.5, lean_az=-1.9, r0=0.32, r1=0.18, n_fronds=12, frond_len=3.9, frond_w=0.62,
                n_coconuts=6, seed=21, coco_color="#6e5226", old_fronds=3)


# ---------------------------------------------------------------------------
# Jungle tree
# ---------------------------------------------------------------------------


def _normal_shade(node, dark, light, bias=0.0, noise=0.08, seed=0, freq=1.5):
    """Colour fn: top-lit gradient from the SDF normal (sky-facing = light)."""
    def fn(p):
        n = S.gradient(node, p, eps=0.02)
        t = np.clip(0.5 + 0.5 * n[:, 2] + bias, 0, 1)
        c = L.lerp(dark, light, t)
        return c * L.jitter(p, noise, freq, seed)[:, None]
    return fn


@prop("jungle_tree", views=((-35, 14), (35, 14), (180, 18), (60, 45)))
def jungle_tree():
    """Broadleaf canopy tree ~9.5 m: buttress fins, forked limbs, tiered puffy canopy."""
    rng = np.random.default_rng(5)
    trunk_path = L.bezier([(0, 0, 0), (0.1, 0, 2.0), (-0.25, 0.1, 3.8), (0.05, -0.05, 5.4)], 16)
    trunk = L.Sweep(trunk_path, np.linspace(0.62, 0.4, 16))
    parts = [S.Field(trunk.dist)]

    def fin(a, R, Hh, t):
        d = np.array([math.cos(a), math.sin(a)])
        nrm = np.array([-math.sin(a), math.cos(a)])

        def fn(p):
            r = p[:, :2] @ d
            lat = p[:, :2] @ nrm
            q = np.clip(r / R, 0, 1)
            prof = Hh * (1 - q) ** 2.2
            d_prof = (p[:, 2] - prof) * 0.55
            d_r = r - R
            d_l = np.abs(lat) - t * (0.35 + 0.65 * (1 - q))
            return np.maximum.reduce([d_prof, d_l, d_r, -r])
        return S.Field(fn)

    for i in range(5):
        a = i * math.tau / 5 + rng.uniform(-0.3, 0.3)
        parts.append(fin(a, rng.uniform(1.3, 1.7), rng.uniform(1.7, 2.3), 0.26))
        # surface root continuing past the fin
        d = np.array([math.cos(a), math.sin(a), 0])
        parts.append(S.RoundCone(tuple(d * 1.4 + [0, 0, 0.05]), tuple(d * 2.3 + [0, 0, -0.02]), 0.12, 0.06))
    tops = [(2.4, 0.8, 6.7), (-2.3, 1.2, 6.6), (-0.7, -2.4, 6.8), (0.3, 0.3, 7.6), (1.5, -1.7, 6.5)]
    limbs = []
    for t in tops:
        mid = (np.array(t) + trunk_path[-3]) / 2 + np.array([0, 0, 0.4])
        limbs.append(L.Sweep(L.bezier([trunk_path[-4], mid, t], 8), np.linspace(0.28, 0.12, 8)))
    wood = S.Union(*parts, *[S.Field(lb.dist) for lb in limbs], k=0.3)
    wood = S.Intersect(wood, S.Plane((0, 0, -1), 0.0))

    def bark_col(p):
        streak = S.fbm(p * np.array([5.0, 5.0, 0.5]), 1.0, 3, 9)
        c = L.ramp(p[:, 2], [(0, "#5f5a3a"), (0.5, "#6a5140"), (3, "#7a604c"), (8, "#836a55")])
        return c * (1 + 0.18 * streak)[:, None]

    wood_ob = L.sdf_part("wood", wood.paint(bark_col), (-2.6, -2.6, -0.1), (2.8, 2.8, 8.0), voxel=0.045,
                         faces=3800, mats=L.mat("Bark"), alpha_fn=lambda p: np.zeros(len(p)))
    # canopy: three tiers of clean rounded puffs
    puffs = []
    tiers = [(6.9, 3.2, 8, 1.35), (7.9, 2.0, 6, 1.25), (8.8, 0.8, 3, 1.1)]
    for ti, (z, ring, n, r) in enumerate(tiers):
        for j in range(n):
            a = j * math.tau / n + ti * 0.6 + rng.uniform(-0.15, 0.15)
            rr = ring * rng.uniform(0.85, 1.05)
            rad = r * rng.uniform(0.85, 1.12)
            puffs.append(S.Ellipsoid((rad, rad, rad * 0.78)).at(math.cos(a) * rr + 0.1, math.sin(a) * rr - 0.1,
                                                                  z + rng.uniform(-0.2, 0.2)))
    puffs.append(S.Ellipsoid((2.2, 2.2, 1.2)).at(0.1, -0.1, 7.4))
    can = S.Union(*puffs, k=0.35)
    shade = _normal_shade(can, "#1b5424", "#8fd048", bias=-0.05, noise=0.05, seed=4, freq=0.8)

    def can_col(p):
        c = shade(p)
        hard = np.min(np.stack([q.dist(p) for q in puffs]), axis=0)
        cav = L.smooth(0.0, 0.22, hard)
        c = c * (1 - 0.45 * cav)[:, None]
        low = 1 - L.smooth(6.0, 7.4, p[:, 2])
        hi = L.smooth(8.4, 9.8, p[:, 2])
        c = c * (1 - 0.3 * low)[:, None]
        return c * (1 - 0.15 * hi[:, None]) + L.col("#b6dc5a")[None, :] * 0.15 * hi[:, None]

    canopy = L.sdf_part("canopy", can.paint(can_col), (-5.2, -5.2, 5.0), (5.2, 5.2, 10.4), voxel=0.06, faces=5200,
                        mats=L.mat("Leaf"),
                        alpha_fn=lambda p: np.clip(0.2 + 0.18 * np.hypot(p[:, 0], p[:, 1]) / 1.5
                                                   + 0.25 * L.smooth(6.5, 10, p[:, 2]), 0, 1) * L.smooth(5.2, 6.4, p[:, 2]))
    return [wood_ob, canopy], []


# ---------------------------------------------------------------------------
# Bushes, fern, flowers, grass, banana
# ---------------------------------------------------------------------------


def _leaf_colors(base, mid, tip, rib="#a9c957", rib_w=0.12, spot=None):
    def top(u, v):
        av = np.abs(v)
        c = L.ramp(u, [(0, base), (0.45, mid), (1.0, tip)])
        r = 1 - L.smooth(0.0, rib_w, av)
        c = c * (1 - 0.6 * r[:, None]) + L.col(rib)[None, :] * 0.6 * r[:, None]
        c = c * (0.85 + 0.25 * L.smooth(0.3, 1.0, av))[:, None]
        return c

    def bot(u, v):
        return L.ramp(u, [(0, base), (1.0, mid)]) * 0.9 + 0.04
    return top, bot


def _petiole(mb, a, b, r0, r1, color, bend=0.2, seg=5, alpha0=0.0, alpha1=0.3):
    a, b = np.asarray(a, float), np.asarray(b, float)
    mid = (a + b) / 2 + np.array([0, 0, bend])
    P = L.bezier([a, mid, b], 6)
    t = np.linspace(0, 1, len(P))
    V, F = L.sweep(P, r0 + (r1 - r0) * t, seg=seg)
    tt = np.r_[np.repeat(t, seg), [0, 1]][:len(V)]
    mb.add(V, F, color=color, alpha=alpha0 + (alpha1 - alpha0) * tt)


def _heart(u):
    return np.sin(np.pi * np.clip(u, 0, 1) ** 0.62) ** 0.7


@prop("bush_a")
def bush_a():
    """Philodendron-like mound of big glossy heart leaves (~1.3 m)."""
    rng = np.random.default_rng(8)
    mb = L.MB()
    top, bot = _leaf_colors("#1c6428", "#2c8c32", "#62b83f", rib="#9ccc5e")
    n = 26
    for i in range(n):
        k = i / (n - 1)
        az = i * 2.39996 + rng.uniform(-0.2, 0.2)
        # leaf bases on a dome, top leaves more upright
        el = math.radians(-4 + 80 * k ** 0.8 + rng.uniform(-5, 5))
        d = np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)])
        base = np.array([0, 0, 0.1]) + d * np.array([0.45, 0.45, 0.85]) * rng.uniform(0.9, 1.05)
        _petiole(mb, (0.04 * math.cos(az), 0.04 * math.sin(az), 0.0), base, 0.03, 0.016, "#3f7d30", bend=0.08,
                 seg=4, alpha1=0.35)
        leaf_d = np.array([d[0], d[1], 0.05 + 0.7 * k])
        bl = L.blade(base, leaf_d, rng.uniform(0.55, 0.7) * (1.1 - 0.25 * k), rng.uniform(0.25, 0.3), n=8, rows=3,
                     width_fn=_heart, droop=0.35, fold=0.24, leaf_droop=0.3, thick=0.01, twist=rng.uniform(-15, 15))
        shade = 0.8 + 0.3 * k
        L.add_blade(mb, bl, lambda u, v, s=shade: top(u, v) * s, bot, alpha=lambda u, v, V: 0.35 + 0.65 * u)
    leaves = mb.object("leaves", L.mat("Leaf"), ground=0.01)
    core = S.Ellipsoid((0.36, 0.36, 0.42), color="#24552a").at(0, 0, 0.1)
    core = S.Intersect(core, S.Plane((0, 0, -1), 0.0))
    core_ob = L.sdf_part("core", core, (-0.6, -0.6, -0.1), (0.6, 0.6, 0.8), 0.04, 300, L.mat("Leaf"),
                         alpha_fn=lambda p: np.zeros(len(p)))
    return [leaves, core_ob], []


@prop("bush_b")
def bush_b():
    """Croton clump: dense rounded bush of variegated red / orange / yellow / green leaves (~1.7 m)."""
    rng = np.random.default_rng(12)
    mb = L.MB()
    palettes = [
        _leaf_colors("#a01e24", "#e0342c", "#ff8a2a", rib="#ffd23c", rib_w=0.22),
        _leaf_colors("#1f6a2a", "#3a9a30", "#c2d63a", rib="#ffcf2c", rib_w=0.28),
        _leaf_colors("#c2401a", "#f07a1c", "#ffc93a", rib="#fff08a", rib_w=0.2),
        _leaf_colors("#6a1a3a", "#b8284a", "#f0544a", rib="#ff9a4a", rib_w=0.2),
    ]
    stems = [(0.0, 0.0, 1.3), (0.3, 0.15, 0.95), (-0.28, 0.2, 0.9), (-0.08, -0.32, 1.05), (0.22, -0.25, 0.7),
             (-0.3, -0.1, 0.62)]
    for si, (sx, sy, h) in enumerate(stems):
        top_pt = np.array([sx * 1.3, sy * 1.3, h])
        _petiole(mb, (sx * 0.3, sy * 0.3, 0.0), top_pt, 0.035, 0.024, "#6b5238", bend=0.0, seg=5, alpha1=0.15)
        n = 8
        for i in range(n):
            k = i / (n - 1)
            az = i * 2.39996 + si * 1.1
            el = math.radians(75 - 105 * k + rng.uniform(-8, 8))
            d = np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)])
            top_c, bot_c = palettes[(i + si) % 4]
            bl = L.blade(top_pt + d * 0.03, d, rng.uniform(0.5, 0.62) * (0.85 + 0.25 * k), rng.uniform(0.11, 0.14),
                         n=7, rows=2, droop=0.25 + 0.35 * k, fold=0.3, leaf_droop=0.15, thick=0.008,
                         width_fn=lambda u: np.sin(np.pi * np.clip(u, 0, 1) ** 0.75) ** 0.7)
            L.add_blade(mb, bl, top_c, bot_c, alpha=lambda u, v, V: 0.3 + 0.7 * u)
    # low skirt of leaves hugging the ground
    for i in range(10):
        az = i * math.tau / 10 + 0.3
        d = np.array([math.cos(az), math.sin(az), 0.25])
        top_c, bot_c = palettes[i % 4]
        bl = L.blade(np.array([0, 0, 0.12]) + d * 0.12, d, rng.uniform(0.55, 0.7), 0.13, n=7, rows=2, droop=0.5,
                     fold=0.3, leaf_droop=0.15, thick=0.008,
                     width_fn=lambda u: np.sin(np.pi * np.clip(u, 0, 1) ** 0.75) ** 0.7)
        L.add_blade(mb, bl, top_c, bot_c, alpha=lambda u, v, V: 0.2 + 0.6 * u)
    return [mb.object("leaves", [L.mat("Leaf")], ground=0.01)], []


@prop("fern")
def fern():
    rng = np.random.default_rng(4)
    mb = L.MB()
    top, bot = _leaf_colors("#2c6e24", "#3f9a2e", "#8cc83e", rib="#6aa63a", rib_w=0.06)
    n = 10
    for i in range(n):
        k = i / (n - 1)
        az = i * 2.39996
        el = math.radians(48 + 30 * k + rng.uniform(-6, 6))
        d = np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)])
        wf = lambda u: L.smooth(0.0, 0.15, u) * (1 - u ** 1.6) ** 0.8
        bl = L.blade(np.array([0, 0, 0.05]) + d * 0.05, d, rng.uniform(0.85, 1.05) * (1.05 - 0.2 * k), 0.18,
                     serrate=int(rng.integers(11, 13)), notch=0.12, sweep_fwd=0.8, rows=3, width_fn=wf,
                     droop=0.5 + 0.3 * (1 - k), fold=0.15, leaf_droop=0.4, thick=0.008)
        L.add_blade(mb, bl, top, bot, alpha=lambda u, v, V: np.clip(u ** 1.2 + 0.1 * np.abs(v), 0, 1))
    # two young fiddleheads
    for j in range(2):
        a = j * 2.6 + 0.5
        pts = [(0, 0, 0.03), (0.05 * math.cos(a), 0.05 * math.sin(a), 0.36)]
        for t in np.linspace(0, 1.6 * math.pi, 9):
            r = 0.05 * (1 - t / (2.2 * math.pi))
            pts.append((0.05 * math.cos(a) + r * math.cos(a) * math.cos(t), 0.05 * math.sin(a) + r * math.sin(a) * math.cos(t),
                        0.41 + r * math.sin(t)))
        P = np.array(pts)
        V, F = L.sweep(P, np.linspace(0.016, 0.009, len(P)), seg=6)
        mb.add(V, F, color="#7db83a", alpha=0.3)
    return [mb.object("fronds", L.mat("Leaf"), ground=0.01)], []


def _hibiscus(mb, center, normal, size, petal="#e8283e", throat="#8a0f2a", seed=0):
    normal = np.asarray(normal, float) / np.linalg.norm(normal)
    ref = np.array([1.0, 0, 0]) if abs(normal[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = np.cross(normal, ref)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(normal, e1)
    for i in range(5):
        a = i * math.tau / 5 + seed
        d = (math.cos(a) * e1 + math.sin(a) * e2) * 0.8 + normal * 0.55
        bl = L.blade(center, d, size, size * 0.52, n=6, rows=3,
                     width_fn=lambda u: np.sin(np.pi * np.clip(u, 0, 1) ** 0.55) ** 0.55,
                     droop=0.15, fold=-0.25, leaf_droop=-0.1, thick=0.006, up=tuple(normal))
        top = lambda u, v: L.ramp(u, [(0, throat), (0.3, petal), (1.0, petal)]) * (1 + 0.15 * np.abs(v))[:, None]
        L.add_blade(mb, bl, top, lambda u, v: L.ramp(u, [(0, throat), (0.4, petal)]) * 0.85, alpha=0.5, mi=1)
    # stamen column
    tip = center + normal * size * 0.95
    V, F = L.sweep(np.array([center, (center + tip) / 2 + normal * 0.01, tip]), [0.012, 0.009, 0.008], seg=5)
    mb.add(V, F, color="#ffd83a", alpha=0.5, mi=1)
    V, F = L.lathe([(0, -0.02), (0.022, -0.012), (0.026, 0.0), (0.02, 0.014), (0, 0.02)], seg=6)
    mb.add(V + tip, F, color="#ffb020", alpha=0.5, mi=1)


def _bird_of_paradise(mb, base, height, az):
    d = np.array([math.cos(az), math.sin(az), 0.0])
    top = np.array(base, float) + np.array([0, 0, height])
    _petiole(mb, base, top, 0.024, 0.02, "#4f8a36", bend=0.0, alpha1=0.3)
    # green-purple beak (spathe) horizontal
    bl = L.blade(top, d + np.array([0, 0, 0.12]), 0.4, 0.05, n=6, rows=3, droop=0.1, fold=0.9,
                 width_fn=lambda u: np.sin(np.pi * np.clip(u, 0.02, 1) ** 0.4), thick=0.008)
    L.add_blade(mb, bl, lambda u, v: L.ramp(u, [(0, "#3e6a3a"), (1, "#8a3a6a")]), None, alpha=0.4, mi=1)
    # orange fan petals + blue tongue
    for j, (up, ang) in enumerate(((0.9, -0.5), (1.0, 0.0), (0.85, 0.5))):
        side = np.cross(d, [0, 0, 1])
        pd = d * 0.35 + np.array([0, 0, up]) + side * ang * 0.5
        bl = L.blade(top + d * 0.1, pd, 0.34, 0.045, n=6, rows=3, droop=-0.05, fold=0.3, thick=0.006,
                     width_fn=lambda u: np.sin(np.pi * np.clip(u, 0, 1) ** 0.7) ** 0.6)
        L.add_blade(mb, bl, lambda u, v: L.ramp(u, [(0, "#ff8a1a"), (1, "#ffb42a")]), None, alpha=0.5, mi=1)
    bl = L.blade(top + d * 0.14, d * 0.6 + np.array([0, 0, 0.7]), 0.28, 0.028, n=5, rows=2, droop=0.0, fold=0.2,
                 thick=0.006)
    L.add_blade(mb, bl, "#2a5ad8", None, alpha=0.5, mi=1)


@prop("flowers")
def flowers():
    """Tropical flower clump: strap leaves, 3 hibiscus and 2 bird-of-paradise (~1 m)."""
    rng = np.random.default_rng(6)
    mb = L.MB()
    top, bot = _leaf_colors("#1f6a2a", "#2e8f33", "#6cbb3e", rib="#86bf52", rib_w=0.1)
    for i in range(10):
        az = i * 2.39996
        el = math.radians(rng.uniform(35, 70))
        d = np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)])
        bl = L.blade(np.array([0, 0, 0.02]), d, rng.uniform(0.55, 0.8), rng.uniform(0.08, 0.1), n=7, rows=3,
                     droop=0.45, fold=0.3, leaf_droop=0.2, thick=0.008)
        L.add_blade(mb, bl, top, bot, alpha=lambda u, v, V: 0.2 + 0.8 * u)
    for j, (x, y, h, col_p, col_t) in enumerate(((0.22, 0.14, 0.62, "#ec2a45", "#8a0f2a"),
                                                  (-0.24, 0.08, 0.52, "#ff5a8a", "#b0205a"),
                                                  (0.04, -0.22, 0.74, "#ffb020", "#d2401a"),
                                                  (-0.12, -0.12, 0.42, "#ec2a45", "#8a0f2a"),
                                                  (0.12, 0.3, 0.45, "#ff7a3a", "#c0202a"))):
        c = np.array([x, y, h])
        _petiole(mb, (x * 0.2, y * 0.2, 0.0), c, 0.022, 0.016, "#4a8a36", bend=0.05, alpha1=0.5)
        nrm = np.array([x * 2.5, y * 2.5, 1.0])
        _hibiscus(mb, c, nrm, 0.2, petal=col_p, throat=col_t, seed=j)
        # a couple of hibiscus leaves on each stem
        for s in (-1, 1):
            dd = np.array([x + 0.2 * s, y - 0.1 * s, 0.25])
            bl = L.blade(c * 0.6, dd, 0.18, 0.07, n=6, rows=3, droop=0.3, fold=0.2, thick=0.006,
                         width_fn=_heart)
            L.add_blade(mb, bl, top, bot, alpha=0.5)
    _bird_of_paradise(mb, (-0.1, 0.2, 0.0), 0.85, 0.4)
    _bird_of_paradise(mb, (0.15, -0.05, 0.0), 0.95, 2.6)
    return [mb.object("flowers", [L.mat("Leaf"), L.mat("Flower")], ground=0.01)], []


@prop("grass_tuft", views=((-35, 18), (35, 18), (180, 20), (90, 40)))
def grass_tuft():
    """~0.4 m clump for mass scattering, < 300 tris."""
    rng = np.random.default_rng(2)
    mb = L.MB()
    n = 10
    for i in range(n):
        az = i * 2.39996 + rng.uniform(-0.2, 0.2)
        el = math.radians(rng.uniform(55, 80))
        d = np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)])
        base = np.array([math.cos(az) * 0.03, math.sin(az) * 0.03, 0.0])
        bl = L.blade(base, d, rng.uniform(0.3, 0.45), rng.uniform(0.025, 0.035), n=4, rows=2, droop=0.35,
                     fold=0.4, leaf_droop=0.0, thick=0.004,
                     width_fn=lambda u: (1 - np.clip(u, 0, 1)) ** 0.8 * 0.9 + 0.1 * (1 - np.clip(u, 0, 1)))
        L.add_blade(mb, bl, lambda u, v: L.ramp(u, [(0, "#2f6b22"), (0.5, "#5ea332"), (1, "#b8d45a")]),
                    lambda u, v: L.ramp(u, [(0, "#2f6b22"), (1, "#8ab846")]),
                    alpha=lambda u, v, V: np.clip(u ** 1.3, 0, 1))
    return [mb.object("grass", L.mat("Leaf"))], []


@prop("banana_plant", views=((-35, 14), (35, 14), (180, 18), (60, 50)))
def banana_plant():
    """Two pseudo-stems with big torn paddle leaves and a hanging bunch (~3.2 m)."""
    rng = np.random.default_rng(9)
    mb = L.MB()
    top, bot = _leaf_colors("#3f8f2a", "#58b033", "#8fd046", rib="#d8d86a", rib_w=0.07)
    stems = [((0, 0, 0), 2.1, 0.17, 8), ((0.6, -0.4, 0), 1.2, 0.11, 5)]
    stem_objs = []
    for si, (b, h, r, nl) in enumerate(stems):
        b = np.array(b, float)
        topp = b + np.array([0.05, 0.02, h])
        node = S.RoundCone(tuple(b), tuple(topp), r * 1.25, r * 0.8)
        stripes = lambda p, b=b: L.ramp(np.clip(p[:, 2] / 2.0, 0, 1), [(0, "#6e7a32"), (0.5, "#7e9a3a"), (1, "#9ab04a")]) * \
            (1 + 0.14 * np.sin(np.arctan2(p[:, 1] - b[1], p[:, 0] - b[0]) * 7 + p[:, 2] * 2))[:, None]
        stem_objs.append(L.sdf_part(f"stem{si}", S.Intersect(node, S.Plane((0, 0, -1), 0.0)).paint(stripes),
                                    b - [0.5, 0.5, 0.1], topp + [0.5, 0.5, 0.2], 0.025, 700, L.mat("Bark"),
                                    alpha_fn=lambda p: np.zeros(len(p))))
        for i in range(nl):
            k = i / max(1, nl - 1)
            az = i * 2.39996 + si * 1.3
            el = math.radians(22 + 38 * k + rng.uniform(-6, 6))
            d = np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)])
            length = (2.0 if si == 0 else 1.3) * rng.uniform(0.85, 1.05) * (1.1 - 0.3 * k)
            width = length * 0.2
            torn = rng.random() < 0.45
            # petiole + leaf; torn leaves are "serrated" with few deep lateral cuts
            pet_end = topp + d * 0.35
            _petiole(mb, topp - [0, 0, 0.15], pet_end, 0.04 if si == 0 else 0.03, 0.025, "#8aae44", bend=0.02,
                     alpha1=0.2)
            wf = lambda u: np.sin(np.pi * np.clip(u, 0, 1) ** 0.8) ** 0.35
            if torn:
                bl = L.blade(pet_end, d, length, width, serrate=int(rng.integers(8, 11)), notch=0.3, sweep_fwd=0.25,
                             rows=3, width_fn=wf, droop=0.55 + 0.35 * (1 - k), fold=0.1, leaf_droop=0.35, thick=0.01)
            else:
                bl = L.blade(pet_end, d, length, width, n=10, rows=3, width_fn=wf, droop=0.55 + 0.35 * (1 - k),
                             fold=0.1, leaf_droop=0.35, thick=0.01)
            L.add_blade(mb, bl, top, bot, alpha=lambda u, v, V: np.clip(0.2 + 0.8 * u ** 1.1, 0, 1))
    # hanging bunch on the big stem
    b0 = np.array([0.05, 0.02, 2.05])
    stalk = L.bezier([b0, b0 + [0.4, 0.3, 0.2], b0 + [0.6, 0.45, -0.3], b0 + [0.62, 0.47, -0.8]], 10)
    V, F = L.sweep(stalk, 0.035, seg=6)
    mb.add(V, F, color="#6a7a36", alpha=0.25)
    bunch = []
    for ring in range(4):
        zc = stalk[-1][2] + 0.45 - ring * 0.12
        c = np.array([stalk[-1][0], stalk[-1][1], zc])
        for j in range(6):
            a = j * math.tau / 6 + ring * 0.5
            dd = np.array([math.cos(a), math.sin(a), 0])
            p0 = c + dd * 0.05
            p1 = c + dd * 0.14 + [0, 0, 0.04]
            p2 = c + dd * 0.17 + [0, 0, 0.14]
            bunch.append(S.Tube([p0, p1, p2], [0.028, 0.032, 0.018], k=0.01))
    bud_c = stalk[-1] + [0, 0, -0.18]
    bunch_node = S.Union(S.Union(*bunch).paint("#9cc23a"),
                         S.Ellipsoid((0.07, 0.07, 0.13), color="#7a1f4a").at(*bud_c), k=0.02)
    bunch_ob = L.sdf_part("bunch", bunch_node, stalk[-1] - [0.4, 0.4, 0.45], stalk[-1] + [0.4, 0.4, 0.8], 0.012,
                          1200, L.mat("Leaf"), alpha_fn=lambda p: np.full(len(p), 0.25))
    return stem_objs + [mb.object("leaves", L.mat("Leaf"), ground=0.01), bunch_ob], []
