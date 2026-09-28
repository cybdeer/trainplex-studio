import {Hand} from 'lucide-react';
import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SLAB_ROTATION_DEG, SPRING_OVERSHOOT} from '../../brand';
import {SLAB, SLAB_OUT_END} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const FONT_SIZE = 96;
const SLAB_H = SLAB.y2 - SLAB.y1; // 160
const CY = (SLAB.y1 + SLAB.y2) / 2; // 380
// Travel along the slab's own (rotated) axis: from fully off-screen left to fully off-screen right.
const TRAVEL = 1080 / 2 + SLAB.width / 2 + 60;

/**
 * Frame 0: full-width navy slab sweeps in from the left, rotated -4°, carrying
 * [Hand] "SCROLL बंद कर!" (white 900, 96 px, "बंद कर!" orange). Holds until "बंद कर!" ends,
 * then slides out right.
 */
export const HookSlab: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame >= SLAB_OUT_END) return null;

  const expoOut = Easing.bezier(0.16, 1, 0.3, 1);
  const pIn = interpolate(frame, [SLAB.inStart - SLAB.lead, SLAB.inStart + SLAB.inFrames], [0, 1], {
    ...clamp,
    easing: expoOut,
  });
  const pOut = interpolate(frame, [SLAB.outStart, SLAB_OUT_END], [0, 1], {
    ...clamp,
    easing: Easing.in(Easing.cubic),
  });
  const slabX = (pIn - 1) * TRAVEL + pOut * TRAVEL;

  // Content trails the slab slightly on entry (parallax), then locks.
  const pText = interpolate(frame, [SLAB.inStart, SLAB.inStart + SLAB.inFrames + 2], [0, 1], {
    ...clamp,
    easing: expoOut,
  });
  const textX = (1 - pText) * -180;

  // Hand icon "stops" into place with a small overshoot.
  const handIn = spring({frame: frame - 2, fps, config: SPRING_OVERSHOOT});
  const handRot = interpolate(handIn, [0, 1], [-28, 0]);

  // "बंद कर!" punches as it is spoken.
  const pulse = interpolate(frame, [SLAB.pulseAt, SLAB.pulseAt + 3, SLAB.pulseAt + 9], [1, 1.1, 1], {
    ...clamp,
    easing: Easing.out(Easing.quad),
  });

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: 540 - SLAB.width / 2,
          top: CY - SLAB_H / 2,
          width: SLAB.width,
          height: SLAB_H,
          transform: `rotate(${SLAB_ROTATION_DEG}deg) translateX(${slabX}px)`,
          transformOrigin: '50% 50%',
          backgroundColor: COLORS.navy,
          borderRadius: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 22,
            transform: `translateX(${textX}px)`,
            fontFamily: FONT_STACK,
            fontWeight: 900,
            fontSize: FONT_SIZE,
            lineHeight: 1,
            color: COLORS.white,
            whiteSpace: 'nowrap',
          }}
        >
          <Hand
            size={92}
            color={COLORS.white}
            strokeWidth={2.6}
            absoluteStrokeWidth={false}
            style={{flex: 'none', transform: `rotate(${handRot}deg)`, transformOrigin: '50% 90%'}}
          />
          <span style={{letterSpacing: '-0.01em'}}>SCROLL</span>
          <span
            style={{
              display: 'inline-block',
              color: COLORS.orange,
              transform: `scale(${pulse})`,
              transformOrigin: '8% 55%', // grow away from "SCROLL" so the word gap never closes
              marginLeft: 6,
            }}
          >
            बंद कर!
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
