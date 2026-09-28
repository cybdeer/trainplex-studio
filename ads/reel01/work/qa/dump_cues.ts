// QA only (Agent 13): evaluates the REAL timing / camera / geometry code from remotion/src in Node
// and dumps it as JSON, so the Python checks use exactly what the render used.
// Build + run:  node work/qa/run_dump.mjs   (bundles this file with esbuild -> work/qa/cues_dump.json)
import {CLIP_FRAMES, CLIP_START, END_SCREEN_START, faceAt, wordsOf, ClipId, WATERMARK_BOX} from '../../remotion/src/timeline';
import {buildChunks, displayText} from '../../remotion/src/captions/chunks';
import {cameraAt} from '../../remotion/src/clips/clip1/camera';
import * as C1 from '../../remotion/src/clips/clip1/cues';
import * as C2 from '../../remotion/src/clips/clip2/cues';
import * as C2L from '../../remotion/src/clips/clip2/layout';
import * as C3 from '../../remotion/src/clips/clip3/cues';
import * as ES from '../../remotion/src/endscreen/geometry';
import {writeFileSync} from 'fs';

const clips: ClipId[] = [1, 2, 3];
const out: Record<string, unknown> = {};

out.CLIP_FRAMES = CLIP_FRAMES;
out.CLIP_START = CLIP_START;
out.END_SCREEN_START = END_SCREEN_START;
out.WATERMARK_BOX = WATERMARK_BOX;

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
      words: ch.words.map((w) => ({text: displayText(w), startFrame: w.startFrame, endFrame: w.endFrame, highlight: w.highlight})),
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
      cam = {scale: C3.zoomAt(f), dx: 0, dy: 0, originX: 540, originY: C3.ZOOM_ORIGIN_Y};
    }
    const s3 = c === 3 ? C3.faceOnScreen(f) : null;
    arr.push({f, face: fa.face, eyes: fa.eyes, mouth: fa.mouth, cam, clip3Screen: s3});
  }
  faces[c] = arr;
}
out.faces = faces;

out.clip1 = {
  SLAB: C1.SLAB,
  SLAB_OUT_END: C1.SLAB_OUT_END,
  SHAKE: C1.SHAKE,
  CARD: C1.CARD,
  ZOOM: C1.ZOOM,
  LOGO: C1.LOGO,
  LOGO_WIDTH: C1.LOGO_WIDTH,
  LOGO_HEIGHT: C1.LOGO_HEIGHT,
  LOGO_PLATE: C1.LOGO_PLATE,
  LOGO_EYES_TOP: C1.LOGO_EYES_TOP,
  WATERMARK_BLOCKED: C1.WATERMARK_BLOCKED,
};
out.clip2 = {CUE: C2.CUE, LEAD: C2.LEAD, EXIT_FRAMES: C2.EXIT_FRAMES, SLAB: C2L.SLAB, CHIP: C2L.CHIP, BADGE: C2L.BADGE};
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
