"""Rocks: faceted-soft boulders, stepping stone, layered cliffs and the stone arch."""

import math

import numpy as np

import props_lib as L
from props import prop
from tt import sdf as S

ROCK_TOP = "#cdb899"
ROCK_SIDE = "#8e7d6c"
ROCK_LOW = "#5a4e44"
SAND = "#dcc393"
MOSS = "#6c9a34"


def rock_color(node, top=ROCK_TOP, side=ROCK_SIDE, low=ROCK_LOW, sand=SAND, moss=None, seed=0, scale=1.0,
               sand_h=0.18, bands=None, grass_top=None):
    """Normal-based rock shading: light sky-facing facets, darker undersides,
    sandy foot, optional moss / grass on top and strata bands."""
    def fn(p):
        n = S.gradient(node, p, eps=0.02 * scale)
        nz = n[:, 2]
        c = np.where(nz[:, None] > 0,
                     L.lerp(side, top, np.clip(nz * 1.3, 0, 1)),
                     L.lerp(side, low, np.clip(-nz * 1.4, 0, 1)))
        if bands is not None:
            zc, cols, soft = bands
            idx = np.clip(np.searchsorted(zc, p[:, 2]) - 1, 0, len(cols) - 1)
            bc = np.array([L.col(cols[i % len(cols)]) for i in range(len(zc))])[idx]
            c = c * 0.4 + bc * (c / np.maximum(L.col(side)[None, :], 1e-3)) * 0.6
            if len(zc) > 2:
                dz = np.min(np.abs(p[:, 2:3] - np.asarray(zc)[None, 1:-1]), axis=1)
                c = c * (1 - 0.32 * (1 - L.smooth(0.0, soft, dz)))[:, None]
        nse = S.fbm(p, 0.9 / scale, 3, seed)
        c = c * (1 + 0.12 * nse)[:, None]
        if sand is not None:
            w = 1 - L.smooth(sand_h * 0.3, sand_h, p[:, 2])
            c = c * (1 - w[:, None]) + L.col(sand)[None, :] * w[:, None]
        if moss is not None:
            m = L.smooth(0.55, 0.85, nz) * L.smooth(-0.1, 0.3, S.fbm(p, 0.7 / scale, 2, seed + 3))
            c = c * (1 - m[:, None]) + L.col(moss)[None, :] * m[:, None]
        if grass_top is not None:
            zt, gcol = grass_top
            g = L.smooth(0.6, 0.82, nz) * L.smooth(zt * 0.55, zt * 0.8, p[:, 2])
            c = c * (1 - g[:, None]) + (L.col(gcol)[None, :] * (1 + 0.15 * nse)[:, None]) * g[:, None]
        return c
    return fn


def boulder(name, center, radii, seed, nplanes=16, k=0.07, faces=2200, voxel=0.03, moss=None):
    node = L.facet_rock(center, radii, nplanes=nplanes, seed=seed, k=k, noise=0.02)
    node = S.Intersect(node, S.Plane((0, 0, -1), 0.0))
    r = max(radii)
    lo = np.array(center) - np.array(radii) * 1.3
    hi = np.array(center) + np.array(radii) * 1.3
    lo[2] = -0.05
    return L.sdf_part(name, node.paint(rock_color(node, moss=moss, seed=seed, scale=r)), lo, hi, voxel, faces,
                      L.mat("Rock"))


@prop("rock_a")
def rock_a():
    """Rounded faceted boulder ~2.3 m."""
    return [boulder("rock", (0, 0, 0.55), (1.15, 0.95, 0.85), seed=3, faces=2400, moss=MOSS)], []


