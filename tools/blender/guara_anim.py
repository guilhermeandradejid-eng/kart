"""Guará's animation set, authored pose-to-pose with the twelve principles.

Driving clips assume the armature object sits on the kart's socket_driver and
the hips are pulled down onto the seat (SEAT). Hand/foot IK targets are in
that seat space: steering-wheel grips and pedals come from kart_parts.

Principles, where they live:
  squash & stretch  - hop/land/boost scale the spine+chest (Sc), cheeks via jaw
  anticipation      - every big action starts with a counter move (hop dips,
                      boost leans in before the kick, throw winds up)
  staging           - clear silhouettes: victory V-pose, look-back twist
  pose to pose      - keyed extremes + breakdowns, eased per key
  follow-through /
  overlapping action- tail, ears, scarf lag via Clip.follow; head keys trail
                      the spine by 2-3 frames (successive breaking of joints)
  slow in / out     - per-key easing ("inout", "out", "back")
  arcs              - hand paths go through breakdown keys off the straight line
  secondary action  - blinks on head turns, ear flicks, tail wags, breathing
  timing            - fast snaps (2-4 frames) against long holds
  exaggeration      - boost face, dizzy spin, victory jump
  solid drawing     - volumes preserved (scale compensates on the other axes)
  appeal            - asymmetry: one ear lags, head tilts, brows differ
"""

import math

import numpy as np

from tt.anim import (L, R, RL, Clip, Sc, breathe, loop_noise, mirror_pose, sym)

# ---- seat space -------------------------------------------------------------
SEAT = {"hips": L(0, 0.0, -0.40)}
WHEEL_C = np.array([0.0, 0.29, 0.23])          # kart wheel centre relative to socket_driver
_c = np.array([0.0, -0.832, 0.555])            # column direction (towards driver)
WHEEL_U = np.array([1.0, 0.0, 0.0])
WHEEL_V = np.array([0.0, 0.555, 0.832])        # wheel "up" in its plane
GRIP_R = 0.13
PEDAL = {"L": np.array([-0.085, 0.27, -0.04]), "R": np.array([0.085, 0.27, -0.04])}
POLE_ARM = {"L": np.array([-0.45, -0.05, 0.05]), "R": np.array([0.45, -0.05, 0.05])}
POLE_LEG = {"L": np.array([-0.12, 0.35, 0.35]), "R": np.array([0.12, 0.35, 0.35])}


def grip(side, steer_deg):
    """Wrist target on the wheel rim. steer_deg > 0 = steering left
    (wheel turns counter-clockwise from the driver's view)."""
    a = math.radians(steer_deg)
    sgn = -1 if side == "L" else 1
    d = sgn * (math.cos(a) * WHEEL_U + math.sin(a) * WHEEL_V)
    return WHEEL_C + GRIP_R * d + np.array([0, -0.035, -0.035])


def seated(clip, steer=None, feet=True, arms=True):
    """Common driving setup: IK on pedals/wheel, poles, seat offset key."""
    for s in "LR":
        clip.pole(f"hand.{s}", POLE_ARM[s])
        clip.pole(f"foot.{s}", POLE_LEG[s])
        if feet:
            clip.target(f"foot.{s}", 0, PEDAL[s])
        if arms and steer is not None:
            clip.target(f"hand.{s}", 0, grip(s, steer))
    return clip


# ---- facial helpers ------------------------------------------------------------

def blink(clip, t, dur=0.2, amount=78):
    """Fast close (2 frames, ease in), slower open (ease out)."""
    for s in "LR":
        clip.key(t, {f"lid_up.{s}": R(0), f"lid_lo.{s}": R(0)}, "inout")
        clip.key(t + dur * 0.33, {f"lid_up.{s}": R(-amount), f"lid_lo.{s}": R(18)}, "in")
        clip.key(t + dur, {f"lid_up.{s}": R(0), f"lid_lo.{s}": R(0)}, "out")


