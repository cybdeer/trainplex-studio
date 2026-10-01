#!/usr/bin/env python3
"""QA (Agent 13) — check 1/2 (visual part): 1:1 crops of every caption chunk and every Devanagari graphic,
composited over a flat mid-grey (from the isolation / graphics renders) and from the delivered MP4.
Writes work/qa/crops/*.png and contact sheets work/qa/view/deva_sheet_*.png for visual inspection.
"""
import json
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw

QA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(QA))
D = json.load(open(os.path.join(QA, "cues_dump.json")))
CS = {int(k): v for k, v in D["CLIP_START"].items()}
BG = (92, 104, 92, 255)
os.makedirs(os.path.join(QA, "crops"), exist_ok=True)
os.makedirs(os.path.join(QA, "view"), exist_ok=True)


def over_grey(path):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, BG)
    bg.alpha_composite(im)
    return bg.convert("RGB"), np.array(im)[..., 3]


def video_frame(g):
    p = os.path.join(QA, "stills", f"video_f{g:03d}.png")
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(ROOT, "output", "TrainPlex_Reel02_9x16.mp4"),
                        "-vf", f"select=eq(n\\,{g})", "-vsync", "0", "-frames:v", "1", p], check=True)
    return Image.open(p).convert("RGB")


items = []  # (label, image)
# every caption chunk, settled (entrance done), captions-only render
for c in (1, 2, 3):
    for ch in D["chunks"][str(c)]:
        lf = min(ch["appear"] + 8, ch["hideEnd"] - 1)
        im, al = over_grey(os.path.join(QA, "iso", f"Cap{c}", f"f{lf:03d}.png"))
        ys, xs = np.nonzero(al > 16)
        box = (max(0, xs.min() - 12), max(0, ys.min() - 12), min(1080, xs.max() + 13), min(1920, ys.max() + 13))
        crop = im.crop(box)
        text = " ".join(w["text"] for w in ch["words"])
        crop.save(os.path.join(QA, "crops", f"cap{c}_{ch['index']}_lf{lf}.png"))
        items.append((f"clip{c} chunk{ch['index']} local {lf} (g{CS[c] + lf}): {text}", crop))

# Devanagari inside clip graphics (graphics-only render, grey background)
G = lambda g: os.path.join(QA, "g", f"f{g:03d}.png")
graphics = [
    ("clip1 slab 'SCROLL बंद कर!' g30", 30, (0, 240, 1080, 540)),
    ("clip2 badges 'PHONE से' g470", 470, (100, 930, 1000, 1200)),
    ("clip3 plate '₹500–600 / 4 घंटे में तक*' g596", 596, (130, 280, 950, 560)),
    ("clip3 disclaimer g596", 596, (150, 1405, 930, 1480)),
    ("end screen headline + sub g845", 845, (60, 740, 1020, 980)),
]
for label, g, box in graphics:
    im, _ = over_grey(G(g))
    crop = im.crop(box)
    crop.save(os.path.join(QA, "crops", f"gfx_g{g}_{box[1]}.png"))
    items.append((label, crop))

# same Devanagari graphics on the DELIVERED video (real background, after H.264)
for label, g, box in [("VIDEO g596 disclaimer (delivered MP4)", 596, (150, 1405, 930, 1480)),
                      ("VIDEO g210 caption 'TrainPlex पे दे।' (delivered MP4)", 210, (60, 1180, 1020, 1420)),
                      ("VIDEO g845 end screen (delivered MP4)", 845, (60, 740, 1020, 980))]:
    crop = video_frame(g).crop(box)
    crop.save(os.path.join(QA, "crops", f"video_g{g}_{box[1]}.png"))
    items.append((label, crop))

# contact sheets, 1:1 scale, max ~1000 px tall each
sheets, cur, h = [], [], 0
for it in items:
    ih = it[1].height + 26
    if cur and h + ih > 1100:
        sheets.append(cur)
        cur, h = [], 0
    cur.append(it)
    h += ih
sheets.append(cur)
for i, sh in enumerate(sheets):
    W = max(im.width for _, im in sh)
    H = sum(im.height + 26 for _, im in sh)
    s = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(s)
    y = 0
    for label, im in sh:
        d.text((4, y + 6), label, fill=(0, 0, 0))
        s.paste(im, (0, y + 26))
        y += im.height + 26
    s.save(os.path.join(QA, "view", f"deva_sheet_{i}.png"))
print(len(items), "crops,", len(sheets), "sheets")
