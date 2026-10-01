#!/usr/bin/env python3
"""Reel 02 automated QA suite — the 9 delivery checks. Writes work/qa/qa_results.json (+ parts/*.json).

Inputs (all produced by work/run_pipeline.ps1):
  output/TrainPlex_Reel02_9x16.mp4, output/TrainPlex_Reel02_9x16_nomusic.mp4
  work/qa/g/f*.png             Reel02Graphics: every overlay of the reel (video hidden, RGBA)
  work/qa/iso/Cap{1,2,3}/      captions only (RGBA) — remotion_qa entry
  work/qa/iso/EndScreenFG/     end screen with its full-bleed backgrounds removed — remotion_qa entry
  work/qa/cues_dump.json       timing / camera / face / geometry evaluated from the real remotion/src code
  work/qa/parts/landmarks.json insightface landmarks + identity similarity per clip frame (qa_landmarks.py)
  work/captions.json, work/script.json, work/norm/clipN.wav

Checks
  1 ffprobe: 1080x1920, 30 fps CFR, H.264 (High), yuv420p, BT.709, duration 25-30 s (both MP4s)
  2 loudness after AAC: -14 +/- 0.5 LUFS integrated, true peak <= -1.0 dBTP (both MP4s)
  3 captions concatenate exactly to the script (data + displayed text), no blank caption frame at chunk swaps
    and no unplanned blank frame while speech continues; every chunk renders on ONE line (block <= 175 px)
  4 no overlay pixel inside the eye / mouth boxes on any clip frame (Haar boxes used by the layout AND
    independent insightface landmark boxes), boxes mapped through the camera transform
  5 every overlay pixel inside the safe zone x 60-1020, y 220-1480 (clip overlays + end-screen foreground)
  6 disclaimer fully visible on every frame the earnings number is shown (plate figure + caption chunk)
  7 never two logos on screen at once (logo-artwork orange #FE5015 blobs per frame)
  8 no black / frozen frames at the joins; audio/video offset <= 1 frame (cross-correlation per clip)
  9 face-embedding similarity of the presenter in all 3 clips vs flow/character/char_01_master.png (0.45)
Exempt from 4/5 (full-frame transitions, not overlays): the 4-frame white join flashes and the 8-frame
orange wipe; the 8 px full-width progress bar at y 220-228 is exempt from 5 (as in Reel 01).
"""
import glob
import json
import os
import re
import subprocess
from collections import Counter

import cv2
import numpy as np
from PIL import Image

QA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(QA))
PARTS = os.path.join(QA, "parts")
os.makedirs(PARTS, exist_ok=True)
OUT = os.path.join(ROOT, "output")
FINAL = os.path.join(OUT, "TrainPlex_Reel02_9x16.mp4")
NOMUSIC = os.path.join(OUT, "TrainPlex_Reel02_9x16_nomusic.mp4")
FPS = 30
W, H = 1080, 1920
SAFE = dict(x1=60, x2=1020, y1=220, y2=1480)
BAR = (220, 228)
ALPHA_VIS = 32
LOGO_ORANGE = np.array([254, 80, 21])  # the logo artwork's own orange (#FE5015), distinct from brand #FF6B35
FACE_SIM_MIN = 0.45

D = json.load(open(os.path.join(QA, "cues_dump.json"), encoding="utf-8"))
CS = {int(k): v for k, v in D["CLIP_START"].items()}
CF = {int(k): v for k, v in D["CLIP_FRAMES"].items()}
ES0, ESN, TOTAL = D["END_SCREEN_START"], D["END_SCREEN_FRAMES"], D["TOTAL_FRAMES"]
FLASH = set(range(CS[2] - 1, CS[2] + 3)) | set(range(CS[3] - 1, CS[3] + 3))
WIPE = set(range(D["WIPE"]["start"], D["WIPE"]["start"] + D["WIPE"]["frames"]))
SCRIPT = json.load(open(os.path.join(ROOT, "work", "script.json"), encoding="utf-8"))
CAPS = json.load(open(os.path.join(ROOT, "work", "captions.json"), encoding="utf-8"))


def seq(folder):
    fs = sorted(glob.glob(os.path.join(folder, "*.png")), key=lambda p: int(re.findall(r"(\d+)", os.path.basename(p))[-1]))
    return fs


