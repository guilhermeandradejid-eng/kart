"""sfx.py - every sound effect of Turbo Turma, synthesized from scratch.

Each generator takes a seeded ``np.random.Generator`` and returns a mono array.
``REGISTRY`` maps output name -> (generator, loop?, target LUFS, description).
"""
from __future__ import annotations

import numpy as np

from dsp import (SR, TAU, N, tvec, ctrl, curve, sweep, pad_to, mix, place, phase, sine, saw, square, triangle,
                 additive, lowpass_resp, fm, env_perc, fade, white, pink, brown, band_noise, shaped_noise,
                 smooth_random, periodic_lfo, filt, lp, hp, bp, tvfilt, modal, midi_hz, saturate, reverb,
                 vowel_tracks, formant_voice, formant_noise, trim_silence)
import instruments as ins


# =========================================================================== helpers
def rms(x):
    return float(np.sqrt(np.mean(x ** 2)) + 1e-12)


def norm(x):
    return x / (np.abs(x).max() + 1e-12)


def env_hump(n, peak=0.3, rise=2.0, fall=2.0):
    x = np.linspace(0, 1, n)
    return np.where(x < peak, (x / peak) ** rise, ((1 - x) / (1 - peak)) ** fall)


def onset(n, ms=1.0):
    return np.clip(tvec(n) / (ms / 1000), 0, 1)


def ping(freq, dur=0.5, decay=0.2, bright=1.0, r=None, detune=0.0):
    """Glassy bell/crystal ping."""
    n = N(dur)
    f = freq * 2 ** (detune / 1200)
    y = modal(f, n, [1.0, 2.0, 3.01, 4.16, 5.43], [1.0, 0.3 * bright, 0.15 * bright, 0.08 * bright, 0.04 * bright],
              [decay, decay * 0.6, decay * 0.4, decay * 0.25, decay * 0.15], r)
    return y * onset(n, 0.7)


PENTA = [0, 2, 4, 7, 9]


def penta_notes(lo, hi, root=0):
    return [m for m in range(lo, hi + 1) if (m - root) % 12 in PENTA]


def sparkle(dur, r, count=12, lo=84, hi=105, t0=0.0, spread=None, decay=0.1, rising=False, level=1.0):
    n = N(dur)
    out = np.zeros(n)
    spread = spread if spread is not None else dur * 0.5
    notes = penta_notes(lo, hi)
    times = np.sort(r.random(count)) * spread + t0
    for i, t in enumerate(times):
        if rising:
            m = notes[min(len(notes) - 1, int(i / max(1, count - 1) * (len(notes) - 1)))]
        else:
            m = notes[r.integers(len(notes))]
        p = ping(midi_hz(m), min(decay * 6, max(0.02, dur - t)), decay * r.uniform(0.6, 1.4), 0.6, r,
                 detune=r.uniform(-8, 8))
        place(out, p * r.uniform(0.4, 1.0), t)
    return out * level


def whoosh(dur, r, f0, f1, q=1.0, peak=0.3, noise="pink", fpow=1.0):
    n = N(dur)
    src = pink(n, r) if noise == "pink" else white(n, r)
    f = sweep(n, f0, f1, power=fpow)
    y = tvfilt(src, "bp", f, q)
    return y * env_hump(n, peak, 2.0, 1.6)


def thud(dur, f0=100.0, f1=45.0, decay=0.08, r=None, click=0.3):
    n = N(dur)
    t = tvec(n)
    f = f1 + (f0 - f1) * np.exp(-t / 0.03)
    y = sine(f, n) * env_perc(n, 0.001, decay)
    if r is not None and click:
        y += click * lp(r.standard_normal(n), 1500) * np.exp(-t / 0.006)
    return y


def creak(dur, r, f=850.0, rough=38.0, level=1.0):
    """Suspension/spring squeak: stick-slip pulsed tone."""
    n = N(dur)
    t = tvec(n)
    ff = f * (1 + 0.06 * smooth_random(n, r, 6) + 0.1 * t / dur)
    am = (0.5 + 0.5 * np.sin(TAU * phase(rough * (1 + 0.2 * smooth_random(n, r, 5)), n))) ** 3
    y = additive(ff, n, lambda k, fk: 1.0 / k ** 1.2, kmax=6)
    return y * am * env_hump(n, 0.25, 1.5, 1.5) * level


def clicks(dur, r, count, decay_s=0.08, fc=3000, width=1.5):
    n = N(dur)
    out = np.zeros(n)
    times = r.exponential(decay_s, count)
    for t in times:
        if t >= dur:
            continue
        k = N(0.003)
        c = r.standard_normal(k) * np.exp(-tvec(k) / 0.0007) * r.uniform(0.3, 1.0)
        place(out, c, t)
    return band_filter(out, fc, width)


def band_filter(x, fc, width_oct=1.0):
    q = 1.0 / (2 * np.sinh(np.log(2) / 2 * width_oct))
    return bp(x, fc, q)


def bloop(dur, f0, f1, decay=0.06, r=None):
    """Cartoon water/bubble 'bloop' - rising sine chirp."""
    n = N(dur)
    t = tvec(n)
    f = f1 + (f0 - f1) * np.exp(-t / (dur * 0.3))
    return sine(f, n) * env_perc(n, 0.002, decay)


def squeal(dur, r, fc=1150.0, loop=False):
    """Tire squeal core (stick-slip tonal cluster + hiss)."""
    n = N(dur)
    y = np.zeros(n)
    for fc_i, lev, dev in ((fc, 1.0, 0.05), (fc * 1.5, 0.55, 0.06), (fc * 2.27, 0.25, 0.04)):
        m = periodic_lfo(n, r, 6, 10)
        jit = smooth_random(n, r, 30)
        f = fc_i * (1 + dev * m + 0.012 * jit)
        if loop:
            c = np.sum(f) / SR
            f *= round(c) / c
        am = (0.65 + 0.35 * smooth_random(n, r, 6)) * (1 + 0.35 * smooth_random(n, r, 45))
        y += lev * additive(f, n, lambda k, fk: [0, 1.0, 0.45, 0.2, 0.1][k], kmax=4) * am
    y /= rms(y)
    hiss = band_noise(n, r, 3500, 1.5) * (0.7 + 0.3 * smooth_random(n, r, 10))
    rumble = lp(brown(n, r), 300, circular=loop)
    return y + 0.3 * hiss + 0.25 * rumble / rms(rumble)


def fanfare_brass(notes, r, gain=1.0):
    """notes: [(t, dur, midi)] -> brass line (mono)."""
    end = max(t + d for t, d, _ in notes) + 0.3
    out = np.zeros(N(end))
    for t, d, m in notes:
        place(out, ins.brass(float(midi_hz(m)), round(d, 3), 1.1), t)
    return out * gain


# =========================================================================== engine
def pulse_train(f, n, r, jitter=0.12, tjit=0.012, misfire=0.0, tau_frac=0.22, wrap=True, amp=None):
    """Combustion pulses (one per cycle of f). Returns (excitation, noise-bursts, phase)."""
    ph = phase(f, n)
    if wrap:
        C = int(round(ph[-1] + f[-1] / SR))
        ks = np.arange(C)
    else:
        ks = np.arange(int(ph[-1]) + 1)
    pos = np.interp(ks, ph, np.arange(n, dtype=float))
    exc = np.zeros(n)
    nz = np.zeros(n)
    for k, p in zip(ks, pos):
        fi = f[min(int(p), n - 1)]
        per = SR / fi
        p = p + r.normal(0, tjit) * per
        a = max(0.15, 1 + jitter * r.standard_normal())
        if r.random() < misfire:
            a *= 0.2
        if amp is not None:
            a *= amp[min(max(int(p), 0), n - 1)]
        K = int(per * 1.6) + 8
        i0 = int(np.floor(p))
        frac = p - i0
        tk = np.maximum((np.arange(K) - frac) / SR, 0)
        taud = tau_frac / fi
        ker = np.exp(-tk / taud) - np.exp(-tk / 0.00012)
        ker -= 0.4 * (np.exp(-tk / (2.5 * taud)) - np.exp(-tk / (0.6 * taud)))
        burst = r.standard_normal(K) * np.exp(-tk / (0.45 * taud)) * r.uniform(0.4, 1.4)
        idx = i0 + np.arange(K)
        if wrap:
            idx %= n
        else:
            m = (idx >= 0) & (idx < n)
            idx, ker, burst = idx[m], ker[m], burst[m]
        exc[idx] += a * ker
        nz[idx] += a * burst
    return exc, nz, ph


