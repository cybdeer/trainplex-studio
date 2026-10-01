import {Clock, Smartphone} from 'lucide-react';
import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SPRING, SPRING_OVERSHOOT} from '../../brand';
import {CARD} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const {x1, y1, x2, y2} = CARD.box;
const CARD_W = x2 - x1; // 240
const CARD_H = y2 - y1; // 240

const COUNT_FROM = 500;
const COUNT_FONT = 72; // "₹500" fits the 240 px card at this size (tabular figures, no jitter)
const SLAM_FONT = 140; // "₹0" slams up to this once the count lands

/** Front face: flat phone icon + orange clock + "4 HRS". */
const HoursFace: React.FC<{frame: number; fps: number}> = ({frame, fps}) => {
  // no opacity fades (flat, opaque graphics): the icon scales up, the text row rises out of a mask
  const icon = spring({frame: frame - CARD.inAt + 1, fps, config: SPRING_OVERSHOOT});
  const row = Math.min(1, spring({frame: frame - (CARD.inAt + 1), fps, config: SPRING}));
  const ROW_H = 64;
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        paddingBottom: 8, // optical centring: the text row carries descender space below the caps
        boxSizing: 'border-box',
      }}
    >
      <div style={{transform: `scale(${icon})`}}>
        <Smartphone size={104} color={COLORS.navy} strokeWidth={2.3} style={{display: 'block'}} />
      </div>
      <div style={{height: ROW_H, overflow: 'hidden'}}>
        <div
          style={{
            height: ROW_H,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            transform: `translateY(${(1 - row) * ROW_H}px)`,
          }}
        >
          <Clock size={40} color={COLORS.orange} strokeWidth={3} style={{display: 'block', flex: 'none'}} />
          <span
            style={{
              fontFamily: FONT_STACK,
              fontWeight: 900,
              fontSize: 56,
              lineHeight: 1,
              color: COLORS.navy,
              letterSpacing: '-0.01em',
              whiteSpace: 'nowrap',
            }}
          >
            4 HRS
          </span>
        </div>
      </div>
    </div>
  );
};

/** Back face: orange "₹500 … ₹0" count-down that slams up big on ₹0. */
const RupeeFace: React.FC<{frame: number}> = ({frame}) => {
  const t = interpolate(frame, [CARD.countStart, CARD.countStart + CARD.countFrames], [0, 1], {
    ...clamp,
    easing: Easing.out(Easing.quad),
  });
  const value = Math.round(COUNT_FROM * (1 - t));
  // ₹0 lands → slams up (4 frames, slight overshoot) while the punch-in zoom is still held
  const land = CARD.countStart + CARD.countFrames;
  const slam = interpolate(frame, [land, land + 4], [0, 1], {...clamp, easing: Easing.out(Easing.back(1.6))});
  const fontSize = value === 0 ? COUNT_FONT + (SLAM_FONT - COUNT_FONT) * slam : COUNT_FONT;
  return (
    <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      <span
        style={{
          fontFamily: FONT_STACK,
          fontWeight: 900,
          fontSize,
          lineHeight: 1,
          color: COLORS.orange,
          fontVariantNumeric: 'tabular-nums',
          letterSpacing: '-0.02em',
          whiteSpace: 'nowrap',
        }}
      >
        ₹{value}
      </span>
    </div>
  );
};

/**
 * Top-right icon card (x 760–1000, y 300–540). Pops on "चार घंटे reels" as "4 HRS", flips into
 * the orange ₹ counter on "Zero!", and slides out right on "वही".
 */
export const StatCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < CARD.inAt || frame >= CARD.outAt + CARD.outFrames) return null;

  // entrance: opaque pop 0.3 → 1 (overshoot peaks ≈ 1.14 → still inside x ≤ 1020). The spring is
  // phase-led by 2 frames so it is already moving fast on the cue frame (springs start at rest).
  const pop = spring({frame: frame - CARD.inAt + 2, fps, config: SPRING});
  const scaleIn = interpolate(pop, [0, 1], [0.3, 1]);

  // flip: front turns away 0 → 80°, faces swap exactly on "Zero!" (back already readable at -65°,
  // showing ₹500) and settle -65° → 0. No frame is edge-on/blank.
  const a = CARD.flipMid - CARD.flipHalf;
  const b = CARD.flipMid;
  const c = CARD.flipMid + CARD.flipHalf;
  const back = frame >= b;
  const rotY = back
    ? interpolate(frame, [b, c], [-65, 0], {...clamp, easing: Easing.out(Easing.cubic)})
    : interpolate(frame, [a, b], [0, 80], {...clamp, easing: Easing.in(Easing.quad)});

  // snappy exit to the right (accelerating, visible travel on every frame)
  const pOut = interpolate(frame, [CARD.outAt, CARD.outAt + CARD.outFrames], [0, 1], {
    ...clamp,
    easing: Easing.in(Easing.quad),
  });
  const exitX = pOut * (1080 - x1 + 40);

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: x1,
          top: y1,
          width: CARD_W,
          height: CARD_H,
          transform: `translateX(${exitX}px) perspective(900px) rotateY(${rotY}deg) scale(${scaleIn})`,
          transformOrigin: '50% 50%',
          backgroundColor: COLORS.white,
          border: `2px solid ${COLORS.border}`,
          borderRadius: 0,
          boxSizing: 'border-box',
          overflow: 'hidden',
        }}
      >
        {back ? <RupeeFace frame={frame} /> : <HoursFace frame={frame} fps={fps} />}
      </div>
    </AbsoluteFill>
  );
};
