"""Shared helpers for the Turbo Turma environment props (props.py).

* `mat(name)`      - vertex-coloured materials whose NAMES select the Godot shader.
* `MB`             - tiny numpy mesh builder with per-corner colours (crisp
                     stripes / checkers without extra geometry), optional UVs.
* geometry helpers - lathe / sweep / grid / leaf blades that feed an MB.
* `Sweep`          - SDF of a tapered tube along a polyline, exposes the
                     arc-length parameter (trunk rings, bamboo nodes, ...).
* `finish()`       - bake transforms, unify colour attributes, join into one
                     mesh, parent to the root empty, export .glb, return stats.
"""

import math
import os

import bpy  # noqa: F401
import bmesh
import numpy as np
from mathutils import Matrix, Vector

from tt import core as C
from tt import sdf as S

H = S.hexrgb
TAU = 2 * math.pi

# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

_SPEC = {
    "Bark": dict(rough=0.9),
    "Leaf": dict(rough=0.42, coat=0.25),
    "Flower": dict(rough=0.5),
    "Rock": dict(rough=0.85),
    "Sand": dict(rough=0.95),
    "Wood": dict(rough=0.72),
    "Straw": dict(rough=0.9),
    "Fabric": dict(rough=0.8),
    "Plastic": dict(rough=0.33, coat=0.3),
    "Metal": dict(rough=0.32, metal=0.85),
    "Rope": dict(rough=0.9),
    "Paint": dict(rough=0.4, coat=0.4),
    "Gold": dict(rough=0.22, metal=1.0),
    "Glass": dict(rough=0.05, alpha=0.4),
    "Tire": dict(rough=0.85),
    "Emissive": dict(rough=0.4),
    "ItemBox": dict(rough=0.06, alpha=0.42, coat=1.0),
    "BoostPad": dict(rough=0.3),
    "Water": dict(rough=0.05, alpha=0.6),
    "Crowd": dict(rough=0.6),
}


