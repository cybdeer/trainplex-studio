import {findPhrase} from '../../timeline';

/**
 * Clip 2 cue frames (LOCAL to the clip, 30 fps) — all derived from captions.json, never hard-coded.
 * Script: "AI कंपनियों के छोटे-छोटे tasks — voice record कर, photos खींच, text check कर।
 *          सब phone से, कोई fees नहीं, training भी free।"
 */
const start = (phrase: string) => findPhrase(2, phrase).startFrame;

export const CUE = {
  ai: start('AI'),
  tasks: start('tasks'),
  voice: start('voice record'),
  photos: start('photos'),
  text: start('text'),
  sab: start('सब'),
  phone: start('phone'),
  fees: start('fees'),
  training: start('training'),
  free: start('free'),
} as const;

/** Graphics land a hair before the syllable so the pop reads "on" the word, not after it. */
export const LEAD = 2;

/** Exit (clear) timing: slab + chips leave on "सब"; each exit is a short ease-in. */
export const EXIT_FRAMES = 7;
export const CHIP_EXIT_STAGGER = 2;
