import {spring} from 'remotion';
import {SAFE} from '../../brand';
import {CLIP_FRAMES, FPS, FrameInterval, Rect, WATERMARK_BOX, faceAt, findPhrase, rectsOverlap, wordsOf} from '../../timeline';

/**
 * Clip 3 — every cue frame (LOCAL to the clip) is derived from captions.json via findPhrase /
 * wordsOf, and every graphic's vertical position is derived from the face track (faceAt), so a
 * re-timed or re-tracked clip re-flows automatically. Nothing here is a hard-coded second.
 */

// ─── Spoken cues ────────────────────────────────────────────────────────────────────────────
const W3 = wordsOf(3);
const RANGE = findPhrase(3, 'पाँच सौ से छह सौ'); // पाँच सौ | से | छह सौ
const TAK = findPhrase(3, 'तक');
const PAISA = findPhrase(3, 'पैसा');
const BANK = findPhrase(3, 'Bank');
const UPI = findPhrase(3, 'UPI');
const TO_NEECHE = findPhrase(3, 'तो नीचे');
const LEARN_MORE = findPhrase(3, 'Learn more');
const REGISTER = findPhrase(3, 'register');

export const CUE = {
  range: RANGE,
  tak: TAK,
  paisa: PAISA,
  bank: BANK,
  upi: UPI,
  toNeeche: TO_NEECHE,
  learnMore: LEARN_MORE,
  register: REGISTER,
} as const;

// ─── Earning figure (plate) ─────────────────────────────────────────────────────────────────
/** Plate starts opening 3 frames ahead of "पाँच" so "₹0" is on screen as the word lands. */
export const PLATE_IN = RANGE.startFrame - 3;
export const PLATE_OPEN_FRAMES = 6;
/** First frame the figure ("₹0") is drawn. */
export const FIGURE_ON = PLATE_IN + 2;
/** Count 1: ₹0 (held 2 frames) → ₹500 across "पाँच सौ". */
export const COUNT_A: FrameInterval = [FIGURE_ON + 2, W3[RANGE.firstIndex + 1].endFrame];
/** Count 2: "–600" unrolls on "से" and counts 500 → 600 through "छह सौ". */
export const COUNT_B: FrameInterval = [W3[RANGE.firstIndex + 2].startFrame, RANGE.endFrame];
/** The figure lands on "तक": pop + video punch-in. */
export const LAND = TAK.startFrame;
/** Plate hands over to the BANK / UPI card on "पैसा". */
export const PLATE_OUT = PAISA.startFrame;
export const PLATE_EXIT_FRAMES = 5;
export const PLATE_GONE = PLATE_OUT + PLATE_EXIT_FRAMES; // first frame with no figure on screen

// ─── Video punch-in (100 % → 112 % on the landing, released on "पैसा") ─────────────────────
export const ZOOM_AMOUNT = 0.12;
/** Transform origin at the eye line of the landing frame, so the eyes never move UP into the plate. */
export const ZOOM_ORIGIN_Y = faceAt(3, LAND).eyes.y1;
export const ZOOM_ORIGIN_X = 540;
/** Camera move: near-critically damped (ζ ≈ 0.95) so the frame never wobbles or dips below 100 %. */
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

/** Screen-space eyes / mouth rects at frame f (face track + punch-in). */
export const faceOnScreen = (f: number) => {
  const {eyes, mouth} = faceAt(3, f);
  return {eyes: toScreen(eyes, f), mouth: toScreen(mouth, f)};
};

// Face samples are every 3rd frame (nearest-sample lookup), so every window is padded by 3 frames.
const minEyesTop = (from: number, to: number) => {
  let m = Infinity;
  for (let f = Math.max(0, from - 3); f <= Math.min(CLIP_FRAMES[3] - 1, to + 3); f++) {
    m = Math.min(m, faceOnScreen(f).eyes.y1);
  }
  return m;
};

const EYE_CLEARANCE = 10; // hard rule: graphic bottom ≥ 10 px above eyes.y1
const EXTRA_MARGIN = 4; // tracker jitter

// ─── BANK / UPI card ────────────────────────────────────────────────────────────────────────
export const CARD_IN = PAISA.startFrame + 1;
export const CARD_EXIT_FRAMES = 5;
/** Card clears out as the CTA begins ("तो नीचे"). */
export const CARD_OUT = TO_NEECHE.startFrame - 3;
export const CARD_GONE = CARD_OUT + CARD_EXIT_FRAMES;
export const BANK_HI = BANK.startFrame;
export const UPI_HI = UPI.startFrame;
export const TICK_AT = UPI.endFrame;

// ─── Disclaimer (legal) ─────────────────────────────────────────────────────────────────────
export const DISC_IN_FRAMES = 5;
export const DISC_OUT_FRAMES = 5;
/** Fully legible (in by DISC_IN + 4) before the plate starts to open, so it covers every frame the figure shows. */
export const DISC_IN = PLATE_IN - DISC_IN_FRAMES - 1;
/** Held through the BANK / UPI beat and cleared exactly when the LEARN MORE block arrives; never earlier than figure-off + 1 s. */
export const DISC_GONE = Math.max(TO_NEECHE.startFrame, PLATE_GONE + FPS + DISC_OUT_FRAMES);
export const DISC_OUT = DISC_GONE - DISC_OUT_FRAMES;

// ─── LEARN MORE arrow ───────────────────────────────────────────────────────────────────────
export const LM_IN = TO_NEECHE.startFrame;
export const BOUNCE_START = LEARN_MORE.startFrame;
export const BOUNCE_PERIOD = 12;
export const BOUNCE_COUNT = 3;
export const PULSE_AT = REGISTER.startFrame;

// ─── Geometry (1080x1920 screen px) ─────────────────────────────────────────────────────────
const TOP_LIMIT = SAFE.y1 + 12; // 232: below the progress bar

const fitAboveEyes = (from: number, to: number, idealBottom: number, height: number, minTop = TOP_LIMIT) => {
  const bottom = Math.floor(Math.min(idealBottom, minEyesTop(from, to) - EYE_CLEARANCE - EXTRA_MARGIN));
  const top = Math.max(minTop, bottom - height);
  return {top, bottom, height: bottom - top};
};

const plateY = fitAboveEyes(PLATE_IN, PLATE_GONE, 620, 260);
export const PLATE = {x1: 140, x2: 940, y1: plateY.top, y2: plateY.bottom};

// Tick badge overhangs the card's top-right corner by half its size, so the card top keeps ≥ 32 px headroom.
export const TICK_SIZE = 64;
const cardY = fitAboveEyes(CARD_IN, CARD_GONE, 520, 200, TOP_LIMIT + TICK_SIZE / 2);
// x ≥ 300 keeps a 40 px gap to the watermark box (x ≤ 260), so the watermark can stay up; the
// card is then centred on his face (face centre x ≈ 620).
export const CARD = {x1: 300, x2: 968, y1: cardY.top, y2: cardY.bottom};

export const DISC_STRIP = {y1: 1416, y2: 1470};
export const LM_BLOCK = {y1: 1310, y2: 1478};

// ─── Watermark contract ─────────────────────────────────────────────────────────────────────
const blocked: FrameInterval[] = [];
if (rectsOverlap(PLATE, WATERMARK_BOX)) blocked.push([PLATE_IN, PLATE_GONE]);
if (rectsOverlap({...CARD, y1: CARD.y1 - TICK_SIZE / 2, x2: CARD.x2 + TICK_SIZE / 2}, WATERMARK_BOX)) {
  blocked.push([CARD_IN, CARD_GONE]);
}
export const WATERMARK_BLOCKED: FrameInterval[] = blocked;
