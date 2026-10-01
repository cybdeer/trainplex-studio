import {CLIP_FRAMES, findPhrase} from '../../timeline';

/**
 * Clip 2 cue frames (LOCAL to the clip, 30 fps) — all derived from captions.json by phrase lookup
 * in the exact script, never hard-coded.
 * Script: "Lecture के बाद, phone से — voice record, photos, text check। AI कंपनियों के छोटे tasks।
 *          कोई fees नहीं, training भी free।"
 */
const start = (phrase: string) => findPhrase(2, phrase).startFrame;

export const CUE = {
  lecture: start('Lecture के बाद'),
  phone: start('phone से'),
  voice: start('voice record'),
  photos: start('photos'),
  text: start('text check'),
  ai: start('AI'),
  fees: start('कोई fees नहीं'),
  training: start('training भी free'),
} as const;

export const CLIP2_END = CLIP_FRAMES[2];

/** Graphics land a hair before the syllable so the pop reads "on" the word, not after it. */
export const LEAD = 2;
/** Exit (clear) timing: each exit is a short ease-in. */
export const EXIT_FRAMES = 7;
export const CHIP_EXIT_STAGGER = 2;

/** Each perk badge must be on screen for at least 1.2 s. */
export const MIN_BADGE_FRAMES = Math.ceil(1.2 * 30);
/**
 * Badge entrance: on its phrase (minus LEAD) — but pulled earlier if the clip would otherwise
 * end less than 1.2 s after it ("training भी free" is the last phrase of the clip).
 */
export const badgeIn = (cue: number) => Math.max(0, Math.min(cue - LEAD, CLIP2_END - MIN_BADGE_FRAMES));
export const FEES_IN = badgeIn(CUE.fees);
export const TRAINING_IN = Math.max(FEES_IN + 3, badgeIn(CUE.training));

// Tag "Lecture के बाद • Phone से": in on "Lecture", "Phone से" lights up on "phone से", leaves on "AI".
export const TAG_IN = Math.max(0, CUE.lecture - LEAD);
export const TAG_OUT = CUE.ai;
export const TAG_GONE = TAG_OUT + EXIT_FRAMES;

// Task chips: each pops on its phrase; all three clear just before the perk badges arrive.
export const CHIPS_OUT = Math.max(CUE.text + 6, FEES_IN - EXIT_FRAMES - 2 * CHIP_EXIT_STAGGER);
export const CHIPS_GONE = CHIPS_OUT + 2 * CHIP_EXIT_STAGGER + EXIT_FRAMES;
