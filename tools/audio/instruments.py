"""instruments.py - synthesized instruments & drum kit shared by music.py and sfx.py.

Every instrument returns a mono float array starting at the note onset (tails
included). Randomness comes from a seed derived from the call arguments, so
renders are deterministic and cacheable.
"""
from __future__ import annotations

import zlib
from functools import lru_cache

import numpy as np

from dsp import (SR, TAU, N, tvec, rng, phase, additive, lowpass_resp, fm, sine, saw, modal, env_perc,
                 lp, hp, bp, filt, karplus, white, pink, saturate, ctrl, curve, fade, tvfilt, square)


def _seed(*args) -> np.random.Generator:
    return rng(zlib.crc32(repr(args).encode()))


def _onset(n, ms=1.5):
    return np.clip(tvec(n) / (ms / 1000.0), 0.0, 1.0)


def _release(x, dur, rel):
    """Hold for ``dur`` then fade over ``rel`` (x must be >= dur+rel long)."""
    n = len(x)
    t = tvec(n)
    g = np.clip(1.0 - (t - dur) / max(rel, 1e-4), 0.0, 1.0) ** 2
    return x * g


# ================================================================= pitched instruments
@lru_cache(maxsize=4096)
def steel_drum(freq: float, dur: float = 0.6, var: int = 0) -> np.ndarray:
    """Steel pan: tuned 1-2-3 partials, beating octave pair and an FM 'ping' attack."""
    r = _seed("steel", freq, dur, var)
    d0 = float(np.clip(0.75 * (440.0 / freq) ** 0.35, 0.25, 1.4))
    ring = max(dur, 0.25) + d0 * 1.5
    n = N(ring)
    t = tvec(n)
    f = freq * (1.0 + 0.006 * np.exp(-t / 0.015))
    parts = [(1.0, 1.0, 1.0), (2.0, 0.55, 0.75), (2.0 * 1.0045, 0.25, 0.7), (3.0, 0.26, 0.45),
             (4.02, 0.10, 0.3), (5.05, 0.05, 0.2)]
    y = np.zeros(n)
    for ratio, a, dm in parts:
        fk = f * ratio
        if fk[0] > 0.45 * SR:
            continue
        y += a * np.exp(-t / (d0 * dm)) * np.sin(TAU * phase(fk, n, r.random()))
    ping = fm(freq, n, ratio=1.0, index=2.5 * np.exp(-t / 0.012)) * np.exp(-t / 0.035)
    y = (y + 0.35 * ping) * _onset(n, 1.0)
    y = _release(y, max(dur, 0.12) + d0 * 0.8, d0)
    return y * 0.5


@lru_cache(maxsize=4096)
def marimba(freq: float, dur: float = 0.4, var: int = 0) -> np.ndarray:
    r = _seed("marimba", freq, dur, var)
    d0 = float(np.clip(0.45 * (330.0 / freq) ** 0.5, 0.12, 0.9))
    n = N(d0 * 5)
    t = tvec(n)
    y = modal(freq, n, [1.0, 3.93, 9.24], [1.0, 0.22, 0.05], [d0, 0.06, 0.02], r)
    mallet = lp(r.standard_normal(n) * np.exp(-t / 0.002), 3000)
    y = (y + 0.25 * mallet) * _onset(n, 0.8)
    return y * 0.6


@lru_cache(maxsize=4096)
def vibes(freq: float, dur: float = 1.0, var: int = 0) -> np.ndarray:
    r = _seed("vibes", freq, dur, var)
    n = N(dur + 1.2)
    t = tvec(n)
    y = modal(freq, n, [1.0, 3.98, 10.1], [1.0, 0.12, 0.03], [1.6, 0.25, 0.05], r)
    trem = 1.0 - 0.25 * (0.5 + 0.5 * np.sin(TAU * 5.2 * t))
    y = y * trem * _onset(n, 1.5)
    return _release(y, dur, 0.6) * 0.5


