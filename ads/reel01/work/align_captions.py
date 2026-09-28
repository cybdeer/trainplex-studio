"""STEP 3 — align the EXACT script to faster-whisper word timings.

Whisper is used ONLY for timing. Each script token is mapped to one or more whisper words by
sequence (ordered spans below); a whisper word that covers two script words (e.g. "500" ->
"पाँच सौ") is split proportionally to character length. Word starts that absorbed a pause are
tightened with a 10 ms RMS onset search. Output times are relative to the TRIMMED clip.
"""
import json, os, wave
import numpy as np
from difflib import SequenceMatcher

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
edit = {c["clip"]: c for c in json.load(open(os.path.join(root, "work", "edit.json")))["clips"]}

# Exact script, pre-chunked ("|" = caption chunk break, 2-4 words, breaks at punctuation).
SCRIPT = {
    1: "भाई, scroll | करना बंद कर! | रोज़ चार घंटे | reels देखता है — | बदले में मिला क्या? | Zero! | वही चार घंटे | TrainPlex पे दे।",
    2: "AI कंपनियों के | छोटे-छोटे tasks — | voice record कर, | photos खींच, | text check कर। | सब phone से, | कोई fees नहीं, | training भी free।",
    3: "Tasks available हों तो | चार घंटे में | पाँच सौ से | छह सौ तक। | पैसा सीधे Bank | या UPI में। | तो नीचे | Learn more दबा | और अभी | register कर!",
}
# Whisper-word span for each script token, in order. (n) = consume n whisper words;
# ("split", k, parts) = this token is part k of a whisper word shared by `parts` tokens.
SPANS = {
    1: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1],       # TrainPlex = ट्रेन+प्लेक्स
    2: [1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],       # छोटे-छोटे = छोटे+छोटे
    3: [1, 1, 1, 1, 1, 1, 1, ("split", 0, 2), ("split", 1, 2), 1, ("split", 0, 2), ("split", 1, 2),
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],                          # 500 / 600 split
}
HIGHLIGHT_PHRASES = ["scroll", "बंद कर", "चार घंटे", "Zero", "TrainPlex", "tasks", "voice record", "photos",
                     "text", "fees नहीं", "free", "पाँच सौ से छह सौ", "Bank", "UPI", "Learn more", "register"]
PUNCT = ",!?।—"

def strip_p(w):
    return w.strip().strip(PUNCT).strip()

def rms_env(clip):
    w = wave.open(os.path.join(root, "work", "transcripts", f"clip{clip}_16k.wav"))
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    hop = 160
    return np.array([20 * np.log10(np.sqrt(np.mean(x[k:k + hop] ** 2)) + 1e-9) for k in range(0, len(x) - hop + 1, hop)])

out, report = [], []
for clip in (1, 2, 3):
    raw = json.load(open(os.path.join(root, "work", "transcripts", f"clip{clip}_raw.json")))
    ww = [w for s in raw["segments"] for w in s["words"]]
    chunks = [c.strip().split() for c in SCRIPT[clip].split("|")]
    # the em dash is punctuation that belongs to the previous word
    toks = []
    for ci, ch in enumerate(chunks):
        for t in ch:
            if t == "—" and toks:
                toks[-1] = (toks[-1][0] + " —", toks[-1][1])
            else:
                toks.append((t, ci))
    assert len(toks) == len(SPANS[clip]), (clip, len(toks), len(SPANS[clip]))
    env = rms_env(clip)
    i = 0
    for (tok, ci), span in zip(toks, SPANS[clip]):
        if isinstance(span, tuple):
            _, k, parts = span
            w = ww[i]
            s, e = w["start"], w["end"]
            seg = (e - s) / parts
            start, end = s + k * seg, s + (k + 1) * seg
            src_words = w["word"].strip()
            if k == parts - 1:
                i += 1
        else:
            grp = ww[i:i + span]
            start, end = grp[0]["start"], grp[-1]["end"]
            src_words = " ".join(g["word"].strip() for g in grp)
            i += span
        # tighten a start that swallowed a pause: if the whisper window contains a run of
        # >= 100 ms below -35 dBFS, the word really starts at the end of the last such run
        a, b = int(round(start * 100)), max(int(round(start * 100)) + 1, int(round(end * 100)))
        quiet = env[a:b] < -35
        run, last_run_end = 0, None
        for k, q in enumerate(quiet):
            run = run + 1 if q else 0
            if run >= 10 and (k + 1 >= len(quiet) or not quiet[k + 1]):
                last_run_end = k + 1
        if last_run_end is not None and (a + last_run_end) / 100.0 < end - 0.05:
            start = (a + last_run_end - 2) / 100.0
        report.append(f"clip{clip}  {tok:<14} <- {src_words:<16} {start:5.2f}-{end:5.2f}")
        out.append({"word": tok, "start": start, "end": end, "clip": clip, "chunk": ci, "highlight": False, "src": src_words})
    assert i == len(ww), (clip, i, len(ww))

# highlight marking by phrase match on punctuation-stripped words (case-insensitive for Latin)
for clip in (1, 2, 3):
    idx = [k for k, w in enumerate(out) if w["clip"] == clip]
    words = [strip_p(out[k]["word"]).lower() for k in idx]
    for ph in HIGHLIGHT_PHRASES:
        p = ph.lower().split()
        for s in range(len(words) - len(p) + 1):
            if words[s:s + len(p)] == p:
                for k in idx[s:s + len(p)]:
                    out[k]["highlight"] = True

# convert to trimmed-clip time, clamp, and interpolate any missing/inverted timings
for w in out:
    ts = edit[w["clip"]]["trim_start"]; dur = edit[w["clip"]]["duration"]
    w["start"] = round(min(max(w["start"] - ts, 0.0), dur), 3)
    w["end"] = round(min(max(w["end"] - ts, 0.0), dur), 3)
for k, w in enumerate(out):
    if w["end"] <= w["start"]:
        nxt = next((o["start"] for o in out[k + 1:] if o["clip"] == w["clip"]), edit[w["clip"]]["duration"])
        w["end"] = round(max(w["start"] + 0.08, min(nxt, w["start"] + 0.3)), 3)

# sanity: the script text reconstructed from captions must equal the exact script
for clip in (1, 2, 3):
    rebuilt = " ".join(w["word"] for w in out if w["clip"] == clip)
    exact = " ".join(SCRIPT[clip].replace("|", " ").split())
    assert rebuilt == exact, (rebuilt, exact)
    assert SequenceMatcher(None, rebuilt, exact).ratio() == 1.0

json.dump([{k: w[k] for k in ("word", "start", "end", "clip", "highlight", "chunk")} for w in out],
          open(os.path.join(root, "work", "captions.json"), "w"), ensure_ascii=False, indent=1)
open(os.path.join(root, "work", "captions_alignment_report.txt"), "w").write("\n".join(report) + "\n")
print("\n".join(report))
print("highlights:", [w["word"] for w in out if w["highlight"]])
