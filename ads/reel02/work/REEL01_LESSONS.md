# Reel 01 → Reel 02: lessons, architecture map, pipeline

Sources: `ads/reel01/output/COMPLETION_REPORT.md`, `ads/reel01/work/qa/QA_NOTES.md`, `ads/reel01/work/AGENT_BRIEF.md`,
`ads/reel01/.gitignore`, and the code in `ads/reel01/remotion` and `ads/reel01/work`. `ads/reel02/` is a copy of Reel 01
with every `Reel01`/`reel01` identifier renamed to `Reel02`/`reel02`. Reel 01 footage, renders and data were not copied.

---

## 1. Lessons, fixes and deviations to carry over

### Footage and edit
1. **Source clips were shorter than the brief assumed.** Veo clips were 8 / 10 / 8 s at 720x1280 @ 24 fps, so the reel came
   out at 28.2 s, under the 30–34 s target. Speech can't be stretched and silence can't be padded, so plan the Reel 02 takes
   to be long enough (about 8.5–10 s of speech per clip) if 30–34 s is required.
2. **Normalise to 1080x1920 @ 30 fps CFR** using a Lanczos upscale, `setsar=1`, yuv420p and CRF 12 intermediates. Snap all
   in/out points to the 30 fps grid.
3. **Silence trim:** use 10 ms RMS analysis with onset/offset at −35 dBFS. Keep about 0.07 s pre-roll and 0.08–0.18 s of tail.
   Never cut speech. Keep join gaps ≤ 0.25 s (Reel 01 had about 0.14 and 0.16 s). Look for clipped syllables or clicks at clip
   tails: Reel 01 clip 3 had one at 7.92 s, which was cut off.
4. **AI watermarks in the source:** clips 1–2 had a ✦ sparkle at about x 865–935, y 1705–1775, and clip 3 had "Veo" at about
   x 1025–1055, y 1883–1896. Both sit below the safe zone. They were **not** cropped, to protect the face. Report them, and
   consider Meta's "AI info" label.
5. **Lip-sync:** the edit never changes timing. Check the generator's lip-sync quality yourself.
6. **Identify clips by content and transcript**, not by upload order. Reel 01 had to re-map uploaded files to clip 1/2/3.

### Transcription and captions
7. **Whisper (faster-whisper large-v3, `hi`, word timestamps, CPU int8) is used for TIMING ONLY.** Caption text is the exact
   script. Whisper misheard "स्क्रोल", "ट्रेन प्लेक्स", "500/600" and "जीरो", so the script's words were substituted. A 100 %
   script-match assert is in `align_captions.py`. Expect the same for Reel 02: "TrainPlex" → "ट्रेन प्लेक्स", "UPI", and the
   numbers पाँच सौ / छह सौ / बीस.
8. **Token→whisper-word mapping (`SPANS`)** is hand-written per clip. It has to handle 1→2 merges (TrainPlex = ट्रेन+प्लेक्स)
   and proportional splits (one "500" token → पाँच + सौ). Redo it for the Reel 02 transcripts.
9. **Pause-swallowing word starts** are tightened with a 10 ms RMS onset search: a ≥ 100 ms run below −35 dBFS inside the
   word window moves the start forward.
10. **Interpolation fallback** for missing or inverted word timings is in the code.
11. **Chunks are 2–4 words and break at punctuation.** Exceptions are allowed for punch words ("Zero!" was 1 word) and to keep a
    chunk on one line and away from the mouth. Chunk breaks are written by hand as `|` in `SCRIPT`.
12. **Caption style:** weight 900, auto-fit 78–92 px per chunk, white with a 5 px navy outline outside the glyph (an under-layer
    with a 10 px stroke plus a fill layer on top, so Devanagari conjuncts show no seams), max 900 px wide, max 2 lines.
    Active word pops 1.0 → 1.12 → 1.0, and the neighbouring words move aside so they don't collide.
13. **Highlights:** orange at 1.15x, Latin words uppercased, **except "TrainPlex", which is never re-cased** (`KEEP_CASE` in
    `chunks.ts`).
