import {Check, Landmark} from 'lucide-react';
import React from 'react';
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SLAB_ROTATION_DEG, SPRING_FIRM, SPRING_OVERSHOOT} from '../../brand';
import {BANK_HI, CARD, CARD_GONE, CARD_IN, CARD_OUT, TICK_AT, TICK_SIZE, UPI_HI} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const TEXT_SIZE = 84;
const CARD_SLIDE = {damping: 24, stiffness: 200, mass: 1};
const ICON_SIZE = 116;
const UNDERLINE_H = 8;

/** Orange bar that wipes in under a word (left → right) on its spoken cue. */
const Underline: React.FC<{at: number}> = ({at}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - at, fps, config: {...SPRING_FIRM, overshootClamping: true}, durationInFrames: 7});
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: -6,
        height: UNDERLINE_H,
        backgroundColor: COLORS.orange,
        transform: `scaleX(${p})`,
        transformOrigin: '0% 50%',
      }}
    />
  );
};

/**
 * "पैसा सीधे Bank या UPI में" — white card (2 px #E8E3DA border, sharp corners) slides in from the
 * right with a navy Landmark icon and "BANK / UPI" (navy 900). Orange underlines hit "BANK" and
 * "UPI" on their words; a flat orange tick badge stamps on the card corner at the end of "UPI".
 */
export const PayoutCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < CARD_IN || frame >= CARD_GONE) return null;

  const w = CARD.x2 - CARD.x1;
  const h = CARD.y2 - CARD.y1;

  // Long travel (≈ 820 px): a lightly-damped spring would overshoot ~150 px into the watermark,
  // so the slide uses a firmer damping (ζ ≈ 0.85, < 1 % overshoot) — still a snappy ~8-frame settle.
  const enter = spring({frame: frame - CARD_IN, fps, config: CARD_SLIDE});
  const enterX = (1 - enter) * (1080 - CARD.x1 + 40);
  const exitX = interpolate(frame, [CARD_OUT, CARD_GONE - 1], [0, 1080 - CARD.x1 + 80], {
    ...clamp,
    easing: Easing.in(Easing.cubic),
  });

  // Content rides in with the card (never an empty white box); the icon lands with a small pop
  // and the words trail the card edge slightly for a sense of momentum.
  const iconP = interpolate(spring({frame: frame - CARD_IN - 2, fps, config: SPRING_OVERSHOOT}), [0, 1], [0.7, 1]);
  const textX = (1 - spring({frame: frame - CARD_IN, fps, config: SPRING_FIRM})) * 60;

  const tick = spring({frame: frame - TICK_AT, fps, config: SPRING_OVERSHOOT});
  const tickRot = interpolate(tick, [0, 1], [-40, SLAB_ROTATION_DEG]);

  const word: React.CSSProperties = {position: 'relative', display: 'inline-block'};

  return (
    <div
      style={{
        position: 'absolute',
        left: CARD.x1,
        top: CARD.y1,
        width: w,
        height: h,
        transform: `translateX(${enterX + exitX}px)`,
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundColor: COLORS.white,
          border: `2px solid ${COLORS.border}`,
          boxSizing: 'border-box',
          display: 'flex',
          alignItems: 'center',
          gap: 34,
          padding: '0 44px',
        }}
      >
        <div style={{transform: `scale(${iconP})`, display: 'flex', flex: 'none'}}>
          <Landmark size={ICON_SIZE} color={COLORS.navy} strokeWidth={2.2} absoluteStrokeWidth={false} />
        </div>
        <div
          style={{
            fontFamily: FONT_STACK,
            fontWeight: 900,
            fontSize: TEXT_SIZE,
            lineHeight: 1,
            color: COLORS.navy,
            letterSpacing: '-0.01em',
            whiteSpace: 'nowrap',
            transform: `translateX(${textX}px)`,
          }}
        >
          <span style={word}>
            BANK
            <Underline at={BANK_HI} />
          </span>
          <span style={{margin: '0 0.22em'}}>/</span>
          <span style={word}>
            UPI
            <Underline at={UPI_HI} />
          </span>
        </div>
      </div>
      {/* tick badge centred on the top-right corner */}
      <div
        style={{
          position: 'absolute',
          left: w - TICK_SIZE / 2,
          top: -TICK_SIZE / 2,
          width: TICK_SIZE,
          height: TICK_SIZE,
          backgroundColor: COLORS.orange,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transform: `scale(${tick}) rotate(${tickRot}deg)`,
          opacity: frame >= TICK_AT ? 1 : 0,
        }}
      >
        <Check size={TICK_SIZE * 0.72} color={COLORS.white} strokeWidth={3.6} />
      </div>
    </div>
  );
};
