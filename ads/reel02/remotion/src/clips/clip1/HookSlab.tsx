import {Wallet} from 'lucide-react';
import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SLAB_ROTATION_DEG, SPRING_OVERSHOOT} from '../../brand';
import {SLAB, SLAB_FONT, SLAB_OUT_END, SLAB_POS, SLAB_SIZE} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/**
 * Frame 0: navy slab (rotated -4°) sweeps in from the left carrying [Wallet] "POCKET MONEY खत्म?"
 * (white 900, "खत्म?" orange). "POCKET MONEY" pops on the spoken words, "खत्म?" punches on "खत्म";
 * the slab slides out right just before the calendar card lands on "बीस".
 */
export const HookSlab: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame >= SLAB_OUT_END) return null;

  const s = SLAB_POS.scale;
  const cx = (SLAB_POS.x1 + SLAB_POS.x2) / 2;
  const cy = (SLAB_POS.y1 + SLAB_POS.y2) / 2;
  const travel = 1080 / 2 + (SLAB_SIZE.w * s) / 2 + 80;

  const expoOut = Easing.bezier(0.16, 1, 0.3, 1);
  const pIn = interpolate(frame, [SLAB.inStart - SLAB.lead, SLAB.inStart + SLAB.inFrames], [0, 1], {...clamp, easing: expoOut});
  const pOut = interpolate(frame, [SLAB.outStart, SLAB_OUT_END], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  const slabX = (pIn - 1) * travel + pOut * travel;
  const pText = interpolate(frame, [SLAB.inStart, SLAB.inStart + SLAB.inFrames + 2], [0, 1], {...clamp, easing: expoOut});
  const textX = (1 - pText) * -160;

  const iconIn = spring({frame: frame - 2, fps, config: SPRING_OVERSHOOT});
  const iconRot = interpolate(iconIn, [0, 1], [-24, 0]);
  const bump = (at: number, amt: number) =>
    interpolate(frame, [at - 1, at + 2, at + 8], [1, 1 + amt, 1], {...clamp, easing: Easing.out(Easing.quad)});
  const pocket = bump(SLAB.pocketAt, 0.06);
  const khatam = bump(SLAB.pulseAt, 0.12);

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: cx - SLAB_SIZE.w / 2,
          top: cy - SLAB_SIZE.h / 2,
          width: SLAB_SIZE.w,
          height: SLAB_SIZE.h,
          transform: `translateX(${slabX}px) rotate(${SLAB_ROTATION_DEG}deg) scale(${s})`,
          transformOrigin: '50% 50%',
          backgroundColor: COLORS.navy,
          borderRadius: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'visible',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 20,
            transform: `translateX(${textX}px)`,
            fontFamily: FONT_STACK,
            fontWeight: 900,
            fontSize: SLAB_FONT,
            lineHeight: 1,
            color: COLORS.white,
            whiteSpace: 'nowrap',
          }}
        >
          <Wallet
            size={78}
            color={COLORS.orange}
            strokeWidth={2.6}
            style={{flex: 'none', transform: `rotate(${iconRot}deg)`, transformOrigin: '50% 90%'}}
          />
          <span style={{display: 'inline-block', letterSpacing: '-0.01em', transform: `scale(${pocket})`}}>POCKET MONEY</span>
          <span
            style={{
              display: 'inline-block',
              color: COLORS.orange,
              transform: `scale(${khatam})`,
              transformOrigin: '10% 55%',
              marginLeft: 4,
            }}
          >
            खत्म?
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
