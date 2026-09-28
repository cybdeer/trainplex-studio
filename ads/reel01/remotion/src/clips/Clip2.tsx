import React from 'react';
import {AbsoluteFill} from 'remotion';
import {VideoLayer} from '../components/VideoLayer';
import {FrameInterval} from '../timeline';

/** Local-frame intervals when this clip's graphics overlap WATERMARK_BOX (watermark ducks out). */
export const CLIP2_WATERMARK_BLOCKED: FrameInterval[] = [];

/** Clip 2 — presenter video + clip-specific motion graphics. Frames are local to the clip. */
export const Clip2: React.FC = () => {
  return (
    <AbsoluteFill>
      <VideoLayer clip={2} />
    </AbsoluteFill>
  );
};
