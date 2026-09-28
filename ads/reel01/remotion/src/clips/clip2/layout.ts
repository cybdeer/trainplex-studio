import {Easing, interpolate, spring} from 'remotion';
import {SPRING} from '../../brand';

/**
 * Clip 2 geometry (1080x1920 canvas px). Positions are chosen against faceAt(2, f) for the
 * frames each element is on screen — see the comments on each block.
 */

// "AI TRAINER TASKS" navy slab, top band. Eyes never rise above y 490 in this clip (faceAt),
// so the slab (rotated bbox ≈ y 236–389) sits well clear of them. It covers WATERMARK_BOX.
export const SLAB = {
  left: 66,
  top: 262,
  height: 100,
  fontSize: 60,
  padX: 32,
  barHeight: 12, // orange underline that wipes in on "tasks"
} as const;

// Task chips, right column. While chips are up (voice → सब) faceAt gives eyes y ≤ 691 and
// mouth x ≤ 706, so the stack starts just below the eye line and right of the mouth.
export const CHIP = {
  x: 716,
  width: 304, // 716 → 1020 (safe-zone edge)
  height: 90,
  top: 702,
  gap: 12,
  fontSize: 32,
  iconSize: 40,
} as const;
export const chipTop = (i: number) => CHIP.top + i * (CHIP.height + CHIP.gap);

// Perk badges, lower band (between chin/mouth and captions): y 960–1185. The three badges form
// ONE block rotated -4° about the canvas centre line (x 540, y = groupY), so every edge stays
// parallel and the row gap stays even: row 1 = PHONE से + ₹0 FEES (centred on x 540),
// row 2 = FREE TRAINING right-aligned under it (staggered).
// Checked against faceAt(2, 185–277) (mouth x ≤ 689, y ≤ 959): row-1 top edge crosses x = 689
// at y ≈ 976; block spans y ≈ 961 (top-right corner) – 1179 (row-2 bottom-left), ≤ 1183 at pop peak.
export const BADGE = {
  fontSize: 64,
  padY: 11, // badge height = 64 + 2·11 = 86 px (tighter than the primitive's default 98 px)
  padX: 22,
  gap: 12, // between PHONE से and ₹0 FEES (≈ the 10 px row gap once tilted)
  rowGap: 10,
  groupY: 986,
} as const;

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
