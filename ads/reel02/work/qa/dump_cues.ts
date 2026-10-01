// QA only: evaluates the REAL timing / camera / geometry code from remotion/src in Node and dumps it
// as JSON, so the Python checks use exactly what the render used.
// Build + run:  node work/qa/run_dump.mjs   (bundles this file with esbuild -> work/qa/cues_dump.json)
import {
  CLIP_FRAMES,
  CLIP_START,
  END_SCREEN_FRAMES,
  END_SCREEN_START,
  TOTAL_FRAMES,
  WIPE_FRAMES,
  WIPE_START,
  faceAt,
  wordsOf,
  ClipId,
  WATERMARK_BOX,
} from '../../remotion/src/timeline';
import {buildChunks, displayText} from '../../remotion/src/captions/chunks';
import {cameraAt} from '../../remotion/src/clips/clip1/camera';
import * as C1 from '../../remotion/src/clips/clip1/cues';
import * as C2 from '../../remotion/src/clips/clip2/cues';
import * as C2L from '../../remotion/src/clips/clip2/layout';
import * as C3 from '../../remotion/src/clips/clip3/cues';
import * as FS from '../../remotion/src/layout/faceSafe';
import * as ES from '../../remotion/src/endscreen/geometry';
import {writeFileSync} from 'fs';

const clips: ClipId[] = [1, 2, 3];
const out: Record<string, unknown> = {};

out.CLIP_FRAMES = CLIP_FRAMES;
out.CLIP_START = CLIP_START;
out.END_SCREEN_START = END_SCREEN_START;
out.END_SCREEN_FRAMES = END_SCREEN_FRAMES;
out.TOTAL_FRAMES = TOTAL_FRAMES;
out.WIPE = {start: WIPE_START, frames: WIPE_FRAMES};
out.WATERMARK_BOX = WATERMARK_BOX;
out.FACE_SAFE = {TOP_MIN: FS.TOP_MIN, TOP_BAND_MAX: FS.TOP_BAND_MAX, LOWER_MAX: FS.LOWER_MAX, FACE_PAD: FS.FACE_PAD};

// Caption chunks (local frames).
out.chunks = Object.fromEntries(
  clips.map((c) => [
    c,
    buildChunks(wordsOf(c), CLIP_FRAMES[c]).map((ch) => ({
      index: ch.index,
      appear: ch.appear,
      firstStart: ch.firstStart,
      lastEnd: ch.lastEnd,
      fadeStart: ch.fadeStart,
      hideEnd: ch.hideEnd,
      exit: ch.exit,
      words: ch.words.map((w) => ({word: w.word, text: displayText(w), startFrame: w.startFrame, endFrame: w.endFrame, highlight: w.highlight})),
    })),
  ]),
);

// Per-frame camera transform of the VIDEO layer + raw face rects (source px).
const faces: Record<string, unknown[]> = {};
for (const c of clips) {
  const arr: unknown[] = [];
  for (let f = 0; f < CLIP_FRAMES[c]; f++) {
    const fa = faceAt(c, f);
    let cam = {scale: 1, dx: 0, dy: 0, originX: 540, originY: 960};
    if (c === 1) {
      const k = cameraAt(f);
      cam = {scale: k.scale, dx: k.dx, dy: k.dy, originX: 540, originY: (k.originY / 100) * 1920};
    } else if (c === 3) {
      cam = {scale: C3.zoomAt(f), dx: 0, dy: 0, originX: C3.ZOOM_ORIGIN_X, originY: C3.ZOOM_ORIGIN_Y};
    }
    arr.push({f, face: fa.face, eyes: fa.eyes, mouth: fa.mouth, cam});
  }
  faces[c] = arr;
}
out.faces = faces;

out.clip1 = {
  CUE: C1.CUE,
  SLAB: C1.SLAB,
  SLAB_OUT_END: C1.SLAB_OUT_END,
  SLAB_POS: C1.SLAB_POS,
  SHAKE: C1.SHAKE,
  CAL: C1.CAL,
  CAL_GONE: C1.CAL_GONE,
  CAL_POS: C1.CAL_POS,
  LOGO: C1.LOGO,
  LOGO_POS: C1.LOGO_POS,
  LOGO_WIDTH: C1.LOGO_WIDTH,
  LOGO_HEIGHT: C1.LOGO_HEIGHT,
  LOGO_PLATE: C1.LOGO_PLATE,
  WATERMARK_BLOCKED: C1.WATERMARK_BLOCKED,
};
out.clip2 = {
  CUE: C2.CUE,
  TAG_IN: C2.TAG_IN,
  TAG_GONE: C2.TAG_GONE,
  CHIPS_OUT: C2.CHIPS_OUT,
  CHIPS_GONE: C2.CHIPS_GONE,
  FEES_IN: C2.FEES_IN,
  TRAINING_IN: C2.TRAINING_IN,
  TAG_POS: C2L.TAG_POS,
  CHIP_POS: C2L.CHIP_POS,
  BADGE_POS: C2L.BADGE_POS,
  WATERMARK_BLOCKED: C2L.WATERMARK_BLOCKED,
};
out.clip3 = {
  PLATE_IN: C3.PLATE_IN,
  FIGURE_ON: C3.FIGURE_ON,
  COUNT_A: C3.COUNT_A,
  COUNT_B: C3.COUNT_B,
  LAND: C3.LAND,
  PLATE_OUT: C3.PLATE_OUT,
  PLATE_GONE: C3.PLATE_GONE,
  PLATE: C3.PLATE,
  CARD: C3.CARD,
  CARD_IN: C3.CARD_IN,
  CARD_OUT: C3.CARD_OUT,
  CARD_GONE: C3.CARD_GONE,
  DISC_IN: C3.DISC_IN,
  DISC_OUT: C3.DISC_OUT,
  DISC_GONE: C3.DISC_GONE,
  DISC_STRIP: C3.DISC_STRIP,
  LM_IN: C3.LM_IN,
  LM_BLOCK: C3.LM_BLOCK,
  ZOOM_ORIGIN_Y: C3.ZOOM_ORIGIN_Y,
  WATERMARK_BLOCKED: C3.WATERMARK_BLOCKED,
};
out.endscreen = {...ES};

writeFileSync(process.argv[2] ?? 'cues_dump.json', JSON.stringify(out, null, 1));
console.log('ok');
