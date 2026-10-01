// End-screen layout + timing constants (local frames, 30 fps). Single source for EndScreen.tsx,
// so the final geometry can be reported/QA'd from one place. The end screen's LENGTH is a timeline
// parameter (timeline.ts END_SCREEN_FRAMES, 90–120 f); everything here lands by frame ~45 so the
// shortest legal end screen still holds the finished layout for ≥ 1.5 s.
import {LOGO_ASPECT} from '../brand';

export const W = 1080;
export const H = 1920;
export const CX = W / 2;

// ─── Logo (real stacked lockup, 862x956 with a 24 px transparent margin on every side) ───────
export const LOGO_W = 400;
export const LOGO_H = LOGO_W / LOGO_ASPECT;
export const LOGO_TOP = 250;
const LOGO_INK_TOP_FRAC = 24 / 956;
const LOGO_INK_BOTTOM_FRAC = 932 / 956;
export const LOGO_INK_TOP = LOGO_TOP + LOGO_H * LOGO_INK_TOP_FRAC;
export const LOGO_INK_BOTTOM = LOGO_TOP + LOGO_H * LOGO_INK_BOTTOM_FRAC;

// Orange underline bar (220 x 10) under the logo.
export const UNDERLINE_W = 220;
export const UNDERLINE_H = 10;
export const UNDERLINE_GAP = 24; // from the logo's visible ink bottom
export const UNDERLINE_TOP = Math.round(LOGO_INK_BOTTOM + UNDERLINE_GAP);

// ─── Text lines (y = vertical centre of the line box) ─────────────────────────────────────
/** Line 1 "पढ़ाई के साथ कमाई". */
export const LINE1_Y = 838;
export const LINE1_SIZE = 96;
/** Line 2 "TrainPlex". */
export const LINE2_Y = 960;
export const LINE2_SIZE = 76;

// ─── Navy wedge (12°, anchored left) + parallel 12 px orange bar ────────────────────────────
export const WEDGE_ANGLE_DEG = 12;
export const WEDGE_SLOPE = Math.tan((WEDGE_ANGLE_DEG * Math.PI) / 180); // ≈ 0.2126
export const WEDGE_LEFT_Y = 1080; // top edge at x = 0; falls to ≈ 1310 at x = 1080
export const WEDGE_RIGHT_Y = WEDGE_LEFT_Y + W * WEDGE_SLOPE;
export const STRIPE_THICKNESS = 12; // perpendicular to the edge
export const STRIPE_GAP = 14;
const COS = Math.cos((WEDGE_ANGLE_DEG * Math.PI) / 180);
export const STRIPE_V_GAP = STRIPE_GAP / COS;
export const STRIPE_V_THICK = STRIPE_THICKNESS / COS;

// ─── "Learn more" CTA button (on the navy wedge, fully below its edge) ───────────────────────
export const CTA_W = 640;
export const CTA_H = 136;
export const CTA_Y = 1376; // centre; top 1308 ≥ wedge edge at the button's right corner (≈ 1253)
export const CTA_SIZE = 66;

// ─── Grid ──────────────────────────────────────────────────────────────────────────────
export const GRID_CELL = 44;
export const GRID_OPACITY = 0.08;
export const GRID_LINE = 2;

// ─── Timing (local frames) ───────────────────────────────────────────────────────────────
export const T = {
  wedge: 0,
  stripe: 2,
  logo: 0,
  underline: 5,
  line1: 12,
  line2: 20,
  cta: 28,
  arrow: 40,
} as const;

// CTA slide: SPRING_FIRM stretched to 26 frames; it first reaches rest 7 frames after it starts
// and is held there — that is the "landing" (used for the ding SFX).
export const CTA_SLIDE_STRETCH = 26;
export const CTA_SLIDE_FRAMES = 7;
export const CTA_PULSE_PERIOD = 20;
export const CTA_PULSE_LEN = 10;
export const CTA_PULSE_SCALE = 0.03;
