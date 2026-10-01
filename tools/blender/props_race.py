"""Race furniture: tyre stack, barrier, fences, rope post, start arch,
grandstand, flags & banners, balloons, signs, billboard, torch, lamp post."""

import math

import numpy as np
from mathutils import Matrix

import props_lib as L
import tt.core as C
from props import prop
from props_beach import FACE_Y, board, flag_cloth, log
from tt import sdf as S

RED = "#e0342c"
WHITE = "#f6f1e6"
YELLOW = "#ffc72a"
BLACK = "#24252b"
TEAL = "#16a6b6"
BLUE = "#1f6fd8"
ORANGE = "#ff7a1a"
GREEN = "#3fb83a"
BALLOON_COLS = [RED, YELLOW, TEAL, "#ff5fa0", GREEN, ORANGE, BLUE]


def _rounded_profile(pts, r=0.04, n=3):
    """Round the corners of a closed 2D polyline (y, z)."""
    P = np.asarray(pts, float)
    out = []
    m = len(P)
    for i in range(m):
        a, b, c = P[i - 1], P[i], P[(i + 1) % m]
        da = (a - b) / (np.linalg.norm(a - b) + 1e-9)
        dc = (c - b) / (np.linalg.norm(c - b) + 1e-9)
        rr = min(r, np.linalg.norm(a - b) * 0.45, np.linalg.norm(c - b) * 0.45)
        s, e = b + da * rr, b + dc * rr
        for t in np.linspace(0, 1, n):
            out.append((1 - t) ** 2 * s + 2 * (1 - t) * t * b + t * t * e)
    return np.array(out)


def extrude_x(profile, xs, scale=None):
    """Closed (y, z) profile extruded through x stations; returns verts, faces
    (faces ordered station-band-major: f = band * n + k) + end caps."""
    prof = np.asarray(profile, float)
    n = len(prof)
    V = []
    for i, x in enumerate(xs):
        s = 1.0 if scale is None else scale[i]
        c = prof.mean(axis=0)
        q = c + (prof - c) * s
        q[:, 1] = np.maximum(q[:, 1], 0.0) if prof[:, 1].min() >= 0 else q[:, 1]
        V.append(np.stack([np.full(n, x), q[:, 0], q[:, 1]], 1))
    V = np.concatenate(V)
    F = []
    for i in range(len(xs) - 1):
        for k in range(n):
            a = i * n + k
            b = i * n + (k + 1) % n
            F.append((a, b, b + n, a + n))
    c0 = len(V)
    V = np.concatenate([V, [[xs[0], *prof.mean(0)]], [[xs[-1], *prof.mean(0)]]])
    last = (len(xs) - 1) * n
    for k in range(n):
        F.append((c0, (k + 1) % n, k))
        F.append((c0 + 1, last + k, last + (k + 1) % n))
    return V, F


def _orient(V, F):
    """Flip faces if the mesh is inside-out (signed volume test)."""
    V = np.asarray(V)
    vol = 0.0
    for f in F:
        for k in range(1, len(f) - 1):
            vol += np.dot(V[f[0]], np.cross(V[f[k]], V[f[k + 1]]))
    return F if vol >= 0 else [f[::-1] for f in F]


# ---------------------------------------------------------------------------
# Tyres, barrier
# ---------------------------------------------------------------------------


def tire_geo(center, ro=0.38, ri=0.2, w=0.26, seg=24):
    rc = (ro + ri) / 2
    a, b = (ro - ri) / 2, w / 2
    prof = []
    for t in np.linspace(0, math.tau, 17)[:-1]:
        ct, st = math.cos(t), math.sin(t)
        # superellipse cross-section (chunky tyre)
        r = rc + a * np.sign(ct) * abs(ct) ** 0.55
        z = b * np.sign(st) * abs(st) ** 0.55
        prof.append((r, z))
    prof.append(prof[0])
    V, F = L.lathe(prof, seg=seg, center=center, cap=False)
    return V, F, prof


@prop("tire_stack", views=((-35, 20), (35, 20), (180, 20), (90, 60)))
def tire_stack():
    """Three stacked tyres (~0.78 m tall, 0.76 m wide) painted in alternating red / white."""
    mb = L.MB()
    rng = np.random.default_rng(1)
    for i, colr in enumerate((RED, WHITE, RED)):
        c = (rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), 0.13 + i * 0.255)
        V, F, prof = tire_geo(c)
        seg = 24
        fcol = []
        for f in range(len(F)):
            band = f // seg
            r0, z0 = prof[band]
            r1, z1 = prof[band + 1]
            inner = (r0 + r1) / 2 < 0.25
            groove = (abs((z0 + z1) / 2) < 0.03) and (r0 + r1) / 2 > 0.36
            fcol.append(L.col(BLACK if inner else ("#5a1a18" if groove and colr == RED else
                                                   ("#b8b2a6" if groove else colr))))
        mb.add(V, F, fcol=np.array(fcol))
    return [mb.object("tyres", L.mat("Tire"), angle=50)], []


