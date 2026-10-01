"""STEP 3 — align the EXACT script (work/script.json) to faster-whisper word timings.

Whisper is used ONLY for timing; caption text is always the script. Each script token is mapped to
whisper words by an ordered span list (SPANS): n = consume n whisper words (e.g. TrainPlex = ट्रेन + प्लेक्स);
("split", k, parts) = token k of one whisper word shared by `parts` tokens, split proportionally
("400" -> चार + सौ). If a re-generated take is heard differently, the span list will no longer add up
and the script fails loudly (assert), so SPANS must be re-checked against work/transcripts/*.json.

Pauses whisper gave to a word are removed with a 10 ms RMS search for >= 100 ms runs below -35 dBFS
inside the word window: a run near the window START moves the word start to the run end; a run near
the window END moves the word end to the run start (and the next word starts at the run end). Runs in
the middle (stop closures) are left alone. Output times are relative to the TRIMMED clip
(work/edit.json), clamped into the clip.

Chunk breaks ('|') follow work/REMOTION_INPUTS.md (one-line chunks where lower-band graphics are up).
"""
import json
import os
import wave
from difflib import SequenceMatcher

import numpy as np

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
edit = {c["clip"]: c for c in json.load(open(os.path.join(root, "work", "edit.json"), encoding="utf-8"))["clips"]}
SCRIPT_JSON = json.load(open(os.path.join(root, "work", "script.json"), encoding="utf-8"))

