#!/usr/bin/env python3
"""QA (Agent 13) — delivery specs of both MP4s (ffprobe, packet durations, atom order, ebur128) + cover JPG.
Output: work/qa/parts/delivery.json
"""
import hashlib
import json
import os
import re
import subprocess

import numpy as np
from PIL import Image

QA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(QA))
OUT = os.path.join(ROOT, "output")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def atoms(path):
    res = []
    with open(path, "rb") as f:
        while True:
            h = f.read(8)
            if len(h) < 8:
                break
            size, kind = int.from_bytes(h[:4], "big"), h[4:].decode("latin-1")
            if size == 1:
                size = int.from_bytes(f.read(8), "big")
                f.seek(size - 16, 1)
            else:
                f.seek(size - 8, 1)
            res.append(kind)
    return res


res = {}
for name in ("TrainPlex_Reel02_9x16.mp4", "TrainPlex_Reel02_9x16_nomusic.mp4"):
    p = os.path.join(OUT, name)
    pr = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", p]).stdout)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    a = next(s for s in pr["streams"] if s["codec_type"] == "audio")
    durs = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=duration_time", "-of", "csv=p=0", p]).stdout.split()
    er = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", p, "-map", "0:a", "-af", "ebur128=peak=true", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    summ = er[er.rfind("Summary:"):]
    g = lambda pat: float(re.search(pat, summ, re.S).group(1))
    # silence at the end (end screen) explains the average AAC bit-rate
    sil = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", p, "-map", "0:a", "-af", "silencedetect=n=-60dB:d=0.5", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    silences = re.findall(r"silence_start: ([\d.]+)", sil)
    at = atoms(p)
    res[name] = {
        "md5": hashlib.md5(open(p, "rb").read()).hexdigest(),
        "size_bytes": os.path.getsize(p),
        "video": {k: v.get(k) for k in ("codec_name", "profile", "level", "width", "height", "pix_fmt", "color_range", "color_space",
                                        "color_transfer", "color_primaries", "r_frame_rate", "avg_frame_rate", "nb_frames", "duration", "bit_rate")},
        "video_packet_durations": sorted(set(durs)), "cfr": len(set(durs)) == 1,
        "audio": {k: a.get(k) for k in ("codec_name", "profile", "sample_rate", "channels", "channel_layout", "bit_rate", "duration", "duration_ts")},
        "format_duration": pr["format"]["duration"],
        "top_level_atoms": at, "faststart": at.index("moov") < at.index("mdat"),
        "loudness": {"I_lufs": g(r"I:\s+(-?[\d.]+) LUFS"), "LRA_lu": g(r"LRA:\s+(-?[\d.]+) LU"), "true_peak_dbtp": g(r"Peak:\s+(-?[\d.]+) dBFS")},
        "silence_starts_s_(<-60dB,>=0.5s)": [float(s) for s in silences],
    }
res["mp4s_byte_identical"] = res["TrainPlex_Reel02_9x16.mp4"]["md5"] == res["TrainPlex_Reel02_9x16_nomusic.mp4"]["md5"]
res["music_asset_present"] = os.path.exists(os.path.join(ROOT, "assets", "music.mp3"))
cov = os.path.join(OUT, "TrainPlex_Reel02_cover.jpg")
im = Image.open(cov)
# the slab: dominant navy band in y 250-520 of the cover
a = np.array(im.convert("RGB")).astype(int)
navy = (np.abs(a - [26, 26, 94]).max(2) <= 14)
res["cover"] = {"size": list(im.size), "format": im.format, "mode": im.mode,
                "navy_px_in_slab_band_y250_520": int(navy[250:520].sum()),
                "navy_band_columns_covered": int(navy[250:520].any(0).sum())}
json.dump(res, open(os.path.join(QA, "parts", "delivery.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