def _brass_core(freq, n, dur, bright, attack, t, r, detunes=(-6.0, 5.0)):
    env_a = np.clip(t / attack, 0, 1) ** 1.5
    swell = env_a * (0.75 + 0.25 * np.exp(-np.maximum(t - attack, 0) / 0.12))
    fc = freq * (1.2 + 5.0 * bright * swell * (0.7 + 0.3 * np.exp(-np.maximum(t - attack, 0) / 0.25)))
    vib = 1.0 + 0.004 * np.sin(TAU * 5.4 * t) * np.clip((t - 0.25) / 0.3, 0, 1)
    scoop = 2.0 ** (-35.0 / 1200.0 * np.exp(-t / 0.03))
    y = np.zeros(n)
    for d in detunes:
        f = freq * 2.0 ** (d / 1200.0) * vib * scoop
        y += additive(f, n, lambda k, fk: lowpass_resp(fk, fc, 2.5) / k, kmax=60, fmax=11000.0,
                      phases=r.random(8))
    return y / len(detunes), swell


@lru_cache(maxsize=2048)
def brass(freq: float, dur: float = 0.5, bright: float = 1.0, var: int = 0) -> np.ndarray:
    """Synth brass section: detuned band-limited saws through a swelling lowpass."""
    r = _seed("brass", freq, dur, bright, var)
    rel = 0.09
    n = N(dur + rel)
    t = tvec(n)
    attack = 0.03 if dur > 0.2 else 0.012
    y, swell = _brass_core(freq, n, dur, bright, attack, t, r)
    y = y * swell
    y = _release(y, dur, rel)
    y = filt(y, "peak", 1400, 1.0, 3.0)
    return saturate(y * 1.3, 1.2) * 0.55


@lru_cache(maxsize=2048)
def bass(freq: float, dur: float = 0.3, var: int = 0) -> np.ndarray:
    """Punchy synth bass: saw/square blend with a plucky filter envelope + sine sub."""
    rel = 0.04
    n = N(dur + rel)
    t = tvec(n)
    fc = freq * (1.8 + 9.0 * np.exp(-t / 0.05))
    body = additive(freq, n, lambda k, fk: (1.0 if k % 2 else 0.55) / k * lowpass_resp(fk, fc, 2.0, 0.3),
                    kmax=40, fmax=6000.0)
    sub = sine(freq, n)
    amp = np.clip(t / 0.003, 0, 1) * (0.72 + 0.28 * np.exp(-t / 0.12))
    y = (0.8 * body + 0.6 * sub) * amp
    y = saturate(y * 1.6, 1.0) / 1.2
    return _release(y, dur, rel)


@lru_cache(maxsize=2048)
def upright(freq: float, dur: float = 0.5, var: int = 0) -> np.ndarray:
    """Soft upright-style bass for bossa (KS string, dark, with thumb thump)."""
    r = _seed("upright", freq, dur, var)
    y = karplus(freq, dur + 0.25, r, t60=1.4, bright=0.1, pluck_pos=0.3, excite_lp=900)
    y = lp(y, 900)
    y = y / (np.abs(y).max() + 1e-9)
    y += 0.5 * sine(freq, len(y)) * env_perc(len(y), 0.004, 0.35)
    return _release(y, dur, 0.12) * 0.6


@lru_cache(maxsize=8192)
def nylon(freq: float, dur: float = 0.8, vel: float = 1.0, var: int = 0) -> np.ndarray:
    """Nylon-string guitar via Karplus-Strong (warm, fingerpicked)."""
    r = _seed("nylon", freq, dur, vel, var)
    t60 = float(np.clip(2.4 * (196.0 / freq) ** 0.4, 0.8, 3.0))
    y = karplus(freq, dur + 0.15, r, t60=t60, bright=0.25 + 0.2 * vel, pluck_pos=0.22, excite_lp=2500 + 2500 * vel)
    y = y / (np.abs(y).max() + 1e-9)
    return _release(y, dur, 0.12) * 0.5


@lru_cache(maxsize=8192)
def cavaco(freq: float, dur: float = 0.25, vel: float = 1.0, var: int = 0) -> np.ndarray:
    """Bright steel-string cavaquinho pluck (short, semi-muted)."""
    r = _seed("cavaco", freq, dur, vel, var)
    y = karplus(freq, dur + 0.08, r, t60=0.9, bright=0.75, pluck_pos=0.12, excite_lp=7000)
    y = y / (np.abs(y).max() + 1e-9)
    return _release(y, dur, 0.06) * 0.4