14. **QA FIX: 1-frame caption blink at hard swaps.** It happened at 21 places. Fix: the fade-in starts one frame early
    (`interpolate(local, [-1, ENTER_FRAMES-1], …)` in `Captions.tsx`). The fix is already in the copied code. Keep it.
15. **Caption sync tolerance is ±2 frames.** Chunks appear at word start −1 to −2 frames (`LEAD_FRAMES = 2`). Words with weak
    voicing (Reel 01 "और") can read about 3 frames early, so spot-check them.
16. **Danda after uppercase Latin** ("FREE।") sits visibly far from the word. This is cosmetic and was not fixed. Consider a
    narrower danda special case.
17. **Caption block bottom is at y 1400.** In clip 3 it rises to y 1290 from the CTA phrase onward, so the LEARN MORE block fits
    at y 1310–1478.

### Brand, layout and face rule
18. **Brand palette only:** cream #FAF7F2, navy #1A1A5E, orange #FF6B35, white #FFFFFF, border/grid #E8E3DA. QA measured
    99.88 % in-palette. Flat fills, `borderRadius: 0`, no gradients or shadows. A 4–6 px navy text outline over video is allowed.
19. **No emoji glyphs**, because they render in non-brand colours. Use lucide icons in brand colours (✋→Hand, 📱→Smartphone,
    🎙→Mic).
20. **Fonts are self-hosted woff2** (Inter + Noto Sans Devanagari at 600/700/800/900) in `remotion/public/fonts`, split by
    `unicode-range`. **The Inter subset has no U+2192 "→"**, so use the lucide ArrowRight icon instead.
21. **Motion:** snappy springs (damping 12–14, stiffness 180–220), 6–10 frame entrances, no fade longer than 12 frames.
    Exceptions were damping 27 for the clip 3 video punch-in and 24 for the BANK card. A brand spring overshoot dipped the
    zoom below 100 %, which showed black edges, and pushed the card into the watermark. Camera moves need near-critical
    damping with `overshootClamping`.
22. **Safe zone:** x 60–1020, y 220–1480. The progress bar takes y 220–228, so graphics start at y ≥ 232.
23. **HARD RULE: no graphic may cover the eyes or mouth while the presenter speaks.** `face_track.py` (OpenCV Haar, every 3rd
    frame) writes `face_boxes.json`, and `faceAt()` derives conservative eyes/mouth rects. Several spec positions had to move:
    clip 2 chips to x 716–1020, y 702–996; badges to y 964–1178; the clip 3 plate to y 289–549. Expect to re-place graphics
    for the Reel 02 face. **Derive positions from `faceAt` and do not hard-code them.**
24. **Face rects must be mapped through the camera transform** (punch-in and shake) before checking clearance. QA does this
    through `cues_dump.json`.
25. **The logo is a stacked lockup** (862x956 transparent crop, height ≈ 1.109 × width). Spec sizes were too big: the clip 1
    hero went 360 → 265 px (it would have covered the eyes) and the end screen went 620 → 420 px (it hit the headline).
    Size the logo from the available space, the way `LOGO_WIDTH` in clip 1 is computed.
26. **Logo must not be altered.** `make_logo_alpha.py` only made the white background and small counters transparent, with an
    edge alpha solved against white (SSIM 0.998). Use the logo files from `logo/` (already copied, together with
    `remotion/public/trainplex_logo_transparent.png`). The asset caveats still apply: the source is only 300x300 (soft at
    420 px), its orange is #FE5015 rather than #FF6B35, and the artwork reads "Train Plex". In **text**, always write "TrainPlex".
27. **Watermark (x 60, y 240, 200 px, 85 %) sits on a cream plate**, because the navy wordmark was illegible over hair. It
    **ducks out** (4-frame fade) when a clip graphic overlaps `WATERMARK_BOX`, using `CLIPn_WATERMARK_BLOCKED` intervals.
    QA FIX: in clip 1 it also hands off to the hero logo plate (`[LOGO.inAt, CLIP1_END]`), so two logos never show together.
    Because of this, its first appearance slipped from 1.0 s to about 1.87 s.