def mat(name):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = C.material(name, "#ffffff", use_vcol=True, **_SPEC[name])
    if name in ("Emissive", "BoostPad"):
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        vc = [n for n in nt.nodes if n.type == "VERTEX_COLOR"][0]
        nt.links.new(vc.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 2.5 if name == "Emissive" else 0.6
    return m


# ---------------------------------------------------------------------------
# Colour helpers (linear rgb)
# ---------------------------------------------------------------------------


def col(c):
    return np.asarray(H(c) if isinstance(c, str) else c, float)


def lerp(a, b, t):
    t = np.asarray(t, float)
    a, b = col(a), col(b)
    if t.ndim == 0:
        return a * (1 - t) + b * t
    return a[None, :] * (1 - t[:, None]) + b[None, :] * t[:, None]


def ramp(t, stops):
    """stops = [(pos, colour), ...] -> (N,3) linear colours."""
    t = np.atleast_1d(np.asarray(t, float))
    pos = np.array([s[0] for s in stops])
    cs = np.array([col(s[1]) for s in stops])
    out = np.empty((len(t), 3))
    for k in range(3):
        out[:, k] = np.interp(t, pos, cs[:, k])
    return out


def smooth(e0, e1, x):
    return S._smoothstep(e0, e1, x)


def jitter(p, amount=0.06, freq=1.0, seed=0):
    """Multiplicative brightness noise for vertex colours."""
    return 1.0 + amount * S.value_noise(np.asarray(p, float), freq, seed)


# ---------------------------------------------------------------------------
# Mesh builder
# ---------------------------------------------------------------------------


class MB:
    """Accumulates (verts, faces, per-corner RGBA, per-vertex UV, material idx)."""

    def __init__(self):
        self.V = []
        self.F = []       # list of tuples (global indices)
        self.FC = []      # per-face list of (k,4) corner colours
        self.FM = []
        self.UV = []
        self.has_uv = False
        self.n = 0

    def add(self, verts, faces, color="#ffffff", fcol=None, vcol=None, alpha=None, uv=None, mi=0):
        """color: constant; fcol: (m,3|4) per face; vcol: (n,3|4) per vertex;
        alpha: scalar or (n,) per vertex wind weight."""
        verts = np.asarray(verts, float).reshape(-1, 3)
        nv = len(verts)
        if vcol is not None:
            vc = np.asarray(vcol, float)
            if vc.ndim == 1:
                vc = np.tile(vc, (nv, 1))
        else:
            vc = np.tile(col(color), (nv, 1))
        if vc.shape[1] == 3:
            vc = np.concatenate([vc, np.ones((nv, 1))], axis=1)
        if alpha is not None:
            vc[:, 3] = np.broadcast_to(np.asarray(alpha, float), (nv,))
        fc = None
        if fcol is not None:
            fc = np.asarray(fcol, float)
            if fc.ndim == 1:
                fc = np.tile(fc, (len(faces), 1))
        for i, f in enumerate(faces):
            f = tuple(int(x) for x in f)
            self.F.append(tuple(x + self.n for x in f))
            if fc is not None:
                c = np.tile(np.r_[fc[i][:3], 1.0], (len(f), 1))
                c[:, 3] = vc[list(f), 3]
            else:
                c = vc[list(f)]
            self.FC.append(c)
            self.FM.append(mi)
        self.V.append(verts)
        if uv is not None:
            self.has_uv = True
            self.UV.append(np.asarray(uv, float))
        else:
            self.UV.append(np.zeros((nv, 2)))
        self.n += nv
        return self

    def object(self, name, mats, smooth=True, angle=None, ground=None):
        V = np.concatenate(self.V) if self.V else np.zeros((0, 3))
        if ground is not None:  # leaves resting on the ground instead of poking through
            V = V.copy()
            V[:, 2] = np.maximum(V[:, 2], ground)
        ob = C.mesh_from_pydata(name, V, self.F)
        me = ob.data
        corner = np.concatenate(self.FC).astype(np.float32)
        a = me.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
        a.data.foreach_set("color", corner.ravel())
        me.color_attributes.active_color = a
        if self.has_uv:
            uvl = me.uv_layers.new(name="UVMap")
            UV = np.concatenate(self.UV)
            li = np.empty(len(me.loops), dtype=np.int32)
            me.loops.foreach_get("vertex_index", li)
            uvl.data.foreach_set("uv", UV[li].astype(np.float32).ravel())
        if not isinstance(mats, (list, tuple)):
            mats = [mats]
        for m in mats:
            me.materials.append(m)
        if len(mats) > 1:
            me.polygons.foreach_set("material_index", np.asarray(self.FM, dtype=np.int32))
        C.shade_smooth(ob, smooth)
        if smooth and angle:
            C.add_smooth_by_angle(ob, angle)
        return ob


# ---------------------------------------------------------------------------
# Geometry generators -> (verts, faces)
# ---------------------------------------------------------------------------


def grid_faces(nu, nv, close_u=False, close_v=False, flip=False):
    """Quads for a (nu, nv) vertex grid indexed i*nv + j."""
    F = []
    for i in range(nu if close_u else nu - 1):
        for j in range(nv if close_v else nv - 1):
            a = i * nv + j
            b = ((i + 1) % nu) * nv + j
            c = ((i + 1) % nu) * nv + (j + 1) % nv
            d = i * nv + (j + 1) % nv
            F.append((a, d, c, b) if flip else (a, b, c, d))
    return F


def lathe(profile, seg=32, phase=0.0, center=(0, 0, 0), cap=True):
    """profile [(r, z), ...] bottom->top. Returns verts, faces, ring-major.
    Faces are ordered ring band by band; face (band i, sector s) has index
    i*seg + s (caps appended after)."""
    prof = np.asarray(profile, float)
    ang = phase + np.arange(seg) * TAU / seg
    V = []
    for r, z in prof:
        V.append(np.stack([r * np.cos(ang), r * np.sin(ang), np.full(seg, z)], axis=1))
    V = np.concatenate(V) + np.asarray(center, float)
    F = []
    n = len(prof)
    for i in range(n - 1):
        for s in range(seg):
            a = i * seg + s
            b = i * seg + (s + 1) % seg
            F.append((a, b, b + seg, a + seg))
    if cap:
        extra = []
        if prof[0][0] > 1e-6:
            c0 = len(V)
            extra.append(np.r_[center[0], center[1], prof[0][1] + center[2]])
            for s in range(seg):
                F.append((c0, (s + 1) % seg, s))
        if prof[-1][0] > 1e-6:
            c1 = len(V) + len(extra)
            extra.append(np.r_[center[0], center[1], prof[-1][1] + center[2]])
            base = (n - 1) * seg
            for s in range(seg):
                F.append((c1, base + s, base + (s + 1) % seg))
        if extra:
            V = np.concatenate([V, np.array(extra)])
    return V, F


def frames(path, up=(0, 0, 1)):
    """Parallel-transport frames along a polyline -> T, N, B (n,3)."""
    P = np.asarray(path, float)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    u = np.asarray(up, float)
    if abs(np.dot(T[0], u)) > 0.95:
        u = np.array([1.0, 0, 0]) if abs(T[0][0]) < 0.9 else np.array([0, 1.0, 0])
    N = [np.cross(np.cross(T[0], u), T[0])]
    N[0] /= np.linalg.norm(N[0])
    for i in range(1, len(P)):
        n = N[-1] - np.dot(N[-1], T[i]) * T[i]
        N.append(n / (np.linalg.norm(n) + 1e-12))
    N = np.array(N)
    B = np.cross(T, N)
    return T, N, B


def sweep(path, radii, seg=10, cap=True, phase=0.0, scale_xy=(1.0, 1.0)):
    """Tube along `path` with per-point radius. Faces ordered band-major
    (face index = i*seg + s), caps appended."""
    P = np.asarray(path, float)
    R = np.broadcast_to(np.asarray(radii, float), (len(P),))
    T, N, B = frames(P)
    ang = phase + np.arange(seg) * TAU / seg
    ca, sa = np.cos(ang) * scale_xy[0], np.sin(ang) * scale_xy[1]
    V = (P[:, None, :] + R[:, None, None] * (ca[None, :, None] * N[:, None, :] + sa[None, :, None] * B[:, None, :]))
    V = V.reshape(-1, 3)
    n = len(P)
    F = []
    for i in range(n - 1):
        for s in range(seg):
            a = i * seg + s
            b = i * seg + (s + 1) % seg
            F.append((a, a + seg, b + seg, b))
    if cap:
        extra = []
        if R[0] > 1e-6:
            c0 = len(V)
            extra.append(P[0])
            for s in range(seg):
                F.append((c0, s, (s + 1) % seg))
        if R[-1] > 1e-6:
            c1 = len(V) + len(extra)
            extra.append(P[-1])
            base = (n - 1) * seg
            for s in range(seg):
                F.append((c1, base + (s + 1) % seg, base + s))
        if extra:
            V = np.concatenate([V, np.array(extra)])
    return V, F


def bezier(pts, n=24):
    """Evaluate a Bezier curve of any degree through control points."""
    P = np.asarray(pts, float)
    t = np.linspace(0, 1, n)[:, None]
    k = len(P) - 1
    out = np.zeros((n, 3))
    for i, p in enumerate(P):
        out += math.comb(k, i) * (1 - t) ** (k - i) * t ** i * p
    return out


def resample(path, n):
    P = np.asarray(path, float)
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    s = np.linspace(0, d[-1], n)
    return np.stack([np.interp(s, d, P[:, k]) for k in range(3)], axis=1)


def xform(V, rot=(0, 0, 0), loc=(0, 0, 0), scale=1.0):
    R = S.rot_matrix(*rot)
    return (np.asarray(V, float) * scale) @ R.T + np.asarray(loc, float)


def box_geo(half, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Flat-shaded box (24 verts) -> verts, faces (face order: -x,+x,-y,+y,-z,+z)."""
    hx, hy, hz = half
    V, F = [], []
    for axis in range(3):
        for sgn in (-1, 1):
            u, v = [a for a in range(3) if a != axis]
            quad = []
            for (a, b) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = [0, 0, 0]
                p[axis] = sgn
                p[u] = a
                p[v] = b
                quad.append(p)
            quad = np.array(quad, float) * np.array([hx, hy, hz])
            # outward winding
            nrm = np.cross(quad[1] - quad[0], quad[2] - quad[0])
            if np.dot(nrm, np.eye(3)[axis] * sgn) < 0:
                quad = quad[::-1]
            F.append(tuple(range(len(V), len(V) + 4)))
            V.extend(quad)
    return xform(np.array(V), rot, loc), F


# ---------------------------------------------------------------------------
# Leaf blades (fronds, broad leaves, petals, grass)
# ---------------------------------------------------------------------------


def blade(base, direction, length, width, n=16, rows=4, width_fn=None, droop=0.4, fold=0.25,
          leaf_droop=0.3, serrate=0, notch=0.35, sweep_fwd=0.35, thick=0.012, twist=0.0,
          curl=0.0, up=(0, 0, 1), side_up=0.0, lean=0.0):
    """A leaf/frond blade along a drooping spine.

    Returns dict(top=(V,F), bot=(V,F), u=(nv,), v=(nv,), spine=(n,3)).
    `serrate` > 0 gives that many leaflets per side (zig-zag outline, notch
    depth `notch` of the half width). `fold` lifts the leaf halves into a V
    (positive) or cups them, `leaf_droop` drops the edges."""
    base = np.asarray(base, float)
    d0 = np.asarray(direction, float)
    d0 = d0 / np.linalg.norm(d0)
    g = np.array([0, 0, -1.0])
    # spine: integrate a gently bending direction (gravity + curl)
    ns = max(n, 12)
    us = np.linspace(0, 1, ns)
    pts = [base]
    d = d0.copy()
    step = length / (ns - 1)
    horiz = np.cross(np.array(up, float), d0)
    if np.linalg.norm(horiz) < 1e-6:
        horiz = np.array([1.0, 0, 0])
    horiz /= np.linalg.norm(horiz)
    for i in range(1, ns):
        d = d + g * droop * step * (0.6 + 1.2 * us[i]) / max(length, 1e-6) * 2.2 + horiz * curl * step / max(length, 1e-6)
        d /= np.linalg.norm(d)
        pts.append(pts[-1] + d * step)
    spine = np.array(pts)
    T, _N, _B = frames(spine)
    side = np.cross(T, np.array(up, float)[None, :])
    bad = np.linalg.norm(side, axis=1) < 1e-6
    side[bad] = horiz
    side /= np.linalg.norm(side, axis=1, keepdims=True)
    # twist the leaf plane about the spine
    if twist:
        a = np.radians(twist) * us[:, None]
        nrm0 = np.cross(side, T)
        side = side * np.cos(a) + nrm0 * np.sin(a)
    nrm = np.cross(side, T)  # roughly up
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)

    def spine_at(u):
        idx = np.clip(u, 0, 1) * (ns - 1)
        i0 = np.clip(np.floor(idx).astype(int), 0, ns - 2)
        f = (idx - i0)[:, None]
        pick = lambda A: A[i0] * (1 - f) + A[i0 + 1] * f
        return pick(spine), pick(side), pick(nrm)

    if width_fn is None:
        width_fn = lambda u: np.sin(np.pi * np.clip(u, 0, 1) ** 0.85) ** 0.8
    # columns along u
    if serrate:
        m = 2 * serrate + 1
        uc = np.linspace(0.0, 1.0, m)
        tip = (np.arange(m) % 2 == 1)
    else:
        m = n
        uc = np.linspace(0, 1, m)
        tip = np.ones(m, bool)
    rv = np.linspace(0, 1, rows)
    verts, U, Vv = [], [], []
    for sgn in (-1, 1):
        for j in range(m):
            e = 1.0 if tip[j] else notch
            for t in rv:
                v = t * e
                u = uc[j] + (sweep_fwd / max(serrate, 1)) * v * (1.0 if serrate else 0.0) * 1.0
                U.append(u)
                Vv.append(sgn * v)
    U = np.array(U)
    Vv = np.array(Vv)
    uu = np.clip(U, 0, 1)
    sp, sd, nr = spine_at(uu)
    w = width * width_fn(uu)
    av = np.abs(Vv)
    lift = fold * av - leaf_droop * av ** 2 + side_up * av * np.sign(Vv)
    P = sp + sd * (Vv * w)[:, None] + nr * (lift * w)[:, None]
    # lean the whole leaf plane
    # faces for each side grid (m columns x rows)
    F = []
    for k, sgn in enumerate((-1, 1)):
        off = k * m * rows
        for j in range(m - 1):
            for r in range(rows - 1):
                a = off + j * rows + r
                b = off + (j + 1) * rows + r
                c = off + (j + 1) * rows + r + 1
                d = off + j * rows + r + 1
                F.append((a, d, c, b) if sgn > 0 else (a, b, c, d))
    # surface normals to offset the underside
    Fa = np.array(F)
    fn = np.cross(P[Fa[:, 1]] - P[Fa[:, 0]], P[Fa[:, 2]] - P[Fa[:, 0]])
    vn = np.zeros_like(P)
    for i in range(4):
        np.add.at(vn, Fa[:, i], fn)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    # make sure "top" normals point along nrm (up-ish)
    if np.mean(np.sum(vn * nr, axis=1)) < 0:
        F = [f[::-1] for f in F]
        vn = -vn
    bot = P - vn * thick
    Fb = [f[::-1] for f in F]
    return dict(top=(P, F), bot=(bot, Fb), u=uu, v=Vv, spine=spine, normal=vn)


def add_blade(mb, bl, top_col, bot_col=None, alpha=None, mi=0):
    """top_col/bot_col: callables (u, v) -> (N,3) or constants."""
    for key, c in (("top", top_col), ("bot", bot_col if bot_col is not None else top_col)):
        V, F = bl[key]
        cc = c(bl["u"], bl["v"]) if callable(c) else np.tile(col(c), (len(V), 1))
        a = alpha(bl["u"], bl["v"], V) if callable(alpha) else alpha
        mb.add(V, F, vcol=cc, alpha=a, mi=mi)


# ---------------------------------------------------------------------------
# SDF helpers
# ---------------------------------------------------------------------------


class Sweep(S.Primitive):
    """SDF of a tapered tube along a polyline; `param(p)` = arc length (m) of
    the closest point, `radius_fn(s, p)` can modulate the radius (rings)."""

    def __init__(self, path, radii, radius_fn=None, **kw):
        super().__init__(**kw)
        self.P = np.asarray(path, float)
        self.R = np.broadcast_to(np.asarray(radii, float), (len(self.P),)).copy()
        seg = np.diff(self.P, axis=0)
        self.L = np.linalg.norm(seg, axis=1)
        self.S0 = np.r_[0, np.cumsum(self.L)]
        self.length = self.S0[-1]
        self.radius_fn = radius_fn

    def _closest(self, p):
        best = np.full(len(p), np.inf)
        s = np.zeros(len(p))
        r = np.zeros(len(p))
        for i in range(len(self.P) - 1):
            a, b = self.P[i], self.P[i + 1]
            ba = b - a
            h = np.clip(((p - a) @ ba) / (ba @ ba), 0, 1)
            dd = np.linalg.norm(p - a - h[:, None] * ba, axis=1)
            ri = self.R[i] * (1 - h) + self.R[i + 1] * h
            val = dd - ri
            sel = val < best
            best = np.where(sel, val, best)
            s = np.where(sel, self.S0[i] + h * self.L[i], s)
            r = np.where(sel, dd, r)
        return best, s, r

    def dist(self, p):
        d, s, dd = self._closest(p)
        if self.radius_fn is not None:
            d = d - self.radius_fn(s, p)
        return d

    def param(self, p):
        return self._closest(p)[1]


def facet_rock(center, radii, nplanes=14, seed=0, k=0.18, noise=0.04, jitter_r=0.12, flat_bottom=True,
               color="#8f857a"):
    """Faceted-soft boulder: smooth intersection of random half spaces clipped
    to an ellipsoid, plus a hint of noise. Returns an SDF node."""
    rng = np.random.default_rng(seed)
    radii = np.asarray(radii, float)
    c = np.asarray(center, float)
    # fibonacci-ish directions, jittered
    ns = []
    for i in range(nplanes):
        z = 1 - 2 * (i + 0.5) / nplanes
        a = i * 2.39996 + rng.uniform(-0.4, 0.4)
        rr = math.sqrt(max(0, 1 - z * z))
        ns.append((rr * math.cos(a), rr * math.sin(a), z))
    ns = np.array(ns) + rng.normal(0, 0.12, (nplanes, 3))
    ns /= np.linalg.norm(ns, axis=1, keepdims=True)
    offs = 1.0 - rng.uniform(0, jitter_r, nplanes)

    def fn(p):
        q = (p - c) / radii
        d = None
        for n, o in zip(ns, offs):
            di = q @ n - o
            if d is None:
                d = di
            else:
                h = np.clip(0.5 - 0.5 * (d - di) / k, 0, 1)
                d = d * (1 - h) + di * h + k * h * (1 - h)
        e = np.linalg.norm(q, axis=1) - 1.2
        h = np.clip(0.5 - 0.5 * (d - e) / k, 0, 1)
        d = d * (1 - h) + e * h + k * h * (1 - h)
        d = d * radii.min()
        if noise:
            d = d + noise * radii.min() * S.fbm(p, 1.4 / radii.min(), 3, seed + 5)
        return d

    return S.Field(fn, color=color)


def sdf_part(name, node, lo, hi, voxel, faces, mats, alpha_fn=None, color_node=None, normals=True):
    if not isinstance(mats, (list, tuple)):
        mats = [mats]
    return C.sdf_object(name, node, lo, hi, voxel=voxel, target_faces=faces, materials=list(mats),
                        alpha_fn=alpha_fn, color_node=color_node, normals=normals)


# ---------------------------------------------------------------------------
# Blender-object helpers
# ---------------------------------------------------------------------------


def corner_colors_from_points(ob):
    """Convert a POINT colour attribute into CORNER domain (for joining)."""
    me = ob.data
    a = me.color_attributes.get("Color")
    if a is None:
        cols = np.ones((len(me.loops), 4), np.float32)
    elif a.domain == "CORNER":
        return
    else:
        pc = np.empty(len(me.vertices) * 4, np.float32)
        a.data.foreach_get("color", pc)
        pc = pc.reshape(-1, 4)
        li = np.empty(len(me.loops), dtype=np.int32)
        me.loops.foreach_get("vertex_index", li)
        cols = pc[li]
        me.color_attributes.remove(a)
    na = me.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
    na.data.foreach_set("color", cols.astype(np.float32).ravel())
    me.color_attributes.active_color = na


def paint(ob, color="#ffffff", fn=None, face_fn=None, alpha=1.0):
    """Colour a plain Blender object. fn(verts)->(n,3) smooth; face_fn(centres)->(m,3) crisp."""
    C.apply_modifiers(ob)
    C.apply_transform(ob)
    me = ob.data
    for a in list(me.color_attributes):
        me.color_attributes.remove(a)
    li = np.empty(len(me.loops), dtype=np.int32)
    me.loops.foreach_get("vertex_index", li)
    if face_fn is not None:
        fc = face_fn(C.face_centers(ob))
        lt = np.empty(len(me.polygons), dtype=np.int32)
        me.polygons.foreach_get("loop_total", lt)
        cols = np.repeat(np.asarray(fc, float), lt, axis=0)
    elif fn is not None:
        cols = np.asarray(fn(C.vertex_array(ob)), float)[li]
    else:
        cols = np.tile(col(color), (len(li), 1))
    rgba = np.ones((len(li), 4), np.float32)
    rgba[:, :3] = cols[:, :3]
    if callable(alpha):
        rgba[:, 3] = np.clip(alpha(C.vertex_array(ob)), 0, 1)[li]
    else:
        rgba[:, 3] = alpha
    na = me.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
    na.data.foreach_set("color", rgba.ravel())
    me.color_attributes.active_color = na
    return ob


def hbox(name, size, loc=(0, 0, 0), rot=(0, 0, 0), m=None, bevel=0.02, color="#ffffff", fn=None, face_fn=None,
         segments=2):
    ob = C.box(name, size=size, loc=loc, rot=rot, mat=m, bevel=bevel, bevel_segments=segments)
    return paint(ob, color, fn=fn, face_fn=face_fn)


def hcyl(name, r, depth, loc=(0, 0, 0), rot=(0, 0, 0), m=None, seg=16, bevel=0.0, color="#ffffff", fn=None,
         face_fn=None):
    ob = C.cylinder(name, r=r, depth=depth, segments=seg, loc=loc, rot=rot, mat=m, bevel=bevel)
    return paint(ob, color, fn=fn, face_fn=face_fn)


def text(name, s, size, depth, m, loc=(0, 0, 0), rot=(0, 0, 0), color="#ffffff", fn=None, face_fn=None,
         font=None):
    ob = C.curve_text(name, s, size=size, depth=depth, mat=m, loc=loc, rot=rot)
    return paint(ob, color, fn=fn, face_fn=face_fn)


def bold_font():
    """A heavy font if the system has one (DejaVu Sans Bold), else Blender's."""
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            try:
                return bpy.data.fonts.load(p, check_existing=True)
            except Exception:
                pass
    return None


def text_bold(name, s, size, depth, m, loc=(0, 0, 0), rot=(0, 0, 0), color="#ffffff", fn=None, face_fn=None,
              bevel=None, extrude_scale=1.0, res=3):
    """Like core.curve_text but with a bold font and chunkier bevel."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = s
    f = bold_font()
    if f is not None:
        cu.font = f
    cu.size = size
    cu.extrude = depth
    cu.bevel_depth = depth * 0.35 if bevel is None else bevel
    cu.bevel_resolution = 1
    cu.resolution_u = res
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    C.link(ob)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    C.activate(ob)
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.view_layer.objects.active
    if m:
        C.set_materials(ob, [m])
    return paint(ob, color, fn=fn, face_fn=face_fn)


# ---------------------------------------------------------------------------
# Finish / export / stats
# ---------------------------------------------------------------------------


def tri_count(ob):
    me = ob.data
    lt = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return int(np.sum(lt - 2))


def finish(name, parts, out_dir, empties=(), join=True):
    """Bake, unify colours, join, parent to a root empty named `name`, export."""
    parts = [p for p in parts if p is not None]
    for o in parts:
        if o.modifiers:
            C.apply_modifiers(o)
        C.apply_transform(o)
        corner_colors_from_points(o)
    if join and len(parts) > 1:
        ob = C.join(parts, name + "_mesh")
    else:
        ob = parts[0]
        ob.name = name + "_mesh"
        ob.data.name = name + "_mesh"
    # merge material slots with the same material
    _dedupe_slots(ob)
    root = C.empty(name, (0, 0, 0))
    ob.parent = root
    for e in empties:
        e.parent = root
    path = os.path.join(out_dir, name + ".glb")
    C.export_glb(path, [root])
    V = C.vertex_array(ob)
    stats = dict(name=name, tris=tri_count(ob), lo=V.min(axis=0).round(3).tolist(), hi=V.max(axis=0).round(3).tolist(),
                 mats=[m.name for m in ob.data.materials])
    return root, ob, stats


def _dedupe_slots(ob):
    me = ob.data
    names = [m.name if m else None for m in me.materials]
    uniq = []
    for n in names:
        if n not in uniq:
            uniq.append(n)
    if len(uniq) == len(names):
        return
    remap = np.array([uniq.index(n) for n in names], dtype=np.int32)
    mi = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("material_index", mi)
    mats = [bpy.data.materials.get(n) for n in uniq]
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", remap[mi])
