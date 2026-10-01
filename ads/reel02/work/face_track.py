"""Detect the presenter's face on EVERY frame of every normalised clip (OpenCV Haar, same detector and
parameters as Reel 01) so overlays can avoid the eyes / mouth.

Per frame: largest Haar face at 540x960 (x2 back to 1080x1920). Frames without a detection, or with a
detection that jumps away from its neighbours (false positive: centre > 25 % of the face width from
the running median), are filled from the nearest good frame (marked "filled": true). Each box also
carries the conservative eyes / mouth rects used by remotion/src/timeline.ts faceAt():
  eyes  = x + 0.2w … x + 0.8w,  y + 0.25h … y + 0.50h
  mouth = x + 0.3w … x + 0.7w,  y + 0.64h … y + 0.92h
Output: work/face_boxes.json (schema of Reel 01: only `boxes` is read by Remotion).
"""
import json
import os

import cv2
import numpy as np

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
assert not casc.empty(), "Haar cascade XML missing (pin opencv 4.x)"


def eyes_mouth(x, y, w, h):
    return ({"x1": round(x + 0.2 * w), "y1": round(y + 0.25 * h), "x2": round(x + 0.8 * w), "y2": round(y + 0.5 * h)},
            {"x1": round(x + 0.3 * w), "y1": round(y + 0.64 * h), "x2": round(x + 0.7 * w), "y2": round(y + 0.92 * h)})


def main():
    res = {}
    for clip in (1, 2, 3):
        cap = cv2.VideoCapture(os.path.join(root, "work", "norm", f"clip{clip}.mp4"))
        raw = []
        while True:
            ok, img = cap.read()
            if not ok:
                break
            g = cv2.cvtColor(cv2.resize(img, (540, 960)), cv2.COLOR_BGR2GRAY)
            det = casc.detectMultiScale(g, 1.1, 6, minSize=(120, 120))
            if len(det):
                x, y, w, h = max(det, key=lambda d: d[2] * d[3])
                raw.append([int(x * 2), int(y * 2), int(w * 2), int(h * 2)])
            else:
                raw.append(None)
        n = len(raw)
        good = [r for r in raw if r]
        assert good, f"clip {clip}: no face detected"
        cx_med = np.median([r[0] + r[2] / 2 for r in good])
        cy_med = np.median([r[1] + r[3] / 2 for r in good])
        w_med = np.median([r[2] for r in good])
        ok = []  # plain bools (json-serialisable counts)
        for r in raw:
            if r is None:
                ok.append(False)
                continue
            d = np.hypot(r[0] + r[2] / 2 - cx_med, r[1] + r[3] / 2 - cy_med)
            ok.append(bool(d <= 0.25 * w_med and 0.6 * w_med <= r[2] <= 1.4 * w_med))
        good_idx = [i for i in range(n) if ok[i]]
        boxes = []
        for f in range(n):
            if ok[f]:
                x, y, w, h = raw[f]
                filled = False
            else:
                j = min(good_idx, key=lambda i: abs(i - f))
                x, y, w, h = raw[j]
                filled = True
            e, m = eyes_mouth(x, y, w, h)
            boxes.append({"frame": f, "x": x, "y": y, "w": w, "h": h, "filled": filled, "eyes": e, "mouth": m})
        x1 = min(b["x"] for b in boxes); y1 = min(b["y"] for b in boxes)
        x2 = max(b["x"] + b["w"] for b in boxes); y2 = max(b["y"] + b["h"] for b in boxes)
        res[str(clip)] = {
            "frames": n, "detections": sum(ok), "filled_frames": n - sum(ok),
            "rejected_outliers": sum(1 for i in range(n) if raw[i] is not None and not ok[i]),
            "union_face_box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            "eyes_band_union": {"y1": min(b["eyes"]["y1"] for b in boxes), "y2": max(b["eyes"]["y2"] for b in boxes)},
            "mouth_band_union": {"y1": min(b["mouth"]["y1"] for b in boxes), "y2": max(b["mouth"]["y2"] for b in boxes)},
            "boxes": boxes,
        }
        r = res[str(clip)]
        print(clip, n, "detected", r["detections"], "filled", r["filled_frames"], "outliers", r["rejected_outliers"],
              r["union_face_box"], r["eyes_band_union"], r["mouth_band_union"])
    json.dump(res, open(os.path.join(root, "work", "face_boxes.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
