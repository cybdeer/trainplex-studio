import {Easing, interpolate, spring} from 'remotion';
import {SLAB_ROTATION_DEG, SPRING} from '../../brand';
import {placeFaceSafe, rotatedBounds} from '../../layout/faceSafe';
import {FrameInterval, rectsOverlap, WATERMARK_BOX} from '../../timeline';
import {CHIPS_GONE, CLIP2_END, CUE, FEES_IN, LEAD, TAG_GONE, TAG_IN} from './cues';

/**
 * Clip 2 geometry (1080x1920 canvas px). Every block is placed by layout/faceSafe against the face
 * track for the frames it is on screen: top band above the face, else the lower band (kurti).
 */

// Tag "Lecture के बाद • Phone से" — navy label with an orange edge bar.
export const TAG = {w: 840, h: 96, fontSize: 50, padX: 30, bar: 12} as const;
export const TAG_POS = placeFaceSafe({
  clip: 2,
  name: 'clip2 tag',
  from: TAG_IN,
  to: TAG_GONE,
  w: TAG.w,
  h: TAG.h + TAG.bar,
  zones: ['top', 'lower'],
  minScale: 0.75,
});

// Three task tiles in one row (icon over label).
export const CHIP = {w: 290, h: 160, gap: 22, fontSize: 38, iconSize: 60} as const;
export const CHIP_ROW = {w: 3 * CHIP.w + 2 * CHIP.gap, h: CHIP.h};
export const CHIP_POS = placeFaceSafe({
  clip: 2,
  name: 'clip2 task chips',
  from: CUE.voice - LEAD,
  to: CHIPS_GONE,
  w: CHIP_ROW.w,
  h: CHIP_ROW.h,
  zones: ['lower', 'top'],
  minScale: 0.75,
});

// Perk badges "₹0 FEES" + "FREE TRAINING": one row, rotated -4° as a block.
export const BADGE = {fontSize: 70, padY: 12, padX: 26, gap: 24, rowW: 900, rowH: 70 + 2 * 12} as const;
const badgeBounds = rotatedBounds(BADGE.rowW, BADGE.rowH, SLAB_ROTATION_DEG);
export const BADGE_POS = placeFaceSafe({
  clip: 2,
  name: 'clip2 perk badges',
  from: FEES_IN,
  to: CLIP2_END - 1,
  // + 7 % pop headroom
  w: badgeBounds.w * 1.07,
  h: badgeBounds.h * 1.07,
  zones: ['lower', 'top'],
  minScale: 0.7,
});

/** Watermark: block while any clip-2 graphic crosses WATERMARK_BOX. */
const blocked: FrameInterval[] = [];
if (rectsOverlap(TAG_POS, WATERMARK_BOX)) blocked.push([TAG_IN, TAG_GONE]);
if (rectsOverlap(CHIP_POS, WATERMARK_BOX)) blocked.push([CUE.voice - LEAD, CHIPS_GONE]);
if (rectsOverlap(BADGE_POS, WATERMARK_BOX)) blocked.push([FEES_IN, CLIP2_END]);
export const WATERMARK_BLOCKED: FrameInterval[] = blocked;

/** Spring 0 → 1 starting at `start` (frames). */
type SpringConfig = {damping: number; stiffness: number; mass: number};
export const springFrom = (frame: number, fps: number, start: number, config: SpringConfig = SPRING) =>
  spring({frame: frame - start, fps, config});

/**
 * Spring that is latched once it first reaches 1: it may overshoot, but it never swings back
 * below its rest pose afterwards (keeps sliding elements from rebounding out of the safe zone).
 */
export const settleFrom = (frame: number, fps: number, start: number, config: SpringConfig = SPRING) => {
  const s = springFrom(frame, fps, start, config);
  for (let f = start; f <= frame; f++) {
    if (springFrom(f, fps, start, config) >= 1) return Math.max(1, s);
  }
  return s;
};

/** Ease-in 0 → 1 over `dur` frames from `start` — used for snappy exits. */
export const exitFrom = (frame: number, start: number, dur: number) =>
  interpolate(frame, [start, start + dur], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic),
  });
