import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {CANVAS, SAFE} from '../brand';
import {VideoLayer} from '../components/VideoLayer';
import {FrameInterval} from '../timeline';
import {WATERMARK_BLOCKED, ZOOM_ORIGIN_Y, zoomAt} from './clip3/cues';
import {Disclaimer} from './clip3/Disclaimer';
import {EarningPlate} from './clip3/EarningPlate';
import {FaceDebug, isFaceDebug} from './clip3/FaceDebug';
import {LearnMore} from './clip3/LearnMore';
import {PayoutCard} from './clip3/PayoutCard';

/** Local-frame intervals when this clip's graphics overlap WATERMARK_BOX (watermark ducks out). */
export const CLIP3_WATERMARK_BLOCKED: FrameInterval[] = WATERMARK_BLOCKED;

/**
 * Clip 3 — EARNING + CTA. Presenter video with a punch-in (100 % → 108 %, origin on the chin line)
 * when the earning figure lands, the "₹400–500 / 2–3 घंटे*" plate, the mandatory disclaimer (held to
 * the clip end), the Bank / UPI card and the "Learn more" down-arrow. Captions are rendered separately, above these graphics.
 * All cues come from captions.json (see clip3/cues.ts); frames are local to the clip.
 */
export const Clip3: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <VideoLayer clip={3} scale={zoomAt(frame)} originY={(ZOOM_ORIGIN_Y / CANVAS.height) * 100} />
      {/* Safe-zone clip (QA check 5): entrance/exit slides never draw outside x 60-1020, y 220-1480. */}
      <AbsoluteFill style={{pointerEvents: 'none', clipPath: `inset(${SAFE.y1}px ${1080 - SAFE.x2}px ${1920 - SAFE.y2}px ${SAFE.x1}px)`}}>
        <EarningPlate />
        <PayoutCard />
        <Disclaimer />
        <LearnMore />
        {isFaceDebug() ? <FaceDebug clip={3} /> : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
