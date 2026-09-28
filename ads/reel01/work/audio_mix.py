#!/usr/bin/env python3
"""STEP 7 — audio: voice clean-up + loudness matching, optional music bed + SFX, mastering.

Re-runnable: every run rebuilds all outputs from the inputs below (nothing is modified in place).

Inputs
  work/edit.json                   clip order + frame counts (30 fps)          [required]
  work/captions.json               word timings -> "speech present" for ducking [required only with music]
  work/norm/clip{1,2,3}.wav        trimmed voice, 48 kHz / 24-bit / stereo      [required]
  assets/music.mp3                 music bed                                    [OPTIONAL — skipped if absent]
  assets/sfx/{whoosh,pop,ding}.wav sound effects                                [OPTIONAL — each skipped if absent]
  work/audio/sfx_cues.json         extra SFX cues, e.g. [{"sfx":"pop","frame":312},{"sfx":"ding","t":25.1}]
                                   ("frame" = GLOBAL reel frame @30 fps, or "t" = seconds)   [OPTIONAL]

Outputs (work/audio/)
  voice_master.wav    voice only ("nomusic" track), 48 kHz / 24-bit / stereo, exactly 1 353 600 samples (28.2 s)
  music_master.wav    voice + music + SFX (bit-identical to voice_master.wav when neither music nor SFX exist)
  audio_report.json   every measurement, gain and decision

Signal chain
  per clip : 80 Hz HPF (2nd-order Butterworth, 12 dB/oct)
             -> objective sibilance measurement -> light split-band de-ess ONLY for clips that measure harsh
             -> static gain so every clip hits VOICE_CLIP_LUFS (measured with ffmpeg ebur128)
             -> 5 ms raised-cosine fade-out/fade-in at every clip edge (in place: timing never shifts)
  timeline : clip1 | clip2 | clip3 (hard cuts, back-to-back from t=0) | 3.5 s end screen (digital silence)
  music    : (optional) loudness-referenced bed, caption-driven ducking, end-screen rise, 0.5 s fade-out
  sfx      : (optional) whooshes at the joins/slab entrances + cue file, each >= 10 dB below the voice
  master   : static make-up gain + gentle look-ahead TRUE-PEAK limiter (4x oversampled detection), iterated
             until ffmpeg ebur128 reads -14.0 LUFS integrated and TP ~= -1.5 dBTP; then an AAC-192k
             round-trip check makes sure the encoded file still measures <= -1.0 dBTP.

Why not ffmpeg `loudnorm` two-pass linear?  To bring these clips to -14 LUFS the static gain pushes clip-2
peaks to ~+1 dBTP.  In that case loudnorm cannot stay linear and silently switches to its dynamic (AGC)
mode, which pumps speech.  (The script re-checks this every run and records loudnorm's own verdict in the
report.)  Its first-pass meter also disagrees with ebur128 by up to 0.4 LU on these short clips.
So: static gain + a transparent true-peak limiter that only touches the few loudest peaks.

Usage
  python3 work/audio_mix.py [--music PATH] [--sfx-dir DIR] [--cues JSON] [--skip-aac-check] [--out-dir DIR]
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from scipy import ndimage as nd
from scipy import signal as sg
from scipy.io import wavfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
OUT_DIR = os.path.join(WORK, "audio")

# ─── Timeline ────────────────────────────────────────────────────────────────────────────────
FS = 48000
FPS = 30
SPF = FS // FPS                 # 1600 samples per video frame
END_SCREEN_FRAMES = 105         # 3.5 s — must match remotion/src/timeline.ts END_SCREEN_FRAMES
MAX_LENGTH_FIX = 8              # clip WAVs may be padded/trimmed by at most this many samples

# ─── Voice processing ────────────────────────────────────────────────────────────────────────
VOICE_CLIP_LUFS = -16.0         # every clip is matched to this integrated loudness before concat
HPF_HZ = 80.0                   # gentle high-pass: removes rumble / handling noise below the voice
HPF_ORDER = 2                   # 2nd-order Butterworth = 12 dB/oct
JOIN_FADE_MS = 5.0              # raised-cosine fades at every clip edge (declick; no timing shift)

# Sibilance measurement (10 ms frames, mono mid signal, speech-active frames only).
SIB_BAND = (5000.0, 10000.0)    # "s / sh / ch" energy
PRES_BAND = (1000.0, 4000.0)    # vowel presence band used as reference
FRAME_MS = 10.0
ACTIVE_BELOW_P95_DB = 30.0      # a frame is "speech-active" if within 30 dB of the clip's p95 frame level
# A clip is judged HARSH when at least DEESS_MIN_FLAGS of these three indicators exceed their limit:
#  ltas_ratio_db  : long-term energy 5–10 kHz vs 1–4 kHz. Normal close-mic speech sits around -12…-20 dB.
#  svr_p99_db     : 99th-pct 5–10 kHz frame level minus 95th-pct broadband (loud vowel) frame level —
#                   "how loud the esses are next to the vowels".  Comfortable speech: <= -14 dB.
#  burst_rel_i_db : loudest 10 ms 5–10 kHz burst minus the clip's integrated loudness — "how loud the
#                   worst ess is once every clip plays at the same LUFS".
DEESS_LIMITS = {"ltas_ratio_db": -10.0, "svr_p99_db": -12.0, "burst_rel_i_db": -7.0}
DEESS_MIN_FLAGS = 2
# Light de-esser (only for clips judged harsh): split-band, only the >5 kHz band is turned down, only
# while a sibilant burst is present, never by more than DEESS_MAX_GR_DB.
DEESS_SPLIT_HZ = 5000.0
DEESS_TARGET_SVR_DB = -14.0     # threshold = loud-vowel level + this
DEESS_RATIO = 3.0
DEESS_MAX_GR_DB = 4.0

# ─── Music (optional) ────────────────────────────────────────────────────────────────────────
# All music levels are relative to the SPEECH loudness: the track is first normalised to the voice's
# integrated loudness (0 LU), then these fader values are applied.
MUSIC_BED_DB = -20.0            # between phrases
MUSIC_DUCK_DB = -26.0           # while speech is present
MUSIC_END_DB = -14.0            # on the end screen (from END_SCREEN_START = frame 741 = 24.7 s)
DUCK_ATTACK_S = 0.150           # full 6 dB duck takes 150 ms
DUCK_RELEASE_S = 0.300          # full 6 dB recovery takes 300 ms (same slew used for the end-screen rise)
DUCK_LOOKAHEAD_S = 0.150        # start ducking 150 ms before a word so the onset is never masked
SPEECH_MERGE_GAP_S = 0.15       # word gaps shorter than this count as continuous speech
SPEECH_TAIL_S = 0.05            # word end + decay
MUSIC_FADE_IN_S = 0.010
MUSIC_FADE_OUT_S = 0.5          # fade-out at the very end of the reel
MUSIC_LOOP_XFADE_S = 0.050      # if the track is shorter than the reel it is looped with this crossfade

# ─── SFX (optional) ──────────────────────────────────────────────────────────────────────────
SFX_NAMES = ("whoosh", "pop", "ding")
SFX_EXTS = (".wav", ".flac", ".aif", ".aiff", ".mp3")
SFX_BELOW_VOICE_DB = 12.0       # SFX loudest 100 ms window sits 12 dB under the voice LUFS (spec: >= 10)
SFX_ALIGN = {"whoosh": "peak", "pop": "onset", "ding": "onset"}   # which part of the sound hits the cue
# Built-in cues (GLOBAL frames @30 fps).  Chip pops / CTA ding depend on graphics timing -> cue file.
DEFAULT_SFX_CUES = [
    {"sfx": "whoosh", "frame": 0, "note": "clip 1 slab entrance (clip1 local frame 0)"},
    {"sfx": "whoosh", "frame": 229, "note": "join clip1 -> clip2 (229/30 s)"},
    {"sfx": "whoosh", "frame": 229 + 7, "note": "clip 2 slab entrance (clip2 local frame ~7)"},
    {"sfx": "whoosh", "frame": 506, "note": "join clip2 -> clip3 (506/30 s)"},
]

# ─── Master ──────────────────────────────────────────────────────────────────────────────────
MASTER_LUFS = -14.0
MASTER_TP_TARGET = -1.5         # measured (ffmpeg ebur128) true peak we aim for before AAC
LIMITER_CEILING_START = -1.6    # limiter ceiling; tightened automatically if a measurement says so
LIMITER_LOOKAHEAD_MS = 3.0      # = attack (gain ramps down linearly over 3 ms before a peak)
LIMITER_RELEASE_MS = 100.0      # exponential release time constant
OVERSAMPLE = 4                  # true-peak detection at 192 kHz
LUFS_TOL = 0.05
AAC_TP_LIMIT = -1.0             # spec: encoded AAC must still measure <= -1.0 dBTP
AAC_TP_MARGIN = 0.1
AAC_BITRATE = "192k"


# ═════════════════════════════════════════════════════════════════════════════════════════════
# I/O helpers
# ═════════════════════════════════════════════════════════════════════════════════════════════
def rel(p):
    return os.path.relpath(p, ROOT)


def db(x):
    return 20.0 * math.log10(max(float(x), 1e-12))


def read_audio(path):
    """Decode any audio file to float64 (n, 2) at 48 kHz via ffmpeg (24-bit PCM -> float is exact)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-map", "0:a:0",
                          "-f", "f64le", "-ac", "2", "-ar", str(FS), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f8").reshape(-1, 2).copy()


