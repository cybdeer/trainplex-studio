# TrainPlex Reel 02 — edit pipeline report
Generated 2026-10-01 18:24 by `work/pipeline_report.py` (re-run: `powershell -ExecutionPolicy Bypass -File work\run_pipeline.ps1`).

## Deliverables
- `output/TrainPlex_Reel02_9x16.mp4` — ffprobe duration **26.866 s** (806 frames @ 30 fps)
- `output/TrainPlex_Reel02_9x16_nomusic.mp4` (voice only; identical mix while no music exists)
- `output/TrainPlex_Reel02_cover.jpg` — Remotion still of global frame 82 (2.73 s): hook slab 'POCKET MONEY खत्म?' landed, face clear, caption below the face
- `output/qa/*.png` — qa_00_50s.png (f15), qa_02_00s.png (f60), qa_04_50s.png (f135), qa_12_00s.png (f360), qa_15_00s.png (f450), qa_22_00s.png (f660), qa_26_00s.png (f780), qa_endscreen_f012.png (f713), qa_endscreen_f045.png (f746), qa_endscreen_f104.png (f805)

## Tool versions
| tool | version |
|---|---|
| python | 3.11.9 |
| ffmpeg | ffmpeg version N-124445-g22d06b39ce-20260513 Copyright (c) 2000-2026 the FFmpeg developers |
| node | v25.9.0 |
| remotion (package.json) | 4.0.529 |
| faster-whisper | 1.2.1 |
| ctranslate2 | 4.8.2 |
| whisper model | large-v3, language hi, CPU int8, word timestamps (timing only) |
| opencv | 4.12.0.88 |
| insightface | 2.0 |
| onnxruntime | 1.30.0 |
| numpy | 2.2.6 |
| scipy | 1.17.1 |
| Pillow | 12.2.0 |
| react | 19.1.0 |
| typescript | 5.8.3 |

## Edit: trims (measured, never speeding speech up)
| clip | source | source dur (s) | in (s) | out (s) | after trim (s) | frames @30 | speech on / off (s) | pre-roll / tail kept (s) | note |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 720x1280 @ 24/1 | 8.000 | 0.0000 | 7.8333 | 7.8333 | 235 | 0.00 / 7.75 | 0.00 / 0.08 | RMS onset 0.00 s (whisper first word 0.00); offset 7.75 s (whisper last word end 7.74); pre-roll kept 0.00 s; tail kept 0.08 s; tail event (click/breath) at 7.87 s excluded; source 8.000 s |
| 2 | 720x1280 @ 24/1 | 8.000 | 0.0000 | 7.7333 | 7.7333 | 232 | 0.17 / 7.54 | 0.17 / 0.19 | RMS onset 0.17 s (whisper first word 0.00); offset 7.54 s (whisper last word end 7.50); pre-roll kept 0.17 s; tail kept 0.19 s; source 8.000 s |
| 3 | 720x1280 @ 24/1 | 8.000 | 0.0000 | 7.8000 | 7.8000 | 234 | 0.10 / 7.65 | 0.10 / 0.15 | RMS onset 0.10 s (whisper first word 0.00); offset 7.65 s (whisper last word end 7.60); pre-roll kept 0.10 s; tail kept 0.15 s; tail event (click/breath) at 7.81 s excluded; source 8.000 s |

- Clips total 701 f = 23.367 s; **end screen 105 f = 3.50 s** (3.5 s preferred, legal window [90, 120] f); **total 806 f = 26.867 s**.
- Order: Clip 1 → Clip 2 → Clip 3 (hard cuts + 4-frame white flash) → 8-frame orange wipe → animated logo CTA end screen.
- Flow Scenebuilder merge trims: `work/flow_merge_trims.json` = clip1 in 0.0000 s / out 7.8333 s; clip2 in 0.0000 s / out 7.7333 s; clip3 in 0.0000 s / out 7.8000 s
- Upscale: Lanczos 720x1280 → 1080x1920, 24 → 30 fps CFR by frame repetition (audio untouched), CRF 12 intermediates.