G = seq(os.path.join(QA, "g"))
assert len(G) == TOTAL, f"graphics render has {len(G)} frames, expected {TOTAL}"


def rgba(path):
    a = np.array(Image.open(path))
    if a.ndim == 3 and a.shape[2] == 3:
        a = np.dstack([a, np.full(a.shape[:2], 255, np.uint8)])
    return a


def clip_of(g):
    for c in (3, 2, 1):
        if CS[c] <= g < CS[c] + CF[c]:
            return c, g - CS[c]
    return None, g - ES0


def runs(frames):
    out = []
    for f in sorted(frames):
        if out and f == out[-1][1] + 1:
            out[-1][1] = f
        else:
            out.append([f, f])
    return out


def to_screen(r, cam):
    s, ox, oy, dx, dy = cam["scale"], cam["originX"], cam["originY"], cam["dx"], cam["dy"]
    return dict(x1=ox + (r["x1"] - ox) * s + dx, y1=oy + (r["y1"] - oy) * s + dy,
                x2=ox + (r["x2"] - ox) * s + dx, y2=oy + (r["y2"] - oy) * s + dy)


def box_px(mask, r):
    x1, y1 = max(0, int(np.floor(r["x1"]))), max(0, int(np.floor(r["y1"])))
    x2, y2 = min(W, int(np.ceil(r["x2"]))), min(H, int(np.ceil(r["y2"])))
    if x2 <= x1 or y2 <= y1:
        return 0
    return int(mask[y1:y2, x1:x2].sum())


def ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-count_frames", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def ebur128(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0",
                        "-af", "ebur128=peak=true:metadata=1,ametadata=mode=print:file=-", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    summ = p.stderr[p.stderr.rfind("Summary:"):]
    I = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1))
    TP = float(re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf)", summ).group(1))
    LRA = float(re.search(r"LRA:\s+(-?[\d.]+) LU", summ).group(1))
    tp_lin = [float(v) for v in re.findall(r"lavfi\.r128\.true_peak=(\S+)", p.stdout)]
    i_prec = [float(v) for v in re.findall(r"lavfi\.r128\.I=(\S+)", p.stdout)]
    return {"I_lufs": I, "LRA_lu": LRA, "true_peak_dbtp": TP,
            "precise_I_lufs": i_prec[-1] if i_prec else None,
            "precise_true_peak_dbtp": round(20 * np.log10(max(tp_lin)), 3) if tp_lin else None}


RESULTS = []


def _np(o):
    """json default: numpy scalars / sets -> python."""
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(type(o))


def record(n, name, ok, evidence):
    RESULTS.append({"check": n, "name": name, "result": "PASS" if ok else "FAIL", "evidence": evidence})
    print(f"[{'PASS' if ok else 'FAIL'}] {n} {name}: {json.dumps(evidence, ensure_ascii=False, default=_np)[:600]}")


# ─── 1. delivery specs ────────────────────────────────────────────────────────────────────────
def check1():
    ev, ok = {}, True
    for path in (FINAL, NOMUSIC):
        p = ffprobe(path)
        v = next(s for s in p["streams"] if s["codec_type"] == "video")
        a = next(s for s in p["streams"] if s["codec_type"] == "audio")
        dur = float(p["format"]["duration"])
        e = {"codec": v["codec_name"], "profile": v.get("profile"), "size": f"{v['width']}x{v['height']}",
             "r_frame_rate": v["r_frame_rate"], "avg_frame_rate": v["avg_frame_rate"], "frames": int(v["nb_read_frames"]),
             "pix_fmt": v["pix_fmt"], "color_space": v.get("color_space"), "color_transfer": v.get("color_transfer"),
             "color_primaries": v.get("color_primaries"), "color_range": v.get("color_range"),
             "duration_s": round(dur, 4), "video_duration_s": float(v["duration"]),
             "audio": f"{a['codec_name']} {a.get('profile')} {a['sample_rate']} Hz {a['channels']} ch",
             "aspect": "9:16" if v["width"] * 16 == v["height"] * 9 else "NOT 9:16"}
        good = (v["codec_name"] == "h264" and v.get("profile") == "High" and v["width"] == 1080 and v["height"] == 1920
                and v["r_frame_rate"] == "30/1" and v["avg_frame_rate"] == "30/1" and v["pix_fmt"] == "yuv420p"
                and v.get("color_space") == "bt709" and v.get("color_primaries") == "bt709" and v.get("color_transfer") == "bt709"
                and 25.0 <= dur <= 30.0 and int(v["nb_read_frames"]) == TOTAL and a["codec_name"] == "aac"
                and a.get("profile") == "LC" and a["sample_rate"] == "48000")
        e["ok"] = good
        ok &= good
        ev[os.path.basename(path)] = e
    record(1, "ffprobe delivery specs (1080x1920, 30 fps, H.264 High, yuv420p, BT.709, 25-30 s)", ok, ev)


