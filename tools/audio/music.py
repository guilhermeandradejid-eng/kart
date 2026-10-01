"""music.py - Turbo Turma soundtrack, composed and rendered in code.

* A tiny step sequencer (``Song``) places instrument renders on stereo tracks.
* Loops are rendered *circularly*: every note/reverb tail that runs past the loop
  end is folded back onto the start, and master dynamics use wrap-around
  windows, so the last sample leads seamlessly into the first.
* Melodies are written as "pos:len:note" strings per bar (16th-note grid).
"""
from __future__ import annotations

import numpy as np

from dsp import (SR, TAU, N, tvec, rng, midi_hz, place, pan, make_ir, convolve, wrap_add, compress,
                 filt, fade, additive, lowpass_resp, saturate, sweep, white, tvfilt, trim_silence, onepole_lp)
import instruments as ins

# =========================================================================== music theory
_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
       "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
_QUAL = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10],
         "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9], "dim": [0, 3, 6], "9": [0, 4, 7, 10, 14], "maj9": [0, 4, 7, 11, 14],
         "m9": [0, 3, 7, 10, 14], "7b9": [0, 4, 7, 10, 13], "sus4": [0, 5, 7], "m7b5": [0, 3, 6, 10]}


def note(name: str) -> int:
    """'F#5' -> midi."""
    i = 2 if len(name) > 2 and name[1] in "#b" else 1
    return 12 * (int(name[i:]) + 1) + _PC[name[:i]]


def parse_chord(sym: str):
    i = 2 if len(sym) > 1 and sym[1] in "#b" else 1
    return _PC[sym[:i]], _QUAL[sym[i:]]


def voicing(sym: str, lo: int, count: int = 4, transpose: int = 0):
    """Close voicing of the chord's tones in [lo, lo+12), extended upward to ``count`` notes."""
    root, iv = parse_chord(sym)
    pcs = [(root + transpose + x) % 12 for x in iv]
    notes = sorted({lo + ((pc - lo) % 12) for pc in pcs})
    k = 0
    while len(notes) < count:
        notes.append(notes[k] + 12)
        k += 1
    return notes[:count]


def bass_root(sym: str, lo: int = 36, transpose: int = 0) -> int:
    root, _ = parse_chord(sym)
    return lo + ((root + transpose - lo) % 12)


def parse_bars(bars, transpose=0, start_bar=0):
    """['0:3:D5 3:3:D5 ...', ...] -> [(beat, dur_beats, midi)]"""
    out = []
    for b, s in enumerate(bars):
        for tok in s.split():
            p, ln, nm = tok.split(":")
            out.append(((start_bar + b) * 4 + int(p) / 4.0, int(ln) / 4.0, note(nm) + transpose))
    return out


def split_bar(sym):
    """'Am|D' -> [(0, 'Am'), (2, 'D')] (beat offsets)."""
    parts = sym.split("|")
    return [(i * 4 / len(parts), p) for i, p in enumerate(parts)]


MAJOR = (0, 2, 4, 5, 7, 9, 11)


def diatonic(m: int, steps: int, key_pc: int) -> int:
    scale = [x for x in range(0, 128) if (x - key_pc) % 12 in MAJOR]
    idx = max(i for i, x in enumerate(scale) if x <= m)
    return scale[idx + steps]


def hz(m):
    return round(float(midi_hz(m)), 3)


# =========================================================================== sequencer
class Song:
    def __init__(self, bpm: float, bars: int, seed: int = 1, tail: float = 5.0, loop: bool = True):
        self.bpm = bpm
        self.spb = 60.0 / bpm
        self.bars = bars
        self.loop = loop
        self.loop_n = int(round(bars * 4 * self.spb * SR))
        self.n = self.loop_n + N(tail)
        self.tracks: dict[str, np.ndarray] = {}
        self.r = rng(seed)
        self.kick_beats: list[float] = []

    def sec(self, beat):
        return beat * self.spb

    def add(self, track, beat, sig, gain=1.0, pan_=0.0, human=0.0):
        buf = self.tracks.get(track)
        if buf is None:
            buf = self.tracks[track] = np.zeros((2, self.n))
        t = self.sec(beat) + (self.r.normal(0.0, human) if human else 0.0)
        if self.loop:
            t %= self.loop_n / SR
        t = max(0.0, t)
        st = pan(sig, pan_) if sig.ndim == 1 else sig
        place(buf, st * gain, t)

    def duck_env(self, release=0.11):
        """Sidechain shape driven by the kick pattern (circular)."""
        L = self.loop_n
        imp = np.zeros(L)
        for b in self.kick_beats:
            imp[int(round(self.sec(b) * SR)) % L] = 1.0
        k = N(0.35)
        t = tvec(k)
        ker = np.clip(t / 0.004, 0, 1) * np.exp(-t / release)
        env = np.clip(wrap_add(np.convolve(imp, ker), L), 0, 1)
        return env[np.arange(self.n) % L]

    def mixdown(self, cfg: dict, t60=1.6, rev_gain=0.5, duck: dict | None = None,
                glue=(-20.0, 2.0), predelay=0.02, damp=5500.0):
        """cfg: track -> (gain, reverb_send). duck: track -> depth. Returns the
        glued stereo mix (exactly loop_n samples for loops)."""
        dry = np.zeros((2, self.n))
        send = np.zeros((2, self.n))
        denv = self.duck_env() if duck else None
        for name, buf in self.tracks.items():
            g, s = cfg.get(name, (1.0, 0.15))
            b = buf * g
            if duck and name in duck:
                b = b * (1.0 - duck[name] * denv)
            dry += b
            send += b * s
        ir = make_ir(t60, damp_hz=damp, predelay=predelay, seed=31, stereo=True)
        wet = convolve(send, ir)
        total = np.zeros((2, wet.shape[-1]))
        total[:, :self.n] += dry
        total += rev_gain * wet
        if self.loop:
            mixbus = wrap_add(total, self.loop_n)
        else:
            mixbus = trim_silence(total, -70.0, 0.05)
        mixbus = filt(mixbus, "hp", 28.0, 0.7, circular=self.loop)
        pk = np.abs(mixbus).max()
        mixbus = mixbus / pk * 0.5
        return compress(mixbus, glue[0], glue[1], 0.01, 0.15, 6.0, circular=self.loop)


