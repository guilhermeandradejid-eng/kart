"""Beach / town props: quiosque, parasol, deck chair, surf rack, lifeguard
tower, buoy, fishing boat, pier post, beach ball."""

import math

import numpy as np
from mathutils import Matrix

import props_lib as L
from props import prop
from tt import sdf as S

WOOD = "#b07a4a"
WOOD_DARK = "#7a5234"
WOOD_LIGHT = "#d2a270"
WHITE = "#f6f1e6"
RED = "#e0342c"

# text facing +Y (readable from the front), +X, ...
FACE_Y = (90, 0, 180)
FACE_X = (90, 0, 90)


def log(mb, a, b, r, color=WOOD, seg=8, rings=2, mi=0, taper=1.0):
    a, b = np.asarray(a, float), np.asarray(b, float)
    P = np.stack([a + (b - a) * t for t in np.linspace(0, 1, rings)])
    R = r * np.linspace(1, taper, rings)
    V, F = L.sweep(P, R, seg=seg)
    mb.add(V, F, color=color, mi=mi)


def board(mb, center, half, rot=(0, 0, 0), color=WOOD, mi=0, jitter=0.0, seed=0):
    V, F = L.box_geo(half, center, rot)
    c = L.col(color)
    if jitter:
        rng = np.random.default_rng(seed)
        c = c * rng.uniform(1 - jitter, 1 + jitter)
    mb.add(V, F, color=c, mi=mi)


