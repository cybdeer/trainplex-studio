import {Easing, interpolate, random} from 'remotion';
import {SHAKE, ZOOM} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/** Decaying, deterministic camera shake (±amp px) for `frames` frames from `start`. */
const shakeAt = (frame: number) => {
  const i = frame - SHAKE.start;
  if (i < 0 || i >= SHAKE.frames) return {dx: 0, dy: 0, amp: 0};
  const amp = SHAKE.amp * Math.pow(1 - i / SHAKE.frames, 1.4);
  // alternate horizontal direction every frame so the jolt reads, magnitude jittered 60–100 %
  const dx = amp * (i % 2 === 0 ? 1 : -1) * (0.6 + 0.4 * random(`clip1-shake-x-${i}`));
  const dy = amp * (random(`clip1-shake-y-${i}`) * 2 - 1);
  return {dx, dy, amp};
};

/** Punch-in zoom scale on "Zero!" (1 → 1.15 → 1). */
const zoomAt = (frame: number) => {
  const a = ZOOM.start;
  const b = a + ZOOM.inFrames;
  const c = b + ZOOM.holdFrames;
  const d = c + ZOOM.outFrames;
  if (frame < a || frame >= d) return 1;
  if (frame < b) {
    return interpolate(frame, [a, b], [1, ZOOM.peak], {...clamp, easing: Easing.out(Easing.cubic)});
  }
  if (frame < c) return ZOOM.peak;
  return interpolate(frame, [c, d], [ZOOM.peak, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
};

/**
 * VideoLayer transform for this frame. During the shake the plate is scaled up just enough
 * (≥ amp on every edge) that the translate never reveals the black backdrop.
 */
export const cameraAt = (frame: number) => {
  const {dx, dy, amp} = shakeAt(frame);
  const cover = amp > 0 ? 1 + (amp + 1) / 540 : 1;
  return {scale: Math.max(zoomAt(frame), cover), dx, dy, originY: ZOOM.originY};
};
