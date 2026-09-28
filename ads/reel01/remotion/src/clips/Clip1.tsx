import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {VideoLayer} from '../components/VideoLayer';
import {FrameInterval} from '../timeline';
import {cameraAt} from './clip1/camera';
import {WATERMARK_BLOCKED} from './clip1/cues';
import {HookSlab} from './clip1/HookSlab';
import {LogoPlate} from './clip1/LogoPlate';
import {StatCard} from './clip1/StatCard';

/** Local-frame intervals when this clip's graphics overlap WATERMARK_BOX (watermark ducks out). */
export const CLIP1_WATERMARK_BLOCKED: FrameInterval[] = WATERMARK_BLOCKED;

/**
 * Clip 1 — HOOK. Presenter video (camera shake on the slab's landing, punch-in zoom on "Zero!")
 * + slab "SCROLL बंद कर!", "4 HRS" card → "₹0" counter, and the real logo plate on "TrainPlex".
 * Frames are local to the clip; every cue comes from captions.json (see clip1/cues.ts).
 */
export const Clip1: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = cameraAt(frame);
  return (
    <AbsoluteFill>
      <VideoLayer clip={1} scale={cam.scale} dx={cam.dx} dy={cam.dy} originY={cam.originY} />
      <HookSlab />
      <StatCard />
      <LogoPlate />
    </AbsoluteFill>
  );
};
