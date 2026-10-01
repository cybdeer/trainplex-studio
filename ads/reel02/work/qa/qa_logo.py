#!/usr/bin/env python3
"""QA (Agent 13) — check 7: logo unaltered.
 (a) logo/trainplex_logo_transparent.png vs logo/trainplex_logo_source.png: composite the transparent PNG over
     white, locate it in the 4x-upscaled source (the generator's working space), bring it back to source scale
     and diff it against the source.
 (b) rendered logos (end screen, clip-1 plate, watermark) vs the transparent PNG resampled to the same
     geometry and composited over the same cream: MAD / max diff / SSIM + ink-box aspect ratio.
Output: work/qa/parts/logo.json, work/qa/view/logo_compare.png
"""
import json
import os

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

QA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(QA))
D = json.load(open(os.path.join(QA, "cues_dump.json")))
CREAM = np.array([250, 247, 242], float)
LOGO = np.array(Image.open(os.path.join(ROOT, "logo", "trainplex_logo_transparent.png")).convert("RGBA")).astype(float)
SRC = np.array(Image.open(os.path.join(ROOT, "logo", "trainplex_logo_source.png")).convert("RGB")).astype(float)
PUB = os.path.join(ROOT, "remotion", "public", "trainplex_logo_transparent.png")


def over(rgba, bg):
    a = rgba[..., 3:4] / 255.0
    return rgba[..., :3] * a + bg * (1 - a)


def ssim(x, y):
    x, y = x.astype(float), y.astype(float)
    if x.ndim == 3:
        x = x @ [0.299, 0.587, 0.114]
        y = y @ [0.299, 0.587, 0.114]
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mx, my = gaussian_filter(x, 1.5), gaussian_filter(y, 1.5)
    sxx = gaussian_filter(x * x, 1.5) - mx * mx
    syy = gaussian_filter(y * y, 1.5) - my * my
    sxy = gaussian_filter(x * y, 1.5) - mx * my
    m = ((2 * mx * my + C1) * (2 * sxy + C2)) / ((mx * mx + my * my + C1) * (sxx + syy + C2))
    return float(m.mean())


def ink_box(rgb, bg, thr=40):
    d = np.abs(rgb - bg).max(2) > thr
    ys, xs = np.nonzero(d)
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def reference(width, left, top, bg, canvas_hw):
    """Transparent PNG composited over bg at full res, resampled to `width` and placed at (left, top) sub-pixel."""
    full = over(LOGO, bg)
    h = width * LOGO.shape[0] / LOGO.shape[1]
    s = width / LOGO.shape[1]
    # area-average downscale then sub-pixel translate (bilinear)
    small = cv2.resize(full, (int(round(width)), int(round(h))), interpolation=cv2.INTER_AREA)
    sx, sy = width / small.shape[1], h / small.shape[0]
    M = np.float32([[sx, 0, left], [0, sy, top]])
    canvas = cv2.warpAffine(small, M, (canvas_hw[1], canvas_hw[0]), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=bg.tolist())
    return canvas, s


out = {}
# ── (a) transparent PNG vs source ──
out["files"] = {
    "source": {"size": list(SRC.shape[1::-1])},
    "transparent": {"size": list(LOGO.shape[1::-1]),
                    "identical_to_remotion_public_copy": open(PUB, "rb").read() == open(os.path.join(ROOT, "logo", "trainplex_logo_transparent.png"), "rb").read()},
}
big = np.array(Image.fromarray(SRC.astype(np.uint8)).resize((1200, 1200), Image.LANCZOS)).astype(np.float32)
comp = over(LOGO, np.array([255.0, 255, 255])).astype(np.float32)
res = cv2.matchTemplate(big, comp, cv2.TM_SQDIFF)
_, _, (x0, y0), _ = cv2.minMaxLoc(res)
canvas = np.full((1200, 1200, 3), 255.0, np.float32)
canvas[y0:y0 + comp.shape[0], x0:x0 + comp.shape[1]] = comp
d4 = np.abs(canvas - big)
back = cv2.resize(canvas, (300, 300), interpolation=cv2.INTER_AREA)
d1 = np.abs(back - SRC)
out["transparent_vs_source"] = {
    "offset_in_4x_space": [int(x0), int(y0)],
    "at_4x": {"mad": round(float(d4.mean()), 3), "p99": round(float(np.percentile(d4, 99)), 2), "max": round(float(d4.max()), 1),
              "ssim": round(ssim(canvas, big), 5)},
    "at_source_scale_300px": {"mad": round(float(d1.mean()), 3), "p99": round(float(np.percentile(d1, 99)), 2),
                              "max": round(float(d1.max()), 1), "ssim": round(ssim(back, SRC), 5)},
    "ink_aspect_source": None, "ink_aspect_transparent": None,
}
bs = ink_box(SRC, np.array([255.0, 255, 255]))
bt = ink_box(comp, np.array([255.0, 255, 255]))
out["transparent_vs_source"]["ink_box_source"] = bs
out["transparent_vs_source"]["ink_box_transparent"] = bt
out["transparent_vs_source"]["ink_aspect_source"] = round((bs[2] - bs[0]) / (bs[3] - bs[1]), 4)
out["transparent_vs_source"]["ink_aspect_transparent"] = round((bt[2] - bt[0]) / (bt[3] - bt[1]), 4)
# solid colours of the artwork
px = LOGO[LOGO[..., 3] == 255][:, :3].astype(int)
keys, cnt = np.unique(px[:, 0] * 65536 + px[:, 1] * 256 + px[:, 2], return_counts=True)
top = sorted(zip(cnt.tolist(), keys.tolist()), reverse=True)[:4]
out["logo_artwork_main_colours"] = ["#%06X (%d px)" % (k, c) for c, k in top]