def write_wav24(path, x):
    """Write float (n, 2) as 48 kHz / 24-bit PCM WAV, deterministically (bit-exact, no encoder tag).

    Samples are rounded to the 24-bit grid here, so ffmpeg's float->s32->s24 path is lossless.
    No dither: at 24 bit the rounding error sits ~-144 dBFS.
    """
    q = np.round(np.clip(x, -1.0, 1.0 - 2.0 ** -23) * 2.0 ** 23) / 2.0 ** 23
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "f64le", "-ar", str(FS),
                    "-ch_layout", "stereo", "-i", "-", "-c:a", "pcm_s24le",
                    "-fflags", "+bitexact", "-flags:a", "+bitexact", path],
                   input=np.ascontiguousarray(q, dtype="<f8").tobytes(), check=True)


def write_tmp_float(path, x):
    wavfile.write(path, FS, x.astype(np.float32))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ffmpeg_ebur128(path, stream="0:a:0"):
    """Authoritative measurement: ffmpeg `ebur128=peak=true+sample`.

    Returns the printed summary (I, LRA, TP, sample peak — 0.1 resolution) plus the same values from
    the filter's metadata (I/LRA to 0.001 LU, peaks to 0.001 linear) for tighter bookkeeping.
    """
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", path, "-map", stream,
                        "-af", "ebur128=peak=true+sample:metadata=1,ametadata=mode=print:file=-",
                        "-f", "null", "-"], capture_output=True, text=True, check=True)
    err, out = p.stderr, p.stdout
    summ = err[err.rfind("Summary:"):]

    def grab(pattern, text):
        m = re.search(pattern, text, re.S)
        if not m:
            return None
        return float("-inf") if m.group(1) == "-inf" else float(m.group(1))

    num = r"(-?inf|-?\d+(?:\.\d+)?)"
    res = {
        "I_lufs": grab(r"I:\s+" + num + r" LUFS", summ),
        "LRA_lu": grab(r"LRA:\s+" + num + r" LU", summ),
        "sample_peak_dbfs": grab(r"Sample peak:\s+Peak:\s+" + num, summ),
        "true_peak_dbtp": grab(r"True peak:\s+Peak:\s+" + num, summ),
    }

    def last(key):
        vals = re.findall(r"^lavfi\.r128\." + re.escape(key) + r"=(\S+)$", out, re.M)
        return float(vals[-1]) if vals else None

    I_p, LRA_p, tp_lin, sp_lin = last("I"), last("LRA"), last("true_peak"), last("sample_peak")
    res["precise"] = {
        "I_lufs": I_p, "LRA_lu": LRA_p,
        "true_peak_dbtp": round(db(tp_lin), 3) if tp_lin else None,
        "sample_peak_dbfs": round(db(sp_lin), 3) if sp_lin else None,
    }
    return res


