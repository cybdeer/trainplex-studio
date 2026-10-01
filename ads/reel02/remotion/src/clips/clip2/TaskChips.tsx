import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Camera, CheckSquare, LucideIcon, Mic} from 'lucide-react';
import {COLORS, FONT_STACK, SPRING, SPRING_OVERSHOOT} from '../../brand';
import {CHIP_EXIT_STAGGER, CHIPS_OUT, CUE, EXIT_FRAMES, LEAD} from './cues';
import {CHIP, CHIP_POS, exitFrom, springFrom} from './layout';

type Task = {cue: number; icon: LucideIcon; label: string};

// Each tile pops on its own spoken phrase: "voice record", "photos", "text check".
const TASKS: Task[] = [
  {cue: CUE.voice, icon: Mic, label: 'Voice record'},
  {cue: CUE.photos, icon: Camera, label: 'Photos'},
  {cue: CUE.text, icon: CheckSquare, label: 'Text check'},
];

const Chip: React.FC<{task: Task; index: number}> = ({task, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const inAt = task.cue - LEAD;
  const outAt = CHIPS_OUT + index * CHIP_EXIT_STAGGER;
  if (frame < inAt || frame >= outAt + EXIT_FRAMES) return null;

  // opaque pop from below (compressed overshoot ≤ 6 %), drop-out on exit
  const s = springFrom(frame, fps, inAt, SPRING_OVERSHOOT);
  const scale = interpolate(s, [0, 1, 1.3], [0.4, 1, 1.06], {extrapolateRight: 'clamp'});
  const rise = interpolate(s, [0, 1], [40, 0], {extrapolateRight: 'clamp'});
  const exit = exitFrom(frame, outAt, EXIT_FRAMES);
  const icon = springFrom(frame, fps, inAt + 3, SPRING_OVERSHOOT);
  const bar = Math.min(1, springFrom(frame, fps, inAt + 2, SPRING));
  const Icon = task.icon;

  return (
    <div
      style={{
        position: 'absolute',
        left: index * (CHIP.w + CHIP.gap),
        top: 0,
        width: CHIP.w,
        height: CHIP.h,
        transform: `translateY(${rise + exit * 260}px) scale(${scale})`,
        opacity: 1 - exit,
        backgroundColor: COLORS.white,
        border: `2px solid ${COLORS.border}`,
        boxSizing: 'border-box',
        borderRadius: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
      }}
    >
      <div style={{transform: `scale(${icon})`, display: 'flex'}}>
        <Icon size={CHIP.iconSize} color={COLORS.orange} strokeWidth={2.4} />
      </div>
      <div
        style={{
          fontFamily: FONT_STACK,
          fontWeight: 800,
          fontSize: CHIP.fontSize,
          lineHeight: 1.05,
          color: COLORS.navy,
          letterSpacing: '-0.01em',
          whiteSpace: 'nowrap',
        }}
      >
        {task.label}
      </div>
      {/* orange base bar */}
      <div
        style={{
          position: 'absolute',
          left: -2,
          right: -2,
          bottom: -2,
          height: 8,
          backgroundColor: COLORS.orange,
          transform: `scaleX(${bar})`,
          transformOrigin: '0% 50%',
        }}
      />
    </div>
  );
};

/** Three white task tiles (lucide icon over label) popping in a row as each task is spoken. */
export const TaskChips: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      left: CHIP_POS.x1,
      top: CHIP_POS.y1,
      width: CHIP_POS.w / CHIP_POS.scale,
      height: CHIP_POS.h / CHIP_POS.scale,
      transform: `scale(${CHIP_POS.scale})`,
      transformOrigin: '0 0',
    }}
  >
    {TASKS.map((t, i) => (
      <Chip key={t.label} task={t} index={i} />
    ))}
  </div>
);