# =========================================================================== shared patterns
def steel_line(song, track, notes, gain=1.0, pan_=0.0, roll=True, octave=0):
    """Steel-pan melody; long notes are rolled (tremolo strikes) like real pan players."""
    for beat, dur, m in notes:
        f = hz(m + octave)
        dsec = dur * song.spb
        song.add(track, beat, ins.steel_drum(f, round(min(dsec, 0.5), 3)), gain, pan_, 0.003)
        if roll and dur >= 1.0:
            k = 0.25
            while k < dur - 0.2:
                v = 0.32 + 0.1 * np.sin(k * 3)
                song.add(track, beat + k, ins.steel_drum(f, 0.15, int(k * 4) % 3), gain * v, pan_, 0.002)
                k += 0.25


def mallet_line(song, track, notes, inst=ins.marimba, gain=1.0, pan_=0.0, octave=0):
    for beat, dur, m in notes:
        song.add(track, beat, inst(hz(m + octave), round(dur * song.spb, 3)), gain, pan_, 0.003)


def brass_line(song, track, notes, gain=1.0, pan_=0.0, bright=1.0, octave=0):
    for beat, dur, m in notes:
        song.add(track, beat, ins.brass(hz(m + octave), round(dur * song.spb * 0.95, 3), bright), gain, pan_)


def drum_bar(song, bar, pattern: dict, fn, track, gain=1.0, pan_=0.0, human=0.002):
    """pattern: {16th position: velocity}."""
    for p, v in pattern.items():
        song.add(track, bar * 4 + p / 4.0, fn(), gain * v, pan_, human)


# =========================================================================== RACE THEME (baiao / samba-rock)
RACE_CHORDS = {
    "A": ["G", "G", "C", "D", "G", "Em", "Am|D", "G"],
    "B": ["C", "D", "Bm", "Em", "Am", "D", "G", "D7"],
    "BR": ["Em", "C", "D", "G", "Em", "C", "Am", "D7"],
}
MEL_A = [
    "0:3:D5 3:3:D5 6:2:B4 8:2:G4 10:2:B4 12:2:D5 14:2:E5",
    "0:6:D5 6:2:B4 8:4:A4 12:2:G4 14:2:B4",
    "0:3:E5 3:3:E5 6:2:C5 8:2:G4 10:2:C5 12:2:E5 14:2:G5",
    "0:6:F#5 6:2:E5 8:6:D5",
    "0:3:D5 3:3:D5 6:2:B4 8:2:G4 10:2:B4 12:2:D5 14:2:G5",
    "0:3:G5 3:3:F#5 6:2:E5 8:4:B4 12:2:E5 14:2:G5",
    "0:3:A5 3:3:G5 6:2:E5 8:3:F#5 11:3:E5 14:2:D5",
    "0:8:G5",
]
MEL_A2_END = "0:6:G5 6:2:D5 8:2:E5 10:2:F#5 12:4:G5"
MEL_B = [
    "0:6:E5 6:2:G5 8:4:E5 12:4:C5",
    "0:6:F#5 6:2:A5 8:4:F#5 12:4:D5",
    "0:3:D5 3:3:F#5 6:6:B5 12:2:A5 14:2:F#5",
    "0:8:G5 8:4:E5 12:4:B4",
    "0:2:C5 2:2:E5 4:4:A5 8:2:G5 10:2:A5 12:4:C6",
    "0:3:B5 3:3:A5 6:2:F#5 8:4:D5 12:2:E5 14:2:F#5",
    "0:3:G5 3:3:D5 6:2:B4 8:2:D5 10:2:G5 12:4:B5",
    "0:6:A5 6:2:F#5 8:4:C6 12:2:A5 14:2:F#5",
]

KICK_BAIAO = {0: 1.0, 3: 0.65, 8: 0.95, 11: 0.65}
SNARE_BACK = {4: 1.0, 12: 1.0, 7: 0.14, 10: 0.12, 15: 0.16}
SURDO = {4: 0.9, 12: 0.9}
SURDO_MUTE = {0: 0.35, 8: 0.35}
TAMBORIM = {0: 0.9, 2: 0.6, 5: 0.8, 7: 0.6, 9: 0.8, 11: 0.6, 14: 0.9}
AGOGO_HI = {0: 1.0, 3: 0.8, 6: 0.9, 10: 0.8}
AGOGO_LO = {2: 0.9, 8: 1.0, 12: 0.8, 14: 0.7}
CAVACO_ACC = {0, 3, 6, 8, 11, 14}


