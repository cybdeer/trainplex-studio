# TrainPlex Reel 01: brand and QA notes (Agent 13)

Scope: measurement only. Nothing under `remotion/src` or `output/` was changed.
Machine-readable results are in `work/qa/qa_results.json`, and the per-check raw data is in `work/qa/parts/*.json`.
The visual evidence is in `work/qa/view/`. That folder, the renders and the crops are regenerable and gitignored.

## Method

- **Full reel graphics layer.** `Reel01Graphics` was rendered for every frame, 0–845, as RGBA PNGs in `work/qa/g/`.
- **Isolation renders.** These come from a QA-only entry, `work/qa/remotion_qa/index.tsx`, which imports the real components unchanged:
  - `Cap1`, `Cap2` and `Cap3` render the captions only.
  - `EndScreenFG` renders the end screen with its full-bleed backgrounds hidden by CSS: the cream fill, the grid/wedge SVGs and the CTA-bar fill. Only text, logo, chips and arrows remain.
- **Timing, camera and face values.** These are not re-implemented. `work/qa/dump_cues.ts` is bundled with esbuild (`node work/qa/run_dump.mjs`), which evaluates `timeline.ts`, `chunks.ts`, `clip1/camera.ts`, `clip3/cues.ts` and `endscreen/geometry.ts` directly. The output is `cues_dump.json`.
- **Face rects.** The eyes/mouth rects from `faceAt` go through the actual VideoLayer transform before comparison: clip 1 has a punch-in plus shake, and clip 3 has a spring punch-in about the eye line.

## Results

| # | Check | Verdict | Evidence (one line) |
|---|-------|---------|---------------------|
| 1 | Devanagari shaping | **PASS** | HarfBuzz shaped all 59 runs with the shipped woff2 files: 0 .notdef, 0 dotted circles, 0 missing code points. The 1:1 crops of all 26 chunks and the graphics text are clean (`view/deva_sheet_0..5.png`). |
| 2 | "TrainPlex" spelling | **PASS** | No variants in `src` or `captions.json`. The caption renders as "TrainPlex पे दे।". The only lowercase use is the URL `trainplex.info/register`. The logo **artwork** reads "Train Plex". |
| 3 | Safe zone | **PASS** | Settled graphics sit within x 60–1020 and y 232–1477. End-screen foreground sits within x 71–1012 and y 252–1464. The only exceedances are entrance/exit motion, plus the clip-1 slab band, which is full-bleed by design; its text stays within x 95–975. |
| 4 | Eyes/mouth clearance | **PASS** | 0 overlapping frames across 729 frames. Minimum clearance is 11 px to the eyes (g201–202, logo plate) and 10 px to the mouth (g333–335, chips). An independent eye-cascade cross-check touched a chip corner in g309, g312 and g313; a visual zoom shows the chip is on the cheek and not the eye. |
| 5 | Caption sync ±2 f | **PASS** | All 26 chunks are first visible at word start −1 frame (clip 3 chunk 0 is +1). 12 of 13 acoustic spot checks are within ±1.2 frames. For "और" the voiced onset is ambiguous (−3.4 frames). **Defect:** there is a 1-frame caption blink at 21 hard swaps (see below). |
| 6 | Disclaimer | **PASS** | Fully visible from clip-3 local frame 50 to 155 (g556–661). The ₹ figure is visible from local 54 to 103, so the disclaimer is on screen for every figure frame and for 1.73 s afterwards. Text is 30 px / 600, a 32 px block. Contrast on the MP4 is at least 8.9:1. |
| 7 | Logo unaltered | **PASS** | The transparent PNG matches the source: SSIM 0.998, aspect 0.8971 vs 0.8982. Rendered logos match the resampled PNG: end screen SSIM 0.998, watermark 0.994, clip-1 plate 0.965 (edge resampling only). Ink aspect is identical and the best shift is 0 px. |
| 8 | Brand colours | **PASS** | 99.88 % of 252 M interior opaque pixels are within 6 RGB of the brand hexes. All 68 off-palette colours come from transition frames only (join flash and fade-ins). The MP4 holds brand colours within 3.3 RGB. |
| D | Delivery specs | **PASS** | 1080x1920, 30 fps CFR, H.264 High, yuv420p bt709, AAC LC 48 kHz, faststart, 28.200 s, −14.0 LUFS, TP −1.5 dBTP. AAC averages 170 kbps: 194 kbps over the voice, plus 3.5 s of digital silence. The cover is 1080x1920 and shows the slab. |