# ─── 2. loudness ──────────────────────────────────────────────────────────────────────────────
def check2():
    ev, ok = {}, True
    for path in (FINAL, NOMUSIC):
        m = ebur128(path)
        tp = m["precise_true_peak_dbtp"] if m["precise_true_peak_dbtp"] is not None else m["true_peak_dbtp"]
        good = abs(m["I_lufs"] + 14.0) <= 0.5 and tp <= -1.0
        m["ok"] = good
        ok &= good
        ev[os.path.basename(path)] = m
    record(2, "loudness after AAC: -14 +/- 0.5 LUFS, TP <= -1 dBTP", ok, ev)


# ─── 3. captions ──────────────────────────────────────────────────────────────────────────────
def norm(s):
    return " ".join(s.split())


def check3():
    ev, ok = {"clips": {}}, True
    for c in (1, 2, 3):
        want = norm(SCRIPT["clips"][f"clip{c}"])
        data = norm(" ".join(w["word"] for w in CAPS if w["clip"] == c))
        chunks = D["chunks"][str(c)]
        code = norm(" ".join(w["word"] for ch in chunks for w in ch["words"]))
        shown = norm(" ".join(w["text"] for ch in chunks for w in ch["words"]))
        # displayed text may only differ by the uppercase rule for Latin highlights (TrainPlex never re-cased)
        shown_ok = shown.lower() == want.lower() and "TrainPlex" in shown if "TrainPlex" in want else shown.lower() == want.lower()
        masks = []
        cap_dir = os.path.join(QA, "iso", f"Cap{c}")
        files = seq(cap_dir)
        assert len(files) == CF[c], (cap_dir, len(files), CF[c])
        alphas = [rgba(p)[..., 3] > ALPHA_VIS for p in files]
        present = [bool(m.any()) for m in alphas]
        # one-line rule (REMOTION_INPUTS.md): rendered block height of every chunk at its settled frame
        heights = {}
        for ch in chunks:
            f = min(ch["appear"] + 9, ch["hideEnd"] - 1)
            ys = np.nonzero(alphas[f].any(1))[0]
            heights[" ".join(w["text"] for w in ch["words"])] = int(ys.max() - ys.min() + 1) if len(ys) else 0
        two_line = [t for t, h in heights.items() if h > 175]
        first, last = chunks[0]["appear"], chunks[-1]["hideEnd"]
        planned = set()
        for i, ch in enumerate(chunks[:-1]):
            if ch["exit"] == "fade":
                planned |= set(range(ch["hideEnd"], chunks[i + 1]["appear"] + 1))
        blanks = [f for f in range(first, last) if not present[f]]
        unplanned = [f for f in blanks if f not in planned]
        swaps = [ch["hideEnd"] for ch in chunks[:-1] if ch["exit"] == "swap"]
        swap_blank = [s for s in swaps if not all(present[f] for f in range(max(0, s - 1), min(CF[c], s + 2)))]
        # is any word spoken while the caption layer is blank?
        spoken_blank = sorted({f for w in CAPS if w["clip"] == c
                               for f in range(round(w["start"] * FPS), max(round(w["start"] * FPS) + 1, round(w["end"] * FPS)))
                               if f < CF[c] and not present[f]})
        good = data == want and code == want and shown_ok and not unplanned and not swap_blank and not spoken_blank and not two_line
        ok &= good
        ev["clips"][c] = {"script_match_data": data == want, "script_match_code_chunks": code == want,
                          "chunk_block_height_px": heights, "two_line_chunks": two_line,
                          "displayed_text_matches_script_case_insensitive": shown_ok, "chunks": len(chunks),
                          "hard_swaps": len(swaps), "swaps_with_blank_frame": swap_blank,
                          "planned_pause_fade_frames": runs(planned & set(blanks)),
                          "unplanned_blank_frames": runs(unplanned), "blank_frames_while_a_word_is_spoken": runs(spoken_blank),
                          "ok": good}
    record(3, "captions = exact script; no blank caption frames at chunk swaps", ok, ev)


