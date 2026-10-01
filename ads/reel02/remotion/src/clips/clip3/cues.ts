import {spring} from 'remotion';
import {placeFaceSafe} from '../../layout/faceSafe';
import {CLIP_FRAMES, FPS, FrameInterval, Rect, WATERMARK_BOX, faceAt, findPhrase, rectsOverlap, wordsOf} from '../../timeline';

/**
 * Clip 3 — every cue frame (LOCAL to the clip) is derived from captions.json by phrase lookup in
 * the exact script, and every graphic's position from the face track (layout/faceSafe), so a
 * re-timed or re-tracked clip re-flows automatically. Nothing here is a hard-coded second.
 * Script: "मैं दिन में दो-तीन घंटे काम करती हूँ और चार सौ से पाँच सौ कमा लेती हूँ, सीधे Bank या UPI में।
 *          नीचे Learn more दबाओ और अभी register करो!"
 */

// ─── Spoken cues ────────────────────────────────────────────────────────────────────────────
const W3 = wordsOf(3);
const HOURS = findPhrase(3, 'दो-तीन घंटे');
const RANGE = findPhrase(3, 'चार सौ से पाँच सौ'); // चार | सौ | से | पाँच | सौ
const KAMA = findPhrase(3, 'कमा लेती हूँ');
const SEEDHE = findPhrase(3, 'सीधे');
const BANK = findPhrase(3, 'Bank');
const UPI = findPhrase(3, 'UPI');
const NEECHE = findPhrase(3, 'नीचे');
const LEARN_MORE = findPhrase(3, 'Learn more');
const REGISTER = findPhrase(3, 'register');

export const CUE = {hours: HOURS, range: RANGE, kama: KAMA, seedhe: SEEDHE, bank: BANK, upi: UPI, neeche: NEECHE, learnMore: LEARN_MORE, register: REGISTER} as const;
export const CLIP3_END = CLIP_FRAMES[3];
const LEAD = 2;

// ─── Disclaimer (legal) — wipes in BEFORE anything numeric appears, holds to the clip end ─────
export const DISC_IN_FRAMES = 5;

// ─── Earnings plate "₹400–500 / 2–3 घंटे*" ────────────────────────────────────────────────────
/** Plate opens on "दो-तीन घंटे" (showing "/ 2–3 घंटे*"); never before the disclaimer is fully in. */
export const PLATE_IN = Math.max(DISC_IN_FRAMES + 1, HOURS.startFrame - LEAD);
export const PLATE_OPEN_FRAMES = 6;
/** First frame the ₹ figure is drawn: just ahead of "चार" (of "चार सौ"). */
export const FIGURE_ON = Math.max(PLATE_IN + 2, RANGE.startFrame - LEAD);
/** Count 1: ₹0 → ₹400 across "चार सौ". */
export const COUNT_A: FrameInterval = [FIGURE_ON + 1, Math.max(FIGURE_ON + 3, W3[RANGE.firstIndex + 1].endFrame)];
/** Count 2: "–500" unrolls on "से" and counts 400 → 500 through "पाँच सौ". */
export const COUNT_B: FrameInterval = [W3[RANGE.firstIndex + 2].startFrame, Math.max(W3[RANGE.firstIndex + 2].startFrame + 2, RANGE.endFrame)];
/** The figure lands on "कमा लेती हूँ": pop + video punch-in. */
export const LAND = KAMA.startFrame;
/** Plate hands over to the Bank / UPI card on "सीधे". */
export const PLATE_OUT = SEEDHE.startFrame;
export const PLATE_EXIT_FRAMES = 5;
export const PLATE_GONE = PLATE_OUT + PLATE_EXIT_FRAMES; // first frame with no figure on screen

export const DISC_IN = PLATE_IN - DISC_IN_FRAMES - 1;
/** Mandatory: visible on every frame the ₹ figure shows — held to the clip end (the wipe covers it). */
export const DISC_GONE = CLIP3_END;
export const DISC_OUT = DISC_GONE; // no exit animation: it is on screen until the last clip-3 frame
if (!(DISC_IN + DISC_IN_FRAMES - 1 <= PLATE_IN && DISC_GONE >= PLATE_GONE)) {
  throw new Error('clip3: disclaimer does not cover every frame of the earnings figure');
}

// ─── Video punch-in (100 % → 108 % on the landing, released on "सीधे") ───────────────────────
export const ZOOM_AMOUNT = 0.08;
/** Transform origin on the chin line, so the face grows UP and never pushes into the lower band. */
const chinWindow = Array.from({length: Math.max(1, PLATE_GONE - LAND + 7)}, (_, i) => Math.max(0, LAND - 3 + i));
export const ZOOM_ORIGIN_Y = Math.max(...chinWindow.map((f) => faceAt(3, Math.min(CLIP3_END - 1, f)).face.y2));
export const ZOOM_ORIGIN_X = 540;
/** Camera move: near-critically damped so the frame never wobbles or dips below 100 %. */
const ZOOM_SPRING = {damping: 27, stiffness: 200, mass: 1, overshootClamping: true};

