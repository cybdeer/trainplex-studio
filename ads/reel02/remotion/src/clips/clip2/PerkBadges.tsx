import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {SLAB_ROTATION_DEG, SPRING_OVERSHOOT} from '../../brand';
import {OrangeBadge} from '../../components/primitives';
import {FEES_IN, TRAINING_IN} from './cues';
import {BADGE, BADGE_POS, springFrom} from './layout';

/**
 * Orange badge that pops on its cue and holds to the clip end (≥ 1.2 s guaranteed by cues.ts).
 * The spring's overshoot is compressed to a ≤ 7 % pop (the placement reserves that headroom).
 */
const PopBadge: React.FC<{inAt: number; children: React.ReactNode}> = ({inAt, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = springFrom(frame, fps, inAt, SPRING_OVERSHOOT);
  const scale = interpolate(s, [0, 1, 1.3], [0.3, 1, 1.07], {extrapolateRight: 'clamp'});
  const opacity = interpolate(frame - inAt, [0, 2], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <OrangeBadge
      fontSize={BADGE.fontSize}
      style={{
        transform: `scale(${scale})`, // rotation comes from the group
        opacity,
        lineHeight: 1,
        padding: `${BADGE.padY}px ${BADGE.padX}px`,
      }}
    >
      {children}
    </OrangeBadge>
  );
};

/** "कोई fees नहीं" → ₹0 FEES, "training भी free" → FREE TRAINING — one row in the face-safe band. */
export const PerkBadges: React.FC = () => {
  const cx = (BADGE_POS.x1 + BADGE_POS.x2) / 2;
  const cy = (BADGE_POS.y1 + BADGE_POS.y2) / 2;
  const s = BADGE_POS.scale;
  return (
    <div
      style={{
        position: 'absolute',
        left: cx - BADGE.rowW / 2,
        top: cy - BADGE.rowH / 2,
        width: BADGE.rowW,
        height: BADGE.rowH,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: BADGE.gap,
        transform: `rotate(${SLAB_ROTATION_DEG}deg) scale(${s})`,
        transformOrigin: '50% 50%',
      }}
    >
      <PopBadge inAt={FEES_IN}>₹0 FEES</PopBadge>
      <PopBadge inAt={TRAINING_IN}>FREE TRAINING</PopBadge>
    </div>
  );
};
