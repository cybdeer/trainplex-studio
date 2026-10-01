import React from 'react';
import {AbsoluteFill, Composition} from 'remotion';
import {Captions} from './captions/Captions';
import {Clip1} from './clips/Clip1';
import {Clip2} from './clips/Clip2';
import {Clip3} from './clips/Clip3';
import {HideVideoContext} from './components/VideoLayer';
import {EndScreen} from './endscreen/EndScreen';
import {loadBrandFonts} from './fonts';
import {Reel} from './Reel';
import {CLIP_FRAMES, END_SCREEN_FRAMES, FPS, TOTAL_FRAMES, WIPE_FRAMES} from './timeline';
import {OrangeWipe} from './transitions/OrangeWipe';
import {PlaceholderBanner} from './components/PlaceholderBanner';

loadBrandFonts();

const W = 1080;
const H = 1920;

// Per-part preview compositions let each part be rendered/QA'd in isolation.
const ClipPreview1: React.FC = () => (
  <AbsoluteFill>
    <Clip1 />
    <Captions clip={1} />
    <PlaceholderBanner />
  </AbsoluteFill>
);
const ClipPreview2: React.FC = () => (
  <AbsoluteFill>
    <Clip2 />
    <Captions clip={2} />
    <PlaceholderBanner />
  </AbsoluteFill>
);
const ClipPreview3: React.FC = () => (
  <AbsoluteFill>
    <Clip3 />
    <Captions clip={3} />
    <PlaceholderBanner />
  </AbsoluteFill>
);

const EndScreenPreview: React.FC = () => (
  <AbsoluteFill>
    <EndScreen />
    <PlaceholderBanner />
  </AbsoluteFill>
);

// QA: graphics layer only (transparent background) — used for brand-colour and safe-zone checks.
const ReelGraphicsOnly: React.FC = () => (
  <HideVideoContext.Provider value>
    <Reel />
  </HideVideoContext.Provider>
);

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Reel02" component={Reel} durationInFrames={TOTAL_FRAMES} fps={FPS} width={W} height={H} />
    <Composition id="Reel02Graphics" component={ReelGraphicsOnly} durationInFrames={TOTAL_FRAMES} fps={FPS} width={W} height={H} />
    <Composition id="Clip1" component={ClipPreview1} durationInFrames={CLIP_FRAMES[1]} fps={FPS} width={W} height={H} />
    <Composition id="Clip2" component={ClipPreview2} durationInFrames={CLIP_FRAMES[2]} fps={FPS} width={W} height={H} />
    <Composition id="Clip3" component={ClipPreview3} durationInFrames={CLIP_FRAMES[3]} fps={FPS} width={W} height={H} />
    <Composition id="EndScreen" component={EndScreenPreview} durationInFrames={END_SCREEN_FRAMES} fps={FPS} width={W} height={H} />
    <Composition id="OrangeWipe" component={OrangeWipe} durationInFrames={WIPE_FRAMES} fps={FPS} width={W} height={H} />
  </>
);
