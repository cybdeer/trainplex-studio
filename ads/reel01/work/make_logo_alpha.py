"""Create a transparent TrainPlex logo from the white-background source PNG.

Rules: never redraw/recolour/stretch the logo. Only the pure-white background (the region
connected to the image border, plus small enclosed letter counters) is made transparent.
Large enclosed white areas (the icon's own white fill) are kept opaque. Anti-aliased edge
pixels get a fractional alpha solved against white, and keep the colour of the nearest
solid logo pixel so the brand colours are not shifted.
"""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
import os, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = Image.open(os.path.join(root, "logo", "trainplex_logo_source.png")).convert("RGB")
SCALE = 4
big = src.resize((src.width * SCALE, src.height * SCALE), Image.LANCZOS)
C = np.asarray(big).astype(np.float64)
W = np.array([255.0, 255.0, 255.0])
d = (255.0 - C).max(axis=2)               # distance from white (max channel)

bg_white = d <= 8                          # near-pure white
lab, n = ndi.label(bg_white)
border_labels = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
sizes = ndi.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
transparent = np.zeros_like(bg_white)
small_limit = 0.004 * lab.size             # letter counters are tiny; icon interior is big
kept_regions = []
for i in range(1, n + 1):
    if i in border_labels or sizes[i - 1] < small_limit:
        transparent |= lab == i
    else:
        kept_regions.append(int(sizes[i - 1]))
print("white regions:", n, "kept opaque (large enclosed):", kept_regions)

# "core" = locally most-saturated pixels (solid logo colour); robust for thin strokes
dmax = ndi.maximum_filter(d, size=5 * SCALE // 2 + 1)
core = (d >= 0.93 * dmax) & (d > 40)
# nearest core colour for every pixel
_, (iy, ix) = ndi.distance_transform_edt(~core, return_indices=True)
F = C[iy, ix]
# alpha solved against white: C = a*F + (1-a)*W
num = ((W - C) * (W - F)).sum(axis=2)
den = ((W - F) ** 2).sum(axis=2) + 1e-6
alpha = np.clip(num / den, 0.0, 1.0)
alpha[core] = 1.0
alpha[transparent] = 0.0
# keep opaque any non-background pixel that is not an edge next to a transparent region
edge_zone = ndi.binary_dilation(transparent, iterations=3 * SCALE // 2)
alpha[~edge_zone & ~transparent] = 1.0
rgb = np.where(core[..., None] | ~edge_zone[..., None], C, F)

out = np.dstack([rgb, alpha * 255.0]).round().clip(0, 255).astype(np.uint8)
im = Image.fromarray(out, "RGBA")
bbox = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
pad = 6 * SCALE
bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad))
im = im.crop(bbox)
os.makedirs(os.path.join(root, "remotion", "public"), exist_ok=True)
im.save(os.path.join(root, "logo", "trainplex_logo_transparent.png"))
im.save(os.path.join(root, "remotion", "public", "trainplex_logo_transparent.png"))
print("saved", im.size, "crop bbox (x4 space)", bbox)
# preview on navy / cream / checker for QA
for name, bgc in (("navy", (26, 26, 94)), ("cream", (250, 247, 242))):
    bgim = Image.new("RGBA", im.size, bgc + (255,))
    bgim.alpha_composite(im)
    bgim.convert("RGB").save(os.path.join(root, "work", f"logo_preview_on_{name}.png"))