## Issues found (none blocking)

1. **1-frame caption blink at every hard chunk swap.** This happens at 21 frames:
   - Clip 1: g21, 59, 83, 110, 144, 199
   - Clip 2: g255, 300, 340, 369, 447, 478
   - Clip 3: g539, 559, 576, 603, 629, 664, 674, 704, 717

   The cause has two parts. In `chunks.ts`, the swap sets `prev.hideEnd = next.appear`. In `Captions.tsx` (`ChunkView`), the fade-in is `interpolate(frame - appear, [0, 6], [0, 1])`, which gives opacity 0 on the appear frame. Together they leave no caption visible for one frame.

   **Fix (preferred):** in `remotion/src/captions/chunks.ts`, in the `swap` branch, set `c.fadeStart = next.appear + 1; c.hideEnd = next.appear + 1;`. The outgoing chunk then stays up during the incoming chunk's 0 %-opacity frame. The incoming chunk is still first visible at word start −1, so sync is unchanged.

   **Alternative:** in `Captions.tsx`, `ChunkView`, use `const local = frame - chunk.appear + 1`. Chunks then appear at word start −2, which is still within ±2.
2. **Tight margin between the clip-2 task chips and the face.** The chips start at x 716, y 702. The eye band ends at y 691 and the mouth band at x 706. The eye cascade grazes the "Voice Recording" chip corner in g309–313. This is not a violation.

   **Optional:** in `remotion/src/clips/clip2/layout.ts`, set `CHIP.top` to 714 and `CHIP.x` to 726 with `width` 294, which gives about 22 px of margin. The stack bottom moves from 996 to 1008. The only badge that pops while the chips are still exiting is "PHONE से" at x ≤ about 590, so it does not collide; re-check stills at clip-2 local frames 83, 104 and 195.
3. **Duplicate logo for 3 frames in clip 1 (g201–203).** The cream logo plate opens empty on g201, because the logo only becomes visible at `inAt + 1`. Meanwhile the watermark is still fading out: its duck starts at `LOGO.inAt + 3`.

   **Optional:** in `remotion/src/clips/clip1/cues.ts`, change `WATERMARK_BLOCKED` to `[LOGO.inAt, CLIP1_END]`. The watermark then fades out over g198–200 and is gone when the plate opens. Optionally, also show the logo on `inAt` itself.
4. **"FREE।" spacing (clip 2 chunk 7).** The Devanagari danda after the Inter caps sits noticeably far from the word. This is cosmetic.

   **Optional:** attach a narrower danda through a special case in the caption display.
5. **Delivery, not a spec failure.** `TrainPlex_Reel01_9x16.mp4` and `_nomusic.mp4` are **byte-identical** (md5 ba8924ab…). This is because `assets/music.mp3` and any SFX are absent, which is documented in `work/audio/audio_report.json`. The end screen (24.7–28.2 s) is silent.

   **Fix:** supply a music bed and re-run `work/audio_mix.py` and then `work/render.py --skip-render`.
6. **Source footage carries generator marks.** A white 4-point sparkle sits at about x 865–935, y 1705–1775 in clips 1 and 2. A "Veo" text mark sits at about x 1025–1055, y 1883–1896 in clip 3. Both are visible in the delivered MP4 below the safe zone. They are not our graphics.

   **Consider:** crop or cover them, or disclose the use of AI-generated video (Meta's "AI info" label).
7. **Logo asset notes.**
   - `logo/trainplex_logo_source.png` is only 300x300 px, so the 420 px end-screen logo is about a 1.95x upscale of source pixels and is slightly soft. A vector or high-res master is recommended.
   - The artwork's orange is #FE5015, not the brand #FF6B35.
   - The wordmark reads "Train Plex".

   These are all artwork issues, not render issues.
8. **Reproduction note.** `.gitignore` rule `work/qa/*/` also ignores `work/qa/remotion_qa/index.tsx`, which is the QA entry needed to regenerate the isolation renders, and `work/qa/parts/`.

## Frame references

- Global frame = clip start + local frame. The clip starts are 0 (clip 1), 229 (clip 2) and 506 (clip 3); the end screen starts at 741.
- Join flash: g228–231 and g505–508. Orange wipe: g737–744.
