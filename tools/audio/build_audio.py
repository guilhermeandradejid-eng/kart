"""build_audio.py - regenerate every Turbo Turma sound from code.

Usage:
    bpython tools/audio/build_audio.py            # everything
    bpython tools/audio/build_audio.py sfx        # only SFX
    bpython tools/audio/build_audio.py music      # only music
    bpython tools/audio/build_audio.py sfx coin hop   # just some files

Each output is normalised (loudness target per file, peak <= -1 dBFS after
Vorbis encoding), encoded as OGG Vorbis q6 @ 44.1 kHz, decoded again and checked
(peak, DC, loop seam, length). Deterministic: seeds derive from file names.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import dsp  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = {"sfx": os.path.join(ROOT, "assets", "audio", "sfx"), "music": os.path.join(ROOT, "assets", "audio", "music")}
PEAK_LIMIT_DB = -1.0


def _registry(kind):
    if kind == "sfx":
        import sfx
        return sfx.REGISTRY
    import music
    return music.REGISTRY


def ffprobe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def build_one(kind, name, spec):
    fn, loop, target, desc = spec
    t0 = time.time()
    r = dsp.rng(zlib.crc32(name.encode()))
    x = np.asarray(fn(r), dtype=float)
    if not loop:
        x = dsp.trim_silence(x, -66.0)
    sat = getattr(sys.modules.get(kind if kind == "sfx" else "music"), "PUNCH", {}).get(name, 0.0)
    y = dsp.finalize(x, target, ceiling_db=-1.5, loop=loop, sat_db=sat)
    path = os.path.join(OUT[kind], name + ".ogg")
    for attempt in range(4):
        dsp.write_ogg(path, y, 6)
        dec = dsp.read_audio(path, channels=2 if y.ndim == 2 else 1)
        pk = float(dsp.lin_to_db(np.abs(dec).max()))
        if pk <= PEAK_LIMIT_DB - 0.05:
            break
        y = y * dsp.db_to_lin(PEAK_LIMIT_DB - 0.25 - pk)
    info = {
        "name": name + ".ogg", "kind": kind, "loop": loop, "desc": desc,
        "samples": y.shape[-1], "dec_samples": dec.shape[-1],
        "peak_db": pk, "lufs": dsp.lufs(dec), "mmax": dsp.momentary_max(dec), "dc": float(np.abs(dec.mean(axis=-1)).max()),
        "seam": (dsp.seam_ratio(dec, refs=getattr(fn, "downbeats", lambda n: None)(dec.shape[-1])) if loop else None),
        "channels": 2 if dec.ndim == 2 else 1, "secs": time.time() - t0,
        "bytes": os.path.getsize(path), "duration": ffprobe_duration(path),
    }
    return info


def main(argv):
    kinds = ["sfx", "music"]
    only = None
    if argv and argv[0] in kinds:
        kinds = [argv[0]]
        only = set(argv[1:]) or None
    rows = []
    for kind in kinds:
        os.makedirs(OUT[kind], exist_ok=True)
        for name, spec in _registry(kind).items():
            if only and name not in only:
                continue
            info = build_one(kind, name, spec)
            rows.append(info)
            print(f"{info['name']:<24} {info['duration']:6.2f}s  ch={info['channels']}  loop={'Y' if info['loop'] else 'n'}"
                  f"  peak={info['peak_db']:6.2f} dBFS  {info['lufs']:6.1f} LUFS (M {info['mmax']:6.1f})  dc={info['dc']:.1e}"
                  + (f"  seam={info['seam']:.2f}" if info['seam'] is not None else "")
                  + f"  {info['bytes'] / 1024:6.0f} KB  ({info['secs']:.1f}s)", flush=True)
    problems = []
    for i in rows:
        if i["peak_db"] > PEAK_LIMIT_DB:
            problems.append(f"{i['name']}: peak {i['peak_db']:.2f}")
        if i["loop"] and i["seam"] > 1.5:
            problems.append(f"{i['name']}: loop seam ratio {i['seam']:.2f}")
        if i["dec_samples"] != i["samples"]:
            problems.append(f"{i['name']}: decoded length {i['dec_samples']} != {i['samples']}")
        if i["dc"] > 3e-3:
            problems.append(f"{i['name']}: DC {i['dc']:.2e}")
    total = sum(os.path.getsize(os.path.join(d, f)) for d in OUT.values() for f in os.listdir(d) if f.endswith(".ogg"))
    print(f"\n{len(rows)} files built. Total audio assets: {total / 1e6:.2f} MB")
    print("Problems:\n  " + "\n  ".join(problems) if problems else "All checks passed.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
