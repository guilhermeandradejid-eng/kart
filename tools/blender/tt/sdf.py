"""Signed-distance-field modelling for Turbo Turma.

Organic, "sculpted toy" shapes (character bodies, kart shells, seats, rocks)
are described as a tree of SDF nodes, evaluated with numpy on a voxel grid
and polygonised with marching cubes. The same tree is evaluated again on the
final vertices to get vertex colours, material ids and analytic normals, so a
decimated mesh still shades as smoothly as the field it came from.

Conventions: metres, Blender axes (Z up, +Y forward, +X right).

    body = Ellipsoid((0.3, 0.25, 0.35), color="#e8742c")
    head = Sphere(0.3).at(0, 0.1, 0.6)
    shape = Union(body, head, k=0.08)
    mesh = build_mesh("Guara", shape, voxel=0.008)
"""

import math

import numpy as np

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def hexrgb(h):
    """'#rrggbb' -> linear rgb tuple (glTF vertex colours are linear)."""
    if not isinstance(h, str):
        return tuple(float(x) for x in h)
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(float(x) for x in srgb_to_linear(srgb))


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------------------
# Rotation helpers
# ---------------------------------------------------------------------------


def rot_matrix(rx=0.0, ry=0.0, rz=0.0):
    """XYZ euler (degrees) -> 3x3, same convention as Blender's 'XYZ'."""
    ax, ay, az = (math.radians(a) for a in (rx, ry, rz))
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    X = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Z @ Y @ X


