import React, {useContext} from 'react';
import {HideVideoContext} from './components/VideoLayer';
import {AbsoluteFill, Sequence} from 'remotion';
import {Captions} from './captions/Captions';
import {Clip1} from './clips/Clip1';
import {Clip2} from './clips/Clip2';
import {Clip3} from './clips/Clip3';
import {EndScreen} from './endscreen/EndScreen';
import {JoinFlash, ProgressBar, Watermark} from './global/GlobalOverlays';
import {OrangeWipe} from './transitions/OrangeWipe';
import {PlaceholderBanner} from './components/PlaceholderBanner';
import {
  CLIP_FRAMES,
  CLIP_START,
  END_SCREEN_FRAMES,
  END_SCREEN_START,
  WIPE_FRAMES,
  WIPE_START,
} from './timeline';

/**
 * Master timeline: clip1 -> clip2 -> clip3 (hard cuts + 4-frame white flash) -> orange wipe ->
 * animated logo CTA end screen. Layer order (bottom -> top): clip video + clip graphics,
 * captions, watermark + progress bar, join flash, end screen, wipe.
 */
export const Reel: React.FC = () => {
  const graphicsOnly = useContext(HideVideoContext);
  return (
    <AbsoluteFill style={{backgroundColor: graphicsOnly ? 'transparent' : '#000'}}>
      <Sequence name="Clip 1 — Hook" from={CLIP_START[1]} durationInFrames={CLIP_FRAMES[1]}>
        <Clip1 />
        <Captions clip={1} />
      </Sequence>
      <Sequence name="Clip 2 — Tasks" from={CLIP_START[2]} durationInFrames={CLIP_FRAMES[2]}>
        <Clip2 />
        <Captions clip={2} />
      </Sequence>
      <Sequence name="Clip 3 — Earning + CTA" from={CLIP_START[3]} durationInFrames={CLIP_FRAMES[3]}>
        <Clip3 />
        <Captions clip={3} />
      </Sequence>
      <Sequence name="Global overlays" from={0} durationInFrames={END_SCREEN_START}>
        <Watermark />
        <ProgressBar />
        <JoinFlash />
      </Sequence>
      <Sequence name="End screen" from={END_SCREEN_START} durationInFrames={END_SCREEN_FRAMES}>
        <EndScreen />
      </Sequence>
      <Sequence name="Orange wipe" from={WIPE_START} durationInFrames={WIPE_FRAMES}>
        <OrangeWipe />
      </Sequence>
      <PlaceholderBanner />
    </AbsoluteFill>
  );
};
