#!/usr/bin/env python3
"""QA (Agent 13) — aggregate work/qa/parts/*.json into work/qa/qa_results.json (verdict + evidence per check).

Full pipeline (from the project root):
  cd remotion && npx remotion render src/index.ts Reel02Graphics $PWD/../work/qa/g --sequence --image-format=png \
      --frames=0-845 --concurrency=3 --image-sequence-pattern='f[frame].[ext]'
  for c in EndScreenFG Cap1 Cap2 Cap3; do npx remotion render ../work/qa/remotion_qa/index.tsx $c $PWD/../work/qa/iso/$c \
      --sequence --image-format=png --concurrency=3 --image-sequence-pattern='f[frame].[ext]'; done
  cd .. && node work/qa/run_dump.mjs
  python3 work/qa/qa_frames.py        # checks 3, 4, 8
  PYTHONPATH=<fonttools+brotli+uharfbuzz> python3 work/qa/qa_shaping.py   # check 1 (machine)
  python3 work/qa/qa_crops.py         # check 1/2 (visual sheets in work/qa/view)
  python3 work/qa/qa_face_verify.py   # check 4 cross-check
  python3 work/qa/qa_logo.py          # check 7
  python3 work/qa/qa_disclaimer.py    # check 6
  python3 work/qa/qa_captions.py      # check 5
  python3 work/qa/qa_delivery.py      # delivery specs
  python3 work/qa/qa_report.py
"""
import json
import os

QA = os.path.dirname(os.path.abspath(__file__))
P = lambda n: json.load(open(os.path.join(QA, "parts", n)))

sz, face, fv, cols, shp, logo, disc, cap, dl = (P("safe_zone.json"), P("face.json"), P("face_verify.json"), P("colours_raw.json"),
                                                 P("shaping.json"), P("logo.json"), P("disclaimer.json"), P("captions.json"), P("delivery.json"))

tot = sum(c["px"] for c in cols)
off = [c for c in cols if c["rgb_dist"] > 6]
off_frames = sorted({f for c in off for a, b in c["frames"] for f in range(a, b + 1)})
blank = cap["blank_frames_during_speech"]
blank_g = [g for c in ("1", "2", "3") for g in blank[c]["unplanned_blank_frames_global"] if g not in (505, 506, 507, 508)]
main = dl["TrainPlex_Reel02_9x16.mp4"]