def face(brow=0.0, angry=0.0, squint=0.0, jaw=0.0, look=(0, 0)):
    """brow: raise (+) / lower (-) in metres*100; angry: inner ends down (deg);
    squint: lids narrow (deg); jaw: open (deg); look: eyes (yaw, pitch) deg."""
    p = {"jaw": R(-jaw)}
    for s, sg in (("L", 1), ("R", -1)):
        p[f"brow.{s}"] = RL((0, sg * angry, 0), (0, 0, brow * 0.01))
        p[f"lid_up.{s}"] = R(-squint)
        p[f"lid_lo.{s}"] = R(squint * 0.6)
        p[f"eye.{s}"] = R(look[1], 0, look[0])
    return p


def merge(*poses):
    out = {}
    for p in poses:
        for b, v in p.items():
            if b in out:
                o = dict(out[b])
                for comp in ("r", "l"):
                    if comp in v:
                        o[comp] = tuple(np.asarray(o.get(comp, (0, 0, 0))) + np.asarray(v[comp]))
                if "s" in v:
                    o["s"] = v["s"]
                out[b] = o
            else:
                out[b] = dict(v)
    return out


# ---- secondary layers -------------------------------------------------------

def tail_wag(amp=12.0, period=1.2, lift=0.0):
    def fn(t):
        out = {}
        for i in range(4):
            ph = t / period - i * 0.12
            out[f"tail.{i}"] = {"r": (lift * (1 if i == 0 else 0.3) + 3 * math.sin(2 * math.pi * ph * 2),
                                      0, amp * math.sin(2 * math.pi * ph) * (0.6 + 0.25 * i))}
        return out
    return fn


def scarf_flap(amp=10.0, period=0.35):
    def fn(t):
        out = {}
        for s, sg in (("L", 1), ("R", -1)):
            for i in range(3):
                ph = t / period - i * 0.18 + (0.25 if s == "R" else 0)
                out[f"scarf.{s}.{i}"] = {"r": (amp * math.sin(2 * math.pi * ph) * (0.5 + 0.4 * i), 0,
                                               sg * amp * 0.4 * math.sin(2 * math.pi * (ph + 0.3)))}
        return out
    return fn


def ear_twitch(t0, side="L", amp=14.0):
    def fn(t):
        dt = t - t0
        if 0 <= dt < 0.35:
            w = math.exp(-dt * 12) * math.sin(dt * 55)
            sg = 1 if side == "L" else -1
            return {f"ear.{side}.0": {"r": (amp * w, 0, sg * amp * 0.5 * w)}, f"ear.{side}.1": {"r": (amp * 0.8 * w, 0, 0)}}
        return {}
    return fn


def jitter(amp=1.0, freq=9.0, bones=("chest", "head"), length=1.0, seed=3):
    def fn(t):
        out = {}
        for i, b in enumerate(bones):
            out[b] = {"r": (amp * loop_noise(t, length, seed + i, int(freq * length)),
                            amp * 0.6 * loop_noise(t, length, seed + 7 + i, int(freq * length)), 0)}
        return out
    return fn


def std_follow(clip, tail_gain=0.9, ear_gain=0.8, scarf_gain=1.2):
    clip.follow(["tail.0", "tail.1", "tail.2", "tail.3"], ["hips", "spine"], lag=0.07, gain=tail_gain, axes=(0.6, 0.3, 1.0))
    for s in "LR":
        clip.follow([f"ear.{s}.0", f"ear.{s}.1"], ["neck", "head"], lag=0.06, gain=ear_gain, axes=(1.0, 0.5, 0.5))
        clip.follow([f"scarf.{s}.0", f"scarf.{s}.1", f"scarf.{s}.2"], ["chest", "neck"], lag=0.06, gain=scarf_gain,
                    axes=(1.0, 0.5, 1.0))
    return clip


# ---- base driving pose ----------------------------------------------------------

DRIVE = merge(SEAT, {
    "spine": R(6, 0, 0), "chest": R(-4, 0, 0), "neck": R(-2, 0, 0), "head": R(-4, 0, 0),
    "tail.0": R(35, 0, 55), "tail.1": R(25, 0, 20), "tail.2": R(10, 0, 10), "tail.3": R(-5, 0, 5),
    "scarf.L.0": R(-25, 0, 0), "scarf.R.0": R(-25, 0, 0),
    "ear.L.0": R(-4, 0, 0), "ear.R.0": R(-4, 0, 0),
})