def ffmpeg_measure_array(x, tmpdir, name):
    path = os.path.join(tmpdir, name + ".wav")
    write_tmp_float(path, x)
    return ffmpeg_ebur128(path)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Internal meters (fast, used inside iterations; cross-checked against ffmpeg in the report)
# ═════════════════════════════════════════════════════════════════════════════════════════════
def _k_weighting_sos(fs):
    """ITU-R BS.1770-4 K-weighting (shelf + RLB high-pass), same analogue prototypes as libebur128."""
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = math.tan(math.pi * f0 / fs)
    Vh = 10 ** (G / 20)
    Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    shelf = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0,
             1.0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    f0, Q = 38.13547087602444, 0.5003270373238773
    K = math.tan(math.pi * f0 / fs)
    a0 = 1 + K / Q + K * K
    rlb = [1.0, -2.0, 1.0, 1.0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    return np.array([shelf, rlb])


K_SOS = _k_weighting_sos(FS)


def lufs_integrated(x):
    """BS.1770-4 gated integrated loudness (400 ms blocks, 75 % overlap, -70 LUFS / -10 LU gates)."""
    y = sg.sosfilt(K_SOS, x, axis=0)
    ms = np.cumsum(np.concatenate([np.zeros((1, 2)), y ** 2]), axis=0)
    blk, hop = int(0.4 * FS), int(0.1 * FS)
    starts = np.arange(0, len(y) - blk + 1, hop)
    z = ((ms[starts + blk] - ms[starts]) / blk).sum(axis=1)
    lk = -0.691 + 10 * np.log10(z + 1e-20)
    abs_g = z[lk > -70]
    if not len(abs_g):
        return float("-inf")
    rel_thr = -0.691 + 10 * np.log10(abs_g.mean()) - 10
    return float(-0.691 + 10 * np.log10(z[(lk > -70) & (lk > rel_thr)].mean()))


def peak_loudness(x, win_s=0.1):
    """Loudest K-weighted `win_s` window (LUFS-like) — used to level short SFX."""
    y = sg.sosfilt(K_SOS, x, axis=0)
    n = max(1, int(win_s * FS))
    e = nd.uniform_filter1d((y ** 2).sum(axis=1), n, mode="constant")
    return float(-0.691 + 10 * np.log10(e.max() + 1e-20))


def oversampled_abs_peak(x):
    """Per-48k-sample true-peak envelope: max |x| over the 4 interpolated points in [n, n+1), both channels."""
    up = sg.resample_poly(x, OVERSAMPLE, 1, axis=0)
    return np.abs(up).reshape(len(x), OVERSAMPLE, 2).max(axis=(1, 2))


def true_peak_dbtp(x):
    return db(oversampled_abs_peak(x).max())


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Voice processing
# ═════════════════════════════════════════════════════════════════════════════════════════════
HPF_SOS = sg.butter(HPF_ORDER, HPF_HZ, btype="highpass", fs=FS, output="sos")
SIB_SOS = sg.butter(4, SIB_BAND, btype="bandpass", fs=FS, output="sos")
PRES_SOS = sg.butter(4, PRES_BAND, btype="bandpass", fs=FS, output="sos")
SPLIT_SOS = sg.butter(4, DEESS_SPLIT_HZ, btype="highpass", fs=FS, output="sos")


def highpass(x):
    """Causal (minimum-phase, like a console HPF) 80 Hz Butterworth; steady-state initial conditions so
    the clip's first sample does not produce a start-up thump."""
    zi = sg.sosfilt_zi(HPF_SOS)
    out = np.empty_like(x)
    for ch in range(x.shape[1]):
        out[:, ch], _ = sg.sosfilt(HPF_SOS, x[:, ch], zi=zi * x[0, ch])
    return out


def sibilance_metrics(x, clip_lufs):
    """Objective sibilance numbers on the mono mid signal (clips are ~mono: L/R correlation > 0.999)."""
    m = x.mean(axis=1)
    hb = sg.sosfiltfilt(SIB_SOS, m)
    pb = sg.sosfiltfilt(PRES_SOS, m)
    N = int(FRAME_MS / 1000 * FS)
    nf = len(m) // N

    def lev(s):
        return 10 * np.log10((s[:nf * N].reshape(nf, N) ** 2).mean(axis=1) + 1e-20)

    Lh, Lp, La = lev(hb), lev(pb), lev(m)
    act = La >= np.percentile(La, 95) - ACTIVE_BELOW_P95_DB
    ltas = 10 * np.log10((10 ** (Lh[act] / 10)).sum() / (10 ** (Lp[act] / 10)).sum())
    sib = act & (Lh > Lp)                       # frames where the 5–10 kHz band dominates = sibilants
    vowel_ref = float(np.percentile(La[act], 95))
    p99h = float(np.percentile(Lh[act], 99))
    maxh = float(Lh[act].max())
    # up to 5 distinct loudest bursts (>= 60 ms apart) for the report
    bursts, taken = [], []
    for k in np.argsort(Lh)[::-1]:
        if not act[k] or any(abs(k - t) < 6 for t in taken):
            continue
        taken.append(k)
        bursts.append({"t_local_s": round(k * FRAME_MS / 1000, 2), "band_5_10k_dbfs": round(float(Lh[k]), 1),
                       "band_1_4k_dbfs": round(float(Lp[k]), 1)})
        if len(bursts) == 5:
            break
    res = {
        "ltas_ratio_db": round(float(ltas), 2),
        "svr_p99_db": round(p99h - vowel_ref, 2),
        "svr_max_db": round(maxh - vowel_ref, 2),
        "burst_rel_i_db": round(maxh - clip_lufs, 2),
        "sibilant_frames_pct_of_speech": round(100.0 * sib.sum() / max(1, act.sum()), 1),
        "sib_band_p99_dbfs": round(p99h, 2),
        "sib_band_max_dbfs": round(maxh, 2),
        "loud_vowel_ref_p95_dbfs": round(vowel_ref, 2),
        "loudest_bursts": bursts,
    }
    flags = {k: res[k] > lim for k, lim in DEESS_LIMITS.items()}
    res["flags"] = flags
    res["harsh"] = sum(flags.values()) >= DEESS_MIN_FLAGS
    return res


def deess(x, metrics):
    """Light split-band de-esser.

    detector : 5 ms RMS of the 5–10 kHz band, compared with threshold = loud-vowel level + DEESS_TARGET_SVR_DB;
               gain reduction = excess * (1 - 1/ratio), capped at DEESS_MAX_GR_DB, and scaled by how
               sibilant the moment is (0 when the 5–10 kHz band is >= 3 dB under the 1–4 kHz band,
               full when it is >= 3 dB above) so vowels/plosives are left alone.
    smoothing: 5 ms hold + 10 ms Hann (zero-phase => ~5 ms look-ahead, no clicks).
    apply    : complementary zero-phase split at 5 kHz: y = x - (1 - g) * high  (g = 1 -> bit-transparent).
    """
    m = x.mean(axis=1)
    hb = sg.sosfiltfilt(SIB_SOS, m)
    pb = sg.sosfiltfilt(PRES_SOS, m)
    w = int(0.005 * FS)
    Lh = 10 * np.log10(nd.uniform_filter1d(hb ** 2, w) + 1e-20)
    Lp = 10 * np.log10(nd.uniform_filter1d(pb ** 2, w) + 1e-20)
    thr = metrics["loud_vowel_ref_p95_dbfs"] + DEESS_TARGET_SVR_DB
    gr = np.minimum(DEESS_MAX_GR_DB, np.maximum(0.0, Lh - thr) * (1 - 1 / DEESS_RATIO))
    gr *= np.clip((Lh - Lp + 3.0) / 6.0, 0.0, 1.0)
    gr = nd.maximum_filter1d(gr, w)
    han = np.hanning(int(0.010 * FS))
    gr = sg.fftconvolve(gr, han / han.sum(), mode="same")
    g = 10 ** (-gr / 20)
    high = sg.sosfiltfilt(SPLIT_SOS, x, axis=0)
    y = x - (1 - g)[:, None] * high
    stats = {
        "threshold_dbfs_5ms_rms": round(float(thr), 2),
        "max_gain_reduction_db": round(float(gr.max()), 2),
        "pct_time_gr_over_1db": round(100.0 * float((gr > 1.0).mean()), 2),
        "pct_time_gr_over_0_1db": round(100.0 * float((gr > 0.1).mean()), 2),
    }
    return y, stats


def edge_fades(x, ms=JOIN_FADE_MS):
    """Raised-cosine fade-in on the first and fade-out on the last `ms` of a clip (in place, no overlap)."""
    n = int(round(ms / 1000 * FS))
    ramp = 0.5 - 0.5 * np.cos(np.pi * (np.arange(n) + 0.5) / n)
    y = x.copy()
    y[:n] *= ramp[:, None]
    y[-n:] *= ramp[::-1, None]
    return y, n


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Master limiter
# ═════════════════════════════════════════════════════════════════════════════════════════════
def true_peak_limiter(x, ceiling_dbtp):
    """Gentle look-ahead true-peak limiter (offline, zero added latency).

    r[n]  = gain needed so the 4x-oversampled peak in [n, n+1) stays under the ceiling
    gmin  = min of r over the NEXT L samples (look-ahead window)
    R     = gain reduction in dB with exponential release (instant attack on gmin)
    g     = moving average of 10^(-R/20) over the PREVIOUS L+1 samples  -> 3 ms linear attack ramp.
    Every average at a peak n only contains values <= r[n], so the ceiling is guaranteed by construction.
    """
    c = 10 ** (ceiling_dbtp / 20)
    p = oversampled_abs_peak(x)
    r = np.minimum(1.0, c / np.maximum(p, 1e-12))
    L = int(round(LIMITER_LOOKAHEAD_MS / 1000 * FS)) // 2 * 2         # even -> odd window L+1
    gmin = nd.minimum_filter1d(r, L + 1, origin=-(L // 2), mode="constant", cval=1.0)   # r[n..n+L]
    Rmin = -20 * np.log10(gmin)
    # exponential release of the dB gain reduction: R[n] = max(Rmin[n], a*R[n-1]), vectorised via
    # log R[n] = max_k(log Rmin[k] + c*k) - c*n  (running maximum)
    cst = 1.0 / (LIMITER_RELEASE_MS / 1000 * FS)
    k = np.arange(len(Rmin))
    logR = np.maximum.accumulate(np.log(np.maximum(Rmin, 1e-9)) + cst * k) - cst * k
    R = np.where(logR > math.log(1e-8), np.exp(logR), 0.0)
    g = nd.uniform_filter1d(10 ** (-R / 20), L + 1, origin=L // 2, mode="nearest")  # g2[n-L..n]
    y = x * g[:, None]
    grdb = -20 * np.log10(g)
    stats = {
        "ceiling_dbtp": round(ceiling_dbtp, 3),
        "max_gain_reduction_db": round(float(grdb.max()), 2),
        "pct_time_gr_over_0_5db": round(100.0 * float((grdb > 0.5).mean()), 3),
        "pct_time_gr_over_1db": round(100.0 * float((grdb > 1.0).mean()), 3),
        "pct_time_gr_over_0_1db": round(100.0 * float((grdb > 0.1).mean()), 3),
    }
    return y, stats


def master(pre, ceiling_dbtp, lufs_target):
    """Static gain + limiter, iterated (internal meter) until integrated loudness == lufs_target."""
    gain_db = lufs_target - lufs_integrated(pre)
    for it in range(1, 9):
        y, st = true_peak_limiter(pre * 10 ** (gain_db / 20), ceiling_dbtp)
        err = lufs_target - lufs_integrated(y)
        if abs(err) < 0.005:
            break
        gain_db += err
    st["makeup_gain_db"] = round(gain_db, 3)
    st["internal_iterations"] = it
    return y, st


def master_verified(pre, name, tmpdir, aac_check=True):
    """Master, then let ffmpeg be the judge: re-aim loudness / ceiling until ffmpeg ebur128 reads
    I = -14.0 (+/-0.05) and TP <= MASTER_TP_TARGET, and (optionally) the AAC-192k encode <= -1.0 dBTP."""
    ceiling, lufs_aim, log = LIMITER_CEILING_START, MASTER_LUFS, []
    for attempt in range(1, 7):
        y, st = master(pre, ceiling, lufs_aim)
        meas = ffmpeg_measure_array(y, tmpdir, f"{name}_try{attempt}")
        I_ff, tp_ff = meas["precise"]["I_lufs"], meas["precise"]["true_peak_dbtp"]
        entry = {"attempt": attempt, "limiter_ceiling_dbtp": round(ceiling, 3),
                 "internal_lufs_aim": round(lufs_aim, 3), "ffmpeg_I": I_ff, "ffmpeg_TP": tp_ff}
        ok = True
        if abs(I_ff - MASTER_LUFS) > LUFS_TOL:
            lufs_aim += MASTER_LUFS - I_ff
            ok = False
        if tp_ff > MASTER_TP_TARGET + 0.02:
            ceiling -= tp_ff - MASTER_TP_TARGET + 0.02
            ok = False
        if ok and aac_check:
            aac = aac_roundtrip(y, tmpdir, f"{name}_try{attempt}")
            entry["aac_roundtrip"] = aac
            if aac["true_peak_dbtp"] > AAC_TP_LIMIT - AAC_TP_MARGIN:
                ceiling -= aac["true_peak_dbtp"] - (AAC_TP_LIMIT - AAC_TP_MARGIN)
                ok = False
        log.append(entry)
        if ok:
            break
    else:
        print(f"WARNING: {name}: mastering did not converge, using last attempt", file=sys.stderr)
    return y, st, log


def aac_roundtrip(x, tmpdir, name):
    """Encode like the final mux (AAC-LC 48 kHz 192 kbps stereo, .m4a) and measure the decoded result."""
    wav = os.path.join(tmpdir, name + "_aac_src.wav")
    m4a = os.path.join(tmpdir, name + ".m4a")
    write_tmp_float(wav, x)
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", wav, "-c:a", "aac", "-profile:a", "aac_low",
                    "-b:a", AAC_BITRATE, "-ar", str(FS), "-ac", "2", m4a], check=True)
    meas = ffmpeg_ebur128(m4a)
    return {"I_lufs": meas["precise"]["I_lufs"], "true_peak_dbtp": meas["precise"]["true_peak_dbtp"],
            "summary": {k: meas[k] for k in ("I_lufs", "LRA_lu", "true_peak_dbtp")}}


def loudnorm_linear_check(pre, tmpdir):
    """Ask ffmpeg loudnorm (two-pass, linear=true) whether it could stay linear for this material."""
    path = os.path.join(tmpdir, "loudnorm_check.wav")
    write_tmp_float(path, pre)
    base = f"loudnorm=I={MASTER_LUFS}:TP={MASTER_TP_TARGET}:LRA=20"

    def run(af):
        err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", path, "-af", af,
                              "-f", "null", "-"], capture_output=True, text=True, check=True).stderr
        return json.loads(err[err.rfind("{"):err.rfind("}") + 1])

    p1 = run(base + ":print_format=json")
    p2 = run(base + f":measured_I={p1['input_i']}:measured_TP={p1['input_tp']}:measured_LRA={p1['input_lra']}"
                    f":measured_thresh={p1['input_thresh']}:offset={p1['target_offset']}:linear=true:print_format=json")
    return {"pass1_input_i": float(p1["input_i"]), "pass1_input_tp": float(p1["input_tp"]),
            "pass2_normalization_type": p2["normalization_type"],
            "note": "loudnorm falls back to 'dynamic' when the static gain would exceed TP; "
                    "that is why a static gain + true-peak limiter is used instead"}


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Music + SFX (optional)
# ═════════════════════════════════════════════════════════════════════════════════════════════
def speech_intervals(captions, clip_start_s):
    """Global [start, end] seconds where speech is present, from word timings (robust vs. breaths/noise)."""
    iv = sorted((clip_start_s[w["clip"]] + w["start"], clip_start_s[w["clip"]] + w["end"] + SPEECH_TAIL_S)
                for w in captions)
    merged = []
    for a, b in iv:
        if merged and a - merged[-1][1] < SPEECH_MERGE_GAP_S:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def music_envelope_db(n, speech, end_rise_s):
    """Fader automation in dB (relative to speech loudness), computed at 1 kHz and interpolated.

    target = DUCK during speech (from DUCK_LOOKAHEAD_S before each word), BED between phrases,
             END from the end-screen start; slew-limited: 6 dB / 150 ms down, 6 dB / 300 ms up.
    """
    cr = 1000
    nc = int(math.ceil(n / FS * cr)) + 1
    t = np.arange(nc) / cr
    tgt = np.full(nc, MUSIC_BED_DB)
    for a, b in speech:
        tgt[(t >= a - DUCK_LOOKAHEAD_S) & (t < b)] = MUSIC_DUCK_DB
    tgt[t >= end_rise_s] = MUSIC_END_DB
    down = (MUSIC_BED_DB - MUSIC_DUCK_DB) / DUCK_ATTACK_S / cr
    up = (MUSIC_BED_DB - MUSIC_DUCK_DB) / DUCK_RELEASE_S / cr
    env = np.empty(nc)
    e = tgt[0]
    for i in range(nc):
        e = max(tgt[i], e - down) if tgt[i] < e else min(tgt[i], e + up)
        env[i] = e
    return np.interp(np.arange(n) / FS, t, env)


