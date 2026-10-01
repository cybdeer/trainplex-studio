#!/usr/bin/env python3
"""QA helper — independent face analysis of EVERY frame of the normalised clips (insightface buffalo_l,
detection + recognition only): bbox, 5-point landmarks (eyes, nose, mouth corners) and the cosine
similarity of the largest face's embedding to flow/character/char_01_master.png.

Used by qa_reel02.py check 4 (eyes/mouth from landmarks, a second detector next to the Haar boxes the
layout uses) and check 9 (identity similarity). insightface buffalo_l is licensed for non-commercial
research: internal QA signal only, never shipped.
Output: work/qa/parts/landmarks.json
"""
import glob
import json
import os

import cv2
import numpy as np

QA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(QA))
REF = os.path.join(ROOT, "flow", "character", "char_01_master.png")
os.makedirs(os.path.join(QA, "parts"), exist_ok=True)


def main():
    from insightface.app import FaceAnalysis
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"], allowed_modules=["detection", "recognition"])
    app.prepare(ctx_id=-1, det_size=(640, 640))

    def largest(img):
        faces = app.get(img)
        return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])) if faces else None

    ref = largest(cv2.imread(REF))
    assert ref is not None, "no face in reference"
    calib = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "flow", "character", "char_*.png"))):
        if os.path.abspath(p) == os.path.abspath(REF):
            continue
        fs = app.get(cv2.imread(p))
        sims = [float(np.dot(x.normed_embedding, ref.normed_embedding)) for x in fs]
        calib[os.path.basename(p)] = round(max(sims), 3) if sims else None

    out = {"reference": os.path.relpath(REF, ROOT).replace("\\", "/"), "ref_calibration_vs_other_sheets": calib, "clips": {}}
    for clip in (1, 2, 3):
        cap = cv2.VideoCapture(os.path.join(ROOT, "work", "norm", f"clip{clip}.mp4"))
        rows, f = [], 0
        while True:
            ok, img = cap.read()
            if not ok:
                break
            fc = largest(img)
            if fc is None:
                rows.append({"f": f, "face": False})
            else:
                rows.append({"f": f, "face": True, "det": round(float(fc.det_score), 3),
                             "bbox": [round(float(v), 1) for v in fc.bbox],
                             "kps": [[round(float(x), 1), round(float(y), 1)] for x, y in fc.kps],
                             "sim": round(float(np.dot(fc.normed_embedding, ref.normed_embedding)), 4)})
            f += 1
        out["clips"][str(clip)] = rows
        sims = [r["sim"] for r in rows if r["face"]]
        print(f"clip{clip}: {len(rows)} frames, faces {len(sims)}, sim min {min(sims):.3f} mean {np.mean(sims):.3f}")
    json.dump(out, open(os.path.join(QA, "parts", "landmarks.json"), "w", encoding="utf-8"), indent=0)


if __name__ == "__main__":
    main()
