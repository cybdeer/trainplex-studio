import React, {useEffect, useMemo, useState} from 'react';
import {
  AbsoluteFill,
  cancelRender,
  continueRender,
  delayRender,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {COLORS, FONT_STACK, SPRING, SPRING_FIRM} from '../brand';
import {CLIP_FRAMES, ClipId, findPhrase, TimedWord, wordsOf} from '../timeline';
import {
  buildChunks,
  ChunkTiming,
  displayText,
  ENTER_FRAMES,
  ENTER_SLIDE_PX,
} from './chunks';
import {FitResult, fitChunk, FONT_WEIGHT, GAP_EM, measureWord, OUTLINE_PX, wordPx} from './fit';

// ─── Layout contract (see AGENT_BRIEF "Captions contract") ─────────────────────────────────────
/** Caption block bottom edge (block grows upward). */
export const CAPTION_BOTTOM_Y = 1400;
/** Clip 3, from the 2nd "तो" ("तो नीचे") to clip end: raised so the LEARN MORE block fits below. */
export const CAPTION_BOTTOM_Y_RAISED = 1290;
const RAISE_MOVE_FRAMES = 6;
const LINE_HEIGHT = 1.12;
/** Active-word pop: 1.0 -> 1.12 -> 1.0. */
const POP = 0.12;
const POP_UP_FRAMES = 3;
const POP_DOWN_FRAMES = 8;

// ─── Fonts must be loaded before measuring (fonts.ts registers them at startup) ───────────────
const fontsLoaded = () =>
  typeof document !== 'undefined' &&
  document.fonts.check(`${FONT_WEIGHT} 92px "Inter"`, 'Aa') &&
  document.fonts.check(`${FONT_WEIGHT} 92px "Noto Sans Devanagari"`, 'कर');

const useFontsReady = () => {
  const [ready, setReady] = useState(fontsLoaded);
  const [handle] = useState(() => (ready ? null : delayRender('Captions: waiting for brand fonts')));
  useEffect(() => {
    if (handle === null) return;
    let alive = true;
    Promise.all([
      document.fonts.load(`${FONT_WEIGHT} 92px "Inter"`, 'Aa'),
      document.fonts.load(`${FONT_WEIGHT} 92px "Noto Sans Devanagari"`, 'कर'),
    ])
      .then(() => document.fonts.ready)
      .then(() => {
        if (alive) setReady(true);
        continueRender(handle);
      })
      .catch((err) => cancelRender(err));
    return () => {
      alive = false;
    };
  }, [handle]);
  return ready;
};

// ─── One word: navy outline layer underneath + fill layer exactly on top ──────────────────────
// A 10 px centred -webkit-text-stroke on the under-layer puts 5 px of navy outside every glyph
// contour; the fill layer on top covers the inner half. Because the fill covers the union of all
// glyph parts, overlapping Devanagari components (conjuncts, matras, nukta) show no internal seams.
const Word: React.FC<{text: string; px: number; color: string; scale: number; z: number}> = ({
  text,
  px,
  color,
  scale,
  z,
}) => {
  // While popping, neighbours are pushed apart by the extra width so words never collide.
  const push = ((scale - 1) * measureWord(text, px)) / 2;
  const base: React.CSSProperties = {
    display: 'block',
    fontFamily: FONT_STACK,
    fontWeight: FONT_WEIGHT,
    fontSize: px,
    lineHeight: LINE_HEIGHT,
    whiteSpace: 'pre',
    fontKerning: 'normal',
  };
  return (
    <span
      style={{
        position: 'relative',
        display: 'inline-block',
        transform: scale === 1 ? undefined : `scale(${scale})`,
        transformOrigin: '50% 58%',
        marginLeft: push,
        marginRight: push,
        zIndex: z,
      }}
    >
      <span
        aria-hidden
        style={{
          ...base,
          color: COLORS.navy,
          WebkitTextStroke: `${OUTLINE_PX * 2}px ${COLORS.navy}`,
        }}
      >
        {text}
      </span>
      <span style={{...base, position: 'absolute', left: 0, top: 0, color}}>{text}</span>
    </span>
  );
};

const popScale = (frame: number, start: number, fps: number) => {
  const t = frame - start;
  if (t < 0) return 1;
  const up = spring({
    frame: t,
    fps,
    config: {...SPRING_FIRM, overshootClamping: true},
    durationInFrames: POP_UP_FRAMES,
  });
  const down = spring({frame: t - POP_UP_FRAMES, fps, config: SPRING, durationInFrames: POP_DOWN_FRAMES});
  return 1 + POP * (up - down);
};

type Prepared = ChunkTiming & {fit: FitResult; texts: string[]};

const ChunkView: React.FC<{chunk: Prepared; frame: number; fps: number; bottomY: number}> = ({
  chunk,
  frame,
  fps,
  bottomY,
}) => {
  const local = frame - chunk.appear;
  const enter = spring({frame: local, fps, config: SPRING_FIRM, durationInFrames: ENTER_FRAMES});
  const fadeIn = interpolate(local, [0, ENTER_FRAMES], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });
  const fadeOut =
    chunk.exit === 'fade'
      ? interpolate(frame, [chunk.fadeStart, chunk.hideEnd], [1, 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : 1;
  const ty = ENTER_SLIDE_PX * (1 - enter);
  const {fontSize, lines} = chunk.fit;

  // The word being spoken sits on top so its pop overlaps neighbours cleanly.
  const activeIdx = (() => {
    let a = -1;
    chunk.words.forEach((w, i) => {
      if (frame >= w.startFrame) a = i;
    });
    return a;
  })();

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        width: 1080,
        bottom: 1920 - bottomY,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        transform: `translateY(${ty}px)`,
        opacity: fadeIn * fadeOut,
      }}
    >
      {lines.map((line, li) => (
        <div
          key={li}
          style={{
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'baseline',
            justifyContent: 'center',
            columnGap: GAP_EM * fontSize,
            whiteSpace: 'nowrap',
          }}
        >
          {line.map((i) => {
            const w: TimedWord = chunk.words[i];
            return (
              <Word
                key={i}
                text={chunk.texts[i]}
                px={wordPx(fontSize, w.highlight)}
                color={w.highlight ? COLORS.orange : COLORS.white}
                scale={popScale(frame, w.startFrame, fps)}
                z={i === activeIdx ? 2 : 1}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
};

/** Kinetic word-by-word captions for one clip (frames local to the clip). */
export const Captions: React.FC<{clip: ClipId}> = ({clip}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const ready = useFontsReady();

  const timings = useMemo(() => buildChunks(wordsOf(clip), CLIP_FRAMES[clip]), [clip]);
  const prepared = useMemo<Prepared[] | null>(() => {
    if (!ready) return null;
    return timings.map((c) => {
      const texts = c.words.map(displayText);
      const fit = fitChunk(c.words.map((w, i) => ({text: texts[i], highlight: w.highlight})));
      return {...c, texts, fit};
    });
  }, [ready, timings]);

  // Clip 3: raise the block from the 2nd "तो" to the clip end. A chunk that starts at/after that
  // word simply enters at the raised position; one spanning the boundary springs up over 6 frames.
  const raiseFrame = useMemo(() => (clip === 3 ? findPhrase(3, 'तो नीचे').startFrame : null), [clip]);

  if (!prepared) return null;

  const visible = prepared.filter((c) => frame >= c.appear && frame < c.hideEnd);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {visible.map((c) => {
        let bottomY = CAPTION_BOTTOM_Y;
        if (raiseFrame !== null) {
          if (c.firstStart >= raiseFrame) {
            bottomY = CAPTION_BOTTOM_Y_RAISED;
          } else {
            const m = spring({
              frame: frame - raiseFrame,
              fps,
              config: SPRING_FIRM,
              durationInFrames: RAISE_MOVE_FRAMES,
            });
            bottomY = interpolate(m, [0, 1], [CAPTION_BOTTOM_Y, CAPTION_BOTTOM_Y_RAISED]);
          }
        }
        return <ChunkView key={c.index} chunk={c} frame={frame} fps={fps} bottomY={bottomY} />;
      })}
    </AbsoluteFill>
  );
};
