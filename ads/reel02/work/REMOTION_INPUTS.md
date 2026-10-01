# Reel 02 — Remotion inputs (contract between the pipeline and `remotion/`)

The Remotion project reads three data files plus the script. **All three currently hold PLACEHOLDER
data** (written by the remotion agent so the project compiles and previews render). While any of them
is a placeholder, every render carries a navy "PLACEHOLDER DATA — NOT FOR DELIVERY" strip at y 1850
and the bundle logs a warning. The strip disappears by itself once real files are copied in.

```powershell
Copy-Item work\captions.json, work\edit.json, work\face_boxes.json remotion\src\data\ -Force
Copy-Item work\norm\clip*.mp4 remotion\public\clips\ -Force     # clip1.mp4 clip2.mp4 clip3.mp4
cd remotion; npx tsc --noEmit; npx remotion compositions src/index.ts
```

Placeholder markers (remove them, i.e. just overwrite the files with the pipeline output):
`edit.json` → `"placeholder": true`; `captions.json` → `"placeholder": true` on every word;
`face_boxes.json` → top-level `"_placeholder"` key.

---

## 1. `work/script.json` (read directly by `remotion/src/timeline.ts`)
Unchanged schema: `{"clips": {"clip1": str, "clip2": str, "clip3": str}, "highlight_phrases": [str]}`.
The bundle **throws** if the words of `captions.json` for a clip, joined with single spaces, are not
exactly the script string for that clip (whitespace-normalised), or if any highlight phrase is missing
or any of its words is not flagged `highlight: true`.

## 2. `remotion/src/data/edit.json` (from `normalise.py`, same schema as Reel 01)
```json
{
  "fps": 30,
  "end_screen_frames": 105,          // OPTIONAL (new). 90–120 = 3.0–4.0 s
  "clips": [
    {"clip": 1, "src": "clips/clip1.mp4", "trim_start": 0.0, "frames": 228, "note": "...",
     "trim_end": 7.6, "duration": 7.6,
     "probe": {"width": 1080, "height": 1920, "r_frame_rate": "30/1", "nb_read_frames": "228"}}
  ]
}
```
Only `fps` (must be 30 if present), `clips[].clip`, `clips[].frames` (int > 0) and the optional
`end_screen_frames` are read.

**End-screen length** is a timeline parameter: legal range = `[max(90, 750 − clipsTotal), min(120, 900 − clipsTotal)]`
frames (3.0–4.0 s, reel total 25.0–30.0 s). If `end_screen_frames` is given it must be in that range;
if absent, 105 (3.5 s) is used, clamped into the range. The bundle throws if no legal value exists
(clips total < 21.0 s or > 27.0 s).

## 3. `remotion/src/data/captions.json` (from `align_captions.py`, same schema as Reel 01)
```json
[{"word": "Hostel", "start": 0.15, "end": 0.55, "clip": 1, "highlight": false, "chunk": 0}, ...]
```
- `word`: exact script spelling incl. trailing punctuation. A stand-alone dash is attached to the
  previous word with a space (`"पूछो —"`, `"से —"`), as in Reel 01.
- `start`/`end`: seconds relative to the TRIMMED clip. `chunk`: caption chunk index (2–4 words).
- `highlight`: true for every word of `script.json` `highlight_phrases`.
- Chunking note: the face-safe lower band for graphics ends at y 1272, which assumes ONE-line caption
  chunks while lower-band graphics are up (chunk block bottom 1400). Keep these chunks short enough
  to stay on one line (≈ ≤ 900 px at 78–92 px, highlights ×1.15): clip 1 "pocket money", clip 2
  "voice record," / "photos, text check।" / "कोई fees नहीं," / "training भी free।", clip 3 the
  "चार सौ से पाँच सौ" / "कमा लेती हूँ," / "सीधे Bank या UPI में।" / "नीचे Learn more दबाओ" chunks. A 2-line
  chunk still renders (captions sit above graphics) but overlaps the graphic's lower edge.