def engine_voice(f, n, r, rough=0.15, bright=1.0, F1=380.0, F2=1150.0, loop=True, misfire=0.0, amp=None,
                 sub=0.3, noise=0.2, drive=1.8):
    """Pulse excitation -> exhaust/body resonances -> soft saturation (+ phase-locked sub)."""
    exc, nz, ph = pulse_train(f, n, r, jitter=rough, tjit=0.006 + 0.02 * rough, misfire=misfire,
                              wrap=loop, amp=amp)
    exc /= rms(exc)
    body = (0.35 * lp(exc, 1500, circular=loop) + 1.0 * bp(exc, F1, 1.5, circular=loop)
            + 0.8 * bright * bp(exc, F2, 2.0, circular=loop) + 0.35 * bright * bp(exc, 2.2 * F2, 2.5, circular=loop))
    body /= rms(body)
    nzf = bp(nz, 2200, 0.7, circular=loop)
    nzf /= rms(nzf)
    s = np.sin(TAU * ph) + 0.35 * np.sin(TAU * 2 * ph + 0.4)
    if amp is not None:
        s *= amp
    x = body + noise * bright * nzf + sub * s
    x = saturate(0.9 * x, drive)
    x = lp(x, 8000, circular=loop)
    return x


def engine_loop(f0, r, rough, bright, F1, F2, noise=0.2, sub=0.3, shelf_db=0.0):
    L = 2.0
    n = N(L)
    C = int(round(f0 * L))
    f0 = C / L
    f = f0 * (1 + 0.016 * periodic_lfo(n, r, 5, 6) + 0.006 * periodic_lfo(n, r, 4, 40))
    x = engine_voice(f, n, r, rough, bright, F1, F2, loop=True, noise=noise, sub=sub)
    return filt(x, "lowshelf", 140.0, 0.7, shelf_db, circular=True)


def engine_idle(r):
    return engine_loop(45.0, r, rough=0.28, bright=0.85, F1=330.0, F2=1000.0, noise=0.2, sub=0.2, shelf_db=-7.0)


def engine_mid(r):
    return engine_loop(90.0, r, rough=0.16, bright=1.0, F1=450.0, F2=1300.0, noise=0.22, sub=0.25, shelf_db=-2.0)


def engine_high(r):
    return engine_loop(160.0, r, rough=0.09, bright=1.15, F1=600.0, F2=1700.0, noise=0.26, sub=0.2)


# =========================================================================== loops
def drift_skid(r):
    return squeal(2.0, r, 1150.0, loop=True)


def wind_loop(r):
    n = N(4.0)
    gust = 0.55 + 0.45 * smooth_random(n, r, 0.8)
    low = lp(brown(n, r), 250, circular=True)
    mid = band_noise(n, r, 700, 2.0)
    hi = band_noise(n, r, 3500, 2.0)
    whistle = band_noise(n, r, 1300, 0.12) * (0.5 + 0.5 * smooth_random(n, r, 1.2))
    return 0.6 * low / rms(low) + 0.8 * mid * gust + 0.3 * hi * gust ** 2 + 0.12 * whistle


def boost_loop(r):
    n = N(2.0)
    roar = 0.9 * lp(brown(n, r), 900, circular=True)
    roar = roar / rms(roar) + 0.8 * band_noise(n, r, 320, 1.5)
    flick = 1 + 0.45 * smooth_random(n, r, 30)
    jet = 0.6 * band_noise(n, r, 1800, 1.6) * (1 + 0.2 * smooth_random(n, r, 20)) + 0.22 * band_noise(n, r, 6000, 1.2)
    crackle = np.zeros(n)
    for _ in range(70):
        k = N(0.002)
        place(crackle, r.standard_normal(k) * np.exp(-tvec(k) / 0.0005) * r.uniform(0.3, 1), r.random() * 2.0, wrap=True)
    crackle = hp(crackle, 1200, circular=True)
    whine = sine(880 * (1 + 0.004 * periodic_lfo(n, r, 3, 4)), n) * 0.5 + sine(1320, n) * 0.25
    x = roar * flick + jet + 0.9 * crackle / (np.abs(crackle).max() + 1e-9) + 0.06 * whine
    return saturate(0.6 * x, 1.4)


def bomb_fuse(r):
    n = N(1.5)
    sizz = band_noise(n, r, 6500, 1.2) * (0.35 + np.abs(smooth_random(n, r, 60))) ** 2
    hiss = band_noise(n, r, 3500, 1.5) * 0.3
    sparks = np.zeros(n)
    for _ in range(55):
        k = N(0.004)
        place(sparks, r.standard_normal(k) * np.exp(-tvec(k) / 0.0008) * r.uniform(0.2, 1), r.random() * 1.5, wrap=True)
    sparks = hp(sparks, 2500, circular=True)
    pops = np.zeros(n)
    for _ in range(7):
        p = ping(r.uniform(3500, 7000), 0.08, 0.015, 0.3, r)
        place(pops, p * r.uniform(0.2, 0.5), r.random() * 1.5, wrap=True)
    return sizz + hiss + 0.8 * sparks / (np.abs(sparks).max() + 1e-9) + pops


def item_roulette(r):
    n = N(1.0)
    out = np.zeros(n)
    notes = [84, 86, 88, 91, 93, 96] * 2
    for i, m in enumerate(notes):
        k = N(0.12)
        t = tvec(k)
        wood = modal(1900, k, [1.0, 2.1], [1.0, 0.4], [0.012, 0.006], r)
        blip = additive(midi_hz(m), k, lambda kk, fk: (1.0 / kk if kk % 2 else 0.25 / kk), kmax=6) * np.exp(-t / 0.03)
        tick = (0.5 * wood + 0.5 * blip) * onset(k, 0.5)
        place(out, tick * (1.0 if i % 2 == 0 else 0.8), i / 12.0, wrap=True)
    return out


# =========================================================================== drift / boost
def drift_tier(r, tier):
    base = {1: 76, 2: 81, 3: 86}[tier]
    steps = {1: [0, 4, 7], 2: [0, 4, 7, 12], 3: [0, 4, 7, 11, 14, 19]}[tier]
    dur = {1: 0.65, 2: 0.75, 3: 0.95}[tier]
    n = N(dur)
    out = np.zeros(n)
    t = tvec(n)
    # rising 'zwip'
    zn = N(0.13)
    zf = sweep(zn, midi_hz(base - 12), midi_hz(base + 12))
    z = triangle(zf, zn) * env_hump(zn, 0.6, 1.5, 1.2)
    place(out, 0.35 * z, 0.0)
    gap = {1: 0.045, 2: 0.04, 3: 0.034}[tier]
    bright = {1: 0.5, 2: 1.0, 3: 0.8}[tier]
    for i, s in enumerate(steps):
        f = midi_hz(base + s)
        p = ping(f, dur, 0.18, bright, r) + 0.7 * ping(f, dur, 0.16, bright, r, detune=9 if tier != 1 else 5)
        if tier == 2:  # warmer, orange: add a little brassy saw bite
            k = N(0.12)
            p = mix(p, 0.15 * saw(f, k) * env_perc(k, 0.002, 0.04))
        place(out, p * (0.7 + 0.3 * i / len(steps)), 0.08 + i * gap)
    shimmer = band_noise(n, r, 8000 + 1500 * tier, 1.0) * (0.5 + 0.5 * np.sin(TAU * 24 * t)) \
        * env_perc(n, 0.08, 0.15 + 0.05 * tier)
    out += 0.12 * shimmer
    out += sparkle(dur, r, 6 + 4 * tier, 88, 108, 0.1, dur * 0.5, 0.06, level=0.35)
    if tier == 3:  # purple: magical detuned chord swell + crackles
        chord = sum(sine(midi_hz(base + s - 12) * (1 + d), n) for s in (0, 7, 11) for d in (-0.003, 0.003))
        out += 0.08 * chord * env_hump(n, 0.25, 2, 2)
        out += 0.3 * clicks(dur, r, 40, 0.25, 5000, 2.0)
    return reverb(out, 0.9, 0.18, seed=11)