28. **End screen:** cream background, 8 % grid (barely visible), navy 18° wedge, 12 px orange bar, logo spring 0.85 → 1.0 with a
    220x10 underline. Chips sit in 2+1 rows, because one row would be 1430 px. The CTA is 53 px instead of 58 px so it fits
    the safe zone when it pulses. "Learn more" is cream on the navy wedge. Do not invent taglines, phone numbers or figures.
29. **Orange wipe is 8 frames centred on the cut** (4 frames cover, 4 frames reveal). Joins use a 4-frame white flash at
    frames cut−1 … cut+2.

### Disclaimer (mandatory for the earning figure)
30. The disclaimer must be on screen **for every frame the ₹ figure shows, plus at least 1 s**. Reel 01 held it 1.73 s after
    the figure. It sits on a text-hugging 70 % navy strip at y 1416–1470, in 30 px / weight 600 white, with contrast ≥ 8.9:1
    and a 5-frame wipe in and out. Timing is derived as `DISC_IN = PLATE_IN − 6` and
    `DISC_GONE = max(CTA phrase start, PLATE_GONE + 30 + 5)`. The earning claim still needs legal/compliance review.

    Disclaimer text, verbatim from `remotion/src/clips/clip3/Disclaimer.tsx`:

    ```ts
    export const DISCLAIMER_TEXT = '*कमाई task availability और approval पर निर्भर है';
    ```

### Audio
31. **Per-clip chain:** 80 Hz high-pass (2nd-order Butterworth) → objective sibilance test (3 indicators; de-ess only when
    2 or more flag; split-band above 5 kHz, max 4 dB) → static gain to −16 LUFS per clip → 5 ms edge fades. Reel 01 clips
    measured −14.35 / −16.45 / −18.06 LUFS before processing, and only clip 3 was de-essed.
32. **Master:** −14.0 LUFS integrated and TP −1.5 dBTP, measured after AAC. **Don't use `loudnorm` two-pass.** It quietly
    switches to dynamic AGC mode when peaks would pass the ceiling. Use static gain plus a 4x-oversampled look-ahead
    true-peak limiter, iterated (max gain reduction was 3.7 dB). Listen once on headphones.
33. **Music and SFX were absent**, so `_9x16.mp4` and `_nomusic.mp4` were byte-identical and the end screen was silent. Ducking
    code is ready (bed −20, duck −26, end −14 dB, attack 150 ms, release 300 ms, fade-out 0.5 s). Put assets in `assets/music.mp3`
    and `assets/sfx/{whoosh,pop,ding}.wav`. End-screen CTA landing frame is `CTA_LAND_FRAME = 57` (for the ding).
34. **Video is rendered muted.** Audio is muxed afterwards by `mux.py`, padded or trimmed to exactly frames/fps × 48000 samples.

### Render and delivery
35. **Render with PNG frames + BT.709.** JPEG frames made FFmpeg emit full-range yuvj420p. Settings: H.264 High, CRF 18,
    yuv420p, `--x264-preset=slow`, concurrency 4 (about 2.5 min). AAC-LC 48 kHz 192k with `+faststart`, verified by atom
    order. The average audio bitrate reads about 170 kbps because of the silent end screen; this is expected.
36. **Cover** = a frame rendered straight from Remotion (no re-compression), saved as JPG q2.
37. **QA grabs** are taken frame-exact from the delivered MP4 with `select=eq(n,N)`.

### Process, environment and repo hygiene
38. **Reel 01 ran on Linux.** On Windows, carry these over:
    - Remove or ignore the Linux browser path in `remotion.config.ts`. It's already guarded by `process.platform === 'linux'`.
      Remotion downloads Chrome Headless Shell on the first bundle; this was verified here.
    - **`python` on PATH is NOT the project interpreter.** It resolves to a hermes-agent venv. Always call
      `C:\Users\DESKTOP\AppData\Local\Programs\Python\Python311\python.exe`.
    - **Set `$env:PYTHONUTF8 = "1"`** before running any script. The scripts use `open()` without `encoding=` (49 call
      sites), and Windows defaults to cp1252, which breaks Devanagari JSON reads and writes.
    - **`render.py` calls `subprocess.run(["npx", …])`.** On Windows `npx` is `npx.cmd`, so this needs `shell=True` or
      `"npx.cmd"`.
    - **OpenCV 5.x ships without the Haar cascade XMLs.** `face_track.py` and `qa_face_verify.py` need them, so OpenCV is
      pinned to **4.12.0.88** here.
