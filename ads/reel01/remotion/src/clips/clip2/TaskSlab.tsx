import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK, SLAB_ROTATION_DEG, SPRING, SPRING_FIRM} from '../../brand';
import {CUE, EXIT_FRAMES, LEAD} from './cues';
import {exitFrom, settleFrom, SLAB, springFrom} from './layout';

export const SLAB_IN = Math.max(0, CUE.ai - LEAD);
export const SLAB_OUT = CUE.sab; // clears together with the chips
export const SLAB_GONE = SLAB_OUT + EXIT_FRAMES;

const OFFSCREEN = 1150; // px travelled from/to the left edge

/** Navy "AI TRAINER TASKS" label slab — slides in from the left, orange underline on "tasks". */
export const TaskSlab: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < SLAB_IN || frame >= SLAB_GONE) return null;

  const enter = settleFrom(frame, fps, SLAB_IN, SPRING_FIRM);
  const exit = exitFrom(frame, SLAB_OUT, EXIT_FRAMES);
  // Over a 1150 px travel a raw spring overshoots ~180 px; compress it to a crisp ≤ 24 px settle.
  const x = interpolate(enter, [0, 1, 1.2], [-OFFSCREEN, 0, 24], {extrapolateRight: 'clamp'}) - exit * OFFSCREEN;

  // "tasks": underline wipes in left → right, slab gives a small confident punch.
  const bar = springFrom(frame, fps, CUE.tasks - LEAD, SPRING);
  const punch = interpolate(frame - (CUE.tasks - LEAD), [0, 3, 9], [1, 1.035, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: SLAB.left,
        top: SLAB.top,
        transform: `translateX(${x}px) rotate(${SLAB_ROTATION_DEG}deg)`,
        transformOrigin: '50% 50%',
      }}
    >
      {/* punch grows from the left edge so the slab never pokes out of the safe zone */}
      <div style={{transform: `scale(${punch})`, transformOrigin: '0% 50%'}}>
        <div
          style={{
            height: SLAB.height,
            display: 'flex',
            alignItems: 'center',
            padding: `0 ${SLAB.padX}px`,
            backgroundColor: COLORS.navy,
            color: COLORS.white,
            fontFamily: FONT_STACK,
            fontWeight: 900,
            fontSize: SLAB.fontSize,
            lineHeight: 1,
            letterSpacing: '0.01em',
            whiteSpace: 'nowrap',
            boxSizing: 'border-box',
          }}
        >
          AI TRAINER TASKS
        </div>
        <div
          style={{
            height: SLAB.barHeight,
            backgroundColor: COLORS.orange,
            transform: `scaleX(${Math.min(1, Math.max(0, bar))})`,
            transformOrigin: '0% 50%',
          }}
        />
      </div>
    </div>
  );
};