def drift_tier1(r):
    return drift_tier(r, 1)


def drift_tier2(r):
    return drift_tier(r, 2)


def drift_tier3(r):
    return drift_tier(r, 3)


def flame_burst(dur, r, decay=0.35, level=1.0):
    n = N(dur)
    roar = lp(brown(n, r), 1200) + 0.5 * band_noise(n, r, 450, 1.5)
    flick = 1 + 0.5 * smooth_random(n, r, 30)
    env = env_perc(n, 0.01, decay)
    crack = clicks(dur, r, 40, decay, 2500, 2.0)
    return (roar * flick / rms(roar) * 0.5 + 0.8 * norm(crack)) * env * level


def miniturbo(r):
    dur = 1.0
    n = N(dur)
    out = np.zeros(n)
    place(out, 0.9 * thud(0.3, 170, 60, 0.06, r, 0.5), 0.0)
    pop = hp(r.standard_normal(N(0.03)), 700) * np.exp(-tvec(N(0.03)) / 0.004)
    place(out, 0.6 * pop, 0.0)
    w = whoosh(0.8, r, 500, 3800, 1.3, 0.18, fpow=0.5)
    place(out, 0.9 * w / (np.abs(w).max() + 1e-9), 0.01)
    place(out, 0.55 * flame_burst(0.95, r, 0.3), 0.02)
    fe = sweep(N(0.6), 80, 190)
    rev = engine_voice(fe, N(0.6), r, 0.1, 1.2, 500, 1500, loop=False, amp=env_perc(N(0.6), 0.02, 0.2))
    place(out, 0.25 * rev, 0.0)
    return out


def boost_pad(r):
    dur = 0.95
    n = N(dur)
    out = np.zeros(n)
    w = whoosh(0.85, r, 800, 7000, 1.4, 0.25, noise="white", fpow=0.7)
    place(out, 0.8 * norm(w), 0.0)
    zn = N(0.22)
    zf = sweep(zn, 3200, 260)
    zap = fm(zf, zn, ratio=0.5, index=2.5 * np.exp(-tvec(zn) / 0.08)) * env_perc(zn, 0.001, 0.07)
    place(out, 0.7 * zap, 0.0)
    for i, m in enumerate([84, 88, 91, 96]):
        k = N(0.1)
        b = square(midi_hz(m), k, 0.3) * env_perc(k, 0.002, 0.03)
        place(out, 0.12 * lp(b, 6000), 0.03 + i * 0.03)
    out += sparkle(dur, r, 10, 90, 108, 0.08, 0.35, 0.07, level=0.35)
    return out


def rocket_start(r):
    dur = 1.9
    n = N(dur)
    out = np.zeros(n)
    rn = N(1.0)
    fe = np.concatenate([sweep(N(0.55), 70, 240), np.full(rn - N(0.55), 240.0)])
    amp = np.clip(tvec(rn) / 0.05, 0, 1) * np.exp(-np.maximum(tvec(rn) - 0.5, 0) / 0.2)
    rev = engine_voice(fe, rn, r, 0.08, 1.3, 520, 1500, loop=False, amp=amp)
    place(out, 0.45 * rev, 0.0)
    place(out, 1.0 * thud(1.0, 120, 38, 0.25, r, 0.6), 0.45)
    blast = lp(brown(N(1.2), r), 3000) * env_perc(N(1.2), 0.005, 0.25)
    place(out, 0.5 * blast / (np.abs(blast).max() + 1e-9), 0.45)
    w = whoosh(1.1, r, 300, 4500, 1.1, 0.3, fpow=0.6)
    place(out, 0.8 * norm(w), 0.42)
    place(out, 0.6 * flame_burst(1.4, r, 0.5), 0.45)
    out += sparkle(dur, r, 14, 88, 108, 0.5, 0.6, 0.08, level=0.3)
    return reverb(out, 1.2, 0.12, seed=3)


def burnout(r):
    dur = 1.7
    n = N(dur)
    out = np.zeros(n)
    en = N(1.15)
    fe = sweep(en, 58, 20)
    amp = np.clip(tvec(en) / 0.02, 0, 1) * np.linspace(1, 0.3, en)
    sput = engine_voice(fe, en, r, rough=0.45, bright=0.8, F1=320, F2=1000, loop=False, misfire=0.35, amp=amp)
    place(out, 0.6 * sput, 0.0)
    for i, t0 in enumerate((0.18, 0.5, 0.82, 1.2)):
        k = N(0.25)
        puff = bp(r.standard_normal(k), 900 - 120 * i, 1.0) * env_perc(k, 0.006, 0.06)
        place(out, puff * (0.9 - 0.15 * i), t0)
    bang = thud(0.25, 200, 70, 0.04, r, 0.8) + 0.6 * bp(r.standard_normal(N(0.25)), 1500, 1.0) * env_perc(N(0.25), 0.001, 0.015)
    place(out, 0.8 * bang, 1.0)
    k = N(0.6)
    hiss = hp(r.standard_normal(k), 3500) * env_perc(k, 0.03, 0.18)
    place(out, 0.25 * hiss, 1.08)
    return out


# =========================================================================== movement / impacts
def hop(r):
    n = N(0.4)
    t = tvec(n)
    f = 260 * (1 + 0.7 * (1 - np.exp(-t / 0.05)))
    f = f * (1 + 0.10 * np.exp(-t / 0.12) * np.sin(TAU * 22 * t))
    y = additive(f, n, lambda k, fk: 1.0 / k ** 1.5 * lowpass_resp(fk, 2500), kmax=8) * env_perc(n, 0.003, 0.12)
    tw = modal(900, n, [1, 2.3, 3.7], [0.3, 0.2, 0.1], [0.05, 0.03, 0.02], r)
    th = lp(r.standard_normal(n), 600) * np.exp(-t / 0.01)
    return y + tw + 0.3 * th


def knock(dur, r, fc=220.0, decay=0.03):
    k = N(dur)
    body = modal(fc, k, [1.0, 1.6, 2.3], [1.0, 0.5, 0.25], [decay, decay * 0.6, decay * 0.4], r) * onset(k, 0.5)
    return body + 0.5 * bp(r.standard_normal(k), fc * 2, 1.0) * env_perc(k, 0.001, decay * 0.5)


def land(r):
    out = np.zeros(N(0.5))
    place(out, thud(0.45, 120, 55, 0.06, r, 0.5), 0.0)
    place(out, 0.7 * knock(0.2, r, 210, 0.035), 0.0)
    place(out, 0.3 * norm(creak(0.2, r, 820, 36)), 0.05)
    place(out, 0.2 * norm(clicks(0.2, r, 10, 0.05, 2500)), 0.01)
    return out


def land_big(r):
    out = np.zeros(N(0.95))
    place(out, 1.2 * thud(0.8, 160, 45, 0.13, r, 0.8), 0.0)
    place(out, 0.8 * knock(0.3, r, 170, 0.05), 0.0)
    k = N(0.3)
    crunch = bp(r.standard_normal(k), 800, 0.8) * env_perc(k, 0.001, 0.07)
    place(out, 0.6 * crunch, 0.0)
    kn = N(0.45)
    tt = tvec(kn)
    sf = 180 * (1 + 0.6 * (1 - np.exp(-tt / 0.06))) * (1 + 0.12 * np.exp(-tt / 0.15) * np.sin(TAU * 15 * tt))
    spring = additive(sf, kn, lambda kk, fk: 1.0 / kk ** 1.4, kmax=8) * env_perc(kn, 0.004, 0.14)
    place(out, 0.35 * spring, 0.04)
    place(out, 0.3 * norm(creak(0.35, r, 700, 30)), 0.1)
    place(out, 0.35 * norm(clicks(0.5, r, 25, 0.12, 2200)), 0.02)
    return out