@prop("rock_b")
def rock_b():
    """Cluster of three fused boulders, ~3.5 m."""
    a = L.facet_rock((0.3, 0, 0.8), (1.25, 1.0, 1.05), nplanes=16, seed=7, k=0.07, noise=0.02)
    b = L.facet_rock((-0.95, 0.25, 0.45), (0.8, 0.7, 0.6), nplanes=14, seed=8, k=0.07, noise=0.02)
    c = L.facet_rock((0.9, 0.75, 0.3), (0.55, 0.5, 0.4), nplanes=12, seed=9, k=0.07, noise=0.02)
    node = S.Intersect(S.Union(a, b, c, k=0.12), S.Plane((0, 0, -1), 0.0))
    ob = L.sdf_part("rock", node.paint(rock_color(node, moss=MOSS, seed=7, scale=1.2)), (-2.2, -1.6, -0.05),
                    (2.0, 1.8, 2.2), 0.035, 3800, L.mat("Rock"))
    return [ob], []


@prop("rock_c")
def rock_c():
    """Small upright rock ~1.3 m."""
    return [boulder("rock", (0, 0, 0.62), (0.62, 0.55, 0.75), seed=12, nplanes=14, faces=1600, voxel=0.022)], []


@prop("rock_flat", views=((-35, 25), (35, 25), (180, 30), (90, 60)))
def rock_flat():
    """Flat stepping stone, ~1.7 x 1.3 m, 0.3 m tall, walkable top."""
    node = L.facet_rock((0, 0, 0.02), (0.85, 0.65, 0.34), nplanes=13, seed=4, k=0.1, noise=0.015)
    node = S.Intersect(node, S.Plane((0, 0, 1), 0.3), k=0.08)
    node = S.Intersect(node, S.Plane((0, 0, -1), 0.0))
    ob = L.sdf_part("rock", node.paint(rock_color(node, seed=4, scale=0.8, sand_h=0.08)), (-1.1, -0.9, -0.05),
                    (1.1, 0.9, 0.4), 0.02, 1400, L.mat("Rock"))
    return [ob], []


# ---------------------------------------------------------------------------
# Layered formations
# ---------------------------------------------------------------------------


def _slab(center, radii, z0, z1, seed, nplanes=9, k=0.12, jit=0.14, round_z=0.25):
    """One stratum: faceted prism between z0 and z1 with rounded edges."""
    rng = np.random.default_rng(seed)
    ang = np.arange(nplanes) * math.tau / nplanes + rng.uniform(-0.25, 0.25, nplanes) + rng.uniform(0, 1)
    ns = np.stack([np.cos(ang), np.sin(ang)], axis=1)
    offs = 1.0 - rng.uniform(0, jit, nplanes)
    c = np.asarray(center, float)
    rad = np.asarray(radii, float)

    def fn(p):
        q = (p[:, :2] - c) / rad
        d = None
        for n, o in zip(ns, offs):
            di = q @ n - o
            if d is None:
                d = di
            else:
                h = np.clip(0.5 - 0.5 * (d - di) / k, 0, 1)
                d = d * (1 - h) + di * h + k * h * (1 - h)
        d = d * rad.min()
        dz = np.maximum(z0 - p[:, 2], p[:, 2] - z1)
        r = round_z
        qa, qb = np.maximum(d + r, 0), np.maximum(dz + r, 0)
        return np.sqrt(qa * qa + qb * qb) + np.minimum(np.maximum(d, dz) + r, 0) - r
    return S.Field(fn)


def strata(center, radii, height, n_layers, seed, taper=0.12, wobble=0.1, k=0.1, nplanes=9, skew=(0, 0)):
    rng = np.random.default_rng(seed)
    zs = np.cumsum(np.r_[0, rng.uniform(0.7, 1.3, n_layers)])
    zs = zs / zs[-1] * height
    layers = []
    for i in range(n_layers):
        t = i / max(1, n_layers - 1)
        s = 1 - taper * t
        cx = center[0] + rng.uniform(-wobble, wobble) * radii[0] + skew[0] * t
        cy = center[1] + rng.uniform(-wobble, wobble) * radii[1] + skew[1] * t
        rr = (radii[0] * s * rng.uniform(0.94, 1.04), radii[1] * s * rng.uniform(0.9, 1.05))
        layers.append(_slab((cx, cy), rr, zs[i] - (0.3 if i == 0 else 0.02), zs[i + 1], seed * 13 + i,
                            nplanes=nplanes))
    return S.Union(*layers, k=k), zs


