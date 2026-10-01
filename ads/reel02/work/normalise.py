"""STEP 2 — measure head/tail silences, trim, and normalise clips to 1080x1920 @ 30 fps CFR.

Trim points are MEASURED on every run (so a re-run on new / 1080p sources re-derives them):
  * 10 ms RMS envelope of the raw clip audio (mono, 48 kHz).
  * speech onset  = first 10 ms bin above -35 dBFS that stays above for >= 50 ms.
  * speech offset = starts at whisper's last word end (work/transcripts/clipN_raw.json, timing only)
                    and extends while the envelope stays above -35 dBFS (gaps < 40 ms bridged).
  * a "tail event" = the first burst above -35 dBFS that starts > 60 ms after the offset (Veo often
    adds a click / breath / half-syllable in the last frames). The cut never reaches into it.
  * head: keep BREATH_TARGET (0.20 s) of pre-roll where the source has it (trim_start floored to the
    30 fps grid); tail: keep up to BREATH_TARGET after the offset, stopping 10 ms before a tail event,
    floored to the 30 fps grid. Speech is never cut, never sped up (video 24->30 fps duplicates
    frames; audio is only trimmed).
  * end-screen length: 3.5 s preferred, clamped into [max(3.0 s, 25.0 s - clips), min(4.0 s, 30.0 s - clips)].

Outputs: work/norm/clipN.mp4 (1080x1920 @ 30, Lanczos, CRF 12), work/norm/clipN.wav (48 kHz/24-bit),
work/edit.json (Remotion contract), work/flow_merge_trims.json (in/out seconds per clip for the Flow
Scenebuilder merge).
"""
import json
import math
import os
import subprocess

import numpy as np

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
THR_DB = -35.0
BREATH_TARGET = 0.20
BREATH_MIN = 0.15
END_PREF, END_MIN, END_MAX = 105, 90, 120
TOTAL_MIN, TOTAL_MAX = 750, 900


def env_db(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64)
    hop = 480
    n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    return db, len(x) / 48000.0


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=duration,width,height,r_frame_rate", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)["streams"][0]


def measure(clip):
    src = os.path.join(root, "clips", f"clip{clip}.mp4")
    db, adur = env_db(src)
    vinfo = probe_duration(src)
    vdur = float(vinfo["duration"])
    dur = min(adur, vdur)
    above = db > THR_DB
    onset = next(i for i in range(len(db) - 5) if above[i:i + 5].all()) / 100.0
    tr = json.load(open(os.path.join(root, "work", "transcripts", f"clip{clip}_raw.json"), encoding="utf-8"))
    words = [w for s in tr["segments"] for w in s["words"]]
    w_first, w_last = words[0]["start"], words[-1]["end"]
    # offset: from whisper's last word end, extend while loud (bridge gaps < 40 ms)
    k = min(len(db) - 1, int(w_last * 100))
    while k > 0 and not above[k] and k > int(w_last * 100) - 15:  # whisper may overshoot into silence
        k -= 1
    gap = 0
    j = k
    while j + 1 < len(db):
        j += 1
        if above[j]:
            gap = 0
            k = j
        else:
            gap += 1
            if gap >= 4:
                break
    offset = (k + 1) / 100.0
    # next event after the offset
    event = None
    for i in range(k + 7, len(db)):
        if above[i]:
            event = i / 100.0
            break
    head_room = BREATH_TARGET
    trim_start = max(0.0, math.floor((onset - head_room) * FPS + 1e-6) / FPS)
    tail_limit = offset + BREATH_TARGET
    if event is not None:
        tail_limit = min(tail_limit, event - 0.01)
    tail_limit = min(tail_limit, dur)
    end = math.floor(tail_limit * FPS + 1e-6) / FPS
    frames = int(round((end - trim_start) * FPS))
    end = trim_start + frames / FPS
    note = (f"RMS onset {onset:.2f} s (whisper first word {w_first:.2f}); offset {offset:.2f} s (whisper last word end "
            f"{w_last:.2f}); pre-roll kept {onset - trim_start:.2f} s; tail kept {end - offset:.2f} s"
            + (f"; tail event (click/breath) at {event:.2f} s excluded" if event is not None and event < offset + BREATH_TARGET + 0.01 else "")
            + f"; source {dur:.3f} s")
    return {
        "clip": clip, "src": f"clips/clip{clip}.mp4", "trim_start": round(trim_start, 4), "frames": frames, "note": note,
        "measure": {"onset_s": onset, "offset_s": offset, "whisper_first_start": w_first, "whisper_last_end": w_last,
                    "tail_event_s": event, "pre_roll_s": round(onset - trim_start, 3), "tail_s": round(end - offset, 3),
                    "source_duration_s": round(dur, 3), "source_width": vinfo["width"], "source_height": vinfo["height"],
                    "source_fps": vinfo["r_frame_rate"],
                    "breath_ok": (onset - trim_start >= BREATH_MIN - 1e-6 or trim_start == 0.0) and end - offset >= BREATH_MIN - 1e-6},
    }