def strum(notes, dur, vel=1.0, down=True, spread=0.011, inst=cavaco, var=0) -> np.ndarray:
    """Strum a chord (list of midi) with per-string delay."""
    order = sorted(notes) if down else sorted(notes, reverse=True)
    total = N(dur + 0.4 + spread * len(notes))
    out = np.zeros(total)
    for i, m in enumerate(order):
        f = float(440.0 * 2 ** ((m - 69) / 12.0))
        s = inst(round(f, 3), round(dur, 3), round(vel, 2), (var + i) % 3)
        i0 = N(i * spread)
        k = min(len(s), total - i0)
        out[i0:i0 + k] += s[:k] * (0.85 + 0.15 * (i == 0))
    return out * vel


@lru_cache(maxsize=2048)
def epiano(freq: float, dur: float = 1.0, vel: float = 0.8, var: int = 0) -> np.ndarray:
    """FM electric piano (Rhodes-like: 1:1 body + 14:1 tine bark)."""
    rel = 0.25
    n = N(dur + rel)
    t = tvec(n)
    d = float(np.clip(1.6 * (262.0 / freq) ** 0.5, 0.6, 3.0))
    body = fm(freq, n, ratio=1.0, index=(0.4 + 1.6 * vel) * np.exp(-t / 0.4) + 0.2)
    tine = fm(freq, n, ratio=14.0, index=0.8 * vel * np.exp(-t / 0.02)) * np.exp(-t / 0.05)
    y = (body * np.exp(-t / d) + 0.12 * tine) * _onset(n, 2.0)
    return _release(y, dur, rel) * 0.45


@lru_cache(maxsize=1024)
def pad(freq: float, dur: float = 2.0, var: int = 0) -> np.ndarray:
    """Warm saw pad (3 detuned voices, slow attack)."""
    rel = 0.4
    n = N(dur + rel)
    t = tvec(n)
    y = sum(saw(freq * 2 ** (c / 1200.0), n, p0=0.3 * i) for i, c in enumerate((-9, 0, 8)))
    y = lp(y, min(2200.0, freq * 5), order=2)
    env = np.clip(t / 0.35, 0, 1) ** 1.5
    return _release(y * env, dur, rel) * 0.18


@lru_cache(maxsize=1024)
def flute(freq: float, dur: float = 0.6, var: int = 0) -> np.ndarray:
    """Soft breathy flute/whistle lead."""
    r = _seed("flute", freq, dur, var)
    rel = 0.12
    n = N(dur + rel)
    t = tvec(n)
    vib = 1.0 + 0.006 * np.sin(TAU * 5.0 * t) * np.clip((t - 0.2) / 0.3, 0, 1)
    f = freq * vib
    tone = additive(f, n, lambda k, fk: [0, 1.0, 0.12, 0.05, 0.02][k] if k < 5 else 0.0, kmax=4)
    breath = bp(r.standard_normal(n), freq * 2, 1.5) * 0.25 + hp(r.standard_normal(n), 5000) * 0.02
    env = np.clip(t / 0.05, 0, 1) ** 2 * (0.9 + 0.1 * np.exp(-t / 0.1))
    chiff = np.exp(-t / 0.03) * 0.5
    y = (tone + breath * (0.5 + chiff)) * env
    return _release(y, dur, rel) * 0.5


@lru_cache(maxsize=1024)
def pluck_synth(freq: float, dur: float = 0.15, var: int = 0) -> np.ndarray:
    """Bright square arp pluck."""
    n = N(dur + 0.08)
    t = tvec(n)
    fc = freq * (1.5 + 8 * np.exp(-t / 0.04))
    y = additive(freq, n, lambda k, fk: (1.0 / k if k % 2 else 0.0) * lowpass_resp(fk, fc, 2.0), kmax=30, fmax=9000)
    y *= env_perc(n, 0.002, 0.12)
    return _release(y, dur, 0.06) * 0.5


# ================================================================= percussion
@lru_cache(maxsize=64)
def kick(var: int = 0, tight: float = 1.0) -> np.ndarray:
    n = N(0.5)
    t = tvec(n)
    f = 46.0 + 120.0 * np.exp(-t / (0.03 * tight))
    body = sine(f, n) * (np.exp(-t / (0.22 * tight)) * np.clip(t / 0.001, 0, 1))
    r = _seed("kick", var)
    click = hp(r.standard_normal(n), 1800) * np.exp(-t / 0.0025) * 0.35
    y = saturate(1.4 * body, 1.3) + click
    return y * 0.9


