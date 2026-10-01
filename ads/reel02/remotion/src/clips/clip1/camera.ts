import {random} from 'remotion';
import {SHAKE} from './cues';

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

/**
 * VideoLayer transform for this frame (shake on the hook slab's landing only — no zoom in Reel 02,
 * so face boxes stay in source coordinates; placement pads by SHAKE.amp instead). During the shake
 * the plate is scaled up just enough that the translate never reveals the black backdrop.
 */
export const cameraAt = (frame: number) => {
  const {dx, dy, amp} = shakeAt(frame);
  const cover = amp > 0 ? 1 + (amp + 1) / 540 : 1;
  return {scale: cover, dx, dy, originY: 50};
};