def main():
    os.makedirs(os.path.join(root, "work", "norm"), exist_ok=True)
    EDIT = [measure(c) for c in (1, 2, 3)]
    clips_total = sum(e["frames"] for e in EDIT)
    lo, hi = max(END_MIN, TOTAL_MIN - clips_total), min(END_MAX, TOTAL_MAX - clips_total)
    if lo > hi:
        raise SystemExit(f"clips total {clips_total} f ({clips_total / FPS:.2f} s): no 3-4 s end screen lands in 25-30 s")
    end_frames = min(hi, max(lo, END_PREF))
    for e in EDIT:
        ss = e["trim_start"]
        dur = e["frames"] / FPS
        end = ss + dur
        e["trim_end"] = round(end, 4)
        e["duration"] = round(dur, 4)
        out_mp4 = os.path.join(root, "work", "norm", f"clip{e['clip']}.mp4")
        out_wav = os.path.join(root, "work", "norm", f"clip{e['clip']}.wav")
        src = os.path.join(root, e["src"])
        vf = (f"trim=start={ss}:end={end + 0.2},setpts=PTS-STARTPTS,fps={FPS}:round=near,"
              "scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-frames:v", str(e["frames"]),
                        "-af", f"atrim=start={ss}:end={end},asetpts=PTS-STARTPTS",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-g", "15", "-bf", "0",
                        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                        "-r", str(FPS), "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                        "-movflags", "+faststart", out_mp4], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af",
                        f"atrim=start={ss}:end={end},asetpts=PTS-STARTPTS", "-ar", "48000", "-ac", "2",
                        "-c:a", "pcm_s24le", out_wav], check=True)
        pr = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                             "stream=width,height,r_frame_rate,nb_read_frames", "-of", "json", out_mp4],
                            capture_output=True, text=True)
        e["probe"] = json.loads(pr.stdout)["streams"][0]
        assert int(e["probe"]["nb_read_frames"]) == e["frames"], e["probe"]
        print(json.dumps(e, ensure_ascii=False))
    edit = {"fps": FPS, "end_screen_frames": end_frames, "clips_total_frames": clips_total,
            "total_frames": clips_total + end_frames, "total_s": round((clips_total + end_frames) / FPS, 4), "clips": EDIT}
    json.dump(edit, open(os.path.join(root, "work", "edit.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    merge = {
        "note": "In/out points (seconds, source clip timebase) used by the edit; match the Flow Scenebuilder merge to these. "
                "Video is 24 fps in the source; in/out values are on the 30 fps output grid.",
        "fps_out": FPS,
        "clips": [{"clip": e["clip"], "src": e["src"], "in_s": e["trim_start"], "out_s": e["trim_end"],
                   "duration_s": e["duration"], "frames_30fps": e["frames"]} for e in EDIT],
        "end_screen_s": round(end_frames / FPS, 4),
        "total_s": edit["total_s"],
    }
    json.dump(merge, open(os.path.join(root, "work", "flow_merge_trims.json"), "w", encoding="utf-8"), indent=2)
    print(f"clips {clips_total} f + end screen {end_frames} f = {clips_total + end_frames} f ({edit['total_s']} s)")


if __name__ == "__main__":
    main()