def race_song(final: bool = False) -> np.ndarray:
    bpm = 150.0 if final else 140.0
    tr = 2 if final else 0  # final lap: up a whole step (A major)
    key_pc = (7 + tr) % 12
    plan = [("A", MEL_A), ("B", MEL_B), ("A2", MEL_A[:7] + [MEL_A2_END]), ("B2", MEL_B)]
    if not final:
        plan.append(("BR", None))
    S = Song(bpm, 8 * len(plan), seed=140 + int(final))

    def chords_of(sec):
        return RACE_CHORDS["BR" if sec == "BR" else sec[0]]

    for si, (sec, mel) in enumerate(plan):
        chords = chords_of(sec)
        b0 = si * 8
        nxt_sec = plan[(si + 1) % len(plan)][0]
        for bi, sym in enumerate(chords):
            bar = b0 + bi
            halves = split_bar(sym)

            def chord_at(beat, halves=halves):
                return halves[-1][1] if (len(halves) > 1 and beat >= 2) else halves[0][1]
            breakdown = sec == "BR" and bi < 4
            fill = bi == 7
            # ------------------------------------------------ bass (baiao cell per half bar)
            nxt = chords[bi + 1] if bi < 7 else chords_of(nxt_sec)[0]
            nroot = bass_root(split_bar(nxt)[0][1], 36, tr)
            if len(halves) == 1:
                r0 = bass_root(sym, 36, tr)
                cells = [(0, 0.75, r0), (0.75, 1.0, r0 + 7), (2, 0.75, r0 + 12), (2.75, 0.75, r0 + 7), (3.5, 0.5, nroot - 1)]
            else:
                r0 = bass_root(halves[0][1], 36, tr)
                r1 = bass_root(halves[1][1], 36, tr)
                cells = [(0, 0.75, r0), (0.75, 0.75, r0 + 7), (1.5, 0.5, r0 + 12), (2, 0.75, r1), (2.75, 0.75, r1 + 7),
                         (3.5, 0.5, nroot - 1)]
            for off, d, m in cells:
                S.add("bass", bar * 4 + off, ins.bass(hz(m), round(d * S.spb * 0.9, 3)), 1.0 if off in (0, 2) else 0.8)
            # ------------------------------------------------ cavaquinho 16th strums
            for p in range(16):
                if breakdown and p % 2:
                    continue
                v = 1.0 if p in CAVACO_ACC else 0.33
                notes = voicing(chord_at(p / 4), 62, 4, tr)
                s = ins.strum(tuple(notes), 0.1 if v < 1 else 0.16, v, down=(p % 2 == 0), spread=0.007, var=p % 3)
                S.add("cavaco", bar * 4 + p / 4, s, 1.0, -0.3, 0.002)
            # ------------------------------------------------ pad bed
            for off, sy in halves:
                dur = (4 / len(halves)) * S.spb
                for j, m in enumerate(voicing(sy, 55, 4, tr)):
                    S.add("pad", bar * 4 + off, ins.pad(hz(m), round(dur, 3)), 1.0, -0.6 + 0.4 * j)
            # ------------------------------------------------ brass: stabs (A, B2, bridge build), swells (B)
            if sec[0] == "A" or sec == "B2" or (sec == "BR" and bi >= 4):
                if sec[0] == "A":
                    stab_pos = [(1.5, 0.35), (3.5, 0.35)]
                elif sec == "B2":
                    stab_pos = [(0, 0.3), (0.75, 0.3), (1.5, 0.3), (2.5, 0.3), (3.0, 0.3)]
                else:
                    stab_pos = [(0, 0.5), (1.5, 0.3), (3, 0.5)] if bi < 7 else [(0, 0.3), (1, 0.3), (2, 0.3), (3, 0.3)]
                for off, d in stab_pos:
                    for j, m in enumerate(voicing(chord_at(off), 60, 4, tr)):
                        S.add("brass", bar * 4 + off, ins.brass(hz(m), round(d * S.spb, 3), 1.1), 0.8,
                              [-0.35, 0.35, -0.15, 0.15][j])
            if sec == "B" or (final and sec == "B2"):
                for off, sy in halves:
                    dur = (4 / len(halves)) * S.spb * 0.97
                    for j, m in enumerate(voicing(sy, 55, 4, tr)):
                        S.add("brasspad", bar * 4 + off, ins.brass(hz(m), round(dur, 3), 0.55), 0.8,
                              [-0.5, 0.5, -0.2, 0.2][j])
            # ------------------------------------------------ drum kit
            if not breakdown:
                kp = dict(KICK_BAIAO)
                if final:
                    kp.update({4: 0.8, 12: 0.8})
                if fill and sec != "BR":
                    kp = {0: 1.0, 3: 0.65, 8: 0.9}
                for p, v in kp.items():
                    S.add("kick", bar * 4 + p / 4, ins.kick(), v)
                    S.kick_beats.append(bar * 4 + p / 4)
                sp = dict(SNARE_BACK) if not fill else {4: 1.0, 8: 0.5, 10: 0.6, 11: 0.5, 12: 0.8, 13: 0.7, 14: 0.9, 15: 1.0}
                if sec == "BR" and fill:
                    sp = {p: 0.3 + 0.7 * p / 15 for p in range(16)}
                drum_bar(S, bar, sp, lambda: ins.snare(int(S.r.integers(4))), "snare", 1.0, 0.05)
                if fill and sec != "BR":
                    for k, (p, f) in enumerate(((8, 200.0), (10, 160.0), (12, 130.0), (14, 100.0))):
                        S.add("toms", bar * 4 + p / 4, ins.tom(f), 0.8, 0.4 - 0.25 * k)
                hp_ = {p: (0.55 if p % 4 == 0 else 0.85) for p in range(0, 16, 2)}
                if final:
                    hp_ = {p: (0.45, 0.3, 0.85, 0.35)[p % 4] for p in range(16)}
                for p, v in hp_.items():
                    S.add("hats", bar * 4 + p / 4, ins.hat(p == 14 and bar % 2 == 1, p % 3), v, 0.25, 0.002)
            else:
                drum_bar(S, bar, {4: 1.0, 12: 1.0}, lambda: ins.clap(int(S.r.integers(3))), "clap", 1.0, 0.0)
            # ------------------------------------------------ Brazilian percussion
            for p in range(16):
                S.add("shaker", bar * 4 + p / 4, ins.shaker(p % 4, p % 4 == 3), (0.5, 0.25, 0.35, 0.85)[p % 4], -0.35, 0.003)
                if final:  # double-time ganza (32nds, soft, other side)
                    S.add("shaker", bar * 4 + p / 4 + 0.125, ins.shaker((p + 1) % 4), 0.25, 0.35, 0.002)
            drum_bar(S, bar, SURDO, lambda: ins.surdo(True), "surdo", 1.0, -0.1)
            drum_bar(S, bar, SURDO_MUTE, lambda: ins.surdo(False), "surdo", 1.0, -0.1)
            for p in range(16):  # triangle, the heartbeat of baiao
                S.add("triangle", bar * 4 + p / 4, ins.triangle_perc(p % 4 == 2, p % 2), (0.45, 0.3, 0.8, 0.3)[p % 4], 0.5, 0.002)
            if sec in ("A2", "B2", "BR") or final:
                pat = TAMBORIM if not final else {p: (1.0 if p in TAMBORIM else 0.35) for p in range(16)}
                drum_bar(S, bar, pat, lambda: ins.tamborim(int(S.r.integers(3))), "tamborim", 1.0, 0.4)
            if sec in ("B", "B2", "BR"):
                drum_bar(S, bar, AGOGO_HI, lambda: ins.agogo(True), "agogo", 1.0, -0.45)
                drum_bar(S, bar, AGOGO_LO, lambda: ins.agogo(False), "agogo", 1.0, -0.45)
            if sec in ("A2", "BR") and bi % 2 == 1:
                S.add("cuica", bar * 4 + 3.5, ins.cuica(True, bi % 3), 1.0, 0.3)
                S.add("cuica", bar * 4 + 1.5, ins.cuica(False, bi % 3), 0.7, 0.3)
            if bi == 0 or (final and bi == 4):
                S.add("crash", bar * 4, ins.crash(bar % 2), 1.0, -0.2)
        # ------------------------------------------------ melody
        if mel is not None:
            notes = parse_bars(mel, tr, b0)
            if sec == "B2":
                brass_line(S, "leadbrass", notes, 0.9, 0.0, 1.25, octave=12 if final else 0)
                steel_line(S, "lead", notes, 0.55, 0.1, octave=12)
            else:
                steel_line(S, "lead", notes, 1.0, 0.05, octave=12 if final else 0)
                if final:
                    mallet_line(S, "marimba", notes, ins.marimba, 0.6, 0.35)
            if sec == "B":
                mallet_line(S, "marimba", notes, ins.marimba, 0.5, 0.35, octave=-12 if not final else 0)
            if sec == "A2":
                harm = [(b, d, diatonic(m, -2, key_pc)) for b, d, m in notes]
                mallet_line(S, "marimba", harm, ins.marimba, 0.7, 0.4, octave=12 if final else 0)
        else:
            # bridge: marimba baiao-cell riff (bars 1-4), 16th arpeggios building (bars 5-8)
            for bi, sym in enumerate(RACE_CHORDS["BR"]):
                bar = b0 + bi
                vc = voicing(sym, 67, 4, tr)
                if bi < 4:
                    for p, idx in ((0, 0), (3, 1), (6, 2), (10, 3), (12, 2), (14, 1)):
                        S.add("marimba", bar * 4 + p / 4, ins.marimba(hz(vc[idx]), 0.3), 0.9, 0.35)
                    if bi % 2 == 1:
                        steel_line(S, "lead", parse_bars(["0:3:B5 3:3:A5 6:2:G5"], tr, bar), 0.8, 0.05)
                else:
                    seq = vc + vc[::-1][1:-1]
                    for p in range(16):
                        m = seq[p % len(seq)] + (12 if bi >= 6 and p % 4 == 0 else 0)
                        S.add("marimba", bar * 4 + p / 4, ins.marimba(hz(m), 0.2), 0.55 + 0.03 * p, 0.35)
            k = N(4 * 2 * S.spb)
            riser = tvfilt(white(k, S.r), "bp", sweep(k, 400, 7000), 2.0) * np.linspace(0, 1, k) ** 2
            S.add("fx", (b0 + 6) * 4, riser, 0.15)
        if final:  # extra 16th arpeggio synth layer
            for bi, sym in enumerate(chords):
                bar = b0 + bi
                halves = split_bar(sym)
                for p in range(16):
                    sy = halves[-1][1] if (len(halves) > 1 and p >= 8) else halves[0][1]
                    vc = voicing(sy, 67, 4, tr)
                    m = (vc + vc[::-1][1:-1])[p % 6]
                    S.add("arp", bar * 4 + p / 4, ins.pluck_synth(hz(m), 0.08), 0.9 if p % 4 == 0 else 0.6,
                          0.45 if p % 2 else -0.45)

    cfg = {
        "kick": (0.84, 0.03), "snare": (0.5, 0.18), "toms": (0.45, 0.15), "clap": (1.3, 0.2), "hats": (0.9, 0.05),
        "shaker": (1.3, 0.08), "surdo": (0.63, 0.1), "triangle": (0.52, 0.1), "tamborim": (0.9, 0.12),
        "agogo": (0.45, 0.15), "cuica": (0.35, 0.2), "crash": (0.68, 0.12), "bass": (0.4, 0.0),
        "cavaco": (0.8, 0.12), "pad": (0.24, 0.4), "brass": (0.38, 0.18), "brasspad": (0.28, 0.25),
        "lead": (0.6, 0.22), "leadbrass": (0.4, 0.2), "marimba": (0.45, 0.22), "arp": (0.3, 0.2),
        "fx": (1.0, 0.3),
    }
    duck = {"bass": 0.35, "pad": 0.4, "brasspad": 0.3, "cavaco": 0.15}
    return S.mixdown(cfg, t60=1.5, rev_gain=0.45, duck=duck)


