// Face-safe placement for clip graphics (pure: no React/DOM, so QA can run it from Node).
//
// HARD RULE: no graphic may cover Priya's eyes or mouth. Stronger default used here: graphics stay
// clear of the whole (padded) Haar face box over every frame they are on screen, after mapping the
// face through the clip's camera transform. Zones, in preference order per graphic:
//   'top'        top band above the face (y 232 … face top), centred
//   'top-left'   top band beside the face, left of it (x 60 … face left)
//   'top-right'  top band beside the face, right of it (face right … x 1020)
//   'lower'      lower band over the kurti/chest (face bottom … LOWER_MAX), centred
// A graphic is tried at full size in each zone in order, then shrunk (down to its minScale) zone by
// zone; if nothing clears the face box, a second pass only protects the eyes + mouth rects (the
// hard rule). If even that fails the bundle throws — a re-tracked face can never silently produce
// a graphic over the eyes/mouth.
import {SAFE} from '../brand';
import {CLIP_FRAMES, ClipId, faceAt, Rect, rectsOverlap} from '../timeline';

/** Graphics start below the progress bar (y 220–228). */
export const TOP_MIN = SAFE.y1 + 12; // 232
/** Top band never extends below this, even when the face sits low. */
export const TOP_BAND_MAX = 560;
/** Lower-band graphics end above a single-line caption block (bottom 1400, ≈ 118 px tall). */
export const LOWER_MAX = 1272;
/** Clearance between a graphic and the padded face box / eyes / mouth (px). */
export const FACE_PAD = 14;
const EYE_MOUTH_PAD = 10;

export type Zone = 'top' | 'top-left' | 'top-right' | 'lower';
export type Placement = Rect & {scale: number; zone: Zone; w: number; h: number; relaxed: boolean};
/** Maps a source-video rect to screen space at local frame f (camera zoom / shake). */
export type CameraMap = (r: Rect, f: number) => Rect;
const identity: CameraMap = (r) => r;

const pad = (r: Rect, p: number): Rect => ({x1: r.x1 - p, y1: r.y1 - p, x2: r.x2 + p, y2: r.y2 + p});
const union = (a: Rect, b: Rect): Rect => ({
  x1: Math.min(a.x1, b.x1),
  y1: Math.min(a.y1, b.y1),
  x2: Math.max(a.x2, b.x2),
  y2: Math.max(a.y2, b.y2),
});

/** Screen-space face / eyes / mouth unions over [from, to] (padded ±3 f: samples are every 3rd frame). */
export const faceWindow = (clip: ClipId, from: number, to: number, cam: CameraMap = identity) => {
  let face: Rect | null = null;
  let eyes: Rect | null = null;
  let mouth: Rect | null = null;
  const a = Math.max(0, Math.floor(from) - 3);
  const b = Math.min(CLIP_FRAMES[clip] - 1, Math.ceil(to) + 3);
  for (let f = a; f <= b; f++) {
    const z = faceAt(clip, f);
    const F = cam(z.face, f);
    const E = cam(z.eyes, f);
    const M = cam(z.mouth, f);
    face = face ? union(face, F) : F;
    eyes = eyes ? union(eyes, E) : E;
    mouth = mouth ? union(mouth, M) : M;
  }
  return {face: face!, eyes: eyes!, mouth: mouth!};
};

/** Axis-aligned bounds of a w×h box rotated by `deg`. */
export const rotatedBounds = (w: number, h: number, deg: number) => {
  const r = (Math.abs(deg) * Math.PI) / 180;
  return {w: w * Math.cos(r) + h * Math.sin(r), h: w * Math.sin(r) + h * Math.cos(r)};
};

type Spec = {
  clip: ClipId;
  from: number; // first local frame the graphic is visible
  to: number; // last local frame the graphic is visible
  w: number; // full-size bounding box (already including rotation)
  h: number;
  zones: Zone[];
  minScale?: number; // default 0.7
  cam?: CameraMap;
  extraPad?: number; // e.g. camera-shake amplitude
  /**
   * 'auto' (default): lower band hugs the chin side (max gap to the caption block below, which
   * grows upward when a chunk wraps to 2 lines); top/side bands are centred. 'centre' / 'near' force it.
   */
  vAlign?: 'auto' | 'centre' | 'near';
  name: string;
};

