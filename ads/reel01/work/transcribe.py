import json, sys, time, subprocess, os
from faster_whisper import WhisperModel
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
t0 = time.time()
model = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)
print("model loaded", time.time()-t0, flush=True)
for i in (1, 2, 3):
    src = os.path.join(root, "clips", f"clip{i}.mp4")
    wav = os.path.join(root, "work", "transcripts", f"clip{i}_16k.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "16000", wav], check=True)
    segs, info = model.transcribe(wav, language="hi", word_timestamps=True, beam_size=5, vad_filter=False)
    out = {"clip": i, "language": info.language, "duration": info.duration, "segments": []}
    for s in segs:
        out["segments"].append({"start": s.start, "end": s.end, "text": s.text,
            "words": [{"word": w.word, "start": w.start, "end": w.end, "prob": w.probability} for w in (s.words or [])]})
    json.dump(out, open(os.path.join(root, "work", "transcripts", f"clip{i}_raw.json"), "w"), ensure_ascii=False, indent=2)
    print(f"clip{i} done", time.time()-t0, " | ".join(s["text"] for s in out["segments"]), flush=True)