def drive_idle():
    c = seated(Clip("drive_idle", 2.4, loop=True), steer=0)
    c.key(0.0, merge(DRIVE, face(look=(0, 0)), {"head": R(-4, 0, 0)}))
    # glance left (head leads, eyes lead the head by 2 frames)
    c.key(0.55, merge(DRIVE, face(look=(18, 2)), {"head": R(-2, 0, 10), "neck": R(-2, 0, 4)}))
    c.key(1.1, merge(DRIVE, face(look=(0, 0)), {"head": R(-4, 0, 0)}))
    c.key(1.55, merge(DRIVE, face(look=(-14, -2)), {"head": R(-5, -3, -7), "neck": R(-2, 0, -3)}))
    c.key(2.4, merge(DRIVE, face(look=(0, 0)), {"head": R(-4, 0, 0)}))
    blink(c, 0.48)
    blink(c, 1.5)
    c.layer(breathe(1.6, 1.2))
    c.layer(tail_wag(8, 2.4 / 2))
    c.layer(ear_twitch(1.05, "R"))
    return std_follow(c)


def steer(side):
    """Held turn pose used in the steering blend space (loops subtly)."""
    sg = 1 if side == "L" else -1                # left turn: lean left (ry<0), look left (rz>0)
    c = seated(Clip(f"steer_{side}", 1.2, loop=True), steer=sg * 55)
    p = merge(DRIVE, face(look=(sg * 20, 0), brow=-0.3), {
        "spine": R(4, -sg * 7, sg * 4), "chest": R(-6, -sg * 4, sg * 6),
        "neck": R(-2, 0, sg * 6), "head": R(-6, -sg * 4, sg * 12),
        "ear.L.0": R(-4, 0, sg * 10), "ear.R.0": R(-4, 0, sg * 10),
        "tail.0": R(35, 0, 55 - sg * 25),
    })
    c.key(0, p)
    c.key(0.6, merge(p, {"chest": R(1, 0, 0)}))
    c.key(1.2, p)
    blink(c, 0.7)
    c.layer(tail_wag(6, 0.6))
    return std_follow(c)


def drift(side):
    sg = 1 if side == "L" else -1
    c = seated(Clip(f"drift_{side}", 0.8, loop=True), steer=sg * 75)
    p = merge(DRIVE, face(look=(sg * 26, 2), angry=14, brow=-0.6, squint=12, jaw=5), {
        "spine": R(0, -sg * 11, sg * 6), "chest": R(-10, -sg * 6, sg * 8),
        "neck": R(-4, 0, sg * 8), "head": R(-8, -sg * 5, sg * 16),
        "ear.L.0": R(38, 0, sg * 12), "ear.R.0": R(38, 0, sg * 12), "ear.L.1": R(20), "ear.R.1": R(20),
        "tail.0": R(40, 0, 55 - sg * 55), "tail.1": R(30, 0, -sg * 25),
    })
    c.key(0, p)
    c.key(0.4, merge(p, {"chest": R(2, sg * 2, 0)}))
    c.key(0.8, p)
    c.layer(jitter(1.4, 12, ("chest", "head"), 0.8))
    c.layer(scarf_flap(14, 0.2))
    c.layer(tail_wag(10, 0.4))
    return std_follow(c, tail_gain=1.2)


def hop():
    c = seated(Clip("hop", 0.42), steer=0)
    c.key(0.0, merge(DRIVE, face()))
    # anticipation: dip (squash)
    c.key(0.07, merge(DRIVE, face(squint=10), {"hips": L(0, 0, -0.030), "spine": Sc(1.08, 1.08, 0.9, (-6, 0, 0)),
                                               "head": R(-12, 0, 0), "ear.L.0": R(-18), "ear.R.0": R(-18)}), "out")
    # action: stretch up, ears fly back
    c.key(0.17, merge(DRIVE, face(brow=0.8, jaw=10), {"hips": L(0, 0, 0.040), "spine": Sc(0.94, 0.94, 1.1, (10, 0, 0)),
                                                       "head": R(6, 0, 0), "ear.L.0": R(30), "ear.R.0": R(30)}), "out")
    # settle with a small overshoot
    c.key(0.30, merge(DRIVE, face(), {"hips": L(0, 0, -0.015), "spine": Sc(1.04, 1.04, 0.95, (2, 0, 0))}), "inout")
    c.key(0.42, merge(DRIVE, face()), "back")
    return std_follow(c, ear_gain=1.2)