def bump_wall(r):
    out = np.zeros(N(0.6))
    place(out, 0.9 * thud(0.3, 150, 60, 0.05, r, 0.6), 0.0)
    k = N(0.2)
    place(out, 0.7 * bp(r.standard_normal(k), 1500, 0.8) * env_perc(k, 0.001, 0.04), 0.0)
    place(out, 0.5 * norm(clicks(0.25, r, 30, 0.05, 2800, 2.0)), 0.0)
    kn = N(0.55)
    ring = modal(520, kn, [1, 1.62, 2.33, 3.06, 4.4], [0.8, 0.6, 0.5, 0.35, 0.2], [0.22, 0.16, 0.12, 0.09, 0.06], r)
    place(out, 0.35 * ring * onset(kn), 0.0)
    kb = N(0.15)
    bonk = sine(sweep(kb, 720, 380), kb) * env_perc(kb, 0.002, 0.05)
    place(out, 0.35 * bonk, 0.005)
    return out


def bump_kart(r):
    n = N(0.4)
    t = tvec(n)
    f = 200 + 240 * np.exp(-t / 0.04)
    y = additive(f, n, lambda k, fk: 1.0 / k * lowpass_resp(fk, 1600), kmax=12) * env_perc(n, 0.002, 0.09)
    y = y + 1.2 * bp(y, 800, 2.5)
    y += 0.8 * thud(0.4, 120, 60, 0.05, r, 0.4)
    kq = N(0.08)
    sq = sine(1250 * (1 + 0.05 * np.sin(TAU * 40 * tvec(kq))), kq) * env_hump(kq, 0.3)
    out = pad_to(y, n)
    place(out, 0.12 * sq, 0.02)
    return out


# =========================================================================== items
def item_box(r):
    dur = 1.0
    out = np.zeros(N(dur))
    for _ in range(45):
        t0 = r.exponential(0.06)
        if t0 > 0.5:
            continue
        f = r.uniform(2500, 9000)
        k = N(0.2)
        s = modal(f, k, [1.0, 2.32, 4.25], [1.0, 0.5, 0.25], [r.uniform(0.02, 0.1)] * 3, r) * onset(k, 0.3)
        place(out, s * r.uniform(0.1, 0.35), t0)
    k = N(0.3)
    crash = hp(r.standard_normal(k), 2500) * env_perc(k, 0.001, 0.07)
    place(out, 0.5 * crash, 0.0)
    for i, m in enumerate([84, 86, 88, 91, 93, 96]):
        place(out, 0.5 * ping(midi_hz(m), 0.6, 0.15, 0.6, r) + 0.3 * ping(midi_hz(m), 0.6, 0.13, 0.6, r, 10), 0.08 + i * 0.035)
    out += sparkle(dur, r, 12, 91, 108, 0.1, 0.4, 0.07, level=0.3)
    return reverb(out, 1.0, 0.18, seed=5)


def item_get(r):
    out = np.zeros(N(1.0))
    for i, m in enumerate([84, 91, 96]):
        f = midi_hz(m)
        b = ping(f, 0.9, 0.32, 0.9, r) + 0.5 * ping(f, 0.9, 0.3, 0.9, r, 6)
        b += 0.2 * fm(f, len(b), 3.5, 1.2 * np.exp(-tvec(len(b)) / 0.05)) * env_perc(len(b), 0.001, 0.1)
        place(out, b * (0.7 + 0.15 * i), i * 0.06)
    out += sparkle(1.0, r, 8, 96, 108, 0.12, 0.3, 0.06, level=0.25)
    return reverb(out, 1.0, 0.15, seed=9)


def coin(r):
    out = np.zeros(N(0.6))
    for t0, m, dur, dec in ((0.0, 83, 0.08, 0.05), (0.075, 88, 0.5, 0.17)):
        f = midi_hz(m)
        k = N(dur)
        tone = square(f, k, 0.3) * env_perc(k, 0.002, dec)
        tone = lp(tone, 7000)
        bell = ping(f * 2, dur, dec * 1.2, 0.5, r)
        place(out, 0.45 * tone + 0.35 * bell, t0)
    out += sparkle(0.6, r, 4, 100, 108, 0.1, 0.2, 0.05, level=0.25)
    return reverb(out, 0.7, 0.1, seed=4)


def banana_drop(r):
    out = np.zeros(N(0.45))
    place(out, bloop(0.25, 170, 420, 0.07), 0.0)
    k = N(0.2)
    sq = tvfilt(r.standard_normal(k), "bp", curve(k, [(0, 600), (0.05, 1500), (0.2, 400)], "exp"), 3.0)
    place(out, 0.5 * sq * env_hump(k, 0.2), 0.01)
    place(out, 0.3 * bloop(0.12, 500, 900, 0.03), 0.09)
    return out


def banana_slip(r):
    out = np.zeros(N(1.05))
    k = N(0.25)
    sq = tvfilt(r.standard_normal(k), "bp", curve(k, [(0, 400), (0.08, 2000), (0.25, 500)], "exp"), 4.0)
    place(out, 0.7 * sq * env_hump(k, 0.25), 0.0)
    place(out, 0.5 * bloop(0.2, 200, 500, 0.06), 0.0)
    kw = N(0.45)
    tw = tvec(kw)
    wf = sweep(kw, 420, 1600) * (1 + 0.03 * np.sin(TAU * 9 * tw))
    whee = additive(wf, kw, lambda kk, fk: 1.0 / kk ** 2, kmax=4) * env_hump(kw, 0.3)
    place(out, 0.35 * whee, 0.12)
    s = squeal(0.6, r, 1300) * env_hump(N(0.6), 0.15, 1.2, 1.5)
    place(out, 0.18 * s, 0.2)
    return out


def bomb_throw(r):
    out = np.zeros(N(0.55))
    k = N(0.45)
    f = curve(k, [(0, 500), (0.18, 2600), (0.45, 800)], "exp")
    w = tvfilt(pink(k, r), "bp", f, 1.5) * env_hump(k, 0.35)
    place(out, norm(w), 0.0)
    kf = N(0.1)
    place(out, 0.35 * sine(sweep(kf, 900, 300), kf) * env_perc(kf, 0.002, 0.03), 0.0)
    kh = N(0.4)
    place(out, 0.1 * band_noise(kh, r, 6500, 1.2) * env_hump(kh, 0.2), 0.12)
    return out


def explosion(r):
    dur = 2.2
    n = N(dur)
    out = np.zeros(n)
    kb = N(1.6)
    tb = tvec(kb)
    boom = sine(28 + 70 * np.exp(-tb / 0.12), kb) * env_perc(kb, 0.002, 0.45)
    place(out, 1.0 * saturate(1.5 * boom), 0.0)
    kn = N(1.2)
    blast = tvfilt(brown(kn, r) + 0.3 * white(kn, r), "lp", sweep(kn, 7000, 250), 0.8) * env_perc(kn, 0.002, 0.3)
    place(out, 0.8 * norm(blast), 0.0)
    kc = N(0.05)
    place(out, 0.4 * hp(r.standard_normal(kc), 1000) * np.exp(-tvec(kc) / 0.008), 0.0)
    km = N(0.9)
    crunch = band_noise(km, r, 450, 2.0) * (1 + 0.5 * smooth_random(km, r, 25)) * env_perc(km, 0.003, 0.18)
    place(out, 0.7 * crunch / (np.abs(crunch).max() + 1e-9), 0.0)
    kr = N(2.0)
    rumble = lp(brown(kr, r), 200) * env_perc(kr, 0.05, 0.6)
    place(out, 0.5 * norm(rumble), 0.02)
    for _ in range(45):
        t0 = 0.15 + r.exponential(0.35)
        if t0 > dur - 0.2:
            continue
        k = N(0.12)
        deb = modal(r.uniform(600, 3000), k, [1, 1.7, 2.6], [1, .6, .3], [0.02, 0.015, 0.01], r) * onset(k, 0.3)
        place(out, deb * r.uniform(0.05, 0.25), t0)
    return reverb(out, 1.8, 0.22, seed=13)


