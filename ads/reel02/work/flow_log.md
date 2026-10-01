# Google Flow log — Reel 02

Project: "TrainPlex Reel 02" (flow.google.com/project/79517316-0202-4bc1-9e0e-ad224f854d8e)
Account: PRO plan, 1,050 credits at start. Agent settings: confirm-before-generating = Always; image 9:16, Nano Banana Pro (highest of Pro / 2 / 2 Lite); video 9:16, Veo 3.1 - Quality (highest of Omni 1.1 Flash / Veo 3.1 Lite / Fast / Quality), x2.
Downloads: 2K upscaled (4K requires paid upgrade -> not used). Flow exports JPG; converted losslessly to PNG.
Visible watermark: Flow account setting "Visible watermarking is required in your region" (locked ON) -> small sparkle mark bottom-right of every image.

## Stage 1 — Character sheet

| File | Source | Notes |
|---|---|---|
| char_01_master.png | master prompt (spec, verbatim) -> re-framed head-and-shoulders -> edit fix | v1 rejected: silver jhumka earrings (bible = small studs), skin lighter than medium-brown. v2 = edit "replace jhumkas with small plain silver studs; natural medium-brown complexion" |
| char_02_fullbody.png | edit of master v2 | full body front, white sneakers, navy sling bag |
| char_03_threequarter_left.png | horizontal MIRROR of char_04 | Flow refused to turn her the other way in 2 attempts (always nose-to-frame-right). Deviation: local mirror; watermark sparkle appears bottom-left |
| char_04_threequarter_right.png | edit of master v2 | |
| char_05_profile_left.png | horizontal MIRROR of Flow profile | same reason as char_03 |
| char_06_expressions.png | edit of master v2 | 2x2: talking, laughing, surprised, confident |

Rejected (ads/reel02/flow/character/_src/rejected/): master_v1_jhumka_lightskin, fullbody_v1_jhumka, threequarter_v1_jhumka. Also rejected in-Flow (not downloaded): initial 2 medium shots (waist-up, not head-and-shoulders), 1 failed "mirror pose" edit.

Prompts used (beyond master spec prompt):
- Re-frame: "Using the first image ... as the identity reference ... tight HEAD-AND-SHOULDERS close-up, front view ..."
- Fix: "Keep this exact image ... Only two changes: (1) replace the dangling jhumka earrings with SMALL PLAIN SILVER STUD earrings ... (2) skin tone a natural medium-brown Indian complexion ..."
- Full body / 3-4 / profile / expressions: "Same person, identical face, medium-brown skin, small silver stud earrings, loose ponytail ... Re-frame as FULL BODY | THREE-QUARTER view | full 90-degree SIDE PROFILE | CHARACTER EXPRESSION SHEET 2x2 ..."

## Stage 2 — Element sheet (all Nano Banana Pro, 2 variations each, 2K download)

| File | Chosen | Rejected + reason |
|---|---|---|
| el_01_hostel_room.png | variation 2 (warmer golden window light, fairy lights) | variation 1: flatter light, less late-afternoon mood. Note: one tiny sticky note on desk has an illegible scribble (background, not readable) |
| el_02_canteen_corridor.png | variation 1 (busy corridor, notice boards, canteen counter, distant students) | variation 2: emptier, signage board top-right risked readable text |
| el_03_campus_steps.png | variation 2 (sun flare through trees, sandstone arches) | variation 1: less golden-hour |
| el_04_props.png | variation 2 + edit "remove ALL writing and labels from the notebooks" | variation 1: bag had brown leather strap (character bag strap is navy fabric). v2 unedited: notebooks had garbled "COLLEGE NOTEBOOG" text -> _src/rejected/props_v1_text_on_notebooks.jpg |

Prompts: each began "New image, NOT based on any previous image, no people ... Photorealistic empty location plate ..." with the §5 Stage 2 description, plus "warm, friendly, youthful colour mood, eye-level smartphone camera perspective, clear space in the foreground for a person. Vertical 9:16. No text, no logos, no watermark."

## Stage 3 — Video clips (Veo 3.1 - Quality, 9:16, 8 s, native speech, 720p original)