## Captions
Exact script from `work/script.json`; whisper large-v3 supplies timing only. Alignment log (`work/captions_alignment_report.txt`):
```
clip1  Hostel         <- हॉस्टिल             0.00- 0.41  (end tightened 0.56 -> 0.41)
clip1  में            <- में                 0.47- 0.76  (start 0.56 -> 0.47: prev word's trailing pause)
clip1  सबसे           <- सब से               0.76- 1.10
clip1  पूछो —         <- पूछो                1.10- 1.44
clip1  pocket         <- पॉकेट               1.82- 2.10  (start tightened 1.44 -> 1.82)
clip1  money          <- मनी                 2.10- 2.24
clip1  कब             <- कब                  2.24- 2.44
clip1  खत्म           <- खतम                 2.52- 2.78  (start tightened 2.44 -> 2.52)
clip1  होती           <- होती                2.78- 2.96
clip1  है?            <- है                  2.96- 3.14
clip1  बीस            <- 20                  3.52- 3.60  (start tightened 3.14 -> 3.52)
clip1  तारीख          <- तारीक               3.86- 4.08  (start tightened 3.60 -> 3.86)
clip1  तक!            <- तक                  4.22- 4.36  (start tightened 4.08 -> 4.22)
clip1  मेरी           <- मेरी                4.87- 5.12  (start tightened 4.36 -> 4.87)
clip1  नहीं           <- नहीं                5.12- 5.34
clip1  होती,          <- होती                5.34- 5.54
clip1  क्योंकि        <- क्योंकि             5.86- 6.06  (start tightened 5.54 -> 5.86)
clip1  मैं            <- मैं                 6.06- 6.16
clip1  TrainPlex      <- ट्रेन प्लेक्स       6.16- 6.60
clip1  पे             <- पे                  6.60- 6.78
clip1  काम            <- काम                 6.78- 6.96
clip1  करती           <- करती                6.96- 7.28
clip1  हूँ।           <- हूँ                 7.28- 7.74
clip2  Lecture        <- लेक्चर              0.15- 0.42  (start tightened 0.00 -> 0.15)
clip2  के             <- के                  0.42- 0.58
clip2  बाद,           <- बाद                 0.58- 0.88
clip2  phone          <- फोन                 1.09- 1.24  (start tightened 0.88 -> 1.09)
clip2  से —           <- से सेंड,            1.24- 1.70
clip2  voice          <- वॉइस                1.99- 2.28  (start tightened 1.70 -> 1.99)
clip2  record,        <- रिकॉर्ड,            2.28- 2.66
clip2  photos,        <- फोटोस,              2.80- 3.18  (start tightened 2.68 -> 2.80)
clip2  text           <- टेक्स               3.31- 3.52  (start tightened 3.18 -> 3.31)
clip2  check।         <- चेक,                3.60- 3.76  (start tightened 3.52 -> 3.60)
clip2  AI             <- एयाई                4.09- 4.36  (start tightened 3.80 -> 4.09)
clip2  कंपनियों       <- कंपीनियों           4.36- 4.82
clip2  के             <- के                  4.82- 4.94
clip2  छोटे           <- छोटे                4.94- 5.20
clip2  tasks।         <- टास्क्स,            5.20- 5.46  (end tightened 5.68 -> 5.46)
clip2  कोई            <- कोई                 6.03- 6.20  (start 5.68 -> 5.66: prev word's trailing pause)  (start tightened 5.66 -> 6.03)
clip2  fees           <- फीज                 6.20- 6.46
clip2  नहीं,          <- नहीं,               6.46- 6.68
clip2  training       <- ट्रेनिंग            6.93- 7.20  (start tightened 6.68 -> 6.93)
clip2  भी             <- भी                  7.20- 7.34
clip2  free।          <- फ्री                7.43- 7.50  (start tightened 7.34 -> 7.43)
clip3  मैं            <- मैं                 0.09- 0.22  (start tightened 0.00 -> 0.09)
clip3  दिन            <- दिन                 0.22- 0.46
clip3  में            <- में                 0.46- 0.58
clip3  दो-तीन         <- दो तीन              0.58- 0.96
clip3  घंटे           <- घंटे                0.96- 1.18
clip3  काम            <- काम                 1.18- 1.42
clip3  करती           <- करती                1.42- 1.72
clip3  हूँ            <- हूँ                 1.72- 1.92
clip3  और             <- और                  2.00- 2.12  (start tightened 1.92 -> 2.00)
clip3  चार            <- 400                 2.12- 2.26
clip3  सौ             <- 400                 2.26- 2.40
clip3  से             <- से                  2.40- 2.68
clip3  पाँच           <- 500                 2.68- 2.77
clip3  सौ             <- 500                 2.77- 2.86
clip3  कमा            <- कमा                 2.86- 3.20
clip3  लेती           <- लेती                3.20- 3.52
clip3  हूँ,           <- हूँ                 3.52- 3.66
clip3  सीधे           <- सीधे                3.80- 3.96  (start tightened 3.66 -> 3.80)
clip3  Bank           <- बैंक                3.96- 4.30
clip3  या             <- या                  4.30- 4.52
clip3  UPI            <- UPI                 4.52- 4.92
clip3  में।           <- में                 4.92- 5.12
clip3  नीचे           <- नीचे                5.42- 5.64  (start tightened 5.12 -> 5.42)
clip3  Learn          <- लर्न                5.64- 5.94
clip3  more           <- मोर                 5.94- 6.10
clip3  दबाओ           <- दबाओ                6.10- 6.42
clip3  और             <- और                  6.62- 6.78  (start tightened 6.42 -> 6.62)
clip3  अभी            <- अभी                 6.78- 6.98
clip3  register       <- रेजिस्टर            6.98- 7.29  (end tightened 7.38 -> 7.29)
clip3  करो!           <- करो                 7.35- 7.60  (start 7.38 -> 7.35: prev word's trailing pause)
```

