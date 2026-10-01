"""Baía dos Coqueiros — track layout (pure numpy, no Blender needed).

The centreline is a closed centripetal Catmull-Rom spline through control
points (x, y, z, width, bank_deg) in Blender axes (Z up). Everything else —
road mesh, terrain carving, AI line, checkpoints, prop placement — is derived
from the densely sampled frames produced here, so tweaking a control point
regenerates a consistent track.

Tour (counter-clockwise from above, start line facing +X):
  beach promenade straight -> sweeping left T1 up the headland -> wooden
  bridge over the river mouth -> climbing jungle esses -> left hairpin ->
  tunnel through the cliff -> downhill esses -> boost pad + big jump over the
  waterfall pool -> banked final left onto the beach.
"""

import json
import math

import numpy as np

# (x, y, z, width, bank_deg)  bank > 0 = raised outer (right) edge for left turns
CONTROL = [
    (-150, 0, 2.0, 20, 0),
    (-60, 0, 2.0, 20, 0),
    (18, 2, 2.0, 18, 0),
    (70, 14, 2.6, 18, 8),        # T1 sweeping left up the headland
    (100, 45, 4.0, 17, 10),
    (106, 86, 5.5, 16, 0),       # chicane right...
    (92, 122, 6.5, 16, -6),
    (108, 154, 7.0, 16, 4),      # ...and left
    (140, 176, 7.5, 15, 0),
    (152, 214, 8.0, 15, 0),      # bridge over the river mouth
    (148, 256, 11.0, 15, 4),
    (128, 298, 15.0, 15, 10),    # hairpin
    (94, 318, 17.0, 15, 14),
    (62, 300, 18.5, 15, 10),
    (46, 262, 20.0, 15, 0),
    (6, 238, 21.5, 14, -4),
    (-44, 246, 22.0, 13, 0),     # tunnel through the cliff
    (-90, 270, 21.5, 14, 0),
    (-126, 256, 20.0, 15, 8),
    (-138, 218, 17.5, 16, 0),
    (-152, 180, 14.0, 16, 0),    # boost pad + ramp -> jump
    (-176, 140, 7.5, 16, 0),
    (-212, 100, 4.2, 18, 10),    # banked final left
    (-234, 52, 3.0, 18, 12),
    (-216, 12, 2.2, 19, 6),
    (-188, -1, 2.0, 20, 0),
]

WATER_LEVEL = 0.0
SAMPLE_STEP = 1.0   # metres between road samples


def catmull_rom_closed(P, n_per_seg=64, alpha=0.5):
    """Centripetal Catmull-Rom through closed control points P (N, D)."""
    P = np.asarray(P, float)
    N = len(P)
    out = []
    for i in range(N):
        p0, p1, p2, p3 = P[(i - 1) % N], P[i], P[(i + 1) % N], P[(i + 2) % N]

        def tj(ti, pa, pb):
            return ti + max(np.linalg.norm(pb[:3] - pa[:3]), 1e-6) ** alpha
        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        for k in range(n_per_seg):
            t = t1 + (t2 - t1) * k / n_per_seg
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    return np.array(out)