Mode deviation: Flow's Ingredients-to-video (character + location references) is only available on Omni 1.1 Flash / Veo 3.1 Lite; Veo 3.1 - Quality rejects reference images. To keep the HIGHEST-quality model AND identity lock, each clip used a two-step "equivalent reference mode":
1. Start frame: Nano Banana Pro image with ingredients = Flow character "Priya" (portrait = char_01_master.png, saved custom voice "Priya voice" based on Autonoe) + the matching element plate (el_01/el_02/el_03), 2 variations, best framing chosen (eyes ~32-42% from top, phone visible).
2. Veo 3.1 - Quality frames-to-video from that start frame with the §5 prompt template + exact line. (The character's saved voice cannot be attached in Quality mode; voice consistency comes from the prompt "a young Indian woman's voice".) el_04_props was not attached (would have injected tiffin/notebooks into frame); the phone/bag were already locked by the character.
Credits: 4 batches x 200 = 800 of 1,050 used (images cost 0).

| Clip | Take | Flow id | Verdict | Reason |
|---|---|---|---|---|
| 1 | take1 | 2193535b | REJECT | last clause spoken in English ("because I work on TrainPlex") -> transcript 0.74; extra hand enters frame at 3.5 s / 6.5 s |
| 1 | take2 | b6b6015c | KEEP -> clips/clip1.mp4 | transcript 1.00, बीस+TrainPlex ok, face sim mean 0.67 |
| 2 | take1 | ffd3ceca | KEEP -> clips/clip2.mp4 | transcript 1.00, face 0.67, no artefacts |
| 2 | take2 | 29e5b7ae | REJECT | large Flow sparkle watermark burnt in for whole clip (from start frame); transcript 0.95 |
| 3 (old script) | take1 | 2fb696f1 | REJECT | founder changed Clip 3 script after generation; also phone disappears after 1.5 s |
| 3 (old script) | take2 | 0cf944f6 | REJECT | founder changed Clip 3 script after generation |
| 3 | take1 | 5d3d0216 | REJECT | face similarity min 0.447 (< 0.45 flag) |
| 3 | take2 | 9bf25b6e | KEEP -> clips/clip3.mp4 | transcript 1.00, numbers दो/तीन/चार सौ/पाँच सौ ok, phone held whole clip, face 0.64 |

Founder script change (1 Oct 2026, mid-run): Clip 3 changed from "Tasks available हों तो चार घंटे में पाँच सौ से छह सौ तक, ..." to "मैं दिन में दो-तीन घंटे काम करती हूँ और चार सौ से पाँच सौ कमा लेती हूँ, सीधे Bank या UPI में। नीचे Learn more दबाओ और अभी register करो!"; earnings plate -> "₹400–500 / 2–3 घंटे*"; highlight -> "चार सौ से पाँच सौ".

Resolution: Flow offers 720p original / 1080p "Upscaled" / 4K (paid upgrade - not used). 1080p upscale downloads were unreliable in the UI (menu froze; only clip 3's arrived: clips/takes/clip3_take2_1080.mp4, archived). For a consistent look across clips, all three edit sources are the 720p originals, Lanczos-upscaled to 1080x1920 in normalise.py (spec-permitted path).
Downloads: Chrome blocked "multiple automatic downloads" for flow.google.com after 2 files; founder enabled it.

## Stage 4 — Merge in Flow Scenebuilder
Scene "TrainPlex Reel 02 - Flow merge" (flow.google.com/project/79517316-.../scene/24d51882-2250-4743-90a5-3a4a73a29684): clip1 take2 -> clip2 take1 -> clip3 take2; tails trimmed to match work/flow_merge_trims.json (7.833 / 7.733 / 7.800 s; Scenebuilder total 23.33 s vs edit 23.37 s, within 1 frame at 24 fps). No head trims needed (speech starts at 0.0-0.1 s). Exported to flow_raw/flow_merged.mp4.

Scene export result: flow_raw/flow_merged.mp4 = 720x1280, 24 fps, 23.41 s (Scenebuilder export offered only this; file is gitignored, kept locally as timing reference/backup cut).
