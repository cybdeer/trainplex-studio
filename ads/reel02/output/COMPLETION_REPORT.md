# TrainPlex Reel 02: Completion Report

**प्रोजेक्ट:** TrainPlex Instagram Reel 02, "College student" (Priya)। Google Flow से character, locations और video clips बने, फिर Remotion से motion-graphics edit और animated logo CTA end screen लगा।
**तारीख:** 2026-10-01
**Worktree:** `C:\TrainPlex\trainplex-studio-reel02`
**Branch:** `feat/reel02-college-student`, base `origin/claude/trainplex-reels-motion-graphics-mj4wj0`
**PR:** §8 देखें (इस रिपोर्ट के बाद)

> **सार:** तीनों clips Google Flow में बनीं (Veo 3.1 - Quality, 9:16, 8 s, native Hindi speech)। हर clip के 2 takes बने, और clip 3 के पुरानी script वाले 2 takes भी। हर clip का एक take चुना गया। Final reel **26.866 s** का है: 806 frames, 1080x1920 @ 30 fps, H.264 High, yuv420p, BT.709, AAC-LC 48 kHz। AAC के बाद loudness **−14.02 LUFS** है और true peak **−1.58 dBTP**। QA की **9 में से 9 जाँचें PASS** हुईं। Music और SFX नहीं थे, इसलिए दोनों MP4 voice-only हैं और byte-for-byte एक जैसे हैं। Flow Scenebuilder merge का export `flow_raw/flow_merged.mp4` (23.412 s) भी मौजूद है। Git commit और PR इस report के बाद होंगे।

---

## 0. Paths (सभी deliverables)

