import {LOGO_ASPECT, SLAB_ROTATION_DEG} from '../../brand';
import {placeFaceSafe, rotatedBounds} from '../../layout/faceSafe';
import {CLIP_FRAMES, findPhrase, FrameInterval, rectsOverlap, WATERMARK_BOX} from '../../timeline';

/**
 * Clip 1 (HOOK) — every cue is derived from captions.json word timings (local frames, 30 fps) by
 * phrase lookup in the exact script; every position comes from the face track (layout/faceSafe).
 * Script: "Hostel में सबसे पूछो — pocket money कब खत्म होती है? बीस तारीख तक! मेरी नहीं होती,
 *          क्योंकि मैं TrainPlex पे काम करती हूँ।"
 */
const W = {
  pocket: findPhrase(1, 'pocket money'),
  khatam: findPhrase(1, 'खत्म'),
  bees: findPhrase(1, 'बीस तारीख'),
  tak: findPhrase(1, 'तक'),
  kyunki: findPhrase(1, 'क्योंकि'),
  brand: findPhrase(1, 'TrainPlex'),
};
export const CUE = W;

export const CLIP1_END = CLIP_FRAMES[1];
/** Graphics land a hair before the syllable so the pop reads "on" the word. */
export const LEAD = 2;

// ─── 1. Hook slab "[Wallet] POCKET MONEY खत्म?" ─────────────────────────────────────────────
// Navy slab rotated -4°, sweeps in on frame 0 (hook), punches "POCKET MONEY" on the spoken words
// and "खत्म?" on "खत्म", hands over to the calendar card on "बीस".
export const SLAB_SIZE = {w: 930, h: 150};
export const SLAB_FONT = 74;
export const SLAB = {
  lead: 1.5, // the sweep is already moving on frame 0
  inStart: 0,
  inFrames: 6,
  pocketAt: W.pocket.startFrame,
  pulseAt: W.khatam.startFrame,
  outStart: W.bees.startFrame - LEAD - 6,
  outFrames: 6,
};
export const SLAB_OUT_END = SLAB.outStart + SLAB.outFrames;
// Camera shake on the slab's landing: ±6 px, 8 frames, decaying, deterministic.
export const SHAKE = {start: 3, frames: 8, amp: 6};
const slabBounds = rotatedBounds(SLAB_SIZE.w, SLAB_SIZE.h, SLAB_ROTATION_DEG);
export const SLAB_POS = placeFaceSafe({
  clip: 1,
  name: 'clip1 hook slab',
  from: 0,
  to: SLAB_OUT_END,
  w: slabBounds.w,
  h: slabBounds.h,
  zones: ['top', 'lower'],
  minScale: 0.8,
  extraPad: SHAKE.amp,
});

// ─── 2. Calendar card: "20" circled on "बीस", struck through on "तारीख … तक" ─────────────────
export const CAL_SIZE = {w: 300, h: 300};
export const CAL = {
  inAt: W.bees.startFrame - LEAD,
  circleFrom: W.bees.startFrame,
  circleTo: W.bees.startFrame + Math.max(6, findPhrase(1, 'बीस').endFrame - W.bees.startFrame),
  strikeFrom: W.bees.endFrame - 2, // "तारीख" ends -> strike starts
  strikeTo: W.tak.endFrame,
  outAt: W.kyunki.startFrame - 2,
  outFrames: 6,
};
export const CAL_GONE = CAL.outAt + CAL.outFrames;
export const CAL_POS = placeFaceSafe({
  clip: 1,
  name: 'clip1 calendar card',
  from: CAL.inAt,
  to: CAL_GONE,
  w: CAL_SIZE.w,
  h: CAL_SIZE.h,
  zones: ['lower', 'top', 'top-left', 'top-right'],
  minScale: 0.6,
});

// ─── 3. Logo plate on the spoken word "TrainPlex" (holds to clip end) ──────────────────────
export const LOGO = {
  inAt: W.brand.startFrame,
  padY: 16,
  padX: 26,
  bar: 6, // orange underline bar inside the plate's bottom edge
  maxWidth: 300,
};
const plateFor = (logoW: number) => ({
  w: logoW + 2 * LOGO.padX,
  h: Math.ceil(logoW / LOGO_ASPECT) + 2 * LOGO.padY + LOGO.bar,
});
const fullPlate = plateFor(LOGO.maxWidth);
export const LOGO_POS = placeFaceSafe({
  clip: 1,
  name: 'clip1 logo plate',
  from: LOGO.inAt - 1,
  to: CLIP1_END - 1,
  w: fullPlate.w,
  h: fullPlate.h,
  zones: ['lower', 'top', 'top-left', 'top-right'],
  minScale: 0.55,
});
export const LOGO_WIDTH = Math.floor(LOGO.maxWidth * LOGO_POS.scale);
export const LOGO_HEIGHT = LOGO_WIDTH / LOGO_ASPECT;
export const LOGO_PLATE = plateFor(LOGO_WIDTH);

// ─── Watermark contract ─────────────────────────────────────────────────────────────────────
// Any graphic crossing WATERMARK_BOX blocks it; the watermark also hands off to the logo plate
// (two logos never show together) from the plate's pop to the clip end.
const blocked: FrameInterval[] = [];
if (rectsOverlap(SLAB_POS, WATERMARK_BOX)) blocked.push([0, SLAB_OUT_END]);
if (rectsOverlap(CAL_POS, WATERMARK_BOX)) blocked.push([CAL.inAt, CAL_GONE]);
blocked.push([LOGO.inAt, CLIP1_END]);
export const WATERMARK_BLOCKED: FrameInterval[] = blocked;
