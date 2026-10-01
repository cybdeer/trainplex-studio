"""QA for one AI-generated video take (vertical talking head, native speech audio).

usage:
  qa_take.py <video.mp4> --clip {1,2,3} [--json out.json]
  qa_take.py --watch <dir> [--minutes 40] [--interval 60]   # QA every new clipN_takeM_720.mp4 lacking .qa.json
  qa_take.py --table                                         # rebuild work/takes_qa.md from clips/takes/*.qa.json

Writes <name>.qa.json and <name>.sheet.jpg next to the video.
The raw transcript is kept in the JSON for reporting only. It is NEVER caption text:
captions always come from work/script.json.

Run with the project interpreter and PYTHONUTF8=1.
"""
import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys
import time
import unicodedata

import cv2
import numpy as np

try:
    from rapidfuzz import fuzz as _fuzz

    def _ratio(a, b):
        return _fuzz.ratio(a, b)
except ImportError:  # pragma: no cover
    import difflib

    def _ratio(a, b):
        return 100.0 * difflib.SequenceMatcher(None, a, b).ratio()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_JSON = os.path.join(ROOT, "work", "script.json")
REF_IMAGE = os.path.join(ROOT, "flow", "character", "char_01_master.png")
TAKES_DIR = os.path.join(ROOT, "clips", "takes")
TABLE_MD = os.path.join(ROOT, "work", "takes_qa.md")

N_FRAMES = 8
FACE_SIM_FLAG = 0.45
EYE_Y_TARGET = 0.35
EYE_Y_TOL = 0.08
MATCH_MIN = 0.85
FUZZ_MIN = 80.0
TAIL_GUARD = 0.15
RESCUE_FUZZ = 55.0
ECHO_MIN_DUR = 0.06   # prompted-pass words shorter than this OR
ECHO_MIN_PROB = 0.30  # less confident than this are treated as prompt echo, not speech

FACE_THRESHOLD_RATIONALE = (
    "Flag when any sampled frame scores below 0.45 cosine (largest face vs flow/character/char_01_master.png, "
    "512-d normed embeddings). Calibration: in Reel 01 the SAME generated presenter scored 0.73 between clips 1 "
    "and 2 but only 0.51-0.54 against clip 3, so generated clips of one person land roughly in 0.5-0.75. "
    "Unrelated faces typically score below ~0.3. 0.45 sits under the observed same-person floor with a small "
    "margin for pose/expression/motion blur, so a flag means 'probably drifted to another face, look at the "
    "sheet', not an automatic reject. ref_calibration lists the master vs the other character sheets for this reel."
)

# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------
# canonical latin form -> spelling variants (Devanagari transliterations and latin forms)
LOAN = {
    "hostel": ["होस्टल", "हॉस्टल", "हॉस्टेल", "होस्टेल", "हास्टल", "हॉस्तल"],
    "pocket": ["पॉकेट", "पोकेट", "पाकेट", "पॉकिट", "पॉकेट्स"],
    "money": ["मनी", "मनि", "मणी", "मानी"],
    "pocketmoney": ["पॉकेटमनी", "पोकेटमनी"],
    "trainplex": ["ट्रेनप्लेक्स", "ट्रेनप्लैक्स", "ट्रेन्प्लेक्स", "ट्रैनप्लेक्स", "ट्रेनप्लेक्श", "ट्रेनप्लेक्‍स",
                  "ट्रेनप्लेक्स़", "trainplex", "trainplexx", "trenplex"],
    "train": ["ट्रेन", "ट्रैन", "ट्रेंन"],
    "plex": ["प्लेक्स", "प्लैक्स", "प्लेक्श", "प्लेक्ष", "प्लेक्‍स", "plax", "plecks"],
    "lecture": ["लेक्चर", "लैक्चर", "लेक्चर्स", "लेक्चरर", "लेकचर"],
    "phone": ["फोन", "फ़ोन", "फौन", "फ़ोन"],
    "voice": ["वॉइस", "वॉयस", "वाइस", "वोइस", "वॉईस", "वायस", "वोईस", "वॉयेस"],
    "record": ["रिकॉर्ड", "रिकोर्ड", "रेकॉर्ड", "रिकार्ड", "रेकोर्ड", "रिकॉड", "रिकॉर्डिंग"],
    "photos": ["फोटोज", "फ़ोटोज", "फोटोस", "फोटो", "फ़ोटो", "फोटोज़", "फ़ोटोज़", "फ़ोटोस", "photo", "fotos"],
    "text": ["टेक्स्ट", "टेक्स", "टैक्स्ट", "टेक्सट", "टेक्स्ट्स", "texts"],
    "check": ["चेक", "चैक", "चेक़", "checks"],
    "ai": ["एआई", "एआइ", "ए.आई.", "ए.आई", "a.i.", "a.i", "एई"],
    "tasks": ["टास्क", "टास्क्स", "टास्कस", "टॉस्क", "टास्क़", "टास्क़्स", "टास्क्स़", "task"],
    "available": ["अवेलेबल", "अवेलबल", "अवैलेबल", "अवेलेबिल", "अवेलबेल", "अवेलेबेल"],
    "bank": ["बैंक", "बेंक", "बँक"],
    "upi": ["यूपीआई", "यूपीआइ", "यू.पी.आई.", "यू.पी.आई", "यूपीई", "u.p.i.", "u.p.i"],
    "learn": ["लर्न", "लर्ण", "लरन", "लर्न्"],
    "more": ["मोर", "मोअर", "मॉर", "मोर्"],
    "learnmore": ["लर्नमोर"],
    "register": ["रजिस्टर", "रेजिस्टर", "रजिस्टार", "रिजिस्टर", "रजिस्ट्र", "रेजिस्टर्ड"],
    "fees": ["फीस", "फ़ीस", "फी", "फ़ी", "fee", "फीज़", "फीज"],
    "training": ["ट्रेनिंग", "ट्रैनिंग", "ट्रेनिंग़", "ट्रेंनिंग"],
    "free": ["फ्री", "फ़्री", "फरी", "फ्रि"],
}
NUMWORDS = {
    "20": ["बीस", "twenty", "बिस"],
    "2": ["दो", "two", "do"],
    "3": ["तीन", "three", "teen"],
    "4": ["चार", "four"],
    "5": ["पाँच", "पांच", "पाच", "five", "पँच"],
    "6": ["छह", "छः", "छे", "छै", "छ", "six", "छेह"],
    "100": ["सौ", "सो", "hundred", "sau"],
    "400": ["चारसौ"],
    "500": ["पाँचसौ", "पांचसौ"],
    "600": ["छहसौ", "छःसौ"],
}

_NUKTA = "़"
_STRIP_CHARS = "‌‍​﻿"
_PUNCT_RE = re.compile(r"[\s\.,!?;:\"'“”‘’()\[\]{}…—–\-|/।॥*₹]+")


def _nfc(s):
    s = unicodedata.normalize("NFD", s)
    s = s.replace(_NUKTA, "")
    for ch in _STRIP_CHARS:
        s = s.replace(ch, "")
    return unicodedata.normalize("NFC", s)


def _key(s):
    """Lookup key: nukta-free, punctuation-free, lowercase."""
    return _PUNCT_RE.sub("", _nfc(s)).lower()


_LOOKUP = {}
for canon, variants in LOAN.items():
    _LOOKUP[_key(canon)] = canon
    for v in variants:
        _LOOKUP[_key(v)] = canon
for canon, variants in NUMWORDS.items():
    _LOOKUP[canon] = canon
    for v in variants:
        _LOOKUP[_key(v)] = canon

# --- tiny Devanagari -> Latin romaniser (lossy on purpose: vowel length, nasalisation, nukta collapsed)
_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
}
_VOW = {
    "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o",
    "औ": "au", "ऑ": "o", "ऍ": "e",
}
_MATRA = {
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
    "ॉ": "o", "ॅ": "e",
}
_VIRAMA = "्"
_NASAL = {"ं": "n", "ँ": "n", "ः": "h"}
_DEVDIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def romanise(word):
    w = _nfc(word).translate(_DEVDIGITS)
    out = []
    i = 0
    n = len(w)
    while i < n:
        ch = w[i]
        if ch in _CONS:
            out.append(_CONS[ch])
            nxt = w[i + 1] if i + 1 < n else ""
            if nxt in _MATRA:
                out.append(_MATRA[nxt])
                i += 2
                continue
            if nxt == _VIRAMA:
                i += 2
                continue
            # inherent vowel, dropped at word end (schwa deletion)
            if i + 1 < n:
                out.append("a")
            i += 1
            continue
        if ch in _VOW:
            out.append(_VOW[ch])
        elif ch in _MATRA:
            out.append(_MATRA[ch])
        elif ch in _NASAL:
            out.append(_NASAL[ch])
        elif ch.isascii():
            out.append(ch.lower())
        i += 1
    return "".join(out)


