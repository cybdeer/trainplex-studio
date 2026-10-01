import {ArrowDown, ArrowRight} from 'lucide-react';
import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SPRING, SPRING_FIRM, SPRING_OVERSHOOT} from '../brand';
import {Logo, OrangeBadge} from '../components/primitives';
import {END_SCREEN_FRAMES} from '../timeline';
import {
  CHIP_ROW_Y,
  CHIP_SIZE,
  CTA_H,
  CTA_PULSE_LEN,
  CTA_PULSE_PERIOD,
  CTA_PULSE_SCALE,
  CTA_SLIDE_FRAMES,
  CTA_SLIDE_STRETCH,
  CTA_TOP,
  CX,
  GRID_CELL,
  GRID_LINE,
  GRID_OPACITY,
  H,
  HEADLINE_SIZE,
  HEADLINE_Y,
  LEARN_Y1,
  LEARN_Y2,
  LOGO_H,
  LOGO_TOP,
  LOGO_W,
  STRIPE_V_GAP,
  STRIPE_V_THICK,
  SUB_SIZE,
  SUB_Y,
  T,
  UNDERLINE_H,
  UNDERLINE_TOP,
  UNDERLINE_W,
  W,
  WEDGE_LEFT_Y,
  WEDGE_SLOPE,
} from './geometry';

/** Local frame on which the CTA bar lands (for the audio/SFX log). */
export const CTA_LAND_FRAME = 57; // = T.cta (50) + CTA_SLIDE_FRAMES (7) — keep in sync with geometry.ts

if (CTA_LAND_FRAME !== T.cta + CTA_SLIDE_FRAMES) {
  throw new Error('EndScreen: CTA_LAND_FRAME out of sync with geometry.ts (T.cta + CTA_SLIDE_FRAMES)');
}

const clamp01 = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// ─── Background: cream + faint 44 px grid ────────────────────────────────────────────────
const Backdrop: React.FC = () => {
  // Offset so a vertical grid line runs through the centre axis (x = 540).
  const ox = CX % GRID_CELL;
  const oy = CTA_TOP % GRID_CELL;
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.cream}}>
      <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
        <defs>
          <pattern id="es-grid" x={ox} y={oy} width={GRID_CELL} height={GRID_CELL} patternUnits="userSpaceOnUse">
            {/* lines drawn 1 px inside the tile so the full 2 px stroke survives pattern clipping */}
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

// ─── Navy wedge + parallel orange bar, rising in from the bottom-left ────────────────────────
const Wedge: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pW = spring({frame: frame - T.wedge, fps, config: SPRING_FIRM, durationInFrames: 16});
  const pS = spring({frame: frame - T.stripe, fps, config: SPRING_FIRM, durationInFrames: 16});
  const rise = (p: number) => `translateY(${(1 - p) * 600}px)`;
  // Each shape is ONE polygon extended far past the canvas (no seams, no exposed ends while it
  // travels/overshoots). Edge: y = base + x * tan(18°), falling to the right.
  const M = 700;
  const edge = (x: number, base: number) => base + x * WEDGE_SLOPE;
  const wedge = [
    [-M, edge(-M, WEDGE_LEFT_Y)],
    [W + M, edge(W + M, WEDGE_LEFT_Y)],
    [W + M, H + M + 600],
    [-M, H + M + 600],
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

// ─── Logo + orange underline ───────────────────────────────────────────────────────────
const LogoBlock: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - T.logo, fps, config: SPRING_OVERSHOOT});
  const scale = 0.85 + 0.15 * p;
  const draw = spring({frame: frame - T.underline, fps, config: SPRING_FIRM, durationInFrames: 12});
  const drawClamped = Math.min(1, draw);
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: CX - LOGO_W / 2,
          top: LOGO_TOP,
          width: LOGO_W,
          height: LOGO_H,
          transform: `scale(${scale})`,
          transformOrigin: '50% 50%',
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
          transform: `scaleX(${drawClamped})`,
          transformOrigin: '0% 50%',
        }}
      />
    </>
  );
};

// ─── Centred text line (box centred on y) ─────────────────────────────────────────────────
const TextLine: React.FC<{
  y: number;
  size: number;
  weight: 700 | 800 | 900;
  start: number;
  travel: number;
  children: React.ReactNode;
}> = ({y, size, weight, start, travel, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - start, fps, config: SPRING});
  const opacity = interpolate(frame, [start, start + 8], [0, 1], clamp01);
  const lh = 1.2;
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
        fontWeight: weight,
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

// ─── Chips ─────────────────────────────────────────────────────────────────────────────
const Chip: React.FC<{start: number; children: React.ReactNode}> = ({start, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - start, fps, config: SPRING_OVERSHOOT});
  const opacity = interpolate(frame, [start, start + 3], [0, 1], clamp01);
  return (
    <OrangeBadge
      fontSize={CHIP_SIZE}
      style={{
        opacity,
        transform: `rotate(-4deg) scale(${p})`,
        padding: '8px 20px',
        lineHeight: 1.2,
      }}
    >
      {children}
    </OrangeBadge>
  );
};