39. **Every cue is derived from `captions.json`** through `findPhrase(clip, phrase, occurrence)` and `wordsOf(clip)`. Seconds
    are never hard-coded. `findPhrase` **throws** when a phrase is missing, so a script change fails loudly at bundle time.
40. **Preview compositions** (`Clip1/2/3`, `EndScreen`, `OrangeWipe`, `Reel02Graphics`) are used to check stills. Render stills,
    not full videos, during iteration.
41. **QA uses the real code.** `dump_cues.ts` is bundled with esbuild (`run_dump.mjs`) so the Python checks use the same
    timing, camera and face values as the render. QA entry: `work/qa/remotion_qa/index.tsx` (Cap1–3, EndScreenFG).
42. **Gitignore bug:** in Reel 01, `work/qa/*/` also ignored `remotion_qa/` and `parts/`. Negations were added. The
    Reel 02 `.gitignore` keeps the `!work/qa/remotion_qa/` negation.
43. **Agent swarm:** run independent overlay work (captions, clip 1/2/3, end screen, audio, QA) as parallel subagents. Each
    agent owns its files only. Shared files (`brand.ts`, `timeline.ts`, `fonts.ts`, `primitives.tsx`, `VideoLayer.tsx`,
    `Reel.tsx`, `Root.tsx`, `GlobalOverlays.tsx`) belong to the orchestrator. Steps that depend on each other (setup → normalise →
    transcribe → align → scaffold → render) are sequential.
44. **Manual checks still needed after build:** native-reader Hindi spelling (nukta, chandrabindu: पाँच, हूँ, …), lip-sync,
    the earning-claim legal review, the limiter by ear, and the closest face clearances (Reel 01: 10–12 px).
