#!/usr/bin/env python3
"""Mux a rendered H.264 video (no audio needed) with a mastered WAV -> Instagram-ready MP4, then measure it.

    python3 work/mux.py <video_without_audio.mp4> <master.wav> <out.mp4> [--bitrate 192k] [--strict]

  video : stream-copied (never re-encoded); expected to be H.264. Any audio already in it is ignored.
  audio : AAC-LC, 48 kHz, 192 kbps, stereo, padded/trimmed to EXACTLY the video duration (frames / fps),
          so a 846-frame @ 30 fps video gets exactly 1 353 600 audio samples (28.2 s).
  mp4   : -movflags +faststart (moov atom before mdat, verified afterwards).
  check : the OUTPUT file's audio is measured with ffmpeg `ebur128=peak=true` (I, LRA, TP) — i.e. after AAC.

Prints a JSON summary; returns the same dict from `mux()` when imported.
Exit code: 0 (muxed); with --strict, 2 if a check failed (TP > -1.0 dBTP, |I - (-14)| > 0.5 LU,
or audio/video durations differ by more than 1 ms).
Stdlib only (needs ffmpeg + ffprobe on PATH).
"""
import argparse
import json
import math
import re
import subprocess
import sys
from fractions import Fraction

FS = 48000
TARGET_LUFS = -14.0
MAX_TP_DBTP = -1.0


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def _probe(path, *extra):
    return json.loads(_run(["ffprobe", "-v", "error", "-of", "json", *extra, path]).stdout)


def video_info(path):
    """Codec, size, fps and the EXACT duration (frame count / frame rate) of the first video stream."""
    s = _probe(path, "-select_streams", "v:0", "-show_streams")["streams"][0]
    fps = Fraction(s["r_frame_rate"])
    frames = int(s["nb_frames"]) if s.get("nb_frames", "N/A") not in ("N/A", "0") else None
    if frames is None:  # containers without a frame count: count packets (no decode)
        c = _probe(path, "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets")
        frames = int(c["streams"][0]["nb_read_packets"])
    return {"codec": s["codec_name"], "width": s["width"], "height": s["height"], "fps": str(fps),
            "frames": frames, "duration_exact": frames / fps}


def audio_samples(path):
    s = _probe(path, "-select_streams", "a:0", "-show_streams")["streams"][0]
    n = int(s["duration_ts"]) if s.get("duration_ts") not in (None, "N/A") else round(float(s["duration"]) * FS)
    return {"codec": s["codec_name"], "sample_rate": int(s["sample_rate"]), "channels": s["channels"],
            "samples": n, "seconds": n / int(s["sample_rate"])}


def top_level_atoms(path):
    """Order of the top-level MP4 boxes (to verify faststart: 'moov' must precede 'mdat')."""
    atoms = []
    with open(path, "rb") as f:
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            size, kind = int.from_bytes(hdr[:4], "big"), hdr[4:].decode("latin-1")
            if size == 1:
                size = int.from_bytes(f.read(8), "big")
                f.seek(size - 16, 1)
            elif size == 0:
                atoms.append(kind)
                break
            else:
                f.seek(size - 8, 1)
            atoms.append(kind)
    return atoms