def canon(raw):
    """Canonical comparison form of one token ('' means drop)."""
    k = _key(raw)
    if not k:
        return ""
    k = k.translate(_DEVDIGITS)
    if k in _LOOKUP:
        return _LOOKUP[k]
    if k.isdigit():
        return str(int(k))
    if re.search(r"[ऀ-ॿ]", k):
        r = romanise(k)
        return _LOOKUP.get(r, r)
    return k


def tokens_eq(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    if a.isdigit() or b.isdigit():
        return False
    if min(len(a), len(b)) <= 2:
        return False
    return _ratio(a, b) >= FUZZ_MIN


def _merge_numbers(toks):
    """['5','100'] -> '500' (keeps raw text and timings)."""
    out = []
    for t in toks:
        if out and t["canon"] == "100" and out[-1]["canon"].isdigit() and int(out[-1]["canon"]) < 10:
            p = out[-1]
            p.update(raw=p["raw"] + " " + t["raw"], canon=str(int(p["canon"]) * 100), end=t.get("end"))
            continue
        out.append(t)
    return out


def script_tokens(line):
    toks = []
    for raw in line.split():
        for piece in re.split(r"[—–\-]+", raw):
            c = canon(piece)
            if c:
                toks.append({"raw": _PUNCT_RE.sub("", piece) or piece, "canon": c})
    return _merge_numbers(toks)


def transcript_tokens(words):
    toks = []
    for w in words:
        for piece in re.split(r"[—–\-/]+", w["word"].strip()):
            c = canon(piece)
            if c:
                toks.append({"raw": piece.strip(), "canon": c, "start": w["start"], "end": w["end"],
                             "prob": w.get("prob")})
    return _merge_numbers(toks)


def align(S, T):
    """Edit-distance alignment with fuzzy equality and 1:2 / 2:1 merges (e.g. TrainPlex = ट्रेन + प्लेक्स)."""
    n, m = len(S), len(T)
    INF = 1e9
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    B = [[None] * (m + 1) for _ in range(n + 1)]
    D[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            best, op = INF, None
            if i and j:
                c = D[i - 1][j - 1] + (0 if tokens_eq(S[i - 1]["canon"], T[j - 1]["canon"]) else 1)
                if c < best:
                    best, op = c, ("m", 1, 1)
            if i and j >= 2:
                merged_raw = canon(T[j - 2]["raw"] + T[j - 1]["raw"])
                merged_can = T[j - 2]["canon"] + T[j - 1]["canon"]
                if tokens_eq(S[i - 1]["canon"], merged_raw) or tokens_eq(S[i - 1]["canon"], merged_can):
                    if D[i - 1][j - 2] < best:
                        best, op = D[i - 1][j - 2], ("m", 1, 2)
            if i >= 2 and j:
                merged = S[i - 2]["canon"] + S[i - 1]["canon"]
                if tokens_eq(merged, T[j - 1]["canon"]):
                    if D[i - 2][j - 1] < best:
                        best, op = D[i - 2][j - 1], ("m", 2, 1)
            if i and D[i - 1][j] + 1 < best:
                best, op = D[i - 1][j] + 1, ("d", 1, 0)
            if j and D[i][j - 1] + 1 < best:
                best, op = D[i][j - 1] + 1, ("i", 0, 1)
            D[i][j], B[i][j] = best, op
    i, j, path = n, m, []
    while i or j:
        op, di, dj = B[i][j]
        si = list(range(i - di, i))
        tj = list(range(j - dj, j))
        if op == "m" and di == 1 and dj == 1 and not tokens_eq(S[i - 1]["canon"], T[j - 1]["canon"]):
            op = "s"
        path.append((op, si, tj))
        i, j = i - di, j - dj
    path.reverse()
    return path


def compare(script_line, words, duration, rescue_from=None):
    S = script_tokens(script_line)
    T = transcript_tokens(words)
    path = align(S, T)
    matched = set()
    windows = {}
    for op, si, tj in path:
        if op == "m":
            matched.update(si)
            for k in si:
                windows[k] = (T[tj[0]]["start"], T[tj[-1]]["end"])

    rescued = []
    if rescue_from:
        # A script word the unprompted pass did not match is accepted from the script-prompted pass only
        # when the unprompted pass heard nothing at that moment, or heard something that looks like a
        # mishearing of it (fuzzy >= RESCUE_FUZZ). A clearly different word (e.g. English "because"
        # for "क्योंकि") is NOT rescued: the prompt makes whisper echo the script.
        for k, (ps, pe) in rescue_from.items():
            if k in matched or k >= len(S):
                continue
            over = [t for t in T if t["start"] < pe + 0.1 and t["end"] > ps - 0.1]
            if not over or any(_ratio(t["canon"], S[k]["canon"]) >= RESCUE_FUZZ for t in over):
                matched.add(k)
                windows[k] = (ps, pe)
                rescued.append(S[k]["raw"])

    missing, wrong, extra = [], [], []
    for op, si, tj in path:
        if op == "s" and not set(si) <= matched:
            wrong.append({"script": " ".join(S[k]["raw"] for k in si), "heard": " ".join(T[k]["raw"] for k in tj),
                          "t": round(T[tj[0]]["start"], 2)})
        elif op == "d" and si[0] not in matched:
            missing.append(S[si[0]]["raw"])
        elif op == "i":
            extra.append(T[tj[0]]["raw"])
    ratio = len(matched) / len(S) if S else 0.0

    t_canons = [t["canon"] for t in T]
    nums = {}
    for idx, s in enumerate(S):
        if s["canon"].isdigit():
            nums[s["raw"] + " (" + s["canon"] + ")"] = s["canon"] in t_canons or idx in matched
    numbers_ok = all(nums.values())

    def _is_tp(x):
        return x == "trainplex" or (len(x) >= 6 and _ratio(x, "trainplex") >= FUZZ_MIN)

    tp = any(_is_tp(c) for c in t_canons)
    for a, b in zip(T, T[1:]):
        if _is_tp(canon(a["raw"] + b["raw"])) or _is_tp(a["canon"] + b["canon"]):
            tp = True
    tp_in_script = any(s["canon"] == "trainplex" for s in S)
    tp = tp or any(S[k]["canon"] == "trainplex" for k in matched)

    starts = [t["start"] for t in T] + [w[0] for w in windows.values()]
    ends = [t["end"] for t in T] + [w[1] for w in windows.values()]
    first_start = min(starts) if starts else None
    last_end = max(ends) if ends else None
    tail_idx = set(range(max(0, len(S) - 2), len(S)))
    heard_at = set(matched)
    for op, si, tj in path:
        if op == "s":
            heard_at.update(si)
    # cut off = nothing at all was heard at the final 2 script positions (a substitution there is a wrong
    # word, reported separately, not a truncation)
    reached_end = bool(heard_at & tail_idx)
    cut_reasons = []
    if last_end is not None and last_end > duration - TAIL_GUARD:
        cut_reasons.append(f"last word ends at {last_end:.2f}s > duration-{TAIL_GUARD}s ({duration - TAIL_GUARD:.2f}s)")
    if not reached_end:
        cut_reasons.append("transcript does not reach the final 2 script words")
    return {
        "script_tokens": [s["raw"] for s in S],
        "heard_tokens": [t["raw"] for t in T],
        "match_ratio": round(ratio, 3),
        "rescued_from_prompted": rescued,
        "match_windows": {int(k): [round(a, 3), round(b, 3)] for k, (a, b) in sorted(windows.items())},
        "missing_words": missing,
        "wrong_words": wrong,
        "extra_words": extra,
        "numbers": nums,
        "numbers_ok": numbers_ok,
        "trainplex_in_script": tp_in_script,
        "trainplex_detected": tp if tp_in_script else None,
        "first_word_start": round(first_start, 3) if first_start is not None else None,
        "last_word_end": round(last_end, 3) if last_end is not None else None,
        "cut_off": bool(cut_reasons),
        "cut_off_reasons": cut_reasons,
    }


# ---------------------------------------------------------------------------
# Media helpers
# ---------------------------------------------------------------------------
def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path])
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    num, den = (v["r_frame_rate"].split("/") if v else ("0", "1"))
    fps = float(num) / float(den) if float(den) else 0.0
    dur = float(d["format"].get("duration", 0))
    res = {
        "width": v["width"] if v else None,
        "height": v["height"] if v else None,
        "fps": round(fps, 3),
        "duration": round(dur, 3),
        "video_codec": v["codec_name"] if v else None,
        "audio_present": a is not None,
        "audio_codec": a["codec_name"] if a else None,
        "audio_sample_rate": int(a["sample_rate"]) if a else None,
        "audio_channels": a.get("channels") if a else None,
    }
    res["resolution_ok"] = (res["width"], res["height"]) in ((720, 1280), (1080, 1920))
    res["fps_ok"] = abs(fps - 24) < 0.05 or abs(fps - 30) < 0.05
    res["duration_ok"] = 7.5 <= dur <= 10.5
    return res


