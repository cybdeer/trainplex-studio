#!/usr/bin/env python3
"""QA (Agent 13) — per-frame graphics analysis on the Reel01Graphics PNG sequence.

Inputs
  work/qa/g/fNNN.png            Reel01Graphics (whole reel, video hidden, RGBA; end screen is opaque RGB)
  work/qa/iso/EndScreenFG/      end screen with the full-bleed backgrounds removed (text/logo/chips/arrows)
  work/qa/cues_dump.json        timing / camera / face values evaluated from the real remotion/src code
Outputs
  work/qa/parts/safe_zone.json  (check 3)
  work/qa/parts/face.json       (check 4)
  work/qa/parts/colours.json    (check 8)
"""
import json
import os
from collections import defaultdict

import cv2
import numpy as np
from PIL import Image

QA = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(QA, "g")
ESFG = os.path.join(QA, "iso", "EndScreenFG")
PARTS = os.path.join(QA, "parts")
os.makedirs(PARTS, exist_ok=True)
cv2.setNumThreads(4)

D = json.load(open(os.path.join(QA, "cues_dump.json")))
CS = {int(k): v for k, v in D["CLIP_START"].items()}
CF = {int(k): v for k, v in D["CLIP_FRAMES"].items()}
ES0 = D["END_SCREEN_START"]  # 741
TOTAL = ES0 + 105

SAFE = dict(x1=60, x2=1020, y1=220, y2=1480)
BAR_ROWS = (220, 228)  # progress bar rows [220, 228)
FLASH = set(range(CS[2] - 1, CS[2] + 3)) | set(range(CS[3] - 1, CS[3] + 3))  # 228-231, 505-508
WIPE = set(range(ES0 - 4, ES0 + 4))  # 737-744
ALPHA_VIS = 32

PALETTE = {
    "cream #FAF7F2": (250, 247, 242),
    "navy #1A1A5E": (26, 26, 94),
    "orange #FF6B35": (255, 107, 53),
    "white #FFFFFF": (255, 255, 255),
    "border #E8E3DA": (232, 227, 218),
}
NAVY = np.array(PALETTE["navy #1A1A5E"], float)


def load(path):
    a = np.array(Image.open(path))
    if a.ndim == 3 and a.shape[2] == 3:
        a = np.dstack([a, np.full(a.shape[:2], 255, np.uint8)])
    return a


def clip_of(g):
    for c in (3, 2, 1):
        if g >= CS[c] and g < CS[c] + CF[c]:
            return c, g - CS[c]
    return None, g - ES0


def bbox(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]  # x1,y1,x2,y2 (exclusive)


def runs(frames):
    frames = sorted(frames)
    out = []
    for f in frames:
        if out and f == out[-1][1] + 1:
            out[-1][1] = f
        else:
            out.append([f, f])
    return out


# ─── face rects on screen (camera transform of the VIDEO layer) ────────────────────────────────
def to_screen(r, cam):
    s, ox, oy, dx, dy = cam["scale"], cam["originX"], cam["originY"], cam["dx"], cam["dy"]
    return dict(x1=ox + (r["x1"] - ox) * s + dx, y1=oy + (r["y1"] - oy) * s + dy,
                x2=ox + (r["x2"] - ox) * s + dx, y2=oy + (r["y2"] - oy) * s + dy)


def rect_clearance(dist, r):
    """min distance (px) from any graphic pixel to rect r, using distance-to-nearest-graphic map `dist`."""
    x1, y1 = max(0, int(np.floor(r["x1"]))), max(0, int(np.floor(r["y1"])))
    x2, y2 = min(1080, int(np.ceil(r["x2"]))), min(1920, int(np.ceil(r["y2"])))
    if x2 <= x1 or y2 <= y1:
        return None
    return float(dist[y1:y2, x1:x2].min())


def speaking(clip, lf):
    for c_chunks in D["chunks"][str(clip)]:
        for w in c_chunks["words"]:
            if w["startFrame"] <= lf < w["endFrame"]:
                return True
    return False


