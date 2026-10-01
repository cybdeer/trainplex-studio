import {ArrowDown} from 'lucide-react';
import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SAFE, SPRING, SPRING_FIRM, SPRING_OVERSHOOT} from '../brand';
import {Logo} from '../components/primitives';
import {END_SCREEN_FRAMES, END_SCREEN_MIN} from '../timeline';
import {
  CTA_H,
  CTA_PULSE_LEN,
  CTA_PULSE_PERIOD,
  CTA_PULSE_SCALE,
  CTA_SIZE,
  CTA_SLIDE_FRAMES,
  CTA_SLIDE_STRETCH,
  CTA_W,
  CTA_Y,
  CX,
  GRID_CELL,
  GRID_LINE,
  GRID_OPACITY,
  H,
  LINE1_SIZE,
  LINE1_Y,
  LINE2_SIZE,
  LINE2_Y,
  LOGO_H,
  LOGO_TOP,
  LOGO_W,
  STRIPE_V_GAP,
  STRIPE_V_THICK,
  T,
  UNDERLINE_H,
  UNDERLINE_TOP,
  UNDERLINE_W,
  W,
  WEDGE_LEFT_Y,
  WEDGE_SLOPE,
} from './geometry';

/** Local frame on which the CTA button lands (for the audio/SFX log). */
export const CTA_LAND_FRAME = T.cta + CTA_SLIDE_FRAMES; // 35

if (CTA_LAND_FRAME + 30 > END_SCREEN_MIN) {
  throw new Error('EndScreen: the CTA must land ≥ 1 s before the shortest legal end screen ends');
}

const clamp01 = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// ─── Background: cream + faint 44 px grid ────────────────────────────────────────────────
const Backdrop: React.FC = () => {
  const ox = CX % GRID_CELL;
  const oy = WEDGE_LEFT_Y % GRID_CELL;
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.cream}}>
      <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
        <defs>
          <pattern id="es-grid" x={ox} y={oy} width={GRID_CELL} height={GRID_CELL} patternUnits="userSpaceOnUse">
            <path
              d={`M ${GRID_CELL} ${GRID_LINE / 2} L ${GRID_LINE / 2} ${GRID_LINE / 2} ${GRID_LINE / 2} ${GRID_CELL}`}
              fill="none"
              stroke={COLORS.border}
              strokeWidth={GRID_LINE}
            />
          </pattern>
        </defs>
        <rect width={W} height={H} fill="url(#es-grid)" opacity={GRID_OPACITY} />
      </svg>
    </AbsoluteFill>
  );
};

// ─── Navy wedge + parallel orange bar, rising in from the bottom ─────────────────────────────
const Wedge: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pW = spring({frame: frame - T.wedge, fps, config: SPRING_FIRM, durationInFrames: 16});
  const pS = spring({frame: frame - T.stripe, fps, config: SPRING_FIRM, durationInFrames: 16});
  const rise = (p: number) => `translateY(${(1 - p) * 700}px)`;
  const M = 700;
  const edge = (x: number, base: number) => base + x * WEDGE_SLOPE;
  const wedge = [
    [-M, edge(-M, WEDGE_LEFT_Y)],
    [W + M, edge(W + M, WEDGE_LEFT_Y)],
    [W + M, H + M + 700],
    [-M, H + M + 700],
  ];
  const sTop = WEDGE_LEFT_Y - STRIPE_V_GAP - STRIPE_V_THICK;
  const sBot = WEDGE_LEFT_Y - STRIPE_V_GAP;
  const stripe = [
    [-M, edge(-M, sTop)],
    [W + M, edge(W + M, sTop)],
    [W + M, edge(W + M, sBot)],
    [-M, edge(-M, sBot)],
  ];
  const pts = (arr: number[][]) => arr.map(([x, y]) => `${x},${y}`).join(' ');
  return (
    <AbsoluteFill>
      <svg width={W} height={H} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
        <polygon points={pts(stripe)} fill={COLORS.orange} style={{transform: rise(pS)}} />
        <polygon points={pts(wedge)} fill={COLORS.navy} style={{transform: rise(pW)}} />
      </svg>
    </AbsoluteFill>
  );
};

// ─── Animated logo + orange underline ──────────────────────────────────────────────────
const LogoBlock: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - T.logo, fps, config: SPRING_OVERSHOOT});
  const scale = 0.82 + 0.18 * p;
  const rise = (1 - Math.min(1, p)) * 40;
  // gentle breathing after it lands keeps the logo alive across a 3–4 s hold
  const breathe = 1 + 0.012 * Math.sin(Math.max(0, frame - 20) / 9);
  const draw = Math.min(1, spring({frame: frame - T.underline, fps, config: SPRING_FIRM, durationInFrames: 12}));
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: CX - LOGO_W / 2,
          top: LOGO_TOP,
          width: LOGO_W,
          height: LOGO_H,
          transform: `translateY(${rise}px) scale(${scale * breathe})`,
          transformOrigin: '50% 50%',
          opacity: interpolate(frame, [0, 3], [0, 1], clamp01),
        }}
      >
        <Logo width={LOGO_W} />
      </div>
      <div
        style={{
          position: 'absolute',
          left: CX - UNDERLINE_W / 2,
          top: UNDERLINE_TOP,
          width: UNDERLINE_W,
          height: UNDERLINE_H,
          backgroundColor: COLORS.orange,
          transform: `scaleX(${draw})`,
          transformOrigin: '0% 50%',
        }}
      />
    </>
  );
};