def boost():
    c = seated(Clip("boost", 1.1), steer=0)
    c.key(0.0, merge(DRIVE, face()))
    c.key(0.08, merge(DRIVE, face(squint=10, brow=-0.4), {"chest": R(-12, 0, 0), "head": R(-10, 0, 0)}), "inout")
    # kick: thrown back into the seat, stretched, huge grin
    c.key(0.20, merge(DRIVE, face(brow=1.2, jaw=24, look=(0, 6)), {
        "spine": Sc(0.95, 0.95, 1.08, (9, 0, 0)), "chest": R(4, 0, 0), "head": R(8, 0, 0),
        "ear.L.0": R(70, 0, -10), "ear.R.0": R(70, 0, 10), "ear.L.1": R(25), "ear.R.1": R(25)}), "out3")
    c.key(0.55, merge(DRIVE, face(brow=0.8, jaw=18), {"spine": R(6, 0, 0), "head": R(4, 0, 0),
                                                       "ear.L.0": R(55), "ear.R.0": R(55)}), "inout")
    c.key(1.1, merge(DRIVE, face(brow=0.3, jaw=4)), "inout")
    blink(c, 0.62)
    c.layer(scarf_flap(18, 0.18))
    return std_follow(c, scarf_gain=1.5)


def land():
    c = seated(Clip("land", 0.45), steer=0)
    c.key(0.0, merge(DRIVE, face(brow=0.5)))
    c.key(0.05, merge(DRIVE, face(squint=40, jaw=0), {"hips": L(0, 0, -0.040), "spine": Sc(1.1, 1.1, 0.86, (-10, 0, 0)),
                                                      "head": R(-16, 0, 0), "ear.L.0": R(-30, 0, 15), "ear.R.0": R(-30, 0, -15)}), "in")
    c.key(0.18, merge(DRIVE, face(brow=0.4), {"hips": L(0, 0, 0.010), "spine": Sc(0.97, 0.97, 1.04, (4, 0, 0)),
                                             "head": R(2, 0, 0)}), "out")
    c.key(0.45, merge(DRIVE, face()), "inout")
    return std_follow(c, ear_gain=1.3, tail_gain=1.3)


def trick(variant):
    c = seated(Clip(f"trick_{variant}", 0.9), steer=0)
    c.key(0.0, merge(DRIVE, face()))
    for s in "LR":
        c.weight(f"hand.{s}", 0.0, 1.0)
        c.weight(f"hand.{s}", 0.12, 0.0, "in")
        c.weight(f"hand.{s}", 0.7, 0.0)
        c.weight(f"hand.{s}", 0.88, 1.0, "inout")
    if variant == "a":   # "Yahoo!" V arms + back arch
        up = sym({"upper_arm.L": R(0, 0, 0), "shoulder.L": R(0, 0, 0)})
        up = merge(up, {"upper_arm.L": R(18, 112, 10), "upper_arm.R": R(18, -112, -10),
                        "forearm.L": R(0, 10, 0), "forearm.R": R(0, -10, 0)})
        c.key(0.10, merge(DRIVE, face(squint=15), {"chest": R(-10, 0, 0), "head": R(-10, 0, 0),
                                                   "upper_arm.L": R(0, 40, 0), "upper_arm.R": R(0, -40, 0)}), "inout")
        c.key(0.26, merge(DRIVE, up, face(brow=1.4, jaw=28, look=(0, 8)), {"spine": R(10, 0, 0), "chest": R(4, 0, 0), "head": R(4, 0, 0),
                                                              "ear.L.0": R(40, 0, 20), "ear.R.0": R(40, 0, -20)}), "back")
        c.key(0.60, merge(DRIVE, up, face(brow=1.0, jaw=22), {"spine": R(8, 0, 0), "head": R(4, 0, 6)}), "inout")
    else:                # one-arm pump with a twist
        c.key(0.10, merge(DRIVE, face(squint=15), {"chest": R(-6, 0, -12), "upper_arm.R": R(0, -30, 0)}), "inout")
        c.key(0.28, merge(DRIVE, face(brow=1.2, jaw=24, look=(-15, 5)), {
            "spine": R(8, 8, -14), "chest": R(4, 6, -16), "head": R(10, 10, -20),
            "upper_arm.R": R(12, -132, -20), "forearm.R": R(0, -40, 0),
            "upper_arm.L": R(0, 60, 0), "ear.L.0": R(30, 0, 25)}), "back")
        c.key(0.60, merge(DRIVE, face(brow=1.0, jaw=20), {"spine": R(6, 6, -10), "head": R(8, 6, -14),
                                                          "upper_arm.R": R(12, -125, -20), "forearm.R": R(0, -20, 0)}), "inout")
    c.key(0.9, merge(DRIVE, face()), "inout")
    c.layer(scarf_flap(16, 0.2))
    return std_follow(c, ear_gain=1.3)


