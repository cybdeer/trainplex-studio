import React from 'react';
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SPRING_FIRM, SPRING_OVERSHOOT} from '../../brand';
import {COUNT_A, COUNT_B, FIGURE_ON, LAND, PLATE, PLATE_GONE, PLATE_IN, PLATE_OPEN_FRAMES, PLATE_OUT, PLATE_SIZE} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const easeOut = Easing.out(Easing.cubic);

const FIGURE_SIZE = 116;
const SUB_SIZE = 56;
const ACCENT_W = 14;
/** Fixed slot for "₹400–500" so the count never re-flows the "/ 2–3 घंटे*" part. */
const FIGURE_SLOT = 540;

/**
 * Navy plate "₹400–500 / 2–3 घंटे*": opens on "दो-तीन घंटे" showing "/ 2–3 घंटे*"; the ₹ figure
 * counts ₹0 → ₹400 across "चार सौ", "–500" unrolls on "से" and counts through "पाँच सौ"; on
 * "कमा लेती हूँ" it lands with a pop (video punch-in from the same cue). Leaves on "सीधे".
 * "*" → disclaimer strip.
 */
export const EarningPlate: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < PLATE_IN || frame >= PLATE_GONE) return null;

  const open = spring({frame: frame - PLATE_IN, fps, config: {...SPRING_FIRM, overshootClamping: true}, durationInFrames: PLATE_OPEN_FRAMES});
  const insetPct = (1 - open) * 50;
  const exitX = interpolate(frame, [PLATE_OUT, PLATE_GONE], [0, -(PLATE.x1 + PLATE_SIZE.w * PLATE.scale + 40)], {
    ...clamp,
    easing: Easing.in(Easing.cubic),
  });

  const a = Math.round(interpolate(frame, COUNT_A, [0, 400], {...clamp, easing: easeOut}));
  const b = Math.round(interpolate(frame, COUNT_B, [400, 500], {...clamp, easing: easeOut}));
  const unroll = spring({frame: frame - COUNT_B[0], fps, config: {...SPRING_FIRM, overshootClamping: true}, durationInFrames: 7});

  const land = spring({frame: frame - LAND, fps, config: SPRING_OVERSHOOT});
  const pop = frame >= LAND ? 1 + 0.08 * (1 - land) : 1;
  const drift = interpolate(frame, [LAND, PLATE_OUT], [1, 1.02], clamp);

  const figureShown = frame >= FIGURE_ON;
  const figureY = interpolate(frame, [FIGURE_ON - 1, FIGURE_ON + 5], [24, 0], {...clamp, easing: easeOut});
  const subIn = interpolate(frame, [PLATE_IN + 2, PLATE_IN + 6], [0, 1], clamp);
  const accent = spring({frame: frame - LAND, fps, config: {...SPRING_FIRM, overshootClamping: true}, durationInFrames: 8});

  const {w, h} = PLATE_SIZE;
  const figureStyle: React.CSSProperties = {
    fontFamily: FONT_STACK,
    fontWeight: 900,
    fontSize: FIGURE_SIZE,
    lineHeight: 1,
    color: COLORS.orange,
    letterSpacing: '-0.03em',
    fontVariantNumeric: 'tabular-nums',
    whiteSpace: 'nowrap',
  };

  return (
    <div
      style={{
        position: 'absolute',
        left: PLATE.x1,
        top: PLATE.y1,
        width: w,
        height: h,
        transformOrigin: '0 0',
        transform: `translateX(${exitX}px) scale(${PLATE.scale})`,
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundColor: COLORS.navy,
          clipPath: `inset(0 ${insetPct}% 0 ${insetPct}%)`,
          overflow: 'hidden',
        }}
      >
        <div style={{position: 'absolute', left: 0, top: 0, width: ACCENT_W, height: h * accent, backgroundColor: COLORS.orange}} />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'center',
            paddingTop: (h - FIGURE_SIZE) / 2 + 6,
            gap: 18,
          }}
        >
          <div style={{width: FIGURE_SLOT, display: 'flex', justifyContent: 'flex-end'}}>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                visibility: figureShown ? 'visible' : 'hidden',
                transform: `translateY(${figureY}px) scale(${pop * drift})`,
                transformOrigin: '100% 60%',
              }}
            >
              <span style={figureStyle}>₹{a}</span>
              <span style={{...figureStyle, display: 'inline-block', overflow: 'hidden', maxWidth: `${unroll * 2.6}em`}}>–{b}</span>
            </div>
          </div>
          <div
            style={{
              fontFamily: FONT_STACK,
              fontWeight: 800,
              fontSize: SUB_SIZE,
              lineHeight: 1,
              color: COLORS.white,
              whiteSpace: 'nowrap',
              opacity: subIn,
            }}
          >
            / 2–3 घंटे*
          </div>
        </div>
      </div>
    </div>
  );
};
