import React from 'react';
import {AbsoluteFill} from 'remotion';
import {VideoLayer} from '../components/VideoLayer';
import {FrameInterval} from '../timeline';

/** Local-frame intervals when this clip's graphics overlap WATERMARK_BOX (watermark ducks out). */
export const CLIP3_WATERMARK_BLOCKED: FrameInterval[] = [];

/** Clip 3 — presenter video + clip-specific motion graphics. Frames are local to the clip. */
export const Clip3: React.FC = () => {
  return (
    <AbsoluteFill>
      <VideoLayer clip={3} />
    </AbsoluteFill>
  );
};
