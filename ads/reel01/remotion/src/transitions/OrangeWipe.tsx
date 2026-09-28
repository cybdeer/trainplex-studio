import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {CANVAS, COLORS} from '../brand';
import {WIPE_FRAMES} from '../timeline';

const W = CANVAS.width;
const HALF = WIPE_FRAMES / 2; // 4 frames cover, 4 frames reveal
const EDGE = 28; // navy edge bar width (px)

/**
 * Edge travel over each 4-frame half, as a fraction of (width + edge bar), sampled at the END of
 * each frame. Cover has a fast attack and is fully orange on its last frame (the cut); reveal
 * accelerates away and leaves a sliver on its last frame so the hand-off to the clean end screen
 * still reads as motion.
 */
const T = [0, 0.25, 0.5, 0.75, 1];
const COVER = [0, 0.3, 0.64, 0.9, 1];
const REVEAL = [0, 0.12, 0.38, 0.68, 0.92];

/**
 * Orange full-frame wipe (left → right), 8 frames centred on the clip 3 → end-screen cut.
 * Frames 0–3: the orange panel's leading edge (with a thin navy bar ahead of it) sweeps across
 * the clip until the frame is fully orange. Frames 4–7 (end screen underneath): the trailing edge
 * (navy bar behind it) sweeps left → right, revealing the end screen.
 */
export const OrangeWipe: React.FC = () => {
  const frame = useCurrentFrame();
  if (frame < 0 || frame >= WIPE_FRAMES) return null;

  const span = W + EDGE;
  let orange: [number, number];
  let navy: [number, number];
  if (frame < HALF) {
    const lead = interpolate((frame + 1) / HALF, T, COVER) * span;
    orange = [0, Math.min(W, lead)];
    navy = [lead, lead + EDGE];
  } else {
    const trail = interpolate((frame - HALF + 1) / HALF, T, REVEAL) * span;
    orange = [trail, W];
    navy = [trail - EDGE, trail];
  }

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          left: orange[0],
          width: orange[1] - orange[0],
          backgroundColor: COLORS.orange,
        }}
      />
      {navy[0] < W && navy[1] > 0 ? (
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: navy[0],
            width: navy[1] - navy[0],
            backgroundColor: COLORS.navy,
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};
