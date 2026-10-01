# Turbo Turma — procedural audio

Every sound effect and music track in `assets/audio/` is synthesized from code in
this folder. No samples and no downloads. Rebuilds are deterministic: seeds come
from file names, and the Ogg files are written bit-exact, so a rebuild with no code
changes leaves git with nothing to commit.

## Regenerating

```bash
bpython tools/audio/build_audio.py            # everything (about 5 min, mostly music_race)
bpython tools/audio/build_audio.py sfx        # only SFX       (~20 s)
bpython tools/audio/build_audio.py music      # only music
bpython tools/audio/build_audio.py sfx coin hop   # just the named files
```

Requirements: Python 3.11+ with `numpy`, `scipy` and `soundfile`, plus `ffmpeg`
built with libvorbis. `soundfile` is only used to read files back for the checks,
because it handles Ogg granule positions exactly; without it the build falls back to
ffmpeg decoding, which can report lengths that are a few samples off. Install it with
`bpython -m pip install soundfile`.

Output: OGG Vorbis q6 at 44.1 kHz. SFX are mono in `assets/audio/sfx/`; music is
stereo in `assets/audio/music/`. Total size is about 6.0 MB.

The build checks every file after encoding and prints a table. It decodes the
encoded file and checks that:
* the sample peak is at or below -1 dBFS. If Vorbis overshoots, the file is re-scaled
  and re-encoded.
* there is no DC offset.
* the decoded length is exact.
* for loops, the wrap point doesn't click.

## Files

| Module | Contents |
|---|---|
| `dsp.py` | Toolkit:<br>• oscillators: PolyBLEP saw and pulse, additive with anti-alias roll-off, FM<br>• envelopes, curves and sweeps<br>• FFT-shaped noise (white, pink, brown and band noise), which is periodic and so loop-safe<br>• RBJ biquads: static, circular, and time-varying in blocks<br>• Karplus-Strong string, vectorized one period at a time, with fractional-delay tuning<br>• modal bars and bells<br>• formant voice: additive glottal source shaped by vowel formant tracks, plus STFT formant-shaped breath noise<br>• stochastic-IR convolution reverb (with a circular mode for loops) and a Freeverb-style Schroeder reverb<br>• RMS compressor, look-ahead brickwall limiter and soft clipper<br>• BS.1770 loudness (integrated and max momentary) and true-peak check<br>• loop helpers: wrap-add, crossfade and seam detector<br>• constant-power pan<br>• Ogg I/O |
| `instruments.py` | Shared instruments:<br>• melodic: steel pan, marimba, vibes, synth brass, synth bass, upright (KS), nylon guitar (KS), cavaquinho (KS) with strums, FM e-piano, pad, flute, pluck arp<br>• kit and Brazilian percussion: kick, snare, hats, crash, surdo, ganzá/shaker, tamborim, agogô, triangle, cuíca, clap, rim click, brushes, toms, timpani, snare roll |
| `sfx.py` | One generator per SFX plus `REGISTRY` (name → generator, loop, target LUFS, description) and `PUNCH` (impacts that may use soft saturation instead of limiting) |
| `music.py` | A small sequencer (`Song`): per-track stereo buffers, sidechain ducking from the kick, reverb send, circular mixdown. Also chord and voicing helpers, melodies written as `pos:len:note` per bar, all six pieces, and `REGISTRY` |
| `build_audio.py` | Entry point: render, master, encode, verify, report |

### How loops stay seamless
Loops are rendered circularly instead of being cut and crossfaded:
* FFT-shaped noise is periodic by construction.
* Modulators have an integer number of cycles per loop.
* Oscillator frequencies are scaled so that each loop holds a whole number of cycles. The engines use 45, 90 and 160 Hz over 2 s.
* Events are wrap-added.
* IIR filters run in `circular` mode, which pre-rolls the filter over the loop.
* Reverb tails and notes that ring past the loop end are folded back onto the start.
* The limiter and compressor use wrap-around windows.

The seam check high-passes the loop rotated so the wrap point sits in the middle. It
then compares the high-frequency energy across the seam with the rest of the file. For
music, it compares the seam with the other downbeats, since the loop point is itself a
downbeat. A value of about 1 or less means there is no click. All loops pass.

### Mastering
* `finalize()` normalizes each file to its target loudness (column below). It then
  controls peaks to -1.5 dBFS sample peak, so the decoded peak stays at or below -1 dBFS.
* Impacts in `sfx.PUNCH` can trade a few dB of peak for tanh saturation, which keeps
  them punchy. The remaining excess goes to a look-ahead limiter of at most 5 dB.
* Very transient sounds (thuds, booms, splashes, UI ticks) therefore sit at or below
  target in integrated LUFS. Their max momentary loudness, which the build also prints,
  is in line with the rest.
* Ambience beds are deliberately quiet, around -21 LUFS, and so are UI ticks. Engines
  are -16 LUFS so the game can layer and pitch them.
* Music is mixed at -14 to -16 LUFS: race -14.5, final lap -14, menu -16, results -15.

