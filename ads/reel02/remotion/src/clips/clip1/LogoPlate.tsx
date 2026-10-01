import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, SPRING_FIRM} from '../../brand';
import {Logo} from '../../components/primitives';
import {LOGO, LOGO_PLATE, LOGO_POS, LOGO_WIDTH} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/**
 * On the spoken word "TrainPlex": the real logo (verbatim PNG) pops in on a cream plate (sharp
 * corners) with an orange underline bar; holds to the end of the clip. Position from the face
 * track (LOGO_POS); the plate opens horizontally only, so its vertical bounds never move.
 */
export const LogoPlate: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < LOGO.inAt - 1) return null;

  const plateIn = interpolate(frame, [LOGO.inAt - 1, LOGO.inAt + 4], [0, 1], {...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1)});
  const logoIn = spring({frame: frame - (LOGO.inAt + 1) + 2, fps, config: SPRING_FIRM});
  const barIn = interpolate(frame, [LOGO.inAt + 2, LOGO.inAt + 7], [0, 1], {...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1)});

  const cx = (LOGO_POS.x1 + LOGO_POS.x2) / 2;
  const left = Math.round(cx - LOGO_PLATE.w / 2);
  const top = LOGO_POS.y1 + Math.round((LOGO_POS.h - LOGO_PLATE.h) / 2);

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left,
          top,
          width: LOGO_PLATE.w,
          height: LOGO_PLATE.h,
          backgroundColor: COLORS.cream,
          borderRadius: 0,
          transform: `scaleX(${plateIn})`,
          transformOrigin: '50% 50%',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left,
          top: top + LOGO_PLATE.h - LOGO.bar,
          width: LOGO_PLATE.w,
          height: LOGO.bar,
          backgroundColor: COLORS.orange,
          transform: `scaleX(${barIn})`,
          transformOrigin: '50% 50%',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: Math.round(cx - LOGO_WIDTH / 2),
          top: top + LOGO.padY,
          visibility: frame >= LOGO.inAt + 1 ? 'visible' : 'hidden',
          transform: `scale(${interpolate(logoIn, [0, 1], [0.5, 1])})`,
          transformOrigin: '50% 50%',
        }}
      >
        <Logo width={LOGO_WIDTH} />
      </div>
    </AbsoluteFill>
  );
};