@prop("barrier", views=((-35, 18), (35, 18), (180, 18), (90, 5)))
def barrier():
    """Water-filled plastic crash barrier, 2 m long along X (red half / white
    half so segments alternate when tiled), 0.8 m tall. Origin at base centre."""
    prof = _rounded_profile([(-0.28, 0.0), (0.28, 0.0), (0.27, 0.12), (0.14, 0.3), (0.11, 0.78), (-0.11, 0.78),
                             (-0.14, 0.3), (-0.27, 0.12)], r=0.05, n=4)
    prof = prof[::-1]
    xs = np.r_[-1.0, -0.985, np.linspace(-0.96, 0.96, 13), 0.985, 1.0]
    scale = np.r_[0.9, 0.96, np.ones(13), 0.96, 0.9]
    V, F = extrude_x(prof, xs, scale)
    F = _orient(V, F)
    n = len(prof)
    fcol = []
    for f in F:
        xc = np.mean([V[j][0] for j in f])
        zc = np.mean([V[j][2] for j in f])
        c = RED if xc < 0 else WHITE
        if 0.5 < zc < 0.56:
            c = WHITE if xc < 0 else RED
        fcol.append(L.col(c))
    mb = L.MB()
    mb.add(V, F, fcol=np.array(fcol))
    # fill caps + connector lugs
    for x in (-0.55, 0.55):
        Vc, Fc = L.lathe([(0.0, 0.78), (0.07, 0.78), (0.07, 0.81), (0.0, 0.82)], seg=10, center=(x, 0, 0))
        mb.add(Vc, Fc, color=BLACK)
    for x in (-1.02, 1.02):
        Vc, Fc = L.box_geo((0.03, 0.06, 0.08), (x, 0, 0.62))
        mb.add(Vc, Fc, color=BLACK)
    return [mb.object("barrier", L.mat("Plastic"), angle=40)], []


# ---------------------------------------------------------------------------
# Fences and rope post
# ---------------------------------------------------------------------------


@prop("fence_wood", views=((-30, 15), (30, 15), (180, 15), (0, 5)))
def fence_wood():
    """Rustic split-rail fence segment, 3 m along X (x = -1.5..1.5); posts at
    x = -1.5 and 0 so segments tile without doubling posts. ~1.1 m tall."""
    mb = L.MB()
    rng = np.random.default_rng(4)
    for x in (-1.5, 0.0):
        V, F = L.sweep(np.array([(x, 0, 0.0), (x + 0.01, 0, 1.1)]), [0.085, 0.075], seg=7)
        mb.add(V, F, color="#8a5d3a")
        Vc, Fc = L.lathe([(0.075, 1.08), (0.04, 1.16), (0.0, 1.18)], seg=7, center=(x + 0.01, 0, 0))
        mb.add(Vc, Fc, color="#a4744a")
    for z, dz in ((0.45, 0.04), (0.88, -0.03)):
        pts = []
        for t in np.linspace(0, 1, 7):
            x = -1.62 + 3.24 * t
            pts.append((x, 0.07 + 0.015 * math.sin(t * 7), z + dz * math.sin(t * math.pi) - 0.02 * math.sin(t * 9)))
        V, F = L.sweep(np.array(pts), np.full(7, 0.055), seg=6, scale_xy=(0.75, 1.0))
        mb.add(V, F, color=["#b07a4a", "#a06c42"][int(z > 0.6)] if True else None)
    # little cross-tie on the middle post
    V, F = L.sweep(np.array([(-0.05, 0.1, 0.4), (0.06, 0.1, 0.95)]), 0.03, seg=5)
    mb.add(V, F, color="#d8c08a")
    del rng
    return [mb.object("fence", L.mat("Wood"), angle=40)], []