def spin_out(r):
    dur = 1.35
    out = np.zeros(N(dur))
    k = N(1.1)
    t = tvec(k)
    f = sweep(k, 1700, 360) * (1 + 0.03 * np.sin(TAU * 7 * t))
    tone = additive(f, k, lambda kk, fk: [0, 1.0, 0.15, 0.05][kk], kmax=3)
    br = tvfilt(white(k, r), "bp", f, 6.0) * 0.4
    wob = 0.75 + 0.25 * np.sin(TAU * 6 * t)
    place(out, 0.6 * (tone + br) * wob * env_hump(k, 0.05, 1.0, 0.8), 0.03)
    s = squeal(0.45, r, 1250) * env_hump(N(0.45), 0.1, 1, 1.5)
    place(out, 0.15 * s, 0.0)
    for t0 in (0.95, 1.08, 1.2):
        kc = N(0.05)
        place(out, 0.12 * sine(sweep(kc, 2800, 3600), kc) * env_hump(kc, 0.3), t0)
    return out


# =========================================================================== race flow / jingles
def tone_beep(freq, dur, hold):
    n = N(dur)
    t = tvec(n)
    y = additive(freq, n, lambda k, fk: [0, 1.0, 0.35, 0.2, 0.1][k], kmax=4)
    env = np.clip(t / 0.003, 0, 1) * np.where(t < hold, 1.0, np.exp(-(t - hold) / 0.05))
    return y * env


def countdown_beep(r):
    return reverb(tone_beep(880.0, 0.4, 0.2), 0.6, 0.08, seed=2)


def countdown_go(r):
    n = N(1.1)
    y = np.zeros(n)
    for m, g in ((81, 0.6), (88, 0.5), (93, 0.7)):
        y += g * pad_to(tone_beep(float(midi_hz(m)), 0.95, 0.55), n)
    y += sparkle(1.1, r, 12, 93, 108, 0.05, 0.5, 0.08, level=0.3)
    w = whoosh(0.5, r, 1000, 6000, 1.2, 0.2, fpow=0.6)
    y += 0.2 * pad_to(norm(w), n)
    return reverb(y, 1.0, 0.12, seed=2)


def lap(r):
    out = np.zeros(N(1.2))
    for i, m in enumerate([79, 83, 86, 91]):
        f = float(midi_hz(m))
        place(out, mix(0.6 * ins.steel_drum(f, 0.3 if i < 3 else 0.6), 0.4 * ins.marimba(f)), i * 0.07)
    place(out, 0.3 * ping(midi_hz(98), 0.8, 0.25, 0.8, r), 0.21)
    place(out, 0.6 * ins.triangle_perc(True), 0.21)
    return reverb(out, 1.0, 0.15, seed=6)


def final_lap(r):
    out = np.zeros(N(2.2))
    notes = [(0.0, 0.11, 72), (0.14, 0.11, 72), (0.28, 0.11, 72), (0.42, 1.0, 79)]
    place(out, fanfare_brass(notes, r), 0.0)
    for m in (64, 67, 72):
        place(out, 0.55 * ins.brass(float(midi_hz(m)), 1.0, 0.9), 0.42)
    for t0, m in ((0.0, 84), (0.14, 84), (0.28, 84), (0.42, 91)):
        place(out, 0.3 * ins.steel_drum(float(midi_hz(m)), 0.2 if m == 84 else 0.8), t0)
    place(out, 0.35 * ins.snare_roll(0.4, 26, 0.2, 0.8), 0.0)
    place(out, 0.7 * ins.crash(), 0.42)
    place(out, 0.8 * ins.timpani(65.4), 0.42)
    place(out, 0.8 * ins.kick(), 0.42)
    return reverb(out, 1.4, 0.18, seed=8)


def pea_whistle(dur, r):
    n = N(dur)
    t = tvec(n)
    trill = smooth_random(n, r, 40) * 0.5 + 0.5 * np.sin(TAU * 32 * t)
    f = 3000 * (1 + 0.03 * trill)
    y = sine(f, n) + 0.2 * sine(2 * f, n)
    y *= (0.7 + 0.3 * trill) * np.clip(t / 0.01, 0, 1) * np.clip((dur - t) / 0.03, 0, 1)
    y += 0.15 * bp(white(n, r), 3000, 2.0)
    return y


def finish(r):
    out = np.zeros(N(2.8))
    place(out, 0.35 * pea_whistle(0.16, r), 0.0)
    place(out, 0.35 * pea_whistle(0.55, r), 0.24)
    notes = [(0.85, 0.1, 67), (0.97, 0.1, 71), (1.09, 0.1, 74), (1.21, 1.2, 79)]
    place(out, fanfare_brass(notes, r), 0.0)
    for m in (67, 71, 74):
        place(out, 0.5 * ins.brass(float(midi_hz(m)), 1.2, 1.0), 1.21)
    for t0, d, m in notes:
        place(out, 0.3 * ins.steel_drum(float(midi_hz(m + 12)), d + 0.2), t0)
    place(out, 0.3 * ins.snare_roll(0.36, 26, 0.3, 0.9), 0.85)
    place(out, 0.7 * ins.crash(), 1.21)
    place(out, 0.8 * ins.timpani(49.0), 1.21)
    place(out, sparkle(1.4, r, 16, 91, 108, 0.0, 0.8, 0.09, level=0.25), 1.21)
    return reverb(out, 1.5, 0.18, seed=10)


def wrong_way(r):
    out = np.zeros(N(0.9))
    for t0 in (0.0, 0.42):
        k = N(0.32)
        t = tvec(k)
        y = square(196, k) + square(207.65, k)
        y = lp(y, 1400, order=2) * np.clip(t / 0.012, 0, 1) * np.clip((0.3 - t) / 0.04, 0, 1)
        place(out, 0.4 * y, t0)
    return out


def trick(r):
    out = np.zeros(N(0.75))
    w = whoosh(0.4, r, 400, 2600, 1.2, 0.45)
    place(out, 0.8 * norm(w), 0.0)
    for t0, m in ((0.2, 96), (0.26, 103)):
        place(out, 0.4 * ping(midi_hz(m), 0.5, 0.18, 0.7, r) + 0.25 * ping(midi_hz(m), 0.5, 0.16, 0.7, r, 8), t0)
    out += sparkle(0.75, r, 8, 96, 108, 0.22, 0.25, 0.06, level=0.25)
    return reverb(out, 0.9, 0.12, seed=12)


def splash(r):
    dur = 1.3
    out = np.zeros(N(dur))
    place(out, 0.6 * thud(0.4, 120, 50, 0.07, r, 0.3), 0.0)
    k = N(0.8)
    body = tvfilt(white(k, r), "bp", sweep(k, 3000, 900), 0.7) * env_perc(k, 0.005, 0.2)
    place(out, 0.7 * norm(body), 0.0)
    kh = N(1.0)
    hiss = lp(hp(white(kh, r), 2500), 9000) * env_perc(kh, 0.02, 0.35)
    place(out, 0.25 * hiss, 0.02)
    for _ in range(40):
        t0 = 0.04 + r.exponential(0.25)
        if t0 > dur - 0.1:
            continue
        f0 = r.uniform(800, 2500)
        kd = N(r.uniform(0.015, 0.035))
        d = sine(sweep(kd, f0, f0 * 1.8), kd) * env_perc(kd, 0.001, 0.008)
        place(out, d * r.uniform(0.08, 0.3), t0)
    return out


def respawn(r):
    out = np.zeros(N(1.05))
    k = N(0.6)
    t = tvec(k)
    rise = sine(sweep(k, 300, 1200) * (1 + 0.01 * np.sin(TAU * 18 * t)), k) * env_hump(k, 0.8, 1.5, 1.0)
    rise *= 0.7 + 0.3 * np.sin(TAU * 16 * t)
    place(out, 0.25 * rise, 0.0)
    for i, m in enumerate([72, 76, 79, 84, 88, 91, 96, 100]):
        place(out, 0.35 * ping(midi_hz(m), 0.5, 0.12, 0.6, r), 0.05 + i * 0.06)
    place(out, 0.6 * bloop(0.15, 300, 900, 0.05), 0.55)
    kp = N(0.03)
    place(out, 0.3 * lp(r.standard_normal(kp), 3000) * np.exp(-tvec(kp) / 0.004), 0.55)
    out += sparkle(1.05, r, 10, 93, 108, 0.55, 0.3, 0.07, level=0.3)
    return reverb(out, 1.1, 0.18, seed=14)


