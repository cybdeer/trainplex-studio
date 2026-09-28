"""STEP 8 — render, mux, verify, cover + QA grabs.

  python3 work/render.py            # full pipeline
  python3 work/render.py --skip-render   # re-mux / re-grab from an existing Remotion render

1. Remotion renders the muted picture (1080x1920, 30 fps, H.264, CRF 18, yuv420p).
2. work/mux.py muxes the FFmpeg-mastered audio (AAC-LC 48 kHz 192 kbps, +faststart) and
   measures loudness of the delivered file.
3. ffprobe verifies every delivery spec; cover JPG + QA PNG grabs are written to output/.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REM = os.path.join(ROOT, "remotion")
OUT = os.path.join(ROOT, "output")
QA = os.path.join(OUT, "qa")
RENDER = os.path.join(ROOT, "work", "render", "reel01_video_muted.mp4")
FPS = 30
END_SCREEN_START = 741  # frames (see remotion/src/timeline.ts)
QA_TIMES = [0.5, 2.0, 4.5, 12.0, 15.0, 22.0, 26.0]
END_QA_LOCAL = [12, 60, 104]  # end-screen local frames: logo landing / chips+CTA / final hold


def run(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def faststart(path):
    with open(path, "rb") as f:
        head = f.read(1 << 20)
    moov, mdat = head.find(b"moov"), head.find(b"mdat")
    return moov != -1 and (mdat == -1 or moov < mdat)


def main():
    os.makedirs(os.path.dirname(RENDER), exist_ok=True)
    os.makedirs(QA, exist_ok=True)
    if "--skip-render" not in sys.argv:
        run(["npx", "remotion", "render", "src/index.ts", "Reel01", RENDER, "--muted",
             "--codec=h264", "--crf=18", "--pixel-format=yuv420p", "--concurrency=4",
             "--x264-preset=slow"], cwd=REM)

    report = {"deliverables": {}}
    for name, master in (("TrainPlex_Reel01_9x16.mp4", "music_master.wav"),
                         ("TrainPlex_Reel01_9x16_nomusic.mp4", "voice_master.wav")):
        out = os.path.join(OUT, name)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "work", "mux.py"), RENDER,
                            os.path.join(ROOT, "work", "audio", master), out],
                           capture_output=True, text=True)
        print(r.stdout[-2000:], r.stderr[-2000:])
        if r.returncode != 0:
            raise SystemExit(f"mux failed for {name}")
        p = probe(out)
        v = next(s for s in p["streams"] if s["codec_type"] == "video")
        a = next(s for s in p["streams"] if s["codec_type"] == "audio")
        # integrated loudness + true peak of the delivered file
        er = subprocess.run(["ffmpeg", "-nostats", "-i", out, "-map", "0:a", "-af", "ebur128=peak=true",
                             "-f", "null", "-"], capture_output=True, text=True).stderr
        summ = er[er.rfind("Summary:"):]
        def grab(label):
            for line in summ.splitlines():
                if line.strip().startswith(label):
                    return float(line.split(":")[1].split()[0])
        report["deliverables"][name] = {
            "video": {k: v.get(k) for k in ("codec_name", "profile", "width", "height", "pix_fmt", "r_frame_rate",
                                            "avg_frame_rate", "nb_frames", "duration", "bit_rate")},
            "audio": {k: a.get(k) for k in ("codec_name", "profile", "sample_rate", "channels", "bit_rate", "duration")},
            "format_duration": p["format"]["duration"],
            "size_bytes": int(p["format"]["size"]),
            "faststart": faststart(out),
            "integrated_lufs": grab("I:"),
            "loudness_range_lu": grab("LRA:"),
            "true_peak_dbtp": grab("Peak:"),
        }

    # Cover: the "SCROLL बंद कर!" moment from Clip 1 — rendered directly from Remotion (no re-compression).
    words = json.load(open(os.path.join(ROOT, "work", "captions.json")))
    c1 = [w for w in words if w["clip"] == 1]
    band = next(i for i, w in enumerate(c1) if w["word"].startswith("बंद"))
    cover_frame = round((c1[band]["start"] + c1[band + 1]["end"]) / 2 * FPS)
    cover_png = os.path.join(ROOT, "work", "render", "cover.png")
    run(["npx", "remotion", "still", "src/index.ts", "Reel01", cover_png, f"--frame={cover_frame}"], cwd=REM)
    run(["ffmpeg", "-v", "error", "-y", "-i", cover_png, "-q:v", "2", "-pix_fmt", "yuvj420p",
         os.path.join(OUT, "TrainPlex_Reel01_cover.jpg")])
    report["cover_frame"] = cover_frame

    # QA grabs from the delivered (music) file, frame-exact via select filter.
    final = os.path.join(OUT, "TrainPlex_Reel01_9x16.mp4")
    grabs = [(f"qa_{t:05.2f}s.png".replace(".", "_", 1).replace("_png", ".png"), round(t * FPS)) for t in QA_TIMES]
    grabs += [(f"qa_endscreen_f{lf:03d}.png", END_SCREEN_START + lf) for lf in END_QA_LOCAL]
    for fname, frame in grabs:
        run(["ffmpeg", "-v", "error", "-y", "-i", final, "-vf", f"select=eq(n\\,{frame})", "-vsync", "0",
             "-frames:v", "1", os.path.join(QA, fname)])
    report["qa_grabs"] = {f: {"frame": fr, "time_s": round(fr / FPS, 3)} for f, fr in grabs}
    json.dump(report, open(os.path.join(ROOT, "work", "render_report.json"), "w"), ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
