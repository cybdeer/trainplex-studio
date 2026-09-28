import React from 'react';
import {Img, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, LOGO_ASPECT, LOGO_FILE, SLAB_ROTATION_DEG, SPRING} from '../brand';

/** Spring 0 -> 1 starting at `delay` (frames). Snappy brand defaults. */
export const useSpringIn = (delay = 0, config: Partial<typeof SPRING> = SPRING, durationInFrames?: number) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: frame - delay, fps, config, durationInFrames});
};

/** The real TrainPlex logo (transparent PNG). Width only — height follows the file's aspect. */
export const Logo: React.FC<{width: number; style?: React.CSSProperties}> = ({width, style}) => (
  <Img
    src={staticFile(LOGO_FILE)}
    style={{width, height: width / LOGO_ASPECT, display: 'block', objectFit: 'contain', ...style}}
  />
);

export const logoHeightFor = (width: number) => width / LOGO_ASPECT;

/** 16 px orange square bullet (sharp corners). */
export const SquareBullet: React.FC<{size?: number}> = ({size = 16}) => (
  <div style={{width: size, height: size, backgroundColor: COLORS.orange, flex: 'none'}} />
);

/** White card: flat fill, 2 px #E8E3DA border, sharp 90° corners. */
export const WhiteCard: React.FC<{style?: React.CSSProperties; children?: React.ReactNode}> = ({style, children}) => (
  <div
    style={{
      backgroundColor: COLORS.white,
      border: `2px solid ${COLORS.border}`,
      borderRadius: 0,
      boxSizing: 'border-box',
      ...style,
    }}
  >
    {children}
  </div>
);

/** Orange badge rotated -4°, white 900 text. */
export const OrangeBadge: React.FC<{fontSize?: number; style?: React.CSSProperties; children?: React.ReactNode}> = ({
  fontSize = 64,
  style,
  children,
}) => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: fontSize * 0.25,
      backgroundColor: COLORS.orange,
      color: COLORS.white,
      fontFamily: FONT_STACK,
      fontWeight: 900,
      fontSize,
      lineHeight: 1.25,
      padding: `${fontSize * 0.14}px ${fontSize * 0.34}px`,
      transform: `rotate(${SLAB_ROTATION_DEG}deg)`,
      whiteSpace: 'nowrap',
      borderRadius: 0,
      ...style,
    }}
  >
    {children}
  </div>
);

/** Base text style using the dual-script font stack. */
export const brandText = (fontSize: number, fontWeight: 600 | 700 | 800 | 900, color: string): React.CSSProperties => ({
  fontFamily: FONT_STACK,
  fontSize,
  fontWeight,
  color,
  lineHeight: 1.2,
});