const SCALES = (min: number) => {
  const out: number[] = [];
  for (let s = 1; s >= min - 1e-9; s -= 0.05) out.push(Math.round(s * 100) / 100);
  return out;
};

const tryZone = (
  zone: Zone,
  w: number,
  h: number,
  blockers: Rect[],
  vAlign: 'auto' | 'centre' | 'near',
): Rect | null => {
  const U = blockers.reduce(union);
  // integer-snap outward (camera springs leave sub-pixel residue that would fail strict overlap tests)
  const B: Rect = {x1: Math.floor(U.x1), y1: Math.floor(U.y1), x2: Math.ceil(U.x2), y2: Math.ceil(U.y2)};
  let band: Rect;
  switch (zone) {
    case 'top':
      band = {x1: SAFE.x1, x2: SAFE.x2, y1: TOP_MIN, y2: Math.min(TOP_BAND_MAX, B.y1)};
      break;
    case 'top-left':
      band = {x1: SAFE.x1, x2: Math.min(SAFE.x2, B.x1), y1: TOP_MIN, y2: TOP_BAND_MAX};
      break;
    case 'top-right':
      band = {x1: Math.max(SAFE.x1, B.x2), x2: SAFE.x2, y1: TOP_MIN, y2: TOP_BAND_MAX};
      break;
    case 'lower':
      band = {x1: SAFE.x1, x2: SAFE.x2, y1: Math.max(TOP_MIN, B.y2), y2: LOWER_MAX};
      break;
  }
  if (band.x2 - band.x1 < w || band.y2 - band.y1 < h) return null;
  const cx = zone === 'top-left' ? band.x1 + (band.x2 - band.x1 - w) / 2 : zone === 'top-right' ? band.x1 + (band.x2 - band.x1 - w) / 2 : 540 - w / 2;
  const x1 = Math.max(band.x1, Math.min(band.x2 - w, cx));
  const snap = (v: number, lo: number, hi: number) => Math.max(Math.ceil(lo), Math.min(Math.floor(hi), v));
  let y1: number;
  if (vAlign === 'near' || (vAlign === 'auto' && zone === 'lower')) {
    y1 = zone === 'lower' ? band.y1 : band.y2 - h;
  } else {
    y1 = band.y1 + (band.y2 - band.y1 - h) / 2;
  }
  const rx = snap(Math.round(x1), band.x1, band.x2 - Math.ceil(w));
  const ry = snap(Math.round(y1), band.y1, band.y2 - Math.ceil(h));
  const r = {x1: rx, y1: ry, x2: rx + Math.ceil(w), y2: ry + Math.ceil(h)};
  const hard = blockers.map((b) => ({x1: Math.floor(b.x1), y1: Math.floor(b.y1), x2: Math.ceil(b.x2), y2: Math.ceil(b.y2)}));
  if (hard.some((b) => rectsOverlap(r, b))) return null;
  return r;
};

/** Place a graphic of size w×h somewhere face-safe (see header). Throws if impossible. */
export const placeFaceSafe = (spec: Spec): Placement => {
  const {clip, from, to, zones, minScale = 0.7, cam, extraPad = 0, vAlign = 'auto'} = spec;
  const fw = faceWindow(clip, from, to, cam);
  const strict = [pad(fw.face, FACE_PAD + extraPad)];
  const relaxed = [pad(fw.eyes, EYE_MOUTH_PAD + extraPad), pad(fw.mouth, EYE_MOUTH_PAD + extraPad)];
  for (const [blockers, isRelaxed] of [
    [strict, false],
    [relaxed, true],
  ] as const) {
    for (const zone of zones) {
      for (const s of SCALES(minScale)) {
        const w = spec.w * s;
        const h = spec.h * s;
        const r = tryZone(zone, w, h, blockers as Rect[], vAlign);
        if (r) return {...r, scale: s, zone, w, h, relaxed: isRelaxed};
      }
    }
  }
  throw new Error(
    `faceSafe: "${spec.name}" (${spec.w}x${spec.h}) cannot be placed clear of the face in clip ${clip} f${from}-${to} (zones ${zones.join(',')})`,
  );
};
