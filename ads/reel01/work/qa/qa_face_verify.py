#!/usr/bin/env python3
"""QA (Agent 13) — check 4 cross-check.
 (a) Independent eye detection: OpenCV haarcascade_eye on the SOURCE clip frames (work/norm/clipN.mp4, no
     graphics), inside the tracked face box, mapped through the real camera transform (zoom/shake) and
     intersected with the graphics alpha (Reel01Graphics render, alpha > 32). Every frame.
 (b) Overlays of the tightest frames on the DELIVERED MP4 with the protected rects drawn, for visual review.
Output: work/qa/parts/face_verify.json, work/qa/view/face_overlay_*.jpg
"""
import json
import os
import subprocess

import cv2
import numpy as np
from PIL import Image

QA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(QA))
D = json.load(open(os.path.join(QA, "cues_dump.json")))
CS = {int(k): v for k, v in D["CLIP_START"].items()}
CF = {int(k): v for k, v in D["CLIP_FRAMES"].items()}
FLASH = set(range(CS[2] - 1, CS[2] + 3)) | set(range(CS[3] - 1, CS[3] + 3))
WIPE = set(range(D["END_SCREEN_START"] - 4, D["END_SCREEN_START"] + 4))
eye_cc = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml"))
cv2.setNumThreads(4)


def to_screen(r, cam):
    s, ox, oy, dx, dy = cam["scale"], cam["originX"], cam["originY"], cam["dx"], cam["dy"]
    return [ox + (r[0] - ox) * s + dx, oy + (r[1] - oy) * s + dy, ox + (r[2] - ox) * s + dx, oy + (r[3] - oy) * s + dy]


res = {"per_clip": {}, "violations": [], "detections": 0}
for c in (1, 2, 3):
    cap = cv2.VideoCapture(os.path.join(ROOT, "work", "norm", f"clip{c}.mp4"))
    min_clear, n_det, worst = 1e9, 0, None
    eyes_outside_band = 0
    for lf in range(CF[c]):
        ok, fr = cap.read()
        if not ok:
            break
        g = CS[c] + lf
        if g in FLASH or g in WIPE:
            continue
        rec = D["faces"][str(c)][lf]
        fb = rec["face"]
        x1, y1, x2, y2 = int(fb["x1"]), int(fb["y1"]), int(fb["x2"]), int(fb["y2"])
        roi = cv2.cvtColor(fr[y1:y1 + (y2 - y1) * 6 // 10, x1:x2], cv2.COLOR_BGR2GRAY)
        w = x2 - x1
        eyes = eye_cc.detectMultiScale(roi, 1.1, 6, minSize=(w // 10, w // 10), maxSize=(w // 3, w // 3))
        if len(eyes) == 0:
            continue
        al = np.array(Image.open(os.path.join(QA, "g", f"f{g:03d}.png")))[..., 3] > 32
        dist = cv2.distanceTransform((~al).astype(np.uint8), cv2.DIST_L2, 5)
        band = rec["eyes"]
        for (ex, ey, ew, eh) in eyes:
            src = [int(x1 + ex), int(y1 + ey), int(x1 + ex + ew), int(y1 + ey + eh)]
            n_det += 1
            # is the detected eye inside the conservative band used by the build (source px)?
            if src[0] < band["x1"] - 2 or src[2] > band["x2"] + 2 or src[1] < band["y1"] - 2 or src[3] > band["y2"] + 2:
                eyes_outside_band += 1
            r = to_screen(src, rec["cam"])
            xa, ya, xb, yb = max(0, int(r[0])), max(0, int(r[1])), min(1080, int(np.ceil(r[2]))), min(1920, int(np.ceil(r[3])))
            if xb <= xa or yb <= ya:
                continue
            cl = float(dist[ya:yb, xa:xb].min())
            if cl < min_clear:
                min_clear, worst = cl, {"g": g, "local": lf, "eye_screen": [round(v, 1) for v in r]}
            if al[ya:yb, xa:xb].any():
                res["violations"].append({"g": g, "clip": c, "local": lf, "eye_screen": [round(v, 1) for v in r],
                                          "overlap_px": int(al[ya:yb, xa:xb].sum())})
    res["per_clip"][c] = {"eye_detections": n_det, "min_clearance_px": round(min_clear, 1), "worst": worst,
                          "detected_eyes_outside_band": eyes_outside_band}
    res["detections"] += n_det
json.dump(res, open(os.path.join(QA, "parts", "face_verify.json"), "w"), indent=1)
print(json.dumps(res["per_clip"], indent=1), "violations:", len(res["violations"]))

# (b) overlays on the delivered MP4
face = json.load(open(os.path.join(QA, "parts", "face.json")))
rows = {r["g"]: r for r in face["rows"]}
picks = [201, 204, 312, 333, 431, 458, 560, 601, 640, 690]
tiles = []
for g in picks:
    p = os.path.join(QA, "stills", f"video_f{g:03d}.png")
    if not os.path.exists(p):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(ROOT, "output", "TrainPlex_Reel01_9x16.mp4"),
                        "-vf", f"select=eq(n\\,{g})", "-vsync", "0", "-frames:v", "1", p], check=True)
    im = cv2.imread(p)
    r = rows[g]
    for key, col in (("eyes", (255, 0, 255)), ("mouth", (255, 255, 0))):
        b = r[key]
        cv2.rectangle(im, (int(b["x1"]), int(b["y1"])), (int(b["x2"]), int(b["y2"])), col, 4)
    cv2.putText(im, f"g{g} c{r['clip']} lf{r['local']} eyes {r['eyes_clear_px']}px mouth {r['mouth_clear_px']}px",
                (20, 1880), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
    tiles.append(cv2.resize(im, (432, 768)))
sheet = np.vstack([np.hstack(tiles[:5]), np.hstack(tiles[5:])])
cv2.imwrite(os.path.join(QA, "view", "face_overlay.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
