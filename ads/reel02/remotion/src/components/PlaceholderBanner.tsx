import React from 'react';
import {AbsoluteFill} from 'remotion';
import {COLORS, FONT_STACK} from '../brand';
import {IS_PLACEHOLDER_DATA} from '../timeline';

if (IS_PLACEHOLDER_DATA && typeof console !== 'undefined') {
  console.warn('[Reel02] src/data holds PLACEHOLDER captions/edit/face data — replace with the pipeline outputs before the final render.');
}

/**
 * Fail-safe: while src/data still holds the synthetic placeholder inputs, every render carries a
 * small "PLACEHOLDER DATA" strip below the safe zone (y 1850), so a placeholder render can never be
 * mistaken for a deliverable. Disappears automatically once real pipeline data is copied in.
 */
export const PlaceholderBanner: React.FC = () => {
  if (!IS_PLACEHOLDER_DATA) return null;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 1850,
          height: 44,
          backgroundColor: COLORS.navy,
          color: COLORS.white,
          fontFamily: FONT_STACK,
          fontWeight: 700,
          fontSize: 26,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          letterSpacing: '0.08em',
        }}
      >
        PLACEHOLDER DATA — NOT FOR DELIVERY
      </div>
    </AbsoluteFill>
  );
};
