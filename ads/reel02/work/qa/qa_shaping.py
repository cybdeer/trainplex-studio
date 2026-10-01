#!/usr/bin/env python3
"""QA (Agent 13) — check 1 (machine part): shape every rendered Devanagari string with HarfBuzz using the
exact self-hosted woff2 subsets (fonts/noto-sans-devanagari-devanagari-<w>-normal.woff2) and report
.notdef (tofu), dotted-circle (U+25CC, broken cluster) glyphs and cmap gaps.
Needs fontTools + brotli + uharfbuzz (installed to a scratch dir; pass it via PYTHONPATH).
Output: work/qa/parts/shaping.json
"""
import io
import json
import os
import re

import uharfbuzz as hb
from fontTools.ttLib import TTFont

QA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(QA))
FONTS = os.path.join(ROOT, "remotion", "public", "fonts")

caps = json.load(open(os.path.join(ROOT, "work", "captions.json")))
STRINGS = {  # string -> weights it is rendered in
    **{w["word"]: [900] for w in caps},
    "बंद कर!": [900],                                   # clip 1 slab
    "PHONE से": [900],                                  # clip 2 badge
    "4 घंटे में तक*": [700],                            # clip 3 plate sub-line
    "*कमाई task availability और approval पर निर्भर है": [600],  # disclaimer
    "AI TRAINER बनें": [900],                           # end screen headline
    "घर बैठे · Phone से · Paid tasks": [700],           # end screen sub-line
}
DEVA = re.compile(r"[ऀ-ॿ₹◌]+")


def woff2_to_ttf_bytes(path):
    f = TTFont(path)
    f.flavor = None
    b = io.BytesIO()
    f.save(b)
    return b.getvalue(), f


out = {"strings": [], "fonts": {}}
fonts = {}
for w in (600, 700, 800, 900):
    p = os.path.join(FONTS, f"noto-sans-devanagari-devanagari-{w}-normal.woff2")
    data, tt = woff2_to_ttf_bytes(p)
    cmap = tt.getBestCmap()
    face = hb.Face(data)
    font = hb.Font(face)
    dotted = tt.getGlyphID(cmap[0x25CC]) if 0x25CC in cmap else None
    fonts[w] = (font, cmap, dotted, tt)
    out["fonts"][w] = {"file": os.path.basename(p), "glyphs": len(tt.getGlyphOrder()), "has_25CC": 0x25CC in cmap,
                       "has_20B9": 0x20B9 in cmap}

problems = 0
for s, weights in STRINGS.items():
    for w in weights:
        font, cmap, dotted, tt = fonts[w]
        for run in DEVA.findall(s):  # only the Devanagari runs go to Noto (unicode-range)
            missing = [f"U+{ord(ch):04X}" for ch in run if ord(ch) not in cmap]
            buf = hb.Buffer()
            buf.add_str(run)
            buf.guess_segment_properties()
            hb.shape(font, buf, {})
            gids = [i.codepoint for i in buf.glyph_infos]
            names = [tt.getGlyphName(g) for g in gids]
            notdef = gids.count(0)
            dc = sum(1 for g in gids if dotted is not None and g == dotted and "◌" not in run)
            ok = not missing and notdef == 0 and dc == 0
            problems += (not ok)
            out["strings"].append({"text": s, "run": run, "weight": w, "script": str(buf.script), "glyphs": names,
                                   "missing_codepoints": missing, "notdef": notdef, "dotted_circles": dc, "ok": ok})

# Inter: every Latin char used (incl. ₹ via latin-ext) must be covered by one of the Inter subsets
inter = {}
for w in (600, 700, 800, 900):
    cm = {}
    for sub in ("latin", "latin-ext"):
        cm.update(TTFont(os.path.join(FONTS, f"inter-{sub}-{w}-normal.woff2")).getBestCmap())
    inter[w] = cm
latin_chars = set("".join(STRINGS)) - set("".join(DEVA.findall("".join(STRINGS))))
latin_chars |= set("SCROLL4HRS₹0123456789–AI TRAINER TASKSVoiceRecordingPhotoCollectionTextAnnotationPHONEसFEESFREETRAININGBANK/UPIREGISTRATIONPAYMENTRegisterfree→trainplex.info/registerLearnmore")
latin_chars = {c for c in latin_chars if not ("ऀ" <= c <= "ॿ")}
out["inter_missing"] = {w: sorted(f"U+{ord(c):04X} {c}" for c in latin_chars if ord(c) not in cm and c.strip()) for w, cm in inter.items()}
out["problem_count"] = problems
json.dump(out, open(os.path.join(QA, "parts", "shaping.json"), "w"), ensure_ascii=False, indent=1)
print("strings shaped:", len(out["strings"]), "problems:", problems)
print("inter missing:", out["inter_missing"])
print(json.dumps(out["fonts"], indent=1))
for r in out["strings"]:
    if not r["ok"]:
        print("PROBLEM", r)
