import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Camera, FileText, LucideIcon, Mic} from 'lucide-react';
import {COLORS, FONT_STACK, SPRING, SPRING_FIRM, SPRING_OVERSHOOT} from '../../brand';
import {SquareBullet, WhiteCard} from '../../components/primitives';
import {CHIP_EXIT_STAGGER, CUE, EXIT_FRAMES, LEAD} from './cues';
import {CHIP, chipTop, exitFrom, springFrom} from './layout';

type Task = {cue: number; icon: LucideIcon; lines: [string, string]};

const TASKS: Task[] = [
  {cue: CUE.voice, icon: Mic, lines: ['Voice', 'Recording']},
  {cue: CUE.photos, icon: Camera, lines: ['Photo', 'Collection']},
  {cue: CUE.text, icon: FileText, lines: ['Text', 'Annotation']},
];

export const CHIPS_OUT = CUE.sab;
export const CHIPS_GONE = CHIPS_OUT + (TASKS.length - 1) * CHIP_EXIT_STAGGER + EXIT_FRAMES;

const TRAVEL = 420; // px: from just beyond the right canvas edge

const Chip: React.FC<{task: Task; index: number}> = ({task, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const inAt = task.cue - LEAD;
  const outAt = CHIPS_OUT + index * CHIP_EXIT_STAGGER;
  if (frame < inAt || frame >= outAt + EXIT_FRAMES) return null;

  // Firm spring, clamped at rest: the chip must never overshoot leftwards towards his mouth.
  const enter = Math.min(1, springFrom(frame, fps, inAt, SPRING_FIRM));
  const exit = exitFrom(frame, outAt, EXIT_FRAMES);
  const x = interpolate(enter, [0, 1], [TRAVEL, 0]) + exit * TRAVEL;

  // bullet + icon settle in a beat after the card lands
  const bullet = springFrom(frame, fps, inAt + 3, SPRING);
  const icon = springFrom(frame, fps, inAt + 4, SPRING_OVERSHOOT);
  const Icon = task.icon;

  return (
    <WhiteCard
      style={{
        position: 'absolute',
        left: CHIP.x,
        top: chipTop(index),
        width: CHIP.width,
        height: CHIP.height,
        transform: `translateX(${x}px)`,
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '0 18px 0 20px',
      }}
    >
      <div style={{transform: `scale(${bullet})`}}>
        <SquareBullet />
      </div>
      <div
        style={{
          flex: 1,
          fontFamily: FONT_STACK,
          fontWeight: 800,
          fontSize: CHIP.fontSize,
          lineHeight: 1.08,
          color: COLORS.navy,
          letterSpacing: '-0.01em',
          whiteSpace: 'nowrap',
        }}
      >
        {task.lines[0]}
        <br />
        {task.lines[1]}
      </div>
      <div style={{transform: `scale(${icon})`, display: 'flex'}}>
        <Icon size={CHIP.iconSize} color={COLORS.orange} strokeWidth={2.5} />
      </div>
    </WhiteCard>
  );
};

/** Three white task chips stacking in on the right as each task is spoken; cleared on "सब". */
export const TaskChips: React.FC = () => (
  <>
    {TASKS.map((t, i) => (
      <Chip key={t.lines.join(' ')} task={t} index={i} />
    ))}
  </>
);
