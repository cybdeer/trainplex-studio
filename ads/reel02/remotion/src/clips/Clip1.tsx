import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {SAFE} from '../brand';
import {VideoLayer} from '../components/VideoLayer';
import {FaceDebug, isFaceDebug} from './clip3/FaceDebug';
import {FrameInterval} from '../timeline';
import {CalendarCard} from './clip1/CalendarCard';
import {cameraAt} from './clip1/camera';
import {WATERMARK_BLOCKED} from './clip1/cues';
import {HookSlab} from './clip1/HookSlab';
import {LogoPlate} from './clip1/LogoPlate';

/** Local-frame intervals when this clip's graphics overlap WATERMARK_BOX / show a logo (watermark ducks out). */
export const CLIP1_WATERMARK_BLOCKED: FrameInterval[] = WATERMARK_BLOCKED;

/**
 * Clip 1 — HOOK. Presenter video (camera shake on the slab's landing) + slab
 * "POCKET MONEY खत्म?", the calendar card ("20" circled then struck on "बीस तारीख") and the real
 * logo plate on "TrainPlex". Frames are local to the clip; every cue comes from captions.json.
 */
export const Clip1: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = cameraAt(frame);
  return (
    <AbsoluteFill>
      <VideoLayer clip={1} scale={cam.scale} dx={cam.dx} dy={cam.dy} originY={cam.originY} />
      {/* Safe-zone clip (QA check 5): entrance/exit slides never draw outside x 60-1020, y 220-1480. */}
      <AbsoluteFill style={{pointerEvents: 'none', clipPath: `inset(${SAFE.y1}px ${1080 - SAFE.x2}px ${1920 - SAFE.y2}px ${SAFE.x1}px)`}}>
        <HookSlab />
        <CalendarCard />
        <LogoPlate />
      </AbsoluteFill>
      {isFaceDebug() ? <FaceDebug clip={1} /> : null}
    </AbsoluteFill>
  );
};