def music_race(r):
    return race_song(False)


def music_race_final(r):
    return race_song(True)


# =========================================================================== MENU (bossa nova)
MENU_CHORDS = {
    "A": ["Fmaj7", "Fmaj7", "Gm7", "C7", "Am7", "D7b9", "Gm7", "C7"],
    "B": ["Bbmaj7", "Bbm6", "Am7", "D7", "Gm7", "C7", "Fmaj7", "Gm7|C7"],
    "A2": ["Fmaj7", "Fmaj7", "Gm7", "C7", "Am7", "D7b9", "Gm7", "Gm7|C7"],
}
MEN_A = [
    "0:4:C5 4:2:A4 6:6:E5 12:4:D5",
    "0:6:C5 6:2:A4 8:8:G4",
    "0:4:Bb4 4:2:D5 6:6:F5 12:4:E5",
    "0:6:E5 6:2:D5 8:8:Bb4",
    "0:4:C5 4:2:E5 6:6:G5 12:4:E5",
    "0:6:F#5 6:2:Eb5 8:8:C5",
    "0:4:D5 4:2:F5 6:6:A5 12:4:G5",
    "0:6:E5 6:2:D5 8:4:C5 12:4:Bb4",
]
MEN_B = [
    "0:8:D5 8:2:F5 10:6:A5",
    "0:8:Db5 8:2:F5 10:6:G5",
    "0:6:C5 6:2:E5 8:8:G5",
    "0:6:F#5 6:2:A5 8:4:C6 12:4:A5",
    "0:6:Bb5 6:2:A5 8:4:F5 12:4:D5",
    "0:6:E5 6:2:G5 8:8:Bb5",
    "0:12:A5 12:4:G5",
    "0:4:F5 4:4:E5 8:4:D5 12:4:C5",
]
GUITAR_PAT = [[0, 3, 6, 10, 13], [2, 6, 8, 12]]
CLAVE = [[0, 3, 6, 10, 13], [2, 6, 10]]