# ─── 4/5/6/7 per-frame overlay analysis on the graphics render ─────────────────────────────────
def landmark_boxes(kps, cam):
    (lx, ly), (rx, ry), _, (mlx, mly), (mrx, mry) = kps
    iod = float(np.hypot(rx - lx, ry - ly))
    eyes = [dict(x1=x - 0.35 * iod, x2=x + 0.35 * iod, y1=y - 0.22 * iod, y2=y + 0.22 * iod) for x, y in ((lx, ly), (rx, ry))]
    mouth = dict(x1=min(mlx, mrx) - 0.2 * iod, x2=max(mlx, mrx) + 0.2 * iod,
                 y1=min(mly, mry) - 0.3 * iod, y2=max(mly, mry) + 0.3 * iod)
    return [to_screen(e, cam) for e in eyes], to_screen(mouth, cam)


def logo_blobs(rgb, al):
    """One blob per logo instance: logo-orange pixels, dilated 31 px so the icon's pieces merge into one."""
    m = (np.abs(rgb.astype(int) - LOGO_ORANGE).max(2) <= 14) & (al > 100)
    if m.sum() < 120:
        return []
    md = cv2.dilate(m.astype(np.uint8), np.ones((31, 31), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(md, connectivity=8)
    out = []
    for i in range(1, n):
        px = int(m[lab == i].sum())
        if px >= 120:
            out.append([int(st[i][0]), int(st[i][1]), int(st[i][0] + st[i][2]), int(st[i][1] + st[i][3]), px])
    # a large logo's icon frame and its inner glyph are separate blobs: merge blobs whose boxes intersect
    merged = True
    while merged:
        merged = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = out[i], out[j]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    out[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]), a[4] + b[4]]
                    del out[j]
                    merged = True
                    break
            if merged:
                break
    return out