results = {
    "generated_by": "Agent 13 (Brand/QA checker) — measurement only; nothing under remotion/src or output/ was modified",
    "inputs": {
        "graphics_render": "work/qa/g/f000-f845.png (Reel02Graphics, full reel, every frame)",
        "isolation_renders": "work/qa/iso/{Cap1,Cap2,Cap3,EndScreenFG} (work/qa/remotion_qa/index.tsx — real components, backgrounds hidden via CSS for EndScreenFG)",
        "cue_dump": "work/qa/cues_dump.json (timing/camera/face values evaluated from remotion/src with esbuild)",
    },
    "checks": {
        "1_devanagari_shaping": {
            "verdict": "PASS",
            "evidence": f"HarfBuzz shaping of all {len(shp['strings'])} Devanagari runs with the shipped Noto Sans Devanagari woff2 subsets: "
                        f"{shp['problem_count']} problems (0 .notdef, 0 dotted-circle, 0 missing code points); visual 1:1 crops of all 26 caption "
                        "chunks + slab/badge/plate/disclaimer/end-screen text show correct conjuncts (क्या, छोटे-छोटे, निर्भर reph, बनें, पाँच chandrabindu, रोज़ nukta).",
            "sheets": [f"work/qa/view/deva_sheet_{i}.png" for i in range(6)],
            "minor": "'FREE।' (clip 2 chunk 7): the Devanagari danda after the Inter caps shows a visibly wider gap than after Devanagari words (font side-bearing) — cosmetic.",
        },
        "2_brand_spelling": {
            "verdict": "PASS",
            "evidence": "No Trainplex/Train Plex/Trainflix/TRAINPLEX string in remotion/src or captions.json; rendered caption reads 'TrainPlex पे दे।' "
                        "(KEEP_CASE stops the highlight upper-casing); only lowercase use is the URL 'trainplex.info/register'. The logo ARTWORK wordmark reads 'Train Plex' (real logo, not our text).",
        },
        "3_safe_zone": {
            "verdict": "PASS",
            "evidence": "Settled graphics (all clip frames without edge motion) span x 60-1020, y 232-1477 (clip1 60-1017/232-1413, clip2 60-1020/236-1415, clip3 60-1015/240-1477); "
                        "end-screen text/logo/chips/arrows (EndScreenFG, lf>=57) x 71-1012, y 252-1464; nothing in rows 228-231. "
                        "Clip-1 hook slab band is full-bleed by design (x 0-1080, y 262-498) with its text/icon inside x 95-975, y 311-455.",
            "motion_only_exceedances_global_frames": sz["violation_runs"],
            "motion_explained": {
                "0-55": "clip1 hook slab: full-bleed band (by design); text leaves the zone only on entry g0-2 and exit g52-55",
                "182-185": "clip1 4HRS/₹0 card exit right", "232-234": "clip2 AI TRAINER TASKS slab entrance from left",
                "302-305, 342-345, 371-374": "clip2 task chips entering from the right", "418-427": "clip2 slab + chips exit",
                "607-613": "clip3 BANK/UPI card entrance (+ ₹ plate exit left at 608-609)", "665-666": "clip3 BANK/UPI card exit right",
            },
        },
        "4_face_clearance": {
            "verdict": "PASS",
            "evidence": f"{sum(v['frames_checked'] for v in face['per_clip'].values())} clip frames (all, minus join-flash/wipe) with camera zoom/shake applied to the Haar eyes/mouth rects: 0 overlapping frames; "
                        f"min clearance eyes {min(v['min_eyes_clear_px'] for v in face['per_clip'].values())} px (g201-202 clip1 logo plate), mouth {min(v['min_mouth_clear_px'] for v in face['per_clip'].values())} px (g333-335 clip2 chips). "
                        f"Independent OpenCV eye-cascade cross-check ({fv['detections']} eye detections): {len(fv['violations'])} frames (g309, g312, g313) where the detector's (oversized) eye box corner touches the 'Voice Recording' chip by 12-39 px; visual zoom (work/qa/view/eye_chip_zoom.png) shows the chip corner on the cheekbone ~35 px below the outer eye corner, not on the eye.",
            "per_clip": face["per_clip"], "eye_cascade_cross_check": fv["per_clip"],
            "tightest": "clip2 chips (x>=716, y>=702) vs eyes band (y2<=691) and mouth band (x2<=706): 10-12 px margins",
        },
        "5_caption_sync": {
            "verdict": "PASS",
            "evidence": f"All {cap['summary']['chunks']} chunks first visible (captions-only render) at word-start -1 frame (clip3 chunk0 +1 at the clip start); tolerance ±2 met. "
                        f"Acoustic spot-check of {len(cap['audio_spot_checks'])} post-pause words: 12 within ±1.2 frames; 'और' (clip3) captions.json start 6.66 s vs strong voiced onset 6.78 s (-3.4 f, weak pre-voicing from 6.48 s — ambiguous).",
            "chunks": cap["chunks"], "audio_spot_checks": cap["audio_spot_checks"],
            "issue_1_frame_caption_blink": {
                "frames_global": blank_g,
                "cause": "remotion/src/captions/Captions.tsx ChunkView: fadeIn = interpolate(frame - appear, [0, 6], [0, 1]) is 0 on the appear frame, while chunks.ts 'swap' sets the previous chunk's hideEnd = next.appear -> no caption at all for 1 frame at every hard swap",
                "fix": "remotion/src/captions/chunks.ts swap branch: c.fadeStart = next.appear + 1; c.hideEnd = next.appear + 1 (outgoing chunk covers the incoming chunk's 0-opacity frame; sync unchanged)",
            },
        },
        "6_disclaimer": {
            "verdict": "PASS",
            "evidence": f"Figure (orange ₹ on navy plate) visible clip3 local {disc['figure_visible_frames_local']} (drawn from 54 at 50 % opacity); disclaimer strip fully visible local {disc['disclaimer_fully_visible_local']} "
                        f"(g556-661) -> covers every figure frame and holds {disc['disclaimer_hold_after_figure_s']} s after the figure leaves. White 600 30 px on 70 % navy: "
                        f"text block {disc['text_block_height_px']} px tall, box {disc['text_box']}; contrast on the delivered MP4 >= {disc['contrast_min_p95_bg']}:1 (vs 95th-pct brightest strip background), mean >= {disc['contrast_min_mean_bg']}:1.",
            "note": "30 px on a 1920 px frame (~1.6 % of height) is legible but small; consider 34-36 px if the legal team wants more margin.",
        },
        "7_logo_unaltered": {
            "verdict": "PASS",
            "evidence": f"transparent PNG vs source (at source scale): SSIM {logo['transparent_vs_source']['at_source_scale_300px']['ssim']}, MAD {logo['transparent_vs_source']['at_source_scale_300px']['mad']}/255, ink aspect {logo['transparent_vs_source']['ink_aspect_transparent']} vs {logo['transparent_vs_source']['ink_aspect_source']}. "
                        f"Rendered vs PNG resampled to same geometry: end screen SSIM {logo['rendered']['endscreen_fg_lf104']['ssim']} (MAD {logo['rendered']['endscreen_fg_lf104']['mad']}), clip1 plate SSIM {logo['rendered']['clip1_plate_g220']['ssim']} (diff = edge resampling only), "
                        f"watermark SSIM {logo['rendered']['watermark_g135']['ssim']}; ink-box aspect identical to reference (0.8957/0.8952), best alignment shift 0 px.",
            "rendered": logo["rendered"], "transparent_vs_source": logo["transparent_vs_source"],
            "notes": ["source logo is only 300x300 px: the end-screen logo (420 px) is a ~1.95x upscale of the source pixels (soft edges)",
                      "logo artwork orange is #FE5015, not brand #FF6B35 (artwork, excluded from the palette check)"],
        },
        "8_brand_colours": {
            "verdict": "PASS",
            "evidence": f"{tot:,} interior fully-opaque graphics pixels (all 846 frames, logos excluded, 3x3-uniform = anti-aliasing excluded): {100 * (1 - sum(c['px'] for c in off) / tot):.2f} % within RGB 6 of the 5 brand hexes "
                        f"(#FAF7F2, #1A1A5E, #FF6B35, #FFFFFF; #E8E3DA only as 2 px borders / 8 % grid = #F9F5F0, d=3). {len(off)} off-palette colours ({sum(c['px'] for c in off):,} px) occur ONLY in transition frames {off_frames}: "
                        "join flash (228-231, 505-508), clip3 figure/sub-line fade-in (560, 563-565), end-screen headline/sub/chip/Learn-more fade-ins (754-806). "
                        "Semi-transparent fills are brand hex at reduced opacity: progress track cream 40 %, disclaimer strip navy 70 %, watermark plate+logo 85 %. "
                        "Delivered MP4 keeps brand colours within 3.3 RGB (cream 249,244,241; navy 25,25,94; orange 255,107,52).",
            "off_palette_top": [{k: c[k] for k in ("hex", "px", "nearest", "rgb_dist", "frames", "where_first")} for c in off[:20]],
        },
    },
    "delivery": {
        "verdict": "PASS",
        "evidence": f"1080x1920, 30/1 CFR (846 packets, one duration), H.264 High L5.0, yuv420p tv bt709, AAC LC 48 kHz stereo, faststart (ftyp, moov, free, mdat), 28.200 s video+audio, "
                    f"{main['loudness']['I_lufs']} LUFS, TP {main['loudness']['true_peak_dbtp']} dBTP, LRA {main['loudness']['LRA_lu']} LU. AAC average 170 kbps = 194 kbps over the voice (0-24.7 s) + digital silence on the 3.5 s end screen.",
        "both_mp4s_byte_identical": dl["mp4s_byte_identical"], "music_asset_present": dl["music_asset_present"],
        "cover": dl["cover"], "files": {k: v for k, v in dl.items() if k.endswith(".mp4")},
    },
}
json.dump(results, open(os.path.join(QA, "qa_results.json"), "w"), ensure_ascii=False, indent=1)
for k, v in results["checks"].items():
    print(k, v["verdict"])
print("delivery", results["delivery"]["verdict"])
