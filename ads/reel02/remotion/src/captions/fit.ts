// Text measurement + per-chunk font auto-fit (browser only; call after the brand fonts are loaded).
import {FONT_STACK} from '../brand';

export const FONT_WEIGHT = 900;
export const FONT_MIN = 78;
export const FONT_MAX = 92;
export const HIGHLIGHT_SCALE = 1.15;
/** Navy outline thickness OUTSIDE the glyphs (px). */
export const OUTLINE_PX = 5;
/** Max caption block width, outline included. */
export const MAX_WIDTH = 900;
/** Word gap as a fraction of the chunk's base font size. */
export const GAP_EM = 0.27;
/** Safety margin on measured widths (canvas vs DOM rounding). */
const SAFETY = 1.01;

export type FitWord = {text: string; highlight: boolean};
export type FitResult = {fontSize: number; lines: number[][]; lineWidths: number[]};

let ctx: CanvasRenderingContext2D | null = null;
const cache = new Map<string, number>();

export const measureWord = (text: string, px: number): number => {
  const key = `${px}|${text}`;
  const hit = cache.get(key);
  if (hit !== undefined) return hit;
  if (!ctx) {
    ctx = document.createElement('canvas').getContext('2d');
  }
  if (!ctx) throw new Error('Captions: 2D canvas unavailable for text measurement');
  ctx.font = `${FONT_WEIGHT} ${px}px ${FONT_STACK}`;
  const w = ctx.measureText(text).width;
  cache.set(key, w);
  return w;
};

export const wordPx = (base: number, highlight: boolean) => (highlight ? base * HIGHLIGHT_SCALE : base);

const lineWidth = (words: FitWord[], idx: number[], base: number) =>
  idx.reduce((sum, i) => sum + measureWord(words[i].text, wordPx(base, words[i].highlight)) * SAFETY, 0) +
  Math.max(0, idx.length - 1) * GAP_EM * base +
  2 * OUTLINE_PX;

const range = (a: number, b: number) => Array.from({length: b - a}, (_, k) => a + k);

/**
 * Largest base size in [78, 92] that fits the chunk on ONE line within 900 px; otherwise the most
 * balanced 2-line split at the largest size where both lines fit.
 */
export const fitChunk = (words: FitWord[]): FitResult => {
  const all = range(0, words.length);
  for (let px = FONT_MAX; px >= FONT_MIN; px--) {
    const w = lineWidth(words, all, px);
    if (w <= MAX_WIDTH) return {fontSize: px, lines: [all], lineWidths: [w]};
  }
  if (words.length < 2) {
    return {fontSize: FONT_MIN, lines: [all], lineWidths: [lineWidth(words, all, FONT_MIN)]};
  }
  // Two lines: choose the split whose wider line is narrowest (balanced), prefer a longer top line on ties.
  let best: {k: number; max: number} | null = null;
  for (let k = 1; k < words.length; k++) {
    const top = lineWidth(words, range(0, k), FONT_MAX);
    const bottom = lineWidth(words, range(k, words.length), FONT_MAX);
    const max = Math.max(top, bottom);
    if (!best || max < best.max - 0.5) best = {k, max};
  }
  const lines = [range(0, best!.k), range(best!.k, words.length)];
  for (let px = FONT_MAX; px >= FONT_MIN; px--) {
    const widths = lines.map((l) => lineWidth(words, l, px));
    if (Math.max(...widths) <= MAX_WIDTH) return {fontSize: px, lines, lineWidths: widths};
  }
  return {fontSize: FONT_MIN, lines, lineWidths: lines.map((l) => lineWidth(words, l, FONT_MIN))};
};