## Game integration notes
* Loop files are seamless at the sample level. Enable `loop = true` on the
  `AudioStreamOggVorbis` (in its import settings or in code). The loop files are:
  * engines: `engine_*`
  * `drift_skid`, `wind_loop`, `boost_loop`, `bomb_fuse`, `item_roulette`
  * ambience: `crowd_loop`, `waves_loop`, `jungle_loop`
  * music: all `music_*` files
* Engine loops: crossfade idle, mid and high by RPM and set `pitch_scale` between 0.7 and 1.5.
  * Their fundamentals are exactly 45, 90 and 160 Hz, so the crossover points are
    pitch ratios of 2.0 between idle and mid, and 1.78 between mid and high.
  * The exhaust resonances are fixed in Hz, so pitching the files shifts the "pipe" too,
    which fits a cartoon kart.
* `music_race_final` is a separate arrangement: 150 BPM and a whole tone higher. Swap
  tracks with a short crossfade instead of trying to sync them.
* The jingles and `lap`, `final_lap` and `finish` are one-shots.

## SFX (`assets/audio/sfx/`)

| File | Duration | Loop | Ch | Target LUFS | Description |
|---|---:|:---:|:---:|---:|---|
| `engine_idle.ogg` | 2.00 s | yes | mono | -16 | Two-stroke kart engine, ~45 Hz fundamental, 2 s loop |
| `engine_mid.ogg` | 2.00 s | yes | mono | -16 | Engine at ~90 Hz, 2 s loop |
| `engine_high.ogg` | 2.00 s | yes | mono | -16 | Engine at ~160 Hz, 2 s loop |
| `drift_skid.ogg` | 2.00 s | yes | mono | -18 | Tire squeal on asphalt |
| `wind_loop.ogg` | 4.00 s | yes | mono | -20 | Speed wind rush |
| `boost_loop.ogg` | 2.00 s | yes | mono | -15 | Flame roar / jet whoosh while boosting |
| `drift_tier1.ogg` | 1.20 s | no | mono | -15 | Drift charge level 1 (blue sparks) sparkle |
| `drift_tier2.ogg` | 1.24 s | no | mono | -14 | Drift charge level 2 (orange sparks) sparkle |
| `drift_tier3.ogg` | 1.35 s | no | mono | -13 | Drift charge level 3 (purple sparks) sparkle |
| `miniturbo.ogg` | 0.99 s | no | mono | -12 | Mini-turbo release: pop + whoosh + flame |
| `boost_pad.ogg` | 0.86 s | no | mono | -12 | Boost pad: bright whoosh with a zap |
| `rocket_start.ogg` | 2.25 s | no | mono | -11 | Rocket start launch |
| `burnout.ogg` | 1.70 s | no | mono | -14 | Failed start: engine sputter/stall with puffs |
| `hop.ogg` | 0.40 s | no | mono | -15 | Cartoon spring boing (drift hop) |
| `land.ogg` | 0.44 s | no | mono | -15 | Landing thud + suspension creak |
| `land_big.ogg` | 0.82 s | no | mono | -12 | Big landing |
| `bump_wall.ogg` | 0.56 s | no | mono | -12 | Wall hit: cartoony plastic/metal crunch |
| `bump_kart.ogg` | 0.40 s | no | mono | -13 | Kart-kart rubbery bonk |
| `item_box.ogg` | 1.34 s | no | mono | -13 | Item box: glass shatter + magical sparkle |
| `item_roulette.ogg` | 1.00 s | yes | mono | -17 | Item roulette tick loop |
| `item_get.ogg` | 1.50 s | no | mono | -14 | Item obtained ding |
| `coin.ogg` | 0.93 s | no | mono | -15 | Golden seashell pickup, 2-note chime |
| `banana_drop.ogg` | 0.27 s | no | mono | -15 | Banana dropped: squishy plop |
| `banana_slip.ogg` | 0.82 s | no | mono | -14 | Slipping on a banana: squelch + slide |
| `bomb_throw.ogg` | 0.52 s | no | mono | -15 | Bomb throw whoosh |
| `bomb_fuse.ogg` | 1.50 s | yes | mono | -19 | Bomb fuse sizzle loop |
| `explosion.ogg` | 2.51 s | no | mono | -10 | Cartoon explosion with debris |
| `spin_out.ogg` | 1.27 s | no | mono | -14 | Dizzy spin-out slide whistle |
| `countdown_beep.ogg` | 0.74 s | no | mono | -14 | Countdown 3-2-1 beep |
| `countdown_go.ogg` | 1.33 s | no | mono | -12 | GO! tone with sparkle |
| `lap.ogg` | 1.69 s | no | mono | -13 | Lap complete jingle |
| `final_lap.ogg` | 2.67 s | no | mono | -12 | Final lap fanfare |
| `finish.ogg` | 3.65 s | no | mono | -12 | Finish-line whistle + fanfare |
| `wrong_way.ogg` | 0.74 s | no | mono | -17 | Soft wrong-way buzzer |
| `trick.ogg` | 1.25 s | no | mono | -14 | Trick: whoosh + sparkle ting |
| `splash.ogg` | 1.04 s | no | mono | -13 | Water splash |
| `respawn.ogg` | 1.84 s | no | mono | -14 | Magical respawn pop-in |
| `ui_move.ogg` | 0.07 s | no | mono | -22 | Menu cursor tick |
| `ui_select.ogg` | 0.59 s | no | mono | -17 | Menu confirm blip |
| `ui_back.ogg` | 0.56 s | no | mono | -18 | Menu back blip |
| `ui_swap_part.ogg` | 0.54 s | no | mono | -16 | Garage: swap kart part ratchet + pop |
| `ui_color.ogg` | 0.65 s | no | mono | -16 | Garage: paint splat + sparkle |
| `ui_start.ogg` | 2.00 s | no | mono | -13 | Press start confirm |
| `crowd_cheer.ogg` | 3.20 s | no | mono | -14 | Crowd cheering burst |
| `crowd_loop.ogg` | 6.00 s | yes | mono | -22 | Ambient crowd murmur |
| `waves_loop.ogg` | 8.00 s | yes | mono | -21 | Gentle ocean surf |
| `jungle_loop.ogg` | 8.00 s | yes | mono | -22 | Jungle birds & insects ambience |
| `voice_yip.ogg` | 0.28 s | no | mono | -14 | Guara: short happy yip |
| `voice_yahoo.ogg` | 0.85 s | no | mono | -14 | Guara: 'ya-hoo!' |
| `voice_woohoo.ogg` | 0.90 s | no | mono | -14 | Guara: 'woo-hoo!' |
| `voice_ouch.ogg` | 0.54 s | no | mono | -14 | Guara: 'ouch!' |
| `voice_laugh.ogg` | 1.24 s | no | mono | -15 | Guara: giggle/laugh |
| `voice_aww.ogg` | 1.00 s | no | mono | -15 | Guara: disappointed 'awww' |
| `voice_hmph.ogg` | 0.48 s | no | mono | -15 | Guara: grumpy 'hmph' |