def hit_spin():
    c = seated(Clip("hit_spin", 1.6), steer=0)
    for s in "LR":
        c.weight(f"hand.{s}", 0.0, 1.0)
        c.weight(f"hand.{s}", 0.1, 0.0, "in")
        c.weight(f"hand.{s}", 1.25, 0.0)
        c.weight(f"hand.{s}", 1.55, 1.0, "inout")
    c.key(0.0, merge(DRIVE, face()))
    c.key(0.08, merge(DRIVE, face(brow=1.6, jaw=26, squint=-10), {
        "spine": R(12, 0, 0), "head": R(20, 0, 0), "upper_arm.L": R(0, 110, 0), "upper_arm.R": R(0, -110, 0),
        "ear.L.0": R(-20, 0, 40), "ear.R.0": R(-20, 0, -40)}), "out3")
    # dizzy circles
    c.key(1.2, merge(DRIVE, face(brow=0.8, jaw=14, squint=20), {"head": R(-6, 0, 0), "upper_arm.L": R(0, 40, 0),
                                                                 "upper_arm.R": R(0, -40, 0)}), "inout")
    c.key(1.6, merge(DRIVE, face()), "inout")

    def dizzy(t):
        if t < 0.15 or t > 1.35:
            return {}
        w = math.sin(math.pi * (t - 0.15) / 1.2)
        a = t * 2 * math.pi * 2.2
        return {"head": {"r": (10 * w * math.sin(a), 12 * w * math.cos(a), 8 * w * math.sin(a))},
                "chest": {"r": (4 * w * math.sin(a - 0.6), 6 * w * math.cos(a - 0.6), 0)},
                "upper_arm.L": {"r": (30 * w * math.sin(a * 1.3), 0, 20 * w * math.cos(a * 1.3))},
                "upper_arm.R": {"r": (30 * w * math.sin(a * 1.3 + 1), 0, -20 * w * math.cos(a * 1.3 + 1))},
                "eye.L": {"r": (15 * w * math.cos(a * 1.6), 0, 20 * w * math.sin(a * 1.6))},
                "eye.R": {"r": (15 * w * math.cos(a * 1.6 + 3.1), 0, 20 * w * math.sin(a * 1.6 + 3.1))}}
    c.layer(dizzy)

    def shake_off(t):
        if 1.3 <= t <= 1.55:
            return {"head": {"r": (0, 0, 22 * math.sin((t - 1.3) * 60) * math.exp(-(t - 1.3) * 10))}}
        return {}
    c.layer(shake_off)
    return std_follow(c, ear_gain=1.4, tail_gain=1.4)


def look_back():
    c = seated(Clip("look_back", 1.0, loop=True), steer=0)
    c.weight("hand.L", 0, 0.0)
    p = merge(DRIVE, face(look=(35, 0), brow=0.5), {
        "spine": R(4, 0, 18), "chest": R(0, 0, 26), "neck": R(0, 0, 20), "head": R(-2, -8, 40),
        "upper_arm.L": R(-20, 30, 20), "forearm.L": R(0, 20, 0),
    })
    c.key(0, p)
    c.key(0.5, merge(p, {"head": R(2, 0, 4)}))
    c.key(1.0, p)
    blink(c, 0.3)
    return std_follow(c)