# =========================================================================== UI
def ui_move(r):
    n = N(0.07)
    t = tvec(n)
    y = sine(1400 + 300 * np.exp(-t / 0.01), n) * env_perc(n, 0.001, 0.012)
    y += 0.2 * lp(r.standard_normal(n), 4000) * np.exp(-t / 0.001)
    return y


def two_blip(m1, m2, gap=0.06, dec2=0.06):
    out = np.zeros(N(0.25))
    for t0, m, dec in ((0.0, m1, 0.03), (gap, m2, dec2)):
        k = N(0.16)
        b = additive(midi_hz(m), k, lambda kk, fk: (1.0 / kk if kk % 2 else 0.3 / kk), kmax=7) * env_perc(k, 0.002, dec)
        place(out, b, t0)
    return out


def ui_select(r):
    return reverb(two_blip(88, 95), 0.5, 0.08, seed=1)


def ui_back(r):
    return reverb(two_blip(83, 76, 0.055, 0.05), 0.5, 0.08, seed=1)


def ui_swap_part(r):
    out = np.zeros(N(0.55))
    for i in range(4):
        k = N(0.05)
        c = modal(2200 - 100 * i, k, [1.0, 1.9], [1.0, 0.4], [0.008, 0.005], r) + 0.5 * hp(r.standard_normal(k), 2000) * np.exp(-tvec(k) / 0.0015)
        place(out, 0.5 * c * onset(k, 0.3), i * 0.035)
    place(out, 0.8 * bloop(0.1, 300, 800, 0.04), 0.16)
    place(out, 0.7 * thud(0.15, 220, 90, 0.04, r, 0.4), 0.16)
    place(out, 0.3 * ping(midi_hz(91), 0.35, 0.12, 0.7, r), 0.18)
    return out


def ui_color(r):
    out = np.zeros(N(0.65))
    k = N(0.2)
    sp = tvfilt(white(k, r), "bp", sweep(k, 2200, 450), 2.0) * env_perc(k, 0.002, 0.06)
    place(out, 0.8 * norm(sp), 0.0)
    place(out, 0.4 * bloop(0.1, 250, 600, 0.03), 0.0)
    for t0 in (0.05, 0.09, 0.14):
        place(out, 0.2 * bloop(0.06, r.uniform(600, 1100), r.uniform(1400, 2000), 0.015), t0)
    out += sparkle(0.65, r, 10, 91, 108, 0.1, 0.3, 0.07, level=0.35)
    return out


def ui_start(r):
    out = np.zeros(N(1.4))
    w = whoosh(0.3, r, 300, 5000, 1.2, 0.8, fpow=0.8)
    place(out, 0.6 * norm(w), 0.0)
    for m in (60, 64, 67, 72):
        place(out, 0.4 * ins.brass(float(midi_hz(m)), 0.5, 1.2), 0.25)
    for m in (84, 88, 91):
        place(out, 0.35 * ins.steel_drum(float(midi_hz(m)), 0.5), 0.25)
    place(out, 0.5 * ins.crash(), 0.25)
    place(out, 0.7 * ins.kick(), 0.25)
    place(out, sparkle(1.0, r, 14, 91, 108, 0.0, 0.5, 0.08, level=0.3), 0.25)
    return reverb(out, 1.3, 0.15, seed=15)


# =========================================================================== crowd & ambience
def crowd_person(dur, r, f0, vowels, excited=1.0, fmax=3800.0, attack=0.08):
    n = N(dur)
    t = tvec(n)
    arc = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7
    f = f0 * (1 + 0.25 * excited * arc) * (1 + 0.02 * smooth_random(n, r, 6))
    ts = np.linspace(0, dur, len(vowels))
    F, B, A = vowel_tracks(n, list(zip(ts, vowels)), r.uniform(0.95, 1.2))
    v = formant_voice(f, n, F, B, A, tilt=1.4, jitter=0.01, r=r, kmax=max(3, int(fmax / f0)))
    env = np.clip(t / attack, 0, 1) * np.clip((dur - t) / (0.4 * dur), 0, 1) ** 1.5
    return v / rms(v) * env


def claps(dur, r, clappers=20, rate=4.2, env=None):
    n = N(dur)
    out = np.zeros(n)
    for _ in range(clappers):
        t0 = r.random() * 0.3
        rr = rate * r.uniform(0.8, 1.2)
        tt = t0
        fc = r.uniform(900, 2200)
        while tt < dur:
            k = N(0.03)
            c = bp(r.standard_normal(k), fc, 1.2) * np.exp(-tvec(k) / 0.006)
            g = 1.0 if env is None else env[min(n - 1, N(tt))]
            place(out, c * g * r.uniform(0.5, 1), tt)
            tt += 1 / rr + r.normal(0, 0.01)
    return out


def crowd_cheer(r):
    dur = 2.6
    n = N(dur)
    out = np.zeros(n)
    for _ in range(44):
        f0 = r.choice([r.uniform(110, 170), r.uniform(190, 300)])
        d = r.uniform(0.8, 1.9)
        vw = [str(v) for v in r.choice(["e", "a", "o", "u", "ae", "i"], 3)]
        v = crowd_person(d, r, f0, vw, excited=r.uniform(0.6, 1.3))
        place(out, v * r.uniform(0.3, 1.0), r.uniform(0.0, 0.35))
    env = np.clip(tvec(n) / 0.15, 0, 1) * np.exp(-np.maximum(tvec(n) - 0.8, 0) / 0.9)
    out = out / rms(out) * env
    cl = claps(dur, r, 26, 4.5, env)
    out += 0.9 * cl / rms(cl) * env
    for t0 in (0.2, 0.7):
        k = N(0.45)
        tw = tvec(k)
        wf = curve(k, [(0, 2200), (0.12, 2900), (0.3, 2700), (0.45, 2300)], "exp") * (1 + 0.01 * np.sin(TAU * 6 * tw))
        place(out, 0.5 * sine(wf, k) * env_hump(k, 0.2, 1.2, 1.5), t0)
    bed = lp(pink(n, r), 2000) * env
    out += 0.5 * bed / rms(bed)
    out = hp(out, 150)
    return reverb(out, 1.4, 0.25, seed=21)


def crowd_loop(r):
    L = 6.0
    n = N(L)
    out = np.zeros(n)
    vowels_all = ["a", "e", "i", "o", "u", "@", "ae"]
    for _ in range(34):
        span = r.uniform(1.2, 3.5)
        f0 = r.choice([r.uniform(100, 150), r.uniform(180, 260)])
        k = N(span)
        tt = tvec(k)
        syl = r.uniform(0.13, 0.28)
        nsyl = int(span / syl)
        seq = [(i * syl, vowels_all[r.integers(len(vowels_all))]) for i in range(nsyl + 1)]
        F, B, A = vowel_tracks(k, seq, r.uniform(0.95, 1.15))
        f = f0 * (1 + 0.12 * smooth_random(k, r, 3) + 0.04 * np.sin(TAU * tt / syl))
        v = formant_voice(f, k, F, B, A, tilt=1.5, jitter=0.01, r=r, kmax=max(3, int(3000 / f0)))
        gate = (0.35 + 0.65 * np.abs(np.sin(np.pi * tt / syl)) ** 1.5) * np.clip(tt / 0.1, 0, 1) * np.clip((span - tt) / 0.2, 0, 1)
        place(out, v / rms(v) * gate * r.uniform(0.2, 1.0), r.random() * L, wrap=True)
    out /= rms(out)
    bed = lp(pink(n, r), 1200, circular=True) * (0.8 + 0.2 * smooth_random(n, r, 0.5))
    out += 0.7 * bed / rms(bed)
    for t0 in (1.1, 4.3):
        k = N(1.2)
        swell = crowd_person(1.2, r, 150, ["o", "o"], 0.8) * 0.3
        place(out, swell, t0, wrap=True)
    cl = np.zeros(n)
    for _ in range(40):
        k = N(0.03)
        place(cl, bp(r.standard_normal(k), r.uniform(900, 2000), 1.2) * np.exp(-tvec(k) / 0.006) * r.uniform(0.2, 0.6),
              r.random() * L, wrap=True)
    out += 0.6 * cl / (rms(cl) + 1e-9) * 0.3
    out = hp(lp(out, 3200, circular=True), 150, circular=True)
    return reverb(out, 1.2, 0.3, seed=22, loop=True)