## Face tracking
- Clip 1: 235 frames, Haar detections 235, filled 0 (outliers rejected 0); face union {'x1': 178, 'y1': 250, 'x2': 954, 'y2': 1034}, eyes y {'y1': 442, 'y2': 702}, mouth y {'y1': 712, 'y2': 975}
- Clip 2: 232 frames, Haar detections 217, filled 15 (outliers rejected 1); face union {'x1': 290, 'y1': 520, 'x2': 898, 'y2': 1096}, eyes y {'y1': 648, 'y2': 889}, mouth y {'y1': 845, 'y2': 1053}
- Clip 3: 234 frames, Haar detections 230, filled 4 (outliers rejected 0); face union {'x1': 350, 'y1': 626, 'x2': 822, 'y2': 1068}, eyes y {'y1': 714, 'y2': 898}, mouth y {'y1': 848, 'y2': 1041}

## Audio
| clip | before I (LUFS) | before TP (dBTP) | sibilance indicators (ltas / svr / burst) | de-essed | gain (dB) | after I (LUFS) |
|---|---|---|---|---|---|---|
| 1 | -22.332 | -2.361 | -13.45 / -17.02 / -8.25 | no (0/3 flags) | 6.516 | -16.004 |
| 2 | -23.826 | -11.437 | -15.42 / -16.4 / -12.53 | no (0/3 flags) | 7.833 | -16.0 |
| 3 | -23.031 | -9.119 | -18.17 / -17.8 / -13.16 | no (0/3 flags) | 7.041 | -16.001 |
- Chain: 80 Hz 2nd-order HPF → sibilance test → static gain to −16 LUFS/clip → 5 ms edge fades → static gain + 4× oversampled look-ahead true-peak limiter (ceiling -1.6 dBTP, max GR 5.81 dB, GR > 1 dB 3.122 % of the time).
- Master WAV: I -14.008 LUFS, TP -1.598 dBTP, LRA 1.99 LU. loudnorm verdict: dynamic (why it is not used).
- **TrainPlex_Reel02_9x16.mp4 after AAC**: I -14.022 LUFS, TP -1.577 dBTP, LRA 1.99 LU; AAC LC 48000 Hz, faststart True.
- **TrainPlex_Reel02_9x16_nomusic.mp4 after AAC**: I -14.022 LUFS, TP -1.577 dBTP, LRA 1.99 LU; AAC LC 48000 Hz, faststart True.
- Music: absent — skipped; SFX: absent — skipped.