def music_menu(r):
    S = Song(100.0, 24, seed=100)
    plan = [("A", MEN_A), ("B", MEN_B), ("A2", MEN_A)]
    for si, (sec, mel) in enumerate(plan):
        chords = MENU_CHORDS[sec]
        b0 = si * 8
        for bi, sym in enumerate(chords):
            bar = b0 + bi
            halves = split_bar(sym)

            def chord_at(beat, halves=halves):
                return halves[-1][1] if (len(halves) > 1 and beat >= 2) else halves[0][1]
            # nylon guitar: thumb bass on 1 & 3, syncopated finger chords
            for off in (0.0, 2.0):
                sy = chord_at(off)
                rt = bass_root(sy, 40)
                m = rt if (off == 0 or len(halves) > 1) else (rt + 7 if rt + 7 <= 52 else rt - 5)
                S.add("guitar", bar * 4 + off, ins.nylon(hz(m), 1.1, 0.8), 0.9, -0.25, 0.004)
            for p in GUITAR_PAT[bar % 2]:
                notes = voicing(chord_at(p / 4), 57, 4)
                s = ins.strum(tuple(notes), 0.5, 0.7, down=False, spread=0.012, inst=ins.nylon, var=p % 3)
                S.add("guitar", bar * 4 + p / 4, s, 0.8, -0.25, 0.005)
            # upright bass
            nx = chords[bi + 1] if bi < 7 else MENU_CHORDS[plan[(si + 1) % 3][0]][0]
            for off, d, kind in ((0, 1.4, "r"), (2, 1.4, "f"), (3.5, 0.45, "a")):
                rt = bass_root(chord_at(off), 33)
                if kind == "f":
                    m = rt if len(halves) > 1 else (rt + 7 if rt + 7 <= 45 else rt - 5)
                elif kind == "a":
                    m = bass_root(split_bar(nx)[0][1], 33) + 1
                else:
                    m = rt
                S.add("bass", bar * 4 + off, ins.upright(hz(m), round(d * S.spb, 3)), 0.55 if kind == "a" else 1.0)
            # e-piano pad
            for off, sy in halves:
                d = (4 / len(halves)) * S.spb
                for j, m in enumerate(voicing(sy, 60, 4)):
                    S.add("epiano", bar * 4 + off, ins.epiano(hz(m), round(d, 3), 0.45), 0.7, [-0.4, 0.4, -0.15, 0.15][j], 0.01)
            # percussion: rim clave, brushes, soft kick
            for p in CLAVE[bar % 2]:
                S.add("rim", bar * 4 + p / 4, ins.rimclick(p % 3), 0.8, 0.2, 0.003)
            for bt in range(4):
                S.add("brush", bar * 4 + bt, ins.brush_swish(round(S.spb * 0.9, 3), bt % 2), 1.0, 0.3 if bt % 2 else -0.3)
            for p in range(16):
                S.add("brush", bar * 4 + p / 4, ins.brush_tap(p % 3), (0.6, 0.25, 0.4, 0.3)[p % 4], 0.15, 0.004)
            for p, v in ((0, 0.8), (6, 0.35), (8, 0.65), (14, 0.35)):
                S.add("kick", bar * 4 + p / 4, ins.kick(1, 0.7), v)
            if sec == "B":
                for p in range(0, 16, 2):
                    S.add("shaker", bar * 4 + p / 4, ins.shaker(p % 4, p % 4 == 2), 0.5 if p % 4 else 0.3, -0.4, 0.004)
        notes = parse_bars(mel, 0, b0)
        if sec == "A":
            for beat, dur, m in notes:
                S.add("flute", beat, ins.flute(hz(m), round(dur * S.spb * 0.92, 3)), 1.0, 0.1, 0.006)
        elif sec == "B":
            for beat, dur, m in notes:
                S.add("vibes", beat, ins.vibes(hz(m), round(dur * S.spb, 3)), 1.0, 0.15, 0.004)
        else:
            for beat, dur, m in notes:
                S.add("flute", beat, ins.flute(hz(m), round(dur * S.spb * 0.92, 3)), 0.9, 0.1, 0.006)
                S.add("vibes", beat, ins.vibes(hz(diatonic(m, -2, 5)), round(dur * S.spb, 3)), 0.6, -0.3, 0.004)
    cfg = {"guitar": (1.06, 0.2), "bass": (0.7, 0.05), "epiano": (0.28, 0.35), "rim": (0.77, 0.2),
           "brush": (0.66, 0.15), "kick": (0.4, 0.05), "shaker": (1.0, 0.1), "flute": (0.4, 0.35), "vibes": (0.5, 0.35)}
    return S.mixdown(cfg, t60=1.9, rev_gain=0.55, glue=(-22.0, 1.8), damp=4500.0)


