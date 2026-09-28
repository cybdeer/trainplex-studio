import React from 'react';
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SPRING_FIRM, SPRING_OVERSHOOT} from '../../brand';
import {COUNT_A, COUNT_B, FIGURE_ON, LAND, PLATE, PLATE_GONE, PLATE_IN, PLATE_OPEN_FRAMES, PLATE_OUT} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const easeOut = Easing.out(Easing.cubic);

const FIGURE_SIZE = 140;
const SUB_SIZE = 44;
const ACCENT_W = 12;

/**
 * Navy plate with the earning figure: "₹0" counts to "₹500", then "–600" unrolls on "से" and
 * counts up through "छह सौ"; on "तक" the figure lands with a scale pop (the video punch-in is
 * driven by Clip3 from the same cue). Sub-line: "4 घंटे में तक*" (asterisk → disclaimer strip).
 */
export const EarningPlate: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < PLATE_IN || frame >= PLATE_GONE) return null;

  // Open: horizontal reveal from the centre line.
  const open = spring({frame: frame - PLATE_IN, fps, config: {...SPRING_FIRM, overshootClamping: true}, durationInFrames: PLATE_OPEN_FRAMES});
  const insetPct = (1 - open) * 50;

  // Exit: pushed out to the left as the BANK / UPI card arrives from the right.
  const exitX = interpolate(frame, [PLATE_OUT, PLATE_GONE], [0, -(PLATE.x2 + 40)], {...clamp, easing: Easing.in(Easing.cubic)});

  // Count-up.
  const a = Math.round(interpolate(frame, COUNT_A, [0, 500], {...clamp, easing: easeOut}));
  const b = Math.round(interpolate(frame, COUNT_B, [500, 600], {...clamp, easing: easeOut}));
  // "–600" unrolls (max-width in em, so it re-centres smoothly) on "से".
  const unroll = spring({frame: frame - COUNT_B[0], fps, config: {...SPRING_FIRM, overshootClamping: true}, durationInFrames: 7});

  // Landing pop on "तक": jump to 110 % and settle with a small overshoot.
  const land = spring({frame: frame - LAND, fps, config: SPRING_OVERSHOOT});
  const pop = frame >= LAND ? 1 + 0.1 * (1 - land) : 1;
  // Tiny continuous drift while held (keeps the plate alive).
  const drift = interpolate(frame, [LAND, PLATE_OUT], [1, 1.025], clamp);

  const figureIn = interpolate(frame, [FIGURE_ON - 1, FIGURE_ON + 1], [0, 1], clamp);
  const figureY = interpolate(frame, [FIGURE_ON - 1, FIGURE_ON + 5], [28, 0], {...clamp, easing: easeOut});
  const subIn = interpolate(frame, [FIGURE_ON + 2, FIGURE_ON + 6], [0, 1], clamp);
  const subY = interpolate(frame, [FIGURE_ON + 2, FIGURE_ON + 8], [20, 0], {...clamp, easing: easeOut});

  // Orange accent bar grows down the left edge on the landing.
  const accent = spring({frame: frame - LAND, fps, config: {...SPRING_FIRM, overshootClamping: true}, durationInFrames: 8});

  const height = PLATE.y2 - PLATE.y1;
  const figureStyle: React.CSSProperties = {
    fontFamily: FONT_STACK,
    fontWeight: 900,
    fontSize: FIGURE_SIZE,
    lineHeight: 1,
    color: COLORS.orange,
    letterSpacing: '-0.02em',
    fontVariantNumeric: 'tabular-nums',
    whiteSpace: 'nowrap',
  };

  return (
    <div
      style={{
        position: 'absolute',
        left: PLATE.x1,
        top: PLATE.y1,
        width: PLATE.x2 - PLATE.x1,
        height,
        transform: `translateX(${exitX}px)`,
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
        {/* left accent bar */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            width: ACCENT_W,
            height: height * accent,
            backgroundColor: COLORS.orange,
          }}
        />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 14,
            paddingTop: 4,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              opacity: figureIn,
              transform: `translateY(${figureY}px) scale(${pop * drift})`,
              transformOrigin: '50% 60%',
            }}
          >
            <span style={figureStyle}>₹{a}</span>
            <span
              style={{
                ...figureStyle,
                display: 'inline-block',
                overflow: 'hidden',
                maxWidth: `${unroll * 3.2}em`,
                verticalAlign: 'bottom',
              }}
            >
              –{b}
            </span>
          </div>
          <div
            style={{
              fontFamily: FONT_STACK,
              fontWeight: 700,
              fontSize: SUB_SIZE,
              lineHeight: 1.3,
              color: COLORS.white,
              whiteSpace: 'nowrap',
              opacity: subIn,
              transform: `translateY(${subY}px)`,
            }}
          >
            4 घंटे में तक*
          </div>
        </div>
      </div>
    </div>
  );
};
