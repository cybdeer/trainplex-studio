import React from 'react';
import {AbsoluteFill} from 'remotion';
import {VideoLayer} from '../components/VideoLayer';
import {FrameInterval} from '../timeline';
import {PerkBadges} from './clip2/PerkBadges';
import {TaskChips} from './clip2/TaskChips';
import {SLAB_GONE, SLAB_IN, TaskSlab} from './clip2/TaskSlab';

/**
 * Local-frame intervals when this clip's graphics overlap WATERMARK_BOX (watermark ducks out).
 * The "AI TRAINER TASKS" slab covers the box from its entrance until it has fully exited.
 */
export const CLIP2_WATERMARK_BLOCKED: FrameInterval[] = [[SLAB_IN, SLAB_GONE]];

/** Clip 2 — presenter video + clip-specific motion graphics. Frames are local to the clip. */
export const Clip2: React.FC = () => {
  return (
    <AbsoluteFill>
      <VideoLayer clip={2} />
      <AbsoluteFill style={{pointerEvents: 'none'}}>
        <TaskSlab />
        <TaskChips />
        <PerkBadges />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
