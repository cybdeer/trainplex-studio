import {cancelRender, continueRender, delayRender, staticFile} from 'remotion';

// Self-hosted brand fonts (copied from @fontsource into public/fonts and ../fonts).
// unicode-range keeps Latin on Inter and Devanagari on Noto Sans Devanagari.
const LATIN =
  'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';
const LATIN_EXT =
  'U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF';
const DEVANAGARI =
  'U+0900-097F,U+1CD0-1CF9,U+200C-200D,U+20A8,U+20B9,U+20F0,U+25CC,U+A830-A839,U+A8E0-A8FF,U+11B00-11B09';

const WEIGHTS = ['600', '700', '800', '900'] as const;

type Face = {family: string; file: string; weight: string; unicodeRange: string};

const FACES: Face[] = WEIGHTS.flatMap((weight) => [
  {family: 'Inter', file: `inter-latin-${weight}-normal.woff2`, weight, unicodeRange: LATIN},
  {family: 'Inter', file: `inter-latin-ext-${weight}-normal.woff2`, weight, unicodeRange: LATIN_EXT},
  {
    family: 'Noto Sans Devanagari',
    file: `noto-sans-devanagari-devanagari-${weight}-normal.woff2`,
    weight,
    unicodeRange: DEVANAGARI,
  },
  {
    family: 'Noto Sans Devanagari',
    file: `noto-sans-devanagari-latin-${weight}-normal.woff2`,
    weight,
    unicodeRange: LATIN,
  },
]);

let started = false;

export const loadBrandFonts = () => {
  if (started || typeof document === 'undefined') {
    return;
  }
  started = true;
  const handle = delayRender('Loading Inter + Noto Sans Devanagari');
  Promise.all(
    FACES.map((f) => {
      const face = new FontFace(f.family, `url('${staticFile(`fonts/${f.file}`)}') format('woff2')`, {
        weight: f.weight,
        style: 'normal',
        unicodeRange: f.unicodeRange,
        display: 'block',
      });
      (document.fonts as unknown as {add: (f: FontFace) => void}).add(face);
      return face.load();
    }),
  )
    .then(() => document.fonts.ready)
    .then(() => continueRender(handle))
    .catch((err) => cancelRender(err));
};
