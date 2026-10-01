import React from 'react';
import {Easing, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, FONT_STACK} from '../../brand';
import {DISC_GONE, DISC_IN, DISC_IN_FRAMES, DISC_OUT, DISC_STRIP} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export const DISCLAIMER_TEXT = '*कमाई task availability और approval पर निर्भर है';

/** navy #1A1A5E at 70 % opacity (strip only — the text stays fully opaque white). */
const NAVY_70 = 'rgba(26, 26, 94, 0.7)';

/**
 * Mandatory earnings disclaimer: text-hugging 70 % navy strip, y 1416–1470 (below the caption
 * block's 1400 bottom edge), white 30 px / 600. On screen for every frame the earning figure is
 * visible plus ≥ 1 s; snappy 5-frame wipe in / 5-frame wipe out.
 */
export const Disclaimer: React.FC = () => {
  const frame = useCurrentFrame();
  if (frame < DISC_IN || frame >= DISC_GONE) return null;

  const inP = interpolate(frame, [DISC_IN, DISC_IN + DISC_IN_FRAMES - 1], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const outP = interpolate(frame, [DISC_OUT, DISC_GONE - 1], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  // In: reveal left → right. Out: collapse towards the right.
  const clipPath = `inset(0 ${(1 - inP) * 100}% 0 ${outP * 100}%)`;
  const textX = interpolate(inP, [0, 1], [-14, 0]);

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        top: DISC_STRIP.y1,
        height: DISC_STRIP.y2 - DISC_STRIP.y1,
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          padding: '0 22px',
          backgroundColor: NAVY_70,
          clipPath,
        }}
      >
        <span
          style={{
            fontFamily: FONT_STACK,
            fontWeight: 600,
            fontSize: 30,
            lineHeight: 1.2,
            color: COLORS.white,
            whiteSpace: 'nowrap',
            transform: `translateX(${textX}px)`,
            display: 'inline-block',
          }}
        >
          {DISCLAIMER_TEXT}
        </span>
      </div>
    </div>
  );
};
