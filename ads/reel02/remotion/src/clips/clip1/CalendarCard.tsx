import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SPRING} from '../../brand';
import {CAL, CAL_GONE, CAL_POS, CAL_SIZE} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const {w: CW, h: CH} = CAL_SIZE;
const HEADER_H = 64;
const RING = 18; // binder squares on the header
const NUM_SIZE = 150;
const CIRCLE_R = 92;
const CIRCLE_STROKE = 11;
const STRIKE_STROKE = 14;

/**
 * Calendar card (white, 2 px border, sharp corners, navy header): pops on "बीस", an orange circle
 * draws around "20" while "बीस" is spoken, then an orange strike-through slashes it on "तारीख … तक".
 * Exits on "क्योंकि". Position/size from the face track (CAL_POS).
 */
export const CalendarCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < CAL.inAt || frame >= CAL_GONE) return null;

  const pop = spring({frame: frame - CAL.inAt + 2, fps, config: SPRING});
  const scaleIn = interpolate(pop, [0, 1], [0.35, 1]);
  const pOut = interpolate(frame, [CAL.outAt, CAL_GONE], [0, 1], {...clamp, easing: Easing.in(Easing.quad)});
  const exitY = pOut * 60;
  const exitO = 1 - pOut;

  const circle = interpolate(frame, [CAL.circleFrom, CAL.circleTo], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const strike = interpolate(frame, [CAL.strikeFrom, CAL.strikeTo], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const circ = 2 * Math.PI * CIRCLE_R;

  const bodyCy = HEADER_H + (CH - HEADER_H) / 2;
  const sx1 = CW / 2 - 104;
  const sy1 = bodyCy + 70;
  const sx2 = CW / 2 + 104;
  const sy2 = bodyCy - 70;
  const sLen = Math.hypot(sx2 - sx1, sy2 - sy1);

  const s = CAL_POS.scale;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: CAL_POS.x1,
          top: CAL_POS.y1,
          width: CW,
          height: CH,
          transformOrigin: '0 0',
          transform: `scale(${s})`,
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            transform: `translateY(${exitY}px) scale(${scaleIn})`,
            transformOrigin: '50% 50%',
            opacity: exitO,
            backgroundColor: COLORS.white,
            border: `2px solid ${COLORS.border}`,
            boxSizing: 'border-box',
            borderRadius: 0,
          }}
        >
          <div style={{position: 'absolute', left: -2, right: -2, top: -2, height: HEADER_H, backgroundColor: COLORS.navy}}>
            {[0.3, 0.7].map((k) => (
              <div
                key={k}
                style={{
                  position: 'absolute',
                  left: CW * k - RING / 2,
                  top: (HEADER_H - RING) / 2,
                  width: RING,
                  height: RING,
                  backgroundColor: COLORS.orange,
                }}
              />
            ))}
          </div>
          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              top: HEADER_H,
              bottom: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: FONT_STACK,
              fontWeight: 900,
              fontSize: NUM_SIZE,
              lineHeight: 1,
              color: COLORS.navy,
              letterSpacing: '-0.03em',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            20
          </div>
          <svg width={CW} height={CH} style={{position: 'absolute', left: -2, top: -2, overflow: 'visible'}}>
            <circle
              cx={CW / 2}
              cy={bodyCy}
              r={CIRCLE_R}
              fill="none"
              stroke={COLORS.orange}
              strokeWidth={CIRCLE_STROKE}
              strokeDasharray={circ}
              strokeDashoffset={circ * (1 - circle)}
              transform={`rotate(-110 ${CW / 2} ${bodyCy})`}
            />
            <line
              x1={sx1}
              y1={sy1}
              x2={sx1 + (sx2 - sx1) * strike}
              y2={sy1 + (sy2 - sy1) * strike}
              stroke={COLORS.orange}
              strokeWidth={STRIKE_STROKE}
              strokeLinecap="butt"
              opacity={strike > 0 ? 1 : 0}
              data-len={sLen}
            />
          </svg>
        </div>
      </div>
    </AbsoluteFill>
  );
};