@lru_cache(maxsize=64)
def snare(var: int = 0, tone: float = 1.0) -> np.ndarray:
    r = _seed("snare", var)
    n = N(0.35)
    t = tvec(n)
    shell = modal(185.0, n, [1.0, 1.78], [1.0, 0.5], [0.07, 0.04], r) * tone
    nz = r.standard_normal(n)
    wires = bp(hp(nz, 1500), 5000, 0.6) * np.exp(-t / 0.13)
    crack = hp(nz, 800) * np.exp(-t / 0.012)
    y = 0.8 * shell + 0.9 * wires / 0.6 + 0.6 * crack
    return y * _onset(n, 0.5) * 0.45


@lru_cache(maxsize=64)
def rimclick(var: int = 0) -> np.ndarray:
    r = _seed("rim", var)
    n = N(0.08)
    t = tvec(n)
    y = modal(1700.0, n, [1.0, 1.47, 0.52], [1.0, 0.5, 0.4], [0.012, 0.008, 0.02], r)
    y += 0.4 * hp(r.standard_normal(n), 3000) * np.exp(-t / 0.002)
    return y * _onset(n, 0.3) * 0.5


_METAL = [205.3, 304.4, 369.6, 522.7, 540.0, 800.0]


def _metal(n, scale=1.0):
    y = sum(square(f * scale * 1.7, n) for f in _METAL)
    return y / 6.0


@lru_cache(maxsize=64)
def hat(open_: bool = False, var: int = 0) -> np.ndarray:
    r = _seed("hat", open_, var)
    dec = 0.22 if open_ else 0.035
    n = N(dec * 5)
    t = tvec(n)
    m = _metal(n, 1.0 + 0.01 * var)
    y = 0.6 * bp(m, 9000, 1.0) + 0.5 * hp(r.standard_normal(n), 7500)
    y = hp(y, 6500) * np.exp(-t / dec) * _onset(n, 0.3)
    return y * 0.4


@lru_cache(maxsize=16)
def crash(var: int = 0) -> np.ndarray:
    r = _seed("crash", var)
    n = N(2.6)
    t = tvec(n)
    m = _metal(n, 1.33)
    nz = r.standard_normal(n)
    y = 0.4 * hp(m, 3000) + 0.8 * hp(nz, 4000)
    y = lp(y, 13000)
    y *= (0.6 * np.exp(-t / 0.15) + 0.4 * np.exp(-t / 0.9)) * _onset(n, 1.0)
    return y * 0.3


@lru_cache(maxsize=64)
def surdo(open_: bool = True, var: int = 0) -> np.ndarray:
    r = _seed("surdo", open_, var)
    n = N(0.9 if open_ else 0.25)
    t = tvec(n)
    f = 58.0 + 20.0 * np.exp(-t / 0.05)
    dec = 0.45 if open_ else 0.07
    y = sine(f, n) * np.exp(-t / dec) + 0.3 * sine(f * 1.59, n) * np.exp(-t / (dec * 0.5))
    y += 0.25 * lp(r.standard_normal(n), 700) * np.exp(-t / 0.01)
    return saturate(y * 1.2) * _onset(n, 1.0) * 0.7


@lru_cache(maxsize=64)
def shaker(var: int = 0, accent: bool = False) -> np.ndarray:
    r = _seed("shaker", var, accent)
    n = N(0.09)
    t = tvec(n)
    env = np.clip(t / 0.008, 0, 1) * np.exp(-t / (0.028 if accent else 0.018))
    y = bp(hp(r.standard_normal(n), 4000), 7500, 0.8) * env
    return y * 0.35


@lru_cache(maxsize=64)
def tamborim(var: int = 0) -> np.ndarray:
    r = _seed("tamb", var)
    n = N(0.15)
    t = tvec(n)
    y = modal(640.0 * (1 + 0.01 * var), n, [1.0, 1.58, 2.3], [1.0, 0.4, 0.2], [0.045, 0.02, 0.012], r)
    y += 0.6 * bp(r.standard_normal(n), 3500, 1.2) * np.exp(-t / 0.006)
    return y * _onset(n, 0.3) * 0.35


@lru_cache(maxsize=16)
def agogo(high: bool = True, var: int = 0) -> np.ndarray:
    f0 = 940.0 if high else 700.0
    n = N(0.5)
    t = tvec(n)
    y = fm(f0, n, ratio=1.41, index=1.6 * np.exp(-t / 0.03)) * np.exp(-t / 0.16)
    y += 0.3 * sine(f0 * 2.72, n) * np.exp(-t / 0.05)
    return y * _onset(n, 0.5) * 0.28


