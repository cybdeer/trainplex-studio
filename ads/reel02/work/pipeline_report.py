"""Writes work/pipeline_report.md from the pipeline's own outputs (re-run after every pipeline run).

Sources: work/edit.json, work/flow_merge_trims.json, work/captions_alignment_report.txt, work/face_boxes.json,
work/audio/audio_report.json, work/render_report.json, work/qa/qa_results.json, work/qa/parts/landmarks.json,
live tool versions. Deviations and code fixes are listed in DEVIATIONS / CODE_FIXES below (plus any that
are detected from the data, e.g. a tail shorter than the breathing-room target).
"""
import datetime
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, "work")
FPS = 30


def load(*p):
    return json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))


def ver(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, shell=os.name == "nt").stdout.strip().splitlines()[0]
    except Exception as e:  # noqa: BLE001
        return f"n/a ({e})"


def pkg(name):
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:  # noqa: BLE001
        return "n/a"


def ffprobe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=nb_frames,codec_type",
                        "-of", "json", path], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


CODE_FIXES = [
    ("work/qa/dump_cues.ts", "Imported Reel 01 exports that no longer exist (clip1 SLAB/STAT_CARD/ZOOM, clip2 SLAB/CHIP/BADGE, "
     "clip3 faceOnScreen). Rewritten against the Reel 02 exports of clip1/cues.ts (SLAB_POS, CAL, CAL_POS, LOGO_POS…), "
     "clip1/camera.ts, clip2/cues.ts + clip2/layout.ts (TAG_POS, CHIP_POS, BADGE_POS), clip3/cues.ts (PLATE, CARD, LM_BLOCK, "
     "DISC_*, zoomAt) and layout/faceSafe.ts (TOP_MIN, LOWER_MAX, FACE_PAD); also dumps END_SCREEN_FRAMES / TOTAL / WIPE."),
    ("work/normalise.py", "Hard-coded Reel 01 EDIT list replaced by a measured trim (RMS + whisper anchor, tail-event guard), "
     "end-screen length choice, work/flow_merge_trims.json, BT.709 tags on the intermediates."),
    ("work/align_captions.py", "Reel 01 SCRIPT/SPANS/HIGHLIGHT_PHRASES replaced: script + highlights read from work/script.json, "
     "Reel 02 chunking + SPANS; pause handling now tightens a word START only when the whisper window opens on a pause and "
     "tightens the END (moving the next word's start) when the pause trails the word (the Reel 01 rule moved 'Hostel' to "
     "0.47 s although it is spoken from 0.00 s); SPANS-vs-transcript count assert."),
    ("work/face_track.py", "Track every frame (was every 3rd), reject outlier detections, fill gaps from the nearest good frame, "
     "store per-frame eyes/mouth rects; UTF-8 + int JSON fix."),
    ("work/audio_mix.py", "END_SCREEN_FRAMES now read from edit.json (was a hard-coded 105 checked against timeline.ts); the "
     "default SFX cues are derived from the clip joins (were Reel 01 frames 229/236/506)."),
    ("work/render.py", "npx -> npx.cmd on Windows; END_SCREEN_START / end-screen grabs derived from edit.json (was 741); cover "
     "frame from the clip-1 'खत्म' cue (Reel 01 'बंद' lookup would crash); mux --strict; colour tags in the report."),
    ("remotion/src/clips/Clip1.tsx, Clip2.tsx, Clip3.tsx, endscreen/EndScreen.tsx (MINIMAL FIX in the Remotion owner's code)",
     "QA check 5 failed on the real render: entrance/exit slides drew outside the safe zone (clip-1 hook slab sweeping in from "
     "x < 60 on f0-3 and out past x 1020 on f100-103, clip-2 tag/chips, clip-3 plate/card exits, end-screen CTA rising from "
     "y 1920 on local f29-34). Fix: each clip's graphics layer and the end-screen CTA are wrapped in an AbsoluteFill with "
     "clipPath inset to SAFE (x 60-1020, y 220-1480), so the slides now enter/leave at the safe-zone edge. No timing, "
     "position or size changed; captions, watermark and progress bar untouched."),
    ("work/qa/qa_reel02.py, qa_landmarks.py", "New 9-check suite for the Reel 02 spec (Reel 01 scripts kept for reference; their "
     "frame ranges were Reel 01 specific)."),
    ("remotion/.real_stills.mjs", "New helper (gitignored) to render stills of the real data; jobs from a JSON file because "
     "PowerShell 5.1 strips quotes from native arguments."),
]