def countdown():
    c = seated(Clip("countdown", 0.8, loop=True), steer=0)
    p0 = merge(DRIVE, face(angry=10, brow=-0.5, squint=14, look=(0, -2)), {
        "spine": R(0, 0, 0), "chest": R(-12, 0, 0), "head": R(-6, 0, 0), "ear.L.0": R(-10, 0, 0), "ear.R.0": R(-10)})
    p1 = merge(p0, {"chest": R(-4, 0, 0), "spine": R(3, 0, 0), "hips": L(0, 0, 0.005)})
    c.key(0.0, p0)
    c.key(0.2, p1, "out")
    c.key(0.4, p0, "in")
    c.key(0.6, p1, "out")
    c.key(0.8, p0, "in")
    c.layer(tail_wag(14, 0.4))
    c.layer(jitter(0.8, 14, ("chest",), 0.8))
    return std_follow(c)


def victory():
    c = seated(Clip("victory", 3.0), steer=0, feet=False)
    floor = {"L": np.array([-0.11, 0.08, -0.12]), "R": np.array([0.11, 0.08, -0.12])}
    for s in "LR":
        c.target(f"foot.{s}", 0.0, PEDAL[s])
        c.target(f"foot.{s}", 0.28, floor[s] + np.array([0, 0.02, 0.02]))
        c.target(f"foot.{s}", 0.40, floor[s])
        c.weight(f"hand.{s}", 0.0, 1.0)
        c.weight(f"hand.{s}", 0.25, 0.0, "in")
    c.key(0.0, merge(DRIVE, face()))
    # anticipation: crouch low, arms down/back
    c.key(0.25, merge(SEAT, face(squint=20, jaw=4), {"hips": L(0, 0.02, -0.020), "spine": Sc(1.06, 1.06, 0.92, (-20, 0, 0)),
                                                     "head": R(-10, 0, 0), "upper_arm.L": R(-30, 0, 0), "upper_arm.R": R(-30, 0, 0),
                                                     "ear.L.0": R(-20), "ear.R.0": R(-20)}), "inout")
    # spring up, V arms (overshoot)
    arms_up = {"upper_arm.L": R(15, 115, 12), "upper_arm.R": R(15, -115, -12), "forearm.L": R(0, 12, 0), "forearm.R": R(0, -12, 0)}
    c.key(0.45, merge(SEAT, arms_up, face(brow=1.5, jaw=30), {"hips": L(0, 0.04, 0.29), "spine": Sc(0.95, 0.95, 1.08, (8, 0, 0)),
                                                             "chest": R(6, 0, 0), "head": R(16, 0, 0),
                                                             "ear.L.0": R(10, 0, 15), "ear.R.0": R(10, 0, -15)}), "out3")
    c.key(0.75, merge(SEAT, arms_up, face(brow=1.2, jaw=26), {"hips": L(0, 0.04, 0.25), "spine": R(4, 0, 0), "head": R(10, 0, 0)}), "inout")
    # three fist pumps with the right arm, left arm waves
    t = 0.75
    for i in range(3):
        pump_up = {"upper_arm.R": R(10, -132, -15), "forearm.R": R(0, -5, 0), "upper_arm.L": R(10, 105, 30), "forearm.L": R(0, 60, 0)}
        pump_dn = {"upper_arm.R": R(0, -100, 30), "forearm.R": R(0, -90, 0), "upper_arm.L": R(10, 118, -10), "forearm.L": R(0, 20, 0)}
        c.key(t + 0.18, merge(SEAT, pump_dn, face(brow=1.0, jaw=18, squint=20), {"hips": L(0, 0.04, 0.21), "spine": R(-4, 0, -4), "head": R(-2, 0, -6)}), "in")
        c.key(t + 0.40, merge(SEAT, pump_up, face(brow=1.4, jaw=30), {"hips": L(0, 0.04, 0.27), "spine": R(8, 0, 4), "head": R(12, 0, 8)}), "back")
        t += 0.40
    c.key(3.0, merge(SEAT, arms_up, face(brow=1.2, jaw=24), {"hips": L(0, 0.04, 0.25), "spine": R(4, 0, 0), "head": R(10, 0, 0)}), "inout")
    blink(c, 1.9)
    c.layer(tail_wag(28, 0.35, lift=20))
    return std_follow(c, ear_gain=1.2)


