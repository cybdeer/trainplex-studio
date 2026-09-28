import {LOGO_ASPECT, SAFE} from '../../brand';
import {CLIP_FRAMES, faceAt, findPhrase, FrameInterval, Rect} from '../../timeline';

/**
 * Clip 1 (HOOK) — every cue is derived from captions.json word timings (local frames, 30 fps).
 * Script: "भाई, scroll करना बंद कर! रोज़ चार घंटे reels देखता है — बदले में मिला क्या? Zero!
 *          वही चार घंटे TrainPlex पे दे।"
 */
const W = {
  bandKar: findPhrase(1, 'बंद कर'),
  chaar: findPhrase(1, 'चार घंटे', 0),
  reels: findPhrase(1, 'reels'),
  zero: findPhrase(1, 'Zero'),
  vahi: findPhrase(1, 'वही'),
  brand: findPhrase(1, 'TrainPlex'),
};

export const CLIP1_END = CLIP_FRAMES[1];

const range = (a: number, b: number) => Array.from({length: Math.max(0, b - a)}, (_, i) => a + i);

// ─── 1. "✋ SCROLL बंद कर!" slab ────────────────────────────────────────────────────────────
export const SLAB = {
  // The sweep is already under way on frame 0 (easing starts LEAD frames before it) so the very
  // first frame of the Reel shows motion, not a bare shot.
  lead: 1.5,
  inStart: 0,
  inFrames: 6,
  pulseAt: W.bandKar.startFrame, // "बंद कर!" punches as it is spoken
  outStart: W.bandKar.endFrame, // hold until "बंद कर!" ends …
  outFrames: 7, // … then slide out to the right
  // geometry (canvas px): band y 300–460 before rotation, rotated exactly -4°
  y1: 300,
  y2: 460,
  width: 1500, // rotated -4° it still spans the full 1080 px (needs ≥ 1080/cos4° + 160·tan4° ≈ 1094)
};
export const SLAB_OUT_END = SLAB.outStart + SLAB.outFrames;

// Camera shake on the slab's landing: ±6 px, 8 frames, decaying, deterministic.
export const SHAKE = {start: 3, frames: 8, amp: 6};

// ─── 2/3. "4 HRS" card → "₹0" counter ────────────────────────────────────────────────────────
export const CARD = {
  box: {x1: 760, y1: 300, x2: 1000, y2: 540} as Rect,
  inAt: W.chaar.startFrame, // pops on "चार घंटे reels"
  flipMid: W.zero.startFrame, // 3D flip, faces swap exactly on "Zero!"
  flipHalf: 3,
  countStart: W.zero.startFrame, // ₹500 → ₹0 over 10 frames
  countFrames: 10,
  outAt: W.vahi.startFrame, // snappy exit on "वही", well before the logo plate
  outFrames: 6,
};

// Punch-in digital zoom on "Zero!": 100 → 115 % in 4 f, hold 8 f, ease back in 5 f.
const zoomStart = W.zero.startFrame;
const zoomWindow = range(zoomStart, zoomStart + 4 + 8 + 5);
const faceCentreY =
  zoomWindow.reduce((s, f) => {
    const {face} = faceAt(1, f);
    return s + (face.y1 + face.y2) / 2;
  }, 0) / zoomWindow.length;
export const ZOOM = {
  start: zoomStart,
  inFrames: 4,
  holdFrames: 8,
  outFrames: 5,
  peak: 1.15,
  // transform-origin at the face centre so the face grows in place and stays framed
  originY: (faceCentreY / 1920) * 100,
};

// ─── 4. Logo plate on "TrainPlex" ────────────────────────────────────────────────────────────
// The real logo is a stacked lockup (h ≈ 1.109·w), so the spec's 360 px would put the plate over
// his eyes. Size it as large as possible with: plate top ≥ 232 (below the progress bar) and plate
// bottom ≤ min(eyes.y1 over the plate's visible frames) − 10.
export const LOGO = {
  inAt: W.brand.startFrame,
  top: SAFE.y1 + 12, // 232
  padY: 14,
  padX: 22,
  bar: 2, // orange underline bar (inside the plate's bottom edge)
};
const plateFrames = range(LOGO.inAt, CLIP1_END);
export const LOGO_EYES_TOP = Math.min(...plateFrames.map((f) => faceAt(1, f).eyes.y1));
export const LOGO_PLATE_BOTTOM_MAX = Math.floor(LOGO_EYES_TOP - 10);
export const LOGO_WIDTH = Math.min(
  360,
  Math.floor((LOGO_PLATE_BOTTOM_MAX - LOGO.top - 2 * LOGO.padY - LOGO.bar) * LOGO_ASPECT),
);
export const LOGO_HEIGHT = LOGO_WIDTH / LOGO_ASPECT;
export const LOGO_PLATE = {
  width: LOGO_WIDTH + 2 * LOGO.padX,
  height: Math.ceil(LOGO_HEIGHT) + 2 * LOGO.padY + LOGO.bar,
};

// ─── Watermark contract ─────────────────────────────────────────────────────────────────────
// The slab crosses WATERMARK_BOX (x 60–260, y 240–462) → block while it is on screen.
// The logo plate (top-centre) does not intersect the box, but a 200 px watermark logo next to the
// ~265 px hero logo reads as a duplicate, so the watermark hands off to the plate: it fades out
// over the 4 frames around the plate's pop and returns with clip 2.
export const WATERMARK_BLOCKED: FrameInterval[] = [
  [0, SLAB_OUT_END],
  [LOGO.inAt, CLIP1_END],
];
