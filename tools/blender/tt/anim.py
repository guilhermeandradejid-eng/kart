"""Pose-to-pose animation authoring with the twelve principles baked in.

A Clip is a set of per-bone key tracks (so bones can be keyed on different
frames -> successive breaking of joints / overlapping action), each key with
its own easing (slow in / slow out, overshoot for snap), plus:

  * layers   - procedural additive motion (breathing, idle noise, shake)
  * follow   - follow-through: a chain inherits its driver's motion with a
               per-link delay and gain (tails, ears, scarf, mane)
  * ik       - hand/foot targets solved by Blender IK then baked to FK

Rotations are authored in ARMATURE axes (X right, Y forward, Z up) with
XYZ euler degrees: rx>0 tips an up-pointing bone backwards, rz>0 turns to
the character's left, ry>0 leans to the character's right. They are
converted to each bone's local frame at bake time, so authors never think
about bone rolls. Mirror rule for L/R: (rx, ry, rz) -> (rx, -ry, -rz).
"""

import math

import numpy as np

FPS = 30

# ---------------------------------------------------------------------------
# Easing
# ---------------------------------------------------------------------------


def _back(t, s=1.70158):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def _elastic(t):
    if t in (0.0, 1.0):
        return t
    return 2 ** (-10 * t) * math.sin((t - 0.075) * (2 * math.pi) / 0.3) + 1


EASE = {
    "linear": lambda t: t,
    "inout": lambda t: t * t * (3 - 2 * t),                    # slow in & slow out
    "inout3": lambda t: 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2,
    "in": lambda t: t * t,                                       # accelerate (fall, throw)
    "out": lambda t: 1 - (1 - t) ** 2,                           # decelerate (settle)
    "in3": lambda t: t ** 3,
    "out3": lambda t: 1 - (1 - t) ** 3,
    "back": _back,                                               # overshoot then settle
    "backsoft": lambda t: _back(t, 0.9),
    "elastic": _elastic,
    "step": lambda t: 0.0 if t < 1.0 else 1.0,
}


def R(x=0.0, y=0.0, z=0.0):
    return {"r": (x, y, z)}


def L(x=0.0, y=0.0, z=0.0):
    return {"l": (x, y, z)}


def RL(r, l):
    return {"r": r, "l": l}


def Sc(x=1.0, y=1.0, z=1.0, r=(0, 0, 0)):
    return {"r": r, "s": (x, y, z)}


def mirror_name(n):
    if n.endswith(".L"):
        return n[:-2] + ".R"
    if n.endswith(".R"):
        return n[:-2] + ".L"
    return n


def mirror_value(v):
    out = {}
    if "r" in v:
        x, y, z = v["r"]
        out["r"] = (x, -y, -z)
    if "l" in v:
        x, y, z = v["l"]
        out["l"] = (-x, y, z)
    if "s" in v:
        out["s"] = v["s"]
    return out


def mirror_pose(pose):
    return {mirror_name(b): mirror_value(v) for b, v in pose.items()}


def sym(pose):
    """Add the mirrored counterpart of every .L bone (symmetric pose)."""
    out = dict(pose)
    for b, v in pose.items():
        if b.endswith(".L"):
            out[mirror_name(b)] = mirror_value(v)
    return out


def _norm(v):
    if isinstance(v, tuple):
        return {"r": v}
    return v


# ---------------------------------------------------------------------------
# Clip
# ---------------------------------------------------------------------------