## 4. `remotion/src/data/face_boxes.json` (from `face_track.py`, same schema as Reel 01)
```json
{"1": {"frames": 228, "detections": 76,
       "union_face_box": {"x1":..,"y1":..,"x2":..,"y2":..},
       "eyes_band_union": {"y1":..,"y2":..}, "mouth_band_union": {"y1":..,"y2":..},
       "boxes": [{"frame": 0, "x": 360, "y": 368, "w": 554, "h": 554}, ...]},
 "2": {...}, "3": {...}}
```
Only `boxes` is read (local frame of the trimmed/normalised clip, 1080x1920 px, every 3rd frame).
Placeholder clip lengths: 7.6 / 7.6 / 8.6 s (clip 3 lengthened for the longer founder-approved
line). The current placeholder is a real Haar track of the stand-in take `clips/takes/clip1_take1_720.mp4`
(same detector/params as `face_track.py`), reused for all three clips.

## 5. Phrase → cue map (all frames derived by `findPhrase` on the exact script; bundle throws if a phrase is missing)
| Clip | Phrase | Cue |
|---|---|---|
| 1 | (frame 0) | hook slab "POCKET MONEY खत्म?" sweeps in |
| 1 | `pocket money` | slab "POCKET MONEY" pop |
| 1 | `खत्म` | slab "खत्म?" punch |
| 1 | `बीस तारीख` | slab out (just before), calendar card in (start − 2 f); circle draws over `बीस`; strike from end of `बीस तारीख` to end of `तक` |
| 1 | `क्योंकि` | calendar card out |
| 1 | `TrainPlex` | logo plate pops, holds to clip end; watermark ducks from here |
| 2 | `Lecture के बाद` | tag "Lecture के बाद • Phone से" in |
| 2 | `phone से` | tag's "Phone से" turns orange + Smartphone icon |
| 2 | `voice record` / `photos` / `text check` | tiles Mic "Voice record" / Camera "Photos" / CheckSquare "Text check" |
| 2 | `AI` | tag out |
| 2 | `कोई fees नहीं` | "₹0 FEES" badge (tiles clear just before) |
| 2 | `training भी free` | "FREE TRAINING" badge; both badges entered ≤ clip end − 36 f (≥ 1.2 s on screen, pulled earlier only if the clip ends too soon) |
| 3 | `दो-तीन घंटे` | earnings plate "₹400–500 / 2–3 घंटे*" opens (shows "/ 2–3 घंटे*"); disclaimer fully in before it |
| 3 | `चार सौ से पाँच सौ` | ₹ figure appears (start − 2 f), ₹0→400 over `चार सौ`, "–500" unrolls from `से` and counts to 500 through `पाँच सौ` |
| 3 | `कमा लेती हूँ` | figure lands (pop) + 8 % video punch-in (origin on the chin line) |
| 3 | `सीधे` | plate out, punch-in released, Bank / UPI card in |
| 3 | `Bank`, `UPI` | underlines; tick at end of `UPI` |
| 3 | `नीचे` | card out (−3 f), "Learn more" + down-arrow in |
| 3 | `Learn more` | arrow bounces ×3 |
| 3 | `register` | "Learn more" pulse |
| 3 | — | disclaimer held to the last clip-3 frame |

Positions: every clip graphic is placed by `remotion/src/layout/faceSafe.ts` against the face boxes
(through the clip-3 punch-in) for exactly the frames it is on screen. Zones in order: top band above
the face / beside it, or the lower band (face bottom … y 1272). It stays clear of the whole Haar
box + 14 px; it shrinks (to a per-graphic minimum) before moving; as a last resort it only protects
the eyes/mouth rects; otherwise the bundle throws.

## 6. Preview stills without real clips
`public/clips/_preview_standin_take.mp4` (gitignored) is a copy of the stand-in take. From `remotion/`:
`node .render_stills.mjs '[["Clip1",118,"name.png"]]'` renders stills into `work/preview_stills/` with
`--props {"standIn": ...}`. The delivery render never sets `standIn`. Add `DEBUG_FACE=1` to overlay
the face / eyes / mouth boxes.
