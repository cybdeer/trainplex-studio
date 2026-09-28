import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SPRING_FIRM, SPRING_OVERSHOOT} from '../../brand';
import {BOUNCE_COUNT, BOUNCE_PERIOD, BOUNCE_START, LM_BLOCK, LM_IN, PULSE_AT} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const LABEL_SIZE = 54;
const LABEL_H = 78;
const ARROW_W = 108;
const ARROW_H = 96;
const BOUNCE_AMP = 10;
// Bounce bottom lands exactly on the block's bottom edge (1478); the shaft top is tucked behind
// the label, so the arrow slides out from under it.
const ARROW_REST_TOP = LM_BLOCK.y2 - BOUNCE_AMP - ARROW_H;
const TUCK = LM_BLOCK.y1 + LABEL_H - ARROW_REST_TOP;
const OUTLINE = 6; // navy outline so the orange arrow reads on any background

/** Solid flat down-arrow (shaft + head), orange with a thin navy outline. */
const DownArrow: React.FC = () => {
  const o = OUTLINE / 2;
  const shaftW = 40;
  const headH = 46;
  const cx = ARROW_W / 2;
  const pts = [
    [cx - shaftW / 2, o],
    [cx + shaftW / 2, o],
    [cx + shaftW / 2, ARROW_H - headH],
    [ARROW_W - o, ARROW_H - headH],
    [cx, ARROW_H - o * 1.6],
    [o, ARROW_H - headH],
    [cx - shaftW / 2, ARROW_H - headH],
  ]
    .map(([x, y]) => `${x},${y}`)
    .join(' ');
  return (
    <svg width={ARROW_W} height={ARROW_H} viewBox={`0 0 ${ARROW_W} ${ARROW_H}`} style={{display: 'block', overflow: 'visible'}}>
      <polygon points={pts} fill={COLORS.orange} stroke={COLORS.navy} strokeWidth={OUTLINE} strokeLinejoin="miter" />
    </svg>
  );
};

/**
 * "तो नीचे Learn more दबा" — LEARN MORE tag (white 900 on orange) with an orange arrow bouncing
 * exactly 3 times towards Instagram's CTA button; lives at y 1310–1478 while captions are raised
 * (bottom edge 1290). Holds until the orange wipe; a small pulse on "register".
 */
export const LearnMore: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < LM_IN) return null;

  const labelIn = spring({frame: frame - LM_IN, fps, config: SPRING_OVERSHOOT});
  const labelScale = interpolate(labelIn, [0, 1], [0.55, 1]);
  const labelOpacity = interpolate(frame, [LM_IN, LM_IN + 3], [0, 1], clamp);

  const arrowIn = spring({frame: frame - LM_IN - 3, fps, config: {...SPRING_FIRM, overshootClamping: true}, durationInFrames: 7});
  const arrowOpacity = interpolate(frame, [LM_IN + 3, LM_IN + 6], [0, 1], clamp);
  const arrowDrop = (1 - arrowIn) * -(ARROW_H - TUCK);

  // Exactly BOUNCE_COUNT bounces (down-and-back), then rest.
  const t = frame - BOUNCE_START;
  const bounce = t >= 0 && t < BOUNCE_COUNT * BOUNCE_PERIOD ? BOUNCE_AMP * Math.abs(Math.sin((Math.PI * t) / BOUNCE_PERIOD)) : 0;

  // "register" pulse.
  const pt = frame - PULSE_AT;
  const pulse = pt >= 0 && pt <= 8 ? 1 + 0.07 * Math.sin((Math.PI * pt) / 8) : 1;


  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: 540 - ARROW_W / 2,
          top: ARROW_REST_TOP,
          width: ARROW_W,
          height: ARROW_H,
          opacity: arrowOpacity,
          transform: `translateY(${arrowDrop + bounce}px)`,
        }}
      >
        <DownArrow />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: LM_BLOCK.y1,
          height: LABEL_H,
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            height: LABEL_H,
            display: 'flex',
            alignItems: 'center',
            padding: '0 40px',
            backgroundColor: COLORS.orange,
            color: COLORS.white,
            fontFamily: FONT_STACK,
            fontWeight: 900,
            fontSize: LABEL_SIZE,
            letterSpacing: '0.04em',
            lineHeight: 1,
            whiteSpace: 'nowrap',
            opacity: labelOpacity,
            transform: `scale(${labelScale * pulse})`,
          }}
        >
          LEARN MORE
        </div>
      </div>
    </>
  );
};