# =========================================================================== RESULTS (light celebratory groove)
RES_CHORDS = ["C", "Am", "F", "G", "C", "Am", "Dm", "G", "C", "Am", "F", "G", "F", "G", "Em|Am", "Dm|G"]
RES_MEL = [
    "0:2:E5 2:2:G5 4:4:C6 8:2:B5 10:2:G5 12:4:E5",
    "0:2:C5 2:2:E5 4:4:A5 8:4:G5 12:4:E5",
    "0:2:F5 2:2:A5 4:4:C6 8:2:A5 10:2:F5 12:4:A5",
    "0:6:G5 6:2:F5 8:4:D5 12:4:B4",
    "0:2:E5 2:2:G5 4:4:C6 8:2:D6 10:2:C6 12:4:G5",
    "0:2:C5 2:2:E5 4:4:A5 8:2:C6 10:2:B5 12:4:A5",
    "0:2:D5 2:2:F5 4:4:A5 8:4:F5 12:4:D5",
    "0:4:G5 4:4:B5 8:4:D6 12:4:B5",
    "0:6:G5 6:2:E5 8:4:C5 12:4:E5",
    "0:6:A5 6:2:E5 8:4:C5 12:4:E5",
    "0:6:A5 6:2:C6 8:4:F5 12:4:A5",
    "0:6:B5 6:2:D6 8:4:G5 12:4:B5",
    "0:4:A5 4:2:G5 6:2:F5 8:4:C5 12:4:F5",
    "0:4:B5 4:2:A5 6:2:G5 8:4:D5 12:4:G5",
    "0:4:G5 4:4:E5 8:4:A5 12:4:C6",
    "0:4:D6 4:4:A5 8:4:B5 12:2:D6 14:2:G5",
]


