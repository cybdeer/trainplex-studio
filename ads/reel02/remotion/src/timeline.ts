import captionsJson from './data/captions.json';
import editJson from './data/edit.json';
import faceJson from './data/face_boxes.json';
// Single source of the exact script (whisper supplies timing only). Imported straight from work/.
import scriptJson from '../../work/script.json';

// ─── Edit decision list (all values at 30 fps) ──────────────────────────────────────────────
export const FPS = 30;
export type ClipId = 1 | 2 | 3;
export const CLIPS: ClipId[] = [1, 2, 3];

type EditJson = {
  placeholder?: boolean;
  fps?: number;
  end_screen_frames?: number;
  clips: {clip: number; frames: number}[];
};
const EDIT = editJson as EditJson;
if (EDIT.fps !== undefined && EDIT.fps !== FPS) {
  throw new Error(`edit.json fps ${EDIT.fps} != ${FPS}`);
}
const clipFrames = (clip: ClipId) => {
  const c = EDIT.clips.find((x) => x.clip === clip);
  if (!c || !Number.isInteger(c.frames) || c.frames <= 0) throw new Error(`edit.json: clip ${clip} frames missing/invalid`);
  return c.frames;
};
export const CLIP_FRAMES: Record<ClipId, number> = {1: clipFrames(1), 2: clipFrames(2), 3: clipFrames(3)};
export const CLIP_START: Record<ClipId, number> = {
  1: 0,
  2: CLIP_FRAMES[1],
  3: CLIP_FRAMES[1] + CLIP_FRAMES[2],
};
export const END_SCREEN_START = CLIP_START[3] + CLIP_FRAMES[3];

// ─── End-screen length: a timeline PARAMETER, 3.0–4.0 s, chosen so the reel lands at 25.0–30.0 s ──
export const END_SCREEN_MIN = 3 * FPS; // 90
export const END_SCREEN_MAX = 4 * FPS; // 120
export const TOTAL_MIN = 25 * FPS; // 750
export const TOTAL_MAX = 30 * FPS; // 900
const END_SCREEN_PREFERRED = Math.round(3.5 * FPS); // 105

/**
 * edit.json may pin `end_screen_frames`; otherwise 3.5 s, nudged within 3.0–4.0 s so the total
 * lands in 25.0–30.0 s. Throws (fails the bundle) if no legal value exists.
 */
const chooseEndScreenFrames = (clipsTotal: number, pinned?: number) => {
  const lo = Math.max(END_SCREEN_MIN, TOTAL_MIN - clipsTotal);
  const hi = Math.min(END_SCREEN_MAX, TOTAL_MAX - clipsTotal);
  if (lo > hi) {
    throw new Error(
      `Timeline: clips total ${clipsTotal} f (${(clipsTotal / FPS).toFixed(2)} s) — no 3.0–4.0 s end screen lands the reel in 25.0–30.0 s`,
    );
  }
  if (pinned !== undefined) {
    if (!Number.isInteger(pinned) || pinned < lo || pinned > hi) {
      throw new Error(`edit.json end_screen_frames=${pinned} outside the legal range [${lo}, ${hi}] for clips total ${clipsTotal} f`);
    }
    return pinned;
  }
  return Math.min(hi, Math.max(lo, END_SCREEN_PREFERRED));
};
export const END_SCREEN_FRAMES = chooseEndScreenFrames(END_SCREEN_START, EDIT.end_screen_frames);
export const TOTAL_FRAMES = END_SCREEN_START + END_SCREEN_FRAMES;
// Orange full-frame wipe clip 3 -> end screen: 8 frames centred on the cut
// (4 frames covering clip 3 left->right, 4 frames revealing the end screen left->right).
export const WIPE_FRAMES = 8;
export const WIPE_START = END_SCREEN_START - WIPE_FRAMES / 2;

export const clipVideo = (clip: ClipId) => `clips/clip${clip}.mp4`;

// ─── Word-timed captions (exact script, whisper timing only) ────────────────────────────────
export type CaptionWord = {
  word: string; // exact script spelling, incl. trailing punctuation
  start: number; // seconds, relative to the trimmed clip
  end: number;
  clip: ClipId;
  highlight: boolean;
  chunk: number; // caption chunk index within the clip (2-4 words)
  placeholder?: boolean;
};

export type TimedWord = CaptionWord & {startFrame: number; endFrame: number; index: number};

const ALL: CaptionWord[] = captionsJson as CaptionWord[];

/** True while src/data still holds the remotion agent's synthetic placeholder inputs. */
export const IS_PLACEHOLDER_DATA =
  Boolean(EDIT.placeholder) ||
  ALL.some((w) => w.placeholder) ||
  Boolean((faceJson as Record<string, unknown>)._placeholder);

export const stripPunct = (w: string) => w.replace(/[,!?।—]/g, '').trim();

