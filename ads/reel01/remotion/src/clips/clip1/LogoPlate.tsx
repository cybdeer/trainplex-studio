import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, SPRING_FIRM} from '../../brand';
import {Logo} from '../../components/primitives';
import {LOGO, LOGO_PLATE, LOGO_WIDTH} from './cues';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/**
 * On "TrainPlex": the real logo pops in top-centre on a cream plate (sharp corners) with an
 * orange underline bar; holds to the end of the clip. The plate opens horizontally only
 * (scaleX), so its vertical bounds never move and never reach the eyes; the logo pops inside.
 */
export const LogoPlate: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < LOGO.inAt) return null;

  // plate snaps open (expo-out, already ~70 % wide on the cue frame), then the logo pops inside it
  // (opaque scale pop — its spring overshoot stays within the plate padding), then the bar draws.
  const plateIn = interpolate(frame, [LOGO.inAt - 1, LOGO.inAt + 4], [0, 1], {
    ...clamp,
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  // phase-led 2 frames so the pop is already moving when the logo first shows (springs start at rest)
  const logoIn = spring({frame: frame - (LOGO.inAt + 1) + 2, fps, config: SPRING_FIRM});
  const barIn = interpolate(frame, [LOGO.inAt + 2, LOGO.inAt + 7], [0, 1], {
    ...clamp,
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const left = 540 - LOGO_PLATE.width / 2;
  const top = LOGO.top;

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {/* cream plate */}
      <div
        style={{
          position: 'absolute',
          left,
          top,
          width: LOGO_PLATE.width,
          height: LOGO_PLATE.height,
          backgroundColor: COLORS.cream,
          borderRadius: 0,
          transform: `scaleX(${plateIn})`,
          transformOrigin: '50% 50%',
        }}
      />
      {/* orange underline bar along the plate's bottom edge */}
      <div
        style={{
          position: 'absolute',
          left,
          top: top + LOGO_PLATE.height - LOGO.bar,
          width: LOGO_PLATE.width,
          height: LOGO.bar,
          backgroundColor: COLORS.orange,
          transform: `scaleX(${barIn})`,
          transformOrigin: '50% 50%',
        }}
      />
      {/* real logo, verbatim */}
      <div
        style={{
          position: 'absolute',
          left: 540 - LOGO_WIDTH / 2,
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
