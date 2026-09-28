#!/usr/bin/env python3
"""QA (Agent 13) — check 5: caption sync.
 (a) First VISIBLE frame of every caption chunk, detected on the captions-only renders (work/qa/iso/CapN,
     alpha > 32), vs the chunk's first word start frame from captions.json (tolerance ±2 frames).
     Also lists blank caption frames inside continuous speech (swap gaps).
 (b) Spot-check word start frames vs acoustic onsets in work/norm/clipN.wav (trimmed clip audio) for words
     that follow a pause (clear onsets).
Output: work/qa/parts/captions.json
"""
import json
import os

import numpy as np
from PIL import Image

QA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(QA))
D = json.load(open(os.path.join(QA, "cues_dump.json")))
CF = {int(k): v for k, v in D["CLIP_FRAMES"].items()}
CS = {int(k): v for k, v in D["CLIP_START"].items()}


def mask(c, lf):
    a = np.array(Image.open(os.path.join(QA, "iso", f"Cap{c}", f"f{lf:03d}.png")))[..., 3]
    return a > 32


def colprof(m):
    return m.any(0)


def jacc(a, b):
    u = (a | b).sum()
    return 1.0 if u == 0 else float((a & b).sum() / u)


def score(m, ref):
    """best 2-D mask IoU against a chunk's settled mask, allowing the 0-24 px entrance slide (and pop)."""
    best = 0.0
    for dy in range(0, 31, 2):
        sh = np.zeros_like(m)
        sh[: m.shape[0] - dy] = m[dy:]  # move the candidate UP by dy (entrance starts 24 px low)
        best = max(best, jacc(sh, ref))
    return best


def is_chunk(m, ref, others):
    """the frame shows this chunk (not a neighbour): non-empty and closer to its settled mask than to the neighbours'."""
    if not m.any():
        return False
    s = score(m, ref)
    return s >= 0.3 and all(s > score(m, o) for o in others)


out = {"chunks": [], "blank_frames_during_speech": {}, "audio_spot_checks": []}
for c in (1, 2, 3):
    masks = [mask(c, lf) for lf in range(CF[c])]
    present = [m.any() for m in masks]
    chunks = D["chunks"][str(c)]
    for i, ch in enumerate(chunks):
        settled = min(ch["appear"] + 8, ch["hideEnd"] - 1)
        ref = masks[settled]
        nb = [masks[min(x["appear"] + 8, x["hideEnd"] - 1)] for j, x in enumerate(chunks) if abs(j - i) == 1]
        fv = None
        for lf in range(max(0, ch["appear"] - 4), ch["hideEnd"]):
            if present[lf] and is_chunk(masks[lf], ref, nb):
                fv = lf
                break
        # last visible frame of this chunk
        lv = None
        for lf in range(settled, min(CF[c], ch["hideEnd"] + 4)):
            if present[lf] and is_chunk(masks[lf], ref, nb):
                lv = lf
        out["chunks"].append({
            "clip": c, "chunk": ch["index"], "text": " ".join(w["text"] for w in ch["words"]),
            "first_word_start": ch["firstStart"], "code_appear": ch["appear"], "first_visible_rendered": fv,
            "offset_frames": None if fv is None else fv - ch["firstStart"],
            "in_sync_pm2": fv is not None and abs(fv - ch["firstStart"]) <= 2,
            "last_word_end": ch["lastEnd"], "last_visible_rendered": lv, "exit": ch["exit"],
        })
    # blank frames while speech continues (between first word and last word of the clip)
    first = chunks[0]["firstStart"]
    last = chunks[-1]["lastEnd"]
    blanks = [lf for lf in range(first, min(CF[c], last)) if not present[lf]]
    # classify: planned fade gaps (chunk exit == fade) vs 1-frame swap gaps
    fade_gaps = set()
    for ch in chunks:
        if ch["exit"] == "fade":
            nxt = next(x for x in chunks if x["appear"] > ch["appear"])
            fade_gaps |= set(range(ch["hideEnd"], nxt["appear"] + 1))
    out["blank_frames_during_speech"][c] = {
        "planned_pause_gaps": [lf for lf in blanks if lf in fade_gaps],
        "unplanned_blank_frames_local": [lf for lf in blanks if lf not in fade_gaps],
        "unplanned_blank_frames_global": [CS[c] + lf for lf in blanks if lf not in fade_gaps],
    }