DEVIATIONS = [
    ("Clip 1 head breathing room 0.00 s", "Speech starts on the first sample of the Veo take ('Hostel' at 0.00 s); nothing can be "
     "added in front without inventing frames, so clip 1 starts at 0.00 s."),
    ("Clip 3 head breathing room 0.10 s", "Speech starts at 0.10 s in the source; kept all of it (target 0.15-0.25 s)."),
    ("Clip 1 tail 0.08 s", "A loud click/burst starts at 7.87 s (-9 to -2 dBFS, after 'हूँ' ends at 7.75 s); the cut at 7.833 s "
     "(frame 235) stops before it. Speech is not cut."),
    ("Join flash / wipe exempt from checks 4-5", "The 4-frame white join flash and the 8-frame orange wipe are full-frame "
     "transitions, not overlays; the 8 px full-width progress bar (y 220-228) is exempt from the safe-zone x-limits, as in Reel 01."),
    ("Earnings caption chunk is 5 words", "'चार सौ से पाँच सौ' is kept as one chunk (2-4 word rule) so the figure reads as one "
     "phrase, as specified in REMOTION_INPUTS.md."),
    ("Clip 2 extra syllable", "Whisper hears an extra word 'सेंड' (1.42-1.70 s) between 'phone से' and 'voice'. Captions follow the "
     "script; the 'से —' word spans it. Needs a human listen: if Priya really says an extra word, the take or the script line "
     "should be revisited."),
    ("Clip 3 CTA caption split", "'नीचे Learn more दबाओ' rendered on TWO lines (221 px block; LEARN MORE is uppercased and "
     "x1.15) and covered the Learn-more arrow block; REMOTION_INPUTS.md requires one line there. Re-chunked as "
     "'नीचे Learn more' | 'दबाओ और अभी' | 'register करो!' (all one line; caption text still = script)."),
    ("Identity similarity dips", "Every frame was scored (not 8 samples): a few clip-2 frames dip below 0.45 (min 0.41, "
     "mid-turn / mid-word); per-clip medians are 0.66-0.69. Check 9 passes on median >= 0.45 and <= 5 % frames below; the "
     "flagged frames are listed in qa_results.json for a look."),
    ("No de-essing", "The objective sibilance test flagged 0-1 of 3 indicators per clip (rule: de-ess at >= 2), so no clip was "
     "de-essed."),
    ("Music / SFX", "assets/music.mp3 and assets/sfx/* are absent: _9x16.mp4 and _nomusic.mp4 carry the same voice-only mix; "
     "the music/SFX hooks in audio_mix.py are ready (drop the files in and re-run from the 'audio' stage)."),
    ("Veo / Flow watermarks", "Source clips carry small visible AI watermarks (Veo text bottom-right, occasional sparkle); not "
     "removed or blurred, per brief. They sit below the safe zone. Consider Meta's 'AI info' label."),
    ("Identity model licence", "insightface buffalo_l is non-commercial research licensed: used only as an internal QA signal."),
]