def per_frame():
    LM = json.load(open(os.path.join(PARTS, "landmarks.json"), encoding="utf-8"))
    safe = np.zeros((H, W), bool)
    safe[SAFE["y1"]:SAFE["y2"], SAFE["x1"]:SAFE["x2"]] = True
    C3 = D["clip3"]
    P = C3["PLATE"]
    Y1, Y2 = C3["DISC_STRIP"]["y1"], C3["DISC_STRIP"]["y2"]
    face_rows, sz_viol, logo_rows, disc_rows = [], [], [], []
    min_clear = {1: [1e9, 1e9], 2: [1e9, 1e9], 3: [1e9, 1e9]}
    for g in range(TOTAL):
        a = rgba(G[g])
        rgb, al = a[..., :3], a[..., 3]
        vis = al > ALPHA_VIS
        clip, lf = clip_of(g)
        # 7: logos (graphics render; end screen is opaque so the logo is found on cream as well)
        blobs = logo_blobs(rgb, al)
        logo_rows.append({"g": g, "logos": len(blobs), "blobs": blobs})
        if clip is None or g in FLASH or g in WIPE:
            continue
        # 5: safe zone (bar rows exempt)
        v5 = vis.copy()
        v5[BAR[0]:BAR[1]] = False
        out = v5 & ~safe
        if out.any():
            ys, xs = np.nonzero(out)
            sz_viol.append({"g": g, "clip": clip, "local": lf, "px": int(out.sum()),
                            "bbox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]})
        # 4: eyes / mouth (Haar boxes of the layout + insightface landmark boxes)
        fr = D["faces"][str(clip)][lf]
        cam = fr["cam"]
        eh, mh = to_screen(fr["eyes"], cam), to_screen(fr["mouth"], cam)
        row = {"g": g, "clip": clip, "local": lf, "haar_eyes_px": box_px(vis, eh), "haar_mouth_px": box_px(vis, mh)}
        lm = LM["clips"][str(clip)][lf]
        if lm["face"]:
            eyes, mouth = landmark_boxes(lm["kps"], cam)
            row["lm_eyes_px"] = sum(box_px(vis, e) for e in eyes)
            row["lm_mouth_px"] = box_px(vis, mouth)
        else:
            row["lm_eyes_px"] = row["lm_mouth_px"] = None
        # clearance (px) from the nearest overlay pixel to the Haar eyes / mouth boxes
        if vis.any():
            dist = cv2.distanceTransform((~vis).astype(np.uint8), cv2.DIST_L2, 5)
            for k, r in enumerate((eh, mh)):
                x1, y1 = max(0, int(r["x1"])), max(0, int(r["y1"]))
                x2, y2 = min(W, int(np.ceil(r["x2"]))), min(H, int(np.ceil(r["y2"])))
                if x2 > x1 and y2 > y1:
                    min_clear[clip][k] = min(min_clear[clip][k], float(dist[y1:y2, x1:x2].min()))
        face_rows.append(row)
        # 6: disclaimer + plate figure (clip 3)
        if clip == 3:
            pr = rgb[P["y1"]:P["y2"], P["x1"]:P["x2"]].astype(int)
            pa = al[P["y1"]:P["y2"], P["x1"]:P["x2"]]
            navy = int(((np.abs(pr - [26, 26, 94]).max(2) <= 8) & (pa > 250)).sum())
            # the ₹ figure is brand-orange text on the navy plate (nothing else orange-filled there before the figure)
            fig = int(((np.abs(pr - [255, 107, 53]).max(2) <= 60) & (pa > 200)).sum()) if navy > 20000 else 0
            st_a = al[Y1:Y2]
            strip_w = int((st_a > 100).any(0).sum())
            text = int(((st_a == 255) & (rgb[Y1:Y2].min(2) > 200)).sum())
            disc_rows.append({"local": lf, "g": g, "figure_px": fig, "strip_w": strip_w, "text_px": text})
    # end-screen foreground (text / logo / CTA) in the safe zone
    es_files = seq(os.path.join(QA, "iso", "EndScreenFG"))
    assert len(es_files) == ESN, (len(es_files), ESN)
    es_viol = []
    for lf, p in enumerate(es_files):
        if ES0 + lf in WIPE:
            continue
        vis = rgba(p)[..., 3] > ALPHA_VIS
        out = vis & ~safe
        if out.any():
            ys, xs = np.nonzero(out)
            es_viol.append({"local": lf, "px": int(out.sum()), "bbox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]})
    return face_rows, min_clear, sz_viol, es_viol, logo_rows, disc_rows


def check4(face_rows, min_clear):
    bad = [r for r in face_rows if r["haar_eyes_px"] or r["haar_mouth_px"] or (r["lm_eyes_px"] or 0) or (r["lm_mouth_px"] or 0)]
    no_lm = [r["g"] for r in face_rows if r["lm_eyes_px"] is None]
    ev = {"frames_checked": len(face_rows), "violating_frames": runs([r["g"] for r in bad]),
          "violations_sample": bad[:10],
          "min_clearance_px_haar": {c: {"eyes": round(v[0], 1), "mouth": round(v[1], 1)} for c, v in min_clear.items()},
          "frames_without_landmark_face": runs(no_lm),
          "exempt": {"join_flash_frames": sorted(FLASH), "orange_wipe_frames": sorted(WIPE)}}
    json.dump({"rows": face_rows}, open(os.path.join(PARTS, "face_overlap.json"), "w"), indent=0, default=_np)
    record(4, "no overlay pixels inside eye/mouth boxes (Haar + insightface landmarks, camera-mapped)", not bad, ev)


def check5(sz_viol, es_viol):
    ev = {"clip_frames_with_pixels_outside": runs([v["g"] for v in sz_viol]), "clip_samples": sz_viol[:8],
          "endscreen_fg_frames_outside": runs([v["local"] for v in es_viol]), "endscreen_samples": es_viol[:8],
          "safe_zone": SAFE, "exempt": "progress bar rows 220-228 (full width), join flashes, orange wipe"}
    record(5, "every overlay inside safe zone x 60-1020, y 220-1480", not sz_viol and not es_viol, ev)


def check6(disc_rows):
    C3 = D["clip3"]
    rows = disc_rows
    full_w = Counter(r["strip_w"] for r in rows if r["strip_w"] > 200).most_common(1)[0][0]
    full_t = Counter(r["text_px"] for r in rows if r["text_px"] > 0).most_common(1)[0][0]
    disc_full = {r["local"] for r in rows if r["strip_w"] >= full_w - 2 and r["text_px"] >= 0.97 * full_t}
    fig_px = {r["local"] for r in rows if r["figure_px"] > 2000}
    # the earnings number also appears spoken + captioned: every frame the caption chunk with चार सौ / पाँच सौ shows
    num_chunks = [ch for ch in D["chunks"]["3"] if any(w["word"].strip(",।!?") in ("चार", "पाँच") for w in ch["words"])]
    cap_num = set()
    for ch in num_chunks:
        cap_num |= set(range(ch["appear"], ch["hideEnd"]))
    code_fig = set(range(C3["FIGURE_ON"], C3["PLATE_GONE"]))
    shown = (fig_px | cap_num | code_fig) - {r for r in range(CF[3]) if CS[3] + r in WIPE | FLASH}
    missing = sorted(shown - disc_full)
    after = [f for f in disc_full if f > max(shown)]
    ev = {"figure_frames_pixel": runs(fig_px), "figure_frames_code": [C3["FIGURE_ON"], C3["PLATE_GONE"] - 1],
          "number_caption_frames": runs(cap_num), "disclaimer_fully_visible_frames": runs(disc_full),
          "frames_number_shown_without_full_disclaimer": runs(missing),
          "disclaimer_in_before_figure_frames": C3["FIGURE_ON"] - min(disc_full) if disc_full else None,
          "disclaimer_hold_after_number_s": round(len(after) / FPS, 2), "strip_y": [C3["DISC_STRIP"]["y1"], C3["DISC_STRIP"]["y2"]],
          "local_frames": "clip 3 local frames (global = local + %d)" % CS[3]}
    json.dump(disc_rows, open(os.path.join(PARTS, "disclaimer_rows.json"), "w"), indent=0, default=_np)
    record(6, "disclaimer visible for the whole window the earnings number is shown", bool(shown) and not missing, ev)


def check7(logo_rows):
    two = [r for r in logo_rows if r["logos"] >= 2]
    by_section = {}
    for r in logo_rows:
        c, _ = clip_of(r["g"])
        key = f"clip{c}" if c else "endscreen"
        by_section.setdefault(key, set()).add(r["g"]) if r["logos"] else None
    ev = {"frames_with_2plus_logos": runs([r["g"] for r in two]), "samples": two[:6],
          "frames_with_a_logo": {k: runs(v) for k, v in by_section.items()},
          "method": "connected blobs (>=120 px, alpha>100) of the logo artwork orange #FE5015 +/-14 per frame of Reel02Graphics"}
    json.dump(logo_rows, open(os.path.join(PARTS, "logo_rows.json"), "w"), indent=0, default=_np)
    record(7, "never two logos on screen at once", not two, ev)


# ─── 8. joins + A/V offset ──────────────────────────────────────────────────────────────────────
def decode(path, a, b):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"select=between(n\\,{a}\\,{b}),scale=270:480",
                          "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 480, 270).astype(float)


def audio_mono(path, sr=48000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def check8():
    ev, ok = {"joins": {}}, True
    for name, cut in (("clip1->clip2", CS[2]), ("clip2->clip3", CS[3]), ("clip3->endscreen", ES0)):
        a, b = cut - 8, cut + 8
        fr = decode(FINAL, a, b)
        means = fr.mean((1, 2))
        diffs = np.abs(np.diff(fr, axis=0)).mean((1, 2))
        black = [a + i for i, m in enumerate(means) if m < 16 and fr[i].max() < 40]
        frozen_runs, run = [], 0
        for i, d in enumerate(diffs):
            run = run + 1 if d < 0.3 else 0
            if run >= 2:  # 3+ identical frames (24->30 fps conversion only ever repeats a frame once)
                frozen_runs.append(a + i + 1)
        good = not black and not frozen_runs
        ok &= good
        ev["joins"][name] = {"frames": [a, b], "mean_luma": [round(m, 1) for m in means], "black_frames": black,
                             "frozen_3plus": frozen_runs, "ok": good}
    # whole-file black / freeze detection
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", FINAL, "-vf",
                        "blackdetect=d=0.03:pix_th=0.10,freezedetect=n=0.001:d=0.15", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    blacks = re.findall(r"black_start:(\S+) black_end:(\S+)", r.stderr)
    freezes = re.findall(r"freeze_start: (\S+)", r.stderr)
    ev["blackdetect_segments"] = blacks
    ev["freezedetect_starts_s"] = freezes
    ok &= not blacks
    # A/V offset: each trimmed source clip's audio located in the delivered audio by cross-correlation
    deliv = audio_mono(FINAL)
    av = {}
    for c in (1, 2, 3):
        ref = audio_mono(os.path.join(ROOT, "work", "norm", f"clip{c}.wav"))
        s0 = int(CS[c] / FPS * 48000)
        pad = 4800  # search +/- 100 ms
        lo = max(0, s0 - pad)
        seg = deliv[lo:s0 + len(ref) + pad]
        n = 1 << int(np.ceil(np.log2(len(seg) + len(ref))))
        xc = np.fft.irfft(np.fft.rfft(seg, n) * np.conj(np.fft.rfft(ref, n)), n)
        lag_range = np.arange(0, len(seg) - len(ref) + 1)
        k = int(lag_range[np.argmax(xc[lag_range])])
        lag_ms = (lo + k - s0) / 48.0
        av[f"clip{c}"] = {"expected_start_s": round(s0 / 48000, 4), "lag_ms": round(lag_ms, 2)}
    av_ok = all(abs(v["lag_ms"]) <= 1000 / FPS for v in av.values())
    p = ffprobe(FINAL)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = next(s for s in p["streams"] if s["codec_type"] == "audio")
    ev["av_offset"] = av
    ev["stream_start_times"] = {"video": v.get("start_time"), "audio": a.get("start_time")}
    ev["stream_durations"] = {"video": v.get("duration"), "audio": a.get("duration")}
    st_ok = abs(float(v.get("start_time", 0)) - float(a.get("start_time", 0))) <= 1 / FPS and \
        abs(float(v["duration"]) - float(a["duration"])) <= 1 / FPS
    ok &= av_ok and st_ok
    record(8, "no black/frozen frames at joins; A/V offset <= 1 frame", ok, ev)


# ─── 9. identity ───────────────────────────────────────────────────────────────────────────────
def check9():
    LM = json.load(open(os.path.join(PARTS, "landmarks.json"), encoding="utf-8"))
    ev, ok = {"reference": LM["reference"], "threshold": FACE_SIM_MIN,
              "ref_calibration_vs_other_sheets": LM["ref_calibration_vs_other_sheets"], "clips": {}}, True
    for c in (1, 2, 3):
        rows = LM["clips"][str(c)]
        sims = np.array([r["sim"] for r in rows if r["face"]])
        below = [r["f"] for r in rows if r["face"] and r["sim"] < FACE_SIM_MIN]
        miss = [r["f"] for r in rows if not r["face"]]
        good = len(sims) > 0 and float(np.median(sims)) >= FACE_SIM_MIN and len(below) <= 0.05 * len(rows)
        ok &= good
        ev["clips"][c] = {"frames": len(rows), "faces": int(len(sims)), "sim_min": round(float(sims.min()), 3),
                          "sim_p05": round(float(np.percentile(sims, 5)), 3), "sim_median": round(float(np.median(sims)), 3),
                          "sim_mean": round(float(sims.mean()), 3), "frames_below_threshold": runs(below),
                          "frames_below_pct": round(100 * len(below) / len(rows), 1), "frames_without_face": runs(miss),
                          "ok": good}
    ev["rule"] = ("per clip: median similarity >= 0.45 and <= 5 % of frames below 0.45 (every frame scored; single "
                  "frames dip with blur / mid-blink / mid-word); flagged frames are listed for a manual look")
    record(9, "face-embedding similarity vs char_01_master.png (insightface, 0.45)", ok, ev)


def main():
    check1()
    check2()
    check3()
    face_rows, min_clear, sz_viol, es_viol, logo_rows, disc_rows = per_frame()
    check4(face_rows, min_clear)
    check5(sz_viol, es_viol)
    check6(disc_rows)
    check7(logo_rows)
    check8()
    check9()
    res = {"reel": "TrainPlex Reel 02", "total_frames": TOTAL, "duration_s": round(TOTAL / FPS, 4),
           "all_pass": all(r["result"] == "PASS" for r in RESULTS),
           "summary": {r["check"]: r["result"] for r in RESULTS}, "checks": RESULTS}
    json.dump(res, open(os.path.join(QA, "qa_results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=_np)
    print("ALL PASS" if res["all_pass"] else "FAILURES: " + ", ".join(str(r["check"]) for r in RESULTS if r["result"] != "PASS"))
    return 0 if res["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