def waves_loop(r):
    L = 8.0
    n = N(L)
    out = np.zeros(n)
    bed = lp(brown(n, r), 400, circular=True)
    out += 0.45 * bed / rms(bed) * (0.8 + 0.2 * smooth_random(n, r, 0.3))
    for t0 in (0.3 + r.uniform(-0.1, 0.1), 3.0 + r.uniform(-0.2, 0.2), 5.6 + r.uniform(-0.2, 0.2)):
        k = N(4.2)
        t = tvec(k)
        swell = lp(brown(k, r), 300) * np.clip(t / 1.1, 0, 1) ** 2 * np.exp(-np.maximum(t - 1.1, 0) / 0.4)
        crash = hp(lp(pink(k, r), 3000), 150) * np.where(t < 1.0, 0, np.clip((t - 1.0) / 0.1, 0, 1) * np.exp(-np.maximum(t - 1.1, 0) / 0.6))
        fizz_am = np.abs(smooth_random(k, r, 40))
        fizz = lp(hp(white(k, r), 1500), 7000) * np.where(t < 1.1, 0, np.clip((t - 1.1) / 0.3, 0, 1)
                                                          * np.exp(-np.maximum(t - 1.4, 0) / 1.2)) * (0.4 + fizz_am)
        wave = 0.6 * swell / rms(swell) + 0.8 * crash / rms(crash) + 0.35 * fizz / rms(fizz)
        wave = fade(wave, 0.0, 0.5)
        place(out, wave * r.uniform(0.8, 1.0), t0, wrap=True)
    return out


def bird_whistle(r, notes, dur_each=0.14, gap=0.04, vib=0.02):
    total = len(notes) * (dur_each + gap) + 0.1
    out = np.zeros(N(total))
    for i, (fa, fb) in enumerate(notes):
        k = N(dur_each)
        t = tvec(k)
        f = sweep(k, fa, fb) * (1 + vib * np.sin(TAU * 30 * t))
        s = (sine(f, k) + 0.1 * sine(2 * f, k)) * env_hump(k, 0.3, 1.2, 1.5)
        place(out, s, i * (dur_each + gap))
    return out


def jungle_loop(r):
    L = 8.0
    n = N(L)
    t = tvec(n)
    out = np.zeros(n)
    cic = band_noise(n, r, 5800, 0.25) * (0.5 + 0.5 * np.sin(TAU * 48 * t)) ** 3
    cic *= 0.4 + 0.6 * (0.5 + 0.5 * periodic_lfo(n, r, 2, 2))
    out += 0.25 * cic / rms(cic)
    for period, f, off in ((0.5, 4300, 0.1), (0.8, 3900, 0.37)):
        tt = off
        while tt < L:
            for j in range(3):
                k = N(0.018)
                place(out, 0.06 * sine(f, k) * env_hump(k, 0.3), tt + j * 0.035, wrap=True)
            tt += period
    events = [
        (0.6, bird_whistle(r, [(2400, 2500), (2900, 2950), (3300, 2700)], 0.12, 0.05)),
        (4.4, bird_whistle(r, [(2400, 2500), (2900, 2950), (3300, 2700)], 0.12, 0.05)),
        (2.2, bird_whistle(r, [(r.uniform(3500, 5000), r.uniform(2500, 3000)) for _ in range(10)], 0.025, 0.035, 0.0)),
        (6.3, bird_whistle(r, [(r.uniform(3500, 5000), r.uniform(2500, 3000)) for _ in range(8)], 0.025, 0.04, 0.0)),
        (3.4, bird_whistle(r, [(1800, 2600), (2600, 1500)], 0.18, 0.08, 0.01)),
    ]
    for t0, s in events:
        place(out, 0.3 * s, t0, wrap=True)
    for t0 in (1.5, 5.2):  # distant dove coo
        k = N(0.5)
        tk = tvec(k)
        coo = additive(curve(k, [(0, 480), (0.15, 560), (0.5, 450)], "exp"), k, lambda kk, fk: 1 / kk ** 2, kmax=4)
        coo *= np.sin(np.pi * tk / 0.5) ** 2 * (0.6 + 0.4 * np.sin(TAU * 4 * tk))
        place(out, 0.12 * coo, t0, wrap=True)
    k = N(0.3)
    sq = saw(curve(k, [(0, 700), (0.1, 950), (0.3, 800)], "exp"), k) * (0.6 + 0.4 * np.sin(TAU * 60 * tvec(k)))
    sq = bp(sq, 1800, 1.2) * env_hump(k, 0.2)
    place(out, 0.1 * sq, 7.0, wrap=True)
    leaves = lp(hp(pink(n, r), 1500, circular=True), 6000, circular=True) * (0.5 + 0.5 * smooth_random(n, r, 0.5)) ** 2
    out += 0.08 * leaves / rms(leaves)
    return reverb(out, 1.3, 0.25, seed=23, loop=True)


# =========================================================================== character voice (Guara pup)
def pup(dur, r, f0_pts, vowels, amp_pts, breath_pts=None, scale=1.3, tilt=1.15, vib_rate=6.0, vib_depth=0.015,
        rough=0.0, breath_gain=0.6):
    n = N(dur)
    t = tvec(n)
    f0 = curve(n, f0_pts, "exp")
    f0 = f0 * (1 + vib_depth * np.sin(TAU * phase(vib_rate, n)) * np.clip(t / 0.12, 0, 1))
    F, B, A = vowel_tracks(n, vowels, scale)
    v = formant_voice(f0, n, F, B, A, tilt=tilt, jitter=0.004, r=r)
    if rough:
        v = v * (1 + rough * np.sin(TAU * phase(f0 * 0.5, n)))
    v = v / rms(v)
    y = v * curve(n, amp_pts)
    if breath_pts is not None:
        br = hp(formant_noise(white(n, r), F, B, A), 400)
        y += breath_gain * br / rms(br) * curve(n, breath_pts)
    return filt(y, "peak", 2800, 1.0, 2.5)


def burst(dur, r, lo, hi, decay, attack=0.003):
    k = N(dur)
    return lp(hp(white(k, r), lo), hi) * env_perc(k, attack, decay)


def voice_yip(r):
    y = pup(0.32, r, [(0, 620), (0.035, 900), (0.12, 980), (0.22, 760), (0.32, 640)],
            [(0, "i"), (0.05, "e"), (0.2, "e"), (0.32, "i")],
            [(0, 0), (0.02, 0.8), (0.05, 1.0), (0.18, 0.9), (0.21, 0.0), (0.32, 0)],
            [(0, 0.1), (0.2, 0.1), (0.21, 0), (0.32, 0)])
    place(y, 0.15 * burst(0.04, r, 200, 1800, 0.008), 0.225)
    return y


def voice_yahoo(r):
    return pup(0.85, r, [(0, 430), (0.08, 520), (0.25, 500), (0.33, 560), (0.45, 780), (0.6, 820), (0.85, 690)],
               [(0, "i"), (0.06, "a"), (0.24, "a"), (0.32, "u"), (0.85, "u")],
               [(0, 0), (0.03, 0.9), (0.2, 1.0), (0.26, 0.25), (0.3, 0.1), (0.36, 0.9), (0.55, 1.0), (0.75, 0.6), (0.85, 0)],
               [(0, 0.05), (0.24, 0.05), (0.28, 0.9), (0.34, 0.3), (0.6, 0.1), (0.85, 0)], tilt=1.05)


