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
// ONE group rotated -4° about its top-left corner (so all edges stay parallel and the row gaps
// stay even): row 1 = PHONE से + ₹0 FEES, row 2 = FREE TRAINING indented to the right.
// Geometry (checked against faceAt(2, 185–277): mouth x ≤ 689, y ≤ 959):
//   row-1 top edge crosses x = 689 at y ≈ 968; lowest point (row-2 bottom-left) ≈ y 1178.
export const BADGE = {
  fontSize: 64,
  padY: 11, // badge height = 64 + 2·11 = 86 px (tighter than the primitive's default 98 px)
  padX: 22,
  gap: 20, // between PHONE से and ₹0 FEES
  rowGap: 12,
  groupX: 120,
  groupY: 1009,
  row2Indent: 220,
} as const;

/** Spring 0 → 1 starting at `start` (frames). */
type SpringConfig = {damping: number; stiffness: number; mass: number};
export const springFrom = (frame: number, fps: number, start: number, config: SpringConfig = SPRING) =>
  spring({frame: frame - start, fps, config});

/** Ease-in 0 → 1 over `dur` frames from `start` — used for snappy exits. */
export const exitFrom = (frame: number, start: number, dur: number) =>
  interpolate(frame, [start, start + dur], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic),
  });