class Clip:
    def __init__(self, name, length, loop=False):
        self.name = name
        self.length = float(length)
        self.loop = loop
        self.tracks = {}      # bone -> [(t, value, ease)]
        self.layers = []      # fn(t) -> {bone: value (additive)}
        self.follows = []     # (chain, driver, lag, gain, axes)
        self.ik = {}          # target name -> [(t, pos, ease)]
        self.ik_weight = {}   # target name -> [(t, w, ease)]
        self.poles = {}       # target name -> pos (armature space)
        self.events = []      # (t, name) -> exported as metadata (footstep, cheer)

    # -- authoring --------------------------------------------------------
    def key(self, t, pose, ease="inout"):
        for b, v in pose.items():
            self.tracks.setdefault(b, []).append((float(t), _norm(v), ease))
        return self

    def keys(self, seq, ease="inout"):
        for item in seq:
            if len(item) == 3:
                self.key(item[0], item[1], item[2])
            else:
                self.key(item[0], item[1], ease)
        return self

    def layer(self, fn):
        self.layers.append(fn)
        return self

    def follow(self, chain, driver, lag=0.06, gain=1.0, axes=(1, 1, 1), falloff=1.0):
        self.follows.append((chain, driver, lag, gain, np.asarray(axes, float), falloff))
        return self

    def target(self, name, t, pos, ease="inout"):
        self.ik.setdefault(name, []).append((float(t), np.asarray(pos, float), ease))
        return self

    def weight(self, name, t, w, ease="inout"):
        self.ik_weight.setdefault(name, []).append((float(t), float(w), ease))
        return self

    def pole(self, name, pos):
        self.poles[name] = np.asarray(pos, float)
        return self

    def event(self, t, name):
        self.events.append((t, name))
        return self

    # -- evaluation -------------------------------------------------------
    @property
    def frames(self):
        return int(round(self.length * FPS)) + (0 if self.loop else 1)

    def _eval_track(self, track, t, comp, default):
        pts = [(k[0], k[1][comp], k[2]) for k in track if comp in k[1]]
        if not pts:
            return None
        pts.sort(key=lambda k: k[0])
        if self.loop:
            # wrap: add the first key again one period later
            first = pts[0]
            if first[0] > 1e-6 or pts[-1][0] < self.length - 1e-6:
                pts = [(pts[-1][0] - self.length, pts[-1][1], pts[-1][2])] + pts + [(first[0] + self.length, first[1], first[2])]
            t = t % self.length
        if t <= pts[0][0]:
            return np.asarray(pts[0][1], float)
        for i in range(len(pts) - 1):
            t0, v0, _e0 = pts[i]
            t1, v1, e1 = pts[i + 1]
            if t0 <= t <= t1:
                u = 0.0 if t1 - t0 < 1e-9 else (t - t0) / (t1 - t0)
                w = EASE[e1](u)
                return np.asarray(v0, float) * (1 - w) + np.asarray(v1, float) * w
        return np.asarray(pts[-1][1], float)

    def base(self, t):
        pose = {}
        for b, tr in self.tracks.items():
            v = {}
            for comp, dflt in (("r", (0, 0, 0)), ("l", (0, 0, 0)), ("s", (1, 1, 1))):
                x = self._eval_track(tr, t, comp, dflt)
                if x is not None:
                    v[comp] = x
            pose[b] = v
        for fn in self.layers:
            for b, dv in fn(t % self.length if self.loop else t).items():
                v = pose.setdefault(b, {})
                for comp in ("r", "l"):
                    if comp in dv:
                        v[comp] = v.get(comp, np.zeros(3)) + np.asarray(dv[comp], float)
                if "s" in dv:
                    v["s"] = v.get("s", np.ones(3)) * np.asarray(dv["s"], float)
        return pose

    def pose_at(self, t):
        pose = self.base(t)
        for chain, driver, lag, gain, axes, falloff in self.follows:
            src_now = self._driver_rot(driver, t)
            for i, bone in enumerate(chain):
                src_then = self._driver_rot(driver, t - lag * (i + 1))
                delta = (src_then - src_now) * gain * (falloff ** i) * axes
                v = pose.setdefault(bone, {})
                v["r"] = v.get("r", np.zeros(3)) + delta
        return pose

    def _driver_rot(self, driver, t):
        if self.loop:
            t = t % self.length
        else:
            t = min(max(t, 0.0), self.length)
        p = self.base(t)
        if isinstance(driver, (list, tuple)):
            acc = np.zeros(3)
            for d in driver:
                acc += np.asarray(p.get(d, {}).get("r", np.zeros(3)))
            return acc
        return np.asarray(p.get(driver, {}).get("r", np.zeros(3)))

    def ik_at(self, t):
        out = {}
        for name, tr in self.ik.items():
            pts = [(k[0], {"p": k[1]}, k[2]) for k in tr]
            pos = self._eval_track([(a, b, c) for a, b, c in pts], t, "p", None)
            w = 1.0
            if name in self.ik_weight:
                ww = self._eval_track([(a, {"w": np.array([b])}, c) for a, b, c in self.ik_weight[name]], t, "w", None)
                w = float(ww[0])
            out[name] = (pos, w)
        for name, tr in self.ik_weight.items():
            if name not in out:
                ww = self._eval_track([(a, {"w": np.array([b])}, c) for a, b, c in tr], t, "w", None)
                out[name] = (None, float(ww[0]))
        return out


# ---------------------------------------------------------------------------
# Procedural helpers for layers
# ---------------------------------------------------------------------------


def wave(amp, period, phase=0.0):
    return lambda t: amp * math.sin(2 * math.pi * (t / period + phase))


def breathe(amp=1.5, period=2.0, bones=("spine", "chest")):
    def fn(t):
        s = math.sin(2 * math.pi * t / period)
        return {b: {"r": (amp * s * (0.6 if i == 0 else 1.0), 0, 0)} for i, b in enumerate(bones)}
    return fn


def noise1(t, seed=0, freq=1.0):
    """Smooth 1D value noise in [-1, 1] (periodic-safe enough for idles)."""
    x = t * freq + seed * 13.37
    i = math.floor(x)
    f = x - i

    def h(n):
        n = (n * 374761393 + seed * 668265263) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0
    u = f * f * (3 - 2 * f)
    return h(i) * (1 - u) + h(i + 1) * u


def loop_noise(t, length, seed=0, cycles=2):
    """Noise that loops seamlessly over `length` (blend of two phases)."""
    a = noise1(t / length * cycles, seed, 1.0)
    b = noise1((t - length) / length * cycles, seed, 1.0)
    w = t / length
    return a * (1 - w) + b * w