def voice_woohoo(r):
    return pup(0.9, r, [(0, 470), (0.1, 560), (0.28, 540), (0.36, 600), (0.5, 860), (0.7, 900), (0.9, 730)],
               [(0, "u"), (0.1, "u"), (0.2, "o"), (0.3, "u"), (0.42, "o"), (0.62, "u"), (0.9, "u")],
               [(0, 0), (0.05, 0.8), (0.22, 1.0), (0.29, 0.2), (0.33, 0.1), (0.4, 0.95), (0.6, 1.0), (0.8, 0.6), (0.9, 0)],
               [(0, 0.1), (0.27, 0.05), (0.31, 0.9), (0.37, 0.2), (0.9, 0)], tilt=0.95)


def voice_ouch(r):
    y = pup(0.55, r, [(0, 780), (0.04, 860), (0.15, 700), (0.35, 460), (0.55, 420)],
            [(0, "a"), (0.15, "a"), (0.32, "u"), (0.55, "u")],
            [(0, 0), (0.015, 1.0), (0.1, 1.0), (0.33, 0.7), (0.38, 0.0), (0.55, 0)],
            [(0, 0.2), (0.33, 0.1), (0.38, 0), (0.55, 0)], rough=0.3)
    place(y, 0.35 * burst(0.12, r, 2500, 7000, 0.035, 0.006), 0.4)
    return y


def voice_laugh(r):
    out = np.zeros(N(1.45))
    starts = [0.0, 0.16, 0.31, 0.46, 0.62, 0.8]
    for i, t0 in enumerate(starts):
        last = i == len(starts) - 1
        d = 0.42 if last else 0.15
        s = [700, 680, 660, 630, 600, 560][i]
        v = "a" if last else "ae"
        seg = pup(d, r, [(0, s * 1.05), (d * 0.6, s), (d, s * 0.9)], [(0, v), (d, v)],
                  [(0, 0), (0.03, 0.2), (0.045, 1.0), (d * 0.7, 0.8), (d, 0)],
                  [(0, 0.0), (0.01, 1.0), (0.04, 0.4), (d, 0.15)], vib_depth=0.03 if last else 0.01,
                  vib_rate=9.0, breath_gain=0.8)
        place(out, seg * (1.0 - 0.06 * i), t0)
    return out


def voice_aww(r):
    return pup(1.0, r, [(0, 560), (0.1, 600), (0.4, 520), (0.8, 380), (1.0, 340)],
               [(0, "a"), (0.25, "a"), (0.6, "o"), (1.0, "o")],
               [(0, 0), (0.06, 0.9), (0.3, 1.0), (0.8, 0.6), (1.0, 0)],
               [(0, 0.15), (1.0, 0.1)], vib_rate=5.0, vib_depth=0.03)


def voice_hmph(r):
    y = pup(0.5, r, [(0, 420), (0.05, 460), (0.25, 340), (0.5, 320)], [(0, "m"), (0.5, "m")],
            [(0, 0), (0.03, 1.0), (0.22, 0.8), (0.26, 0), (0.5, 0)], None, rough=0.2, tilt=1.0)
    place(y, 0.6 * burst(0.2, r, 200, 1200, 0.06, 0.003), 0.26)
    return y


# =========================================================================== registry
# Impact-type sounds may trade up to this many dB of peak for soft saturation
# (keeps them punchy and loud without squashing them with the limiter).
PUNCH = {"bump_wall": 6, "bump_kart": 4, "land": 5, "land_big": 6, "explosion": 6, "splash": 4, "miniturbo": 4,
         "burnout": 4, "rocket_start": 4, "banana_drop": 3, "hop": 2, "ui_swap_part": 3}

# name: (generator, loop, target LUFS, description)
REGISTRY = {
    "engine_idle": (engine_idle, True, -16, "Two-stroke kart engine, ~45 Hz fundamental, 2 s loop"),
    "engine_mid": (engine_mid, True, -16, "Engine at ~90 Hz, 2 s loop"),
    "engine_high": (engine_high, True, -16, "Engine at ~160 Hz, 2 s loop"),
    "drift_skid": (drift_skid, True, -18, "Tire squeal on asphalt"),
    "wind_loop": (wind_loop, True, -20, "Speed wind rush"),
    "boost_loop": (boost_loop, True, -15, "Flame roar / jet whoosh while boosting"),
    "drift_tier1": (drift_tier1, False, -15, "Drift charge level 1 (blue sparks) sparkle"),
    "drift_tier2": (drift_tier2, False, -14, "Drift charge level 2 (orange sparks) sparkle"),
    "drift_tier3": (drift_tier3, False, -13, "Drift charge level 3 (purple sparks) sparkle"),
    "miniturbo": (miniturbo, False, -12, "Mini-turbo release: pop + whoosh + flame"),
    "boost_pad": (boost_pad, False, -12, "Boost pad: bright whoosh with a zap"),
    "rocket_start": (rocket_start, False, -11, "Rocket start launch"),
    "burnout": (burnout, False, -14, "Failed start: engine sputter/stall with puffs"),
    "hop": (hop, False, -15, "Cartoon spring boing (drift hop)"),
    "land": (land, False, -15, "Landing thud + suspension creak"),
    "land_big": (land_big, False, -12, "Big landing"),
    "bump_wall": (bump_wall, False, -12, "Wall hit: cartoony plastic/metal crunch"),
    "bump_kart": (bump_kart, False, -13, "Kart-kart rubbery bonk"),
    "item_box": (item_box, False, -13, "Item box: glass shatter + magical sparkle"),
    "item_roulette": (item_roulette, True, -17, "Item roulette tick loop"),
    "item_get": (item_get, False, -14, "Item obtained ding"),
    "coin": (coin, False, -15, "Golden seashell pickup, 2-note chime"),
    "banana_drop": (banana_drop, False, -15, "Banana dropped: squishy plop"),
    "banana_slip": (banana_slip, False, -14, "Slipping on a banana: squelch + slide"),
    "bomb_throw": (bomb_throw, False, -15, "Bomb throw whoosh"),
    "bomb_fuse": (bomb_fuse, True, -19, "Bomb fuse sizzle loop"),
    "explosion": (explosion, False, -10, "Cartoon explosion with debris"),
    "spin_out": (spin_out, False, -14, "Dizzy spin-out slide whistle"),
    "countdown_beep": (countdown_beep, False, -14, "Countdown 3-2-1 beep"),
    "countdown_go": (countdown_go, False, -12, "GO! tone with sparkle"),
    "lap": (lap, False, -13, "Lap complete jingle"),
    "final_lap": (final_lap, False, -12, "Final lap fanfare"),
    "finish": (finish, False, -12, "Finish-line whistle + fanfare"),
    "wrong_way": (wrong_way, False, -17, "Soft wrong-way buzzer"),
    "trick": (trick, False, -14, "Trick: whoosh + sparkle ting"),
    "splash": (splash, False, -13, "Water splash"),
    "respawn": (respawn, False, -14, "Magical respawn pop-in"),
    "ui_move": (ui_move, False, -22, "Menu cursor tick"),
    "ui_select": (ui_select, False, -17, "Menu confirm blip"),
    "ui_back": (ui_back, False, -18, "Menu back blip"),
    "ui_swap_part": (ui_swap_part, False, -16, "Garage: swap kart part ratchet + pop"),
    "ui_color": (ui_color, False, -16, "Garage: paint splat + sparkle"),
    "ui_start": (ui_start, False, -13, "Press start confirm"),
    "crowd_cheer": (crowd_cheer, False, -14, "Crowd cheering burst"),
    "crowd_loop": (crowd_loop, True, -22, "Ambient crowd murmur"),
    "waves_loop": (waves_loop, True, -21, "Gentle ocean surf"),
    "jungle_loop": (jungle_loop, True, -22, "Jungle birds & insects ambience"),
    "voice_yip": (voice_yip, False, -14, "Guara: short happy yip"),
    "voice_yahoo": (voice_yahoo, False, -14, "Guara: 'ya-hoo!'"),
    "voice_woohoo": (voice_woohoo, False, -14, "Guara: 'woo-hoo!'"),
    "voice_ouch": (voice_ouch, False, -14, "Guara: 'ouch!'"),
    "voice_laugh": (voice_laugh, False, -15, "Guara: giggle/laugh"),
    "voice_aww": (voice_aww, False, -15, "Guara: disappointed 'awww'"),
    "voice_hmph": (voice_hmph, False, -15, "Guara: grumpy 'hmph'"),
}
