import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Smartphone} from 'lucide-react';
import {COLORS, SLAB_ROTATION_DEG, SPRING_OVERSHOOT} from '../../brand';
import {OrangeBadge} from '../../components/primitives';
import {CUE, LEAD} from './cues';
import {BADGE, springFrom} from './layout';

/**
 * Orange badge that pops on its spoken cue and holds to the clip end. The spring's overshoot is
 * compressed to a ≤ 7 % pop so the badge never swells into the mouth zone or below y 1185.
 */
const PopBadge: React.FC<{cue: number; children: React.ReactNode}> = ({cue, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const inAt = cue - LEAD;
  // Always laid out (hidden before its cue) so the rows never re-flow when a sibling pops in.
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
        gap: 14,
      }}
    >
      {children}
    </OrangeBadge>
  );
};

/** "सब phone से, कोई fees नहीं, training भी free" — three perk badges in the lower band. */
export const PerkBadges: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      left: BADGE.groupX,
      top: BADGE.groupY,
      transform: `rotate(${SLAB_ROTATION_DEG}deg)`,
      transformOrigin: '0 0',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'flex-start',
      gap: BADGE.rowGap,
    }}
  >
    <div style={{display: 'flex', gap: BADGE.gap}}>
      <PopBadge cue={CUE.phone}>
        <Smartphone size={Math.round(BADGE.fontSize * 0.84)} color={COLORS.white} strokeWidth={2.75} />
        <span>PHONE से</span>
      </PopBadge>
      <PopBadge cue={CUE.fees}>₹0 FEES</PopBadge>
    </div>
    <div style={{display: 'flex', marginLeft: BADGE.row2Indent}}>
      <PopBadge cue={CUE.free}>FREE TRAINING</PopBadge>
    </div>
  </div>
);
