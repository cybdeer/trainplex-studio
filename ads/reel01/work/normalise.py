"""STEP 2 — trim leading/trailing silence and normalise clips to 1080x1920 @ 30 fps CFR.

Trim points come from a 10 ms RMS analysis (see COMPLETION_REPORT.md): speech onset/offset is
where RMS crosses -35 dBFS; we keep ~0.07 s pre-roll and ~0.08-0.18 s tail so speech is never
cut, and join gaps stay <= 0.25 s. All in/out points are snapped to the 30 fps grid.
"""
import json, os, subprocess
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
# (clip, trim_start_s, frames) — frames are at 30 fps
EDIT = [
    {"clip": 1, "src": "clips/clip1.mp4", "trim_start": 0.0, "frames": 229,
     "note": "onset 0.15 s (lead-in < 0.15 s of silence, kept); offset 7.56 s; tail after 7.633 s removed"},
    {"clip": 2, "src": "clips/clip2.mp4", "trim_start": 0.2, "frames": 277,
     "note": "0.27 s leading silence -> trimmed 0.20 s; offset 9.27 s (decay to 9.43 s); 0.57 s trailing silence removed"},
    {"clip": 3, "src": "clips/clip3.mp4", "trim_start": 0.0, "frames": 235,
     "note": "speech from 0.00 s; 'कर!' ends 7.76 s; cut at 7.833 s removes a clipped syllable/click at 7.92 s"},
]
os.makedirs(os.path.join(root, "work", "norm"), exist_ok=True)
for e in EDIT:
    ss = e["trim_start"]; dur = e["frames"] / FPS; end = ss + dur
    e["trim_end"] = round(end, 4); e["duration"] = round(dur, 4)
    out_mp4 = os.path.join(root, "work", "norm", f"clip{e['clip']}.mp4")
    out_wav = os.path.join(root, "work", "norm", f"clip{e['clip']}.wav")
    src = os.path.join(root, e["src"])
    vf = (f"trim=start={ss}:end={end + 0.2},setpts=PTS-STARTPTS,fps={FPS}:round=near,"
          "scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-frames:v", str(e["frames"]),
                    "-af", f"atrim=start={ss}:end={end},asetpts=PTS-STARTPTS",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-g", "15", "-bf", "0",
                    "-r", str(FPS), "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-movflags", "+faststart", out_mp4], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af",
                    f"atrim=start={ss}:end={end},asetpts=PTS-STARTPTS", "-ar", "48000", "-ac", "2",
                    "-c:a", "pcm_s24le", out_wav], check=True)
    pr = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                         "stream=width,height,r_frame_rate,nb_read_frames", "-of", "json", out_mp4],
                        capture_output=True, text=True)
    e["probe"] = json.loads(pr.stdout)["streams"][0]
    print(e)
json.dump({"fps": FPS, "clips": EDIT}, open(os.path.join(root, "work", "edit.json"), "w"), ensure_ascii=False, indent=2)
