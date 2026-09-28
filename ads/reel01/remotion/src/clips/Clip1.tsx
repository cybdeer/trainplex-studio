import React from 'react';
import {AbsoluteFill} from 'remotion';
import {VideoLayer} from '../components/VideoLayer';
import {FrameInterval} from '../timeline';

/** Local-frame intervals when this clip's graphics overlap WATERMARK_BOX (watermark ducks out). */
export const CLIP1_WATERMARK_BLOCKED: FrameInterval[] = [];

/** Clip 1 — presenter video + clip-specific motion graphics. Frames are local to the clip. */
export const Clip1: React.FC = () => {
  return (
    <AbsoluteFill>
      <VideoLayer clip={1} />
    </AbsoluteFill>
  );
};
