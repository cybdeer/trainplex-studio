import captionsJson from './data/captions.json';
import editJson from './data/edit.json';
import faceJson from './data/face_boxes.json';

// ─── Edit decision list (all values at 30 fps) ──────────────────────────────────────────────
export const FPS = 30;
export type ClipId = 1 | 2 | 3;
export const CLIPS: ClipId[] = [1, 2, 3];

const editClips = (editJson as {clips: {clip: number; frames: number}[]}).clips;
export const CLIP_FRAMES: Record<ClipId, number> = {
  1: editClips.find((c) => c.clip === 1)!.frames,
  2: editClips.find((c) => c.clip === 2)!.frames,
  3: editClips.find((c) => c.clip === 3)!.frames,
};
export const CLIP_START: Record<ClipId, number> = {
  1: 0,
  2: CLIP_FRAMES[1],
  3: CLIP_FRAMES[1] + CLIP_FRAMES[2],
};
export const END_SCREEN_START = CLIP_START[3] + CLIP_FRAMES[3];
export const END_SCREEN_FRAMES = 105; // 3.5 s
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
};

export type TimedWord = CaptionWord & {startFrame: number; endFrame: number; index: number};

const ALL: CaptionWord[] = captionsJson as CaptionWord[];

export const stripPunct = (w: string) => w.replace(/[,!?।—]/g, '').trim();

export const wordsOf = (clip: ClipId): TimedWord[] =>
  ALL.filter((w) => w.clip === clip).map((w, index) => ({
    ...w,
    index,
    startFrame: Math.round(w.start * FPS),
    endFrame: Math.max(Math.round(w.start * FPS) + 1, Math.round(w.end * FPS)),
  }));

/**
 * Find a phrase ("चार घंटे", "Zero", "TrainPlex") in a clip, punctuation-insensitive and
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

// ─── Presenter face zones (OpenCV Haar, every 3rd frame) — graphics must not cover these ────
type Box = {frame: number; x: number; y: number; w: number; h: number};
const FACES = faceJson as unknown as Record<string, {boxes: Box[]}>;

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

// Watermark box (top-left real-logo bug). Clip graphics that intersect it export their
// local-frame intervals so the watermark ducks out (4-frame fade) instead of clashing.
export const WATERMARK_BOX: Rect = {x1: 60, y1: 240, x2: 260, y2: 240 + 200 / (862 / 956)};
export type FrameInterval = [number, number]; // [startFrame, endFrame) local to the clip
