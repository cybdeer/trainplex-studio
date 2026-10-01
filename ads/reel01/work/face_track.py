"""Detect the presenter's face per frame (OpenCV Haar) so overlays can avoid eyes/mouth."""
import cv2, json, os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
res = {}
for clip in (1, 2, 3):
    cap = cv2.VideoCapture(os.path.join(root, "work", "norm", f"clip{clip}.mp4"))
    f, boxes = 0, []
    while True:
        ok, img = cap.read()
        if not ok: break
        if f % 3 == 0:
            g = cv2.cvtColor(cv2.resize(img, (540, 960)), cv2.COLOR_BGR2GRAY)
            det = casc.detectMultiScale(g, 1.1, 6, minSize=(120, 120))
            if len(det):
                x, y, w, h = max(det, key=lambda d: d[2] * d[3])
                boxes.append({"frame": f, "x": int(x * 2), "y": int(y * 2), "w": int(w * 2), "h": int(h * 2)})
        f += 1
    xs = [b["x"] for b in boxes]; ys = [b["y"] for b in boxes]
    x2 = [b["x"] + b["w"] for b in boxes]; y2 = [b["y"] + b["h"] for b in boxes]
    union = {"x1": min(xs), "y1": min(ys), "x2": max(x2), "y2": max(y2)} if boxes else None
    # eyes ~ 0.30-0.50 of face box height, mouth ~ 0.68-0.90
    res[clip] = {"frames": f, "detections": len(boxes), "union_face_box": union,
                 "eyes_band_union": {"y1": min(b["y"] + int(0.28 * b["h"]) for b in boxes), "y2": max(b["y"] + int(0.52 * b["h"]) for b in boxes)},
                 "mouth_band_union": {"y1": min(b["y"] + int(0.66 * b["h"]) for b in boxes), "y2": max(b["y"] + int(0.92 * b["h"]) for b in boxes)},
                 "boxes": boxes}
    print(clip, f, len(boxes), union, res[clip]["eyes_band_union"], res[clip]["mouth_band_union"])
json.dump(res, open(os.path.join(root, "work", "face_boxes.json"), "w"), indent=1)