# ── (b) acoustic onsets ──
def load_wav(p):
    """mono float32 via ffmpeg (the masters are WAVE_FORMAT_EXTENSIBLE 24-bit)."""
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64), 48000


caps = json.load(open(os.path.join(ROOT, "work", "captions.json")))
SPOT = {1: ["रोज़", "बदले", "Zero!", "वही"], 2: ["voice", "photos", "text", "सब", "कोई", "training"], 3: ["पैसा", "तो", "और"]}
for c, words in SPOT.items():
    x, fs = load_wav(os.path.join(ROOT, "work", "norm", f"clip{c}.wav"))
    hop = int(0.005 * fs)
    win = int(0.010 * fs)
    nfr = (len(x) - win) // hop
    env = np.array([np.sqrt(np.mean(x[i * hop:i * hop + win] ** 2)) + 1e-9 for i in range(nfr)])
    db = 20 * np.log10(env)
    cw = [w for w in caps if w["clip"] == c]
    for word in words:
        occ = [i for i, w in enumerate(cw) if w["word"] == word]
        i = occ[-1] if word == "तो" else occ[0]  # 2nd "तो" in clip 3 follows the pause
        w = cw[i]
        prev_end = cw[i - 1]["end"] if i > 0 else 0.0
        a = int(max(0, min(prev_end, w["start"]) - 0.05) / 0.005)
        b = int((w["start"] + 0.25) / 0.005)
        seg = db[a:b]
        floor_i = a + int(np.argmin(db[a:int(w["start"] / 0.005) + 6]))
        floor = db[floor_i]
        peak = db[int(w["start"] / 0.005):int(w["end"] / 0.005) + 1].max()
        thr = floor + 0.25 * (peak - floor)
        # onset = first crossing after which the level stays above thr for >= 120 ms (rejects clicks / lip smacks)
        on = next((k for k in range(floor_i, b) if (db[k:k + 24] >= thr).all()), None)
        t_on = on * 0.005 + 0.005 if on is not None else None
        sf = round(w["start"] * 30)
        out["audio_spot_checks"].append({
            "clip": c, "word": word, "caption_start_s": w["start"], "caption_start_frame": sf,
            "onset_s": None if t_on is None else round(t_on, 3), "onset_frame": None if t_on is None else round(t_on * 30, 1),
            "diff_frames": None if t_on is None else round(sf - t_on * 30, 1),
            "gap_floor_db": round(float(floor), 1), "word_peak_db": round(float(peak), 1),
        })

ok = sum(1 for r in out["chunks"] if r["in_sync_pm2"])
out["summary"] = {
    "chunks": len(out["chunks"]), "in_sync_pm2": ok,
    "offsets_frames": sorted(set(r["offset_frames"] for r in out["chunks"])),
    "audio_max_abs_diff_frames": max(abs(r["diff_frames"]) for r in out["audio_spot_checks"] if r["diff_frames"] is not None),
}
json.dump(out, open(os.path.join(QA, "parts", "captions.json"), "w"), ensure_ascii=False, indent=1)
for r in out["chunks"]:
    print(r["clip"], r["chunk"], r["first_word_start"], r["code_appear"], r["first_visible_rendered"], r["offset_frames"], r["last_visible_rendered"], r["exit"], r["text"])
print(json.dumps(out["blank_frames_during_speech"], indent=1))
for r in out["audio_spot_checks"]:
    print(r)
print(out["summary"])
