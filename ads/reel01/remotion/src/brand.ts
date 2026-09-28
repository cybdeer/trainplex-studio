// TrainPlex brand system — exact values from the brief. Do not add colours here.
export const COLORS = {
  cream: '#FAF7F2', // end-screen background, light caption plates
  navy: '#1A1A5E', // primary text on light, CTA bar, dark plates
  orange: '#FF6B35', // highlights, keyword emphasis, accents, TLD
  white: '#FFFFFF', // caption text on video
  border: '#E8E3DA', // 2 px card borders / end-screen grid (named in the brief)
} as const;

// Every text element uses this stack so Latin (Inter) and Devanagari (Noto Sans Devanagari)
// both render with correct shaping.
export const FONT_STACK = '"Inter", "Noto Sans Devanagari", sans-serif';

export const CANVAS = {width: 1080, height: 1920} as const;

// Instagram Reels safe zone: all text + key graphics inside this box.
export const SAFE = {x1: 60, x2: 1020, y1: 220, y2: 1480} as const;
export const CAPTION_ZONE = {y1: 1180, y2: 1420} as const;

// "Snappy and confident" motion: damping ~12-14, stiffness ~180-220.
export const SPRING = {damping: 13, stiffness: 200, mass: 1} as const;
export const SPRING_OVERSHOOT = {damping: 12, stiffness: 210, mass: 1} as const;
export const SPRING_FIRM = {damping: 14, stiffness: 190, mass: 1} as const;

export const ENTRANCE_FRAMES = 8; // 6-10 frame entrances
export const MAX_FADE_FRAMES = 12; // no slow fades longer than this

export const SLAB_ROTATION_DEG = -4;

// Real logo (transparent version generated from logo/trainplex_logo_source.png — never redrawn).
export const LOGO_FILE = 'trainplex_logo_transparent.png';
export const LOGO_ASPECT = 862 / 956; // width / height of the transparent crop (stacked lockup)
