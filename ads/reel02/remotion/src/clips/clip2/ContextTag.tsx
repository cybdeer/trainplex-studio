import {Smartphone} from 'lucide-react';
import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SPRING_FIRM, SPRING_OVERSHOOT} from '../../brand';
import {CUE, EXIT_FRAMES, LEAD, TAG_GONE, TAG_IN, TAG_OUT} from './cues';
import {exitFrom, settleFrom, springFrom, TAG, TAG_POS} from './layout';

const OFFSCREEN = 1150;

/**
 * Navy tag "Lecture के बाद • Phone से": slides in from the left on "Lecture"; on "phone से" the
 * second half lights up orange and a Smartphone icon pops; slides out on "AI".
 */
export const ContextTag: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < TAG_IN || frame >= TAG_GONE) return null;

  const enter = settleFrom(frame, fps, TAG_IN, SPRING_FIRM);
  const exit = exitFrom(frame, TAG_OUT, EXIT_FRAMES);
  const x = interpolate(enter, [0, 1, 1.2], [-OFFSCREEN, 0, 20], {extrapolateRight: 'clamp'}) - exit * OFFSCREEN;

  const phoneAt = CUE.phone - LEAD;
  const lit = frame >= phoneAt;
  const icon = springFrom(frame, fps, phoneAt, SPRING_OVERSHOOT);
  const punch = interpolate(frame - phoneAt, [0, 3, 9], [1, 1.08, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const bar = Math.min(1, settleFrom(frame, fps, TAG_IN + 3, SPRING_FIRM));
  const iconSize = Math.round(TAG.fontSize * 0.95);

  return (
    <div
      style={{
        position: 'absolute',
        left: TAG_POS.x1,
        top: TAG_POS.y1,
        width: TAG.w,
        height: TAG.h,
        transform: `translateX(${x}px) scale(${TAG_POS.scale})`,
        transformOrigin: '0 0',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundColor: COLORS.navy,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 18,
          padding: `0 ${TAG.padX}px`,
          fontFamily: FONT_STACK,
          fontWeight: 900,
          fontSize: TAG.fontSize,
          lineHeight: 1,
          color: COLORS.white,
          whiteSpace: 'nowrap',
        }}
      >
        <span>Lecture के बाद</span>
        <span style={{color: COLORS.orange}}>•</span>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 10,
            color: lit ? COLORS.orange : COLORS.white,
            transform: `scale(${punch})`,
          }}
        >
          <span style={{display: 'flex', width: lit ? iconSize : 0, overflow: 'visible', transform: `scale(${icon})`}}>
            <Smartphone size={iconSize} color={COLORS.orange} strokeWidth={2.8} />
          </span>
          Phone से
        </span>
      </div>
      {/* orange edge bar under the tag */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: TAG.h,
          width: TAG.w,
          height: TAG.bar,
          backgroundColor: COLORS.orange,
          transform: `scaleX(${bar})`,
          transformOrigin: '0% 50%',
        }}
      />
    </div>
  );
};