def victory_loop():
    c = Clip("victory_loop", 1.2, loop=True)
    floor = {"L": np.array([-0.11, 0.08, -0.12]), "R": np.array([0.11, 0.08, -0.12])}
    for s in "LR":
        c.pole(f"foot.{s}", POLE_LEG[s])
        c.target(f"foot.{s}", 0.0, floor[s])
    arms_a = {"upper_arm.L": R(12, 120, 20), "forearm.L": R(0, 30, 0), "upper_arm.R": R(12, -120, -20), "forearm.R": R(0, -30, 0)}
    arms_b = {"upper_arm.L": R(12, 108, -15), "forearm.L": R(0, 5, 0), "upper_arm.R": R(12, -108, 15), "forearm.R": R(0, -5, 0)}
    c.key(0.0, merge(SEAT, arms_a, face(brow=1.2, jaw=26), {"hips": L(0, 0.04, 0.25), "head": R(10, 0, 8), "spine": R(4, 0, 4)}))
    c.key(0.3, merge(SEAT, arms_b, face(brow=1.0, jaw=20, squint=15), {"hips": L(0, 0.04, 0.22), "head": R(6, 0, 0)}), "inout")
    c.key(0.6, merge(SEAT, arms_a, face(brow=1.2, jaw=26), {"hips": L(0, 0.04, 0.25), "head": R(10, 0, -8), "spine": R(4, 0, -4)}), "inout")
    c.key(0.9, merge(SEAT, arms_b, face(brow=1.0, jaw=20, squint=15), {"hips": L(0, 0.04, 0.22), "head": R(6, 0, 0)}), "inout")
    c.key(1.2, merge(SEAT, arms_a, face(brow=1.2, jaw=26), {"hips": L(0, 0.04, 0.25), "head": R(10, 0, 8), "spine": R(4, 0, 4)}), "inout")
    c.layer(tail_wag(28, 0.3, lift=20))
    return std_follow(c)


def lose():
    c = seated(Clip("lose", 2.4, loop=True), steer=0)
    for s in "LR":
        c.weight(f"hand.{s}", 0, 0.35)
    slump = merge(DRIVE, face(brow=0.6, angry=-16, squint=28, look=(0, -10)), {
        "spine": R(-6, 0, 0), "chest": R(-8, 0, 0), "neck": R(-6, 0, 0), "head": R(-13, 0, 6),
        "ear.L.0": R(-40, 0, -35), "ear.R.0": R(-40, 0, 35), "ear.L.1": R(-20), "ear.R.1": R(-20),
        "upper_arm.L": R(-10, -10, -10), "upper_arm.R": R(-10, 10, 10),
        "tail.0": R(10, 0, 60), "tail.1": R(-10, 0, 10), "tail.2": R(-15), "tail.3": R(-10)})
    inhale = merge(slump, {"chest": R(6, 0, 0), "head": R(8, 0, 0), "spine": R(3, 0, 0)})
    c.key(0.0, slump)
    c.key(0.9, inhale, "inout")   # big breath in ...
    c.key(1.5, slump, "in")        # ... and the sigh drops fast
    c.key(2.4, slump)
    blink(c, 1.6, dur=0.35)
    return std_follow(c, ear_gain=0.5)


def wave():
    c = seated(Clip("wave", 1.6, loop=True), steer=0)
    c.weight("hand.R", 0, 0.0)
    base = merge(DRIVE, face(brow=0.9, jaw=14, look=(-10, 4)), {"head": R(2, 8, -12), "spine": R(6, 0, -4),
                                                                "upper_arm.R": R(20, -120, -10)})
    a = merge(base, {"forearm.R": R(0, -30, 25), "hand.R": R(0, 0, 15)})
    b = merge(base, {"forearm.R": R(0, -30, -20), "hand.R": R(0, 0, -15)})
    c.key(0.0, a)
    c.key(0.4, b)
    c.key(0.8, a)
    c.key(1.2, b)
    c.key(1.6, a)
    blink(c, 0.9)
    c.layer(tail_wag(16, 0.8))
    return std_follow(c)