export const zoomAt = (f: number) => {
  const pin = spring({frame: f - LAND, fps: FPS, config: ZOOM_SPRING});
  const out = spring({frame: f - PLATE_OUT, fps: FPS, config: ZOOM_SPRING});
  return 1 + ZOOM_AMOUNT * pin * (1 - out);
};

/** Maps a rect from source-video pixels to screen pixels through the punch-in at frame f. */
export const toScreen = (r: Rect, f: number): Rect => {
  const s = zoomAt(f);
  const mx = (x: number) => ZOOM_ORIGIN_X + (x - ZOOM_ORIGIN_X) * s;
  const my = (y: number) => ZOOM_ORIGIN_Y + (y - ZOOM_ORIGIN_Y) * s;
  return {x1: mx(r.x1), y1: my(r.y1), x2: mx(r.x2), y2: my(r.y2)};
};

/** Screen-space face / eyes / mouth rects at frame f (face track + punch-in). */
export const faceOnScreen = (f: number) => {
  const {face, eyes, mouth} = faceAt(3, f);
  return {face: toScreen(face, f), eyes: toScreen(eyes, f), mouth: toScreen(mouth, f)};
};

// ─── Bank / UPI card ────────────────────────────────────────────────────────────────────────
export const CARD_IN = SEEDHE.startFrame + 1;
export const CARD_EXIT_FRAMES = 5;
/** Card clears as the CTA begins ("नीचे"). */
export const CARD_OUT = Math.max(UPI.endFrame + 4, NEECHE.startFrame - 3);
export const CARD_GONE = CARD_OUT + CARD_EXIT_FRAMES;
export const BANK_HI = BANK.startFrame;
export const UPI_HI = UPI.startFrame;
export const TICK_AT = UPI.endFrame;

// ─── LEARN MORE arrow ───────────────────────────────────────────────────────────────────────
export const LM_IN = Math.max(CARD_GONE - 2, NEECHE.startFrame);
export const BOUNCE_START = LEARN_MORE.startFrame;
export const BOUNCE_PERIOD = 12;
export const BOUNCE_COUNT = 3;
export const PULSE_AT = REGISTER.startFrame;

// ─── Geometry (1080x1920 screen px), all face-safe ──────────────────────────────────────────
export const PLATE_SIZE = {w: 940, h: 190};
const platePos = placeFaceSafe({
  clip: 3,
  name: 'clip3 earnings plate',
  from: PLATE_IN,
  to: PLATE_GONE,
  w: PLATE_SIZE.w,
  h: PLATE_SIZE.h * 1.1, // landing pop headroom
  zones: ['lower', 'top'],
  minScale: 0.75,
  cam: toScreen,
});
export const PLATE = {...platePos, y1: platePos.y1 + Math.round((platePos.h - PLATE_SIZE.h * platePos.scale) / 2)};

// Tick badge overhangs the card's top-right corner by half its size.
export const TICK_SIZE = 64;
export const CARD_SIZE = {w: 760, h: 190};
const cardPos = placeFaceSafe({
  clip: 3,
  name: 'clip3 bank/upi card',
  from: CARD_IN,
  to: CARD_GONE,
  w: CARD_SIZE.w + TICK_SIZE / 2,
  h: CARD_SIZE.h + TICK_SIZE / 2,
  zones: ['lower', 'top'],
  minScale: 0.75,
  cam: toScreen,
});
export const CARD = {
  scale: cardPos.scale,
  x1: cardPos.x1,
  y1: cardPos.y1 + (TICK_SIZE / 2) * cardPos.scale,
  x2: cardPos.x1 + CARD_SIZE.w * cardPos.scale,
  y2: cardPos.y2,
};

export const LM_SIZE = {w: 600, h: 192};
export const LM_BLOCK = placeFaceSafe({
  clip: 3,
  name: 'clip3 learn more',
  from: LM_IN,
  to: CLIP3_END - 1,
  w: LM_SIZE.w,
  h: LM_SIZE.h,
  zones: ['lower', 'top'],
  minScale: 0.75,
  cam: toScreen,
});

/** Disclaimer strip: below the caption block (bottom edge 1400), inside the safe zone. */
export const DISC_STRIP = {y1: 1416, y2: 1470};

// ─── Watermark contract ─────────────────────────────────────────────────────────────────────
const blocked: FrameInterval[] = [];
if (rectsOverlap(PLATE, WATERMARK_BOX)) blocked.push([PLATE_IN, PLATE_GONE]);
if (rectsOverlap({...CARD, y1: CARD.y1 - TICK_SIZE / 2}, WATERMARK_BOX)) blocked.push([CARD_IN, CARD_GONE]);
if (rectsOverlap(LM_BLOCK, WATERMARK_BOX)) blocked.push([LM_IN, CLIP3_END]);
export const WATERMARK_BLOCKED: FrameInterval[] = blocked;