45. **Face-embedding check (new for Reel 02, check #9), smoke test on Reel 01 frames:** with insightface buffalo_l, the same
    Reel 01 presenter scored cosine **0.73** between clips 1 and 2, but only **0.51–0.54** against clip 3. Generated
    characters drift between clips, so calibrate the pass threshold on the chosen Reel 02 character references
    (`flow/character/*.png`) before trusting it. Note that the buffalo_l model pack is licensed for non-commercial research
    use. Use it only as an internal QA signal and don't ship it.

---

## 2. Architecture map

### Remotion (`remotion/`, entry `src/index.ts` → `RemotionRoot`)
| File | Role |
|---|---|
| `src/brand.ts` | Brand constants: `COLORS`, `FONT_STACK`, `CANVAS`, `SAFE` (60–1020 × 220–1480), `CAPTION_ZONE`, springs `SPRING`/`SPRING_OVERSHOOT`/`SPRING_FIRM`, `ENTRANCE_FRAMES = 8`, `MAX_FADE_FRAMES = 12`, `SLAB_ROTATION_DEG = −4`, `LOGO_FILE`, `LOGO_ASPECT = 862/956`. Never add colours. |
| `src/fonts.ts` | `loadBrandFonts()`: registers 16 self-hosted woff2 FontFaces (Inter latin/latin-ext and Noto Devanagari devanagari/latin, weights 600–900) with `unicode-range`, wrapped in `delayRender`. |
| `src/timeline.ts` | EDL: `FPS = 30`, `CLIP_FRAMES` (from `data/edit.json`), `CLIP_START`, `END_SCREEN_START`, `END_SCREEN_FRAMES = 105`, `TOTAL_FRAMES`, `WIPE_FRAMES = 8`, `WIPE_START`. Captions: `wordsOf(clip)`, `findPhrase(clip, phrase, occ)`, `stripPunct`. Face: `faceAt(clip, frame)` → face/eyes/mouth rects (from `data/face_boxes.json`), `rectsOverlap`, `WATERMARK_BOX`, `FrameInterval`. |
| `src/Root.tsx` | Compositions `Reel02` (full), `Reel02Graphics` (video hidden, for QA), `Clip1`/`Clip2`/`Clip3` (clip + captions), `EndScreen`, `OrangeWipe`. 1080x1920 @ 30. |
| `src/Reel.tsx` | Master sequence: clips 1–3 (each with its captions) → global overlays → end screen → orange wipe. |
| `src/components/primitives.tsx` | `useSpringIn`, `<Logo width>` (real PNG, aspect locked), `logoHeightFor`, `SquareBullet`, `WhiteCard`, `OrangeBadge` (−4°), `brandText`. |
| `src/components/VideoLayer.tsx` | Full-bleed muted `OffthreadVideo` of `public/clips/clipN.mp4` with `scale`/`dx`/`dy`/`originY` for zoom and shake. `HideVideoContext` hides video for QA. |
| `src/captions/Captions.tsx` | Kinetic captions per clip: font-ready gate, `ChunkView` (spring slide, early fade-in fix, exit fade/swap), `Word` (navy under-stroke plus fill), active-word pop, clip 3 raise to y 1290 from `findPhrase(3,'तो नीचे')`. |
| `src/captions/chunks.ts` | Pure chunk timing (`buildChunks`: appear/fade/hide, swap vs fade into pauses) and display rules (`displayText`: uppercase Latin highlights except `KEEP_CASE` TrainPlex). Usable from Node for QA. |
| `src/captions/fit.ts` | Canvas text measurement plus `fitChunk` (largest size from 78–92 px on one line within 900 px, else a balanced 2-line split). |
| `src/global/GlobalOverlays.tsx` | `ProgressBar` (y 220, 8 px), `Watermark` (cream plate, ducks on `CLIPn_WATERMARK_BLOCKED`), `JoinFlash` (4-frame white flash at each cut). |
| `src/transitions/OrangeWipe.tsx` | 8-frame left→right orange wipe with a 28 px navy leading/trailing edge bar. |
| `src/endscreen/EndScreen.tsx` + `geometry.ts` | Animated CTA end screen (cream, grid, wedge, logo spring, headline, sub line, chips, CTA bar with pulse, Learn more arrow). Geometry constants live in `geometry.ts`. Exports `CTA_LAND_FRAME`. |
| `src/clips/Clip1.tsx` + `clip1/*` | `cues.ts` (all cue frames from `findPhrase`; slab, card, zoom, logo-plate sizing from the face), `camera.ts` (shake + punch-in), `HookSlab.tsx`, `StatCard.tsx`, `LogoPlate.tsx`. |
| `src/clips/Clip2.tsx` + `clip2/*` | `cues.ts`, `layout.ts` (face-calibrated positions), `TaskSlab.tsx`, `TaskChips.tsx`, `PerkBadges.tsx`. |
| `src/clips/Clip3.tsx` + `clip3/*` | `cues.ts` (figure/plate/zoom/disclaimer/LEARN MORE timing and face-derived placement, `toScreen`, `faceOnScreen`), `EarningPlate.tsx`, `PayoutCard.tsx`, **`Disclaimer.tsx`**, `LearnMore.tsx`, `FaceDebug.tsx` (debug overlay). |
| `src/data/{captions,edit,face_boxes}.json` | Copies of `work/*.json` that the bundle imports. **They currently hold Reel 01 placeholder data** so the project compiles; replace them with Reel 02 outputs. |
| `public/fonts/*.woff2`, `public/trainplex_logo_transparent.png` | Static assets. `public/clips/clipN.mp4` (gitignored) = normalised clips. |

### Python pipeline (`work/`)
| Script | Reads | Writes |
|---|---|---|
| `normalise.py` | `clips/clip{1,2,3}.mp4` and the hard-coded `EDIT` list (`trim_start`, `frames`, `note` per clip) | `work/norm/clipN.mp4` (1080x1920 @ 30, CRF 12, AAC 256k), `work/norm/clipN.wav` (48 kHz/24-bit stereo), `work/edit.json` = `{"fps":30,"clips":[{"clip","src","trim_start","frames","note","trim_end","duration","probe":{width,height,r_frame_rate,nb_read_frames}}]}` |
| `transcribe.py` | `clips/clipN.mp4` (raw, untrimmed) | `work/transcripts/clipN_16k.wav`, `work/transcripts/clipN_raw.json` = `{"clip","language","duration","segments":[{"start","end","text","words":[{"word","start","end","prob"}]}]}` |
| `align_captions.py` | `work/edit.json`, `work/transcripts/clipN_raw.json` + `_16k.wav`, hard-coded `SCRIPT` / `SPANS` / `HIGHLIGHT_PHRASES` | `work/captions.json` = `[{"word","start","end","clip","highlight","chunk"}]` (seconds relative to the TRIMMED clip, exact script spelling with punctuation), `work/captions_alignment_report.txt` |
| `make_logo_alpha.py` | `logo/trainplex_logo_source.png` | `logo/trainplex_logo_transparent.png`, `remotion/public/trainplex_logo_transparent.png`, `work/logo_preview_on_{navy,cream}.png`. Already done; reuse the outputs. |
| `face_track.py` | `work/norm/clipN.mp4` | `work/face_boxes.json` = `{"<clip>":{"frames","detections","union_face_box":{x1,y1,x2,y2},"eyes_band_union":{y1,y2},"mouth_band_union":{y1,y2},"boxes":[{"frame","x","y","w","h"}]}}` (every 3rd frame, 1080x1920 px) |
| `audio_mix.py` | `work/edit.json`, `work/norm/clipN.wav`, `work/captions.json` (only with music), optional `assets/music.mp3`, `assets/sfx/{whoosh,pop,ding}.*`, `work/audio/sfx_cues.json` (`[{"sfx","frame"}|{"sfx","t"}]`) | `work/audio/voice_master.wav`, `work/audio/music_master.wav`, `work/audio/audio_report.json`. Flags: `--music --sfx-dir --cues --skip-aac-check --out-dir` |
| `mux.py` | `<video.mp4> <master.wav> <out.mp4> [--bitrate 192k] [--strict]` | MP4 (stream-copied video, AAC padded or trimmed to the exact video length, faststart) plus a JSON loudness/spec report on stdout. With `--strict` it exits 2 on failure. |
| `render.py` | Remotion project, `work/audio/{music,voice}_master.wav`, `work/captions.json` | `work/render/reel02_video_muted.mp4`, `output/TrainPlex_Reel02_9x16.mp4`, `output/TrainPlex_Reel02_9x16_nomusic.mp4`, `output/TrainPlex_Reel02_cover.jpg`, `output/qa/qa_*.png`, `work/render_report.json`. `--skip-render` re-muxes only. |
| `script.json` (new) | — | Exact Reel 02 script (clip1/2/3) plus highlight phrases. This is the single source for alignment. |

### QA (`work/qa/`)
| File | Check |
|---|---|
| `remotion_qa/index.tsx` | QA-only entry: `Cap1/2/3` (captions only), `EndScreenFG` (end screen with backgrounds hidden). |
| `dump_cues.ts` + `run_dump.mjs` | Evaluates the real timeline, chunks, camera, cue and geometry code in Node and writes `cues_dump.json`. |
| `qa_frames.py` | #3 safe zone, #4 eyes/mouth clearance, #8 brand colours (on `work/qa/g/fNNN.png` = `Reel02Graphics` RGBA sequence). |
| `qa_shaping.py` | #1 HarfBuzz shaping of every Devanagari string (needs uharfbuzz, fontTools, brotli). |
| `qa_crops.py` | #1/#2 visual 1:1 crops and contact sheets. |
| `qa_face_verify.py` | #4 cross-check: independent Haar eye detection mapped through the camera. |
| `qa_logo.py` | #7 logo unaltered (SSIM vs source and vs the rendered logos). |
| `qa_disclaimer.py` | #6 disclaimer coverage of the figure frames, size and contrast. |
| `qa_captions.py` | #5 caption sync (±2 frames) and blank-frame detection. |
| `qa_delivery.py` | Delivery specs of both MP4s plus the cover. |
| `qa_report.py` | Aggregates `parts/*.json` into `qa_results.json`. |
| *(to add)* | #9 face-embedding similarity (insightface) between `flow/character/*.png` references and the presenter in each clip. |

---

## 3. Commands (Windows PowerShell, from `ads\reel02`)

```powershell
$env:PYTHONUTF8 = "1"
$py = "C:\Users\DESKTOP\AppData\Local\Programs\Python\Python311\python.exe"

# 0. put the chosen takes at clips\clip1.mp4, clip2.mp4, clip3.mp4 (candidates live in clips\takes\, raw Flow output in flow_raw\)
& $py work\normalise.py             # needs Reel 02 EDIT values first (see section 4)
& $py work\transcribe.py            # faster-whisper large-v3, hi, word timestamps
& $py work\align_captions.py        # needs Reel 02 SCRIPT/SPANS/chunks (see section 4)
& $py work\face_track.py
Copy-Item work\captions.json, work\edit.json, work\face_boxes.json remotion\src\data\ -Force
New-Item -ItemType Directory -Force remotion\public\clips | Out-Null
Copy-Item work\norm\clip*.mp4 remotion\public\clips\ -Force
& $py work\audio_mix.py
cd remotion; npm ci; npx tsc --noEmit; cd ..
# iterate on stills:  cd remotion; npx remotion still src/index.ts Clip1 ..\work\stills\c1_f040.png --frame=40
& $py work\render.py                # fix npx -> shell=True / npx.cmd first on Windows
# QA (see qa_report.py docstring for the full sequence)
cd remotion; npx remotion render src/index.ts Reel02Graphics ..\work\qa\g --sequence --image-format=png --image-sequence-pattern="f[frame].[ext]"; cd ..
node work\qa\run_dump.mjs
& $py work\qa\qa_frames.py; & $py work\qa\qa_shaping.py; & $py work\qa\qa_crops.py; & $py work\qa\qa_face_verify.py
& $py work\qa\qa_logo.py; & $py work\qa\qa_disclaimer.py; & $py work\qa\qa_captions.py; & $py work\qa\qa_delivery.py; & $py work\qa\qa_report.py
```

---

## 4. Needs Reel02 content (hard-coded Reel 01 script, timings or copy; do NOT reuse values)

**Python**
- `work/normalise.py`: the `EDIT` list (per-clip `trim_start`, `frames`, `note`) comes from Reel 01 RMS analysis. Re-measure it
  on the Reel 02 takes.
- `work/transcribe.py`: hard-codes 3 clips (`for i in (1, 2, 3)`). That's fine if Reel 02 also has 3.
- `work/align_captions.py`: `SCRIPT` (Reel 01 text and `|` chunk breaks), `SPANS` (whisper mapping), and `HIGHLIGHT_PHRASES`.
  Load the text and highlights from `work/script.json`, choose the chunk breaks, and rebuild `SPANS` from the Reel 02 transcripts.
- `work/audio_mix.py`: `DEFAULT_SFX_CUES` uses global frames 0 / 229 / 236 / 506 (Reel 01 joins and slab entrance). Comments
  mention frame 741 and 1 353 600 samples. `END_SCREEN_FRAMES = 105` must match `timeline.ts`.
- `work/mux.py`: generic. Only the docstring example says 846 frames.
- `work/render.py`: `END_SCREEN_START = 741` is hard-coded and should be derived. `QA_TIMES` (0.5…26 s), `END_QA_LOCAL`, and the
  cover frame (it looks up the clip 1 word starting with "बंद", which doesn't exist in Reel 02 and will crash) all need changing.
- `work/qa/qa_disclaimer.py`: the clip 3 frame range `S3 + 234` / `range(0, 235)` (Reel 01 clip 3 = 235 frames).
- `work/qa/qa_frames.py`: `TOTAL = ES0 + 105`, `range(105)`, and comments with Reel 01 frame numbers.
- `work/qa/qa_crops.py`: end-screen crop at global frame 845.
- `work/qa/qa_report.py`: excluded flash frames `(505, 506, 507, 508)`, `--frames=0-845`, and hand-written frame-range notes and
  evidence strings.
- `work/qa/qa_shaping.py`: the `STRINGS` list of graphic strings (slab, badges, plate sub-line, disclaimer, end-screen copy).
- `work/AGENT_BRIEF.md`: Reel 01 face geometry, contracts and composition frame counts (846/229/277/235). Rewrite it for Reel 02.

**Remotion**
- `src/data/captions.json`, `edit.json`, `face_boxes.json`: Reel 01 placeholders. Replace them.
- `src/clips/clip1/*`: the whole hook is Reel 01 content. Cues use `findPhrase(1, 'बंद कर' | 'चार घंटे' | 'reels' | 'Zero' |
  'वही' | 'TrainPlex')`, `HookSlab.tsx` ("SCROLL बंद कर!"), and `StatCard.tsx` ("4 HRS" → ₹500 → ₹0). Only the `LogoPlate` on
  "TrainPlex" maps to the Reel 02 clip 1 ("…मैं TrainPlex पे काम करती हूँ।").
- `src/clips/clip2/*`: cues `findPhrase(2, 'AI' | 'tasks' | 'voice record' | 'photos' | 'text' | 'सब' | 'phone' | 'fees' |
  'training' | 'free')`. **'सब' does not exist in Reel 02 clip 2**, so the bundle will throw. The Reel 02 order is also different
  (phone/voice/photos/text comes before AI/tasks). Also `TaskSlab.tsx` ("AI TRAINER TASKS"), `TaskChips.tsx`
  (Voice Recording / Photo Collection / Text Annotation), `PerkBadges.tsx` ("PHONE से", "₹0 FEES", "FREE TRAINING"), and
  `layout.ts` (positions calibrated to the Reel 01 face).
- `src/clips/clip3/cues.ts`: `findPhrase(3, 'पाँच सौ से छह सौ' | 'तक' | 'पैसा' | 'Bank' | 'UPI' | 'तो नीचे' | 'Learn more' |
  'register')`. **'पैसा' and 'तो नीचे' do not exist in Reel 02 clip 3** ("सीधे Bank…", "नीचे Learn more दबाओ"). Re-key the plate
  hand-off (`PLATE_OUT`), `DISC_GONE` and the LEARN MORE/caption raise (e.g. to 'सीधे' and 'नीचे'). `DISC_STRIP` and the
  face-derived placements must be re-checked.
- `src/clips/clip3/EarningPlate.tsx`: sub-line "4 घंटे में तक*" (still matches the Reel 02 claim, but confirm), and the
  ₹0 → ₹500–600 count.
- `src/clips/clip3/PayoutCard.tsx` (BANK / UPI) and `LearnMore.tsx` ("LEARN MORE", pulse on "register"). The Reel 02 verbs are
  "दबाओ" / "करो".
- `src/captions/Captions.tsx`: `CAPTION_BOTTOM_Y_RAISED` trigger `findPhrase(3, 'तो नीचे')`. It must change, because it throws
  on the Reel 02 script.
- `src/endscreen/EndScreen.tsx`: copy "AI TRAINER बनें", "घर बैठे · Phone से · Paid tasks", chips "FREE REGISTRATION" /
  "FREE TRAINING" / "BANK / UPI PAYMENT", CTA "Register free → trainplex.info/register", "Learn more". It's probably reusable,
  but confirm with the Reel 02 brief (the student angle could fit "Hostel से / Phone से").
- `src/timeline.ts`: `END_SCREEN_FRAMES = 105`; `ClipId = 1 | 2 | 3`.
- `src/global/GlobalOverlays.tsx`: watermark `inAt = 1.0 s` and the duck intervals come from each clip's
  `CLIPn_WATERMARK_BLOCKED`. Recompute them after the new graphics exist.
- Highlight casing: Reel 02 highlights include Latin phrases ("pocket money", "Learn more", "Bank या UPI"), which will be
  uppercased. "TrainPlex" stays exactly as written.