def main():
    safe = np.zeros((1920, 1080), bool)
    safe[SAFE["y1"]:SAFE["y2"], SAFE["x1"]:SAFE["x2"]] = True

    sz_frames = {}
    sz_viol = defaultdict(list)  # key -> frames
    slab_text = {}
    face_rows = []
    colour_count = defaultdict(int)
    colour_frames = defaultdict(set)
    colour_where = {}
    k3 = np.ones((3, 3), np.uint8)

    for g in range(TOTAL):
        a = load(os.path.join(G, f"f{g:03d}.png"))
        rgb, al = a[..., :3], a[..., 3]
        clip, lf = clip_of(g)

        # ── check 8: interior opaque colours (every frame) ──
        op = (al == 255).astype(np.uint8)
        interior = cv2.erode(op, k3).astype(bool)
        for ch in range(3):
            c = rgb[..., ch]
            interior &= (cv2.dilate(c, k3).astype(int) - cv2.erode(c, k3).astype(int)) <= 2
        excl = np.zeros_like(interior)
        excl[240:500, 56:282] = True  # watermark plate + logo (85 % opacity anyway)
        if clip == 1 and lf >= D["clip1"]["LOGO"]["inAt"]:
            lw = D["clip1"]["LOGO_WIDTH"]
            excl[232:232 + 14 + int(np.ceil(D["clip1"]["LOGO_HEIGHT"])) + 16, int(540 - lw / 2) - 30:int(540 + lw / 2) + 30] = True
        if clip is None:  # end screen logo (scale pop about its centre)
            excl[226:714, 316:764] = True
        sel = interior & ~excl
        if sel.any():
            px = rgb[sel].astype(np.int64)
            keys = (px[:, 0] << 16) | (px[:, 1] << 8) | px[:, 2]
            u, cnt = np.unique(keys, return_counts=True)
            ys, xs = np.nonzero(sel)
            for kk, n in zip(u.tolist(), cnt.tolist()):
                colour_count[kk] += n
                colour_frames[kk].add(g)
                if kk not in colour_where and n >= 20:
                    m = keys == kk
                    colour_where[kk] = [int(xs[m].min()), int(ys[m].min()), int(xs[m].max()) + 1, int(ys[m].max()) + 1, g]

        # ── check 3: safe zone ──
        if clip is not None:
            if g in FLASH or g in WIPE:
                continue
            vis = al > ALPHA_VIS
            vis[BAR_ROWS[0]:BAR_ROWS[1]] = False
            bb = bbox(vis)
            out = vis & ~safe
            gap = vis[228:232].any()  # between the bar and the 232 graphics line
            rec = {"clip": clip, "local": lf, "bbox": bb, "outside_px": int(out.sum()), "rows_228_231": bool(gap)}
            if out.any():
                n, lab, stats, _ = cv2.connectedComponentsWithStats(vis.astype(np.uint8), connectivity=8)
                comps = []
                for i in range(1, n):
                    x, y, w, h, area = stats[i]
                    cm = lab == i
                    o = int((cm & out).sum())
                    if o:
                        mc = rgb[cm].mean(0).round().astype(int).tolist()
                        comps.append({"bbox": [int(x), int(y), int(x + w), int(y + h)], "area": int(area), "outside_px": o, "mean_rgb": mc})
                rec["components_outside"] = comps
                side = []
                obb = bbox(out)
                if obb[0] < SAFE["x1"]: side.append("left")
                if obb[2] > SAFE["x2"]: side.append("right")
                if obb[1] < SAFE["y1"]: side.append("top")
                if obb[3] > SAFE["y2"]: side.append("bottom")
                rec["outside_bbox"] = obb
                rec["sides"] = side
                sz_viol[f"clip{clip}:" + "+".join(side)].append(g)
            sz_frames[g] = rec
            # clip-1 slab: text/icon (non-navy) extents inside the full-bleed band
            if clip == 1 and lf < D["clip1"]["SLAB_OUT_END"]:
                band = np.zeros_like(vis)
                band[240:540] = True
                far = np.linalg.norm(rgb.astype(float) - NAVY, axis=2) > 90
                tm = band & (al > 200) & far
                slab_text[g] = bbox(tm)

            # ── check 4: eyes / mouth vs graphics ──
            fr = D["faces"][str(clip)][lf]
            eyes, mouth = to_screen(fr["eyes"], fr["cam"]), to_screen(fr["mouth"], fr["cam"])
            if clip == 1 and fr["cam"]["dx"] != 0:
                pass
            gm = al > ALPHA_VIS  # includes the progress bar (never near the face)
            inv = (~gm).astype(np.uint8)
            dist = cv2.distanceTransform(inv, cv2.DIST_L2, 5) if gm.any() else np.full(gm.shape, 9999, np.float32)
            ce, cmth = rect_clearance(dist, eyes), rect_clearance(dist, mouth)

            def overlap_px(r):
                x1, y1 = max(0, int(np.floor(r["x1"]))), max(0, int(np.floor(r["y1"])))
                x2, y2 = min(1080, int(np.ceil(r["x2"]))), min(1920, int(np.ceil(r["y2"])))
                return int(gm[y1:y2, x1:x2].sum())

            face_rows.append({
                "g": g, "clip": clip, "local": lf, "speaking": speaking(clip, lf),
                "eyes": {k: round(v, 1) for k, v in eyes.items()},
                "mouth": {k: round(v, 1) for k, v in mouth.items()},
                "cam_scale": round(fr["cam"]["scale"], 4),
                "eyes_clear_px": None if ce is None else round(ce, 1),
                "mouth_clear_px": None if cmth is None else round(cmth, 1),
                "eyes_overlap_px": overlap_px(eyes), "mouth_overlap_px": overlap_px(mouth),
            })
        else:
            sz_frames[g] = None

    # ── end screen (text/logo/chips/arrows only) ──
    es = {}
    for lf in range(105):
        a = load(os.path.join(ESFG, f"f{lf:03d}.png"))
        vis = a[..., 3] > ALPHA_VIS
        out = vis & ~safe
        es[lf] = {"bbox": bbox(vis), "outside_px": int(out.sum()), "outside_bbox": bbox(out)}
        if (ES0 + lf) in WIPE:
            es[lf]["note"] = "under orange wipe (frames 741-744)"

    # summarise check 3
    viol_runs = {k: runs(v) for k, v in sz_viol.items()}
    clip_bbox_union = {}
    for c in (1, 2, 3):
        bbs = [r["bbox"] for g, r in sz_frames.items() if r and r["clip"] == c and r["bbox"]]
        clip_bbox_union[c] = [min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs)]
    rows_gap = [g for g, r in sz_frames.items() if r and r["rows_228_231"]]
    json.dump({
        "excluded_frames": {"join_flash": sorted(FLASH), "orange_wipe": sorted(WIPE), "progress_bar_rows": list(BAR_ROWS)},
        "violation_runs": viol_runs,
        "violations": {g: r for g, r in sz_frames.items() if r and r["outside_px"]},
        "graphics_bbox_union_per_clip": clip_bbox_union,
        "frames_with_pixels_in_rows_228_231": runs(rows_gap),
        "clip1_slab_text_bbox": slab_text,
        "endscreen_fg": es,
        "endscreen_fg_union_settled_(lf>=8)": [min(es[f]["bbox"][0] for f in range(8, 105)), min(es[f]["bbox"][1] for f in range(8, 105)),
                                          max(es[f]["bbox"][2] for f in range(8, 105)), max(es[f]["bbox"][3] for f in range(8, 105))],
    }, open(os.path.join(PARTS, "safe_zone.json"), "w"), indent=1)

    # summarise check 4
    viol = [r for r in face_rows if r["eyes_overlap_px"] or r["mouth_overlap_px"]]
    valid_e = [r for r in face_rows if r["eyes_clear_px"] is not None]
    valid_m = [r for r in face_rows if r["mouth_clear_px"] is not None]
    worst_e = sorted(valid_e, key=lambda r: r["eyes_clear_px"])[:12]
    worst_m = sorted(valid_m, key=lambda r: r["mouth_clear_px"])[:12]
    per_clip = {}
    for c in (1, 2, 3):
        rr = [r for r in face_rows if r["clip"] == c]
        per_clip[c] = {
            "frames_checked": len(rr),
            "min_eyes_clear_px": min(r["eyes_clear_px"] for r in rr),
            "min_mouth_clear_px": min(r["mouth_clear_px"] for r in rr),
            "violating_frames": runs([r["g"] for r in rr if r["eyes_overlap_px"] or r["mouth_overlap_px"]]),
        }
    json.dump({"per_clip": per_clip, "violations": viol, "worst_eyes": worst_e, "worst_mouth": worst_m, "rows": face_rows},
              open(os.path.join(PARTS, "face.json"), "w"), indent=1)

    # summarise check 8
    cols = []
    for kk, n in colour_count.items():
        rgb = ((kk >> 16) & 255, (kk >> 8) & 255, kk & 255)
        best = min(PALETTE.items(), key=lambda p: np.linalg.norm(np.subtract(rgb, p[1])))
        cols.append({"rgb": rgb, "hex": "#%02X%02X%02X" % rgb, "px": n, "nearest": best[0],
                     "rgb_dist": round(float(np.linalg.norm(np.subtract(rgb, best[1]))), 2),
                     "frames": runs(colour_frames[kk]), "n_frames": len(colour_frames[kk]),
                     "where_first": colour_where.get(kk)})
    cols.sort(key=lambda c: -c["px"])
    json.dump(cols, open(os.path.join(PARTS, "colours_raw.json"), "w"))
    print("done")


if __name__ == "__main__":
    main()