def look_rotation(forward, up=(0, 0, 1)):
    """3x3 whose local +Z points along `forward` (used to orient capsules etc.)."""
    f = np.asarray(forward, float)
    f = f / (np.linalg.norm(f) + 1e-12)
    u = np.asarray(up, float)
    if abs(np.dot(f, u)) > 0.99:
        u = np.array([0.0, 1.0, 0.0]) if abs(f[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x = np.cross(u, f)
    x /= np.linalg.norm(x)
    y = np.cross(f, x)
    return np.stack([x, y, f], axis=1)


# ---------------------------------------------------------------------------
# Value noise (for rocks, bark, fur clumps) - deterministic, vectorised
# ---------------------------------------------------------------------------


def _hash3(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float64) / float(0xFFFFFF)


def value_noise(p, freq=1.0, seed=0):
    """Smooth 3D value noise in [-1, 1]."""
    q = p * freq
    i = np.floor(q).astype(np.int64)
    f = q - i
    u = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = ((u[:, 0] if dx else 1 - u[:, 0])
                     * (u[:, 1] if dy else 1 - u[:, 1])
                     * (u[:, 2] if dz else 1 - u[:, 2]))
                out = out + w * _hash3(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out * 2.0 - 1.0


def fbm(p, freq=1.0, octaves=4, seed=0, gain=0.5, lacunarity=2.0):
    total = 0.0
    amp = 1.0
    norm = 0.0
    for o in range(octaves):
        total = total + amp * value_noise(p, freq * (lacunarity ** o), seed + o * 17)
        norm += amp
        amp *= gain
    return total / norm


# ---------------------------------------------------------------------------
# Node base
# ---------------------------------------------------------------------------


class Node:
    """An SDF node. `dist(p)` -> (N,), `attrs(p)` -> (d, mat(N,), col(N,3))."""

    mat = 0
    color = (0.8, 0.8, 0.8)

    # -- transforms (return new wrapper nodes) --
    def at(self, x=0.0, y=0.0, z=0.0):
        return Transform(self, offset=(x, y, z))

    def rot(self, rx=0.0, ry=0.0, rz=0.0):
        return Transform(self, rotation=rot_matrix(rx, ry, rz))

    def scaled(self, s):
        return Transform(self, scale=s)

    def mirror_x(self):
        return MirrorX(self)

    def stretch(self, sx=1.0, sy=1.0, sz=1.0):
        return Stretch(self, sx, sy, sz)

    def inflate(self, r):
        return Offset(self, r)

    def shell(self, thickness):
        return Shell(self, thickness)

    def displace(self, fn):
        return Displace(self, fn)

    def paint(self, color=None, mat=None):
        """Recolour / re-material a whole subtree."""
        return Paint(self, color, mat)

    # -- evaluation --
    def dist(self, p):
        raise NotImplementedError

    def attrs(self, p):
        d = self.dist(p)
        col = np.empty((len(p), 3))
        c = self.color
        if callable(c):
            col[:] = c(p)
        else:
            col[:] = c
        return d, np.full(len(p), self.mat, dtype=np.int32), col


class Primitive(Node):
    def __init__(self, color="#cccccc", mat=0):
        self.color = color if callable(color) else hexrgb(color)
        self.mat = mat


# ---------------------------------------------------------------------------
# Primitives (all centred at the origin in local space)
# ---------------------------------------------------------------------------


class Sphere(Primitive):
    def __init__(self, r, **kw):
        super().__init__(**kw)
        self.r = r

    def dist(self, p):
        return np.linalg.norm(p, axis=1) - self.r


class Ellipsoid(Primitive):
    """Approximate (Quilez) ellipsoid distance; exact enough for meshing."""

    def __init__(self, radii, **kw):
        super().__init__(**kw)
        self.r = np.asarray(radii, float)

    def dist(self, p):
        k0 = np.linalg.norm(p / self.r, axis=1)
        k1 = np.linalg.norm(p / (self.r * self.r), axis=1)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


class Box(Primitive):
    """Rounded box. `half` = half extents INCLUDING the rounding."""

    def __init__(self, half, round=0.0, **kw):
        super().__init__(**kw)
        self.b = np.asarray(half, float) - round
        self.round = round

    def dist(self, p):
        q = np.abs(p) - self.b
        outside = np.linalg.norm(np.maximum(q, 0.0), axis=1)
        inside = np.minimum(np.max(q, axis=1), 0.0)
        return outside + inside - self.round


class Capsule(Primitive):
    def __init__(self, a, b, r, **kw):
        super().__init__(**kw)
        self.a = np.asarray(a, float)
        self.b = np.asarray(b, float)
        self.r = r

    def dist(self, p):
        pa = p - self.a
        ba = self.b - self.a
        h = np.clip((pa @ ba) / (ba @ ba), 0.0, 1.0)
        return np.linalg.norm(pa - h[:, None] * ba, axis=1) - self.r


class RoundCone(Primitive):
    """Tapered capsule from a (radius ra) to b (radius rb). Great for limbs."""

    def __init__(self, a, b, ra, rb, **kw):
        super().__init__(**kw)
        self.a = np.asarray(a, float)
        self.b = np.asarray(b, float)
        self.ra = ra
        self.rb = rb

    def dist(self, p):
        a, b, r1, r2 = self.a, self.b, self.ra, self.rb
        ba = b - a
        l2 = ba @ ba
        rr = r1 - r2
        a2 = l2 - rr * rr
        il2 = 1.0 / l2
        pa = p - a
        y = pa @ ba
        z = y - l2
        xv = pa * l2 - y[:, None] * ba
        x2 = np.sum(xv * xv, axis=1)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d = np.where(
            np.sign(z) * a2 * z2 > k,
            np.sqrt(x2 + z2) * il2 - r2,
            np.where(np.sign(y) * a2 * y2 < k,
                     np.sqrt(x2 + y2) * il2 - r1,
                     (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1))
        return d


class Cylinder(Primitive):
    """Capped cylinder along local Z with optional edge rounding."""

    def __init__(self, r, half_h, round=0.0, **kw):
        super().__init__(**kw)
        self.r = r - round
        self.h = half_h - round
        self.round = round

    def dist(self, p):
        dxy = np.linalg.norm(p[:, :2], axis=1) - self.r
        dz = np.abs(p[:, 2]) - self.h
        outside = np.sqrt(np.maximum(dxy, 0) ** 2 + np.maximum(dz, 0) ** 2)
        inside = np.minimum(np.maximum(dxy, dz), 0.0)
        return outside + inside - self.round


class Torus(Primitive):
    """Torus in the local XY plane (axis Z)."""

    def __init__(self, R, r, **kw):
        super().__init__(**kw)
        self.R = R
        self.r = r

    def dist(self, p):
        q = np.linalg.norm(p[:, :2], axis=1) - self.R
        return np.sqrt(q * q + p[:, 2] ** 2) - self.r


class Plane(Primitive):
    """Half space: negative below the plane n.p = h."""

    def __init__(self, normal=(0, 0, 1), h=0.0, **kw):
        super().__init__(**kw)
        n = np.asarray(normal, float)
        self.n = n / np.linalg.norm(n)
        self.h = h

    def dist(self, p):
        return p @ self.n - self.h


class Tube(Primitive):
    """Chain of round cones through `points` with per-point `radii`.

    Joined with a small smooth-union so the chain reads as one soft limb
    (tails, ears, fingers, fronds, hoses)."""

    def __init__(self, points, radii, k=0.0, **kw):
        super().__init__(**kw)
        self.pts = [np.asarray(q, float) for q in points]
        if np.isscalar(radii):
            radii = [radii] * len(points)
        self.radii = list(radii)
        self.k = k

    def dist(self, p):
        d = None
        for i in range(len(self.pts) - 1):
            a, b = self.pts[i], self.pts[i + 1]
            ra, rb = self.radii[i], self.radii[i + 1]
            if np.linalg.norm(b - a) < 1e-6:
                continue
            if abs(ra - rb) > np.linalg.norm(b - a) * 0.99:
                di = Sphere(max(ra, rb)).dist(p - (a if ra > rb else b))
            else:
                di = RoundCone(a, b, ra, rb).dist(p)
            if d is None:
                d = di
            elif self.k > 0:
                d, _ = _smin(d, di, self.k)
            else:
                d = np.minimum(d, di)
        return d


def box2d(px, py, hx, hy, r=0.0):
    """2D rounded box distance (half extents include rounding)."""
    qx = np.abs(px) - (hx - r)
    qy = np.abs(py) - (hy - r)
    return (np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2)
            + np.minimum(np.maximum(qx, qy), 0.0) - r)


def superellipse2d(px, py, a, b, n=4.0):
    """Approximate distance to a superellipse |x/a|^n + |y/b|^n = 1."""
    k = (np.abs(px / a) ** n + np.abs(py / b) ** n) ** (1.0 / n)
    return (k - 1.0) * np.minimum(a, b)


class Revolved(Primitive):
    """Solid of revolution around local Z. `fn2d(radial, axial)` is a 2D SDF
    in the (distance-from-axis, z) half plane. Tires, rims, pots, domes."""

    def __init__(self, fn2d, **kw):
        super().__init__(**kw)
        self.fn2d = fn2d

    def dist(self, p):
        r = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        return self.fn2d(r, p[:, 2])


class PolarRepeat(Node):
    """Repeat `child` `count` times around local Z (child modelled on +X)."""

    def __init__(self, child, count, phase=0.0):
        self.child = child
        self.count = count
        self.phase = math.radians(phase)

    def _p(self, p):
        a = np.arctan2(p[:, 1], p[:, 0]) - self.phase
        sector = 2 * math.pi / self.count
        a = np.mod(a + sector / 2, sector) - sector / 2
        r = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        q = np.empty_like(p)
        q[:, 0] = r * np.cos(a)
        q[:, 1] = r * np.sin(a)
        q[:, 2] = p[:, 2]
        return q

    def dist(self, p):
        return self.child.dist(self._p(p))

    def attrs(self, p):
        return self.child.attrs(self._p(p))


class Field(Primitive):
    """Arbitrary distance function fn(p) -> (N,)."""

    def __init__(self, fn, **kw):
        super().__init__(**kw)
        self.fn = fn

    def dist(self, p):
        return self.fn(p)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


def _smin(a, b, k):
    """Polynomial smooth min. Returns (d, h) where h=1 means fully `a`."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1.0 - h), h


class Transform(Node):
    def __init__(self, child, offset=(0, 0, 0), rotation=None, scale=1.0):
        self.child = child
        self.offset = np.asarray(offset, float)
        self.R = np.eye(3) if rotation is None else np.asarray(rotation, float)
        self.s = float(scale)

    def _local(self, p):
        # p_local = R^T (p - offset) / s
        return ((p - self.offset) @ self.R) / self.s

    def dist(self, p):
        return self.child.dist(self._local(p)) * self.s

    def attrs(self, p):
        d, m, c = self.child.attrs(self._local(p))
        return d * self.s, m, c

    # chaining keeps a single wrapper
    def at(self, x=0.0, y=0.0, z=0.0):
        return Transform(self.child, self.offset + np.array([x, y, z]), self.R, self.s)

    def rot(self, rx=0.0, ry=0.0, rz=0.0):
        R = rot_matrix(rx, ry, rz)
        return Transform(self.child, R @ self.offset, R @ self.R, self.s)


class Stretch(Node):
    """Non-uniform scale about the local origin (approximate distance,
    conservative: multiplied by the smallest factor). Flattens ears, scarves."""

    def __init__(self, child, sx=1.0, sy=1.0, sz=1.0):
        self.child = child
        self.s = np.array([sx, sy, sz], float)
        self.k = float(self.s.min())

    def dist(self, p):
        return self.child.dist(p / self.s) * self.k

    def attrs(self, p):
        d, m, c = self.child.attrs(p / self.s)
        return d * self.k, m, c


class MirrorX(Node):
    """Symmetric about the YZ plane (model one side at +X)."""

    def __init__(self, child):
        self.child = child

    def _m(self, p):
        q = p.copy()
        q[:, 0] = np.abs(q[:, 0])
        return q

    def dist(self, p):
        return self.child.dist(self._m(p))

    def attrs(self, p):
        return self.child.attrs(self._m(p))


class Offset(Node):
    def __init__(self, child, r):
        self.child = child
        self.r = r

    def dist(self, p):
        return self.child.dist(p) - self.r

    def attrs(self, p):
        d, m, c = self.child.attrs(p)
        return d - self.r, m, c


class Shell(Node):
    def __init__(self, child, t):
        self.child = child
        self.t = t

    def dist(self, p):
        return np.abs(self.child.dist(p)) - self.t

    def attrs(self, p):
        d, m, c = self.child.attrs(p)
        return np.abs(d) - self.t, m, c


class Displace(Node):
    def __init__(self, child, fn):
        self.child = child
        self.fn = fn

    def dist(self, p):
        return self.child.dist(p) + self.fn(p)

    def attrs(self, p):
        d, m, c = self.child.attrs(p)
        return d + self.fn(p), m, c


class Paint(Node):
    def __init__(self, child, color=None, mat=None):
        self.child = child
        self.color = None if color is None else (color if callable(color) else hexrgb(color))
        self.pmat = mat

    def dist(self, p):
        return self.child.dist(p)

    def attrs(self, p):
        d, m, c = self.child.attrs(p)
        if self.color is not None:
            if callable(self.color):
                c = self.color(p)
            else:
                c = np.broadcast_to(np.asarray(self.color), c.shape).copy()
        if self.pmat is not None:
            m = np.full_like(m, self.pmat)
        return d, m, c


class Union(Node):
    """(Smooth) union. Colours blend across the fillet so seams look painted.

    `color_k` lets the colour transition be sharper (smaller) or softer than
    the geometric fillet `k`."""

    def __init__(self, *children, k=0.0, color_k=None):
        self.children = [c for c in children if c is not None]
        self.k = k
        self.color_k = color_k

    def dist(self, p):
        d = self.children[0].dist(p)
        for c in self.children[1:]:
            dc = c.dist(p)
            d = _smin(dc, d, self.k)[0] if self.k > 0 else np.minimum(d, dc)
        return d

    def attrs(self, p):
        d, m, col = self.children[0].attrs(p)
        for c in self.children[1:]:
            dc, mc, cc = c.attrs(p)
            if self.k > 0:
                ck = self.color_k if self.color_k else self.k
                nd, _ = _smin(dc, d, self.k)
                hc = np.clip(0.5 + 0.5 * (d - dc) / ck, 0.0, 1.0)
                col = col * (1 - hc[:, None]) + cc * hc[:, None]
                m = np.where(hc > 0.5, mc, m)
                d = nd
            else:
                sel = dc < d
                d = np.where(sel, dc, d)
                m = np.where(sel, mc, m)
                col = np.where(sel[:, None], cc, col)
        return d, m, col


class Subtract(Node):
    """a minus b. With `carve` the cut surface takes b's colour/material
    (mouths, nostrils, vents, sockets)."""

    def __init__(self, a, b, k=0.0, carve=False):
        self.a = a
        self.b = b
        self.k = k
        self.carve = carve

    def _op(self, da, db):
        if self.k > 0:
            h = np.clip(0.5 - 0.5 * (db + da) / self.k, 0.0, 1.0)
            return da * (1 - h) + (-db) * h + self.k * h * (1 - h), h
        sel = -db > da
        return np.where(sel, -db, da), sel.astype(float)

    def dist(self, p):
        return self._op(self.a.dist(p), self.b.dist(p))[0]

    def attrs(self, p):
        da, ma, ca = self.a.attrs(p)
        if not self.carve:
            db = self.b.dist(p)
            d, _ = self._op(da, db)
            return d, ma, ca
        db, mb, cb = self.b.attrs(p)
        d, h = self._op(da, db)
        sel = h > 0.5
        return d, np.where(sel, mb, ma), np.where(sel[:, None], cb, ca)


class Intersect(Node):
    def __init__(self, a, b, k=0.0):
        self.a = a
        self.b = b
        self.k = k

    def _op(self, da, db):
        if self.k > 0:
            h = np.clip(0.5 - 0.5 * (db - da) / self.k, 0.0, 1.0)
            return db * (1 - h) + da * h + self.k * h * (1 - h)
        return np.maximum(da, db)

    def dist(self, p):
        return self._op(self.a.dist(p), self.b.dist(p))

    def attrs(self, p):
        da, ma, ca = self.a.attrs(p)
        db = self.b.dist(p)
        return self._op(da, db), ma, ca


class ColorRegion(Node):
    """Paints `color`/`mat` where `region` (another SDF, in the same space) is
    inside, with a soft edge of width `soft`. Geometry comes from `child` only.
    Used for markings: dark socks, white muzzle, tail tip, stripes."""

    def __init__(self, child, region, color, soft=0.01, mat=None):
        self.child = child
        self.region = region
        self.color = hexrgb(color)
        self.soft = soft
        self.pmat = mat

    def dist(self, p):
        return self.child.dist(p)

    def attrs(self, p):
        d, m, c = self.child.attrs(p)
        rd = self.region.dist(p)
        w = 1.0 - _smoothstep(-self.soft, self.soft, rd)
        c = c * (1 - w[:, None]) + np.asarray(self.color)[None, :] * w[:, None]
        if self.pmat is not None:
            m = np.where(w > 0.5, self.pmat, m)
        return d, m, c


# ---------------------------------------------------------------------------
# Evaluation / meshing
# ---------------------------------------------------------------------------


def estimate_bounds(node, lo, hi, voxel):
    """Tighten a generous box to where the field is actually negative."""
    return np.asarray(lo, float), np.asarray(hi, float)


def sample_grid(node, lo, hi, voxel, chunk=2_000_000):
    lo = np.asarray(lo, float) - 2 * voxel
    hi = np.asarray(hi, float) + 2 * voxel
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    xs = lo[0] + np.arange(n[0]) * voxel
    ys = lo[1] + np.arange(n[1]) * voxel
    zs = lo[2] + np.arange(n[2]) * voxel
    vol = np.empty(n, dtype=np.float32)
    plane = n[1] * n[2]
    step = max(1, chunk // plane)
    Y, Z = np.meshgrid(ys, zs, indexing="ij")
    yz = np.stack([Y.ravel(), Z.ravel()], axis=1)
    for i0 in range(0, n[0], step):
        i1 = min(n[0], i0 + step)
        cnt = i1 - i0
        P = np.empty((cnt * plane, 3))
        P[:, 0] = np.repeat(xs[i0:i1], plane)
        P[:, 1:] = np.tile(yz, (cnt, 1))
        vol[i0:i1] = node.dist(P).reshape(cnt, n[1], n[2])
    return vol, lo


def polygonise(node, lo, hi, voxel):
    """Marching cubes -> (verts (V,3), faces (F,3)) with outward winding."""
    from skimage import measure

    vol, origin = sample_grid(node, lo, hi, voxel)
    if vol.min() > 0 or vol.max() < 0:
        raise ValueError("SDF has no surface inside the given bounds")
    verts, faces, _n, _v = measure.marching_cubes(vol, level=0.0, spacing=(voxel, voxel, voxel),
                                                  allow_degenerate=False)
    verts = verts + origin
    # make winding outward: signed volume must be positive
    v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    vol_sign = np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2)))
    if vol_sign < 0:
        faces = faces[:, ::-1]
    return verts, faces.astype(np.int64)


def gradient(node, p, eps=1e-4):
    """Central-difference normals of the field at points p."""
    g = np.empty_like(p)
    for i in range(3):
        e = np.zeros(3)
        e[i] = eps
        g[:, i] = node.dist(p + e) - node.dist(p - e)
    n = np.linalg.norm(g, axis=1, keepdims=True)
    return g / np.maximum(n, 1e-12)


def auto_bounds(node, guess_lo, guess_hi, voxel_coarse=0.02):
    """Shrink a generous bounding box to the occupied region (+margin)."""
    vol, origin = sample_grid(node, guess_lo, guess_hi, voxel_coarse)
    inside = np.argwhere(vol < voxel_coarse)
    if len(inside) == 0:
        raise ValueError("empty SDF")
    lo = origin + inside.min(axis=0) * voxel_coarse - voxel_coarse * 2
    hi = origin + inside.max(axis=0) * voxel_coarse + voxel_coarse * 2
    return lo, hi
