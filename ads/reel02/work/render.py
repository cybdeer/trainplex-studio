"""STEP 8 — render, mux, verify, cover + QA grabs.

  python work/render.py                  # full: Remotion render + mux + cover + grabs
  python work/render.py --skip-render    # re-mux / re-grab from an existing Remotion render

1. Remotion renders the muted picture (1080x1920, 30 fps, H.264 High, CRF 18, yuv420p, BT.709,
   PNG intermediate frames, x264 preset slow).
2. work/mux.py muxes the FFmpeg-mastered audio (AAC-LC 48 kHz 192 kbps, +faststart) and measures the
   loudness of the delivered file (after AAC).
3. Cover JPG (rendered straight from Remotion, no re-compression) + frame-exact QA PNG grabs.
All frame numbers are derived from work/edit.json / work/captions.json (nothing hard-coded per take).
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REM = os.path.join(ROOT, "remotion")
OUT = os.path.join(ROOT, "output")
QA = os.path.join(OUT, "qa")
RENDER = os.path.join(ROOT, "work", "render", "reel02_video_muted.mp4")
FPS = 30
QA_TIMES = [0.5, 2.0, 4.5, 12.0, 15.0, 22.0, 26.0]
NPX = "npx.cmd" if os.name == "nt" else "npx"


def run(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def timeline():
    edit = json.load(open(os.path.join(ROOT, "work", "edit.json"), encoding="utf-8"))
    clips = sorted(edit["clips"], key=lambda c: c["clip"])
    es_start = sum(c["frames"] for c in clips)
    es_frames = int(edit.get("end_screen_frames", 105))
    return clips, es_start, es_frames


def cover_frame():
    """Strongest hook frame: clip 1, the hook slab's "खत्म?" punch has landed (6 f after the word starts),
    while the presenter looks into the lens; captions sit below the face (y <= 1400)."""
    words = json.load(open(os.path.join(ROOT, "work", "captions.json"), encoding="utf-8"))
    c1 = [w for w in words if w["clip"] == 1]
    k = next(w for w in c1 if w["word"].startswith("खत्म"))
    return round(k["start"] * FPS) + 6


def main():
    os.makedirs(os.path.dirname(RENDER), exist_ok=True)
    os.makedirs(QA, exist_ok=True)
    clips, es_start, es_frames = timeline()
    total = es_start + es_frames
    if "--skip-render" not in sys.argv:
        run([NPX, "remotion", "render", "src/index.ts", "Reel02", RENDER, "--muted",
             "--codec=h264", "--crf=18", "--pixel-format=yuv420p", "--concurrency=4",
             "--x264-preset=slow", "--image-format=png", "--color-space=bt709"], cwd=REM)

    report = {"timeline": {"clip_frames": [c["frames"] for c in clips], "end_screen_start": es_start,
                           "end_screen_frames": es_frames, "total_frames": total, "total_s": round(total / FPS, 4)},
              "deliverables": {}}
    for name, master in (("TrainPlex_Reel02_9x16.mp4", "music_master.wav"),
                         ("TrainPlex_Reel02_9x16_nomusic.mp4", "voice_master.wav")):
        out = os.path.join(OUT, name)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "work", "mux.py"), RENDER,
                            os.path.join(ROOT, "work", "audio", master), out, "--strict"],
                           capture_output=True, text=True)
        print(r.stderr[-1500:])
        if r.returncode != 0:
            raise SystemExit(f"mux failed for {name}: {r.stderr[-800:]}")
        res = json.loads(r.stdout)
        p = probe(out)
        v = next(s for s in p["streams"] if s["codec_type"] == "video")
        a = next(s for s in p["streams"] if s["codec_type"] == "audio")
        report["deliverables"][name] = {
            "video": {k: v.get(k) for k in ("codec_name", "profile", "width", "height", "pix_fmt", "color_space",
                                            "color_transfer", "color_primaries", "color_range", "r_frame_rate",
                                            "avg_frame_rate", "nb_frames", "duration", "bit_rate")},
            "audio": {k: a.get(k) for k in ("codec_name", "profile", "sample_rate", "channels", "bit_rate", "duration")},
            "format_duration": p["format"]["duration"],
            "size_bytes": int(p["format"]["size"]),
            "faststart": res["container"]["faststart"],
            "loudness_after_aac": res["loudness_after_aac"],
            "mux_warnings": res["warnings"],
        }

    cf = cover_frame()
    cover_png = os.path.join(ROOT, "work", "render", "cover.png")
    run([NPX, "remotion", "still", "src/index.ts", "Reel02", cover_png, f"--frame={cf}"], cwd=REM)
    run(["ffmpeg", "-v", "error", "-y", "-i", cover_png, "-q:v", "2", "-pix_fmt", "yuvj420p",
         os.path.join(OUT, "TrainPlex_Reel02_cover.jpg")])
    report["cover_frame"] = cf

    final = os.path.join(OUT, "TrainPlex_Reel02_9x16.mp4")
    grabs = [(f"qa_{t:05.2f}s.png".replace(".", "_", 1).replace("_png", ".png"), round(t * FPS)) for t in QA_TIMES]
    # end screen: logo landed / CTA landed / final frame
    for lf in (12, 45, es_frames - 1):
        grabs.append((f"qa_endscreen_f{lf:03d}.png", es_start + lf))
    for fname, frame in grabs:
        if frame >= total:
            raise SystemExit(f"grab {fname} frame {frame} beyond the reel ({total} frames)")
        run(["ffmpeg", "-v", "error", "-y", "-i", final, "-vf", f"select=eq(n\\,{frame})", "-vsync", "0",
             "-frames:v", "1", os.path.join(QA, fname)])
    report["qa_grabs"] = {f: {"frame": fr, "time_s": round(fr / FPS, 3)} for f, fr in grabs}
    json.dump(report, open(os.path.join(ROOT, "work", "render_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
