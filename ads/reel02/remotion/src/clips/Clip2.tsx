import React from 'react';
import {AbsoluteFill} from 'remotion';
import {SAFE} from '../brand';
import {VideoLayer} from '../components/VideoLayer';
import {FaceDebug, isFaceDebug} from './clip3/FaceDebug';
import {FrameInterval} from '../timeline';
import {ContextTag} from './clip2/ContextTag';
import {WATERMARK_BLOCKED} from './clip2/layout';
import {PerkBadges} from './clip2/PerkBadges';
import {TaskChips} from './clip2/TaskChips';

/** Local-frame intervals when this clip's graphics overlap WATERMARK_BOX (watermark ducks out). */
export const CLIP2_WATERMARK_BLOCKED: FrameInterval[] = WATERMARK_BLOCKED;

/**
 * Clip 2 — presenter video + tag "Lecture के बाद • Phone से", task tiles (Voice record / Photos /
 * Text check) and perk badges (₹0 FEES / FREE TRAINING). Frames are local to the clip.
 */
export const Clip2: React.FC = () => (
  <AbsoluteFill>
    <VideoLayer clip={2} />
    {/* Safe-zone clip (QA check 5): entrance/exit slides never draw outside x 60-1020, y 220-1480. */}
    <AbsoluteFill style={{pointerEvents: 'none', clipPath: `inset(${SAFE.y1}px ${1080 - SAFE.x2}px ${1920 - SAFE.y2}px ${SAFE.x1}px)`}}>
      <ContextTag />
      <TaskChips />
      <PerkBadges />
      {isFaceDebug() ? <FaceDebug clip={2} /> : null}
    </AbsoluteFill>
  </AbsoluteFill>
);
