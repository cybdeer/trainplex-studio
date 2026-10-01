// End-screen layout + timing constants (local frames, 30 fps). Single source for EndScreen.tsx
// and its parts, so the final geometry can be reported/QA'd from one place.
import {LOGO_ASPECT} from '../brand';

export const W = 1080;
export const H = 1920;
export const CX = W / 2;

// ─── Logo (real stacked lockup, 862x956 with a 24 px transparent margin on every side) ───────
// Spec asked for 620 px wide centred at y 560 — impossible with a stacked lockup (it would be
// 688 px tall and collide with the headline). Sized so: box top >= 240, underline bar 24 px under
// the logo's visible ink, and >= 30 px clear above the headline's ink.
export const LOGO_W = 420;
export const LOGO_H = LOGO_W / LOGO_ASPECT;
export const LOGO_TOP = 240;
const LOGO_INK_TOP_FRAC = 24 / 956;
const LOGO_INK_BOTTOM_FRAC = 932 / 956;
export const LOGO_INK_TOP = LOGO_TOP + LOGO_H * LOGO_INK_TOP_FRAC;
export const LOGO_INK_BOTTOM = LOGO_TOP + LOGO_H * LOGO_INK_BOTTOM_FRAC;

// Orange underline bar (220 x 10) under the logo.
export const UNDERLINE_W = 220;
export const UNDERLINE_H = 10;
export const UNDERLINE_GAP = 24; // from the logo's visible ink bottom
export const UNDERLINE_TOP = Math.round(LOGO_INK_BOTTOM + UNDERLINE_GAP);

// ─── Text blocks (y = vertical centre of the line box) ─────────────────────────────────────
export const HEADLINE_Y = 820;
export const HEADLINE_SIZE = 88;
export const SUB_Y = 930;
export const SUB_SIZE = 44;

// Chips: 3 won't fit 960 px in one row at 38 px/900 -> 2 + 1.
export const CHIP_SIZE = 38;
export const CHIP_ROW_Y = [1040, 1146] as const;

// ─── CTA bar (full bleed) ────────────────────────────────────────────────────────────────
export const CTA_TOP = 1240;
export const CTA_BOTTOM = 1400;
export const CTA_H = CTA_BOTTOM - CTA_TOP;
export const CTA_TEXT_BOX = {x1: 60, x2: 1020} as const;

// "Learn more" block under the bar.
export const LEARN_Y1 = 1420;
export const LEARN_Y2 = 1470;

// ─── Navy wedge (18°, anchored bottom-left) + parallel 12 px orange bar ────────────────────
export const WEDGE_ANGLE_DEG = 18;
export const WEDGE_SLOPE = Math.tan((WEDGE_ANGLE_DEG * Math.PI) / 180); // ≈ 0.3249
export const WEDGE_LEFT_Y = 1175; // top edge at x = 0; falls to ≈ 1526 at x = 1080
export const WEDGE_RIGHT_Y = WEDGE_LEFT_Y + W * WEDGE_SLOPE;
export const STRIPE_THICKNESS = 12; // measured perpendicular to the edge
export const STRIPE_GAP = 14; // perpendicular gap between stripe and wedge
const COS = Math.cos((WEDGE_ANGLE_DEG * Math.PI) / 180);
export const STRIPE_V_GAP = STRIPE_GAP / COS;
export const STRIPE_V_THICK = STRIPE_THICKNESS / COS;
/** Fraction of the canvas the wedge covers (trapezoid). */
export const WEDGE_COVERAGE = (W * (H - (WEDGE_LEFT_Y + WEDGE_RIGHT_Y) / 2)) / (W * H);

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
  headline: 12,
  sub: 24,
  chips: [36, 42, 48] as const,
  cta: 50,
  learn: 60,
} as const;

// CTA slide: SPRING_FIRM stretched to 26 frames; it first reaches its resting position 7 frames
// after it starts (value 1.009 at +7) and is held there — that is the "landing".
export const CTA_SLIDE_STRETCH = 26;
export const CTA_SLIDE_FRAMES = 7;
export const CTA_PULSE_PERIOD = 20;
export const CTA_PULSE_LEN = 10;
export const CTA_PULSE_SCALE = 0.03;