def music_results(r):
    S = Song(128.0, 16, seed=128)
    for bar, sym in enumerate(RES_CHORDS):
        halves = split_bar(sym)

        def chord_at(beat, halves=halves):
            return halves[-1][1] if (len(halves) > 1 and beat >= 2) else halves[0][1]
        for off, d, iv in ((0, 0.75, 0), (0.75, 0.75, 7), (1.5, 0.5, 12), (2, 0.75, 0), (2.75, 0.75, 7), (3.5, 0.5, 12)):
            rt = bass_root(chord_at(off), 36)
            S.add("bass", bar * 4 + off, ins.bass(hz(rt + iv), round(d * S.spb * 0.85, 3)), 1.0 if iv == 0 else 0.75)
        for p in (2, 6, 10, 14, 7, 15):
            notes = voicing(chord_at(p / 4), 62, 4)
            S.add("cavaco", bar * 4 + p / 4, ins.strum(tuple(notes), 0.14, 1.0 if p % 4 == 2 else 0.5, p % 2 == 0,
                                                      0.007, var=p % 3), 1.0, -0.3, 0.003)
        for off, sy in halves:
            for j, m in enumerate(voicing(sy, 55, 4)):
                S.add("pad", bar * 4 + off, ins.pad(hz(m), round(4 / len(halves) * S.spb, 3)), 1.0, -0.5 + 0.33 * j)
        for p, v in ((0, 1.0), (8, 0.9), (11, 0.5)):
            S.add("kick", bar * 4 + p / 4, ins.kick(), v)
            S.kick_beats.append(bar * 4 + p / 4)
        for p in (4, 12):
            S.add("clap", bar * 4 + p / 4, ins.clap(p % 3), 1.0, 0.0, 0.002)
        for p in range(16):
            S.add("shaker", bar * 4 + p / 4, ins.shaker(p % 4, p % 4 == 3), (0.5, 0.25, 0.35, 0.8)[p % 4], -0.35, 0.003)
        for p in range(2, 16, 4):
            S.add("hats", bar * 4 + p / 4, ins.hat(p == 14 and bar % 2 == 1, 1), 0.7, 0.3)
        drum_bar(S, bar, SURDO, lambda: ins.surdo(True), "surdo", 0.8, -0.1)
        if bar >= 8:
            drum_bar(S, bar, TAMBORIM, lambda: ins.tamborim(int(S.r.integers(3))), "tamborim", 0.8, 0.4)
        if bar % 8 == 0:
            S.add("crash", bar * 4, ins.crash(0), 0.8, -0.2)
        if bar % 4 == 3:
            for i, m in enumerate((84, 88, 91, 96)):
                S.add("sparkle", bar * 4 + 3 + i * 0.125, ins.steel_drum(hz(m), 0.15), 0.35, 0.4)
    notes = parse_bars(RES_MEL, 0, 0)
    first = [x for x in notes if x[0] < 32]
    second = [x for x in notes if x[0] >= 32]
    mallet_line(S, "marimba", first, ins.marimba, 1.0, 0.1)
    steel_line(S, "lead", [(b + 0.5, 0.5, m + 12) for b, d, m in first if d >= 1.0], 0.35, -0.3, roll=False)
    steel_line(S, "lead", second, 0.9, 0.05)
    mallet_line(S, "marimba", [(b, d, diatonic(m, -2, 0)) for b, d, m in second], ins.marimba, 0.6, 0.35)
    cfg = {"bass": (0.4, 0.0), "cavaco": (1.0, 0.12), "pad": (0.24, 0.4), "kick": (0.85, 0.03), "clap": (1.6, 0.2),
           "shaker": (1.3, 0.08), "hats": (1.05, 0.05), "surdo": (0.6, 0.1), "tamborim": (1.0, 0.12),
           "crash": (0.8, 0.12), "sparkle": (0.32, 0.3), "marimba": (0.6, 0.22), "lead": (0.7, 0.22)}
    return S.mixdown(cfg, t60=1.5, rev_gain=0.45, duck={"bass": 0.3, "pad": 0.35})


# =========================================================================== JINGLES
def jingle_victory(r):
    S = Song(132.0, 4, seed=5, tail=3.0, loop=False)
    trip = 1.0 / 3
    mel = [(0, trip, "G4"), (trip, trip, "C5"), (2 * trip, trip, "E5"), (1, 1.0, "G5"), (2, 0.5, "E5"),
           (2.5, 0.5, "G5"), (3, 1.0, "A5"), (4, 0.5, "F5"), (4.5, 0.5, "A5"), (5, trip, "G5"),
           (5 + trip, trip, "A5"), (5 + 2 * trip, trip, "B5"), (6, 3.6, "C6")]
    for b, d, nm in mel:
        m = note(nm)
        S.add("brasslead", b, ins.brass(hz(m), round(d * S.spb * 0.95, 3), 1.3), 1.0, 0.0)
        S.add("steel", b, ins.steel_drum(hz(m + 12), round(min(d * S.spb, 0.6), 3)), 0.45, 0.2)
    for b, d, sym in ((1, 2, "C"), (3, 2, "F"), (5, 1, "G"), (6, 3.6, "C")):
        for j, m in enumerate(voicing(sym, 55, 4)):
            S.add("brass", b, ins.brass(hz(m), round(d * S.spb * 0.95, 3), 0.9), 0.6, [-0.5, 0.5, -0.2, 0.2][j])
        rt = bass_root(sym, 36)
        S.add("bass", b, ins.bass(hz(rt), round(d * S.spb * 0.9, 3)), 1.0)
        S.add("timp", b, ins.timpani(hz(rt - 12 if rt > 40 else rt)), 0.8, -0.1)
    for b in (1, 6):
        S.add("kick", b, ins.kick(), 1.0)
        S.add("crash", b, ins.crash(int(b == 6)), 1.0, -0.2)
    for b in (2, 3, 4):
        S.add("snare", b, ins.snare(b), 0.7, 0.05)
    S.add("snare", 4.5, ins.snare_roll(1.5 * S.spb, 28, 0.2, 1.0), 0.6, 0.05)
    for i, m in enumerate([84, 88, 91, 96, 100, 103, 108]):
        S.add("steel", 6 + i * 0.125, ins.steel_drum(hz(m), 0.2), 0.3, -0.3 + 0.1 * i)
    for p in range(0, 24):
        S.add("shaker", p / 4, ins.shaker(p % 4, p % 4 == 3), (0.5, 0.25, 0.35, 0.8)[p % 4], -0.35)
    cfg = {"brasslead": (0.7, 0.2), "steel": (0.6, 0.25), "brass": (0.45, 0.25), "bass": (0.6, 0.0),
           "timp": (0.7, 0.2), "kick": (0.8, 0.05), "crash": (0.5, 0.15), "snare": (0.55, 0.2), "shaker": (0.3, 0.1)}
    return fade(S.mixdown(cfg, t60=1.8, rev_gain=0.5), 0.0, 0.6)