const ChipRow: React.FC<{y: number; children: React.ReactNode}> = ({y, children}) => (
  <div
    style={{
      position: 'absolute',
      left: 60,
      width: 960,
      top: y - 40,
      height: 80,
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      gap: 22,
    }}
  >
    {children}
  </div>
);

// ─── CTA bar ───────────────────────────────────────────────────────────────────────────
// 58 px requested; the full line is ≈ 1086 px wide at 58/800 with default tracking, so tracking
// and gaps were tightened first and the size reduced minimally to fit x 60–1020 (see report).
const CTA_SIZE = 53;
const CTA_TRACKING = -0.03; // em
const CTA_ARROW_GAP = 16; // visible gap between words and the arrow's ink

const CtaBar: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const raw = spring({frame: frame - T.cta, fps, config: SPRING_FIRM, durationInFrames: CTA_SLIDE_STRETCH});
  const p = frame >= CTA_LAND_FRAME ? 1 : Math.min(1, raw);
  const y = (1 - p) * (H - CTA_TOP);
  // Pulse 1.0 -> 1.03 -> 1.0 at landing and every 20 frames after.
  // The pulse that would be cut off by the end of the screen is shortened so it completes on the
  // last frame (final frame at rest).
  let scale = 1;
  if (frame >= CTA_LAND_FRAME) {
    const since = frame - CTA_LAND_FRAME;
    const pulseStart = CTA_LAND_FRAME + Math.floor(since / CTA_PULSE_PERIOD) * CTA_PULSE_PERIOD;
    const len = Math.min(CTA_PULSE_LEN, END_SCREEN_FRAMES - 1 - pulseStart);
    const t = frame - pulseStart;
    if (len > 0 && t < len) scale = 1 + CTA_PULSE_SCALE * Math.sin((Math.PI * t) / len);
  }
  // lucide ArrowRight ink spans x 5–19 of its 24-unit box -> trim the side padding with margins.
  const iconSize = Math.round(CTA_SIZE * 0.9);
  const iconPad = (iconSize * 5) / 24;
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: CTA_TOP,
        width: W,
        height: CTA_H,
        backgroundColor: COLORS.navy,
        transform: `translateY(${y}px) scale(${scale})`,
        transformOrigin: '50% 50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          fontFamily: FONT_STACK,
          fontSize: CTA_SIZE,
          fontWeight: 800,
          letterSpacing: `${CTA_TRACKING}em`,
          lineHeight: 1,
          whiteSpace: 'nowrap',
          color: COLORS.cream,
        }}
      >
        <span>Register free</span>
        <ArrowRight
          size={iconSize}
          color={COLORS.cream}
          strokeWidth={3.2}
          style={{flex: 'none', margin: `0 ${CTA_ARROW_GAP - iconPad}px`}}
        />
        <span>
          trainplex<span style={{color: COLORS.orange}}>.info/register</span>
        </span>
      </div>
    </div>
  );
};

// ─── Learn more ────────────────────────────────────────────────────────────────────────
const LearnMore: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - T.learn, fps, config: SPRING});
  const opacity = interpolate(frame, [T.learn, T.learn + 6], [0, 1], clamp01);
  const bounce = frame >= T.learn ? Math.abs(Math.sin(((frame - T.learn) * Math.PI) / 14)) * 8 : 0;
  return (
    <div
      style={{
        position: 'absolute',
        left: 60,
        width: 960,
        top: LEARN_Y1,
        height: LEARN_Y2 - LEARN_Y1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        opacity,
        transform: `translateY(${(1 - p) * 16}px)`,
      }}
    >
      <div style={{transform: `translateY(${bounce - 4}px)`, display: 'flex'}}>
        <ArrowDown size={40} color={COLORS.orange} strokeWidth={3.5} />
      </div>
      <span
        style={{
          fontFamily: FONT_STACK,
          fontSize: 36,
          fontWeight: 700,
          lineHeight: 1.2,
          color: COLORS.cream,
        }}
      >
        Learn more
      </span>
    </div>
  );
};

/** Animated logo CTA end screen — 105 frames (3.5 s). */
export const EndScreen: React.FC = () => {
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.cream, overflow: 'hidden'}}>
      <Backdrop />
      <Wedge />
      <LogoBlock />
      <TextLine y={HEADLINE_Y} size={HEADLINE_SIZE} weight={900} start={T.headline} travel={60}>
        <span style={{color: COLORS.orange}}>AI</span> TRAINER बनें
      </TextLine>
      <TextLine y={SUB_Y} size={SUB_SIZE} weight={700} start={T.sub} travel={40}>
        घर बैठे · Phone से · Paid tasks
      </TextLine>
      <ChipRow y={CHIP_ROW_Y[0]}>
        <Chip start={T.chips[0]}>FREE REGISTRATION</Chip>
        <Chip start={T.chips[1]}>FREE TRAINING</Chip>
      </ChipRow>
      <ChipRow y={CHIP_ROW_Y[1]}>
        <Chip start={T.chips[2]}>BANK / UPI PAYMENT</Chip>
      </ChipRow>
      <CtaBar />
      <LearnMore />
    </AbsoluteFill>
  );
};

