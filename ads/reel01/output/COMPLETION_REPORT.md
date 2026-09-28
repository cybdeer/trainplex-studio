# TrainPlex Reel 01: Completion Report

**प्रोजेक्ट:** TrainPlex Instagram Reels Ad (motion-graphics edit और animated logo CTA end screen)
**तारीख:** 2026-09-28
**Branch / PR:** `claude/trainplex-reels-motion-graphics-mj4wj0` → [cybdeer/trainplex-studio#1](https://github.com/cybdeer/trainplex-studio/pull/1) (draft)

> **सार:** तीनों clips का motion-graphics edit, kinetic Hindi/English captions, animated CTA end screen और mastered audio तैयार है। Final video **28.2 s** का है, 1080x1920 @ 30 fps, H.264 High, yuv420p, AAC 48 kHz। Loudness **−14.0 LUFS** है और true peak **−1.5 dBTP**। Brand/QA agent की सभी 8 जाँचें **PASS** हुईं। Music और SFX files नहीं मिलीं, इसलिए दोनों MP4 अभी voice-only हैं।

---

## 1. Output files

| File | Path | विवरण |
|---|---|---|
| मुख्य video | `ads/reel01/output/TrainPlex_Reel01_9x16.mp4` | 1080x1920, 30 fps, 846 frames, 28.2 s, 18.2 MB |
| Voice-only video | `ads/reel01/output/TrainPlex_Reel01_9x16_nomusic.mp4` | Music न होने से ऊपर वाली file के byte-for-byte बराबर |
| Cover | `ads/reel01/output/TrainPlex_Reel01_cover.jpg` | 1080x1920, clip 1 frame 40 ("SCROLL बंद कर!" slab और "करना बंद कर!" caption) |
| QA frame grabs | `ads/reel01/output/qa/` | `qa_00_50s`, `qa_02_00s`, `qa_04_50s`, `qa_12_00s`, `qa_15_00s`, `qa_22_00s`, `qa_26_00s`, `qa_endscreen_f012/f060/f104` (.png) |
| यह report | `ads/reel01/output/COMPLETION_REPORT.md` | |
| Remotion project | `ads/reel01/remotion/` | TypeScript, entry `src/index.ts`, compositions `Reel01`, `Reel01Graphics`, `Clip1–3`, `EndScreen`, `OrangeWipe` |
| Pipeline scripts | `ads/reel01/work/` | `normalise.py`, `transcribe.py`, `align_captions.py`, `make_logo_alpha.py`, `face_track.py`, `audio_mix.py`, `mux.py`, `render.py` |
| Data / reports | `ads/reel01/work/` | `captions.json`, `edit.json`, `face_boxes.json`, `transcripts/clip*_raw.json`, `audio/audio_report.json`, `render_report.json`, `qa/qa_results.json`, `qa/QA_NOTES.md` |

**दोबारा बनाने का तरीका** (Linux; Windows पर यही commands PowerShell में चलेंगी):

```bash
cd ads/reel01
python3 work/normalise.py            # trim + 1080x1920 @ 30 fps
python3 work/transcribe.py           # faster-whisper large-v3 (timing)
python3 work/align_captions.py       # exact script → work/captions.json
cp work/captions.json remotion/src/data/captions.json
cp work/norm/clip*.mp4 remotion/public/clips/
python3 work/audio_mix.py            # voice/music masters (−14 LUFS)
cd remotion && npm ci && cd ..
python3 work/render.py               # render + mux + cover + QA grabs
```

---

## 2. Tool versions

| Tool | Version |
|---|---|
| Node.js / npm | v22.22.2 / 10.9.7 |
| FFmpeg / ffprobe | 6.1.1 (Ubuntu build) |
| Python | 3.11.15 |
| faster-whisper / ctranslate2 | 1.2.1 / 4.8.2 (model: `Systran/faster-whisper-large-v3`, CPU int8) |
| Remotion / @remotion/renderer | 4.0.529 |
| React / TypeScript | 19.1.0 / 5.8.3 |
| lucide-react | 1.48.0 |
| @fontsource/inter / @fontsource/noto-sans-devanagari | 5.3.0 / 5.3.0 |
| Chromium headless shell | 141.0.7390.37 |
| OpenCV / Pillow / numpy / scipy | 4.12.0 / 12.3.0 / 2.4.6 / 1.17.1 |

---

## 3. Durations और loudness

| Clip | Source | Trim (in → out) | Final duration | Frames |
|---|---|---|---|---|
| Clip 1: Hook | 8.000 s, 720x1280 @ 24 fps | 0.000 → 7.633 s | **7.633 s** | 229 |
| Clip 2: Tasks | 10.005 s, 720x1280 @ 24 fps | 0.200 → 9.433 s | **9.233 s** | 277 |
| Clip 3: Earning + CTA | 8.000 s, 720x1280 @ 24 fps | 0.000 → 7.833 s | **7.833 s** | 235 |
| End screen | — | — | **3.500 s** | 105 |
| **कुल** | | | **28.200 s** | **846** |

- **Join gaps:** clip 1→2 में आवाज़ के बीच ≈ 0.14 s और clip 2→3 में ≈ 0.16 s का अंतर है, दोनों ≤ 0.25 s की शर्त के अंदर।
- **Final loudness (दोनों MP4, AAC के बाद):** Integrated **−14.0 LUFS**, True Peak **−1.5 dBTP**, LRA 3.4 LU।
- **Per-clip loudness (processing से पहले):** clip 1: −14.35, clip 2: −16.45, clip 3: −18.06 LUFS। तीनों को −16.00 LUFS पर बराबर किया गया।

---

## 4. Requirements checklist

### Execution mode

| Requirement | Status | Note |
|---|---|---|
| MAX AGENT SWARM, 15 agents | **PARTIAL** | 15 roles तय किए गए (नीचे §6)। जो काम एक साथ हो सकते थे, उनके लिए 7 subagents parallel चलाए गए: captions, clip 1, clip 2, clip 3, end screen, audio, QA। Setup → probe → transcribe → align → render जैसे क्रम वाले कदम orchestrator ने खुद किए, क्योंकि वे एक-दूसरे पर निर्भर थे। |
| `/fewer-permission-prompts` शुरू में चलाना | **NOT DONE** | यह session cloud container में auto-permission mode में चला, इसलिए permission prompts का सवाल नहीं था। |
| Windows PowerShell / winget | **DEVIATION** | काम Linux cloud container में हुआ। Installs `apt` (FFmpeg), `pip` और `npm` से हुए। Project root `C:\TrainPlex\ads\reel01\` की जगह repo में `ads/reel01/` है, folder structure वही है। |

### Inputs

| Requirement | Status | Note |
|---|---|---|
| clip1/2/3.mp4 | **DONE** | Upload हुई तीन files को content और transcription से पहचानकर `clips/clip1..3.mp4` में रखा: hand-stop gesture और "scroll बंद कर" वाली clip = clip 1; tasks वाली = clip 2; earning/CTA वाली = clip 3। |
| Logo: transparent बनाना, redraw/recolour नहीं | **DONE** | Source 300x300 white-background PNG था। `work/make_logo_alpha.py` ने सिर्फ़ बाहर का सफ़ेद background और letters के अंदर के छोटे खाली हिस्से transparent किए। Anti-aliased edge alpha white के against निकाला, logo के रंग नहीं बदले, icon का सफ़ेद भीतरी हिस्सा वैसा ही रखा। SSIM (source से मिलान) 0.998। |
| Optional `assets/music.mp3` | **NOT DONE (absent)** | File नहीं मिली, इसलिए music के बिना render किया। Pipeline में ducking code तैयार है। |
| Optional `assets/sfx/` | **NOT DONE (absent)** | Files नहीं मिलीं, इसलिए SFX skip किए। Cue list तैयार है। |
| Optional `assets/broll/portal_tasks.mp4` | **NOT DONE (absent)** | File नहीं मिली, इसलिए PiP skip किया। |

### Output

| Requirement | Status | Note |
|---|---|---|
| `TrainPlex_Reel01_9x16.mp4` spec | **DONE** | 1080x1920, 30 fps CFR, H.264 High (L5.0), yuv420p BT.709, AAC-LC 48 kHz, `+faststart`, −14.0 LUFS, TP −1.5 dBTP। Audio bitrate 192k set है, पर file का average 170 kbps आता है क्योंकि end screen के 3.5 s silent हैं। Voice वाले हिस्से पर यह ≈ 194 kbps है। |
| `_nomusic.mp4` | **DONE** | Music न होने से दोनों files एक जैसी हैं। |
| `cover.jpg` | **DONE** | "SCROLL बंद कर!" वाला moment (frame 40)। |
| `qa/` frame grabs | **DONE** | 7 time points और end screen के 3 frames। |
| `COMPLETION_REPORT.md` | **DONE** | यही file। |

### Brand system और safe zones

| Requirement | Status | Note |
|---|---|---|
| सिर्फ़ brand colours | **DONE** | QA: 99.88% solid graphics pixels brand hex से 6 RGB के अंदर हैं। Off-palette pixels सिर्फ़ transition frames (flash/fade) में मिले। Emoji (✋ 📱 🎙) की जगह brand-colour lucide icons लगाए, क्योंकि emoji अपने अलग रंगों में render होते हैं। |
| Fonts: Inter + Noto Sans Devanagari (600/800/900, और 700) | **DONE** | `fonts/` और `remotion/public/fonts/` में self-hosted हैं। `unicode-range` से Latin Inter में और Devanagari Noto में render होता है। |
| Flat, sharp 90° corners, कोई gradient/shadow नहीं | **DONE** | हर जगह `borderRadius: 0`। |
| Snappy springs (damping 12–14, stiffness 180–220), 6–10 frame entrances | **DONE (2 exceptions)** | Video punch-in (clip 3) में damping 27 और BANK card slide में damping 24 रखा। Brand springs से zoom डगमगाकर 100% से नीचे चला जाता और किनारों पर काली पट्टी दिखती, और card watermark से टकराता। |
| Safe zone x 60–1020, y 220–1480 | **DONE** | Settled graphics x 60–1020, y 232–1477 में हैं। Entrance/exit के बीच कुछ frames ज़ोन से बाहर जाते हैं। Clip 1 का slab design से full-width है, उसका text x 95–975 में है। |
| Caption baseline zone y 1180–1420 | **DONE** | Caption block का bottom y 1400 पर है। Clip 3 के "तो नीचे…" हिस्से में LEARN MORE block के लिए bottom y 1290 पर है। |

### Step 1: Setup

| Requirement | Status | Note |
|---|---|---|
| Node, FFmpeg, Python 3.11, faster-whisper, Remotion | **DONE** | Versions §2 में हैं। Remotion project `remotion/` में manually scaffold किया। |

### Step 2: Probe, trim, normalise

| Requirement | Status | Note |
|---|---|---|
| ffprobe | **DONE** | तीनों clips 720x1280, 24 fps, AAC 48 kHz stereo हैं। |
| 1080x1920 @ 30 fps CFR | **DONE** | Lanczos upscale, `work/norm/`। |
| Silence trim (−40 dB, > 0.15 s, speech न कटे) | **DONE** | 10 ms RMS analysis किया। Clip 2 की शुरुआत की 0.27 s silence में से 0.20 s हटाई। तीनों clips के आखिर की silence हटाई। Clip 3 के आखिर में 7.92 s पर एक कटा हुआ syllable/click था, वह भी हटा दिया। |
| Join gap ≤ 0.25 s | **DONE** | ≈ 0.14 s और ≈ 0.16 s। |
| Watermark report (face crop नहीं) | **DONE (flagged)** | §7 में देखें। Crop नहीं किया। |
| Hard cuts, 4-frame white flash, whoosh | **PARTIAL** | Hard cuts और 4-frame flash (frames 228–231, 505–508) लगे हैं। Whoosh file नहीं थी, इसलिए skip। |

### Step 3: Transcription और alignment

| Requirement | Status | Note |
|---|---|---|
| faster-whisper large-v3, `hi`, word timestamps | **DONE** | Raw JSON `work/transcripts/clip*_raw.json` में है। |
| Exact script words, whisper सिर्फ़ timing के लिए | **DONE** | Whisper ने "स्क्रोल", "ट्रेन प्लेक्स", "500", "600", "जीरो" जैसे शब्द सुने थे। Captions में इनकी जगह exact script के शब्द हैं (scroll, TrainPlex, पाँच सौ, छह सौ, Zero!)। Script से 100% मिलान का assert लगाया है। |
| `work/captions.json` [{word,start,end,clip,highlight}] | **DONE** | साथ में `chunk` field जोड़ी है। |
| Timing न मिले तो interpolation | **DONE** | Code में fallback है, लेकिन इस बार कोई word बिना timing नहीं था। Pause निगलने वाले word starts को energy onset से ठीक किया। |

### Step 4: Kinetic captions

| Requirement | Status | Note |
|---|---|---|
| 2–4 words के chunks, punctuation पर break | **DONE (2 exceptions)** | "Zero!" जानबूझकर 1-word punch chunk है। Clip 3 के आखिरी हिस्से को "और अभी" \| "register कर!" में बाँटा ताकि caption एक line में रहे और मुँह से दूर रहे। |
| Style: 900 weight, 78–92 px, white, 5 px navy stroke, max 2 lines, 900 px | **DONE** | हर chunk का font size 78–92 px के बीच auto-fit होता है। सभी chunks एक line में आते हैं। Stroke glyph के बाहर लगता है, जिससे Devanagari में seams नहीं दिखते। |
| Active word pop 1.0 → 1.12 → 1.0 | **DONE** | Pop के समय बगल के words थोड़ा खिसकते हैं ताकि टकराव न हो। |
| Highlight words: orange, 1.15x, Latin uppercase | **DONE (1 exception)** | "TrainPlex" uppercase नहीं किया, क्योंकि brand spelling का नियम ऊपर है। |
| Entrance (24 px slide + 6-frame fade), 4-frame exit | **DONE** | Fade-in 1 frame पहले शुरू होता है, ताकि chunk बदलते समय कोई blank frame न रहे (QA fix)। |

### Step 5: Clip 1 (Hook)

| Requirement | Status | Note |
|---|---|---|
| Navy slab, −4°, "✋ SCROLL बंद कर!" 96 px, camera shake | **DONE** | ✋ की जगह lucide Hand icon है। Shake ±6 px, 8 frames का है। Slab "बंद कर!" खत्म होने (frame 49) के बाद दाईं ओर निकल जाता है। |
| "4 HRS" card (x 760–1000, y 300–540) | **DONE** | Frame 69 पर "चार घंटे" के साथ आता है। |
| "Zero!" पर ₹500 → ₹0 counter और 115% punch-in | **DONE** | Count 10 frames का है, zoom 4 frames में चढ़ता है, 8 frames रुकता है, फिर वापस आता है। |
| "TrainPlex" पर logo, cream plate, orange bar | **PARTIAL** | Logo width 360 की जगह **265 px** है। असली logo stacked lockup है (height ≈ 1.1 × width), इसलिए 360 px पर plate आँखें ढक देती। |

### Step 5: Clip 2 (Tasks)

| Requirement | Status | Note |
|---|---|---|
| "AI TRAINER TASKS" navy slab, −4° | **DONE** | Frame 43 पर "tasks" के साथ orange underline और एक छोटा punch जोड़ा। |
| Task chips (Voice Recording / Photo Collection / Text Annotation) | **PARTIAL** | Chips **x 716–1020, y 702–996** पर हैं, spec में x 620–1000 और y 460 से शुरू था। Spec वाली जगह दाईं आँख ढकती। Chips 304 px चौड़े हैं, इसलिए labels दो lines में हैं। |
| Broll PiP | **NOT DONE (absent)** | File नहीं थी। |
| Badges "PHONE से", "₹0 FEES", "FREE TRAINING" | **PARTIAL** | Badges **निचले हिस्से (y 964–1178)** में हैं, spec में y 380–700 था। वह हिस्सा ठीक आँखों पर पड़ता। 📱 की जगह lucide Smartphone icon है। "FREE TRAINING" "training" शब्द पर आता है, ताकि cut से पहले करीब 1 s दिखे। |

### Step 5: Clip 3 (Earning + CTA)

| Requirement | Status | Note |
|---|---|---|
| Navy plate, ₹0 → ₹500–600 count-up, "4 घंटे में तक*", 112% punch-in | **PARTIAL** | Plate **y 289–549** पर है (spec y 360–620), क्योंकि frames 68–70 पर आँखों का ऊपरी किनारा y 619 तक आता है। Zoom eye-line पर anchored है। |
| Disclaimer (figure + 1 s तक) | **DONE** | Local frames 50–155 तक पूरा दिखता है। Figure frames 54–103 में है, यानी disclaimer figure के बाद 1.73 s और रहता है। 30 px, weight 600, contrast ≥ 8.9:1। |
| BANK / UPI white card, orange tick | **DONE** | x 300–968, y 313–513। |
| LEARN MORE, bouncing arrow (3 bounces), y < 1480 | **DONE** | Label y 1310–1388, arrow का निचला सिरा ≤ 1478। |
| 8-frame orange wipe (left → right) | **DONE** | Cut के दोनों ओर 4+4 frames (737–744): पहले 4 frames clip को ढकते हैं, अगले 4 end screen खोलते हैं। |

### Global overlays

| Requirement | Status | Note |
|---|---|---|
| Progress bar (y 220, 8 px, cream 40% track, orange fill) | **DONE** | End screen से पहले तक 100% भर जाता है। |
| Logo watermark (x 60, y 240, 200 px, 85%) | **DONE (deviations)** | ① Cream plate जोड़ा, क्योंकि navy wordmark गहरे बालों पर पढ़ने में नहीं आता था। ② Slab, earning plate या clip 1 का hero logo स्क्रीन पर हो, तो watermark 4 frames में fade होकर छिप जाता है। इसलिए यह पहली बार 1.0 s की जगह ≈ 1.87 s (frame 56) पर दिखता है। Face पर कभी नहीं आता। |

### Step 6: End screen

| Requirement | Status | Note |
|---|---|---|
| Cream background, 8% grid, navy wedge 18° (~30%), 12 px orange bar | **DONE** | Wedge frame का 29.7% ढकता है। 8% grid spec के अनुसार है, पर लगभग दिखाई नहीं देता। |
| Logo 0.85 → 1.0 spring, 220x10 underline | **PARTIAL** | Logo **420 px** का है और top y 240 पर है, spec में 620 px और center y 560 था। 620 px पर stacked logo 688 px ऊँचा होता और headline से टकराता। |
| Headline "AI TRAINER बनें" (AI orange) | **DONE** | f12 से। |
| Sub line "घर बैठे · Phone से · Paid tasks" | **DONE** | f24 से। |
| 3 chips, −4° | **DONE** | एक row में 1430 px बनते, इसलिए 2+1 rows में हैं। f36, f42, f48 पर pop करते हैं। |
| Navy CTA bar "Register free → trainplex.info/register" 58 px | **PARTIAL** | Text **53 px** का है, क्योंकि 58 px पर line 1086 px चौड़ी होती और pulse पर safe zone से बाहर जाती। "→" की जगह lucide ArrowRight icon है, क्योंकि loaded Inter subset में U+2192 नहीं है। Bar f50–57 में आता है, फिर हर 20 frames पर pulse होता है। |
| Bouncing arrow + "Learn more" 36 px | **DONE (colour deviation)** | Label navy की जगह cream रंग का है, क्योंकि वह navy wedge के ऊपर पड़ता है। |
| Ding SFX | **NOT DONE (absent)** | CTA landing का frame (`CTA_LAND_FRAME = 57`) export कर रखा है। |
| कोई invented tagline, फ़ोन नंबर या earning figure नहीं | **DONE** | |

### Step 7: Audio

| Requirement | Status | Note |
|---|---|---|
| हर clip की loudness बराबर, 80 Hz HPF | **DONE** | तीनों −16 LUFS पर, Butterworth 12 dB/oct। |
| De-ess, सिर्फ़ तीखी sibilance पर | **DONE** | तीन मापों से फैसला किया। Clip 3 में 3/3 flags आए, इसलिए उस पर हल्का de-ess (max 4 dB, 5 kHz से ऊपर) लगाया। Clips 1 और 2 में 0/3 flags थे, वे बिना बदलाव के हैं। |
| Music bed और ducking | **NOT DONE (absent)** | Code तैयार है (−20 / −26 / −14 dB, 150/300 ms, 0.5 s fade)। |
| SFX | **NOT DONE (absent)** | |
| −14 LUFS, TP ≤ −1 dBTP | **DONE** | −14.0 LUFS / −1.5 dBTP (AAC के बाद)। Linear loudnorm संभव नहीं था (clip 2 के peaks), इसलिए static gain के बाद 4x-oversampled true-peak limiter लगाया। |

### Step 8: Render और QA

| Check | Status | Evidence (Agent 13) |
|---|---|---|
| Render: Remotion, CRF 18, H.264 | **DONE** | PNG frames और BT.709। FFmpeg से mux किया। Render ≈ 2.5 min। |
| 1. Devanagari shaping | **PASS** | सभी 59 Devanagari runs की HarfBuzz जाँच में कोई dotted-circle या tofu नहीं मिला। 26 caption chunks के 1:1 crops भी देखे। |
| 2. "TrainPlex" spelling | **PASS** | Code और captions में कोई गलत variant नहीं मिला। |
| 3. Safe zone | **PASS** | Settled graphics x 60–1020, y 232–1477 में हैं। |
| 4. आँख/मुँह न ढकें | **PASS** | 729 frames की जाँच zoom/shake के साथ की। आँखों से सबसे कम दूरी 11 px और मुँह से 10 px रही। |
| 5. Caption sync ±2 frames | **PASS** | सभी 26 chunks पहले word से ≤ 1 frame आगे दिखते हैं। |
| 6. Disclaimer | **PASS** | Figure के हर frame पर मौजूद है और उसके बाद 1.73 s और रहता है। |
| 7. Logo unaltered | **PASS** | SSIM: end screen 0.998, watermark 0.994, clip 1 plate 0.965 (अंतर सिर्फ़ resample का)। |
| 8. Brand colours | **PASS** | 99.88% pixels palette में हैं। |
| Duration 30–34 s | **PARTIAL** | **28.2 s।** Source clips 8/10/8 s के थे, हर एक ~10 s का नहीं। Speech धीमी किए या खाली padding डाले बिना लंबाई नहीं बढ़ सकती। |

**QA के बाद सुधार:**
1. Chunk बदलते समय 21 जगह caption 1 frame के लिए गायब होता था। Fade-in को 1 frame पहले शुरू करके यह ठीक किया।
2. Clip 1 में logo plate आने पर 3 frames तक watermark भी साथ दिखता था। अब watermark plate के साथ ही हट जाता है।

---

## 5. Spec से बदलाव (deviations) और कारण

1. **Environment:** काम Windows/PowerShell की जगह Linux cloud container में हुआ, paths `ads/reel01/` में हैं।
2. **Logo का आकार:** असली logo stacked lockup है, horizontal नहीं। इसलिए clip 1 में 265 px (spec 360) और end screen में 420 px (spec 620) रखा, ताकि आँखें न ढकें और headline से टकराव न हो।
3. **Face rule के कारण जगह बदली:** clip 2 के chips और badges, और clip 3 का plate और card अपनी spec वाली जगह से खिसकाए गए। §4 में पूरी geometry दी है।
4. **Emoji की जगह brand-colour lucide icons:** ✋ → Hand, 📱 → Smartphone, 🎙 → Mic। Emoji अपने गैर-brand रंगों में render होते हैं।
5. **CTA text 53 px (spec 58 px):** 58 px पर line safe zone में फिट नहीं होती। "→" की जगह icon है।
6. **End screen का "Learn more" cream रंग में है**, क्योंकि navy wedge पर navy text पढ़ा नहीं जाता।
7. **Watermark:** cream plate जोड़ा, और slab/plate/hero logo के साथ auto-hide होता है।
8. **"TrainPlex" highlight uppercase नहीं किया** (brand spelling का नियम)।
9. **Caption chunks:** "Zero!" 1 word का है, और "और अभी | register कर!" दो chunks में बँटा है।
10. **कुल लंबाई 28.2 s है (target 30–34 s):** source clips छोटे थे।
11. **Wipe cut के दोनों ओर 4+4 frames का है**, ताकि end screen साफ़ reveal हो।
12. **कुछ springs में damping ज़्यादा (24, 27):** zoom डगमगाने से किनारों पर काली पट्टी दिखती और card watermark से टकराता।

---

## 6. Agent swarm (15 roles)

| # | Role | किसने किया |
|---|---|---|
| 1 | Orchestrator / integration | Orchestrator |
| 2 | Environment setup | Orchestrator (FFmpeg, faster-whisper, Remotion, fonts) |
| 3 | Probe + trim/normalise | Orchestrator (`normalise.py`) |
| 4 | Transcription | Orchestrator (`transcribe.py`) |
| 5 | Caption alignment | Orchestrator (`align_captions.py`) |
| 6 | Remotion scaffold + timeline | Orchestrator (`timeline.ts`, `Reel.tsx`, `Root.tsx`, `brand.ts`) |
| 7 | Kinetic captions | Subagent (parallel) |
| 8 | Clip 1 overlays | Subagent (parallel) |
| 9 | Clip 2 overlays | Subagent (parallel) |
| 10 | Clip 3 overlays + disclaimer + wipe | Subagent (parallel) |
| 11 | Animated end screen | Subagent (parallel) |
| 12 | Audio | Subagent (parallel) |
| 13 | Brand/QA checker | Subagent |
| 14 | Render + export | Orchestrator (`render.py`, `mux.py`) |
| 15 | Completion report | Orchestrator |

---

## 7. Manual verification ज़रूरी

1. **Hindi spelling:** "रोज़" (nukta), "पाँच" (chandrabindu), "खींच", "नहीं", "निर्भर" किसी native reader से एक बार पढ़वा लें।
2. **Lip-sync:** Veo clips की अपनी lip-sync quality एक बार देख लें। Edit से timing नहीं बदली गई।
3. **Source clips में AI watermark:**
   - Clip 1 और clip 2: ✦ sparkle, करीब **x 865–935, y 1705–1775**।
   - Clip 3: "**Veo**" text, करीब **x 1025–1055, y 1883–1896**।
   - दोनों Instagram के नीचे वाले UI हिस्से (y > 1480) में हैं। चेहरा बचाने के लिए crop नहीं किया।
   - Instagram पर "AI info" label लगाने पर विचार करें।
4. **Logo:**
   - Source सिर्फ़ 300x300 px का है, इसलिए end screen पर 420 px logo थोड़ा soft दिखता है।
   - Logo artwork का orange #FE5015 है, brand का #FF6B35 नहीं।
   - Wordmark "Train Plex" (space के साथ) है, जबकि text rule "TrainPlex" है।
   - High-res या vector logo मिले तो बेहतर होगा।
5. **Music/SFX नहीं हैं:** दोनों MP4 एक जैसे हैं और end screen के 3.5 s silent हैं। Assets डालकर ये चलाएँ:
   ```bash
   python3 work/audio_mix.py
   python3 work/render.py --skip-render
   ```
6. **Earning claim:** "₹500–600 / 4 घंटे" disclaimer के साथ है, फिर भी legal/compliance review ज़रूरी है।
7. **Limiter:** peaks पर अधिकतम 3.7 dB कम किया गया है। एक बार headphones पर सुन लें।
8. **Caption timing:** clip 3 का "और" (weak voicing) ≈ 3 frames पहले दिख सकता है। यह ±2 frames की सीमा पर है, एक बार देख लें।
9. **Clip 2 chips:** face zone से सिर्फ़ 10–12 px दूर हैं (violation नहीं, पर करीब हैं)।

---

## 8. इस PR में साथ में ठीक हुए CI issues

ये `develop` पर पहले से मौजूद थे, और PR owner के कहने पर इसी PR में जोड़े गए:
- `label_studio/users/decorators/require_role.py`: ruff I001 (import के बाद एक extra blank line)।
- `label_studio/core/services/wa_broadcast.py` और `daily_report_email.py`: undefined `_FOUNDER_DIGIT_RE` की जगह `founder_guard.digits_only` लगाया। पहले यह NameError देता था और pytest smoke test fail होता था।
- अब CI (Lint TrainPlex Python, Test TrainPlex pytest) green है।
