# Shared brief for all build agents — TrainPlex Reel 01

Project root: /home/user/trainplex-studio/ads/reel01   (Linux cloud container; the original brief said
C:\TrainPlex\ads\reel01 on Windows — same structure here)
Remotion project: ./remotion  (TypeScript, Remotion 4.0.529, React 19, lucide-react 1.48 installed)

## Ground rules
- ONLY edit the files you own (listed in your task). Do NOT edit brand.ts, timeline.ts, fonts.ts,
  primitives.tsx, VideoLayer.tsx, Reel.tsx, Root.tsx, GlobalOverlays.tsx — other agents run in parallel.
  If you need a helper, put it in your own file(s).
- Read first: remotion/src/brand.ts, remotion/src/timeline.ts, remotion/src/components/primitives.tsx,
  remotion/src/components/VideoLayer.tsx, remotion/src/Reel.tsx, remotion/src/Root.tsx, work/captions.json.
- Timing: NEVER hard-code seconds. Derive every cue from captions.json via `findPhrase(clip, phrase, occurrence)`
  / `wordsOf(clip)` in timeline.ts (frames are LOCAL to the clip, 30 fps).
- Typecheck must pass for your files: `cd remotion && npx tsc --noEmit` (errors in other agents' in-progress
  files are not yours — but yours must be clean).
- Verify visually by rendering STILLS only (no full video renders — 4 CPUs are shared by 6 agents):
  `cd remotion && npx remotion still src/index.ts <CompositionId> ../work/stills/<your-folder>/<name>.png --frame=<N>`
  Composition ids: Reel01 (whole, 846 f), Clip1 (229 f), Clip2 (277 f), Clip3 (235 f), EndScreen (105 f), OrangeWipe (8 f).
  Clip1/2/3 previews = that clip's video + its graphics + its captions. Then LOOK at the PNGs with the Read tool
  (downscale with PIL first if you want, e.g. to 540x960) and iterate until it looks professional.

## Brand system (exact — do not deviate)
Colours: Cream #FAF7F2 · Navy #1A1A5E · Orange #FF6B35 · White #FFFFFF · (card border / grid #E8E3DA). No other colours
in graphics (icons too: draw lucide icons in brand colours; NO emoji glyphs — they render in non-brand colours; replace
✋/📱/🎙 with lucide Hand / Smartphone / Mic icons in brand colours).
Fonts: ALWAYS `fontFamily: FONT_STACK` ("Inter", "Noto Sans Devanagari") — already loaded (600/700/800/900).
Shapes: flat solid fills, sharp 90° corners (borderRadius 0), no gradients, no glassmorphism, no drop-shadow blobs.
A thin 4–6 px navy text outline on white text over video is allowed.
Motion: snappy/confident springs (damping ~12–14, stiffness ~180–220 — use SPRING / SPRING_OVERSHOOT / SPRING_FIRM
from brand.ts), 6–10 frame entrances, no fade longer than 12 frames.

## Instagram safe zone (1080x1920)
All text + key graphics inside x 60–1020, y 220–1480. Progress bar lives at y 220–228, so graphics start at y ≥ 232.
Caption zone: captions' block bottom edge at y 1400 by default (see Captions contract).

## The presenter's face — HARD RULE: no graphic may cover the eyes or mouth while he speaks
`faceAt(clip, localFrame)` in timeline.ts returns conservative `eyes` and `mouth` rects (from OpenCV tracking,
work/face_boxes.json). The face is BIG in these clips (≈ x 200–840, eyes ≈ y 560–760, mouth ≈ y 800–1000, chin ≈ 1000–1060).
If a spec position would cover eyes/mouth, move/resize the graphic minimally and REPORT the deviation.
Typical free areas: top band y 232–(eyes.y1-10); right column x ≥ 820 (varies); lower band between chin and captions.

## Watermark contract
A small real-logo watermark sits top-left at WATERMARK_BOX (x 60–260, y 240–462) from 1.0 s. If your clip graphics
intersect that box, export the local-frame intervals from your ClipN.tsx as `CLIPn_WATERMARK_BLOCKED` (already
stubbed, type FrameInterval[] = [start, end) ) — the global watermark then ducks out automatically.

## Captions contract (for coordination)
- Captions render ABOVE clip graphics. Default: caption block bottom edge y = 1400, grows upward, max 2 lines
  (auto-fit font 78–92 px so most chunks are ONE line, max width 900 px).
- Clip 3: from the start of the 2nd "तो" (findPhrase(3, 'तो नीचे')) to clip end, captions are RAISED:
  block bottom edge y = 1290, so the LEARN MORE arrow block can live at y 1310–1478.
- Clip 3 disclaimer strip lives at y 1416–1470 (below captions).
- Clip 2 badges live in the lower band y 960–1185 during "सब phone से, कोई fees नहीं, training भी free" — the
  caption chunks there are one line (block top ≥ 1280).

## Real logo
`<Logo width={..}/>` in primitives.tsx (public/trainplex_logo_transparent.png, 862x956, stacked lockup: icon above
"Train Plex" wordmark + tagline). Use verbatim — never redraw, recolour, stretch, crop or re-letter it.
Height = width / (862/956) ≈ 1.109 × width. NOTE: the file itself shows the wordmark as "Train Plex" — that's the
real logo; in any TEXT you write, the brand is always "TrainPlex".

## Deliverable of every agent
Reply with: files changed, what was implemented, every deviation from the spec + why, still frames you checked
(paths), anything that needs the orchestrator's attention.