def build_music(path, n, voice_lufs, speech, end_rise_s):
    mus = read_audio(path)
    src_len = len(mus)
    looped = False
    if len(mus) < n:                                   # loop with a short crossfade
        looped = True
        xf = int(MUSIC_LOOP_XFADE_S * FS)
        ramp = np.linspace(0, 1, xf)[:, None]
        out = mus.copy()
        while len(out) < n:
            out = np.concatenate([out[:-xf], out[-xf:] * (1 - ramp) + mus[:xf] * ramp, mus[xf:]])
        mus = out
    mus = mus[:n]
    m_lufs = lufs_integrated(mus)
    mus = mus * 10 ** ((voice_lufs - m_lufs) / 20)    # 0 LU relative to the speech
    env_db = music_envelope_db(n, speech, end_rise_s)
    gain = 10 ** (env_db / 20)
    fi, fo = int(MUSIC_FADE_IN_S * FS), int(MUSIC_FADE_OUT_S * FS)
    gain[:fi] *= np.linspace(0, 1, fi)
    gain[-fo:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo)      # 0.5 s cosine fade-out
    bed = mus * gain[:, None]
    info = {"status": "used", "path": rel(path), "source_seconds": round(src_len / FS, 3), "looped": looped,
            "source_lufs": round(m_lufs, 2), "normalised_to_lufs": round(voice_lufs, 2),
            "fader_db": {"bed": MUSIC_BED_DB, "ducked": MUSIC_DUCK_DB, "end_screen": MUSIC_END_DB},
            "duck_attack_s": DUCK_ATTACK_S, "duck_release_s": DUCK_RELEASE_S, "duck_lookahead_s": DUCK_LOOKAHEAD_S,
            "end_rise_from_s": round(end_rise_s, 4), "fade_out_s": MUSIC_FADE_OUT_S,
            "envelope_checkpoints_db": {f"{s:.2f}s": round(float(env_db[min(n - 1, int(s * FS))]), 2)
                                        for s in (0.0, 5.5, 12.0, 24.5, 24.7, 25.0, 27.0)}}
    return bed, info