## Music (`assets/audio/music/`)

| File | Duration | Loop | Ch | Target LUFS | Description |
|---|---:|:---:|:---:|---:|---|
| `music_race.ogg` | 68.57 s | yes | stereo | -14.5 | Race theme: tropical baiao/samba-rock, 140 BPM, G major (A-B-A'-B'-bridge) |
| `music_race_final.ogg` | 51.20 s | yes | stereo | -14.0 | Final-lap version: 150 BPM, up a tone, lead +8va, double-time percussion, arp layer |
| `music_menu.ogg` | 57.60 s | yes | stereo | -16.0 | Menu/garage bossa nova, 100 BPM, F major (nylon guitar, e-piano, flute, vibes) |
| `music_results.ogg` | 30.00 s | yes | stereo | -15.0 | Results screen: light celebratory groove, 128 BPM, C major |
| `jingle_victory.ogg` | 5.45 s | no | stereo | -14.0 | Victory fanfare (brass + steel pan + timpani) |
| `jingle_lose.ogg` | 4.38 s | no | stereo | -15.0 | Comedic sad-trombone 'wah wah wah waaah' |

### Music details
* **music_race**: G major, 140 BPM, 40 bars, laid out A-B-A'-B'-Bridge.
  * Groove: baião rhythm with the zabumba "3+3+2" kick and bass cell, rock backbeat
    snare, surdo on 2 and 4, a triangle on 16ths, ganzá, tamborim teleco-teco, agogô
    and cuíca, plus a 16th-note cavaquinho strum.
  * Lead: steel-pan melody, with rolls on long notes. Marimba harmonizes in 3rds in A'.
    B' moves the melody to brass with the steel an octave up.
  * Brass: stabs and swells, over a pad.
  * The bridge is a percussion breakdown that builds back up, with a riser, into the
    loop point.
* **music_race_final**: the same song at 150 BPM in A major, 32 bars.
  * The lead is an octave up, doubled by marimba.
  * Percussion is double-time: 16th-note hats, 32nd-note ganzá, a busier tamborim and
    four-on-the-floor kick under the baião cell.
  * Adds a 16th-note arp synth layer, extra crashes and a brass melody an octave up.
* **music_menu**: F major bossa nova, 100 BPM, 24 bars, laid out A-B-A'.
  * Nylon guitar (Karplus-Strong) with thumb bass and syncopated comping, plus upright bass.
  * Rhodes-style FM e-piano.
  * Rim-click bossa clave, brushes and a soft kick.
  * Flute melody in A, vibes in B, both in thirds in A'.
* **music_results**: C major, 128 BPM, 16 bars (exactly 30 s).
  * Marimba melody first, then steel pan with marimba thirds.
  * Clap backbeat, light samba percussion, cavaquinho offbeats.
* **jingle_victory**: a brass fanfare (triplet pickup, I-IV-V-I) doubled by steel pan,
  with timpani, snare roll, crash and an ascending sparkle.
* **jingle_lose**: plunger-muted trombone playing G-F#-F-E. The last note wobbles with
  wah and vibrato and droops, and a tuba "bwomp" ends it.