def measure_loudness(path):
    """ffmpeg ebur128 on the first audio stream: printed summary + 3-decimal values from the metadata."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", path, "-map", "0:a:0",
                        "-af", "ebur128=peak=true+sample:metadata=1,ametadata=mode=print:file=-",
                        "-f", "null", "-"], capture_output=True, text=True, check=True)
    summ = p.stderr[p.stderr.rfind("Summary:"):]
    num = r"(-?inf|-?\d+(?:\.\d+)?)"

    def grab(pat):
        m = re.search(pat, summ, re.S)
        return None if not m else float(m.group(1))

    def last(key):
        v = re.findall(r"^lavfi\.r128\." + re.escape(key) + r"=(\S+)$", p.stdout, re.M)
        return float(v[-1]) if v else None

    tp_lin, sp_lin = last("true_peak"), last("sample_peak")
    return {
        "I_lufs": grab(r"I:\s+" + num + r" LUFS"),
        "LRA_lu": grab(r"LRA:\s+" + num + r" LU"),
        "true_peak_dbtp": grab(r"True peak:\s+Peak:\s+" + num),
        "sample_peak_dbfs": grab(r"Sample peak:\s+Peak:\s+" + num),
        "precise": {"I_lufs": last("I"), "LRA_lu": last("LRA"),
                    "true_peak_dbtp": round(20 * math.log10(tp_lin), 3) if tp_lin else None,
                    "sample_peak_dbfs": round(20 * math.log10(sp_lin), 3) if sp_lin else None},
    }


def mux(video, audio, out, bitrate="192k"):
    vi = video_info(video)
    ai = audio_samples(audio)
    n = int(round(vi["duration_exact"] * FS))           # exact audio length = video length
    warnings = []
    if vi["codec"] != "h264":
        warnings.append(f"video codec is {vi['codec']}, not h264 (stream is still copied as-is)")
    if abs(ai["seconds"] - float(vi["duration_exact"])) > 1 / 30:
        warnings.append(f"master is {ai['seconds']:.4f} s but video is {float(vi['duration_exact']):.4f} s "
                        f"(audio padded/trimmed to the video)")
    af = f"aresample={FS},apad=whole_len={n},atrim=end_sample={n}"
    _run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", video, "-i", audio,
          "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
          "-af", af, "-c:a", "aac", "-profile:a", "aac_low", "-b:a", bitrate, "-ar", str(FS), "-ac", "2",
          "-movflags", "+faststart", out])

    streams = _probe(out, "-show_streams", "-show_format")
    v = next(s for s in streams["streams"] if s["codec_type"] == "video")
    a = next(s for s in streams["streams"] if s["codec_type"] == "audio")
    atoms = top_level_atoms(out)
    faststart = "moov" in atoms and "mdat" in atoms and atoms.index("moov") < atoms.index("mdat")
    res = {
        "output": out,
        "video": {"codec": v["codec_name"], "size": f"{v['width']}x{v['height']}", "fps": v["r_frame_rate"],
                  "frames": int(v.get("nb_frames", 0)), "duration_s": float(v["duration"]),
                  "copied_from": video},
        "audio": {"codec": a["codec_name"], "profile": a.get("profile"), "sample_rate": int(a["sample_rate"]),
                  "channels": a["channels"], "bit_rate": int(a.get("bit_rate", 0)),
                  "duration_s": float(a["duration"]), "target_samples": n, "master": audio,
                  "master_samples": ai["samples"]},
        "container": {"duration_s": float(streams["format"]["duration"]), "faststart": faststart,
                      "top_level_atoms": atoms},
        "loudness_after_aac": measure_loudness(out),
    }
    if not faststart:
        warnings.append("moov atom is not before mdat (faststart failed)")
    if abs(res["audio"]["duration_s"] - res["video"]["duration_s"]) > 0.001:
        warnings.append(f"audio {res['audio']['duration_s']} s vs video {res['video']['duration_s']} s")
    L = res["loudness_after_aac"]
    tp = L["precise"]["true_peak_dbtp"] if L["precise"]["true_peak_dbtp"] is not None else L["true_peak_dbtp"]
    if tp is not None and tp > MAX_TP_DBTP:
        warnings.append(f"true peak after AAC {tp} dBTP > {MAX_TP_DBTP}")
    if L["I_lufs"] is not None and abs(L["I_lufs"] - TARGET_LUFS) > 0.5:
        warnings.append(f"integrated loudness {L['I_lufs']} LUFS is off the {TARGET_LUFS} target")
    res["warnings"] = warnings
    return res


def main():
    ap = argparse.ArgumentParser(description="Mux H.264 video + mastered WAV -> AAC MP4 and measure loudness")
    ap.add_argument("video")
    ap.add_argument("master")
    ap.add_argument("out")
    ap.add_argument("--bitrate", default="192k")
    ap.add_argument("--strict", action="store_true", help="exit 2 if any check fails")
    a = ap.parse_args()
    res = mux(a.video, a.master, a.out, a.bitrate)
    print(json.dumps(res, indent=1))
    L = res["loudness_after_aac"]
    print(f"{a.out}: I {L['I_lufs']} LUFS ({L['precise']['I_lufs']}), LRA {L['LRA_lu']} LU, "
          f"TP {L['true_peak_dbtp']} dBTP ({L['precise']['true_peak_dbtp']}), "
          f"duration a/v {res['audio']['duration_s']}/{res['video']['duration_s']} s, "
          f"faststart {res['container']['faststart']}" + ("" if not res["warnings"] else
                                                          f"  WARNINGS: {res['warnings']}"), file=sys.stderr)
    return 2 if (a.strict and res["warnings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
