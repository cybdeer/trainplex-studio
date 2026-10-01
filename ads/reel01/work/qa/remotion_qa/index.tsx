// QA-only Remotion entry (Agent 13). Imports the REAL components from remotion/src unchanged and
// registers isolation compositions for measurement. Nothing in remotion/src is modified.
//   CapN        : only the kinetic captions of clip N (transparent background)
//   EndScreenFG : the end screen with its full-bleed backgrounds (cream fill, grid, wedge, stripe,
//                 CTA-bar fill) made transparent via CSS, leaving text / logo / chips / arrows only.
import React from 'react';
import {AbsoluteFill, Composition, registerRoot} from 'remotion';
import {Captions} from '../../../remotion/src/captions/Captions';
import {EndScreen} from '../../../remotion/src/endscreen/EndScreen';
import {loadBrandFonts} from '../../../remotion/src/fonts';
import {CLIP_FRAMES, END_SCREEN_FRAMES, FPS} from '../../../remotion/src/timeline';

loadBrandFonts();

const HIDE_BG = `
  div[style*="background-color: rgb(250, 247, 242)"] { background-color: transparent !important; }
  div[style*="background-color: rgb(26, 26, 94)"] { background-color: transparent !important; }
  svg[width="1080"] { display: none !important; }
`;

const EndScreenFG: React.FC = () => (
  <AbsoluteFill>
    <style>{HIDE_BG}</style>
    <EndScreen />
  </AbsoluteFill>
);

const Cap: React.FC<{clip: 1 | 2 | 3}> = ({clip}) => (
  <AbsoluteFill>
    <Captions clip={clip} />
  </AbsoluteFill>
);
const Cap1: React.FC = () => <Cap clip={1} />;
const Cap2: React.FC = () => <Cap clip={2} />;
const Cap3: React.FC = () => <Cap clip={3} />;

const Root: React.FC = () => (
  <>
    <Composition id="Cap1" component={Cap1} durationInFrames={CLIP_FRAMES[1]} fps={FPS} width={1080} height={1920} />
    <Composition id="Cap2" component={Cap2} durationInFrames={CLIP_FRAMES[2]} fps={FPS} width={1080} height={1920} />
    <Composition id="Cap3" component={Cap3} durationInFrames={CLIP_FRAMES[3]} fps={FPS} width={1080} height={1920} />
    <Composition id="EndScreenFG" component={EndScreenFG} durationInFrames={END_SCREEN_FRAMES} fps={FPS} width={1080} height={1920} />
  </>
);

registerRoot(Root);