def trombone(freq_curve, n, wah, vib):
    """Plunger-muted trombone: additive saw through a 'wah' lowpass."""
    t = tvec(n)
    f = freq_curve * (1 + vib * np.sin(TAU * 5.5 * t))
    fc = f * (1.3 + 5.0 * wah)
    y = additive(f, n, lambda k, fk: lowpass_resp(fk, fc, 2.2, 0.4) / k, kmax=50, fmax=9000.0)
    return saturate(y * 1.2, 1.2)


def jingle_lose(r):
    S = Song(90.0, 2, seed=7, tail=2.5, loop=False)
    total = N(4.0)
    t = tvec(total)
    notes = [(0.0, 0.5, "G3"), (0.55, 0.5, "F#3"), (1.1, 0.5, "F3"), (1.7, 1.9, "E3")]
    fcur = np.full(total, float(midi_hz(note("G3"))))
    wah = np.zeros(total)
    vib = np.zeros(total)
    amp = np.zeros(total)
    for i, (t0, d, nm) in enumerate(notes):
        f = float(midi_hz(note(nm)))
        m = t >= t0
        tl = t[m] - t0
        scoop = 2 ** (-60 / 1200 * np.exp(-tl / 0.04))
        if i < 3:
            droop = 2 ** (-40 / 1200 * np.clip((tl - d * 0.6) / (d * 0.4), 0, 1))
        else:
            droop = 2 ** (-110 / 1200 * np.clip((tl - 0.9) / 1.0, 0, 1))
        fcur[m] = f * scoop * droop
        mm = (t >= t0) & (t < t0 + d + 0.06)
        tl = t[mm] - t0
        if i < 3:
            wah[mm] = np.sin(np.pi * np.clip(tl / d, 0, 1)) ** 1.5
            amp[mm] = np.clip(tl / 0.03, 0, 1) * np.clip((d + 0.06 - tl) / 0.08, 0, 1)
        else:
            wah[mm] = 0.4 + 0.6 * (0.5 + 0.5 * np.sin(TAU * 2.2 * tl - np.pi / 2)) * np.exp(-tl / 1.5)
            vib[mm] = 0.012 * np.clip(tl / 0.8, 0, 1)
            amp[mm] = np.clip(tl / 0.03, 0, 1) * np.clip((d + 0.06 - tl) / 0.5, 0, 1)
    amp = onepole_lp(amp, 60.0)
    y = trombone(fcur, total, onepole_lp(wah, 30.0), vib) * amp
    S.add("trombone", 0, y, 1.0, 0.0)
    S.add("tuba", 3.55 / S.spb, ins.bass(hz(28), 0.35), 0.8, 0.0)
    S.add("timp", 3.55 / S.spb, ins.timpani(41.2), 0.4, 0.0)
    for tt in (0.0, 0.55, 1.1, 1.7):
        S.add("brush", tt / S.spb, ins.brush_tap(1), 0.8, 0.2)
    cfg = {"trombone": (0.8, 0.2), "tuba": (0.6, 0.1), "timp": (0.5, 0.2), "brush": (0.5, 0.1)}
    y = S.mixdown(cfg, t60=1.4, rev_gain=0.45)[:, :N(4.4)]
    return fade(y, 0.0, 0.6)


# =========================================================================== registry
REGISTRY = {
    "music_race": (music_race, True, -14.5, "Race theme: tropical baiao/samba-rock, 140 BPM, G major (A-B-A'-B'-bridge)"),
    "music_race_final": (music_race_final, True, -14.0, "Final-lap version: 150 BPM, up a tone, lead +8va, double-time percussion, arp layer"),
    "music_menu": (music_menu, True, -16.0, "Menu/garage bossa nova, 100 BPM, F major (nylon guitar, e-piano, flute, vibes)"),
    "music_results": (music_results, True, -15.0, "Results screen: light celebratory groove, 128 BPM, C major"),
    "jingle_victory": (jingle_victory, False, -14.0, "Victory fanfare (brass + steel pan + timpani)"),
    "jingle_lose": (jingle_lose, False, -15.0, "Comedic sad-trombone 'wah wah wah waaah'"),
}