export const wordsOf = (clip: ClipId): TimedWord[] =>
  ALL.filter((w) => w.clip === clip).map((w, index) => ({
    ...w,
    index,
    startFrame: Math.round(w.start * FPS),
    endFrame: Math.max(Math.round(w.start * FPS) + 1, Math.round(w.end * FPS)),
  }));

/**
 * Find a phrase ("बीस तारीख", "Learn more", "TrainPlex") in a clip, punctuation-insensitive and
 * case-insensitive. Returns start frame of the first word and end frame of the last word,
 * relative to the clip start. Throws if the phrase is not in the script — timings are always
 * re-derived from captions.json, never hard-coded seconds.
 */
export const findPhrase = (clip: ClipId, phrase: string, occurrence = 0) => {
  const words = wordsOf(clip);
  const target = phrase.toLowerCase().split(/\s+/);
  let seen = 0;
  for (let i = 0; i + target.length <= words.length; i++) {
    const ok = target.every((t, k) => stripPunct(words[i + k].word).toLowerCase() === t);
    if (ok) {
      if (seen === occurrence) {
        const last = words[i + target.length - 1];
        return {
          startFrame: words[i].startFrame,
          endFrame: last.endFrame,
          start: words[i].start,
          end: last.end,
          firstIndex: i,
          lastIndex: i + target.length - 1,
        };
      }
      seen++;
    }
  }
  throw new Error(`Phrase "${phrase}" (#${occurrence}) not found in clip ${clip}`);
};

// ─── Script contract: captions.json must reproduce work/script.json 1:1 ───────────────────────
type ScriptJson = {clips: Record<string, string>; highlight_phrases: string[]};
const SCRIPT = scriptJson as ScriptJson;
const norm = (s: string) => s.replace(/\s+/g, ' ').trim();
for (const clip of CLIPS) {
  const want = norm(SCRIPT.clips[`clip${clip}`] ?? '');
  const got = norm(wordsOf(clip).map((w) => w.word).join(' '));
  if (want !== got) {
    throw new Error(`captions.json clip ${clip} does not match work/script.json exactly:\n  script : ${want}\n  caption: ${got}`);
  }
  for (const w of wordsOf(clip)) {
    if (!(w.end >= w.start)) throw new Error(`captions.json clip ${clip}: inverted timing on "${w.word}"`);
  }
}
/** Every highlight phrase must exist somewhere in the script and be flagged highlight=true. */
export const HIGHLIGHT_PHRASES = SCRIPT.highlight_phrases;
for (const phrase of HIGHLIGHT_PHRASES) {
  const hit = CLIPS.map((c) => {
    try {
      return {c, p: findPhrase(c, phrase)};
    } catch {
      return null;
    }
  }).find((x) => x !== null);
  if (!hit) throw new Error(`Highlight phrase "${phrase}" not found in any clip`);
  const ws = wordsOf(hit.c).slice(hit.p.firstIndex, hit.p.lastIndex + 1);
  if (!ws.every((w) => w.highlight)) {
    throw new Error(`Highlight phrase "${phrase}" (clip ${hit.c}) is not flagged highlight=true in captions.json`);
  }
}

// ─── Presenter face zones (OpenCV Haar, every 3rd frame) — graphics must not cover these ────
type Box = {frame: number; x: number; y: number; w: number; h: number};
const FACES = faceJson as unknown as Record<string, {boxes: Box[]}>;
for (const clip of CLIPS) {
  if (!FACES[String(clip)]?.boxes?.length) throw new Error(`face_boxes.json: no boxes for clip ${clip}`);
}

export type Rect = {x1: number; y1: number; x2: number; y2: number};

export const faceAt = (clip: ClipId, localFrame: number): {face: Rect; eyes: Rect; mouth: Rect} => {
  const boxes = FACES[String(clip)].boxes;
  let best = boxes[0];
  for (const b of boxes) {
    if (Math.abs(b.frame - localFrame) < Math.abs(best.frame - localFrame)) best = b;
  }
  const {x, y, w, h} = best;
  return {
    face: {x1: x, y1: y, x2: x + w, y2: y + h},
    // conservative bands calibrated on real frames (eyes ~0.40 h, mouth ~0.80 h of the Haar box)
    eyes: {x1: x + 0.2 * w, y1: y + 0.25 * h, x2: x + 0.8 * w, y2: y + 0.5 * h},
    mouth: {x1: x + 0.3 * w, y1: y + 0.64 * h, x2: x + 0.7 * w, y2: y + 0.92 * h},
  };
};

export const rectsOverlap = (a: Rect, b: Rect) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;

// Watermark box (top-left real-logo bug, x 60, y 240, 200 px + 8 px cream plate). Clip graphics
// that intersect it export their local-frame intervals so the watermark ducks out.
export const WATERMARK_BOX: Rect = {x1: 60, y1: 240, x2: 60 + 200 + 16, y2: 240 + 200 / (862 / 956) + 16};
export type FrameInterval = [number, number]; // [startFrame, endFrame) local to the clip