def resample(curve, step):
    seg = np.linalg.norm(np.diff(curve[:, :3], axis=0, append=curve[:1, :3]), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    total = s[-1]
    n = int(total // step)
    targets = np.linspace(0, total, n, endpoint=False)
    closed = np.vstack([curve, curve[:1]])
    out = np.empty((n, curve.shape[1]))
    for d in range(curve.shape[1]):
        out[:, d] = np.interp(targets, s, closed[:, d])
    return out, total


def smooth_closed(a, iters=3):
    a = a.copy()
    for _ in range(iters):
        a = 0.25 * np.roll(a, 1, axis=0) + 0.5 * a + 0.25 * np.roll(a, -1, axis=0)
    return a


class Layout:
    def __init__(self, control=CONTROL, step=SAMPLE_STEP):
        dense = catmull_rom_closed(np.array(control, float), 80)
        samp, self.length = resample(dense, step)
        samp[:, :2] = smooth_closed(samp[:, :2], 40)
        samp[:, 2] = smooth_closed(samp[:, 2], 20)
        samp[:, 3] = smooth_closed(samp[:, 3], 30)
        samp[:, 4] = smooth_closed(samp[:, 4], 30)
        self.pos = samp[:, :3]
        self.width = samp[:, 3]
        self.bank = samp[:, 4]
        self.n = len(self.pos)
        self.s = np.arange(self.n) * (self.length / self.n)
        fwd = np.roll(self.pos, -1, axis=0) - np.roll(self.pos, 1, axis=0)
        self.fwd = fwd / np.linalg.norm(fwd, axis=1, keepdims=True)
        up0 = np.array([0, 0, 1.0])
        right = np.cross(self.fwd, up0)
        right /= np.linalg.norm(right, axis=1, keepdims=True)
        # bank: rotate right/up around forward (positive bank lifts the right edge)
        b = np.radians(self.bank)[:, None]
        up = np.cross(right, self.fwd)
        self.right = right * np.cos(b) + up * np.sin(b)
        self.up = np.cross(self.right, self.fwd)
        # signed curvature in the ground plane (+ = turning left)
        f2 = self.fwd[:, :2] / np.linalg.norm(self.fwd[:, :2], axis=1, keepdims=True)
        ang = np.arctan2(f2[:, 1], f2[:, 0])
        dang = np.angle(np.exp(1j * (np.roll(ang, -1) - np.roll(ang, 1))))
        self.curv = smooth_closed(dang / (2 * self.length / self.n), 6)
        self.tags = self._tags()

    # -- feature ranges, in metres along the track --------------------------
    def near_control(self, i):
        c = np.array(CONTROL[i][:3], float)
        return int(np.argmin(np.linalg.norm(self.pos - c, axis=1)))

    def _tags(self):
        n = self.n
        tags = [set() for _ in range(n)]
        self.features = {}
        m = self.length / n

        def span(name, a, b):
            ia, ib = int(a / m) % n, int(b / m) % n
            idx = range(ia, ib) if ia <= ib else list(range(ia, n)) + list(range(0, ib))
            for i in idx:
                tags[i].add(name)
            self.features.setdefault(name, []).append((a, b))

        s = lambda i: self.near_control(i) * m  # noqa: E731
        span("bridge", s(8) + 14, s(10) - 16)
        span("tunnel", s(16) - 34, s(16) + 30)
        # jump: ramp ends at ramp_s+3, gap until landing
        self.ramp_s = s(20) + 1.0
        span("gap", self.ramp_s + 3.2, self.ramp_s + 21.0)
        span("start", 0, 1)
        return tags

    def index_at(self, s):
        return int(round(s / (self.length / self.n))) % self.n

    def frame(self, s):
        i = self.index_at(s)
        return self.pos[i], self.fwd[i], self.right[i], self.up[i], self.width[i]

    def start_s(self):
        # start line on the promenade, 30 m past control point 0
        return (self.near_control(1) * (self.length / self.n)) - 25.0


def to_godot(v):
    """Blender (x, y, z) -> Godot (x, z, -y)."""
    v = np.asarray(v, float)
    return [float(v[0]), float(v[2]), float(-v[1])]


if __name__ == "__main__":
    import sys
    L = Layout()
    print("length %.1f m, %d samples" % (L.length, L.n))
    print("max |curvature| %.4f (radius %.1f m)" % (np.abs(L.curv).max(), 1 / np.abs(L.curv).max()))
    print("features", {k: [(round(a), round(b)) for a, b in v] for k, v in L.features.items()})
    if len(sys.argv) > 1:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(14, 6))
        sc = ax[0].scatter(L.pos[:, 0], L.pos[:, 1], c=L.pos[:, 2], s=2, cmap="terrain")
        for i, c in enumerate(CONTROL):
            ax[0].annotate(str(i), c[:2], fontsize=8)
        for side in (-1, 1):
            e = L.pos + L.right * (L.width[:, None] / 2) * side
            ax[0].plot(e[:, 0], e[:, 1], "k-", lw=0.5)
        for name, col in (("bridge", "brown"), ("tunnel", "black"), ("gap", "red")):
            idx = [i for i in range(L.n) if name in L.tags[i]]
            ax[0].scatter(L.pos[idx, 0], L.pos[idx, 1], s=6, c=col)
        i0 = L.index_at(L.start_s())
        ax[0].plot(*L.pos[i0, :2], "g*", ms=14)
        ax[0].set_aspect("equal")
        plt.colorbar(sc, ax=ax[0])
        ax[1].plot(L.s, L.pos[:, 2], label="z")
        ax[1].plot(L.s, L.curv * 500, label="curv*500")
        ax[1].plot(L.s, L.bank, label="bank")
        ax[1].legend()
        plt.savefig(sys.argv[1], dpi=90)