def bamboo(mb, a, b, r, node_len=0.32, seg=6, base="#c9b056", node="#8a7a34"):
    a, b = np.asarray(a, float), np.asarray(b, float)
    Lb = np.linalg.norm(b - a)
    n_nodes = max(1, int(Lb / node_len))
    ts = []
    for k in range(n_nodes + 1):
        t0 = k / n_nodes
        ts += [t0 - 0.02, t0, t0 + 0.02] if 0 < k < n_nodes else [t0]
    ts = np.clip(np.array(ts), 0, 1)
    P = a[None, :] + (b - a)[None, :] * ts[:, None]
    R = np.full(len(ts), r)
    for i, t in enumerate(ts):
        if any(abs(t - k / n_nodes) < 1e-6 for k in range(1, n_nodes)):
            R[i] = r * 1.12
    V, F = L.sweep(P, R, seg=seg)
    fcol = []
    for f in range(len(F)):
        band = f // seg
        if band < len(ts) - 1:
            tm = (ts[band] + ts[band + 1]) / 2
            near = min(abs(tm - k / n_nodes) for k in range(1, n_nodes)) if n_nodes > 1 else 1
            fcol.append(L.col(node if near < 0.025 else base) * (0.92 + 0.16 * ((band // 3) % 2)))
        else:
            fcol.append(L.col("#e6d8a0"))
    mb.add(V, F, fcol=np.array(fcol))


@prop("bamboo_fence", views=((-30, 15), (30, 15), (180, 15), (0, 5)))
def bamboo_fence():
    """Bamboo palisade, 3 m along X (x = -1.5..1.5), ~1.2 m, two cross rails and rope ties."""
    mb = L.MB()
    rng = np.random.default_rng(6)
    xs = np.arange(-1.46, 1.5, 0.105)
    for i, x in enumerate(xs):
        h = 1.05 + 0.12 * ((i % 3) == 1) + rng.uniform(-0.04, 0.04)
        bamboo(mb, (x, 0, 0.0), (x, 0, h), 0.045, seg=6)
    for z in (0.3, 0.85):
        bamboo(mb, (-1.52, 0.08, z), (1.52, 0.08, z), 0.035, node_len=0.6, seg=6)
    rope = L.MB()
    for x in (-1.0, 0.0, 1.0):
        for z in (0.3, 0.85):
            Vt, Ft = L.sweep(np.array([(x + 0.06 * math.cos(a), 0.06 + 0.05 * math.sin(a), z + 0.03 * math.sin(2 * a))
                                       for a in np.linspace(0, math.tau, 9)]), 0.012, seg=4, cap=False)
            rope.add(Vt, Ft, color="#d8c08a")
    return [mb.object("bamboo", L.mat("Wood")), rope.object("ties", L.mat("Rope"))], []


@prop("rope_post", views=((-30, 15), (30, 15), (180, 15), (0, 5)))
def rope_post():
    """Track-side stanchion (1.0 m): red/white striped post, knob cap, rope
    collar with short sagging rope stubs along +-X for chaining posts."""
    mb = L.MB()
    prof = [(0.0, 0.0), (0.16, 0.0), (0.16, 0.06), (0.06, 0.1)] + \
        [(0.06 - 0.005 * (z - 0.1) / 0.8, z) for z in np.arange(0.2, 0.9, 0.1)] + \
        [(0.055, 0.9), (0.075, 0.93), (0.08, 0.99), (0.05, 1.04), (0.0, 1.05)]
    seg = 12
    V, F = L.lathe(prof, seg=seg)
    fcol = []
    for f, fc in enumerate(F):
        band = f // seg if f < (len(prof) - 1) * seg else len(prof)
        zc = np.mean([V[j][2] for j in fc])
        c = BLACK if zc < 0.08 else (RED if int((zc - 0.1) / 0.2) % 2 == 0 else WHITE)
        if zc > 0.9:
            c = YELLOW
        fcol.append(L.col(c))
    mb.add(V, F, fcol=np.array(fcol))
    post = mb.object("post", L.mat("Paint"), angle=40)
    rp = L.MB()
    Vt, Ft = L.sweep(np.array([(0.075 * math.cos(a), 0.075 * math.sin(a), 0.82) for a in np.linspace(0, math.tau, 13)]),
                     0.02, seg=5, cap=False)
    rp.add(Vt, Ft, color="#d8c08a")
    for sx in (-1, 1):
        pts = [(sx * (0.07 + 0.35 * t), 0, 0.82 - 0.12 * math.sin(t * math.pi * 0.5)) for t in np.linspace(0, 1, 6)]
        Vt, Ft = L.sweep(np.array(pts), 0.02, seg=5)
        rp.add(Vt, Ft, color="#d8c08a", alpha=np.r_[np.repeat(np.linspace(0, 0.5, 6), 5), [0, 0.5]][:len(Vt)])
    return [post, rp.object("rope", L.mat("Rope"))], []


# ---------------------------------------------------------------------------
# Start arch
# ---------------------------------------------------------------------------


def _balloon(mb, c, r, color, alpha=0.6):
    prof = [(0.0, -1.18), (0.12, -1.12), (0.08, -1.04), (0.45, -0.85), (0.8, -0.45), (0.98, 0.0), (0.9, 0.45),
            (0.6, 0.85), (0.0, 1.0)]
    V, F = L.lathe([(p[0] * r, p[1] * r) for p in prof], seg=12, center=c)
    mb.add(V, F, color=color, alpha=alpha)


@prop("start_arch", views=((-25, 12), (25, 12), (180, 14), (0, 4, "top", 16)))
def start_arch():
    """Inflatable start/finish arch spanning 22 m over the road (clear opening
    x = -11..11, ~9.5 m high), road along Y. Puffy tube with a checkered band,
    "TURBO TURMA" banner slab on both faces, balloons on top."""
    Rx, Rz, z0 = 12.0, 5.6, 4.6
    # tube centreline: leg up, elliptical crown, leg down
    pts = [(-Rx, 0, z) for z in np.linspace(0.0, z0, 16)]
    for t in np.linspace(math.pi, 0, 90)[1:-1]:
        pts.append((Rx * math.cos(t), 0, z0 + Rz * math.sin(t)))
    pts += [(Rx, 0, z) for z in np.linspace(z0, 0.0, 16)]
    P = L.resample(np.array(pts), 170)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    seg_len = 1.6
    f = np.mod(s / seg_len, 1.0)
    radii = 1.0 + 0.08 * np.sin(f * math.pi) ** 0.7 - 0.06
    radii[:3] = [1.25, 1.18, 1.1]
    radii[-3:] = [1.1, 1.18, 1.25]
    seg = 32
    # frames: keep the tube's local "up" = world Y so the band is on the faces
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    N = np.tile([0.0, 1.0, 0.0], (len(P), 1))
    B = np.cross(T, N)
    ang = np.arange(seg) * math.tau / seg
    V = (P[:, None, :] + radii[:, None, None] * (np.cos(ang)[None, :, None] * N[:, None, :]
                                                  + np.sin(ang)[None, :, None] * B[:, None, :])).reshape(-1, 3)
    F = []
    for i in range(len(P) - 1):
        for k in range(seg):
            a = i * seg + k
            b = i * seg + (k + 1) % seg
            F.append((a, b, b + seg, a + seg))
    F = _orient(V, F)
    fcol = []
    for fi in range(len(F)):
        i, k = fi // seg, fi % seg
        a = (k + 0.5) * math.tau / seg
        ny = math.cos(a)
        if abs(ny) > 0.94:
            check = (i // 2 + int((a % math.pi) / (math.tau / seg) // 2)) % 2
            c = BLACK if check else WHITE
        elif abs(ny) > 0.86:
            c = YELLOW
        else:
            c = RED if int(s[i] / seg_len) % 2 == 0 else ORANGE
        fcol.append(L.col(c))
    mb = L.MB()
    mb.add(V, F, fcol=np.array(fcol), alpha=0.0)
    # anchor bags at the feet
    for sx in (-1, 1):
        for dy in (-1.6, 1.6):
            Vb, Fb = L.lathe([(0.0, 0.0), (0.55, 0.0), (0.6, 0.25), (0.45, 0.55), (0.0, 0.6)], seg=10,
                             center=(sx * Rx, dy, 0))
            mb.add(Vb, Fb, color="#3a3e48")
    tube = mb.object("tube", L.mat("Plastic"))
    # banner slab across the crown, both faces
    top = z0 + Rz
    bw, bh = 6.2, 1.15
    bz = top + 1.0 + bh - 0.2
    pb = L.MB()
    board(pb, (0, 0, bz), (bw, 0.7, bh), color=BLUE)
    board(pb, (0, 0, bz), (bw + 0.12, 0.62, bh + 0.12), color=YELLOW)
    for sx in (-1, 1):
        V2, F2 = L.sweep(np.array([(sx * (bw + 0.12), 0, bz + bh + 0.1), (sx * (bw + 0.12), 0, bz - bh - 0.1)]),
                         0.16, seg=8)
        pb.add(V2, F2, color=YELLOW)
        # struts tying the slab to the tube
        x_s = sx * (bw - 1.0)
        z_t = z0 + Rz * math.sqrt(max(0, 1 - (x_s / Rx) ** 2)) + 0.6
        V2, F2 = L.sweep(np.array([(x_s, 0, z_t), (x_s, 0, bz - bh + 0.1)]), 0.1, seg=6)
        pb.add(V2, F2, color="#9aa0aa")
    parts = [tube, pb.object("banner", L.mat("Paint"), angle=35)]
    for rot, y, nm in ((FACE_Y, 0.72, "title_front"), ((90, 0, 0), -0.72, "title_back")):
        t = L.text_bold(nm, "TURBO TURMA", 1.45, 0.08, L.mat("Paint"), loc=(0, y, bz - 0.05), rot=rot,
                        color="#ffffff", bevel=0.03, res=2)
        L.paint(t, fn=lambda V: L.ramp(V[:, 2], [(bz - 0.6, "#ffd23c"), (bz + 0.5, "#ffffff")]))
        parts.append(t)
    # balloons along the crown
    bm = L.MB()
    spots = [(-9.0, 0.4), (-7.2, 0.15), (7.2, 0.15), (9.0, 0.4), (0.0, 0.0)]
    for j, (x, _l) in enumerate(spots):
        zt = z0 + Rz * math.sqrt(max(0, 1 - (x / Rx) ** 2)) + 0.9
        if abs(x) < 1:
            zt = bz + bh + 0.75
        for k, (dx, dy, dz) in enumerate(((0, 0, 0.5), (-0.6, 0.3, 0), (0.6, -0.3, 0.05), (0.0, 0.5, -0.25),
                                          (0.0, -0.5, -0.2))):
            _balloon(bm, (x + dx, dy, zt + dz), 0.55, BALLOON_COLS[(j * 2 + k) % len(BALLOON_COLS)])
    parts.append(bm.object("balloons", L.mat("Plastic")))
    return parts, []


# ---------------------------------------------------------------------------
# Grandstand
# ---------------------------------------------------------------------------


@prop("grandstand", views=((-30, 18), (30, 18), (160, 22), (0, 8)))
def grandstand():
    """Bleachers 14 m long (X), 6 rows rising toward -Y, front edge at y = 0,
    colourful seats, striped awning on steel columns. Origin at front-centre base."""
    W = 7.0
    rows = 6
    depth, rise, base = 0.8, 0.45, 0.55
    mp = L.MB()   # painted structure (Paint)
    ms = L.MB()   # seats (Plastic)
    mm = L.MB()   # steel (Metal)
    for i in range(rows):
        y0, y1 = -depth * i, -depth * (i + 1)
        z = base + rise * i
        board(mp, (0, (y0 + y1) / 2, z / 2), (W, depth / 2, z / 2), color=["#d9d4c8", "#cfc9bc"][i % 2])
        board(mp, (0, y0 - 0.02, z - 0.03), (W + 0.02, 0.04, 0.035), color=YELLOW)
        # bucket seats
        n = 26
        for k in range(n):
            x = -W + 0.3 + (2 * W - 0.6) * k / (n - 1)
            cy = y0 - depth * 0.55
            colr = [RED, TEAL, YELLOW, BLUE, GREEN, ORANGE][(k // 2 + i) % 6]
            V, F = L.box_geo((0.2, 0.18, 0.04), (x, cy, z + 0.2))
            ms.add(V, F, color=colr)
            V, F = L.box_geo((0.2, 0.035, 0.18), (x, cy - 0.2, z + 0.36), rot=(-8, 0, 0))
            ms.add(V, F, color=colr)
            V, F = L.box_geo((0.05, 0.05, 0.1), (x, cy, z + 0.1))
            ms.add(V, F, color=BLACK)
    back_y = -depth * rows
    top_z = base + rise * (rows - 1)
    board(mp, (0, back_y - 0.1, (top_z + 1.4) / 2), (W, 0.1, (top_z + 1.4) / 2), color="#2f8fb0")
    # side panels (stepped)
    for sx in (-1, 1):
        for i in range(rows):
            y0, y1 = -depth * i, -depth * (i + 1)
            z = base + rise * i
            board(mp, (sx * (W + 0.06), (y0 + y1) / 2, z / 2 + 0.05), (0.06, depth / 2 + 0.01, z / 2 + 0.05),
                  color="#2f8fb0")
    # front wall + railing
    board(mp, (0, 0.04, base / 2), (W + 0.05, 0.04, base / 2), color=RED)
    for x in np.linspace(-W, W, 15):
        mm.add(*L.sweep(np.array([(x, 0.06, base), (x, 0.06, base + 0.9)]), 0.025, seg=6), color="#e8e8e8")
    mm.add(*L.sweep(np.array([(-W, 0.06, base + 0.9), (W, 0.06, base + 0.9)]), 0.04, seg=8), color="#e8e8e8")
    # columns + awning
    a_front_z, a_back_z = top_z + 3.2, top_z + 3.9
    a_front_y, a_back_y = 1.0, back_y - 0.3
    for x in (-W + 0.2, -W / 3, W / 3, W - 0.2):
        mm.add(*L.sweep(np.array([(x, 0.25, 0.0), (x, 0.25, a_front_z - 0.25 + 0.05)]), 0.08, seg=8), color="#e8e8e8")
        mm.add(*L.sweep(np.array([(x, back_y - 0.15, 0.0), (x, back_y - 0.15, a_back_z)]), 0.08, seg=8),
               color="#e8e8e8")
        mm.add(*L.sweep(np.array([(x, 0.25, a_front_z - 0.2), (x, back_y - 0.15, a_back_z - 0.15)]), 0.06, seg=6),
               color="#e8e8e8")
    parts = [mp.object("stand", L.mat("Paint"), angle=35), ms.object("seats", L.mat("Plastic"), angle=35)]
    # awning: striped fabric sheet with scalloped valance at the front
    nx, ny = 29, 6
    xs = np.linspace(-W - 0.4, W + 0.4, nx)
    ys = np.linspace(a_back_y, a_front_y, ny)
    V = []
    for y in ys:
        t = (y - a_back_y) / (a_front_y - a_back_y)
        for x in xs:
            V.append((x, y, a_back_z + (a_front_z - a_back_z) * t + 0.12 * math.sin(t * math.pi)))
    V = np.array(V)
    F = L.grid_faces(ny, nx, flip=True)
    stripe = [WHITE, RED, WHITE, TEAL]
    fcol = np.array([L.col(stripe[(f % (nx - 1)) % 4 if True else 0]) for f in range(len(F))])
    aw = L.MB()
    aw.add(V, F, fcol=fcol, alpha=0.15)
    aw.add(V - np.array([0, 0, 0.03]), [f[::-1] for f in F], fcol=fcol * 0.85, alpha=0.15)
    # valance
    edge = V[-nx:]
    vv = []
    for j, p in enumerate(edge):
        vv.append(p)
    for j, p in enumerate(edge):
        vv.append(p - np.array([0, 0, 0.45 - 0.15 * (j % 2)]))
    vv = np.array(vv)
    Fv = [(j, j + 1, nx + j + 1, nx + j) for j in range(nx - 1)]
    fv = np.array([L.col(stripe[j % 4]) for j in range(nx - 1)])
    aw.add(vv, Fv, fcol=fv, alpha=0.5)
    aw.add(vv + np.array([0, -0.01, 0]), [f[::-1] for f in Fv], fcol=fv * 0.85, alpha=0.5)
    parts.append(aw.object("awning", L.mat("Fabric")))
    parts.append(mm.object("steel", L.mat("Metal")))
    # pennant flags along the valance top (small, Fabric)
    return parts, []


# ---------------------------------------------------------------------------
# Flags, banners, balloons
# ---------------------------------------------------------------------------


@prop("flag_pole", views=((-30, 12), (30, 12), (180, 12), (0, 4)))
def flag_pole():
    """6 m pole with a checkered race flag (1.6 x 1.0 m) ready for wind (alpha 0 at the hoist -> 1 at the fly)."""
    mb = L.MB()
    V, F = L.lathe([(0.0, 0.0), (0.22, 0.0), (0.22, 0.12), (0.08, 0.16), (0.055, 0.3), (0.045, 6.0), (0.0, 6.0)],
                   seg=10)
    mb.add(V, F, color="#e8e8ec")
    V, F = L.lathe([(0.0, 5.98), (0.07, 6.04), (0.08, 6.1), (0.06, 6.17), (0.0, 6.2)], seg=10)
    mb.add(V, F, color=YELLOW)
    pole = mb.object("pole", L.mat("Metal"), angle=40)

    def checks(u, v):
        return L.col(BLACK if (int(u * 8) + int(v * 5)) % 2 else "#ffffff")

    flag = flag_cloth((0.05, 0, 5.9), 1.6, 1.0, checks, nu=17, nv=11, wave=0.14)
    return [pole, flag], []


@prop("feather_banner", views=((-30, 12), (30, 12), (180, 12), (0, 4)))
def feather_banner():
    """Vertical feather banner ~4 m: bent fibre pole + sail (wind alpha 0 at the pole -> 1 at the free edge)."""
    pole_pts = [(0, 0, z) for z in np.linspace(0.15, 3.0, 8)]
    for t in np.linspace(0, 1, 9)[1:]:
        a = t * math.radians(80)
        pole_pts.append((0.55 * (1 - math.cos(a)) / (1 - math.cos(math.radians(80))) * 0.9, 0,
                         3.0 + 0.75 * math.sin(a) / math.sin(math.radians(80))))
    P = L.resample(np.array(pole_pts), 30)
    mb = L.MB()
    V, F = L.sweep(P, 0.022, seg=6)
    mb.add(V, F, color="#d8d8dc")
    # cross-foot base
    for a in (0, math.pi / 2):
        V, F = L.box_geo((0.4, 0.04, 0.03), (0, 0, 0.03), rot=(0, 0, math.degrees(a)))
        mb.add(V, F, color="#3a3e48")
    V, F = L.lathe([(0.06, 0.0), (0.05, 0.25), (0.0, 0.27)], seg=8)
    mb.add(V, F, color="#3a3e48")
    pole = mb.object("pole", L.mat("Metal"))
    # sail: rows along the pole from z=0.6 to the tip, extending to the free side (+X / down at the top)
    s_idx = np.arange(4, len(P))
    nu = 8
    T, _N, _B = L.frames(P)
    V, A, U, Vp = [], [], [], []
    for r_i, i in enumerate(s_idx):
        t = r_i / (len(s_idx) - 1)
        side = np.cross(T[i], [0, 1, 0])
        side = -side if side[0] < 0 else side
        w = 0.55 + 0.25 * math.sin(min(1, t * 1.3) * math.pi * 0.5)
        if t > 0.8:
            w *= max(0.05, 1 - (t - 0.8) / 0.2 * 0.95)
        for u in np.linspace(0, 1, nu):
            V.append(P[i] + side * w * u + np.array([0, 0.05 * math.sin(u * 3 + t * 4) * u, 0]))
            A.append(u ** 1.1)
            U.append(u)
            Vp.append(t)
    V = np.array(V)
    F = L.grid_faces(len(s_idx), nu, flip=True)
    fcol = []
    for f in range(len(F)):
        rr, k = f // (nu - 1), f % (nu - 1)
        t = rr / (len(s_idx) - 2)
        u = (k + 0.5) / (nu - 1)
        c = ORANGE
        if u > 0.78:
            c = YELLOW
        elif abs(u - (0.2 + 0.5 * t)) < 0.09:
            c = "#ffffff"
        fcol.append(L.col(c))
    fcol = np.array(fcol)
    cm = L.MB()
    cm.add(V, F, fcol=fcol, alpha=np.array(A))
    cm.add(V + np.array([0, -0.008, 0]), [f[::-1] for f in F], fcol=fcol * 0.9, alpha=np.array(A))
    return [pole, cm.object("sail", L.mat("Fabric"))], []


@prop("balloon_cluster", views=((-30, 12), (30, 12), (180, 12), (0, 4)))
def balloon_cluster():
    """Seven balloons on strings tied to a sand weight, floating ~2.4-3.4 m.
    Wind alpha rises from 0 at the weight to ~1 at the balloons."""
    rng = np.random.default_rng(3)
    bm = L.MB()
    sm = L.MB()
    knot = np.array([0, 0, 0.32])
    for k in range(7):
        a = k * 2.39996
        rr = 0.25 + 0.3 * (k % 3) / 2
        c = np.array([math.cos(a) * rr, math.sin(a) * rr, 2.5 + 0.35 * (k % 4) + rng.uniform(-0.1, 0.1)])
        _balloon(bm, c, 0.32, BALLOON_COLS[k], alpha=1.0)
        bot = c - [0, 0, 0.32 * 1.18]
        pts = L.bezier([knot, knot + [0, 0, 0.8], bot - [0, 0, 0.5], bot], 8)
        Vs, Fs = L.sweep(pts, 0.006, seg=3)
        sm.add(Vs, Fs, color="#f0f0f0",
               alpha=np.r_[np.repeat(np.linspace(0, 0.9, 8), 3), [0, 0.9]][:len(Vs)])
    wm = L.MB()
    V, F = L.lathe([(0.0, 0.0), (0.18, 0.0), (0.2, 0.12), (0.15, 0.26), (0.05, 0.32), (0.0, 0.33)], seg=10)
    wm.add(V, F, color="#3a8fd0")
    return [bm.object("balloons", L.mat("Plastic")), sm.object("strings", L.mat("Rope")),
            wm.object("weight", L.mat("Fabric"))], []


# ---------------------------------------------------------------------------
# Signs, billboard, torch, lamp
# ---------------------------------------------------------------------------


def _poly_prism(poly2d, y0, y1):
    """Extrude a convex-or-not 2D polygon in the XZ plane between y0 and y1."""
    P = np.asarray(poly2d, float)
    n = len(P)
    V = np.concatenate([np.stack([P[:, 0], np.full(n, y0), P[:, 1]], 1),
                        np.stack([P[:, 0], np.full(n, y1), P[:, 1]], 1)])
    F = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for k in range(n):
        F.append((k, (k + 1) % n, n + (k + 1) % n, n + k))
    return V, _orient(V, F)


@prop("sign_chevron", views=((-25, 10), (25, 10), (180, 10), (0, 3)))
def sign_chevron():
    """Corner warning sign: 2.4 x 1.0 m yellow board with three bold black
    chevrons pointing +X, on two steel posts (board 0.9..1.9 m). Faces +Y."""
    W, Hh, zc = 1.2, 0.5, 1.4
    mp = L.MB()
    board(mp, (0, 0, zc), (W, 0.04, Hh), color=YELLOW)
    board(mp, (0, -0.005, zc), (W + 0.05, 0.035, Hh + 0.05), color=BLACK)
    board(mp, (0, -0.041, zc), (W, 0.002, Hh), color=YELLOW)
    for k in range(3):
        x0 = -0.75 + k * 0.62
        poly = [(x0 - 0.18, zc + 0.38), (x0 + 0.06, zc + 0.38), (x0 + 0.36, zc), (x0 + 0.06, zc - 0.38),
                (x0 - 0.18, zc - 0.38), (x0 + 0.12, zc)]
        for y0, y1 in ((0.04, 0.055), (-0.055, -0.04)):
            V, F = _poly_prism(poly if y0 > 0 else [(-p[0] * -1, p[1]) for p in poly], y0, y1)
            mp.add(V, F, color=BLACK)
    sign = mp.object("board", L.mat("Paint"), angle=30)
    mm = L.MB()
    for x in (-0.75, 0.75):
        mm.add(*L.sweep(np.array([(x, -0.09, 0.0), (x, -0.09, zc + Hh - 0.05)]), 0.045, seg=8), color="#a8adb6")
        V, F = L.box_geo((0.14, 0.14, 0.02), (x, -0.09, 0.02))
        mm.add(V, F, color="#80858e")
    return [sign, mm.object("posts", L.mat("Metal"))], []


@prop("billboard", views=((-25, 12), (25, 12), (180, 12), (0, 4)))
def billboard():
    """Sponsor billboard: 7 x 3.2 m board (2.4..5.6 m up) on steel legs with
    a catwalk; front (+Y) art for the fictional sponsor "SUCO TURBO"."""
    W, Hh, zc = 3.5, 1.6, 4.0
    mp = L.MB()
    board(mp, (0, 0, zc), (W, 0.08, Hh), color="#ffffff")
    board(mp, (0, -0.02, zc), (W + 0.12, 0.08, Hh + 0.12), color=BLUE)
    # art: sunset bands on the left, big orange "sun" disc
    for i, colr in enumerate((YELLOW, ORANGE, RED)):
        board(mp, (-W + 1.2, 0.09, zc - Hh + 0.3 + i * 0.35), (1.15, 0.01, 0.15), color=colr)
    V, F = L.lathe([(0.0, 0.0), (0.85, 0.0), (0.85, 0.02), (0.0, 0.02)], seg=24)
    V = L.xform(V, rot=(-90, 0, 0), loc=(-W + 1.2, 0.08, zc + 0.35))
    mp.add(V, _orient(V, F), color=ORANGE)
    parts = [mp.object("board", L.mat("Paint"), angle=30)]
    for s, size, z, colr in (("SUCO", 0.95, zc + 0.5, RED), ("TURBO", 0.8, zc - 0.6, TEAL)):
        t = L.text_bold("txt_" + s, s, size, 0.04, L.mat("Paint"), loc=(1.0, 0.13, z), rot=FACE_Y, color=colr, bevel=0,
                        res=2)
        parts.append(t)
    mm = L.MB()
    for x in (-2.4, 2.4):
        mm.add(*L.sweep(np.array([(x, -0.3, 0.0), (x, -0.3, zc + Hh)]), 0.13, seg=8), color="#9aa0aa")
        mm.add(*L.sweep(np.array([(x, -1.3, 0.0), (x, -0.32, zc - Hh)]), 0.08, seg=6), color="#9aa0aa")
        V, F = L.box_geo((0.35, 0.35, 0.08), (x, -0.3, 0.08))
        mm.add(V, F, color="#80858e")
    for z in (zc - Hh + 0.1, zc + Hh - 0.1):
        mm.add(*L.sweep(np.array([(-W, -0.12, z), (W, -0.12, z)]), 0.06, seg=6), color="#9aa0aa")
    # catwalk + lamps
    V, F = L.box_geo((W, 0.35, 0.03), (0, 0.4, zc - Hh - 0.12))
    mm.add(V, F, color="#80858e")
    for x in (-2.0, 0.0, 2.0):
        mm.add(*L.sweep(np.array([(x, 0.1, zc + Hh + 0.12), (x, 0.7, zc + Hh + 0.45), (x, 0.9, zc + Hh + 0.4)]), 0.035,
                        seg=6), color="#5a5f6a")
    parts.append(mm.object("steel", L.mat("Metal")))
    lm = L.MB()
    for x in (-2.0, 0.0, 2.0):
        V, F = L.box_geo((0.18, 0.1, 0.06), (x, 0.92, zc + Hh + 0.34))
        lm.add(V, F, color="#fff4c8")
    parts.append(lm.object("lamps", L.mat("Emissive")))
    return parts, []


@prop("tiki_torch", views=((-30, 12), (30, 12), (180, 12), (0, 4)))
def tiki_torch():
    """Bamboo tiki torch (1.9 m) with a woven straw cup. Empty "flame" at the top marks where Godot spawns fire."""
    mb = L.MB()
    bamboo(mb, (0, 0, 0.0), (0, 0, 1.55), 0.04, node_len=0.38, seg=7)
    wood = mb.object("pole", L.mat("Wood"))
    cup = S.Revolved(lambda r, z: S.superellipse2d(r, z - 1.68, 0.12 + 0.035 * np.clip((z - 1.55) / 0.2, 0, 1),
                                                   0.15, n=3.0))
    cup = S.Subtract(cup, S.Cylinder(0.1, 0.06).at(0, 0, 1.84), k=0.02)

    def weave(p):
        a = np.arctan2(p[:, 1], p[:, 0])
        w = (np.sin(a * 12 + np.sign(np.sin(p[:, 2] * 60)) * 0.8) > 0)
        return np.where(w[:, None], L.col("#d6ac5a")[None, :], L.col("#a87c38")[None, :])
    cup_ob = L.sdf_part("cup", cup.paint(weave), (-0.25, -0.25, 1.45), (0.25, 0.25, 1.9), 0.008, 1600, L.mat("Straw"))
    rp = L.MB()
    for z in (1.5, 1.56):
        Vt, Ft = L.sweep(np.array([(0.05 * math.cos(a), 0.05 * math.sin(a), z) for a in np.linspace(0, math.tau, 11)]),
                         0.012, seg=4, cap=False)
        rp.add(Vt, Ft, color="#c8a870")
    wick = L.MB()
    V, F = L.lathe([(0.0, 1.8), (0.05, 1.8), (0.045, 1.86), (0.0, 1.88)], seg=8)
    wick.add(V, F, color="#3a2c22")
    return [wood, cup_ob, rp.object("lashing", L.mat("Rope")), wick.object("wick", L.mat("Bark"))], \
        [C.empty("flame", (0, 0, 1.9))]


@prop("lamp_post", views=((-30, 10), (30, 10), (180, 10), (0, 3)))
def lamp_post():
    """Boardwalk lamp post (4.6 m): fluted cast base, slim pole, curled arm and a lantern (Glass + Emissive bulb)."""
    mb = L.MB()
    prof = [(0.0, 0.0), (0.24, 0.0), (0.24, 0.1), (0.18, 0.16), (0.16, 0.5), (0.11, 0.62), (0.1, 0.8),
            (0.07, 0.88), (0.06, 4.0), (0.08, 4.05), (0.08, 4.12), (0.0, 4.14)]
    V, F = L.lathe(prof, seg=12)
    mb.add(V, F, color="#2f6e5a")
    arm = [(0.0, 0, 3.75)] + [(0.05 + 0.45 * t, 0, 3.75 + 0.55 * math.sin(t * math.pi * 0.6)) for t in np.linspace(0, 1, 8)]
    V, F = L.sweep(np.array(arm), 0.035, seg=6)
    mb.add(V, F, color="#2f6e5a")
    curl = [(0.15 + 0.12 * math.cos(a), 0, 3.95 + 0.12 * math.sin(a)) for a in np.linspace(math.pi * 1.4, -0.3, 10)]
    V, F = L.sweep(np.array(curl), 0.02, seg=5)
    mb.add(V, F, color="#2f6e5a")
    lx = 0.52
    ltop = 3.75 + 0.55 * math.sin(0.6 * math.pi)
    V, F = L.lathe([(0.0, ltop - 0.05), (0.03, ltop - 0.05), (0.03, ltop - 0.12), (0.2, ltop - 0.16),
                    (0.22, ltop - 0.2), (0.0, ltop - 0.2)], seg=8, center=(lx, 0, 0))
    mb.add(V, F, color="#2f6e5a")
    V, F = L.lathe([(0.0, ltop - 0.62), (0.08, ltop - 0.62), (0.1, ltop - 0.58), (0.0, ltop - 0.56)], seg=8,
                   center=(lx, 0, 0))
    mb.add(V, F, color="#2f6e5a")
    gm = L.MB()
    V, F = L.lathe([(0.1, ltop - 0.57), (0.17, ltop - 0.2)], seg=8, center=(lx, 0, 0), cap=False)
    gm.add(V, F, color="#fff2c8")
    em = L.MB()
    V, F = L.lathe([(0.0, ltop - 0.5), (0.07, ltop - 0.45), (0.08, ltop - 0.35), (0.05, ltop - 0.27),
                    (0.0, ltop - 0.25)], seg=8, center=(lx, 0, 0))
    em.add(V, F, color="#ffe9a0")
    return [mb.object("post", L.mat("Metal"), angle=40), gm.object("glass", L.mat("Glass")),
            em.object("bulb", L.mat("Emissive"))], []