def audio_tail_db(path, duration):
    """RMS dBFS of the final 100 ms (speech still running at the cut reads loud)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                       capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if x.size == 0:
        return None, None
    tail = x[-1600:]
    db = 20 * math.log10(max(1e-9, float(np.sqrt(np.mean(tail ** 2)))))
    full = 20 * math.log10(max(1e-9, float(np.sqrt(np.mean(x ** 2)))))
    return round(db, 1), round(full, 1)


def black_freeze(path, duration):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-an", "-vf",
             "blackdetect=d=0.08:pic_th=0.90:pix_th=0.10,freezedetect=n=-60dB:d=0.4", "-f", "null", "-"])
    log = r.stderr
    blacks = [{"start": float(a), "end": float(b)} for a, b in
              re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)", log)]
    fstarts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    fends = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", log)]
    freezes = []
    for k, s in enumerate(fstarts):
        e = fends[k] if k < len(fends) else duration
        freezes.append({"start": s, "end": e})
    head = 0.5
    tail = duration - 0.5

    def at_head(ev):
        return ev["start"] <= head

    def at_tail(ev):
        return ev["end"] >= tail

    return {
        "black_segments": blacks,
        "freeze_segments": freezes,
        "black_head": any(at_head(e) for e in blacks),
        "black_tail": any(at_tail(e) for e in blacks),
        "freeze_head": any(at_head(e) for e in freezes),
        "freeze_tail": any(at_tail(e) for e in freezes),
    }


# ---------------------------------------------------------------------------
# Models (loaded once per process)
# ---------------------------------------------------------------------------
_WHISPER = None
_FACE = None
_REF = None


def whisper():
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel
        _WHISPER = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)
    return _WHISPER


def face_app():
    global _FACE
    if _FACE is None:
        from insightface.app import FaceAnalysis
        _FACE = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _FACE.prepare(ctx_id=-1, det_size=(640, 640))
    return _FACE


def largest_face(img):
    faces = face_app().get(img)
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def ref_embedding():
    """Master reference embedding + calibration vs the other character sheets (cached on disk)."""
    global _REF
    if _REF is not None:
        return _REF
    f = largest_face(cv2.imread(REF_IMAGE))
    if f is None:
        raise SystemExit(f"no face found in reference {REF_IMAGE}")
    calib = {}
    for p in sorted(glob.glob(os.path.join(os.path.dirname(REF_IMAGE), "char_*.png"))):
        if os.path.abspath(p) == os.path.abspath(REF_IMAGE):
            continue
        img = cv2.imread(p)
        faces = face_app().get(img) if img is not None else []
        # multi-view sheets: take the best-matching face on the sheet
        sims = [float(np.dot(x.normed_embedding, f.normed_embedding)) for x in faces]
        calib[os.path.basename(p)] = round(max(sims), 3) if sims else None
    _REF = (f.normed_embedding, calib)
    return _REF


def transcribe(wav, prompt=None):
    segs, info = whisper().transcribe(wav, language="hi", word_timestamps=True, beam_size=5, vad_filter=False,
                                      initial_prompt=prompt, condition_on_previous_text=False)
    words, text = [], []
    for s in segs:
        text.append(s.text)
        for w in (s.words or []):
            words.append({"word": w.word, "start": round(w.start, 3), "end": round(w.end, 3),
                          "prob": round(w.probability, 3)})
    return " ".join(t.strip() for t in text), words


# ---------------------------------------------------------------------------
# Frames: face similarity, eye/mouth position, contact sheet
# ---------------------------------------------------------------------------
def frames_check(path, out_sheet, duration):
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    ref, calib = ref_embedding()
    idxs = [min(total - 1, int((k + 0.5) * total / N_FRAMES)) for k in range(N_FRAMES)]
    rows, thumbs = [], []
    for fi in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, img = cap.read()
        if not ok:
            rows.append({"frame": fi, "t": round(fi / fps, 2), "face": False})
            continue
        H, W = img.shape[:2]
        f = largest_face(img)
        row = {"frame": fi, "t": round(fi / fps, 2), "face": f is not None}
        vis = img.copy()
        if f is not None:
            sim = float(np.dot(f.normed_embedding, ref))
            k = f.kps
            row.update(sim=round(sim, 3), det_score=round(float(f.det_score), 3),
                       eye_y_frac=round(float((k[0][1] + k[1][1]) / 2 / H), 3),
                       mouth_y_frac=round(float((k[3][1] + k[4][1]) / 2 / H), 3),
                       face_w_frac=round(float((f.bbox[2] - f.bbox[0]) / W), 3))
            x1, y1, x2, y2 = [int(v) for v in f.bbox]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 200, 255), max(2, W // 300))
            for (px, py) in k:
                cv2.circle(vis, (int(px), int(py)), max(3, W // 200), (0, 255, 0), -1)
        tw = 360
        th = int(round(tw * H / W))
        t = cv2.resize(vis, (tw, th), interpolation=cv2.INTER_AREA)
        label = f"{row['t']:.2f}s" + (f"  sim {row['sim']:.2f}" if f is not None else "  NO FACE")
        cv2.rectangle(t, (0, 0), (tw, 30), (0, 0, 0), -1)
        cv2.putText(t, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        thumbs.append(t)
        rows.append(row)
    cap.release()
    if thumbs:
        th = thumbs[0].shape[0]
        thumbs = [cv2.resize(t, (360, th)) for t in thumbs]
        while len(thumbs) % 4:
            thumbs.append(np.zeros_like(thumbs[0]))
        grid = np.vstack([np.hstack(thumbs[r * 4:(r + 1) * 4]) for r in range(len(thumbs) // 4)])
        cv2.imwrite(out_sheet, grid, [cv2.IMWRITE_JPEG_QUALITY, 88])
    sims = [r["sim"] for r in rows if "sim" in r]
    eyes = [r["eye_y_frac"] for r in rows if "eye_y_frac" in r]
    mouths = [r["mouth_y_frac"] for r in rows if "mouth_y_frac" in r]
    faces_found = sum(1 for r in rows if r.get("face"))
    res = {
        "reference": os.path.relpath(REF_IMAGE, ROOT).replace("\\", "/"),
        "frames": rows,
        "faces_found": faces_found,
        "sim_min": round(min(sims), 3) if sims else None,
        "sim_mean": round(float(np.mean(sims)), 3) if sims else None,
        "threshold": FACE_SIM_FLAG,
        "threshold_rationale": FACE_THRESHOLD_RATIONALE,
        "ref_calibration": calib,
        "eye_y_mean": round(float(np.mean(eyes)), 3) if eyes else None,
        "mouth_y_mean": round(float(np.mean(mouths)), 3) if mouths else None,
        "eye_y_target": EYE_Y_TARGET,
        "note": "insightface buffalo_l is licensed for non-commercial research: internal QA signal only, never shipped.",
    }
    res["face_flag"] = (not sims) or faces_found < N_FRAMES or min(sims) < FACE_SIM_FLAG
    res["eye_y_ok"] = res["eye_y_mean"] is not None and abs(res["eye_y_mean"] - EYE_Y_TARGET) <= EYE_Y_TOL
    return res


# ---------------------------------------------------------------------------
# Main QA
# ---------------------------------------------------------------------------
def load_script(clip):
    with open(SCRIPT_JSON, encoding="utf-8") as fh:
        return json.load(fh)["clips"][f"clip{clip}"]


def qa(video, clip, json_out=None, quiet=False):
    t0 = time.time()
    video = os.path.abspath(video)
    stem = os.path.splitext(video)[0]
    line = load_script(clip)
    pr = probe(video)
    dur = pr["duration"]

    wav = stem + ".16k.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-ac", "1", "-ar", "16000", wav], check=True)
    try:
        text_a, words_a = transcribe(wav)
        text_b, words_b = transcribe(wav, prompt=line)
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass
    def _ok(c):
        return (c["match_ratio"] >= MATCH_MIN and c["numbers_ok"]
                and (clip != 1 or bool(c["trainplex_detected"])) and not c["cut_off"])

    echo = [w for w in words_b if (w["end"] - w["start"]) < ECHO_MIN_DUR or w["prob"] < ECHO_MIN_PROB]
    words_b_rel = [w for w in words_b if w not in echo]
    passes = {}
    for name, text, words in (("unprompted", text_a, words_a), ("prompted", text_b, words_b_rel)):
        c = compare(line, words, dur)
        c["transcript_ok"] = _ok(c)
        c["raw_text"] = text
        c["raw_words"] = words_a if name == "unprompted" else words_b
        passes[name] = c
    passes["prompted"]["suspect_prompt_echo_words"] = echo
    # verdict pass: unprompted transcript, with words rescued from the prompted pass only where plausible
    rescue = {int(k): tuple(v) for k, v in passes["prompted"]["match_windows"].items()}
    tr = compare(line, words_a, dur, rescue_from=rescue)
    tr["transcript_ok"] = _ok(tr)
    tail_db, full_db = audio_tail_db(video, dur)

    transcript = {
        "script_line": line,
        "used_pass": "unprompted + plausible rescues from prompted",
        "transcript_ok": tr["transcript_ok"],
        "transcript_ok_unprompted": passes["unprompted"]["transcript_ok"],
        "prompt_dependent": tr["transcript_ok"] and not passes["unprompted"]["transcript_ok"],
        "rescued_from_prompted": tr["rescued_from_prompted"],
        "prompt_echo_words_dropped": [w["word"].strip() for w in echo],
        "match_ratio": tr["match_ratio"],
        "missing_words": tr["missing_words"],
        "wrong_words": tr["wrong_words"],
        "extra_words": tr["extra_words"],
        "numbers": tr["numbers"],
        "numbers_ok": tr["numbers_ok"],
        "trainplex_detected": tr["trainplex_detected"],
        "first_word_start": tr["first_word_start"],
        "last_word_end": tr["last_word_end"],
        "cut_off": tr["cut_off"],
        "cut_off_reasons": tr["cut_off_reasons"],
        "audio_tail_100ms_dbfs": tail_db,
        "audio_mean_dbfs": full_db,
        "passes": passes,
        "note": "Raw whisper text is for QA reporting only. Captions always use the exact script from work/script.json.",
    }
    sheet = stem + ".sheet.jpg"
    face = frames_check(video, sheet, dur)
    bf = black_freeze(video, dur)

    problems = []
    if not pr["audio_present"]:
        problems.append("no audio")
    if not pr["resolution_ok"]:
        problems.append(f"resolution {pr['width']}x{pr['height']}")
    if not pr["fps_ok"]:
        problems.append(f"fps {pr['fps']}")
    if not transcript["transcript_ok"]:
        problems.append("transcript")
    review = []
    if transcript["prompt_dependent"]:
        review.append("transcript passes only with script prompt (listen)")
    if face["face_flag"]:
        review.append("face similarity / detection")
    if not face["eye_y_ok"]:
        review.append(f"eye_y {face['eye_y_mean']}")
    if bf["black_head"] or bf["black_tail"]:
        review.append("black frames at head/tail")
    if bf["freeze_head"] or bf["freeze_tail"]:
        review.append("frozen frames at head/tail")
    if not pr["duration_ok"]:
        review.append(f"duration {dur}s")
    verdict = "FAIL" if problems else ("REVIEW" if review else "PASS")

    m = re.search(r"clip(\d)_take(\d+)", os.path.basename(video))
    result = {
        "video": os.path.relpath(video, ROOT).replace("\\", "/"),
        "clip": clip,
        "take": int(m.group(2)) if m else None,
        "probe": pr,
        "transcript": transcript,
        "face": face,
        "black_freeze": bf,
        "contact_sheet": os.path.relpath(sheet, ROOT).replace("\\", "/"),
        "verdict": verdict,
        "fail_reasons": problems,
        "review_reasons": review,
        "qa_seconds": round(time.time() - t0, 1),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    outs = [stem + ".qa.json"] + ([json_out] if json_out else [])
    for o in outs:
        with open(o, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
    if not quiet:
        print_summary(result)
    return result


def print_summary(r):
    p, t, f, b = r["probe"], r["transcript"], r["face"], r["black_freeze"]
    print(f"\n=== {r['video']}  (clip {r['clip']}, take {r['take']})  VERDICT: {r['verdict']}")
    print(f"probe      : {p['width']}x{p['height']} @ {p['fps']} fps, {p['duration']} s, audio={p['audio_present']}")
    print(f"script     : {t['script_line']}")
    for k in ("unprompted", "prompted"):
        ps = t["passes"][k]
        print(f"heard[{k[:5]}]: {ps['raw_text']}   (ratio {ps['match_ratio']}, ok={ps['transcript_ok']})")
    print(f"transcript : ok={t['transcript_ok']} (pass={t['used_pass']}) ratio={t['match_ratio']} "
          f"numbers={t['numbers']} trainplex={t['trainplex_detected']}")
    print(f"             missing={t['missing_words']} wrong={[(w['script'], w['heard']) for w in t['wrong_words']]}")
    print(f"timing     : first {t['first_word_start']} s, last {t['last_word_end']} s, cut_off={t['cut_off']} "
          f"{t['cut_off_reasons']} tail100ms={t['audio_tail_100ms_dbfs']} dBFS")
    print(f"face       : sim min {f['sim_min']} mean {f['sim_mean']} (flag<{f['threshold']}: {f['face_flag']}), "
          f"faces {f['faces_found']}/{N_FRAMES}, eye_y {f['eye_y_mean']} mouth_y {f['mouth_y_mean']}")
    print(f"black/frz  : head black={b['black_head']} tail black={b['black_tail']} head freeze={b['freeze_head']} "
          f"tail freeze={b['freeze_tail']}")
    print(f"sheet      : {r['contact_sheet']}")
    if r["fail_reasons"] or r["review_reasons"]:
        print(f"reasons    : fail={r['fail_reasons']} review={r['review_reasons']}")


# ---------------------------------------------------------------------------
# Table + watch
# ---------------------------------------------------------------------------
TAKE_RE = re.compile(r"^clip([123])_take(\d+)_720\.mp4$")


def build_table():
    rows = []
    for j in glob.glob(os.path.join(TAKES_DIR, "clip*_take*_720.qa.json")):
        with open(j, encoding="utf-8") as fh:
            rows.append(json.load(fh))
    rows.sort(key=lambda r: (r["clip"], r["take"] or 0))
    L = ["# Reel 02 takes QA", "",
         f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `work/qa_take.py`. Transcript columns use the unprompted whisper pass; "
         "a word is taken from the script-prompted pass only where the unprompted pass heard nothing or a "
         "near-spelling there (`*` = passes only thanks to such rescues). Prompted-pass words with ~0 s duration "
         "or prob < 0.30 are treated as prompt echo and ignored. "
         f"Face sim = insightface cosine vs `flow/character/char_01_master.png`, flag < {FACE_SIM_FLAG}. "
         f"eye_y target ~{EYE_Y_TARGET}.", "",
         "| clip | take | transcript_ok | match | missing / wrong words | numbers ok | TrainPlex ok | cut off | "
         "face sim min / mean | eye_y | verdict |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        t, f = r["transcript"], r["face"]
        mw = (list(t["missing_words"]) + [f"{w['script']}→{w['heard']}" for w in t["wrong_words"]]
              + [f"+{w}" for w in t["extra_words"]])
        tp = "n/a" if t["trainplex_detected"] is None else ("yes" if t["trainplex_detected"] else "NO")
        reasons = r["fail_reasons"] + r["review_reasons"]
        verdict = r["verdict"] + (f" ({'; '.join(reasons)})" if reasons else "")
        L.append(
            f"| {r['clip']} | {r['take']} | {'yes' if t['transcript_ok'] else 'NO'}{'*' if t['prompt_dependent'] else ''}"
            f" | {t['match_ratio']:.2f} | {', '.join(mw) if mw else '-'} | {'yes' if t['numbers_ok'] else 'NO'} | {tp}"
            f" | {'YES' if t['cut_off'] else 'no'} | {f['sim_min']} / {f['sim_mean']} | {f['eye_y_mean']} | {verdict} |")
    with open(TABLE_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return "\n".join(L)


def pending(d):
    out = []
    for p in sorted(os.listdir(d)):
        m = TAKE_RE.match(p)
        if not m:
            continue
        full = os.path.join(d, p)
        if os.path.exists(os.path.splitext(full)[0] + ".qa.json"):
            continue
        out.append((full, int(m.group(1))))
    return out


def stable(path, wait=3.0):
    """True when the file size is unchanged over `wait` seconds (download finished)."""
    try:
        a = os.path.getsize(path)
        time.sleep(wait)
        return a > 0 and a == os.path.getsize(path)
    except OSError:
        return False


def watch(d, minutes, interval):
    end = time.time() + minutes * 60
    print(f"watching {d} for {minutes} min (every {interval}s)", flush=True)
    while True:
        for path, clip in pending(d):
            if not stable(path):
                continue
            try:
                qa(path, clip)
            except Exception as e:  # keep watching even if one take is broken
                print(f"QA ERROR {path}: {e!r}", flush=True)
                with open(os.path.splitext(path)[0] + ".qa.error.txt", "w", encoding="utf-8") as fh:
                    fh.write(repr(e))
                continue
            build_table()
            sys.stdout.flush()
        if time.time() >= end:
            break
        time.sleep(interval)
    print(build_table())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--clip", type=int, choices=(1, 2, 3))
    ap.add_argument("--json")
    ap.add_argument("--watch")
    ap.add_argument("--minutes", type=float, default=40)
    ap.add_argument("--interval", type=float, default=60)
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()
    if a.watch:
        watch(a.watch, a.minutes, a.interval)
    elif a.table:
        print(build_table())
    else:
        if not a.video or not a.clip:
            ap.error("video and --clip are required")
        qa(a.video, a.clip, a.json)
        build_table()


if __name__ == "__main__":
    main()
