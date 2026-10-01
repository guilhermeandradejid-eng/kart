"""dsp.py - small procedural-audio toolkit for Turbo Turma (numpy + scipy only).

Conventions
-----------
* Sample rate is ``SR`` (44.1 kHz). Signals are float64 numpy arrays, mono ``(n,)``
  or stereo ``(2, n)``.
* Control parameters (frequency, cutoff, index, ...) may be scalars, per-sample
  arrays, or short arrays that get stretched over the note ("breakpoint" style).
* Phases are in *cycles* (0..1), not radians.
* Everything that has to loop is built *circularly*: FFT-shaped noise is periodic
  by construction, IIR filters run in ``circular`` mode, events are wrap-added and
  the master limiter uses wrap-around windows, so the last sample flows into the
  first one exactly.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np
from scipy import signal
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d, uniform_filter1d

SR = 44100
TAU = 2.0 * np.pi
NYQ = SR / 2.0


# --------------------------------------------------------------------------- basics
def N(dur: float) -> int:
    """Seconds -> sample count (>= 1)."""
    return max(1, int(round(dur * SR)))


def tvec(n: int) -> np.ndarray:
    return np.arange(n) / SR


def rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def midi_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


def db_to_lin(d):
    return 10.0 ** (np.asarray(d, dtype=float) / 20.0)


def lin_to_db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-12))


def ctrl(v, n: int) -> np.ndarray:
    """Broadcast a control value to ``n`` samples (short arrays are stretched)."""
    a = np.asarray(v, dtype=float)
    if a.ndim == 0:
        return np.full(n, float(a))
    if len(a) == n:
        return a
    return np.interp(np.linspace(0.0, 1.0, n), np.linspace(0.0, 1.0, len(a)), a)


def curve(n: int, points, kind: str = "lin") -> np.ndarray:
    """Breakpoint curve. ``points`` = [(time_s, value), ...]; 'exp' interpolates in log."""
    ts = np.array([p[0] for p in points], dtype=float)
    vs = np.array([p[1] for p in points], dtype=float)
    t = tvec(n)
    if kind == "exp":
        return np.exp(np.interp(t, ts, np.log(np.maximum(vs, 1e-9))))
    return np.interp(t, ts, vs)


def sweep(n: int, f0: float, f1: float, kind: str = "exp", power: float = 1.0) -> np.ndarray:
    x = np.linspace(0.0, 1.0, n) ** power
    if kind == "exp":
        return f0 * (f1 / f0) ** x
    return f0 + (f1 - f0) * x


def pad_to(x: np.ndarray, n: int) -> np.ndarray:
    if x.shape[-1] >= n:
        return x[..., :n]
    pad = [(0, 0)] * (x.ndim - 1) + [(0, n - x.shape[-1])]
    return np.pad(x, pad)


def mix(*parts, n: int | None = None) -> np.ndarray:
    """Sum signals of different lengths (zero padded)."""
    parts = [p for p in parts if p is not None]
    n = n or max(p.shape[-1] for p in parts)
    out = np.zeros(n)
    for p in parts:
        out += pad_to(p, n)
    return out


def place(buf: np.ndarray, sig: np.ndarray, t: float, gain: float = 1.0, wrap: bool = False):
    """Add ``sig`` into ``buf`` at time ``t`` (seconds). Mono or stereo buffers."""
    i0 = int(round(t * SR))
    n = buf.shape[-1]
    m = sig.shape[-1]
    if wrap:
        idx = (np.arange(m) + i0) % n
        if buf.ndim == 1:
            np.add.at(buf, idx, gain * sig)
        else:
            s2 = sig if sig.ndim == 2 else np.broadcast_to(sig, (buf.shape[0], m))
            for c in range(buf.shape[0]):
                np.add.at(buf[c], idx, gain * s2[c])
        return buf
    if i0 >= n or i0 + m <= 0:
        return buf
    s0 = max(0, -i0)
    e = min(m, n - i0)
    if buf.ndim == 2 and sig.ndim == 1:
        buf[:, i0 + s0:i0 + e] += gain * sig[s0:e]
    else:
        buf[..., i0 + s0:i0 + e] += gain * sig[..., s0:e]
    return buf


# --------------------------------------------------------------------------- oscillators
def phase(freq, n: int, p0: float = 0.0) -> np.ndarray:
    """Integrate a (time-varying) frequency into a phase in cycles, starting at p0."""
    f = ctrl(freq, n)
    ph = np.empty(n)
    ph[0] = 0.0
    np.cumsum(f[:-1] / SR, out=ph[1:])
    return ph + p0


def _blep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    y = np.zeros_like(t)
    m = t < dt
    x = t[m] / dt[m]
    y[m] = x + x - x * x - 1.0
    m = t > 1.0 - dt
    x = (t[m] - 1.0) / dt[m]
    y[m] = x * x + x + x + 1.0
    return y


def sine(freq, n: int, p0: float = 0.0) -> np.ndarray:
    return np.sin(TAU * phase(freq, n, p0))


def saw(freq, n: int, p0: float = 0.0) -> np.ndarray:
    """PolyBLEP band-limited sawtooth."""
    f = ctrl(freq, n)
    t = phase(f, n, p0) % 1.0
    dt = np.clip(np.abs(f) / SR, 1e-7, 0.5)
    return 2.0 * t - 1.0 - _blep(t, dt)


def square(freq, n: int, duty=0.5, p0: float = 0.0) -> np.ndarray:
    """PolyBLEP band-limited pulse wave (duty may vary per sample)."""
    f = ctrl(freq, n)
    d = ctrl(duty, n)
    t = phase(f, n, p0) % 1.0
    dt = np.clip(np.abs(f) / SR, 1e-7, 0.5)
    y = np.where(t < d, 1.0, -1.0)
    y += _blep(t, dt)
    y -= _blep((t - d) % 1.0, dt)
    return y - (2.0 * d - 1.0)


def triangle(freq, n: int, p0: float = 0.0) -> np.ndarray:
    t = phase(freq, n, p0 + 0.25) % 1.0
    return 4.0 * np.abs(t - 0.5) - 1.0


def additive(freq, n: int, amp_fn, kmax: int = 80, fmax: float = 15000.0, phases=None) -> np.ndarray:
    """Harmonic additive synthesis. ``amp_fn(k, fk)`` returns amplitude (scalar or per-sample)
    for harmonic k whose instantaneous frequency is ``fk`` (array). Harmonics fade out
    smoothly approaching ``fmax`` so nothing aliases."""
    f = ctrl(freq, n)
    ph = phase(f, n)
    out = np.zeros(n)
    fmax = min(fmax, 0.45 * SR)
    for k in range(1, kmax + 1):
        fk = k * f
        if fk.min() >= fmax:
            break
        a = amp_fn(k, fk)
        if np.isscalar(a) and a == 0:
            continue
        a = a * np.clip((fmax - fk) / (0.15 * fmax), 0.0, 1.0)
        p = 0.0 if phases is None else phases[k % len(phases)]
        out += a * np.sin(TAU * (k * ph + p))
    return out


def lowpass_resp(fk, fc, order: float = 2.0, q: float = 0.0):
    """Magnitude of a smooth lowpass (+ optional resonant bump) at frequency fk."""
    r = fk / np.maximum(fc, 1.0)
    mag = 1.0 / np.sqrt(1.0 + r ** (2 * order))
    if q > 0:
        mag = mag * (1.0 + q * np.exp(-((r - 1.0) / 0.25) ** 2))
    return mag


def fm(freq, n: int, ratio: float = 1.0, index=1.0, fb: float = 0.0, mod_detune: float = 0.0) -> np.ndarray:
    """Two-operator FM (phase modulation). ``index`` may be an envelope."""
    f = ctrl(freq, n)
    pm = phase(f * ratio + mod_detune, n)
    mod = np.sin(TAU * pm)
    if fb:
        mod = np.sin(TAU * pm + fb * mod)
    return np.sin(TAU * phase(f, n) + ctrl(index, n) * mod)


# --------------------------------------------------------------------------- envelopes
def env_perc(n: int, attack: float = 0.002, decay: float = 0.2, curve_pow: float = 1.0) -> np.ndarray:
    """Linear attack then exponential decay (``decay`` = time constant in s)."""
    t = tvec(n)
    a = max(attack, 1.0 / SR)
    rise = np.clip(t / a, 0.0, 1.0) ** curve_pow
    fall = np.exp(-np.maximum(t - a, 0.0) / max(decay, 1e-5))
    return rise * fall


def env_adsr(n: int, a: float, d: float, s: float, r: float, gate: float | None = None) -> np.ndarray:
    t = tvec(n)
    gate = (n / SR - r) if gate is None else gate
    a = max(a, 1e-4)
    e = np.where(t < a, t / a, s + (1.0 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    g_level = s + (1.0 - s) * np.exp(-max(gate - a, 0.0) / max(d, 1e-4)) if gate > a else gate / a
    rel = g_level * np.exp(-(t - gate) / max(r / 4.0, 1e-4))
    e = np.where(t < gate, e, rel)
    return e


def fade(x: np.ndarray, fin: float = 0.0, fout: float = 0.0) -> np.ndarray:
    x = x.copy()
    n = x.shape[-1]
    if fin > 0:
        k = min(n, N(fin))
        x[..., :k] *= np.sin(0.5 * np.pi * np.linspace(0, 1, k)) ** 2
    if fout > 0:
        k = min(n, N(fout))
        x[..., n - k:] *= np.cos(0.5 * np.pi * np.linspace(0, 1, k)) ** 2
    return x


def trim_silence(x: np.ndarray, thresh_db: float = -70.0, keep: float = 0.02) -> np.ndarray:
    """Cut trailing near-silence (keeps a short tail) and fade the end."""
    a = np.abs(x) if x.ndim == 1 else np.abs(x).max(axis=0)
    idx = np.nonzero(a > db_to_lin(thresh_db) * max(a.max(), 1e-9))[0]
    if len(idx) == 0:
        return x
    end = min(x.shape[-1], idx[-1] + N(keep))
    return fade(x[..., :end], 0.0, min(0.01, end / SR / 4))


# --------------------------------------------------------------------------- noise
def white(n: int, r: np.random.Generator) -> np.ndarray:
    return r.standard_normal(n)


def shaped_noise(n: int, r: np.random.Generator, mag_fn) -> np.ndarray:
    """FFT-shaped Gaussian noise, unit RMS. Periodic with period n (loop friendly)."""
    X = np.fft.rfft(r.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    X *= mag_fn(f)
    X[0] = 0.0
    y = np.fft.irfft(X, n)
    return y / (np.sqrt(np.mean(y ** 2)) + 1e-12)


def pink(n: int, r: np.random.Generator) -> np.ndarray:
    return shaped_noise(n, r, lambda f: 1.0 / np.sqrt(np.maximum(f, 20.0)))


def brown(n: int, r: np.random.Generator) -> np.ndarray:
    return shaped_noise(n, r, lambda f: 1.0 / np.maximum(f, 20.0))


def band_noise(n: int, r: np.random.Generator, fc: float, width_oct: float = 1.0, tilt: float = 0.0) -> np.ndarray:
    """Noise with a Gaussian (in log-frequency) band around fc. Periodic."""
    def mag(f):
        lf = np.log2(np.maximum(f, 1.0) / fc)
        return np.exp(-0.5 * (lf / (width_oct / 2.0)) ** 2) * (np.maximum(f, 1.0) / fc) ** tilt
    return shaped_noise(n, r, mag)


def smooth_random(n: int, r: np.random.Generator, rate_hz: float = 2.0) -> np.ndarray:
    """Smooth random control signal in [-1, 1], periodic over n samples."""
    y = shaped_noise(n, r, lambda f: np.exp(-(f / rate_hz) ** 2))
    return y / (np.abs(y).max() + 1e-12)


def periodic_lfo(n: int, r: np.random.Generator, n_comp: int = 6, max_cycles: int = 8) -> np.ndarray:
    """Sum of sines with an integer number of cycles over n (exactly periodic, zero mean)."""
    t = np.arange(n) / n
    y = np.zeros(n)
    for _ in range(n_comp):
        c = r.integers(1, max_cycles + 1)
        y += r.uniform(0.3, 1.0) / c ** 0.5 * np.sin(TAU * (c * t + r.random()))
    return y / (np.abs(y).max() + 1e-12)


# --------------------------------------------------------------------------- filters
def biquad_ba(kind: str, f0, q=0.7071, gain_db=0.0):
    """RBJ cookbook biquads; f0/q may be arrays (returns coefficient arrays)."""
    f0 = np.clip(np.asarray(f0, dtype=float), 5.0, 0.49 * SR)
    q = np.maximum(np.asarray(q, dtype=float), 0.05)
    w0 = TAU * f0 / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2.0 * q)
    A = 10.0 ** (np.asarray(gain_db, dtype=float) / 40.0)
    one = np.ones_like(cw)
    if kind == "lp":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "hp":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "bp":  # 0 dB peak gain
        b = [alpha, 0 * cw, -alpha]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "notch":
        b = [one, -2 * cw, one]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "peak":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind in ("lowshelf", "highshelf"):
        sq = 2 * np.sqrt(A) * alpha
        if kind == "lowshelf":
            b = [A * ((A + 1) - (A - 1) * cw + sq), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sq)]
            a = [(A + 1) + (A - 1) * cw + sq, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sq]
        else:
            b = [A * ((A + 1) + (A - 1) * cw + sq), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sq)]
            a = [(A + 1) - (A - 1) * cw + sq, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sq]
    else:
        raise ValueError(kind)
    b = np.array([np.broadcast_to(v, cw.shape) for v in b], dtype=float)
    a = np.array([np.broadcast_to(v, cw.shape) for v in a], dtype=float)
    return b / a[0], a / a[0]


def _lfilter(b, a, x, circular: bool):
    if circular:
        n = x.shape[-1]
        xx = np.concatenate([x, x, x], axis=-1)
        return signal.lfilter(b, a, xx, axis=-1)[..., 2 * n:]
    return signal.lfilter(b, a, x, axis=-1)


def filt(x, kind: str, f0: float, q: float = 0.7071, gain_db: float = 0.0, order: int = 1, circular: bool = False):
    """Static biquad (cascaded ``order`` times). Works on mono or stereo."""
    b, a = biquad_ba(kind, f0, q, gain_db)
    for _ in range(order):
        x = _lfilter(b, a, x, circular)
    return x


def lp(x, f0, q=0.7071, order=1, circular=False):
    return filt(x, "lp", f0, q, order=order, circular=circular)


def hp(x, f0, q=0.7071, order=1, circular=False):
    return filt(x, "hp", f0, q, order=order, circular=circular)


def bp(x, f0, q=1.0, order=1, circular=False):
    return filt(x, "bp", f0, q, order=order, circular=circular)


def tvfilt(x: np.ndarray, kind: str, f0, q=0.7071, gain_db=0.0, block: int = 32, order: int = 1) -> np.ndarray:
    """Time-varying biquad (coefficients updated every ``block`` samples)."""
    n = x.shape[-1]
    f = ctrl(f0, n)
    qq = ctrl(q, n)
    centers = np.minimum(np.arange(0, n, block) + block // 2, n - 1)
    B, A = biquad_ba(kind, f[centers], qq[centers], gain_db)
    y = x.astype(float)
    for _ in range(order):
        out = np.empty(n)
        zi = np.zeros(2)
        for j, s in enumerate(range(0, n, block)):
            e = min(n, s + block)
            out[s:e], zi = signal.lfilter(B[:, j], A[:, j], y[s:e], zi=zi)
        y = out
    return y


def onepole_lp(x, fc, circular=False):
    a = np.exp(-TAU * fc / SR)
    return _lfilter([1 - a], [1, -a], x, circular)


def dc_block(x, circular=False):
    if circular:
        x = x - x.mean(axis=-1, keepdims=True)
        return filt(x, "hp", 18.0, 0.6, circular=True)
    return filt(x, "hp", 15.0, 0.6)


def comb_ff(x, delay_s: float, g: float) -> np.ndarray:
    """Feed-forward comb (e.g. pluck position / flanging colour)."""
    d = N(delay_s)
    y = x.copy()
    y[d:] += g * x[:-d]
    return y


# --------------------------------------------------------------------------- physical-ish models
def karplus(freq: float, dur: float, r: np.random.Generator, t60: float = 2.0, bright: float = 0.5,
            pluck_pos: float = 0.18, excite_lp: float = 6000.0, excite=None) -> np.ndarray:
    """Vectorised Karplus-Strong string with fractional-delay tuning.

    Loop filter = [1-s, s] averaging (brightness) convolved with a linear
    fractional delay, so the fundamental is tuned exactly.  Processing runs one
    period (N samples) at a time, which is valid because every feedback tap is
    at least N samples in the past.
    """
    n = N(dur)
    s = float(np.clip(0.5 - 0.45 * bright, 0.05, 0.5))  # 0.5 = darkest
    period = SR / freq
    Nd = int(np.floor(period - s))
    fr = period - s - Nd
    h = np.convolve([1 - s, s], [1 - fr, fr])  # taps at delays Nd, Nd+1, Nd+2
    g = 10.0 ** (-3.0 / (t60 * freq))
    if excite is None:
        ex = r.uniform(-1, 1, Nd)
        ex = lp(ex, excite_lp)
        p = max(1, int(pluck_pos * Nd))
        ex[p:] -= ex[:-p]  # pluck-position comb
        ex -= ex.mean()
    else:
        ex = excite
    x = np.zeros(n)
    x[:min(n, len(ex))] = ex[:n]
    P = Nd + 2
    yb = np.zeros(P + n)
    for st in range(0, n, Nd):
        e = min(n, st + Nd)
        i = np.arange(st, e) + P
        yb[i] = x[st:e] + g * (h[0] * yb[i - Nd] + h[1] * yb[i - Nd - 1] + h[2] * yb[i - Nd - 2])
    return yb[P:]


def modal(freq: float, n: int, ratios, amps, decays, r=None, detune_cents: float = 0.0) -> np.ndarray:
    """Sum of exponentially decaying sine partials (bells, bars, drums)."""
    t = tvec(n)
    out = np.zeros(n)
    for i, (rt, a, d) in enumerate(zip(ratios, amps, decays)):
        fk = freq * rt
        if fk >= 0.45 * SR:
            continue
        ph = r.random() if r is not None else 0.0
        out += a * np.exp(-t / d) * np.sin(TAU * (fk * t + ph))
    k = max(1, min(n // 5, N(0.05)))  # never end on a truncated partial (click)
    out[n - k:] *= np.cos(0.5 * np.pi * np.linspace(0, 1, k)) ** 2
    return out


# --------------------------------------------------------------------------- formant voice
# Adult-male-ish vowel formants (Hz) and bandwidths; scaled for a small cartoon pup.
VOWELS = {
    "a": ([800, 1250, 2600, 3400], [80, 90, 120, 150], [1.0, 0.55, 0.25, 0.12]),
    "e": ([500, 1800, 2550, 3400], [70, 90, 120, 150], [1.0, 0.45, 0.30, 0.12]),
    "i": ([300, 2250, 3000, 3600], [50, 90, 120, 150], [1.0, 0.35, 0.30, 0.15]),
    "o": ([500, 850, 2500, 3300], [70, 80, 120, 150], [1.0, 0.55, 0.12, 0.06]),
    "u": ([320, 700, 2400, 3300], [50, 70, 120, 150], [1.0, 0.30, 0.08, 0.04]),
    "@": ([550, 1500, 2500, 3400], [80, 90, 120, 150], [1.0, 0.45, 0.20, 0.10]),
    "ae": ([700, 1650, 2500, 3400], [80, 90, 120, 150], [1.0, 0.55, 0.25, 0.12]),
    "m": ([260, 1100, 2300, 3200], [60, 200, 250, 250], [1.0, 0.06, 0.03, 0.02]),
}


def vowel_tracks(n: int, seq, scale: float = 1.0):
    """``seq`` = [(time_s, vowel), ...] -> per-sample formant freq/bw/amp arrays (4 x n)."""
    ts = np.array([s[0] for s in seq], dtype=float)
    t = tvec(n)
    F = np.zeros((4, n))
    B = np.zeros((4, n))
    A = np.zeros((4, n))
    for j in range(4):
        F[j] = np.interp(t, ts, [VOWELS[v][0][j] * scale for _, v in seq])
        B[j] = np.interp(t, ts, [VOWELS[v][1][j] * scale for _, v in seq])
        A[j] = np.interp(t, ts, [VOWELS[v][2][j] for _, v in seq])
    return F, B, A


def formant_gain(fk, F, B, A):
    """Spectral envelope (sum of resonance peaks) evaluated at frequencies fk."""
    g = np.zeros_like(fk)
    for j in range(F.shape[0]):
        g += A[j] / np.sqrt(1.0 + ((fk - F[j]) / (0.5 * B[j] + 0.08 * F[j])) ** 2)
    return g


def formant_voice(f0, n: int, F, B, A, tilt: float = 1.2, jitter: float = 0.0, r=None, kmax: int = 60) -> np.ndarray:
    """Additive glottal source whose harmonic amplitudes follow the formant envelope.
    Time-varying formants never glitch (no recursive filter state)."""
    f = ctrl(f0, n)
    if jitter and r is not None:
        f = f * (1.0 + jitter * smooth_random(n, r, 30.0))
    return additive(f, n, lambda k, fk: formant_gain(fk, F, B, A) / k ** tilt, kmax=kmax, fmax=9000.0)


def stft_shape(x: np.ndarray, gain_fn, nfft: int = 1024) -> np.ndarray:
    """Apply a time-varying spectral envelope ``gain_fn(freqs, t_frames) -> (nf, nt)`` via STFT."""
    n = len(x)
    f, t, Z = signal.stft(x, SR, nperseg=nfft, noverlap=nfft * 3 // 4, boundary="even")
    Z *= gain_fn(f, t)
    _, y = signal.istft(Z, SR, nperseg=nfft, noverlap=nfft * 3 // 4)
    return pad_to(y, n)


def formant_noise(x: np.ndarray, F, B, A) -> np.ndarray:
    """Shape (breath) noise with per-sample formant tracks (via STFT)."""
    def g(freqs, tf):
        idx = np.clip((tf * SR).astype(int), 0, F.shape[1] - 1)
        return _formant_grid(freqs, F[:, idx], B[:, idx], A[:, idx])
    return stft_shape(x, g)


def _formant_grid(freqs, F, B, A):
    fk = freqs[:, None]
    g = np.zeros((len(freqs), F.shape[1]))
    for j in range(F.shape[0]):
        g += A[j][None, :] / np.sqrt(1.0 + ((fk - F[j][None, :]) / (0.5 * B[j][None, :] + 0.08 * F[j][None, :])) ** 2)
    return g


# --------------------------------------------------------------------------- effects
def pan(x: np.ndarray, p: float = 0.0) -> np.ndarray:
    """Constant-power pan of a mono signal; p in [-1 (left), 1 (right)]."""
    a = (np.clip(p, -1, 1) + 1.0) * np.pi / 4.0
    return np.vstack([np.cos(a) * x, np.sin(a) * x]) * np.sqrt(2.0)


def saturate(x, drive: float = 1.0):
    """tanh soft clip normalised so small signals keep unity gain."""
    return np.tanh(drive * x) / drive


def make_ir(t60: float = 1.6, dur: float | None = None, damp_hz: float = 5000.0, predelay: float = 0.012,
            seed: int = 7, stereo: bool = True, er_gain: float = 0.35) -> np.ndarray:
    """Stochastic late-reverb impulse response (smooth, FDN-like dense tail) with
    frequency dependent decay (highs die ~2.5x faster) and a few early reflections.
    Returns (2, m) or (m,), unit energy per channel."""
    r = rng(seed)
    dur = dur or min(t60 * 1.2, 4.0)
    m = N(dur)
    t = tvec(m)
    chans = []
    for c in range(2 if stereo else 1):
        nz = r.standard_normal(m)
        lo = lp(nz, damp_hz, order=2)
        hi = nz - lo
        tail = lo * np.exp(-6.91 * t / t60) + hi * np.exp(-6.91 * t / (t60 * 0.4))
        tail = hp(tail, 120.0)
        tail *= np.clip((t - predelay) / 0.02, 0, 1)  # predelay + soft onset
        er = np.zeros(m)
        for _ in range(8):
            d = r.uniform(0.004, 0.045)
            k = N(d + predelay * 0.5)
            if k < m:
                er[k] += r.uniform(-1, 1) * np.exp(-d / 0.03)
        ir = tail / np.sqrt(np.sum(tail ** 2)) + er_gain * er / (np.sqrt(np.sum(er ** 2)) + 1e-9)
        chans.append(ir / np.sqrt(np.sum(ir ** 2)))
    return np.array(chans) if stereo else chans[0]


def convolve(x: np.ndarray, ir: np.ndarray, loop_len: int | None = None) -> np.ndarray:
    """Convolve mono/stereo x with mono/stereo IR. With ``loop_len`` the result is
    folded circularly to exactly that length (seamless loop reverb)."""
    xs = x if x.ndim == 2 else x[None, :]
    irs = ir if ir.ndim == 2 else ir[None, :]
    nch = max(xs.shape[0], irs.shape[0])
    outs = []
    for c in range(nch):
        y = signal.oaconvolve(xs[min(c, xs.shape[0] - 1)], irs[min(c, irs.shape[0] - 1)])
        outs.append(y)
    y = np.array(outs)
    if loop_len is not None:
        y = wrap_add(y, loop_len)
    if x.ndim == 1 and ir.ndim == 1:
        y = y[0]
    return y


def reverb(x: np.ndarray, t60: float = 1.4, wet: float = 0.2, seed: int = 7, damp_hz: float = 5000.0,
           predelay: float = 0.012, loop: bool = False, stereo_out: bool | None = None) -> np.ndarray:
    """Dry + convolution reverb. Non-loop output is lengthened by the tail."""
    stereo_out = (x.ndim == 2) if stereo_out is None else stereo_out
    ir = make_ir(t60, damp_hz=damp_hz, predelay=predelay, seed=seed, stereo=stereo_out)
    n = x.shape[-1]
    wetsig = convolve(x, ir, loop_len=n if loop else None)
    if stereo_out and x.ndim == 1:
        dry = np.vstack([x, x])
    else:
        dry = x
    if loop:
        return dry + wet * wetsig
    out = wet * wetsig
    out[..., :n] += dry
    return out


def schroeder(x: np.ndarray, room: float = 0.8, damp: float = 0.3, spread: int = 23) -> np.ndarray:
    """Freeverb-style Schroeder reverb (8 LP-feedback combs + 4 allpasses per channel).
    Vectorised a delay-line-length at a time. Returns stereo wet signal, same length."""
    combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617]
    aps = [556, 441, 341, 225]
    scale = SR / 44100.0
    fb = 0.7 + 0.28 * room
    outs = []
    for ch in range(2):
        inp = 0.015 * x
        acc = np.zeros_like(inp)
        for d0 in combs:
            D = int((d0 + ch * spread) * scale)
            s = np.zeros(len(inp))  # s[n] = in[n] + fb*lp(out)[n]; out[n] = s[n-D]
            out = np.zeros(len(inp))
            zi = np.zeros(1)
            for st in range(0, len(inp), D):
                e = min(len(inp), st + D)
                o = s[st - D:e - D] if st >= D else np.zeros(e - st)
                out[st:e] = o
                lpo, zi = signal.lfilter([1 - damp], [1, -damp], o, zi=zi)
                s[st:e] = inp[st:e] + fb * lpo
            acc += out
        y = acc
        for d0 in aps:
            D = int((d0 + ch * spread) * scale)
            v = np.zeros(len(y))
            res = np.zeros(len(y))
            for st in range(0, len(y), D):
                e = min(len(y), st + D)
                prev = v[st - D:e - D] if st >= D else np.zeros(e - st)
                v[st:e] = y[st:e] + 0.5 * prev
                res[st:e] = prev - y[st:e]
            y = res
        outs.append(y)
    return np.array(outs)


# --------------------------------------------------------------------------- dynamics
def _mono_abs(x):
    return np.abs(x) if x.ndim == 1 else np.abs(x).max(axis=0)


def compress(x: np.ndarray, thresh_db: float = -18.0, ratio: float = 3.0, attack: float = 0.005,
             release: float = 0.12, knee_db: float = 6.0, makeup_db: float = 0.0, circular: bool = False) -> np.ndarray:
    """Feed-forward RMS compressor with soft knee; stereo-linked."""
    p = x ** 2 if x.ndim == 1 else (x ** 2).mean(axis=0)
    a = np.exp(-1.0 / (attack * SR))
    lev = _lfilter([1 - a], [1, -a], p, circular)
    lev_db = 10 * np.log10(np.maximum(lev, 1e-12))
    over = lev_db - thresh_db
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    rr = np.exp(-1.0 / (release * SR))
    gr = _lfilter([1 - rr], [1, -rr], gr, circular)
    g = db_to_lin(makeup_db - gr)
    return x * g


def limiter(x: np.ndarray, ceiling_db: float = -1.0, window: float = 0.008, hold: float = 0.02,
            circular: bool = False) -> np.ndarray:
    """Look-ahead brickwall limiter: min-filter (hold) + box smoothing guarantees
    gain <= required gain at every sample (no overshoot)."""
    c = db_to_lin(ceiling_db)
    a = _mono_abs(x)
    g = np.minimum(1.0, c / np.maximum(a, 1e-12))
    L = max(1, N(window))
    H = max(L, N(hold))
    mode = "wrap" if circular else "nearest"
    gmin = minimum_filter1d(g, size=2 * H + 1, mode=mode)
    gs = uniform_filter1d(gmin, size=L + 1, mode=mode)
    gs = np.minimum(gs, g)  # numerical safety
    y = x * gs
    return np.clip(y, -c, c)


# --------------------------------------------------------------------------- loudness (BS.1770)
def _k_weight(x):
    b1, a1 = biquad_ba("highshelf", 1681.974450955533, 0.7071752369554196, 3.999843853973347)
    b2, a2 = biquad_ba("hp", 38.13547087602444, 0.5003270373238773)
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=-1), axis=-1)


def lufs(x: np.ndarray) -> float:
    """Integrated loudness (gated, BS.1770-4). Sounds < 0.4 s use a single block."""
    y = _k_weight(x)
    y = y[None, :] if y.ndim == 1 else y
    n = y.shape[1]
    blk = N(0.4)
    if n <= blk:
        ms = np.mean(y ** 2, axis=1).sum()
        return float(-0.691 + 10 * np.log10(max(ms, 1e-12)))
    hop = blk // 4
    starts = np.arange(0, n - blk + 1, hop)
    cs = np.cumsum(np.pad(y ** 2, ((0, 0), (1, 0))), axis=1)
    ms = ((cs[:, starts + blk] - cs[:, starts]) / blk).sum(axis=0)
    l = -0.691 + 10 * np.log10(np.maximum(ms, 1e-12))
    ms = ms[l > -70]
    if len(ms) == 0:
        return -70.0
    rel = -0.691 + 10 * np.log10(ms.mean()) - 10
    l2 = -0.691 + 10 * np.log10(np.maximum(ms, 1e-12))
    ms = ms[l2 > rel]
    return float(-0.691 + 10 * np.log10(ms.mean()))


def true_peak_db(x: np.ndarray) -> float:
    y = signal.resample_poly(x, 4, 1, axis=-1)
    return float(lin_to_db(np.abs(y).max()))


def softclip(x: np.ndarray, ceiling: float, knee_db: float = 4.0) -> np.ndarray:
    """Linear below ceiling-knee, then tanh-saturates towards ``ceiling`` (never exceeds it)."""
    th = ceiling * 10 ** (-knee_db / 20)
    a = np.abs(x)
    over = a > th
    y = x.copy()
    y[over] = np.sign(x[over]) * (th + (ceiling - th) * np.tanh((a[over] - th) / (ceiling - th)))
    return y


def finalize(x: np.ndarray, target_lufs: float, ceiling_db: float = -1.5, loop: bool = False,
             max_limit_db: float = 5.0, sat_db: float = 0.0, fade_out: float = 0.004) -> np.ndarray:
    """DC removal, loudness normalisation, then peak control to the ceiling:
    optional soft saturation (up to ``sat_db`` of peak reduction, for impacts),
    then a look-ahead limiter (up to ``max_limit_db``). If a sound would need more
    than that, it is left quieter than the target instead of being squashed."""
    x = dc_block(np.asarray(x, dtype=float), circular=loop)
    if not loop:
        x = fade(x, 0.0, fade_out)
    y = x * db_to_lin(target_lufs - lufs(x))
    excess = lin_to_db(_mono_abs(y).max()) - ceiling_db
    if excess > sat_db + max_limit_db:
        y *= db_to_lin(-(excess - sat_db - max_limit_db))
        excess = sat_db + max_limit_db
    if excess > 0 and sat_db > 0:
        c1 = db_to_lin(ceiling_db + max(0.0, excess - sat_db) + 0.3)
        y = softclip(y, float(c1))
    if lin_to_db(_mono_abs(y).max()) > ceiling_db:
        y = limiter(y, ceiling_db, circular=loop)
    tp = true_peak_db(y)
    if tp > ceiling_db + 0.3:
        y *= db_to_lin(ceiling_db + 0.3 - tp)
    return y


# --------------------------------------------------------------------------- loops
def wrap_add(x: np.ndarray, loop_len: int) -> np.ndarray:
    """Fold everything past ``loop_len`` back onto the start (circular render)."""
    out = np.zeros(x.shape[:-1] + (loop_len,))
    for s in range(0, x.shape[-1], loop_len):
        seg = x[..., s:s + loop_len]
        out[..., :seg.shape[-1]] += seg
    return out


def loop_crossfade(x: np.ndarray, loop_len: int, xfade: int) -> np.ndarray:
    """Make a loop of ``loop_len`` from a render of >= loop_len + xfade samples by
    equal-power crossfading the overhang into the head."""
    assert x.shape[-1] >= loop_len + xfade
    out = x[..., :loop_len].copy()
    w = np.linspace(0, 1, xfade)
    fin = np.sin(0.5 * np.pi * w)
    fout = np.cos(0.5 * np.pi * w)
    out[..., :xfade] = out[..., :xfade] * fin + x[..., loop_len:loop_len + xfade] * fout
    return out


def seam_ratio(x: np.ndarray, win: int = 64, refs=None) -> float:
    """Loop-click detector. Rotate the loop so the wrap point sits in the middle,
    high-pass it (>7 kHz, where a discontinuity's energy shows up) and compare the
    energy in a short window across the seam with the 99.5th percentile of the same
    window energy everywhere else in the file. <= ~1: no click at the loop point.
    For music, ``refs`` = sample positions of comparable moments (other downbeats);
    the seam is then compared with the loudest of those instead."""
    x = x if x.ndim == 2 else x[None, :]
    worst = 0.0
    for c in x:
        n = len(c)
        y = filt(np.roll(c, n // 2), "hp", 7000.0, 0.7, order=2, circular=True)
        e = uniform_filter1d(y ** 2, win, mode="wrap")
        seam = e[n // 2 - win // 2: n // 2 + win // 2].max()
        if refs is None:
            ref = np.percentile(e, 99.5)
        else:
            ref = max(e[(np.arange(-win // 2, win // 2) + p + n // 2) % n].max() for p in refs)
        worst = max(worst, seam / (ref + 1e-15))
    return float(worst)


def momentary_max(x: np.ndarray) -> float:
    """Max momentary loudness (400 ms window, LUFS) - the 'how loud does it hit' number."""
    y = _k_weight(x)
    y = y[None, :] if y.ndim == 1 else y
    blk = N(0.4)
    p = (y ** 2).sum(axis=0)
    if len(p) < blk:
        p = np.pad(p, (0, blk - len(p)))
    ms = uniform_filter1d(p, blk, mode="constant")
    return float(-0.691 + 10 * np.log10(max(ms.max(), 1e-12)))


# --------------------------------------------------------------------------- I/O
def write_ogg(path: str, x: np.ndarray, quality: float = 6.0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = np.asarray(x, dtype=np.float32)
    data = data.T if data.ndim == 2 else data
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        wavfile.write(tmp, SR, data)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:a", "libvorbis",
                        "-q:a", str(quality), "-ar", str(SR), "-fflags", "+bitexact", "-flags:a", "+bitexact",
                        "-serial_offset", "1", path], check=True)
    finally:
        os.remove(tmp)


def read_audio(path: str, channels: int | None = None) -> np.ndarray:
    """Decode an audio file to float (channels, n). Uses libsndfile (exact Ogg
    granule handling) when the ``soundfile`` package is present, else ffmpeg."""
    try:
        import soundfile as sf
        y, _ = sf.read(path, dtype="float64", always_2d=True)
        y = y.T
        return y[0] if y.shape[0] == 1 else y
    except ImportError:
        pass
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                            "stream=channels", "-of", "csv=p=0", path], capture_output=True, text=True)
    ch = channels or int(probe.stdout.strip() or 1)
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-acodec", "pcm_f32le", "-ar", str(SR),
           "-ac", str(ch), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    y = np.frombuffer(raw, dtype=np.float32).astype(float)
    return y.reshape(-1, ch).T if ch > 1 else y