# Chunked script ('|' = caption chunk break). Must equal script.json exactly once the bars are removed.
CHUNKED = {
    1: "Hostel में सबसे पूछो — | pocket money | कब खत्म होती है? | बीस तारीख तक! | मेरी नहीं होती, | क्योंकि मैं TrainPlex | पे काम करती हूँ।",
    2: "Lecture के बाद, | phone से — | voice record, | photos, text check। | AI कंपनियों के | छोटे tasks। | कोई fees नहीं, | training भी free।",
    3: "मैं दिन में | दो-तीन घंटे काम | करती हूँ और | चार सौ से पाँच सौ | कमा लेती हूँ, | सीधे Bank या UPI में। | नीचे Learn more | दबाओ और अभी | register करो!",
}
# Whisper-word spans per script token (after the em dash is attached to the previous token).
SPANS = {
    # Hostel में सबसे(सब+से) पूछो— pocket money कब खत्म होती है? बीस तारीख तक! मेरी नहीं होती, क्योंकि मैं TrainPlex(ट्रेन+प्लेक्स) पे काम करती हूँ।
    1: [1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1],
    # Lecture के बाद, phone "से —"(से + an extra syllable whisper hears as "सेंड") voice record, photos, text check। AI ...
    2: [1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    # मैं दिन में दो-तीन(दो+तीन) घंटे काम करती हूँ और चार सौ(=400 split) से पाँच सौ(=500 split) कमा ...
    3: [1, 1, 1, 2, 1, 1, 1, 1, 1, ("split", 0, 2), ("split", 1, 2), 1, ("split", 0, 2), ("split", 1, 2),
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
}
HIGHLIGHT_PHRASES = SCRIPT_JSON["highlight_phrases"]
PUNCT = ",!?।—"


def norm(s):
    return " ".join(s.split())


def strip_p(w):
    return w.strip().strip(PUNCT).strip()


def rms_env(clip):
    w = wave.open(os.path.join(root, "work", "transcripts", f"clip{clip}_16k.wav"))
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    hop = 160
    return np.array([20 * np.log10(np.sqrt(np.mean(x[k:k + hop] ** 2)) + 1e-9) for k in range(0, len(x) - hop + 1, hop)])


def main():
    for c in (1, 2, 3):
        assert norm(CHUNKED[c].replace("|", " ")) == norm(SCRIPT_JSON["clips"][f"clip{c}"]), f"CHUNKED clip {c} != script.json"
    out, report = [], []
    for clip in (1, 2, 3):
        raw = json.load(open(os.path.join(root, "work", "transcripts", f"clip{clip}_raw.json"), encoding="utf-8"))
        ww = [w for s in raw["segments"] for w in s["words"]]
        chunks = [c.strip().split() for c in CHUNKED[clip].split("|")]
        toks = []
        for ci, ch in enumerate(chunks):
            for t in ch:
                if t == "—" and toks:
                    toks[-1] = (toks[-1][0] + " —", toks[-1][1])
                else:
                    toks.append((t, ci))
        assert len(toks) == len(SPANS[clip]), (clip, len(toks), len(SPANS[clip]))
        need = sum(1 if isinstance(s, tuple) and s[1] == s[2] - 1 else (0 if isinstance(s, tuple) else s) for s in SPANS[clip])
        assert need == len(ww), f"clip {clip}: SPANS consume {need} whisper words, transcript has {len(ww)} — re-map SPANS"
        env = rms_env(clip)
        i = 0
        carry = None
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
            # carried from the previous word: its trailing pause showed where this word really starts
            tightened = ""
            if carry is not None and 0 < start - carry < 0.15:
                tightened += f"  (start {start:.2f} -> {carry:.2f}: prev word's trailing pause)"
                start = carry
            carry = None
            a, b = int(round(start * 100)), max(int(round(start * 100)) + 1, int(round(end * 100)))
            quiet = env[a:b] < -35
            runs, run = [], 0
            for k, q in enumerate(quiet):
                run = run + 1 if q else 0
                if run >= 10 and (k + 1 >= len(quiet) or not quiet[k + 1]):
                    runs.append((k + 1 - run, k + 1))  # [run start, run end) in bins from a
            lead = [r for r in runs if r[0] <= 20 and (len(quiet) - r[1]) >= 5]
            trail = [r for r in runs if r[0] > 20 and (len(quiet) - r[1]) < 12]
            if lead:
                # the window opens on a pause (whisper absorbed it): the word starts after the last such run
                new = (a + lead[-1][1] - 2) / 100.0
                tightened += f"  (start tightened {start:.2f} -> {new:.2f})"
                start = new
            elif trail:
                # the word ended before a pause that whisper gave to it: end at the pause, the next word
                # starts at its end
                new_end = (a + trail[0][0] + 2) / 100.0
                carry = (a + trail[0][1] - 2) / 100.0
                tightened += f"  (end tightened {end:.2f} -> {new_end:.2f})"
                end = new_end
            report.append(f"clip{clip}  {tok:<14} <- {src_words:<18} {start:5.2f}-{end:5.2f}{tightened}")
            out.append({"word": tok, "start": start, "end": end, "clip": clip, "chunk": ci, "highlight": False, "src": src_words})
        assert i == len(ww), (clip, i, len(ww))

    for clip in (1, 2, 3):
        idx = [k for k, w in enumerate(out) if w["clip"] == clip]
        words = [strip_p(out[k]["word"]).lower() for k in idx]
        for ph in HIGHLIGHT_PHRASES:
            p = ph.lower().split()
            for s in range(len(words) - len(p) + 1):
                if words[s:s + len(p)] == p:
                    for k in idx[s:s + len(p)]:
                        out[k]["highlight"] = True
    for ph in HIGHLIGHT_PHRASES:  # every highlight must land somewhere
        p = ph.lower().split()
        assert any([strip_p(w["word"]).lower() for w in out[k:k + len(p)]] == p for k in range(len(out))), ph

    for w in out:
        ts = edit[w["clip"]]["trim_start"]
        dur = edit[w["clip"]]["duration"]
        w["start"] = round(min(max(w["start"] - ts, 0.0), dur), 3)
        w["end"] = round(min(max(w["end"] - ts, 0.0), dur), 3)
    for k, w in enumerate(out):
        if w["end"] <= w["start"]:
            nxt = next((o["start"] for o in out[k + 1:] if o["clip"] == w["clip"]), edit[w["clip"]]["duration"])
            w["end"] = round(max(w["start"] + 0.08, min(nxt, w["start"] + 0.3)), 3)

    for clip in (1, 2, 3):
        rebuilt = " ".join(w["word"] for w in out if w["clip"] == clip)
        exact = norm(SCRIPT_JSON["clips"][f"clip{clip}"])
        assert rebuilt == exact, (rebuilt, exact)
        assert SequenceMatcher(None, rebuilt, exact).ratio() == 1.0

    json.dump([{k: w[k] for k in ("word", "start", "end", "clip", "highlight", "chunk")} for w in out],
              open(os.path.join(root, "work", "captions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(root, "work", "captions_alignment_report.txt"), "w", encoding="utf-8").write("\n".join(report) + "\n")
    print("\n".join(report))
    print("highlights:", [w["word"] for w in out if w["highlight"]])
    print("script match: 100 % (all 3 clips)")


if __name__ == "__main__":
    main()