def flag_cloth(attach, width, height, colors, name="flag", nu=10, nv=6, wave=0.08):
    """Rectangular cloth hanging from a pole at `attach` (top of the hoist
    edge), extending along +X. Wind alpha 0 at the hoist -> 1 at the fly edge.
    `colors`: two colours in horizontal bands, or callable(u, v) -> rgb."""
    a = np.asarray(attach, float)
    us = np.linspace(0, 1, nu)
    vs = np.linspace(0, 1, nv)
    V = []
    for u in us:
        for v in vs:
            V.append(a + np.array([u * width, wave * math.sin(u * 5.5) * u, -v * height - 0.05 * u * u]))
    V = np.array(V)
    F = L.grid_faces(nu, nv)
    if callable(colors):
        fcol = np.array([colors((f // (nv - 1) + 0.5) / (nu - 1), (f % (nv - 1) + 0.5) / (nv - 1))
                         for f in range(len(F))])
    else:
        fcol = np.array([L.col(colors[int((f % (nv - 1)) >= (nv - 1) / 2)]) for f in range(len(F))])
    alpha = np.repeat(us, nv) ** 1.1
    mb = L.MB()
    mb.add(V, F, fcol=fcol, alpha=alpha)
    mb.add(V + np.array([0, -0.008, 0]), [f[::-1] for f in F], fcol=fcol * 0.9, alpha=alpha)
    return mb.object(name, L.mat("Fabric"))


# ---------------------------------------------------------------------------
# Quiosque
# ---------------------------------------------------------------------------


def thatch_roof(R=3.1, eave=2.45, apex=4.9, tiers=3, seed=0, name="roof", faces=5000):
    """Conical thatch: stacked tiers with shaggy jagged fringes and straw grooves."""
    def seg2d(r, z, a, b, th):
        pa_r, pa_z = r - a[0], z - a[1]
        ba_r, ba_z = b[0] - a[0], b[1] - a[1]
        h = np.clip((pa_r * ba_r + pa_z * ba_z) / (ba_r ** 2 + ba_z ** 2), 0, 1)
        return np.hypot(pa_r - h * ba_r, pa_z - h * ba_z) - th

    slope = (apex - eave) / R

    def fn(p):
        r = np.hypot(p[:, 0], p[:, 1])
        ang = np.arctan2(p[:, 1], p[:, 0])
        z = p[:, 2]
        d = None
        for t in range(tiers):
            Rt = R * (1 - t / tiers)
            jag = 0.08 * np.abs(np.sin(ang * (30 - 6 * t) + t)) + 0.04 * np.sin(ang * 7 + t * 2)
            z_edge = apex - slope * Rt - 0.13 * t
            di = seg2d(r, z, (0.0, apex + 0.05), (Rt + jag - 0.05, z_edge - 0.08), 0.11 + 0.04 * (r / R))
            d = di if d is None else np.minimum(d, di)
        return d + 0.012 * np.sin(ang * 90 + 3 * np.sin(r * 4))

    def col(p):
        r = np.hypot(p[:, 0], p[:, 1])
        ang = np.arctan2(p[:, 1], p[:, 0])
        streak = 0.5 + 0.5 * np.sin(ang * 90 + 3 * np.sin(r * 4))
        t = np.clip(streak * 0.6 + 0.4 * (0.5 + 0.5 * S.value_noise(p, 2.2, seed)), 0, 1)
        c = L.lerp("#a67c34", "#ecc86c", t)
        zc = apex - slope * r
        under = L.smooth(0.02, 0.14, zc - p[:, 2])
        return c * (1 - 0.4 * under)[:, None]

    node = S.Field(fn, color=col)
    finial = S.Union(S.RoundCone((0, 0, apex - 0.2), (0, 0, apex + 0.45), 0.13, 0.03, color="#9a6e3a"),
                     S.Sphere(0.1, color=RED).at(0, 0, apex + 0.52), k=0.03)
    node = S.Union(node, finial, k=0.04)
    return L.sdf_part(name, node, (-R - 0.4, -R - 0.4, eave - 0.6), (R + 0.4, R + 0.4, apex + 0.7), 0.03, faces,
                      L.mat("Straw"))


def coconut_drink(center, seed=0, mb=None):
    """Green coconut with a cut top (SDF) + a bendy straw added to `mb`."""
    c = np.asarray(center, float)
    shell = S.Ellipsoid((0.12, 0.12, 0.13), color="#5f9a2a").at(*c)
    shell = S.Intersect(shell, S.Plane((0, 0, 1), c[2] + 0.085), k=0.012)
    shell = S.ColorRegion(shell, S.Sphere(0.1).at(c[0], c[1], c[2] + 0.13), "#f2ecd0", soft=0.008)
    if mb is not None:
        rng = np.random.default_rng(seed)
        a = rng.uniform(0, math.tau)
        top = c + np.array([0.02, 0, 0.08])
        s_end = top + np.array([math.cos(a) * 0.05, math.sin(a) * 0.05, 0.2])
        V, F = L.sweep(np.array([top - [0, 0, 0.05], s_end, s_end + [math.cos(a) * 0.06, math.sin(a) * 0.06, -0.01]]),
                       0.01, seg=6)
        mb.add(V, F, color=["#ff5fa0", "#35c4e0", "#ffd23c", "#7ad04a"][seed % 4])
    return shell


@prop("beach_hut", views=((-35, 16), (35, 16), (180, 18), (0, 8)))
def beach_hut():
    """Quiosque (~6.3 m roof, 5 m tall): hexagonal plank deck, log posts,
    bamboo counter on the three +Y sides, tiered thatch roof, coconut drinks,
    a hanging coconut bunch, a COCO sign and bar stools."""
    R = 2.3
    mb = L.MB()
    mb_p = L.MB()
    w = 0.3
    for i, x in enumerate(np.arange(-R + w / 2, R, w)):
        ax = abs(x) + w / 2
        hy = R * math.sqrt(3) / 2 if ax <= R / 2 else math.sqrt(3) * (R - ax)
        board(mb, (x, 0, 0.2), (w / 2 - 0.012, max(hy, 0.12), 0.05), color=WOOD_LIGHT, jitter=0.08, seed=i)
    V, F = L.lathe([(R * 0.97, 0.0), (R * 0.97, 0.16)], seg=6, cap=False)
    mb.add(V, F, color=WOOD_DARK)
    corners = [np.array([math.cos(a), math.sin(a)]) * (R - 0.22) for a in np.arange(6) * math.tau / 6]
    apex, eave, Rr = 4.9, 2.45, 3.15
    for i, c in enumerate(corners):
        log(mb, (c[0], c[1], 0.1), (c[0], c[1], 2.75), 0.1, color="#9a6a40", seg=8)
        n = corners[(i + 1) % 6]
        log(mb, (c[0], c[1], 2.7), (n[0], n[1], 2.7), 0.07, color="#8a5c36", seg=6)
        # rafter up to the apex (hidden mostly by the thatch, visible from below)
        z_at = apex - (apex - eave) / Rr * np.linalg.norm(c) - 0.14
        log(mb, (c[0], c[1], 2.7), (c[0] * 0.1, c[1] * 0.1, apex - 0.35), 0.06, color="#8a5c36", seg=6)
        del z_at
    front = [0, 1, 2, 3]
    for k in range(3):
        a, b = corners[front[k]], corners[front[k + 1]]
        mid = (a + b) / 2
        d = b - a
        Ls = np.linalg.norm(d)
        ang = math.degrees(math.atan2(d[1], d[0]))
        out = mid / np.linalg.norm(mid)
        n = int(Ls / 0.1)
        for j in range(n):
            p = a + d * (j + 0.5) / n + out * 0.02
            log(mb, (p[0], p[1], 0.24), (p[0], p[1], 1.04), 0.047, color=["#cdaa5c", "#b8954c"][j % 2], seg=6)
        top_c = mid + out * 0.1
        board(mb, (top_c[0], top_c[1], 1.09), (Ls / 2 + 0.14, 0.25, 0.045), rot=(0, 0, ang), color=WOOD)
        band_c = mid + out * 0.08
        board(mb_p, (band_c[0], band_c[1], 0.36), (Ls / 2, 0.03, 0.08), rot=(0, 0, ang),
              color=["#1ab0c8", "#ffc12a", "#1ab0c8"][k])
    board(mb, (0, -R * 0.62, 1.25), (1.0, 0.16, 0.03), color=WOOD)
    for x in (-0.7, -0.35, 0.3, 0.65):
        V, F = L.lathe([(0.0, 0.0), (0.05, 0.0), (0.05, 0.16), (0.02, 0.2), (0.02, 0.26), (0.0, 0.26)], seg=8,
                       center=(x, -R * 0.62, 1.28))
        mb_p.add(V, F, color=["#3ab0e0", "#e0342c", "#7ad04a", "#ffc12a"][int((x + 1) * 3) % 4])
    # sign over the front: two-tone board + white letters
    sign_y = R * math.sqrt(3) / 2 - 0.12
    board(mb_p, (0, sign_y + 0.02, 2.4), (1.12, 0.03, 0.3), color="#ffe8a8")
    board(mb_p, (0, sign_y + 0.05, 2.4), (1.02, 0.02, 0.24), color="#17a38e")
    parts = [mb.object("wood", L.mat("Wood"), angle=35), mb_p.object("paint", L.mat("Paint"), angle=35)]
    parts.append(L.text_bold("sign_txt", "COCO", 0.36, 0.025, L.mat("Paint"), loc=(0, sign_y + 0.09, 2.38),
                             rot=FACE_Y, color="#ffffff", bevel=0, res=2))
    parts.append(thatch_roof(R=Rr, eave=eave, apex=apex, tiers=3, seed=2))
    mb_s = L.MB()
    drinks = []
    for k, (a_i, t) in enumerate(((1, 0.3), (1, 0.75), (2, 0.5), (0, 0.55))):
        a, b = corners[a_i], corners[a_i + 1]
        p = (a + (b - a) * t) * 1.03
        drinks.append(coconut_drink((p[0], p[1], 1.26), seed=k, mb=mb_s))
    hang = corners[4]
    bunch = [S.Ellipsoid((0.13, 0.13, 0.15), color="#7a5a2a").at(hang[0] + dx, hang[1] + dy, 2.2 + dz)
             for dx, dy, dz in ((0.16, 0.0, 0.0), (0.0, 0.16, -0.08), (0.12, 0.12, -0.24))]
    parts.append(L.sdf_part("coconuts", S.Union(*drinks, *bunch), (-R - 0.4, -R - 0.4, 0.9), (R + 0.4, R + 0.4, 2.5),
                            0.012, 2400, L.mat("Wood")))
    V, F = L.sweep(np.array([(hang[0] + 0.1, hang[1] + 0.08, 2.1), (hang[0] + 0.02, hang[1] + 0.02, 2.62)]), 0.015,
                   seg=5)
    mb_s.add(V, F, color="#d8c08a")
    parts.append(mb_s.object("straws", L.mat("Plastic")))
    mb_t = L.MB()
    for x in (-0.95, 0.0, 0.95):
        y = R + 0.45 - abs(x) * 0.45
        V, F = L.lathe([(0.0, 0.0), (0.17, 0.0), (0.12, 0.3), (0.1, 0.6), (0.21, 0.62), (0.22, 0.72), (0.0, 0.74)],
                       seg=12, center=(x, y, 0))
        fcol = np.array([L.col(RED) if (i // 12) >= 4 else L.col(WOOD) for i in range(len(F))])
        mb_t.add(V, F, fcol=fcol)
    parts.append(mb_t.object("stools", L.mat("Wood"), angle=40))
    return parts, []


# ---------------------------------------------------------------------------
# Parasol, deck chair, surf rack
# ---------------------------------------------------------------------------


@prop("umbrella", views=((-35, 20), (35, 20), (180, 35), (90, 5)))
def umbrella():
    """Striped beach parasol: canopy r 1.35 m, 2.5 m tall. Fabric canopy (wind alpha to the rim)."""
    gores = 8
    seg = gores * 4
    R = 1.35
    top_z = 2.35
    rings = np.linspace(0, 1, 9)
    ang = np.arange(seg) * math.tau / seg
    rib = np.abs(np.cos(ang * gores / 2))
    V = []
    for t in rings:
        z = top_z - 0.5 * t ** 1.6
        sag = 0.06 * t * (1 - rib)
        rr = R * t * (1 - 0.03 * (1 - rib) * t)
        V.append(np.stack([rr * np.cos(ang), rr * np.sin(ang), z - sag], 1))
    V = np.concatenate(V)
    F = L.grid_faces(len(rings), seg, close_v=True)
    colors = [RED, "#fff7ea"]
    fcol = np.array([L.col(colors[((f % seg) * gores // seg) % 2]) for f in range(len(F))])
    mb = L.MB()
    alpha_c = lambda V: np.clip(np.hypot(V[:, 0], V[:, 1]) / R, 0, 1) * 0.6
    mb.add(V, F, fcol=fcol, alpha=alpha_c(V))
    Vb = V - np.array([0, 0, 0.02])
    mb.add(Vb, [f[::-1] for f in F], fcol=fcol * 0.85, alpha=alpha_c(Vb))
    edge = V[-seg:]
    lo = edge - np.array([0, 0, 0.14])
    lo[:, 2] += 0.06 * (1 - rib)
    Vv = np.concatenate([edge, lo])
    Fv = [(s, (s + 1) % seg, seg + (s + 1) % seg, seg + s) for s in range(seg)]
    fv = np.array([L.col(colors[((s * gores // seg) + 1) % 2]) for s in range(seg)])
    mb.add(Vv, [f[::-1] for f in Fv], fcol=fv, alpha=0.7)
    mb.add(Vv * np.array([0.99, 0.99, 1]), Fv, fcol=fv * 0.85, alpha=0.7)
    canopy = mb.object("canopy", L.mat("Fabric"))
    wood = L.MB()
    V, F = L.lathe([(0.032, 0.0), (0.032, top_z + 0.02), (0.0, top_z + 0.02)], seg=10)
    wood.add(V, F, color="#f2efe6")
    V, F = L.lathe([(0.0, top_z - 0.02), (0.05, top_z + 0.02), (0.035, top_z + 0.1), (0.0, top_z + 0.15)], seg=10)
    wood.add(V, F, color=RED)
    V, F = L.lathe([(0.04, 1.1), (0.05, 1.12), (0.05, 1.2), (0.04, 1.22)], seg=10, cap=False)
    wood.add(V, F, color=RED)
    V, F = L.lathe([(0.0, 0.0), (0.24, 0.0), (0.13, 0.07), (0.035, 0.12)], seg=12)
    wood.add(V, F, color="#dcc393")
    for g in range(gores):
        a = g * math.tau / gores
        pts = [(math.cos(a) * R * t, math.sin(a) * R * t, top_z - 0.5 * t ** 1.6 - 0.025) for t in np.linspace(0.05, 0.98, 5)]
        V, F = L.sweep(np.array(pts), 0.009, seg=4)
        wood.add(V, F, color="#e8e2d4")
        mid = np.array(pts[2])
        V, F = L.sweep(np.array([mid, (0, 0, top_z - 0.75)]), 0.007, seg=4)
        wood.add(V, F, color="#e8e2d4")
    return [canopy, wood.object("pole", L.mat("Wood"))], []


@prop("beach_chair", views=((-40, 22), (40, 22), (180, 25), (90, 5)))
def beach_chair():
    """Wooden deck chair with a striped fabric sling, 0.66 m wide, 1.1 m deep, 1 m tall. Faces +Y."""
    mb = L.MB()
    W = 0.31
    for sx in (-1, 1):
        x = sx * W
        rails = [((x, 0.45, 0.42), (x, -0.25, 0.3)),
                 ((x, -0.25, 0.3), (x, -0.62, 0.98)),
                 ((x, 0.4, 0.0), (x, 0.3, 0.58)),
                 ((x, -0.5, 0.0), (x, -0.1, 0.34)),
                 ((x, 0.38, 0.58), (x, -0.32, 0.58))]
        for a, b in rails:
            log(mb, a, b, 0.024, color=WOOD, seg=6)
        board(mb, (x, 0.03, 0.605), (0.045, 0.36, 0.02), color=WOOD_LIGHT)
    for y, z in ((0.45, 0.42), (-0.25, 0.3), (-0.62, 0.98), (0.35, 0.06), (-0.45, 0.06)):
        log(mb, (-W, y, z), (W, y, z), 0.02, color=WOOD_DARK, seg=6)
    wood = mb.object("frame", L.mat("Wood"))
    path = np.array([(0, 0.43, 0.41), (0, 0.1, 0.3), (0, -0.2, 0.27), (0, -0.4, 0.56), (0, -0.6, 0.94)])
    path = L.resample(L.bezier(path, 30), 22)
    nx = 9
    xs = np.linspace(-W + 0.02, W - 0.02, nx)
    V = []
    for p in path:
        for x in xs:
            sag = 0.035 * (1 - (x / W) ** 2)
            V.append((x, p[1] + sag * 0.3, p[2] - sag))
    V = np.array(V)
    F = L.grid_faces(len(path), nx, flip=True)
    stripes = ["#1a8fe0", "#fff7ea", "#ffc12a", "#fff7ea"]
    fcol = np.array([L.col(stripes[(f % (nx - 1)) // 2 % 4]) for f in range(len(F))])
    sm = L.MB()
    sm.add(V, F, fcol=fcol, alpha=0.2)
    sm.add(V - np.array([0, 0, 0.01]), [f[::-1] for f in F], fcol=fcol * 0.85, alpha=0.2)
    return [wood, sm.object("sling", L.mat("Fabric"))], []


def surfboard(center, length, width, color, stripe):
    """Standing surfboard (nose up, deck facing +Y), rounded SDF."""
    c = np.asarray(center, float)
    hl = length / 2

    def fn(p):
        q = p - c
        z = np.clip(q[:, 2] / hl, -1, 1)
        wz = np.where(z > 0, (1 - z ** 2) ** 0.55 * (1 - 0.25 * z), (1 - z ** 2) ** 0.3) * width / 2
        thick = 0.036 * (1 - z ** 2) ** 0.4 + 0.006
        d2 = np.maximum(np.abs(q[:, 0]) - wz, np.abs(q[:, 2]) - hl) * 0.85
        dy = np.abs(q[:, 1]) - thick
        return np.hypot(np.maximum(d2, 0), np.maximum(dy, 0)) + np.minimum(np.maximum(d2, dy), 0) - 0.004

    body = S.Field(fn, color=color)
    node = S.ColorRegion(body, S.Box((width, 0.2, 0.07)).at(c[0], c[1], c[2] + length * 0.18), stripe, soft=0.004)
    node = S.ColorRegion(node, S.Box((width, 0.2, 0.025)).at(c[0], c[1], c[2] + length * 0.18 + 0.12), stripe,
                         soft=0.004)
    node = S.ColorRegion(node, S.Box((0.012, 0.2, hl * 0.8)).at(c[0], c[1], c[2] - hl * 0.1), "#fffaf0", soft=0.004)
    fin = S.Box((0.008, 0.07, 0.07), round=0.006, color=stripe).at(c[0], c[1] - 0.08, c[2] - hl * 0.8)
    return S.Union(node, fin, k=0.01)


@prop("surfboard_rack", views=((-35, 16), (35, 16), (180, 18), (0, 5)))
def surfboard_rack():
    """Rustic A-frame rack (2.4 m along X) holding four colourful boards upright."""
    mb = L.MB()
    for sx in (-1.1, 1.1):
        log(mb, (sx, -0.45, 0.0), (sx, -0.05, 1.45), 0.05, color=WOOD, seg=7)
        log(mb, (sx, 0.45, 0.0), (sx, 0.05, 1.45), 0.05, color=WOOD, seg=7)
        log(mb, (sx, -0.3, 0.55), (sx, 0.3, 0.55), 0.035, color=WOOD_DARK, seg=6)
    for y, z in ((-0.2, 0.8), (0.2, 0.8), (0.0, 1.43)):
        log(mb, (-1.2, y, z), (1.2, y, z), 0.04, color=WOOD, seg=7)
    board(mb, (0, 0, 0.1), (1.12, 0.26, 0.1), color=WOOD_DARK)
    board(mb, (0, 0, 0.21), (1.1, 0.2, 0.012), color="#5a3c26")
    wood = mb.object("rack", L.mat("Wood"), angle=35)
    boards = []
    specs = [("#ff7a2a", "#ffe04a"), ("#23b8d8", "#ffffff"), ("#ffd23c", RED), ("#7ad04a", "#1a6fd0")]
    for i, (c1, c2) in enumerate(specs):
        L_ = 2.0 - 0.14 * (i % 2)
        boards.append(surfboard((-0.75 + i * 0.5, 0.0, 0.2 + L_ / 2), L_, 0.46, c1, c2))
    ob = L.sdf_part("boards", S.Union(*boards), (-1.2, -0.3, 0.1), (1.2, 0.3, 2.4), 0.011, 4400, L.mat("Paint"))
    return [wood, ob], []


# ---------------------------------------------------------------------------
# Lifeguard tower
# ---------------------------------------------------------------------------


@prop("lifeguard_tower", views=((-35, 14), (35, 14), (180, 16), (0, 6)))
def lifeguard_tower():
    """Posto de salva-vidas (~6.5 m to the flag top): cabin on stilts, ramp to +Y,
    red/white paint, life ring, flag (Fabric, wind alpha)."""
    mb = L.MB()
    H = 2.2
    for sx in (-1, 1):
        for sy in (-1, 1):
            log(mb, (sx * 1.0, sy * 1.0, 0.0), (sx * 0.95, sy * 0.95, H), 0.08, color=WHITE, seg=8)
        log(mb, (sx * 1.0, -1.0, 0.25), (sx * 0.95, 0.95, H - 0.1), 0.04, color=RED, seg=6)
        log(mb, (-1.0, sx * 1.0, 0.25), (0.95, sx * 0.95, H - 0.1), 0.04, color=RED, seg=6)
    for i, x in enumerate(np.arange(-1.15, 1.2, 0.23)):
        board(mb, (x, 0.12, H + 0.05), (0.105, 1.37, 0.05), color=WOOD_LIGHT, jitter=0.06, seed=i)
    cz = H + 0.1
    wall_h = 1.5
    for sy in (-1, 1):
        y = sy * 0.95
        if sy < 0:
            board(mb, (0, y, cz + wall_h / 2), (1.0, 0.04, wall_h / 2), color=WHITE)
        else:
            board(mb, (0, y, cz + 0.45), (1.0, 0.04, 0.45), color=WHITE)
            board(mb, (0, y, cz + wall_h - 0.1), (1.0, 0.04, 0.1), color=WHITE)
            for x in (-0.96, 0.0, 0.96):
                board(mb, (x, y, cz + 1.1), (0.05, 0.05, 0.31), color=WHITE)
        board(mb, (0, y + sy * 0.012, cz + 0.2), (1.01, 0.04, 0.1), color=RED)
    for sx in (-1, 1):
        x = sx * 0.98
        board(mb, (x, 0, cz + 0.45), (0.04, 0.95, 0.45), color=WHITE)
        board(mb, (x, 0, cz + wall_h - 0.1), (0.04, 0.95, 0.1), color=WHITE)
        board(mb, (x, 0, cz + 1.1), (0.05, 0.05, 0.31), color=WHITE)
        board(mb, (x + sx * 0.012, 0, cz + 0.2), (0.04, 0.96, 0.1), color=RED)
    rz = cz + wall_h
    for sy in (-1, 1):
        board(mb, (0, sy * 0.62, rz + 0.3), (1.25, 0.68, 0.05), rot=(-sy * 24, 0, 0), color=RED)
    board(mb, (0, 0, rz + 0.585), (1.28, 0.08, 0.06), color=WHITE)
    for x in (-1.1, -0.55, 0.55, 1.1):
        log(mb, (x, 1.42, H + 0.1), (x, 1.42, H + 0.95), 0.03, color=WHITE, seg=6)
    log(mb, (-1.15, 1.42, H + 0.95), (-0.4, 1.42, H + 0.95), 0.04, color=RED, seg=6)
    log(mb, (0.4, 1.42, H + 0.95), (1.15, 1.42, H + 0.95), 0.04, color=RED, seg=6)
    for sx in (-0.36, 0.36):
        log(mb, (sx, 3.5, 0.0), (sx, 1.47, H + 0.08), 0.05, color=WHITE, seg=6)
        log(mb, (sx, 3.5, 0.9), (sx, 1.47, H + 0.95), 0.03, color=RED, seg=6)
    for i in range(9):
        t = (i + 0.5) / 9
        board(mb, (0, 3.5 - 2.03 * t, (H + 0.08) * t + 0.03), (0.34, 0.08, 0.025), color=WOOD_LIGHT)
    parts = [mb.object("tower", L.mat("Paint"), angle=35)]
    gm = L.MB()
    board(gm, (0, 0.94, cz + 1.1), (0.95, 0.01, 0.29), color="#2a3e52")
    for sx in (-1, 1):
        board(gm, (sx * 0.97, 0, cz + 1.1), (0.01, 0.9, 0.29), color="#2a3e52")
    parts.append(gm.object("windows", L.mat("Glass")))
    rc = np.array([0.8, 1.48, H + 0.55])
    ring = S.Torus(0.24, 0.065).rot(90, 0, 0).at(*rc)

    def ring_col(p):
        a = np.arctan2(p[:, 2] - rc[2], p[:, 0] - rc[0])
        return np.where((np.mod(a / (math.pi / 2), 2) < 1)[:, None], L.col("#ff5a1a")[None, :], L.col("#ffffff")[None, :])
    parts.append(L.sdf_part("lifering", ring.paint(ring_col), rc - 0.4, rc + 0.4, 0.012, 900, L.mat("Plastic")))
    pm = L.MB()
    V, F = L.lathe([(0.035, rz + 0.5), (0.035, rz + 2.3), (0.0, rz + 2.36)], seg=8)
    pm.add(V, F, color="#dddddd")
    parts.append(pm.object("pole", L.mat("Metal")))
    parts.append(flag_cloth((0.035, 0, rz + 2.28), 0.85, 0.55, [RED, "#ffd23c"], name="flag"))
    parts.append(L.text_bold("sign", "SALVA-VIDAS", 0.19, 0.012, L.mat("Paint"), loc=(0, 1.0, cz + 0.6), rot=FACE_Y,
                             color=RED, bevel=0, res=2))
    return parts, []


# ---------------------------------------------------------------------------
# Buoy, boat, pier post, beach ball
# ---------------------------------------------------------------------------


@prop("buoy", views=((-35, 14), (35, 14), (180, 18), (90, 3)))
def buoy():
    """Channel buoy. Origin at the WATERLINE (z = 0): float -0.45..0.57 m, lamp top at 1.55 m."""
    prof = [(0.0, -0.45), (0.3, -0.42), (0.5, -0.2), (0.55, 0.05), (0.5, 0.35), (0.34, 0.52), (0.18, 0.56),
            (0.0, 0.57)]
    prof = L.resample(np.array([(r, 0, z) for r, z in prof]), 16)[:, [0, 2]]
    seg = 24
    V, F = L.lathe(prof, seg=seg)
    fcol = []
    for f in F:
        zc = np.mean([V[j][2] for j in f])
        red = (zc < -0.05) or (0.2 < zc < 0.4) or zc > 0.5
        fcol.append(L.col(RED if red else "#fff7ea"))
    mb = L.MB()
    mb.add(V, F, fcol=np.array(fcol))
    ring = L.MB()
    V, F = L.sweep(np.array([(0.57 * math.cos(a), 0.57 * math.sin(a), 0.05) for a in np.linspace(0, math.tau, 25)]),
                   0.05, seg=8, cap=False)
    ring.add(V, F, color="#2b2d35")
    parts = [mb.object("float", L.mat("Plastic"), angle=40), ring.object("fender", L.mat("Tire"))]
    cage = L.MB()
    for k in range(4):
        a = k * math.tau / 4 + math.pi / 4
        cage.add(*L.sweep(np.array([(0.22 * math.cos(a), 0.22 * math.sin(a), 0.5),
                                    (0.12 * math.cos(a), 0.12 * math.sin(a), 1.35)]), 0.025, seg=6), color="#d8d8d0")
    V, F = L.sweep(np.array([(0.13 * math.cos(a), 0.13 * math.sin(a), 1.3) for a in np.linspace(0, math.tau, 17)]),
                   0.022, seg=6, cap=False)
    cage.add(V, F, color="#d8d8d0")
    V, F = L.lathe([(0.0, 1.3), (0.16, 1.3), (0.16, 1.36), (0.0, 1.36)], seg=12)
    cage.add(V, F, color="#d8d8d0")
    parts.append(cage.object("cage", L.mat("Metal")))
    lm = L.MB()
    V, F = L.lathe([(0.0, 1.36), (0.08, 1.37), (0.09, 1.46), (0.06, 1.53), (0.0, 1.55)], seg=12)
    lm.add(V, F, color="#ffcf3a")
    parts.append(lm.object("light", L.mat("Emissive")))
    return parts, []


@prop("boat", views=((-40, 18), (40, 18), (160, 22), (90, 4)))
def boat():
    """Small colourful wooden fishing boat, 4.6 m long (along Y, bow +Y),
    1.6 m beam. Origin at the WATERLINE; keel at z = -0.35."""
    Lh = 2.3
    Bh = 0.8

    def half_width(y, z):
        t = np.clip(y / Lh, -1, 1)
        w = np.where(t > 0, (1 - t ** 2.2) ** 0.65, (1 - np.abs(t) ** 3.5) ** 0.5 * 0.92)
        flare = 0.72 + 0.28 * np.clip((z + 0.35) / 0.9, 0, 1)
        return Bh * w * flare

    def gunwale(y):
        t = y / Lh
        return 0.55 + 0.35 * np.clip(t, 0, 1) ** 2.5 + 0.12 * np.clip(-t, 0, 1) ** 2

    def keel(y):
        t = y / Lh
        return -0.35 + 0.25 * np.clip(t, 0, 1) ** 2.0 + 0.05 * np.clip(-t, 0, 1) ** 2

    def hull(p, inset=0.0):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        hw = half_width(y, z) - inset
        rel = np.abs(x) / np.maximum(hw, 1e-3)
        bottom = keel(y) + inset + 0.22 * np.minimum(rel, 1.5) ** 2
        return np.maximum.reduce([(np.abs(x) - hw) * 0.8, (bottom - z) * 0.7, np.abs(y) - (Lh - inset * 1.5)])

    outer = S.Field(lambda p: np.maximum(hull(p), p[:, 2] - gunwale(p[:, 1])))
    inner = S.Field(lambda p: np.maximum(hull(p, 0.07), -(p[:, 2] - (keel(p[:, 1]) + 0.14))))
    shell = S.Subtract(outer, inner, k=0.03)

    def hull_col(p):
        z = p[:, 2]
        g = gunwale(p[:, 1])
        c = np.tile(L.col("#1f7fd0"), (len(p), 1))
        c[z < 0.02] = L.col(RED)
        c[z > g - 0.17] = L.col("#fff7ea")
        c[z > g - 0.06] = L.col("#ffc12a")
        inside = inner.dist(p) < 0.03
        c[inside] = L.col("#c49262")
        c[inside & (z < keel(p[:, 1]) + 0.22)] = L.col("#9a6e48")
        return c

    parts = [L.sdf_part("hull", shell.paint(hull_col), (-1.0, -2.5, -0.5), (1.0, 2.5, 1.0), 0.02, 6500,
                        L.mat("Paint"))]
    mb = L.MB()
    for y, w in ((0.9, 0.6), (-0.3, 0.72), (-1.4, 0.66)):
        board(mb, (0, y, 0.34), (w, 0.13, 0.03), color=WOOD_LIGHT)
    for x in (-0.3, 0.0, 0.3):
        board(mb, (x, -0.2, -0.12), (0.12, 1.5, 0.02), color="#a9784c")
    for sx in (-1, 1):
        a = np.array([sx * 0.2, -1.2, 0.42])
        b = np.array([sx * 0.52, 1.3, 0.56])
        log(mb, a, b, 0.026, color=WOOD, seg=6)
        dirv = (b - a) / np.linalg.norm(b - a)
        V, F = L.sweep(np.array([b, b + dirv * 0.18, b + dirv * 0.42]), [0.03, 0.075, 0.07], seg=8,
                       scale_xy=(1.0, 0.18))
        mb.add(V, F, color=RED)
    parts.append(mb.object("fittings", L.mat("Wood"), angle=35))
    name = L.text_bold("name", "SAUDADE", 0.15, 0.008, L.mat("Paint"), rot=FACE_X, color="#ffffff", bevel=0, res=2)
    y_n = 1.2
    z_n = float(gunwale(y_n)) - 0.33
    x_n = float(half_width(np.array([y_n]), np.array([z_n]))[0]) + 0.012
    name.data.transform(Matrix.Translation((x_n, y_n, z_n)))
    parts.append(name)
    return parts, []


@prop("pier_post")
def pier_post():
    """Weathered wooden piling (2.6 m) with rope lashing, a mooring cleat and a weedy, barnacled foot."""
    def rad(s, p):
        return 0.012 * np.sin(np.arctan2(p[:, 1], p[:, 0]) * 9) + 0.01 * S.value_noise(p, 3.0, 2)

    sw = L.Sweep(np.array([(0, 0, 0), (0.0, 0.02, 1.3), (0.02, 0.0, 2.55)]), [0.2, 0.19, 0.18], radius_fn=rad)

    def col(p):
        c = L.ramp(p[:, 2], [(0, "#4f5a3a"), (0.5, "#5f6844"), (0.62, "#7a5a3c"), (2.2, "#9a7654"), (2.6, "#a8845e")])
        return c * (1 + 0.14 * S.fbm(p * np.array([6, 6, 0.8]), 1.0, 2, 4))[:, None]
    top = S.Revolved(lambda r, z: S.box2d(r, z - 2.55, 0.17, 0.04, 0.03))
    node = S.Union(S.Field(sw.dist), top, k=0.05).paint(col)
    barn = S.Union(*[S.Sphere(0.035 + 0.01 * (i % 3)).at(0.2 * math.cos(i * 2.4), 0.2 * math.sin(i * 2.4),
                                                        0.15 + 0.07 * (i % 5)) for i in range(14)]).paint("#cfc8b8")
    wood = L.sdf_part("post", S.Intersect(S.Union(node, barn, k=0.02), S.Plane((0, 0, -1), 0.0)),
                      (-0.35, -0.35, -0.05), (0.35, 0.35, 2.7), 0.014, 2400, L.mat("Wood"))
    rope = S.Union(*[S.Torus(0.205, 0.028).at(0, 0, z) for z in (1.95, 2.02, 2.09, 2.16)]).paint("#d8c08a")
    rp = L.sdf_part("rope", rope, (-0.3, -0.3, 1.85), (0.3, 0.3, 2.25), 0.01, 900, L.mat("Rope"))
    cleat = S.Union(S.Capsule((-0.14, 0.24, 1.6), (0.14, 0.24, 1.6), 0.035),
                    S.Capsule((-0.05, 0.17, 1.6), (-0.05, 0.24, 1.6), 0.03),
                    S.Capsule((0.05, 0.17, 1.6), (0.05, 0.24, 1.6), 0.03), k=0.02)
    cl = L.sdf_part("cleat", cleat.paint("#4a4d55"), (-0.25, 0.1, 1.5), (0.25, 0.32, 1.7), 0.008, 500, L.mat("Metal"))
    return [wood, rp, cl], []


@prop("beach_ball", views=((-35, 20), (35, 20), (180, 30), (90, 60)))
def beach_ball():
    """0.5 m beach ball, six coloured gores and white caps. Origin at the base (resting on the ground)."""
    R = 0.25
    seg = 36
    prof = [(R * math.sin(t), R - R * math.cos(t)) for t in np.linspace(0, math.pi, 17)]
    V, F = L.lathe(prof, seg=seg, cap=False)
    cols = [RED, "#ffffff", "#ffc12a", "#ffffff", "#1a7fe0", "#ffffff"]
    fcol = []
    for i in range(len(F)):
        band = i // seg
        fcol.append(L.col("#ffffff") if band < 2 or band >= 14 else L.col(cols[((i % seg) * 6) // seg]))
    mb = L.MB()
    mb.add(V, F, fcol=np.array(fcol))
    V2, F2 = L.lathe([(0.0, 2 * R + 0.004), (0.04, 2 * R - 0.001), (0.045, 2 * R - 0.006)], seg=12, cap=False)
    mb.add(V2, F2, color="#1a7fe0")
    return [mb.object("ball", L.mat("Plastic"))], []