BANDS = ["#b99a78", "#cfae84", "#a8866a", "#d8bf94", "#b48f6c", "#c9a57c", "#a98a70"]


def formation(name, node, zs, lo, hi, voxel, faces, seed, grass=True):
    node = node.displace(lambda p: 0.18 * S.fbm(p, 0.25, 3, seed) + 0.05 * np.sin(p[:, 2] * 6.0))
    node = S.Intersect(node, S.Plane((0, 0, -1), 0.0))
    top = float(zs[-1])
    colf = rock_color(node, seed=seed, scale=4.0, sand_h=0.5, bands=(zs, BANDS, 0.18),
                      grass_top=(top, "#5a9a2e") if grass else None, moss=None)
    return L.sdf_part(name, node.paint(colf), lo, hi, voxel, faces, L.mat("Rock"))


@prop("cliff_a")
def cliff_a():
    """Track wall formation ~16 m wide (X), ~7 m deep, ~11 m tall, stepped strata."""
    main, zs = strata((0, 0), (8.0, 3.4), 10.8, 6, seed=2, taper=0.18, wobble=0.05, skew=(0.6, -0.3))
    side, _ = strata((-5.2, 1.4), (3.2, 2.2), 6.2, 3, seed=5, taper=0.2)
    node = S.Union(main, side, k=0.5)
    return [formation("cliff", node, zs, (-10, -5.5, -0.1), (10, 5.5, 11.5), 0.11, 14000, seed=2)], []


@prop("cliff_b")
def cliff_b():
    """Taller formation ~19 m wide, ~14 m tall, with a lower shoulder and a pillar."""
    main, zs = strata((0.8, 0), (7.4, 3.2), 14.0, 8, seed=9, taper=0.22, wobble=0.06, skew=(-0.8, 0.4))
    shoulder, _ = strata((-6.0, 0.6), (3.6, 2.6), 5.0, 3, seed=11, taper=0.1)
    pillar, _ = strata((7.2, 1.8), (1.8, 1.6), 8.5, 5, seed=13, taper=0.15)
    node = S.Union(main, shoulder, pillar, k=0.6)
    return [formation("cliff", node, zs, (-10.5, -5, -0.1), (10.5, 5.5, 14.8), 0.12, 16000, seed=9)], []


@prop("rock_arch", views=((-30, 12), (30, 12), (180, 14), (0, 3)))
def rock_arch():
    """Natural stone arch. Clear opening 22 m wide (x = -11..11) and ~10 m tall
    at the centre, road along Y through it. Origin at the arch base centre."""
    mass, zs = strata((0, 0), (17.5, 4.2), 15.0, 7, seed=21, taper=0.1, wobble=0.03, nplanes=11)
    feet = S.Union(
        _slab((-14.2, 0.2), (4.6, 5.0), -0.3, 3.0, 31, nplanes=9),
        _slab((14.0, -0.3), (4.8, 5.2), -0.3, 3.4, 32, nplanes=9), k=0.6)
    body = S.Union(mass, feet, k=0.8)

    def opening(p):
        x, z = p[:, 0], p[:, 2]
        e = np.sqrt((x / 11.0) ** 2 + (np.maximum(z - 4.5, 0) / 5.5) ** 2) - 1.0
        return e * 5.5
    hole = S.Field(opening)
    saddle = S.Field(lambda p: p[:, 2] - (15.4 - 3.2 * np.exp(-(p[:, 0] / 7.0) ** 2)))
    node = S.Subtract(S.Intersect(body, saddle, k=0.8), hole, k=0.9)
    ob = formation("arch", node, zs, (-20, -6.5, -0.1), (20, 6.5, 16.5), 0.14, 20000, seed=21)
    return [ob], []