def main():
    edit = load("work", "edit.json")
    merge = load("work", "flow_merge_trims.json")
    audio = load("work", "audio", "audio_report.json")
    render = load("work", "render_report.json")
    qa = load("work", "qa", "qa_results.json") if os.path.exists(os.path.join(W, "qa", "qa_results.json")) else None
    faces = load("work", "face_boxes.json")
    tv = load("work", "tool_versions.json")
    final = os.path.join(ROOT, "output", "TrainPlex_Reel02_9x16.mp4")
    fp = ffprobe_duration(final)
    L = []
    a = L.append
    a("# TrainPlex Reel 02 — edit pipeline report")
    a(f"Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} by `work/pipeline_report.py` (re-run: "
      "`powershell -ExecutionPolicy Bypass -File work\\run_pipeline.ps1`).")
    a("")
    a("## Deliverables")
    a(f"- `output/TrainPlex_Reel02_9x16.mp4` — ffprobe duration **{float(fp['format']['duration']):.3f} s** "
      f"({next(s['nb_frames'] for s in fp['streams'] if s['codec_type'] == 'video')} frames @ 30 fps)")
    a("- `output/TrainPlex_Reel02_9x16_nomusic.mp4` (voice only; identical mix while no music exists)")
    a(f"- `output/TrainPlex_Reel02_cover.jpg` — Remotion still of global frame {render['cover_frame']} "
      f"({render['cover_frame'] / FPS:.2f} s): hook slab 'POCKET MONEY खत्म?' landed, face clear, caption below the face")
    a("- `output/qa/*.png` — " + ", ".join(f"{k} (f{v['frame']})" for k, v in render["qa_grabs"].items()))
    a("")
    a("## Tool versions")
    live = {
        "python": sys.version.split()[0], "ffmpeg": ver(["ffmpeg", "-version"]), "node": ver(["node", "--version"]),
        "remotion (package.json)": tv.get("remotion"), "faster-whisper": pkg("faster-whisper"), "ctranslate2": pkg("ctranslate2"),
        "whisper model": "large-v3, language hi, CPU int8, word timestamps (timing only)",
        "opencv": pkg("opencv-python") if pkg("opencv-python") != "n/a" else pkg("opencv-python-headless"),
        "insightface": pkg("insightface"), "onnxruntime": pkg("onnxruntime"), "numpy": pkg("numpy"), "scipy": pkg("scipy"),
        "Pillow": pkg("Pillow"), "react": tv.get("react"), "typescript": tv.get("typescript"),
    }
    a("| tool | version |")
    a("|---|---|")
    for k, v in live.items():
        a(f"| {k} | {v} |")
    a("")
    a("## Edit: trims (measured, never speeding speech up)")
    a("| clip | source | source dur (s) | in (s) | out (s) | after trim (s) | frames @30 | speech on / off (s) | pre-roll / tail kept (s) | note |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for c in edit["clips"]:
        m = c["measure"]
        a(f"| {c['clip']} | {m['source_width']}x{m['source_height']} @ {m['source_fps']} | {m['source_duration_s']:.3f} | "
          f"{c['trim_start']:.4f} | {c['trim_end']:.4f} | {c['duration']:.4f} | {c['frames']} | {m['onset_s']:.2f} / {m['offset_s']:.2f} | "
          f"{m['pre_roll_s']:.2f} / {m['tail_s']:.2f} | {c['note']} |")
    a("")
    a(f"- Clips total {edit['clips_total_frames']} f = {edit['clips_total_frames'] / FPS:.3f} s; **end screen "
      f"{edit['end_screen_frames']} f = {edit['end_screen_frames'] / FPS:.2f} s** (3.5 s preferred, legal window "
      f"[{max(90, 750 - edit['clips_total_frames'])}, {min(120, 900 - edit['clips_total_frames'])}] f); "
      f"**total {edit['total_frames']} f = {edit['total_s']:.3f} s**.")
    a("- Order: Clip 1 → Clip 2 → Clip 3 (hard cuts + 4-frame white flash) → 8-frame orange wipe → animated logo CTA end screen.")
    a("- Flow Scenebuilder merge trims: `work/flow_merge_trims.json` = " +
      "; ".join(f"clip{c['clip']} in {c['in_s']:.4f} s / out {c['out_s']:.4f} s" for c in merge["clips"]))
    a("- Upscale: Lanczos 720x1280 → 1080x1920, 24 → 30 fps CFR by frame repetition (audio untouched), CRF 12 intermediates.")
    a("")
    a("## Captions")
    a("Exact script from `work/script.json`; whisper large-v3 supplies timing only. Alignment log "
      "(`work/captions_alignment_report.txt`):")
    a("```")
    a(open(os.path.join(W, "captions_alignment_report.txt"), encoding="utf-8").read().rstrip())
    a("```")
    a("")
    a("## Face tracking")
    for k in ("1", "2", "3"):
        f = faces[k]
        a(f"- Clip {k}: {f['frames']} frames, Haar detections {f['detections']}, filled {f['filled_frames']} "
          f"(outliers rejected {f['rejected_outliers']}); face union {f['union_face_box']}, eyes y {f['eyes_band_union']}, "
          f"mouth y {f['mouth_band_union']}")
    a("")
    a("## Audio")
    vp = audio["voice_processing"]
    a("| clip | before I (LUFS) | before TP (dBTP) | sibilance indicators (ltas / svr / burst) | de-essed | gain (dB) | after I (LUFS) |")
    a("|---|---|---|---|---|---|---|")
    for c in vp["clips"]:
        s = c.get("sibilance", {})
        a(f"| {c['clip']} | {c['before']['precise']['I_lufs']} | {c['before']['precise']['true_peak_dbtp']} | "
          f"{s.get('ltas_ratio_db')} / {s.get('svr_p99_db')} / {s.get('burst_rel_i_db')} | {'yes' if c.get('deess', {}).get('applied') else 'no'} ({sum(bool(v) for v in (s.get('flags') or {}).values())}/3 flags) | "
          f"{c.get('gain_db')} | {c['after']['precise']['I_lufs']} |")
    vm = audio["outputs"]["voice_master"]
    a(f"- Chain: 80 Hz 2nd-order HPF → sibilance test → static gain to −16 LUFS/clip → 5 ms edge fades → static gain + "
      f"4× oversampled look-ahead true-peak limiter (ceiling {vm['limiter'].get('ceiling_dbtp')} dBTP, max GR "
      f"{vm['limiter'].get('max_gain_reduction_db')} dB, GR > 1 dB {vm['limiter'].get('pct_time_gr_over_1db')} % of the time).")
    a(f"- Master WAV: I {vm['measured']['precise']['I_lufs']} LUFS, TP {vm['measured']['precise']['true_peak_dbtp']} dBTP, "
      f"LRA {vm['measured']['precise']['LRA_lu']} LU. loudnorm verdict: {audio['mastering']['loudnorm_linear_check'].get('pass2_normalization_type')} "
      "(why it is not used).")
    for name, d in render["deliverables"].items():
        la = d["loudness_after_aac"]
        a(f"- **{name} after AAC**: I {la['precise']['I_lufs']} LUFS, TP {la['precise']['true_peak_dbtp']} dBTP, LRA {la['precise']['LRA_lu']} LU; "
          f"AAC {d['audio']['profile']} {d['audio']['sample_rate']} Hz, faststart {d['faststart']}.")
    a(f"- Music: {audio['music']['status']}; SFX: {audio['sfx']['status']}.")
    a("")
    a("## Render")
    v = render["deliverables"]["TrainPlex_Reel02_9x16.mp4"]["video"]
    a(f"Remotion → H.264 {v['profile']}, {v['width']}x{v['height']}, {v['r_frame_rate']} fps, {v['pix_fmt']}, "
      f"{v['color_space']}/{v['color_primaries']}/{v['color_transfer']} ({v['color_range']} range), CRF 18, x264 slow, PNG "
      f"intermediate frames, {v['nb_frames']} frames, {int(v['bit_rate']) / 1e6:.2f} Mb/s.")
    a("")
    a("## QA (work/qa/qa_results.json)")
    if qa:
        a("| # | check | result | key evidence |")
        a("|---|---|---|---|")
        for r in qa["checks"]:
            ev = json.dumps(r["evidence"], ensure_ascii=False)
            a(f"| {r['check']} | {r['name']} | **{r['result']}** | {ev[:400].replace('|', '/')}{'…' if len(ev) > 400 else ''} |")
        a("")
        a(f"All pass: **{qa['all_pass']}**")
    a("")
    a("## Deviations (with reasons)")
    devs = list(DEVIATIONS)
    for c in edit["clips"]:
        if not c["measure"]["breath_ok"] and not any(d[0].startswith(f"Clip {c['clip']} ") for d in devs):
            devs.append((f"Clip {c['clip']} breathing room", c["note"]))
    for t, d in devs:
        a(f"- **{t}** — {d}")
    a("")
    a("## Code fixes / changes")
    for f, d in CODE_FIXES:
        a(f"- `{f}` — {d}")
    a("")
    a("## Manual checks still needed")
    a("- Listen: lip-sync, the clip-2 extra syllable after 'phone से', the limiter on headphones, the clip-1 tail click is gone.")
    a("- Native-reader Hindi spelling of captions and graphics; legal review of the earnings claim and disclaimer.")
    a("")
    a("## Re-run when the 1080p Flow upscales arrive")
    a("Replace `clips/clip1.mp4`, `clip2.mp4`, `clip3.mp4` (same takes, same names), then:")
    a("```powershell")
    a("cd C:\\TrainPlex\\trainplex-studio-reel02\\ads\\reel02")
    a("powershell -ExecutionPolicy Bypass -File work\\run_pipeline.ps1")
    a("```")
    open(os.path.join(W, "pipeline_report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote work/pipeline_report.md")


if __name__ == "__main__":
    main()
