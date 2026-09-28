import React, {createContext, useContext} from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile} from 'remotion';
import {ClipId, clipVideo} from '../timeline';

/** QA only: when true, video layers render nothing so graphics can be checked on transparency. */
export const HideVideoContext = createContext(false);

/**
 * The presenter clip, full-bleed 1080x1920. Audio is muted here: the voice track is processed
 * and loudness-normalised separately with FFmpeg (work/audio_mix.py) and muxed after render.
 * `scale` (1 = 100 %) and `dx/dy` (px) drive punch-in zooms and camera shake.
 */
export const VideoLayer: React.FC<{clip: ClipId; scale?: number; dx?: number; dy?: number; originY?: number}> = ({
  clip,
  scale = 1,
  dx = 0,
  dy = 0,
  originY = 50,
}) => {
  const hideVideo = useContext(HideVideoContext);
  if (hideVideo) return null;
  return (
    <AbsoluteFill style={{overflow: 'hidden', backgroundColor: '#000'}}>
      <OffthreadVideo
        src={staticFile(clipVideo(clip))}
        muted
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `translate(${dx}px, ${dy}px) scale(${scale})`,
          transformOrigin: `50% ${originY}%`,
        }}
      />
    </AbsoluteFill>
  );
};