# ── (b) rendered logos ──
cases = []
# end screen, settled (scale spring ~1 at local 104), foreground-only render (transparent bg) and full render (cream)
es = D["endscreen"]
cases.append(("endscreen_fg_lf104", os.path.join(QA, "iso", "EndScreenFG", "f104.png"), es["LOGO_W"], es["CX"] - es["LOGO_W"] / 2, es["LOGO_TOP"], "transparent"))
cases.append(("endscreen_full_g845", os.path.join(QA, "g", "f845.png"), es["LOGO_W"], es["CX"] - es["LOGO_W"] / 2, es["LOGO_TOP"], "opaque"))
c1 = D["clip1"]
cases.append(("clip1_plate_g220", os.path.join(QA, "g", "f220.png"), c1["LOGO_WIDTH"], 540 - c1["LOGO_WIDTH"] / 2, c1["LOGO"]["top"] + c1["LOGO"]["padY"], "opaque"))
cases.append(("watermark_g135", os.path.join(QA, "g", "f135.png"), 200, 68, 248, "unpremult"))
cases.append(("watermark_g640", os.path.join(QA, "g", "f640.png"), 200, 68, 248, "unpremult"))
tiles = []
out["rendered"] = {}
for name, path, width, left, top, mode in cases:
    a = np.array(Image.open(path).convert("RGBA")).astype(float)
    if mode == "transparent":
        rgb = over(a, CREAM)  # composite the isolated logo over cream exactly like the end screen
    else:
        rgb = a[..., :3]  # opaque, or unpremultiplied RGB inside the 85 % watermark plate (logo over cream)
    ref, s = reference(width, left, top, CREAM, rgb.shape[:2])
    h = width * LOGO.shape[0] / LOGO.shape[1]
    x1, y1, x2, y2 = int(np.floor(left)), int(np.floor(top)), int(np.ceil(left + width)), int(np.ceil(top + h))
    R, F = rgb[y1:y2, x1:x2], ref[y1:y2, x1:x2]
    d = np.abs(R - F)
    bi, bf = ink_box(R, CREAM), ink_box(F, CREAM)
    # best integer shift (checks for a positional offset rather than an alteration)
    best = min(((float(np.abs(rgb[y1 + dy:y2 + dy, x1 + dx:x2 + dx] - F).mean()), dx, dy) for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)))
    out["rendered"][name] = {
        "box": [x1, y1, x2, y2], "logo_width_px": round(width, 2), "scale_vs_png": round(s, 4),
        "effective_scale_vs_300px_source": round(width / (LOGO.shape[1] / 4), 3),
        "mad": round(float(d.mean()), 2), "p99": round(float(np.percentile(d, 99)), 1), "max": round(float(d.max()), 1),
        "ssim": round(ssim(R, F), 4), "best_shift_mad": [round(best[0], 2), best[1], best[2]],
        "alpha_in_plate": int(np.median(a[y1:y2, x1:x2, 3])),
        "ink_box_rendered": bi, "ink_box_reference": bf,
        "ink_aspect_rendered": round((bi[2] - bi[0]) / (bi[3] - bi[1]), 4),
        "ink_aspect_reference": round((bf[2] - bf[0]) / (bf[3] - bf[1]), 4),
    }
    t = np.hstack([R, F, np.clip(d * 4, 0, 255)]).astype(np.uint8)
    tiles.append(cv2.resize(t, (900, int(900 * t.shape[0] / t.shape[1]))))
sheet = np.vstack(tiles)
Image.fromarray(sheet).save(os.path.join(QA, "view", "logo_compare.png"))
json.dump(out, open(os.path.join(QA, "parts", "logo.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
