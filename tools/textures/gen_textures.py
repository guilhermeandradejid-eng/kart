"""Procedural, perfectly tileable PBR-ish textures for Turbo Turma.

Spectral synthesis: white noise filtered in the Fourier domain is periodic by
construction, so every texture tiles seamlessly. Worley noise is computed on a
torus for the same reason. Outputs (assets/textures/):
    <name>_albedo.jpg   sRGB colour (stylised, CTR-like saturation)
    <name>_normal.png   tangent-space normal map from the height field
    <name>_mask.png     R = roughness, G = height/cavity (AO-ish), B = extra mask

    bpython tools/textures/gen_textures.py [names...]
"""

import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "textures")
N = 1024


# ---------------------------------------------------------------- noise

def band_noise(n, freq, seed, width=0.5):
    """Periodic noise concentrated around `freq` cycles per tile (0..1 range)."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, n))
    F = np.fft.fft2(w)
    fx = np.fft.fftfreq(n) * n
    r = np.sqrt(fx[None, :] ** 2 + fx[:, None] ** 2)
    filt = np.exp(-((np.log2(r + 1e-6) - np.log2(freq)) ** 2) / (2 * width ** 2))
    filt[0, 0] = 0
    out = np.real(np.fft.ifft2(F * filt))
    out -= out.min()
    return out / (out.max() + 1e-9)


def fbm(n, base, octaves, seed, gain=0.5):
    acc = np.zeros((n, n))
    amp = 1.0
    tot = 0.0
    for o in range(octaves):
        acc += band_noise(n, base * 2 ** o, seed + o * 31) * amp
        tot += amp
        amp *= gain
    return acc / tot


def worley(n, cells, seed, second=False):
    """Toroidal Worley noise: F1 (and F2-F1 edge if second)."""
    rng = np.random.default_rng(seed)
    pts = rng.random((cells, 2)) * n
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    d1 = np.full((n, n), 1e9, np.float32)
    d2 = np.full((n, n), 1e9, np.float32)
    for (px, py) in pts:
        dx = np.abs(xs - px)
        dy = np.abs(ys - py)
        dx = np.minimum(dx, n - dx)
        dy = np.minimum(dy, n - dy)
        d = np.sqrt(dx * dx + dy * dy)
        m = d < d1
        d2 = np.where(m, d1, np.minimum(d2, d))
        d1 = np.where(m, d, d1)
    scale = n / np.sqrt(cells)
    if second:
        return (d2 - d1) / scale
    return d1 / scale


def warp(img, dx, dy, amount):
    n = img.shape[0]
    ys, xs = np.mgrid[0:n, 0:n]
    x2 = (xs + (dx - 0.5) * amount * n).astype(int) % n
    y2 = (ys + (dy - 0.5) * amount * n).astype(int) % n
    return img[y2, x2]


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) == 2 and np.ndim(a) == 3 else t
    return a * (1 - t) + b * t


def col(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def ramp(t, stops):
    """t (H,W) -> colour via [(pos, '#hex'), ...]."""
    out = np.zeros(t.shape + (3,))
    pos = [s[0] for s in stops]
    cols = [col(s[1]) for s in stops]
    for c in range(3):
        out[..., c] = np.interp(t, pos, [cc[c] for cc in cols])
    return out


def normal_from_height(h, strength):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    nx = -gx * strength
    ny = gy * strength
    nz = np.ones_like(h)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / l, ny / l, nz / l], -1) * 0.5 + 0.5


def save(name, albedo, height, strength, rough, extra=None):
    os.makedirs(OUT, exist_ok=True)
    a = (np.clip(albedo, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(a, "RGB").save(os.path.join(OUT, f"{name}_albedo.jpg"), quality=92)
    nm = (np.clip(normal_from_height(height, strength), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(nm, "RGB").resize((N // 2, N // 2), Image.LANCZOS).save(os.path.join(OUT, f"{name}_normal.png"), optimize=True)
    ex = extra if extra is not None else np.zeros_like(height)
    rough = np.broadcast_to(rough, height.shape)
    m = np.stack([np.clip(rough, 0, 1), np.clip(height, 0, 1), np.clip(ex, 0, 1)], -1)
    Image.fromarray((m * 255).astype(np.uint8), "RGB").resize((N // 2, N // 2), Image.LANCZOS).save(
        os.path.join(OUT, f"{name}_mask.png"), optimize=True)
    print("wrote", name)


# ---------------------------------------------------------------- materials

def grass():
    big = fbm(N, 3, 3, 1)
    clumps = fbm(N, 14, 3, 2)
    blades = band_noise(N, 160, 3, 0.35)
    blades2 = band_noise(N, 90, 4, 0.4)
    tone = big * 0.55 + clumps * 0.45
    c = ramp(tone, [(0.0, "#2f7d24"), (0.35, "#3f9a2c"), (0.6, "#5cb53a"), (0.85, "#86cf4a"), (1.0, "#a6dc5c")])
    tips = smooth(blades * 0.6 + blades2 * 0.4, 0.62, 0.82)
    c = lerp(c, c * 1.25 + np.array([0.05, 0.06, -0.02]), tips)
    shade = smooth(1 - (blades * 0.5 + blades2 * 0.5), 0.55, 0.8)
    c = c * (1 - 0.35 * shade[..., None])
    # tiny flower / clover specks
    sp = band_noise(N, 220, 9, 0.25)
    specks = smooth(sp, 0.93, 0.97) * smooth(clumps, 0.55, 0.7)
    c = lerp(c, col("#f4f0a0"), specks * 0.8)
    h = blades * 0.5 + blades2 * 0.3 + clumps * 0.2
    save("grass", c, h, 6.0, 0.85 - tips * 0.15, clumps)


def sand():
    big = fbm(N, 3, 3, 11)
    n2 = fbm(N, 8, 2, 12)
    ys, xs = np.mgrid[0:N, 0:N] / N
    w = fbm(N, 4, 2, 13)
    ripple = np.sin((xs * 22 + ys * 6 + w * 3.5) * 2 * np.pi) * 0.5 + 0.5
    ripple = ripple ** 1.6
    grains = band_noise(N, 300, 14, 0.3)
    tone = big * 0.6 + n2 * 0.4
    c = ramp(tone, [(0.0, "#d8b67a"), (0.4, "#e8c98d"), (0.7, "#f2d8a2"), (1.0, "#fbe8bf")])
    c = c * (0.94 + 0.08 * ripple[..., None])
    c = c * (0.93 + 0.12 * grains[..., None])
    # shell fragments
    shells = smooth(band_noise(N, 120, 15, 0.25), 0.94, 0.975)
    c = lerp(c, col("#fff7ea"), shells * 0.9)
    pebbles = smooth(1 - worley(N, 260, 16), 0.85, 0.95) * smooth(n2, 0.6, 0.75)
    c = lerp(c, col("#b89a70"), pebbles * 0.6)
    h = ripple * 0.6 + grains * 0.25 + shells * 0.15
    save("sand", c, h, 3.5, 0.92 - shells * 0.4, ripple)


def dirt():
    big = fbm(N, 3, 3, 21)
    n2 = fbm(N, 10, 3, 22)
    st = worley(N, 520, 23)
    pebble = smooth(0.27, 0.2, st) * smooth(fbm(N, 6, 2, 27), 0.4, 0.62)
    tone = big * 0.5 + n2 * 0.5
    c = ramp(tone, [(0.0, "#7a5230"), (0.4, "#946338"), (0.75, "#b07a48"), (1.0, "#c99560")])
    pc = ramp(fbm(N, 40, 2, 24), [(0.0, "#9a8d7c"), (0.5, "#bdb09a"), (1.0, "#ded2bc")])
    shade = np.clip(1.0 - st / 0.27, 0, 1) ** 0.5
    c = lerp(c, pc * (0.72 + 0.35 * shade[..., None]), pebble)
    grains = band_noise(N, 260, 26, 0.3)
    c = c * (0.88 + 0.18 * grains[..., None])
    ruts = smooth(0.55, 0.75, fbm(N, 5, 2, 28))
    c = c * (1 - 0.12 * ruts[..., None])
    h = pebble * shade * 0.7 + n2 * 0.2 + grains * 0.1
    save("dirt", c, h, 7.0, 0.9 - pebble * 0.15, pebble)


def rock():
    ys, xs = np.mgrid[0:N, 0:N] / N
    w = fbm(N, 3, 3, 31)
    strata = np.sin((ys * 7 + w * 2.2) * 2 * np.pi) * 0.5 + 0.5
    strata2 = np.sin((ys * 23 + w * 4.0) * 2 * np.pi) * 0.5 + 0.5
    big = fbm(N, 4, 4, 32)
    cells = worley(N, 60, 33, second=True)
    cells = warp(cells, fbm(N, 6, 2, 36), fbm(N, 6, 2, 37), 0.06)
    cracks = smooth(0.05, 0.0, cells) * smooth(big, 0.3, 0.6)
    tone = big * 0.5 + strata * 0.35 + strata2 * 0.15
    c = ramp(tone, [(0.0, "#6e6157"), (0.35, "#8c7c6b"), (0.65, "#ab9880"), (1.0, "#d0bc9e")])
    c = c * (1 - 0.35 * cracks[..., None])
    lichen = smooth(fbm(N, 12, 3, 34), 0.64, 0.76) * smooth(strata, 0.55, 0.95)
    c = lerp(c, col("#86a84c"), lichen * 0.5)
    fine = band_noise(N, 200, 35, 0.35)
    c = c * (0.9 + 0.16 * fine[..., None])
    h = big * 0.35 + strata * 0.35 + strata2 * 0.1 - cracks * 0.35 + fine * 0.1
    save("rock", c, h, 9.0, 0.88 - lichen * 0.1, lichen)


def asphalt():
    big = fbm(N, 2, 3, 41)
    patches = smooth(fbm(N, 4, 3, 42), 0.62, 0.68)
    agg = band_noise(N, 380, 43, 0.25)
    agg2 = band_noise(N, 200, 44, 0.3)
    mid = fbm(N, 16, 2, 46)
    c = ramp(big * 0.6 + mid * 0.4, [(0.0, "#46444a"), (0.5, "#56535a"), (1.0, "#676369")])
    c = lerp(c, c * 0.8 + np.array([0.0, 0.0, 0.01]), patches * 0.6)
    light = smooth(agg, 0.7, 0.84)
    dark = smooth(1 - agg2, 0.74, 0.9)
    c = lerp(c, col("#9b968f"), light * 0.5)
    c = lerp(c, col("#2b292e"), dark * 0.45)
    h = agg * 0.55 + agg2 * 0.3 + mid * 0.15
    save("asphalt", c, h, 5.0, 0.8 - light * 0.25 + patches * 0.05, patches)


def wood():
    ys, xs = np.mgrid[0:N, 0:N] / N
    w = fbm(N, 3, 3, 51)
    fibre = band_noise(N, 120, 54, 0.3)
    fibre = np.mean([np.roll(fibre, k, 1) for k in range(-24, 25, 4)], axis=0)  # stretch along X
    grain = np.sin((ys * 40 + w * 1.5 + fibre * 0.8) * 2 * np.pi) * 0.5 + 0.5
    knots = smooth(0.12, 0.0, worley(N, 6, 52))
    tone = grain * 0.5 + fibre * 0.3 + w * 0.2
    c = ramp(tone, [(0.0, "#6e4425"), (0.5, "#93623a"), (1.0, "#b98552")])
    c = lerp(c, col("#4a2c16"), knots * 0.7)
    h = grain * 0.4 + fibre * 0.4 + knots * 0.2
    save("wood", c, h, 4.0, 0.75, knots)


def leaf():
    """Big-leaf albedo detail used by foliage (veins + speckle)."""
    ys, xs = np.mgrid[0:N, 0:N] / N
    veins = smooth(0.03, 0.0, np.abs(np.sin((xs * 16 + fbm(N, 6, 2, 61) * 0.5) * np.pi)))
    c = ramp(fbm(N, 6, 3, 62), [(0.0, "#2f8a2b"), (1.0, "#6ccf45")])
    c = lerp(c, col("#b6e66a"), veins * 0.6)
    save("leaf", c, veins + fbm(N, 20, 2, 63) * 0.2, 3.0, 0.6, veins)


GROUPS = {"grass": grass, "sand": sand, "dirt": dirt, "rock": rock, "asphalt": asphalt, "wood": wood, "leaf": leaf}

if __name__ == "__main__":
    names = sys.argv[1:] or list(GROUPS)
    for n in names:
        GROUPS[n]()
