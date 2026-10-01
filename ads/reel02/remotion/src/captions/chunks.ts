// Pure caption-chunk timing (no DOM / Remotion imports, so it can also be run from Node for QA).
// All frames are LOCAL to the clip (30 fps), derived from captions.json word timings.
import type {TimedWord} from '../timeline';

/** A chunk may appear up to this many frames before its first word is spoken. */
export const LEAD_FRAMES = 2;
/** Entrance: slide up 24 px + fade in over 6 frames. */
export const ENTER_FRAMES = 6;
export const ENTER_SLIDE_PX = 24;
/** Exit (into a pause): 4-frame fade, starting ~6 frames after the last word ends. */
export const EXIT_FADE_FRAMES = 4;
export const EXIT_DELAY_FRAMES = 6;
/** Only exit into a pause when the pause is > 0.4 s AND it leaves a visible blank (no 1-2 frame flicker). */
export const EXIT_GAP_FRAMES = 12;
export const MIN_BLANK_FRAMES = 3;

export type ChunkTiming = {
  index: number; // chunk index within the clip (captions.json `chunk`)
  words: TimedWord[];
  firstStart: number; // start frame of its first word
  lastEnd: number; // end frame of its last word
  appear: number; // first visible frame (entrance starts)
  fadeStart: number; // exit fade starts (== hideEnd for a hard swap)
  hideEnd: number; // first frame it is no longer visible
  exit: 'swap' | 'fade' | 'clip-end';
};

export const buildChunks = (words: TimedWord[], clipFrames: number): ChunkTiming[] => {
  const groups = new Map<number, TimedWord[]>();
  for (const w of words) {
    const g = groups.get(w.chunk) ?? [];
    g.push(w);
    groups.set(w.chunk, g);
  }
  const ordered = [...groups.entries()].sort((a, b) => a[1][0].startFrame - b[1][0].startFrame);

  const chunks: ChunkTiming[] = ordered.map(([index, ws]) => {
    const firstStart = ws[0].startFrame;
    const lastEnd = Math.max(...ws.map((w) => w.endFrame));
    return {
      index,
      words: ws,
      firstStart,
      lastEnd,
      appear: Math.max(0, firstStart - LEAD_FRAMES),
      fadeStart: clipFrames,
      hideEnd: clipFrames,
      exit: 'clip-end',
    };
  });

  // Never let a chunk appear before (or on the same frame as) the previous one.
  for (let i = 1; i < chunks.length; i++) {
    chunks[i].appear = Math.max(chunks[i].appear, chunks[i - 1].appear + 1);
  }

  for (let i = 0; i < chunks.length - 1; i++) {
    const c = chunks[i];
    const next = chunks[i + 1];
    const gap = next.firstStart - c.lastEnd;
    const fadeStart = c.lastEnd + EXIT_DELAY_FRAMES;
    const blank = next.appear - (fadeStart + EXIT_FADE_FRAMES);
    if (gap > EXIT_GAP_FRAMES && blank >= MIN_BLANK_FRAMES) {
      c.exit = 'fade';
      c.fadeStart = fadeStart;
      c.hideEnd = fadeStart + EXIT_FADE_FRAMES;
    } else {
      // Continuous speech / short pause: hold until the next chunk appears, then hard-swap.
      c.exit = 'swap';
      c.fadeStart = next.appear;
      c.hideEnd = next.appear;
    }
  }
  const last = chunks[chunks.length - 1];
  if (last) {
    last.exit = 'clip-end';
    last.fadeStart = clipFrames;
    last.hideEnd = clipFrames;
  }
  return chunks;
};

// ─── Display rules ───────────────────────────────────────────────────────────────────────────
const LATIN = /[A-Za-z]/;
/** Brand spelling beats the uppercase rule: "TrainPlex" is never re-cased. */
const KEEP_CASE = new Set(['TrainPlex']);

export const isLatinWord = (word: string) => LATIN.test(word);

/** Text as displayed: highlight Latin words are uppercased (except brand names). */
export const displayText = (w: Pick<TimedWord, 'word' | 'highlight'>) => {
  if (!w.highlight || !isLatinWord(w.word)) return w.word;
  const bare = w.word.replace(/[^A-Za-z]/g, '');
  if (KEEP_CASE.has(bare)) return w.word;
  return w.word.toUpperCase();
};
