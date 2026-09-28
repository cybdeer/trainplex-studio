import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, SAFE} from '../brand';
import {Logo} from '../components/primitives';
import {CLIP1_WATERMARK_BLOCKED} from '../clips/Clip1';
import {CLIP2_WATERMARK_BLOCKED} from '../clips/Clip2';
import {CLIP3_WATERMARK_BLOCKED} from '../clips/Clip3';
import {CLIP_START, END_SCREEN_START, FPS, FrameInterval} from '../timeline';

// Global-frame intervals during which clip graphics occupy the watermark box.
const BLOCKED: FrameInterval[] = [
  ...CLIP1_WATERMARK_BLOCKED.map(([a, b]): FrameInterval => [CLIP_START[1] + a, CLIP_START[1] + b]),
  ...CLIP2_WATERMARK_BLOCKED.map(([a, b]): FrameInterval => [CLIP_START[2] + a, CLIP_START[2] + b]),
  ...CLIP3_WATERMARK_BLOCKED.map(([a, b]): FrameInterval => [CLIP_START[3] + a, CLIP_START[3] + b]),
];
const DUCK = 4; // frames
const WATERMARK_PAD = 8; // px cream plate around the 200 px logo

const duckFactor = (frame: number) => {
  let f = 1;
  for (const [a, b] of BLOCKED) {
    // fully hidden inside [a, b), 4-frame fade out before a and fade in after b
    const v = frame < a ? (a - frame) / DUCK : frame >= b ? (frame - b + 1) / DUCK : 0;
    f = Math.min(f, Math.min(1, Math.max(0, v)));
  }
  return f;
};

/** Thin progress bar at the top of the safe zone (y 220, 8 px): cream track 40 %, orange fill. */
export const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const p = Math.min(1, Math.max(0, frame / END_SCREEN_START));
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{position: 'absolute', left: 0, top: SAFE.y1, width: 1080, height: 8, backgroundColor: COLORS.cream, opacity: 0.4}} />
      <div style={{position: 'absolute', left: 0, top: SAFE.y1, width: 1080 * p, height: 8, backgroundColor: COLORS.orange}} />
    </AbsoluteFill>
  );
};

/**
 * Small real-logo watermark top-left (x 60, y 240, width 200, 85 %) from 1.0 s to the end screen.
 * It sits on a small cream plate for legibility and ducks out while a clip graphic occupies its
 * box (slabs/plates), so graphics never clash.
 */
export const Watermark: React.FC = () => {
  const frame = useCurrentFrame();
  const inAt = Math.round(1.0 * FPS);
  const opacity = interpolate(frame, [inAt, inAt + 6, END_SCREEN_START - 1, END_SCREEN_START], [0, 0.85, 0.85, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  if (frame < inAt || frame >= END_SCREEN_START) return null;
  const duck = duckFactor(frame);
  if (duck <= 0) return null;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {/* Cream plate (sharp corners) keeps the navy wordmark legible over dark hair/backgrounds. */}
      <div
        style={{
          position: 'absolute',
          left: 60,
          top: 240,
          padding: WATERMARK_PAD,
          backgroundColor: COLORS.cream,
          opacity: opacity * duck,
        }}
      >
        <Logo width={200} />
      </div>
    </AbsoluteFill>
  );
};

/** 4-frame white flash centred on each hard cut between clips (whoosh SFX only if supplied). */
export const JoinFlash: React.FC = () => {
  const frame = useCurrentFrame();
  const cuts = [CLIP_START[2], CLIP_START[3]];
  // frames cut-1, cut, cut+1, cut+2
  const curve = [0.55, 0.95, 0.5, 0.18];
  let opacity = 0;
  for (const c of cuts) {
    const k = frame - (c - 1);
    if (k >= 0 && k < curve.length) opacity = curve[k];
  }
  if (opacity === 0) return null;
  return <AbsoluteFill style={{backgroundColor: COLORS.white, opacity, pointerEvents: 'none'}} />;
};
