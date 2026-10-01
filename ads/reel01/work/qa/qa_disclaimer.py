#!/usr/bin/env python3
"""QA (Agent 13) — check 6: disclaimer visible + legible whenever the ₹ figure is on screen (clip 3).
Per clip-3 frame (graphics render): figure present? (orange text pixels inside the plate), disclaimer strip
visible width + text present. Legibility: glyph heights from the render; contrast of the white text against the
real strip background measured on the DELIVERED MP4 frames (navy 70 % over video).
Output: work/qa/parts/disclaimer.json
"""
import json
import os
import subprocess

import numpy as np
from PIL import Image

QA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(QA))
D = json.load(open(os.path.join(QA, "cues_dump.json")))
C3 = D["clip3"]
S3 = D["CLIP_START"]["3"]
ORANGE = np.array([255, 107, 53])
NAVY = np.array([26, 26, 94])
Y1, Y2 = C3["DISC_STRIP"]["y1"], C3["DISC_STRIP"]["y2"]
P = C3["PLATE"]


def lum(rgb):
    c = np.asarray(rgb, float) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return c @ [0.2126, 0.7152, 0.0722]


def contrast(l1, l2):
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# decode the delivered clip-3 frames once (raw RGB)
W, H = 1080, 1920
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(ROOT, "output", "TrainPlex_Reel01_9x16.mp4"),
                      "-vf", f"select=between(n\\,{S3}\\,{S3 + 234})", "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                     capture_output=True, check=True).stdout
vid = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

rows = []
for lf in range(0, 235):
    g = S3 + lf
    a = np.array(Image.open(os.path.join(QA, "g", f"f{g:03d}.png")).convert("RGBA")).astype(int)
    rgb, al = a[..., :3], a[..., 3]
    plate = rgb[P["y1"]:P["y2"], 0:1080]
    pa = al[P["y1"]:P["y2"], 0:1080]
    navy_px = int(((np.abs(plate - NAVY).max(2) <= 6) & (pa > 250)).sum())
    # figure = orange glyph pixels on the navy plate (the BANK/UPI card that follows is white, not navy)
    fig_px = int(((np.abs(plate - ORANGE).max(2) <= 60) & (pa > 60)).sum()) - int(P["y2"] - P["y1"]) * 12 if navy_px > 40000 else 0
    strip_a = al[Y1:Y2]
    strip_cols = (strip_a > 100).any(0)
    strip_w = int(strip_cols.sum())
    text = (strip_a == 255) & (rgb[Y1:Y2].min(2) > 200)  # opaque white text pixels
    rows.append({"local": lf, "g": g, "figure_px": max(0, fig_px), "strip_width": strip_w, "text_px": int(text.sum())})

WIPE_L = D["END_SCREEN_START"] - 4 - S3  # clip-3 frames under the orange wipe are excluded
FLASH_L = 3  # clip-3 local 0-2 are under the white join flash
rows = [r for r in rows if FLASH_L <= r["local"] < WIPE_L]
from collections import Counter
full_w = Counter(r["strip_width"] for r in rows if r["strip_width"] > 200).most_common(1)[0][0]
full_t = Counter(r["text_px"] for r in rows if r["text_px"] > 0).most_common(1)[0][0]
fig_frames = [r["local"] for r in rows if r["figure_px"] > 300]
disc_full = [r["local"] for r in rows if r["strip_width"] >= full_w - 2 and r["text_px"] >= 0.97 * full_t]
disc_any = [r["local"] for r in rows if r["strip_width"] > 200]  # (>200: ignore the LEARN MORE arrow tip in these rows)
bad = [f for f in fig_frames if f not in disc_full]
after = [f for f in disc_full if fig_frames and f > max(fig_frames)]

# glyph metrics on a fully visible frame
ref = next(r for r in rows if r["local"] == 90)
a = np.array(Image.open(os.path.join(QA, "g", f"f{ref['g']:03d}.png")).convert("RGBA")).astype(int)
text = (a[Y1:Y2, :, 3] == 255) & (a[Y1:Y2, :, :3].min(2) > 200)
ys, xs = np.nonzero(text)
text_box = [int(xs.min()), int(ys.min()) + Y1, int(xs.max()) + 1, int(ys.max()) + 1 + Y1]
strip_cols = np.nonzero((a[Y1:Y2, :, 3] > 100).any(0))[0]
# Latin x-height: rows covered by the word "task" region ~ use column band of Latin run (approx. 2nd quarter)
col_prof = text.any(0)
# per-row coverage to find the dense band (x-height / Devanagari body between headline and baseline)
row_cov = text.sum(1)

# contrast on the delivered video: strip background = strip pixels that are not text (dilated)
from scipy.ndimage import binary_dilation
cons = []
for lf in sorted(set(disc_full)):
    g = S3 + lf
    ga = np.array(Image.open(os.path.join(QA, "g", f"f{g:03d}.png")).convert("RGBA")).astype(int)
    st = (ga[Y1:Y2, :, 3] > 100)
    tx = binary_dilation((ga[Y1:Y2, :, 3] == 255) & (ga[Y1:Y2, :, :3].min(2) > 200), iterations=3)
    bgm = st & ~tx
    v = vid[lf, Y1:Y2][bgm].astype(float)
    L = lum(v)
    tv = vid[lf, Y1:Y2][(ga[Y1:Y2, :, 3] == 255) & (ga[Y1:Y2, :, :3].min(2) > 240)].astype(float)
    Lt = float(np.median(lum(tv))) if len(tv) else 1.0
    cons.append({"local": lf, "bg_mean_rgb": v.mean(0).round(1).tolist(), "text_median_lum": round(Lt, 3),
                 "contrast_mean_bg": round(contrast(Lt, float(L.mean())), 2),
                 "contrast_p95_brightest_bg": round(contrast(Lt, float(np.percentile(L, 95))), 2)})

out = {
    "cues_local": {k: C3[k] for k in ("PLATE_IN", "FIGURE_ON", "PLATE_OUT", "PLATE_GONE", "DISC_IN", "DISC_OUT", "DISC_GONE")},
    "figure_visible_frames_local": [min(fig_frames), max(fig_frames)] if fig_frames else None,
    "figure_visible_count": len(fig_frames),
    "disclaimer_fully_visible_local": [min(disc_full), max(disc_full)],
    "disclaimer_any_visible_local": [min(disc_any), max(disc_any)],
    "figure_frames_without_full_disclaimer": bad,
    "disclaimer_hold_after_figure_frames": len(after),
    "disclaimer_hold_after_figure_s": round(len(after) / 30, 2),
    "strip_x": [int(strip_cols.min()), int(strip_cols.max()) + 1], "strip_y": [Y1, Y2],
    "text_box": text_box, "text_block_height_px": text_box[3] - text_box[1],
    "font": "Inter / Noto Sans Devanagari 600, 30 px, white on rgba(26,26,94,0.7)",
    "contrast_min_mean_bg": min(c["contrast_mean_bg"] for c in cons),
    "contrast_min_p95_bg": min(c["contrast_p95_brightest_bg"] for c in cons),
    "contrast_samples": cons[::10],
    "rows": rows,
}
json.dump(out, open(os.path.join(QA, "parts", "disclaimer.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ("rows",)}, indent=1))