@lru_cache(maxsize=16)
def triangle_perc(open_: bool = True, var: int = 0) -> np.ndarray:
    r = _seed("tri", open_, var)
    dec = 0.5 if open_ else 0.04
    n = N(dec * 4 + 0.02)
    y = modal(1760.0, n, [1.0, 2.75, 4.2, 5.9], [0.6, 1.0, 0.6, 0.4], [dec, dec * 0.8, dec * 0.6, dec * 0.4], r)
    return y * _onset(n, 0.3) * 0.12


@lru_cache(maxsize=16)
def clap(var: int = 0) -> np.ndarray:
    r = _seed("clap", var)
    n = N(0.3)
    t = tvec(n)
    env = np.zeros(n)
    for k, d in enumerate((0.0, 0.009, 0.017, 0.026)):
        env += np.where(t >= d, np.exp(-(t - d) / 0.006), 0.0) * (0.7 if k < 3 else 1.0)
    env += np.where(t >= 0.026, 0.5 * np.exp(-(t - 0.026) / 0.09), 0.0)
    y = bp(r.standard_normal(n), 1300, 1.1) * env
    return y * 0.5


@lru_cache(maxsize=16)
def cuica(up: bool = True, var: int = 0) -> np.ndarray:
    """The squeaky samba friction drum: a vocal-like pitched 'whoop'."""
    r = _seed("cuica", up, var)
    n = N(0.28)
    f = curve(n, [(0, 420), (0.08, 820), (0.2, 650), (0.28, 500)] if up else
              [(0, 700), (0.1, 520), (0.28, 380)], "exp")
    y = additive(f, n, lambda k, fk: 1.0 / k ** 1.3 * lowpass_resp(fk, 1800, 2.0), kmax=12)
    y = bp(y, 1100, 0.8) * 2 + 0.3 * y
    env = np.sin(np.pi * np.clip(tvec(n) / 0.26, 0, 1)) ** 1.2
    return y * env * 0.35


@lru_cache(maxsize=16)
def brush_swish(dur: float = 0.3, var: int = 0) -> np.ndarray:
    r = _seed("brush", dur, var)
    n = N(dur)
    t = tvec(n)
    env = np.sin(np.pi * t / dur) ** 2
    return bp(r.standard_normal(n), 4200, 0.7) * env * 0.12


@lru_cache(maxsize=16)
def brush_tap(var: int = 0) -> np.ndarray:
    r = _seed("btap", var)
    n = N(0.15)
    t = tvec(n)
    y = lp(hp(r.standard_normal(n), 1500), 7000) * np.exp(-t / 0.035) * np.clip(t / 0.004, 0, 1)
    return y * 0.3


@lru_cache(maxsize=16)
def tom(freq: float = 120.0, var: int = 0) -> np.ndarray:
    r = _seed("tom", freq, var)
    n = N(0.5)
    t = tvec(n)
    f = freq * (1 + 0.5 * np.exp(-t / 0.03))
    y = sine(f, n) * np.exp(-t / 0.18) + 0.2 * lp(r.standard_normal(n), 1500) * np.exp(-t / 0.01)
    return saturate(y) * _onset(n, 0.5) * 0.6


@lru_cache(maxsize=8)
def timpani(freq: float = 65.0, var: int = 0) -> np.ndarray:
    r = _seed("timp", freq, var)
    n = N(1.8)
    t = tvec(n)
    y = modal(freq, n, [1.0, 1.5, 1.98, 2.44], [1.0, 0.5, 0.3, 0.15], [0.9, 0.5, 0.35, 0.25], r)
    y += 0.3 * lp(r.standard_normal(n), 600) * np.exp(-t / 0.02)
    return y * _onset(n, 1.0) * 0.6


def snare_roll(dur: float, rate: float = 24.0, v0: float = 0.2, v1: float = 1.0, var: int = 0) -> np.ndarray:
    n = N(dur + 0.4)
    out = np.zeros(n)
    k = int(dur * rate)
    for i in range(k):
        v = v0 + (v1 - v0) * (i / max(1, k - 1)) ** 1.5
        s = snare(i % 4, 0.5)
        i0 = N(i / rate)
        m = min(len(s), n - i0)
        out[i0:i0 + m] += v * s[:m]
    return out