## Render
Remotion → H.264 High, 1080x1920, 30/1 fps, yuv420p, bt709/bt709/bt709 (tv range), CRF 18, x264 slow, PNG intermediate frames, 806 frames, 5.81 Mb/s.

## QA (work/qa/qa_results.json)
| # | check | result | key evidence |
|---|---|---|---|
| 1 | ffprobe delivery specs (1080x1920, 30 fps, H.264 High, yuv420p, BT.709, 25-30 s) | **PASS** | {"TrainPlex_Reel02_9x16.mp4": {"codec": "h264", "profile": "High", "size": "1080x1920", "r_frame_rate": "30/1", "avg_frame_rate": "30/1", "frames": 806, "pix_fmt": "yuv420p", "color_space": "bt709", "color_transfer": "bt709", "color_primaries": "bt709", "color_range": "tv", "duration_s": 26.866, "video_duration_s": 26.866, "audio": "aac LC 48000 Hz 2 ch", "aspect": "9:16", "ok": true}, "TrainPlex_… |
| 2 | loudness after AAC: -14 +/- 0.5 LUFS, TP <= -1 dBTP | **PASS** | {"TrainPlex_Reel02_9x16.mp4": {"I_lufs": -14.0, "LRA_lu": 2.0, "true_peak_dbtp": -1.6, "precise_I_lufs": -14.022, "precise_true_peak_dbtp": -1.577, "ok": true}, "TrainPlex_Reel02_9x16_nomusic.mp4": {"I_lufs": -14.0, "LRA_lu": 2.0, "true_peak_dbtp": -1.6, "precise_I_lufs": -14.022, "precise_true_peak_dbtp": -1.577, "ok": true}} |
| 3 | captions = exact script; no blank caption frames at chunk swaps | **PASS** | {"clips": {"1": {"script_match_data": true, "script_match_code_chunks": true, "chunk_block_height_px": {"Hostel में सबसे पूछो —": 116, "POCKET MONEY": 89, "कब खत्म होती है?": 110, "बीस तारीख तक!": 110, "मेरी नहीं होती,": 113, "क्योंकि मैं TrainPlex": 104, "पे काम करती हूँ।": 131}, "two_line_chunks": [], "displayed_text_matches_script_case_insensitive": true, "chunks": 7, "hard_swaps": 5, "swaps_wi… |
| 4 | no overlay pixels inside eye/mouth boxes (Haar + insightface landmarks, camera-mapped) | **PASS** | {"frames_checked": 689, "violating_frames": [], "violations_sample": [], "min_clearance_px_haar": {"1": {"eyes": 109.2, "mouth": 54.0}, "2": {"eyes": 210.5, "mouth": 57.0}, "3": {"eyes": 185.0, "mouth": 42.0}}, "frames_without_landmark_face": [], "exempt": {"join_flash_frames": [234, 235, 236, 237, 466, 467, 468, 469], "orange_wipe_frames": [697, 698, 699, 700, 701, 702, 703, 704]}} |
| 5 | every overlay inside safe zone x 60-1020, y 220-1480 | **PASS** | {"clip_frames_with_pixels_outside": [], "clip_samples": [], "endscreen_fg_frames_outside": [], "endscreen_samples": [], "safe_zone": {"x1": 60, "x2": 1020, "y1": 220, "y2": 1480}, "exempt": "progress bar rows 220-228 (full width), join flashes, orange wipe"} |
| 6 | disclaimer visible for the whole window the earnings number is shown | **PASS** | {"figure_frames_pixel": [[62, 117]], "figure_frames_code": [62, 118], "number_caption_frames": [[62, 83]], "disclaimer_fully_visible_frames": [[13, 229]], "frames_number_shown_without_full_disclaimer": [], "disclaimer_in_before_figure_frames": 49, "disclaimer_hold_after_number_s": 3.7, "strip_y": [1416, 1470], "local_frames": "clip 3 local frames (global = local + 467)"} |
| 7 | never two logos on screen at once | **PASS** | {"frames_with_2plus_logos": [], "samples": [], "frames_with_a_logo": {"clip1": [[33, 183], [186, 233]], "clip2": [[366, 465]], "clip3": [[470, 696]], "endscreen": [[704, 805]]}, "method": "connected blobs (>=120 px, alpha>100) of the logo artwork orange #FE5015 +/-14 per frame of Reel02Graphics"} |
| 8 | no black/frozen frames at joins; A/V offset <= 1 frame | **PASS** | {"joins": {"clip1->clip2": {"frames": [227, 243], "mean_luma": [108.9, 109.5, 110.2, 111.4, 112.6, 112.6, 113.5, 190.0, 245.8, 185.5, 141.2, 117.5, 118.4, 118.5, 117.8, 116.6, 116.1], "black_frames": [], "frozen_3plus": [], "ok": true}, "clip2->clip3": {"frames": [459, 475], "mean_luma": [118.8, 118.9, 118.9, 118.9, 119.0, 119.0, 119.2, 192.7, 245.6, 183.1, 137.5, 112.7, 113.1, 113.1, 113.1, 113.0… |
| 9 | face-embedding similarity vs char_01_master.png (insightface, 0.45) | **PASS** | {"reference": "flow/character/char_01_master.png", "threshold": 0.45, "ref_calibration_vs_other_sheets": {"char_02_fullbody.png": 0.776, "char_03_threequarter_left.png": 0.811, "char_04_threequarter_right.png": 0.809, "char_05_profile_left.png": 0.464, "char_06_expressions.png": 0.715}, "clips": {"1": {"frames": 235, "faces": 235, "sim_min": 0.493, "sim_p05": 0.528, "sim_median": 0.687, "sim_mean"… |

All pass: **True**

## Deviations (with reasons)
- **Clip 1 head breathing room 0.00 s** — Speech starts on the first sample of the Veo take ('Hostel' at 0.00 s); nothing can be added in front without inventing frames, so clip 1 starts at 0.00 s.
- **Clip 3 head breathing room 0.10 s** — Speech starts at 0.10 s in the source; kept all of it (target 0.15-0.25 s).
- **Clip 1 tail 0.08 s** — A loud click/burst starts at 7.87 s (-9 to -2 dBFS, after 'हूँ' ends at 7.75 s); the cut at 7.833 s (frame 235) stops before it. Speech is not cut.
- **Join flash / wipe exempt from checks 4-5** — The 4-frame white join flash and the 8-frame orange wipe are full-frame transitions, not overlays; the 8 px full-width progress bar (y 220-228) is exempt from the safe-zone x-limits, as in Reel 01.
- **Earnings caption chunk is 5 words** — 'चार सौ से पाँच सौ' is kept as one chunk (2-4 word rule) so the figure reads as one phrase, as specified in REMOTION_INPUTS.md.
- **Clip 2 extra syllable** — Whisper hears an extra word 'सेंड' (1.42-1.70 s) between 'phone से' and 'voice'. Captions follow the script; the 'से —' word spans it. Needs a human listen: if Priya really says an extra word, the take or the script line should be revisited.
- **Clip 3 CTA caption split** — 'नीचे Learn more दबाओ' rendered on TWO lines (221 px block; LEARN MORE is uppercased and x1.15) and covered the Learn-more arrow block; REMOTION_INPUTS.md requires one line there. Re-chunked as 'नीचे Learn more' | 'दबाओ और अभी' | 'register करो!' (all one line; caption text still = script).
- **Identity similarity dips** — Every frame was scored (not 8 samples): a few clip-2 frames dip below 0.45 (min 0.41, mid-turn / mid-word); per-clip medians are 0.66-0.69. Check 9 passes on median >= 0.45 and <= 5 % frames below; the flagged frames are listed in qa_results.json for a look.
- **No de-essing** — The objective sibilance test flagged 0-1 of 3 indicators per clip (rule: de-ess at >= 2), so no clip was de-essed.
- **Music / SFX** — assets/music.mp3 and assets/sfx/* are absent: _9x16.mp4 and _nomusic.mp4 carry the same voice-only mix; the music/SFX hooks in audio_mix.py are ready (drop the files in and re-run from the 'audio' stage).
- **Veo / Flow watermarks** — Source clips carry small visible AI watermarks (Veo text bottom-right, occasional sparkle); not removed or blurred, per brief. They sit below the safe zone. Consider Meta's 'AI info' label.
- **Identity model licence** — insightface buffalo_l is non-commercial research licensed: used only as an internal QA signal.

## Code fixes / changes
- `work/qa/dump_cues.ts` — Imported Reel 01 exports that no longer exist (clip1 SLAB/STAT_CARD/ZOOM, clip2 SLAB/CHIP/BADGE, clip3 faceOnScreen). Rewritten against the Reel 02 exports of clip1/cues.ts (SLAB_POS, CAL, CAL_POS, LOGO_POS…), clip1/camera.ts, clip2/cues.ts + clip2/layout.ts (TAG_POS, CHIP_POS, BADGE_POS), clip3/cues.ts (PLATE, CARD, LM_BLOCK, DISC_*, zoomAt) and layout/faceSafe.ts (TOP_MIN, LOWER_MAX, FACE_PAD); also dumps END_SCREEN_FRAMES / TOTAL / WIPE.
- `work/normalise.py` — Hard-coded Reel 01 EDIT list replaced by a measured trim (RMS + whisper anchor, tail-event guard), end-screen length choice, work/flow_merge_trims.json, BT.709 tags on the intermediates.
- `work/align_captions.py` — Reel 01 SCRIPT/SPANS/HIGHLIGHT_PHRASES replaced: script + highlights read from work/script.json, Reel 02 chunking + SPANS; pause handling now tightens a word START only when the whisper window opens on a pause and tightens the END (moving the next word's start) when the pause trails the word (the Reel 01 rule moved 'Hostel' to 0.47 s although it is spoken from 0.00 s); SPANS-vs-transcript count assert.
- `work/face_track.py` — Track every frame (was every 3rd), reject outlier detections, fill gaps from the nearest good frame, store per-frame eyes/mouth rects; UTF-8 + int JSON fix.
- `work/audio_mix.py` — END_SCREEN_FRAMES now read from edit.json (was a hard-coded 105 checked against timeline.ts); the default SFX cues are derived from the clip joins (were Reel 01 frames 229/236/506).
- `work/render.py` — npx -> npx.cmd on Windows; END_SCREEN_START / end-screen grabs derived from edit.json (was 741); cover frame from the clip-1 'खत्म' cue (Reel 01 'बंद' lookup would crash); mux --strict; colour tags in the report.
- `remotion/src/clips/Clip1.tsx, Clip2.tsx, Clip3.tsx, endscreen/EndScreen.tsx (MINIMAL FIX in the Remotion owner's code)` — QA check 5 failed on the real render: entrance/exit slides drew outside the safe zone (clip-1 hook slab sweeping in from x < 60 on f0-3 and out past x 1020 on f100-103, clip-2 tag/chips, clip-3 plate/card exits, end-screen CTA rising from y 1920 on local f29-34). Fix: each clip's graphics layer and the end-screen CTA are wrapped in an AbsoluteFill with clipPath inset to SAFE (x 60-1020, y 220-1480), so the slides now enter/leave at the safe-zone edge. No timing, position or size changed; captions, watermark and progress bar untouched.
- `work/qa/qa_reel02.py, qa_landmarks.py` — New 9-check suite for the Reel 02 spec (Reel 01 scripts kept for reference; their frame ranges were Reel 01 specific).
- `remotion/.real_stills.mjs` — New helper (gitignored) to render stills of the real data; jobs from a JSON file because PowerShell 5.1 strips quotes from native arguments.

## Manual checks still needed
- Listen: lip-sync, the clip-2 extra syllable after 'phone से', the limiter on headphones, the clip-1 tail click is gone.
- Native-reader Hindi spelling of captions and graphics; legal review of the earnings claim and disclaimer.

## Re-run when the 1080p Flow upscales arrive
Replace `clips/clip1.mp4`, `clip2.mp4`, `clip3.mp4` (same takes, same names), then:
```powershell
cd C:\TrainPlex\trainplex-studio-reel02\ads\reel02
powershell -ExecutionPolicy Bypass -File work\run_pipeline.ps1
```