// ─── Centred text line (box centred on y) ─────────────────────────────────────────────────
const TextLine: React.FC<{y: number; size: number; start: number; travel: number; children: React.ReactNode}> = ({
  y,
  size,
  start,
  travel,
  children,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - start, fps, config: SPRING});
  const opacity = interpolate(frame, [start, start + 8], [0, 1], clamp01);
  const lh = 1.3;
  return (
    <div
      style={{
        position: 'absolute',
        left: 60,
        width: 960,
        top: y - (size * lh) / 2,
        height: size * lh,
        textAlign: 'center',
        fontFamily: FONT_STACK,
        fontSize: size,
        fontWeight: 900,
        lineHeight: lh,
        color: COLORS.navy,
        whiteSpace: 'nowrap',
        opacity,
        transform: `translateY(${(1 - p) * travel}px)`,
      }}
    >
      {children}
    </div>
  );
};

// ─── "Learn more" CTA button ────────────────────────────────────────────────────────────
const CtaButton: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const raw = spring({frame: frame - T.cta, fps, config: SPRING_FIRM, durationInFrames: CTA_SLIDE_STRETCH});
  const p = frame >= CTA_LAND_FRAME ? 1 : Math.min(1, raw);
  const y = (1 - p) * (H - (CTA_Y - CTA_H / 2));
  // Pulse 1.0 -> 1.03 -> 1.0 at landing and every 20 frames; the last pulse completes on the last frame.
  let scale = 1;
  if (frame >= CTA_LAND_FRAME) {
    const since = frame - CTA_LAND_FRAME;
    const pulseStart = CTA_LAND_FRAME + Math.floor(since / CTA_PULSE_PERIOD) * CTA_PULSE_PERIOD;
    const len = Math.min(CTA_PULSE_LEN, END_SCREEN_FRAMES - 1 - pulseStart);
    const t = frame - pulseStart;
    if (len > 0 && t < len) scale = 1 + CTA_PULSE_SCALE * Math.sin((Math.PI * t) / len);
  }
  const arrowIn = spring({frame: frame - T.arrow, fps, config: SPRING_OVERSHOOT});
  const bounce = frame >= T.arrow ? Math.abs(Math.sin(((frame - T.arrow) * Math.PI) / 14)) * 10 : 0;
  const iconSize = Math.round(CTA_SIZE * 0.95);
  return (
    <div
      style={{
        position: 'absolute',
        left: CX - CTA_W / 2,
        top: CTA_Y - CTA_H / 2,
        width: CTA_W,
        height: CTA_H,
        backgroundColor: COLORS.orange,
        transform: `translateY(${y}px) scale(${scale})`,
        transformOrigin: '50% 50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 22,
        borderRadius: 0,
      }}
    >
      <span
        style={{
          fontFamily: FONT_STACK,
          fontSize: CTA_SIZE,
          fontWeight: 900,
          lineHeight: 1,
          letterSpacing: '-0.01em',
          whiteSpace: 'nowrap',
          color: COLORS.white,
        }}
      >
        Learn more
      </span>
      <div style={{display: 'flex', transform: `translateY(${bounce - 4}px) scale(${Math.min(1.1, arrowIn)})`}}>
        <ArrowDown size={iconSize} color={COLORS.white} strokeWidth={3.4} />
      </div>
    </div>
  );
};

/**
 * Animated logo CTA end screen (length = timeline END_SCREEN_FRAMES, 3.0–4.0 s): cream + grid,
 * navy wedge with orange bar, real logo springs in with an underline, line 1 "पढ़ाई के साथ कमाई",
 * line 2 "TrainPlex", and an orange "Learn more" button (down-arrow) that lands and pulses.
 */
export const EndScreen: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: COLORS.cream, overflow: 'hidden'}}>
    <Backdrop />
    <Wedge />
    <LogoBlock />
    <TextLine y={LINE1_Y} size={LINE1_SIZE} start={T.line1} travel={60}>
      पढ़ाई के साथ <span style={{color: COLORS.orange}}>कमाई</span>
    </TextLine>
    <TextLine y={LINE2_Y} size={LINE2_SIZE} start={T.line2} travel={40}>
      TrainPlex
    </TextLine>
    {/* Safe-zone clip (QA check 5): the button rises into view at y 1480, never below the safe zone. */}
    <AbsoluteFill style={{clipPath: `inset(${SAFE.y1}px ${1080 - SAFE.x2}px ${1920 - SAFE.y2}px ${SAFE.x1}px)`}}>
      <CtaButton />
    </AbsoluteFill>
  </AbsoluteFill>
);
