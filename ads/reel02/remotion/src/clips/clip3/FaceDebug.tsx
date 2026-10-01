import React from 'react';
import {getInputProps, useCurrentFrame} from 'remotion';
import {ClipId, faceAt, Rect, WATERMARK_BOX} from '../../timeline';
import {faceOnScreen} from './cues';

/** QA only: render with --props='{"debugFace":true}' to see the face box and protected eyes/mouth rects. */
export const isFaceDebug = () => Boolean((getInputProps() as {debugFace?: boolean}).debugFace);

const Box: React.FC<{r: Rect; color: string; label: string}> = ({r, color, label}) => (
  <div
    style={{
      position: 'absolute',
      left: r.x1,
      top: r.y1,
      width: r.x2 - r.x1,
      height: r.y2 - r.y1,
      outline: `3px dashed ${color}`,
      color,
      fontSize: 22,
      fontFamily: 'monospace',
    }}
  >
    {label}
  </div>
);

export const FaceDebug: React.FC<{clip: ClipId}> = ({clip}) => {
  const frame = useCurrentFrame();
  const {face, eyes, mouth} = clip === 3 ? faceOnScreen(frame) : faceAt(clip, frame);
  return (
    <>
      <Box r={face} color="#ffff00" label="face" />
      <Box r={eyes} color="#ff00ff" label={`eyes y1=${Math.round(eyes.y1)}`} />
      <Box r={mouth} color="#00ffff" label="mouth" />
      <Box r={WATERMARK_BOX} color="#ffff00" label="wm" />
      <Box r={{x1: 60, y1: 232, x2: 1020, y2: 1480}} color="#00ff00" label="" />
      <div style={{position: 'absolute', left: 0, right: 0, top: 1400, height: 0, outline: '2px solid #ff0000'}} />
      <div style={{position: 'absolute', left: 70, top: 1850, color: '#fff', fontSize: 40, fontFamily: 'monospace'}}>f{frame}</div>
    </>
  );
};