def find_sfx(sfx_dir):
    found = {}
    for name in SFX_NAMES:
        for ext in SFX_EXTS:
            p = os.path.join(sfx_dir, name + ext)
            if os.path.isfile(p):
                found[name] = p
                break
    return found


def build_sfx(files, cues, n, voice_lufs):
    track = np.zeros((n, 2))
    placed, levels = [], {}
    sounds = {}
    for name, path in files.items():
        s = read_audio(path)
        pl = peak_loudness(s)
        g_db = (voice_lufs - SFX_BELOW_VOICE_DB) - pl
        s = s * 10 ** (g_db / 20)
        env = nd.uniform_filter1d(np.abs(s).max(axis=1), int(0.01 * FS))
        sounds[name] = (s, int(np.argmax(env)))
        levels[name] = {"path": rel(path), "seconds": round(len(s) / FS, 3), "peak_100ms_lufs_raw": round(pl, 2),
                        "gain_db": round(g_db, 2),
                        "peak_100ms_rel_voice_db": round(peak_loudness(s) - voice_lufs, 2)}
    for cue in cues:
        name = cue["sfx"]
        if name not in sounds:
            placed.append({**cue, "status": "skipped (file absent)"})
            continue
        s, pk = sounds[name]
        t = cue["frame"] / FPS if "frame" in cue else float(cue["t"])
        start = int(round(t * FS)) - (pk if SFX_ALIGN.get(name) == "peak" else 0)
        start = max(0, start)
        end = min(n, start + len(s))
        track[start:end] += s[:end - start]
        placed.append({**cue, "status": "placed", "start_s": round(start / FS, 4)})
    return track, levels, placed