def throw(kind):
    c = seated(Clip(f"throw_{kind}", 0.6), steer=0)
    c.weight("hand.R", 0.0, 1.0)
    c.weight("hand.R", 0.06, 0.0, "in")
    c.weight("hand.R", 0.45, 0.0)
    c.weight("hand.R", 0.6, 1.0, "inout")
    c.key(0.0, merge(DRIVE, face()))
    if kind == "fwd":
        c.key(0.16, merge(DRIVE, face(squint=10, angry=8), {"chest": R(4, 0, -20), "upper_arm.R": R(-60, -120, -30),
                                                            "forearm.R": R(0, -80, 0), "head": R(0, 0, -6)}), "inout")
        c.key(0.26, merge(DRIVE, face(brow=1.0, jaw=18), {"chest": R(-10, 0, 14), "upper_arm.R": R(40, -80, 20),
                                                          "forearm.R": R(0, -10, 0), "head": R(-4, 0, 6)}), "in")
    else:
        c.key(0.16, merge(DRIVE, face(look=(-30, 0)), {"chest": R(2, 0, -16), "upper_arm.R": R(-30, -60, 0), "head": R(0, 0, -30)}), "inout")
        c.key(0.30, merge(DRIVE, face(look=(-30, -5), jaw=10), {"chest": R(4, 0, -22), "upper_arm.R": R(-70, -40, 10),
                                                                "forearm.R": R(0, -20, 0), "head": R(0, 0, -45)}), "out")
    c.key(0.6, merge(DRIVE, face()), "inout")
    return std_follow(c)


def cheer():
    c = seated(Clip("cheer", 0.8), steer=0)
    c.weight("hand.L", 0.0, 1.0)
    c.weight("hand.L", 0.08, 0.0, "in")
    c.weight("hand.L", 0.62, 0.0)
    c.weight("hand.L", 0.8, 1.0, "inout")
    c.key(0.0, merge(DRIVE, face()))
    c.key(0.12, merge(DRIVE, face(squint=10), {"upper_arm.L": R(-10, 60, 20), "forearm.L": R(0, 90, 0), "chest": R(-6, 0, 6)}), "inout")
    c.key(0.26, merge(DRIVE, face(brow=1.3, jaw=26), {"upper_arm.L": R(15, 128, 10), "forearm.L": R(0, 10, 0),
                                                      "chest": R(8, 0, -6), "head": R(10, 0, -10)}), "back")
    c.key(0.5, merge(DRIVE, face(brow=1.0, jaw=18), {"upper_arm.L": R(15, 120, 10), "chest": R(4, 0, -4), "head": R(6, 0, -6)}), "inout")
    c.key(0.8, merge(DRIVE, face()), "inout")
    c.layer(tail_wag(22, 0.3))
    return std_follow(c)


def stand_idle():
    c = Clip("stand_idle", 3.0, loop=True)
    arms = {"upper_arm.L": R(0, -25, 0), "upper_arm.R": R(0, 25, 0), "forearm.L": R(10, 0, 0), "forearm.R": R(10, 0, 0)}
    a = merge(arms, face(brow=0.3, look=(0, 0)), {"hips": RL((0, 0, 3), (0.012, 0, 0)), "spine": R(0, 2, -2),
                                                  "thigh.L": R(0, 0, 0), "head": R(0, 5, 2)})
    b = merge(arms, face(brow=0.5, look=(-12, 3)), {"hips": RL((0, 0, -3), (-0.012, 0, 0)), "spine": R(0, -2, 3),
                                                    "head": R(2, -6, -8)})
    c.key(0.0, a)
    c.key(1.5, b)
    c.key(3.0, a)
    blink(c, 1.3)
    blink(c, 2.6, dur=0.18)
    c.layer(breathe(2.0, 1.5))
    c.layer(tail_wag(14, 1.0, lift=10))
    c.layer(ear_twitch(0.7, "L"))
    return std_follow(c)


def all_clips():
    return [drive_idle(), steer("L"), steer("R"), drift("L"), drift("R"), hop(), boost(), land(),
            trick("a"), trick("b"), hit_spin(), look_back(), countdown(), victory(), victory_loop(), lose(),
            wave(), throw("fwd"), throw("back"), cheer(), stand_idle()]