Base: `C:\TrainPlex\trainplex-studio-reel02\ads\reel02\`

| क्या | Path | विवरण |
|---|---|---|
| मुख्य video | `output/TrainPlex_Reel02_9x16.mp4` | 1080x1920, 30 fps, 806 frames, 26.866 s, 20,120,971 bytes |
| Voice-only video | `output/TrainPlex_Reel02_9x16_nomusic.mp4` | Music नहीं थी, इसलिए ऊपर वाली file के byte-for-byte बराबर (`cmp` से जाँचा) |
| Cover | `output/TrainPlex_Reel02_cover.jpg` | 1080x1920। Global frame 82 (2.73 s) का Remotion still: hook slab "POCKET MONEY खत्म?" दिख रहा है, चेहरा साफ़ है, caption चेहरे के नीचे है |
| QA frame grabs | `output/qa/` | `qa_00_50s.png` (f15), `qa_02_00s.png` (f60), `qa_04_50s.png` (f135), `qa_12_00s.png` (f360), `qa_15_00s.png` (f450), `qa_22_00s.png` (f660), `qa_26_00s.png` (f780), `qa_endscreen_f012.png` (f713), `qa_endscreen_f045.png` (f746), `qa_endscreen_f104.png` (f805) |
| यह report | `output/COMPLETION_REPORT.md` | |
| Flow merge export | `flow_raw/flow_merged.mp4` | 720x1280 @ 24 fps, 561 frames। Video 23.412 s, audio 23.381 s। (`flow_raw/` gitignored है) |
| चुनी गई clips | `clips/clip1.mp4`, `clips/clip2.mp4`, `clips/clip3.mp4` | तीनों 720x1280 @ 24 fps, 8.000 s, Flow 720p originals |
| सभी takes + take-QA | `clips/takes/` | `*_720.mp4`, `*.qa.json`, `*.sheet.jpg`, `take_ids.txt`, archived `clip3_take2_1080.mp4` (gitignored) |
| Character sheet | `flow/character/char_01 … char_06*.png` | Originals `flow/character/_src/`, rejected `flow/character/_src/rejected/` |
| Element sheet | `flow/elements/el_01 … el_04*.png` | Originals `flow/elements/_src/`, rejected `flow/elements/_src/rejected/` |
| Checkpoint sheets | `work/checkpoint_A_character_sheet.jpg`, `work/checkpoint_B_element_sheet.jpg` | Founder को दिखाई गईं |
| Flow log | `work/flow_log.md` | Flow के चारों stages, prompts, takes, ids |
| Take QA | `work/takes_qa.md`, `work/qa_take.py` | Transcription + face similarity |
| Script | `work/script.json` | Exact script और highlight phrases |
| Edit data | `work/edit.json`, `work/flow_merge_trims.json`, `work/captions.json`, `work/captions_alignment_report.txt`, `work/face_boxes.json` | |
| Pipeline report | `work/pipeline_report.md`, `work/pipeline_run.log`, `work/run_pipeline.ps1` | |
| QA | `work/qa/qa_results.json`, `work/qa/qa_reel02.py`, `work/qa/qa_landmarks.py` | 9 checks |
| Tool versions | `work/tool_versions.json` | |
| Remotion project | `remotion/` | Compositions `Reel02`, `Reel02Graphics`, `Clip1–3`, `EndScreen`, `OrangeWipe` |

**दोबारा बनाने का तरीका** (PowerShell, `ads\reel02` से):

```powershell
$env:PYTHONUTF8 = "1"
powershell -ExecutionPolicy Bypass -File work\run_pipeline.ps1
```

Flow के 1080p upscales बाद में मिलें, तो वही takes उन्हीं नामों से `clips\clip1.mp4`, `clip2.mp4`, `clip3.mp4` पर रखकर यही command दोबारा चलाएँ।

---

## 1. Brief की हर requirement: स्थिति

### §1 Repo setup

| Requirement | Status | Note |
|---|---|---|
| अलग worktree | **DONE** | `C:\TrainPlex\trainplex-studio-reel02`। Main clone `C:\TrainPlex\trainplex-studio` में `develop` पर founder के uncommitted बदलाव थे, इसलिए उसे छुआ नहीं गया। |
| Branch `feat/reel02-college-student` | **DONE** | `origin/claude/trainplex-reels-motion-graphics-mj4wj0` से बनी। अभी checkout यही branch है। |
| Reel 01 को copy करके rename करना | **DONE** | `ads/reel02/` Reel 01 की copy है। हर `Reel01`/`reel01` identifier `Reel02`/`reel02` में बदला गया। Reel 01 की footage, renders और data copy नहीं किए गए (`work/REEL01_LESSONS.md`)। |
| Folders | **DONE** | `flow/character`, `flow/elements`, `flow_raw`, `clips/takes`, `work`, `output`, `output/qa`, `remotion`। |
| `.gitignore` | **DONE** | `flow_raw/`, `clips/takes/*`, normalised media, renders, stills और QA artefacts ignored हैं। `flow/character/*.png`, `flow/elements/*.png` और `work/qa/remotion_qa/` commit में जाएँगे (Reel 01 वाले gitignore bug का negation रखा है)। |

### §2 Human checkpoints

| Checkpoint | Status | Note |
|---|---|---|
| A: character sheet | **DONE** | `work/checkpoint_A_character_sheet.jpg` founder को दिखाई गई। |
| B: element sheet | **DONE** | `work/checkpoint_B_element_sheet.jpg` founder को दिखाई गई। |
| C | **NOT DONE (founder के निर्देश से skip)** | Founder ने कहा: "final output ही दो, बार बार मत पूछो"। इसलिए checkpoint C छोड़ दिया गया। |
| Blocker | **हल हुआ** | Chrome ने flow.google.com के लिए 2 files के बाद "multiple automatic downloads" रोक दिए। Founder ने यह permission खुद enable की। |

### §3 Character bible

| Requirement | Status | Note |
|---|---|---|
| Master portrait (head-and-shoulders) | **DONE (fix के बाद)** | v1 reject हुआ: silver jhumka earrings थे (bible में छोटे studs हैं) और skin medium-brown से हल्की थी। v2 edit से बना। |
| Full body | **DONE** | Master v2 का edit। White sneakers, navy sling bag। |
| 3/4 right | **DONE** | Master v2 का edit। |
| 3/4 left | **PARTIAL** | Flow से नहीं बन सका। 3/4 right का local horizontal mirror है। |
| Profile left | **PARTIAL** | Flow के profile का local horizontal mirror है। |
| Expressions (2x2) | **DONE** | Talking, laughing, surprised, confident। |
| Bible के तय तत्व | **DONE** | एक ही चेहरा, medium-brown skin, छोटे silver stud earrings, loose ponytail। Flow character का नाम "Priya" है, saved custom voice "Priya voice" (Autonoe पर based)। Bible के बाकी details इन files में दर्ज नहीं हैं: **अज्ञात / जाँचें**। |

### §4 Script

| Clip | Status | Final line (`work/script.json`) |
|---|---|---|
| 1 | **DONE** | Hostel में सबसे पूछो — pocket money कब खत्म होती है? बीस तारीख तक! मेरी नहीं होती, क्योंकि मैं TrainPlex पे काम करती हूँ। |
| 2 | **DONE** | Lecture के बाद, phone से — voice record, photos, text check। AI कंपनियों के छोटे tasks। कोई fees नहीं, training भी free। |
| 3 | **DONE (founder ने run के बीच बदली)** | मैं दिन में दो-तीन घंटे काम करती हूँ और चार सौ से पाँच सौ कमा लेती हूँ, सीधे Bank या UPI में। नीचे Learn more दबाओ और अभी register करो! |

**Clip 3 में founder का बदलाव (1 Oct 2026, run के बीच में):**

| | Line | Earnings plate | Highlight |
|---|---|---|---|
| **पुरानी** | Tasks available हों तो चार घंटे में पाँच सौ से छह सौ तक, सीधे Bank या UPI में। नीचे Learn more दबाओ और अभी register करो! | Reel 01 वाला ₹500–600 / "4 घंटे में तक*" | — |
| **नई** | मैं दिन में दो-तीन घंटे काम करती हूँ और चार सौ से पाँच सौ कमा लेती हूँ, सीधे Bank या UPI में। नीचे Learn more दबाओ और अभी register करो! | "₹400–500 / 2–3 घंटे*" | "चार सौ से पाँच सौ" |

Highlight phrases: pocket money, बीस तारीख, TrainPlex, phone से, कोई fees नहीं, training भी free, चार सौ से पाँच सौ, Bank या UPI, Learn more।

### §5 Google Flow के 4 stages

| Stage | Status | Note |
|---|---|---|
| 1. Character sheet | **DONE (deviations)** | 6 sheets बनीं। 2 mirror हैं और master में jhumka fix हुआ। विवरण §2 में। |
| 2. Element sheet | **DONE** | 4 plates, हर एक के 2 variations में से चुनी गईं। Props plate पर text हटाने का edit हुआ। |
| 3. Video clips | **PARTIAL** | Highest model (Veo 3.1 - Quality) रखा, पर इस mode में Ingredients-to-video नहीं चलता। इसलिए start frame + frames-to-video से बनाया। Edit का source 720p है, Flow 1080p upscale नहीं। |
| 4. Scenebuilder merge | **DONE** | clip1 take2 → clip2 take1 → clip3 take2, tails `work/flow_merge_trims.json` के हिसाब से trim किए गए। Export `flow_raw/flow_merged.mp4` में है (23.412 s)। |

### §6 Edit spec

| Requirement | Status | Note |
|---|---|---|
| 1080x1920 @ 30 fps CFR | **DONE** | Lanczos 720x1280 → 1080x1920। 24 → 30 fps frame repetition से किया, audio को नहीं छुआ। CRF 12 intermediates। |
| Measured trim, speech कभी तेज़ नहीं | **DONE** | RMS + whisper anchor और tail-event guard। तीनों clips में head trim 0.0 s (§3 में table)। |
| कुल लंबाई 25–30 s | **DONE** | 26.867 s (806 frames)। |
| End screen 3.0–4.0 s | **DONE** | 105 frames = 3.50 s (3.5 s preferred)। Legal window [90, 120] frames। |
| Order और transitions | **DONE** | Clip 1 → Clip 2 → Clip 3 hard cuts पर, हर cut पर 4-frame white flash। फिर 8-frame orange wipe और animated logo CTA end screen। |
| Captions = exact script | **DONE** | Whisper large-v3 सिर्फ़ timing के लिए। QA check 3 PASS। |
| Phrase → cue graphics | **DONE** | Clip 1: hook slab "POCKET MONEY खत्म?", "बीस तारीख" पर calendar card (circle + strike), "TrainPlex" पर logo plate। Clip 2: "Lecture के बाद • Phone से" tag, Mic/Camera/CheckSquare tiles, "₹0 FEES" और "FREE TRAINING" badges। Clip 3: earnings plate "₹400–500 / 2–3 घंटे*" count-up के साथ, 8 % punch-in, Bank / UPI card और tick, "Learn more" + down-arrow। सारे cues `findPhrase` से script पर derive होते हैं। |
| Flow merge trims export | **DONE** | `work/flow_merge_trims.json`। |

### §7 Brand / layout

| Requirement | Status | Note |
|---|---|---|
| Brand colours, flat, sharp corners | **DONE** | Cream #FAF7F2, Navy #1A1A5E, Orange #FF6B35, White, border #E8E3DA। Emoji की जगह lucide icons। |
| Safe zone x 60–1020, y 220–1480 | **DONE (code fix के बाद)** | पहले render पर QA check 5 fail हुआ। Fix: graphics layer को SAFE पर clip किया (§4 deviation 11)। अब PASS। |
| आँख/मुँह पर कोई graphic नहीं | **DONE** | QA check 4: 689 frames जाँचे, 0 violations। सबसे कम clearance: eyes 109.2 px, mouth 42.0 px (clip 3)। |
| कभी दो logos एक साथ नहीं | **DONE** | QA check 7 PASS। |
| Logo unaltered | **DONE** | Reel 01 वाला transparent logo (`make_logo_alpha.py` output) ही इस्तेमाल हुआ। |
| Text में brand "TrainPlex" | **DONE** | Captions में "TrainPlex" uppercase नहीं किया जाता (KEEP_CASE)। |

### §8 Audio

| Requirement | Status | Note |
|---|---|---|
| Per-clip chain (HPF, sibilance test, −16 LUFS, fades) | **DONE** | §3 में numbers। किसी clip पर de-ess नहीं लगा (0/3 flags)। |
| Master −14 LUFS, TP ≤ −1 dBTP (AAC के बाद) | **DONE** | −14.022 LUFS, −1.577 dBTP, LRA 1.99 LU। |
| Music bed + ducking | **NOT DONE (asset absent)** | `assets/music.mp3` नहीं था। Code तैयार है। |
| SFX (whoosh/pop/ding) | **NOT DONE (asset absent)** | `assets/sfx/*` नहीं थे। Cues अब clip joins से derive होते हैं। |

### §9 Outputs

| Output | Status | Note |
|---|---|---|
| `TrainPlex_Reel02_9x16.mp4` | **DONE** | §3 और §0 देखें। |
| `TrainPlex_Reel02_9x16_nomusic.mp4` | **DONE** | Music नहीं थी, इसलिए मुख्य file जैसा ही है। |
| `TrainPlex_Reel02_cover.jpg` | **DONE** | Frame 82। |
| `output/qa/*.png` | **DONE** | 7 time points और end screen के 3 frames। |
| `flow_raw/flow_merged.mp4` | **DONE** | 23.412 s। |
| `COMPLETION_REPORT.md` | **DONE** | यही file। |

### §10 QA (9 checks), `work/qa/qa_results.json`, all_pass = true

| # | Check | Result | मुख्य evidence |
|---|---|---|---|
| 1 | ffprobe delivery specs (1080x1920, 30 fps, H.264 High, yuv420p, BT.709, 25–30 s) | **PASS** | दोनों MP4: h264 High, 1080x1920, 30/1, 806 frames, yuv420p, bt709 (tv range), 26.866 s, AAC LC 48 kHz 2 ch |
| 2 | AAC के बाद loudness −14 ± 0.5 LUFS, TP ≤ −1 dBTP | **PASS** | −14.022 LUFS, TP −1.577 dBTP, LRA 2.0 LU (दोनों files) |
| 3 | Captions = exact script, chunk swap पर कोई blank frame नहीं | **PASS** | Chunks: clip 1 में 7, clip 2 में 8, clip 3 में 9। कोई chunk 2 lines में नहीं। Blank swaps 0। Planned pause fades: clip 1 f141–143, clip 2 f174–178 |
| 4 | Eye/mouth boxes में कोई overlay pixel नहीं (Haar + insightface landmarks, camera-mapped) | **PASS** | 689 frames, 0 violations। Min clearance (Haar): clip 1 eyes 109.2 / mouth 54.0, clip 2 210.5 / 57.0, clip 3 185.0 / 42.0 px |
| 5 | हर overlay safe zone x 60–1020, y 220–1480 में | **PASS** | बाहर 0 frames। Exempt: progress bar rows 220–228, join flashes, orange wipe |
| 6 | Earnings number दिखने के पूरे समय disclaimer दिखे | **PASS** | Figure clip-3 local f62–117 (pixel) / 62–118 (code)। Disclaimer पूरा f13–229। Figure से 49 frames पहले आता है, बाद में 3.7 s रहता है। Strip y 1416–1470 |
| 7 | कभी दो logos एक साथ नहीं | **PASS** | 2+ logos वाले frames 0। Logo frames: clip 1 [33–183], [186–233]; clip 2 [366–465]; clip 3 [470–696]; end screen [704–805] |
| 8 | Joins पर black/frozen frames नहीं, A/V offset ≤ 1 frame | **PASS** | तीनों joins पर black 0, 3+ frozen 0। A/V lag 0 ms (तीनों clips)। Video और audio दोनों 0.000 से शुरू, दोनों 26.866 s। Freezedetect ने सिर्फ़ end screen (24.87–26.2 s) में starts दिए |
| 9 | Face-embedding similarity vs `char_01_master.png` (insightface, 0.45) | **PASS** | Median: clip 1 0.687, clip 2 0.662, clip 3 0.638। Min: 0.493 / 0.406 / 0.477। Clip 2 के frames 59–60 और 81–84 (2.6 %) 0.45 से नीचे हैं |

### §11 Git + PR

| Requirement | Status | Note |
|---|---|---|
| Commit + push + PR | **इस रिपोर्ट के बाद (pending)** | Main agent यह काम इस report के बाद करेगा और PR link §8 की `PR:` वाली line में भरेगा। |

---

## 2. Google Flow के 4 stages: prompts, चुने गए और reject हुए takes

**Flow project:** "TrainPlex Reel 02" (`flow.google.com/project/79517316-0202-4bc1-9e0e-ad224f854d8e`)
**Account:** PRO plan, शुरुआत में 1,050 credits।
**Settings:** confirm-before-generating = Always। Image 9:16, Nano Banana Pro (Pro / 2 / 2 Lite में सबसे ऊँचा)। Video 9:16, Veo 3.1 - Quality (Omni 1.1 Flash / Veo 3.1 Lite / Fast / Quality में सबसे ऊँचा), x2।
**Downloads:** 2K upscaled। 4K के लिए paid upgrade चाहिए, इसलिए उसका इस्तेमाल नहीं हुआ। Flow JPG export करता है, उन्हें losslessly PNG में बदला गया।
**Visible watermark:** Flow की account setting "Visible watermarking is required in your region" locked ON है। इसलिए हर image के नीचे-दाएँ एक छोटा sparkle mark है।

### Stage 1: Character sheet

| File | Source | Note |
|---|---|---|
| `char_01_master.png` | Master spec prompt (verbatim) → head-and-shoulders में re-frame → edit fix | v1 reject: silver jhumka earrings (bible में छोटे studs) और skin medium-brown से हल्की। v2 = edit: "replace jhumkas with small plain silver studs; natural medium-brown complexion" |
| `char_02_fullbody.png` | Master v2 का edit | Full body front, white sneakers, navy sling bag |
| `char_03_threequarter_left.png` | `char_04` का horizontal MIRROR | Flow ने 2 कोशिशों में उसे दूसरी तरफ़ नहीं घुमाया (नाक हमेशा frame के दाईं ओर)। Mirror की वजह से sparkle नीचे-बाएँ आ गया |
| `char_04_threequarter_right.png` | Master v2 का edit | |
| `char_05_profile_left.png` | Flow profile का horizontal MIRROR | `char_03` वाला ही कारण |
| `char_06_expressions.png` | Master v2 का edit | 2x2: talking, laughing, surprised, confident |

**Reject हुए (download किए, `flow/character/_src/rejected/`):** `master_v1_jhumka_lightskin`, `fullbody_v1_jhumka`, `threequarter_v1_jhumka`।
**Flow के अंदर reject (download नहीं किए):** शुरुआती 2 medium shots (waist-up थे, head-and-shoulders नहीं) और 1 failed "mirror pose" edit।

**Prompts (master spec prompt के अलावा):**
- Re-frame: "Using the first image ... as the identity reference ... tight HEAD-AND-SHOULDERS close-up, front view ..."
- Fix: "Keep this exact image ... Only two changes: (1) replace the dangling jhumka earrings with SMALL PLAIN SILVER STUD earrings ... (2) skin tone a natural medium-brown Indian complexion ..."
- Full body / 3-4 / profile / expressions: "Same person, identical face, medium-brown skin, small silver stud earrings, loose ponytail ... Re-frame as FULL BODY | THREE-QUARTER view | full 90-degree SIDE PROFILE | CHARACTER EXPRESSION SHEET 2x2 ..."

### Stage 2: Element sheet (सब Nano Banana Pro, हर एक के 2 variations, 2K download)

| File | चुना गया | Reject + कारण |
|---|---|---|
| `el_01_hostel_room.png` | Variation 2: खिड़की से गर्म सुनहरी रोशनी, fairy lights | Variation 1: रोशनी flat थी, late-afternoon वाला mood कम था। Note: desk के एक छोटे sticky note पर अपठनीय लिखावट है (background में, पढ़ी नहीं जा सकती) |
| `el_02_canteen_corridor.png` | Variation 1: भीड़ वाला corridor, notice boards, canteen counter, दूर students | Variation 2: ज़्यादा खाली था, और ऊपर-दाएँ signage board पर पढ़ने लायक text आने का खतरा था |
| `el_03_campus_steps.png` | Variation 2: पेड़ों से sun flare, sandstone arches | Variation 1: golden-hour कम था |
| `el_04_props.png` | Variation 2 + edit "remove ALL writing and labels from the notebooks" | Variation 1: bag का strap भूरे leather का था (character के bag का strap navy fabric है)। Variation 2 बिना edit: notebooks पर बिगड़ा हुआ text "COLLEGE NOTEBOOG" था → `_src/rejected/props_v1_text_on_notebooks.jpg` |

**Prompts:** हर एक "New image, NOT based on any previous image, no people ... Photorealistic empty location plate ..." से शुरू हुआ, फिर §5 Stage 2 का description। साथ में: "warm, friendly, youthful colour mood, eye-level smartphone camera perspective, clear space in the foreground for a person. Vertical 9:16. No text, no logos, no watermark."

### Stage 3: Video clips (Veo 3.1 - Quality, 9:16, 8 s, native speech, 720p original)

**Mode deviation:** Flow का Ingredients-to-video (character + location references) सिर्फ़ Omni 1.1 Flash / Veo 3.1 Lite पर चलता है। Veo 3.1 - Quality reference images नहीं लेता। सबसे ऊँचा model और identity lock दोनों रखने के लिए हर clip दो कदम में बनी ("equivalent reference mode"):
1. **Start frame:** Nano Banana Pro image, ingredients = Flow character "Priya" (portrait = `char_01_master.png`, saved custom voice "Priya voice", Autonoe पर based) + clip की location plate (el_01 / el_02 / el_03)। 2 variations, सबसे अच्छी framing चुनी: आँखें ऊपर से ~32–42 % पर, phone दिखता हुआ।
2. **Video:** उस start frame से Veo 3.1 - Quality frames-to-video, §5 prompt template + exact line के साथ।
   - Character की saved voice Quality mode में attach नहीं हो सकती। Voice consistency prompt "a young Indian woman's voice" से रखी गई।
   - `el_04_props` attach नहीं किया, क्योंकि इससे tiffin/notebooks frame में आ जाते। Phone और bag character से पहले ही lock थे।

**Credits:** 4 batches x 200 = 1,050 में से 800 इस्तेमाल हुए। Images का कोई credit नहीं लगा।

| Clip | Take | Flow id | फैसला | कारण |
|---|---|---|---|---|
| 1 | take1 | 2193535b | **REJECT** | आखिरी हिस्सा English में बोला ("because I work on TrainPlex"), transcript match 0.74। 3.5 s और 6.5 s पर frame में एक extra हाथ आता है |
| 1 | take2 | b6b6015c | **KEEP** → `clips/clip1.mp4` | Transcript 1.00, बीस + TrainPlex सही, face sim mean 0.67 |
| 2 | take1 | ffd3ceca | **KEEP** → `clips/clip2.mp4` | Transcript 1.00, face 0.67, कोई artefact नहीं |
| 2 | take2 | 29e5b7ae | **REJECT** | पूरी clip में बड़ा Flow sparkle watermark जला हुआ है (start frame से आया)। Transcript 0.95 |
| 3 (पुरानी script) | take1 | 2fb696f1 | **REJECT** | Generation के बाद founder ने clip 3 की script बदल दी। साथ ही 1.5 s के बाद phone गायब हो जाता है |
| 3 (पुरानी script) | take2 | 0cf944f6 | **REJECT** | Generation के बाद founder ने clip 3 की script बदल दी |
| 3 | take1 | 5d3d0216 | **REJECT** | Face similarity min 0.447 (0.45 flag से नीचे) |
| 3 | take2 | 9bf25b6e | **KEEP** → `clips/clip3.mp4` | Transcript 1.00, अंक दो/तीन/चार सौ/पाँच सौ सही, phone पूरी clip में हाथ में, face 0.64 |

**Take QA (`work/takes_qa.md`, `work/qa_take.py`):** Transcript columns बिना prompt वाले whisper pass से हैं। Script-prompted pass का शब्द सिर्फ़ तब लिया गया जब unprompted pass ने वहाँ कुछ नहीं सुना या मिलती-जुलती spelling सुनी। Prompted-pass के जिन शब्दों की duration ~0 s या prob < 0.30 थी, उन्हें prompt echo मानकर छोड़ा गया। Face sim = `flow/character/char_01_master.png` से insightface cosine, flag < 0.45। eye_y target ~0.35।

| Clip | Take | transcript_ok | match | गलत / छूटे शब्द | Face sim min / mean | eye_y | Verdict (script) |
|---|---|---|---|---|---|---|---|
| 1 | 1 | NO | 0.74 | क्योंकि, मैं, पे→I, काम→work, करती→on, हूँ→trainplex | 0.597 / 0.706 | 0.32 | FAIL (transcript) |
| 1 | 2 | yes | 1.00 | — | 0.505 / 0.67 | 0.317 | PASS |
| 2 | 1 | yes | 1.00 | — | 0.535 / 0.674 | 0.406 | PASS |
| 2 | 2 | yes | 0.95 | से→कॉर्ड | 0.667 / 0.73 | 0.419 | PASS (watermark की वजह से manual REJECT) |
| 3 पुरानी | 1 | yes | 0.96 | available→अवेलिबल | 0.482 / 0.594 | 0.42 | PASS (script बदलने से REJECT) |
| 3 पुरानी | 2 | yes | 0.96 | available→अवेलिबल | 0.561 / 0.654 | 0.417 | PASS (script बदलने से REJECT) |
| 3 नई | 1 | yes | 1.00 | — | 0.447 / 0.6 | 0.423 | REVIEW (face similarity) |
| 3 नई | 2 | yes | 1.00 | — | 0.573 / 0.642 | 0.422 | PASS |

सभी 8 takes का probe: 720x1280, 24 fps, 8.0 s, h264 + AAC 48 kHz stereo। किसी भी take में black/freeze segment नहीं मिला।

**Resolution:** Flow में 720p original, 1080p "Upscaled" और 4K (paid upgrade, इस्तेमाल नहीं) के options हैं। UI में 1080p upscale downloads भरोसेमंद नहीं थे (menu freeze हो जाता था)। सिर्फ़ clip 3 का 1080p आया: `clips/takes/clip3_take2_1080.mp4` (archived)। तीनों clips एक जैसी दिखें, इसलिए edit के तीनों sources 720p originals हैं, जिन्हें `normalise.py` में Lanczos से 1080x1920 पर upscale किया गया (spec में यह रास्ता allowed है)।

### Stage 4: Flow Scenebuilder merge

- **Scene:** "TrainPlex Reel 02 - Flow merge" (`flow.google.com/project/79517316-.../scene/24d51882-2250-4743-90a5-3a4a73a29684`)।
- **क्रम:** clip1 take2 → clip2 take1 → clip3 take2।
- **Trims:** tails `work/flow_merge_trims.json` के हिसाब से काटी गईं: 7.833 / 7.733 / 7.800 s। Head trim की ज़रूरत नहीं थी (speech 0.0–0.1 s पर शुरू होती है)।
- **Durations:** Scenebuilder total 23.33 s, edit का clips total 23.367 s (24 fps पर 1 frame के अंदर)।
- **Export:** `flow_raw/flow_merged.mp4`। ffprobe: 720x1280 @ 24 fps, 561 frames, video 23.412 s, audio 23.381 s।

---

## 3. Tool versions, durations और loudness

### Tool versions (`work/tool_versions.json`, `work/pipeline_report.md`)

| Tool | Version |
|---|---|
| OS | Windows (10.0.26300) |
| Node.js / npm | v25.9.0 / 11.12.1 |
| Remotion / @remotion/cli / @remotion/renderer | 4.0.529 |
| React / TypeScript | 19.1.0 / 5.8.3 |
| lucide-react | 1.48.0 |
| @fontsource/inter / @fontsource/noto-sans-devanagari | 5.3.0 / 5.3.0 |
| Chrome headless shell | Remotion ने पहले bundle पर download किया (version: अज्ञात / जाँचें) |
| Python | 3.11.9 (`C:\Users\DESKTOP\AppData\Local\Programs\Python\Python311\python.exe`) |
| FFmpeg / ffprobe | N-124445-g22d06b39ce-20260513 (`C:\TrainPlex\tools\ffmpeg\bin`), libx264 / loudnorm / ebur128 मौजूद |
| faster-whisper / ctranslate2 | 1.2.1 / 4.8.2 |
| Whisper model | Systran/faster-whisper-large-v3, language hi, CPU int8, word timestamps (सिर्फ़ timing) |
| insightface / onnxruntime | 2.0 (buffalo_l) / 1.30.0 |
| OpenCV | 4.12.0 (4.12.0.88) |
| numpy / scipy / Pillow / scikit-image | 2.2.6 / 1.17.1 / 12.2.0 / 0.26.0 |
| pyloudnorm / uharfbuzz / fonttools | 0.2.0 / 0.56.2 / 4.66.1 |
| mediapipe | Installed नहीं (`face_track.py` OpenCV Haar इस्तेमाल करता है) |
| Google Flow | Image: Nano Banana Pro। Video: Veo 3.1 - Quality |

### Clip durations (trim से पहले और बाद में)

| Clip | Source | Source duration | In → Out | Trim के बाद | Frames @ 30 | Speech on / off | Pre-roll / tail रखा | Note |
|---|---|---|---|---|---|---|---|---|
| 1 | 720x1280 @ 24 | 8.000 s | 0.0000 → 7.8333 s | **7.833 s** | 235 | 0.00 / 7.75 s | 0.00 / 0.08 s | 7.87 s पर click/breath, cut उससे पहले |
| 2 | 720x1280 @ 24 | 8.000 s | 0.0000 → 7.7333 s | **7.733 s** | 232 | 0.17 / 7.54 s | 0.17 / 0.19 s | |
| 3 | 720x1280 @ 24 | 8.000 s | 0.0000 → 7.8000 s | **7.800 s** | 234 | 0.10 / 7.65 s | 0.10 / 0.15 s | 7.81 s पर click/breath, cut उससे पहले |
| Clips कुल | | 24.000 s | | **23.367 s** | 701 | | | |
| End screen | | | | **3.500 s** | 105 | | | |
| **Reel कुल** | | | | **26.867 s** | **806** | | | |

**Join gaps (आवाज़ के बीच, RMS numbers से गणना):** clip 1→2 ≈ 0.08 + 0.17 = **0.25 s**। Clip 2→3 ≈ 0.19 + 0.10 = **0.29 s**। Reel 01 का guideline ≤ 0.25 s था, clip 2→3 उससे थोड़ा ऊपर है। Speech नहीं काटी जाती, इसलिए इसे वैसा ही रखा। एक बार सुनकर देख लें।

### ffprobe (इस report के लिए दोबारा चलाया)

| File | Duration | Video | Audio |
|---|---|---|---|
| `output/TrainPlex_Reel02_9x16.mp4` | **26.866 s** | h264 1080x1920, 30/1, 806 frames | AAC |
| `output/TrainPlex_Reel02_9x16_nomusic.mp4` | **26.866 s** | h264 1080x1920, 30/1, 806 frames | AAC |
| `flow_raw/flow_merged.mp4` | **23.412 s** (audio 23.381 s) | h264 720x1280, 24/1, 561 frames | AAC |

### Loudness

| Clip | पहले I (LUFS) | पहले TP (dBTP) | Sibilance indicators (ltas / svr / burst) | De-ess | Gain (dB) | बाद में I (LUFS) |
|---|---|---|---|---|---|---|
| 1 | −22.332 | −2.361 | −13.45 / −17.02 / −8.25 | नहीं (0/3) | +6.516 | −16.004 |
| 2 | −23.826 | −11.437 | −15.42 / −16.4 / −12.53 | नहीं (0/3) | +7.833 | −16.000 |
| 3 | −23.031 | −9.119 | −18.17 / −17.8 / −13.16 | नहीं (0/3) | +7.041 | −16.001 |

- **Chain:** 80 Hz 2nd-order HPF → sibilance test → static gain से हर clip −16 LUFS → 5 ms edge fades → static gain + 4x oversampled look-ahead true-peak limiter (ceiling −1.6 dBTP, max GR 5.81 dB, GR > 1 dB सिर्फ़ 3.122 % समय)।
- **Master WAV:** I −14.008 LUFS, TP −1.598 dBTP, LRA 1.99 LU। `loudnorm` dynamic mode में चला जाता, इसलिए उसका इस्तेमाल नहीं किया।
- **AAC के बाद (दोनों MP4):** I **−14.022 LUFS**, TP **−1.577 dBTP**, LRA 1.99 LU। AAC LC 48000 Hz, faststart True।

### Render

Remotion → H.264 High, 1080x1920, 30/1 fps, yuv420p, bt709/bt709/bt709 (tv range), CRF 18, x264 slow, PNG intermediate frames, 806 frames, 5.81 Mb/s। Video muted render हुआ, audio बाद में `mux.py --strict` से जोड़ा गया।

### Face tracking (`work/face_boxes.json`)

| Clip | Frames | Haar detections | Filled | Outliers rejected | Face union (x1, y1 → x2, y2) |
|---|---|---|---|---|---|
| 1 | 235 | 235 | 0 | 0 | 178, 250 → 954, 1034 |
| 2 | 232 | 217 | 15 | 1 | 290, 520 → 898, 1096 |
| 3 | 234 | 230 | 4 | 0 | 350, 626 → 822, 1068 |

---

## 4. Deviations और उनके कारण

1. **Veo 3.1 - Quality में Ingredients mode नहीं है।**
   - Ingredients-to-video सिर्फ़ Omni 1.1 Flash / Veo 3.1 Lite पर है।
   - सबसे ऊँचा model रखने के लिए start frame (Nano Banana Pro + Priya + location plate) बनाकर उससे frames-to-video चलाया।

2. **3/4-left और left-profile images mirror हैं।**
   - Flow ने 2 कोशिशों में भी character को दूसरी तरफ़ नहीं घुमाया।
   - इसलिए locally horizontal mirror किया। इन दोनों में sparkle watermark नीचे-बाएँ है।
   - Mirror से चेहरे की असमानताएँ (जैसे बालों की माँग) उलटी हो सकती हैं। Profile-left की master से similarity सिर्फ़ 0.464 है (बाकी sheets 0.715–0.811)।

3. **Master v1 में jhumka fix।**
   - v1 में silver jhumkas थे और skin हल्की थी।
   - Edit से छोटे silver studs और natural medium-brown skin किया। v1 पर बनी full-body और 3/4 images भी reject कीं।

4. **4K की जगह 2K images।** 4K download के लिए paid upgrade चाहिए था।

5. **Flow 1080p upscale की जगह 720p + Lanczos।**
   - Flow UI में 1080p upscale download भरोसेमंद नहीं था (menu freeze होता था)। सिर्फ़ clip 3 का 1080p मिला।
   - तीनों clips एक जैसी दिखें, इसलिए तीनों 720p originals को Lanczos से upscale किया।

6. **Flow/Veo के visible watermarks नहीं हटाए।**
   - Flow की account setting में visible watermark locked ON है ("required in your region")।
   - Source clips में छोटे AI watermarks हैं: नीचे-दाएँ Veo text और कभी-कभी sparkle। Brief के अनुसार इन्हें न हटाया गया, न blur किया गया।
   - ये safe zone के नीचे हैं। Clip 2 take2 को reject किया गया, क्योंकि उसमें बड़ा sparkle पूरी clip में जला हुआ था।
   - Meta का "AI info" label लगाने पर विचार करें।

7. **Clip 3 की script founder ने बदली (1 Oct 2026, run के बीच)।**
   - नया earnings claim **₹400–500 / 2–3 घंटे** है। Plate "₹400–500 / 2–3 घंटे*" है और disclaimer के साथ दिखता है (QA check 6 PASS)।
   - पुरानी script वाले 2 takes (2fb696f1, 0cf944f6) बेकार हुए। नई script के लिए 2 और takes बनाने पड़े।
   - यह नया claim है, इसलिए legal review ज़रूरी है (§6)।
   - Reel 01 का disclaimer text था: "*कमाई task availability और approval पर निर्भर है"। Reel 02 में यही text है या बदला गया: **अज्ञात / जाँचें**।

8. **Props plate (el_04) video ingredient में इस्तेमाल नहीं हुई।** उससे tiffin और notebooks frame में आ जाते। Phone और bag character से पहले ही lock थे।

9. **Priya की custom voice attach नहीं हुई।** Quality mode में saved voice ("Priya voice", Autonoe पर based) attach नहीं होती। Voice consistency सिर्फ़ prompt "a young Indian woman's voice" से रखी गई। तीनों clips की आवाज़ एक जैसी लगती है या नहीं, यह सुनकर जाँचें।

10. **Clip 2 में शायद एक extra शब्द "सेंड" है।**
    - Whisper ने "phone से" और "voice" के बीच 1.42–1.70 s पर एक extra शब्द "सेंड" सुना।
    - Captions script के हिसाब से हैं, और "से —" वाला word उस हिस्से को cover करता है।
    - अगर Priya सच में extra शब्द बोलती है, तो take या script line पर दोबारा सोचना होगा।

11. **Safe-zone clipping का code fix।**
    - असली render पर QA check 5 fail हुआ, क्योंकि entrance/exit slides safe zone से बाहर बन रही थीं:
      - Clip 1 का hook slab f0–3 पर x < 60 से अंदर आता था और f100–103 पर x 1020 से बाहर जाता था।
      - Clip 2 के tag/chips भी बाहर जाते थे।
      - Clip 3 के plate/card exits भी बाहर जाते थे।
      - End screen का CTA local f29–34 पर y 1920 से उठता था।
    - Fix: `Clip1.tsx`, `Clip2.tsx`, `Clip3.tsx` और `EndScreen.tsx` में graphics layer और end-screen CTA को `clipPath` inset से SAFE (x 60–1020, y 220–1480) पर clip किया। Timing, position या size में कोई बदलाव नहीं हुआ।

12. **Clip 3 में caption split बदला।**
    - "नीचे Learn more दबाओ" 2 lines में बन रहा था (221 px block, LEARN MORE uppercase और x1.15)। इससे Learn-more arrow block ढक जाता था, जबकि `REMOTION_INPUTS.md` में वहाँ एक line चाहिए।
    - नया split: "नीचे Learn more" | "दबाओ और अभी" | "register करो!"। तीनों एक line में हैं, और caption text अब भी script के बराबर है।

13. **QA rules का calibration।**
    - **Check 9 (identity):** हर frame score होता है, 8 samples नहीं। Rule: हर clip का median ≥ 0.45 और 0.45 से नीचे ≤ 5 % frames। Blur, blink या बोलते समय single frames नीचे जाते हैं।
      - Reference की calibration दूसरी sheets से की: full body 0.776, 3/4 left 0.811, 3/4 right 0.809, profile left 0.464, expressions 0.715।
      - Clip 2 के कुछ frames (min 0.406, frames 59–60, 81–84) flag हैं।
    - **Take QA:** Transcript unprompted whisper से लिया। Prompted pass से सिर्फ़ "rescue" लिया गया, और prompt echo (duration ~0 या prob < 0.30) को अनदेखा किया।
    - **Checks 4–5:** 4-frame white join flash और 8-frame orange wipe full-frame transitions हैं, overlay नहीं, इसलिए exempt हैं। 8 px progress bar (y 220–228) x-limits से exempt है (Reel 01 जैसा)।

14. **Clip 1 के आगे breathing room 0.00 s है।** "Hostel" source के पहले sample पर शुरू होता है। Frames बनाए बिना आगे कुछ नहीं जोड़ा जा सकता।

15. **Clip 3 के आगे breathing room 0.10 s है** (target 0.15–0.25 s)। Source में speech 0.10 s पर शुरू होती है, पूरा 0.10 s रखा।

16. **Clip 1 की tail 0.08 s है।** 7.87 s पर एक तेज़ click/burst (−9 से −2 dBFS) है, जो "हूँ" (7.75 s पर खत्म) के बाद आता है। Cut 7.833 s (frame 235) पर उससे पहले होता है। Speech नहीं कटी।

17. **Earnings caption chunk 5 शब्दों का है।** "चार सौ से पाँच सौ" एक chunk में रखा (नियम 2–4 शब्द), ताकि figure एक phrase की तरह पढ़ा जाए। यह `REMOTION_INPUTS.md` के अनुसार है।

18. **De-essing नहीं लगा।** Objective sibilance test में हर clip के 3 indicators में से 0 flag हुए (de-ess का नियम ≥ 2)।

19. **Music/SFX नहीं हैं।** `assets/music.mp3` और `assets/sfx/*` मौजूद नहीं थे। इसलिए `_9x16.mp4` और `_nomusic.mp4` में एक ही voice-only mix है, और end screen silent है। `audio_mix.py` में hooks तैयार हैं।

20. **Identity model का licence।** insightface buffalo_l non-commercial research licence के तहत है। इसे सिर्फ़ internal QA signal के रूप में इस्तेमाल किया, ship नहीं किया।

21. **Pipeline code में Reel 01 की hard-coded values बदली गईं (code fixes):**
    - `work/qa/dump_cues.ts`: Reel 02 के exports पर दोबारा लिखा।
    - `work/normalise.py`: hard-coded EDIT की जगह measured trim, end-screen length का चुनाव, `flow_merge_trims.json`, BT.709 tags।
    - `work/align_captions.py`: script और highlights `script.json` से आते हैं। Pause handling ठीक की (Reel 01 वाला rule "Hostel" को 0.47 s पर ले जाता था, जबकि वह 0.00 s से बोला गया है)। SPANS count assert जोड़ा।
    - `work/face_track.py`: अब हर frame track होता है (पहले हर 3rd frame)। Outliers reject होते हैं, gaps भरे जाते हैं, per-frame eyes/mouth rects बनते हैं।
    - `work/audio_mix.py`: `END_SCREEN_FRAMES` अब `edit.json` से आता है। SFX cues clip joins से derive होते हैं।
    - `work/render.py`: Windows पर `npx.cmd`। End-screen start और cover frame derive होते हैं (Reel 01 का "बंद" lookup crash करता)। `mux --strict`।
    - `work/qa/qa_reel02.py`, `qa_landmarks.py`: नया 9-check suite।
    - `remotion/.real_stills.mjs`: नया helper (gitignored)। PowerShell 5.1 native arguments से quotes हटा देता है, इसलिए jobs JSON file से पढ़ता है।

22. **Downloads blocker।** Chrome ने 2 files के बाद flow.google.com के automatic downloads रोक दिए। Founder ने permission enable की।

23. **Checkpoint C skip।** Founder का निर्देश था: "final output ही दो, बार बार मत पूछो"।

---

## 5. Agent roles: brief के 15 roles और असल में क्या चला

**ईमानदार स्थिति:** Brief में 15 roles थे, लेकिन काम **करीब 5 background agents + main session** में बँटा, 15 अलग agents में नहीं। कारण:
- इस account पर ~5 से ज़्यादा concurrent agents चलाने पर 429 (rate limit) आता है।
- कई roles एक ही shared files पर काम करते हैं: `timeline.ts`, `brand.ts`, `captions.json`, `edit.json`, और remotion data files। अलग-अलग agents में बाँटने पर output एक-दूसरे को overwrite कर देते।
- Google Flow का काम एक ही browser session में होना था। इसलिए सिर्फ़ main session ने browser इस्तेमाल किया।

| Agent | किसने किया | कौन से roles |
|---|---|---|
| **Main session** | Orchestrator | Orchestration और integration, **Google Flow operator** (अकेला browser user: character/element sheets, start frames, video takes, Scenebuilder merge, downloads), founder checkpoints A/B, takes का visual QA फैसला (keep/reject), founder का clip 3 बदलाव लागू करना |
| Background agent 1 | Repo / env setup | Worktree, branch, Reel 01 copy और rename, folders, `.gitignore`, tool versions (`work/tool_versions.json`), `work/REEL01_LESSONS.md` |
| Background agent 2 | Take-QA | Transcription और face similarity। `work/qa_take.py` बनाया, `clips/takes/*.qa.json`, contact sheets और `work/takes_qa.md` दिए |
| Background agent 3 | Remotion motion graphics | Clip 1–3 graphics, end screen, captions, overlays। `work/REMOTION_INPUTS.md` contract |
| Background agent 4 | Edit pipeline | Normalise/trim, caption alignment, face tracking, audio, render/mux/cover/grabs, 9-check QA suite, safe-zone fix, `work/pipeline_report.md` |
| Background agent 5 | Report writer | यह `COMPLETION_REPORT.md` |

**Brief के 15 roles का mapping** (role names Reel 01 वाली सूची के आधार पर। Reel 02 brief की exact सूची इन files में नहीं है: **अज्ञात / जाँचें**):

| # | Role | असल में किसने किया |
|---|---|---|
| 1 | Orchestrator / integration | Main session |
| 2 | Environment setup | Agent 1 (repo/env) |
| 3 | Character + element generation (Flow) | Main session (Flow operator) |
| 4 | Video generation (Flow) + merge | Main session (Flow operator) |
| 5 | Take QA (transcript + identity) | Agent 2 (take-QA), फैसला main session का |
| 6 | Probe + trim/normalise | Agent 4 (edit pipeline) |
| 7 | Transcription + caption alignment | Agent 4 (edit pipeline) |
| 8 | Kinetic captions | Agent 3 (Remotion) |
| 9 | Clip 1 overlays | Agent 3 (Remotion) |
| 10 | Clip 2 overlays | Agent 3 (Remotion) |
| 11 | Clip 3 overlays + disclaimer + wipe | Agent 3 (Remotion) |
| 12 | Animated end screen | Agent 3 (Remotion) |
| 13 | Audio | Agent 4 (edit pipeline) |
| 14 | Brand/QA checker + render/export | Agent 4 (edit pipeline) |
| 15 | Completion report | Agent 5 (report writer) |

---

## 6. Manual verification ज़रूरी

1. **Lip-sync:** तीनों clips एक बार ध्यान से देखें। Edit से timing नहीं बदली गई, lip-sync Veo का अपना है।
2. **Clip 2 का extra शब्द:** 1.42–1.70 s पर "phone से" के बाद "सेंड" जैसा कुछ सुनाई देता है या नहीं, सुनें। अगर है, तो take या script line पर फैसला करें।
3. **Limiter:** headphones पर सुनें। Max gain reduction 5.81 dB है (Reel 01 में 3.7 dB था)। Clip 1 के आखिर का click अब नहीं होना चाहिए, यह भी सुनें।
4. **Join gaps:** clip 2→3 पर आवाज़ के बीच ≈ 0.29 s का gap है। ठीक लगता है या नहीं, सुनें।
5. **Voice consistency:** saved "Priya voice" attach नहीं हुई थी। तीनों clips में आवाज़ एक ही लड़की की लगे, यह जाँचें।
6. **Native Hindi review:** captions और graphics की spelling किसी native reader से पढ़वाएँ (chandrabindu: पाँच, हूँ; "खत्म", "तारीख", "कंपनियों", "दो-तीन")।
7. **Earnings claim का legal review:** नया claim "₹400–500 / 2–3 घंटे" और "चार सौ से पाँच सौ कमा लेती हूँ" disclaimer के साथ है। फिर भी legal/compliance review ज़रूरी है। Disclaimer का Reel 02 text भी confirm करें (§4 deviation 7)।
8. **Watermarks:** paid ads के लिए Flow sparkle और Veo text watermark acceptable हैं या नहीं, तय करें। Meta का "AI info" label लगाने पर विचार करें।
9. **Flow merged export:** `flow_raw/flow_merged.mp4` (23.412 s, 561 frames @ 24) को edit के clips total 23.367 s और Scenebuilder total 23.33 s से मिलाएँ। Cut points और takes सही हैं, यह एक बार देखकर confirm करें।
10. **Identity dips:** clip 2 के frames 59–60 और 81–84 (similarity < 0.45) एक बार देखें।
11. **Music/SFX:** बाद में जोड़ने हैं। Files `assets/music.mp3` और `assets/sfx/{whoosh,pop,ding}.wav` पर रखें, फिर `audio` stage से pipeline दोबारा चलाएँ। तब तक end screen silent है।
12. **Logo lockup:**
    - Source logo सिर्फ़ 300x300 px का है, इसलिए बड़े size पर soft दिखता है।
    - Artwork का orange #FE5015 है, brand का #FF6B35 नहीं।
    - Wordmark "Train Plex" (space के साथ) है, जबकि text rule "TrainPlex" है।
    - High-res या vector lockup मिलना बेहतर होगा।
13. **End screen copy:** Reel 02 के end screen का text (headline, chips, CTA) इन files में दर्ज नहीं है। `output/qa/qa_endscreen_*.png` देखकर confirm करें: **अज्ञात / जाँचें**।

---

## 7. Credits used

| Item | Credits |
|---|---|
| शुरुआत में (PRO plan) | 1,050 |
| Video takes: 4 batches x 200 (8 takes, Veo 3.1 - Quality x2) | 800 |
| Images (character, elements, start frames, edits) | 0 (free) |
| बाकी (गणना) | ≈ 250 |

8 takes में से 3 इस्तेमाल हुए। 2 takes (clip 3 की पुरानी script) founder के script बदलने से बेकार हुए। 1 take transcript की वजह से, 1 watermark की वजह से, और 1 face similarity की वजह से reject हुआ।

---

## 8. Git + PR

- Branch: `feat/reel02-college-student`
- Commit और PR: **इस रिपोर्ट के बाद** (pending)
- `flow_raw/` और `clips/takes/*` gitignored हैं। Flow reference PNGs (`flow/character/*.png`, `flow/elements/*.png`) commit होंगी।

PR: https://github.com/cybdeer/trainplex-studio/pull/2 (draft, base develop)