# ═════════════════════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--music", default=os.path.join(ROOT, "assets", "music.mp3"))
    ap.add_argument("--sfx-dir", default=os.path.join(ROOT, "assets", "sfx"))
    ap.add_argument("--cues", default=os.path.join(OUT_DIR, "sfx_cues.json"))
    ap.add_argument("--skip-aac-check", action="store_true")
    ap.add_argument("--out-dir", default=OUT_DIR, help="where the masters + report go (default work/audio)")
    args = ap.parse_args()
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    edit = json.load(open(os.path.join(WORK, "edit.json"), encoding="utf-8"))
    assert edit["fps"] == FPS
    clips = sorted(edit["clips"], key=lambda c: c["clip"])
    tl_ts = os.path.join(ROOT, "remotion", "src", "timeline.ts")          # read-only consistency check
    if os.path.isfile(tl_ts):
        m = re.search(r"END_SCREEN_FRAMES\s*=\s*(\d+)", open(tl_ts, encoding="utf-8").read())
        if m and int(m.group(1)) != END_SCREEN_FRAMES:
            print(f"WARNING: timeline.ts END_SCREEN_FRAMES={m.group(1)} != {END_SCREEN_FRAMES}", file=sys.stderr)

    report = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
              "script": "work/audio_mix.py",
              "ffmpeg": subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.split("\n")[0],
              "meter": "ffmpeg ebur128=peak=true+sample (summary = 0.1 resolution; 'precise' = filter metadata)"}

    with tempfile.TemporaryDirectory(prefix="audio_mix_") as tmp:
        # ── 1. load + verify exact lengths ────────────────────────────────────────────────────
        voice_clips, tl = [], []
        for c in clips:
            path = os.path.join(WORK, "norm", f"clip{c['clip']}.wav")
            x = read_audio(path)
            want = c["frames"] * SPF
            fix = want - len(x)
            if abs(fix) > MAX_LENGTH_FIX:
                sys.exit(f"clip{c['clip']}.wav has {len(x)} samples, expected {want} — refusing to fix {fix}")
            x = np.concatenate([x, np.zeros((fix, 2))]) if fix > 0 else x[:want]
            tl.append({"clip": c["clip"], "frames": c["frames"], "expected_samples": want,
                       "file_samples": want - fix, "padded(+)/trimmed(-)": fix})
            voice_clips.append((c["clip"], path, x))
        end_n = END_SCREEN_FRAMES * SPF
        total_frames = sum(c["frames"] for c in clips) + END_SCREEN_FRAMES
        total_n = total_frames * SPF
        clip_start_n = np.cumsum([0] + [c["frames"] * SPF for c in clips])
        report["timeline"] = {"fs": FS, "fps": FPS, "clips": tl, "end_screen_frames": END_SCREEN_FRAMES,
                              "end_screen_samples": end_n, "total_frames": total_frames,
                              "total_samples": total_n, "total_seconds": total_n / FS,
                              "clip_start_samples": [int(v) for v in clip_start_n[:-1]],
                              "end_screen_start_s": round(clip_start_n[-1] / FS, 6)}

        # ── 2. per clip: measure, HPF, sibilance decision, (de-ess), loudness match, edge fades ─
        clip_reports, processed = [], []
        for cid, path, x in voice_clips:
            cr = {"clip": cid, "source": rel(path)}
            cr["before"] = ffmpeg_ebur128(path)
            cr["before"]["I_lufs_internal_meter"] = round(lufs_integrated(x), 3)
            y = highpass(x)
            I_hp = ffmpeg_measure_array(y, tmp, f"clip{cid}_hpf")["precise"]["I_lufs"]
            cr["after_hpf_I_lufs"] = I_hp
            sib = sibilance_metrics(y, I_hp)
            cr["sibilance"] = sib
            if sib["harsh"]:
                y, st = deess(y, sib)
                cr["deess"] = {"applied": True, **st}
                I_hp = ffmpeg_measure_array(y, tmp, f"clip{cid}_deess")["precise"]["I_lufs"]
                cr["sibilance_after_deess"] = sibilance_metrics(y, I_hp)
                cr["after_deess_I_lufs"] = I_hp
            else:
                cr["deess"] = {"applied": False}
            gain_db = VOICE_CLIP_LUFS - I_hp
            y = y * 10 ** (gain_db / 20)
            y, nfade = edge_fades(y)
            cr["gain_db"] = round(gain_db, 3)
            cr["after"] = ffmpeg_measure_array(y, tmp, f"clip{cid}_final")
            cr["after"]["I_lufs_internal_meter"] = round(lufs_integrated(y), 3)
            clip_reports.append(cr)
            processed.append(y)
            print(f"clip{cid}: I {cr['before']['precise']['I_lufs']:.2f} -> {cr['after']['precise']['I_lufs']:.2f} LUFS "
                  f"(gain {gain_db:+.2f} dB), de-ess {'YES' if sib['harsh'] else 'no'} "
                  f"[ltas {sib['ltas_ratio_db']}, svr {sib['svr_p99_db']}, burst {sib['burst_rel_i_db']}]")

        voice_pre = np.concatenate(processed + [np.zeros((end_n, 2))])
        assert len(voice_pre) == total_n, (len(voice_pre), total_n)
        voice_pre_lufs = lufs_integrated(voice_pre)
        report["voice_processing"] = {
            "hpf": {"type": "Butterworth high-pass", "fc_hz": HPF_HZ, "order": HPF_ORDER,
                    "slope_db_per_oct": 6 * HPF_ORDER,
                    "implementation": "causal (minimum-phase) scipy sosfilt per clip, steady-state initial conditions"},
            "clip_loudness_target_lufs": VOICE_CLIP_LUFS,
            "join_fades": {"ms": JOIN_FADE_MS, "samples": nfade, "shape": "raised cosine",
                           "where": "fade-in at the first and fade-out at the last 5 ms of every clip; "
                                    "samples stay in place (no timing shift, no overlap)",
                           "cut_points_samples": [int(v) for v in clip_start_n]},
            "clips": clip_reports,
            "concatenated_pre_master_I_lufs_internal": round(voice_pre_lufs, 3),
        }
        report["deess"] = {
            "method": "10 ms frames of the mono mid signal; speech-active frames = within 30 dB of the clip's "
                      "95th-percentile frame level; bands = 4th-order Butterworth 5–10 kHz (sibilance) and "
                      "1–4 kHz (presence), zero-phase",
            "indicators": {
                "ltas_ratio_db": "long-term energy 5–10 kHz / 1–4 kHz (speech-active frames)",
                "svr_p99_db": "99th-pct 5–10 kHz frame level minus 95th-pct broadband frame level (esses vs loud vowels)",
                "burst_rel_i_db": "loudest 10 ms 5–10 kHz burst minus the clip's integrated loudness"},
            "limits": DEESS_LIMITS, "rule": f"de-ess a clip if >= {DEESS_MIN_FLAGS} of the 3 indicators exceed their limit",
            "settings_if_applied": {"split_hz": DEESS_SPLIT_HZ, "threshold": f"loud-vowel p95 level {DEESS_TARGET_SVR_DB:+} dB",
                                    "ratio": DEESS_RATIO, "max_gain_reduction_db": DEESS_MAX_GR_DB},
            "decision": {f"clip{c['clip']}": ("DE-ESSED" if c["deess"]["applied"] else "untouched")
                         for c in clip_reports},
        }

        # ── 3. voice master ───────────────────────────────────────────────────────────────────
        aac = not args.skip_aac_check
        report["mastering"] = {"target_lufs": MASTER_LUFS, "target_true_peak_dbtp": MASTER_TP_TARGET,
                               "limiter": {"type": "look-ahead true-peak limiter, 4x oversampled detection, "
                                                   "stereo-linked", "lookahead_attack_ms": LIMITER_LOOKAHEAD_MS,
                                           "release_ms": LIMITER_RELEASE_MS},
                               "loudnorm_linear_check": loudnorm_linear_check(voice_pre, tmp)}
        voice_master, vst, vlog = master_verified(voice_pre, "voice", tmp, aac)
        vpath = os.path.join(out_dir, "voice_master.wav")
        write_wav24(vpath, voice_master)

        # ── 4. music + SFX (optional) ─────────────────────────────────────────────────────────
        mix = voice_pre.copy()
        if os.path.isfile(args.music):
            caps = json.load(open(os.path.join(WORK, "captions.json"), encoding="utf-8"))
            speech = speech_intervals(caps, {c["clip"]: clip_start_n[i] / FS for i, c in enumerate(clips)})
            bed, minfo = build_music(args.music, total_n, voice_pre_lufs, speech, clip_start_n[-1] / FS)
            minfo["speech_intervals_s"] = [[round(a, 3), round(b, 3)] for a, b in speech]
            mix += bed
        else:
            minfo = {"status": "absent — skipped", "path": rel(args.music),
                     "would_apply": {"fader_db": {"bed": MUSIC_BED_DB, "ducked": MUSIC_DUCK_DB, "end_screen": MUSIC_END_DB},
                                     "reference": "music normalised to the speech loudness (0 LU) before the fader",
                                     "duck_attack_s": DUCK_ATTACK_S, "duck_release_s": DUCK_RELEASE_S,
                                     "end_rise_from_s": round(clip_start_n[-1] / FS, 4),
                                     "fade_out_s": MUSIC_FADE_OUT_S}}
        report["music"] = minfo

        sfx_files = find_sfx(args.sfx_dir)
        cues = list(DEFAULT_SFX_CUES)
        cue_src = "built-in join/slab whooshes"
        if os.path.isfile(args.cues):
            extra = json.load(open(args.cues, encoding="utf-8"))
            cues += [c for c in extra if c not in cues]
            cue_src += f" + {rel(args.cues)}"
        if sfx_files:
            sfx_track, sfx_levels, placed = build_sfx(sfx_files, cues, total_n, voice_pre_lufs)
            mix += sfx_track
            report["sfx"] = {"status": "used: " + ", ".join(sorted(sfx_files)), "cue_source": cue_src,
                             "missing": [s for s in SFX_NAMES if s not in sfx_files],
                             "level_rule": f"loudest 100 ms window = voice LUFS - {SFX_BELOW_VOICE_DB} dB",
                             "files": sfx_levels, "cues": placed}
        else:
            report["sfx"] = {"status": "absent — skipped", "dir": rel(args.sfx_dir), "cue_source": cue_src,
                             "cues_that_would_play": cues,
                             "level_rule": f"loudest 100 ms window = voice LUFS - {SFX_BELOW_VOICE_DB} dB (spec >= 10)"}

        # ── 5. music master ───────────────────────────────────────────────────────────────────
        mpath = os.path.join(out_dir, "music_master.wav")
        if not sfx_files and not os.path.isfile(args.music):
            music_master, mst, mlog = voice_master, vst, [{"note": "no music/SFX: identical to voice master"}]
            m_note = "No music and no SFX present -> music_master.wav is the voice master (bit-identical)."
        else:
            music_master, mst, mlog = master_verified(mix, "music", tmp, aac)
            m_note = "voice + music/SFX, mastered with the same chain"
        write_wav24(mpath, music_master)

        # ── 6. measure the written files (the numbers that matter) ────────────────────────────
        outs = {}
        for key, path, st, log, note in (("voice_master", vpath, vst, vlog, "voice only (nomusic track)"),
                                         ("music_master", mpath, mst, mlog, m_note)):
            meas = ffmpeg_ebur128(path)
            info = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_name,sample_rate,channels,bits_per_sample,duration_ts,duration",
                                   "-of", "json", path], capture_output=True, text=True, check=True)
            outs[key] = {"path": rel(path), "note": note, "sha256": sha256(path),
                         "stream": json.loads(info.stdout)["streams"][0],
                         "measured": meas,
                         "internal_true_peak_dbtp_4x": round(true_peak_dbtp(read_audio(path)), 3),
                         "limiter": st, "mastering_attempts": log}
        outs["music_master"]["identical_to_voice_master"] = outs["music_master"]["sha256"] == outs["voice_master"]["sha256"]
        report["outputs"] = outs

    rpath = os.path.join(out_dir, "audio_report.json")
    with open(rpath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    for key in ("voice_master", "music_master"):
        m = outs[key]["measured"]
        print(f"{key}: I {m['I_lufs']} LUFS  LRA {m['LRA_lu']} LU  TP {m['true_peak_dbtp']} dBTP  "
              f"(precise I {m['precise']['I_lufs']}, TP {m['precise']['true_peak_dbtp']})  -> {outs[key]['path']}")
    print(f"music: {report['music']['status']} | sfx: {report['sfx']['status']} | report -> {rel(rpath)}")


if __name__ == "__main__":
    main()
