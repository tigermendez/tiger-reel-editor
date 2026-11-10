"""Speech to text with the exact time of every word. Runs inside the 'core' environment (reel.py calls it).

  transcribe <media> <out-prefix> [--language es] [--names "Claude, Ana"] [--model large-v3-turbo]
      Whisper (faster-whisper) writes the words; WhisperX (wav2vec2) then measures where each one sounds.
      Leaves <out>.txt, <out>.srt (one cue per phrase), <out>.words.json ([{"w", "start", "end"}]) and
      <out>.listen.json: the moments Whisper was unsure about, for the person to listen to.
  align <media> <phrases.srt> <out.words.json> [--language es]
      After fixing a word or a name in the .srt, puts every word back where it is actually said.

Why two models: Whisper alone spreads a phrase's time evenly over its words, so in a long phrase a word can land
seconds early or late, often inside a pause. Aligning on the audio fixes that. Repeated takes are kept on purpose
(condition_on_previous_text=False): choosing the good take is the editor's call, not the transcriber's.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
# -I ignores PYTHONUTF8, and Windows consoles cannot print "→" or accents in their legacy code page.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

warnings.filterwarnings("ignore")


def to_wav(media, tmp):
    wav = os.path.join(tmp, "a.wav")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", media, "-vn", "-ac", "1", "-ar", "16000", wav],
                   check=True)
    return wav


def ts(t):
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(segments, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, s in enumerate(segments, 1):
            f.write(f"{i}\n{ts(s['start'])} --> {ts(s['end'])}\n{s['text'].strip()}\n\n")


def read_srt(path):
    out = []
    for block in re.split(r"\n\s*\n", open(path, encoding="utf-8-sig").read().strip()):
        lines = block.strip().splitlines()
        i = next((k for k, l in enumerate(lines) if "-->" in l), None)
        if i is None or i + 1 >= len(lines):
            continue
        a, z = [sum(float(x) * m for x, m in zip(re.split("[:,.]", t.strip()), (3600, 60, 1, 0.001)))
                for t in lines[i].split("-->")]
        out.append({"start": a, "end": z, "text": " ".join(lines[i + 1:]).strip()})
    return out


def align(wav, segments, language):
    import whisperx
    audio = whisperx.load_audio(wav)
    model, meta = whisperx.load_align_model(language_code=language, device="cpu")
    r = whisperx.align(segments, model, meta, audio, "cpu", return_char_alignments=False)
    words = [{"w": x["word"].strip(), "start": x.get("start"), "end": x.get("end")}
             for x in r["word_segments"] if x["word"].strip()]
    # Numbers and symbols ("2026", "%") have no letters to align: place them between their neighbours.
    for i, x in enumerate(words):
        if x["start"] is None:
            x["start"] = words[i - 1]["end"] if i else 0.0
            nxt = next((y["start"] for y in words[i + 1:] if y["start"] is not None), x["start"] + 0.3)
            x["end"] = max(x["start"] + 0.1, nxt)
    return [{"w": x["w"], "start": round(x["start"], 2), "end": round(x["end"], 2)} for x in words]


def save_words(words, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=0)


# Whisper invents these over silence or music (it learned them from subtitle credits on its training videos).
HALLUCINATIONS = re.compile(
    r"^(gracias por ver( el v[ií]deo)?|thanks? (you )?for watching|subt[ií]tulos (realizados )?por|amara\.org|"
    r"suscr[ií]bete|please subscribe|thank you\.?|gracias\.?|obrigad[oa] por assistir)", re.I)


def hallucination(seg):
    """A phrase that is probably not speech: Whisper itself says so, or it is a known silence filler."""
    text = seg.text.strip()
    if seg.no_speech_prob > 0.6 and seg.avg_logprob < -0.8:
        return True
    long_for_its_words = (seg.end - seg.start) > 4 * max(1, len(text.split()))
    return bool(HALLUCINATIONS.match(text)) and (long_for_its_words or seg.no_speech_prob > 0.3)


def moments_to_listen(heard, threshold):
    """Words Whisper heard with low confidence, grouped into moments with their neighbours as context.

    Low confidence is where stumbles, half-said words, mumbles, mispronunciations and unknown names show up. It is
    a pointer for the person's ears, not a verdict: Whisper cannot judge tone or delivery."""
    out = []
    for i, (st, en, w, p, first) in enumerate(heard):
        # The first word after a pause often scores low just because there is no context yet: only flag it when
        # Whisper is really unsure.
        if p >= threshold or (first and p >= threshold / 2):
            continue
        if out and st - out[-1]["end"] < 1.0:
            out[-1]["end"] = round(en, 2)
            out[-1]["words"].append(w)
            out[-1]["last"] = i
            continue
        out.append({"start": round(st, 2), "end": round(en, 2), "words": [w], "first": i, "last": i})
    for m in out:
        a, b = max(0, m.pop("first") - 3), min(len(heard), m.pop("last") + 4)
        flagged = set(m["words"])
        m["context"] = " ".join(f"[{h[2]}]" if h[2] in flagged and h[3] < threshold else h[2] for h in heard[a:b])
        m["words"] = " ".join(m["words"])
    return out


def cmd_transcribe(a):
    from faster_whisper import WhisperModel
    with tempfile.TemporaryDirectory() as tmp:
        wav = to_wav(a.media, tmp)
        model = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
        # hotwords reach every 30 s window; initial_prompt alone only helps the first one when we do not condition
        # on previous text (which we avoid so repeated takes are not skipped).
        segs, info = model.transcribe(wav, language=a.language, initial_prompt=a.names or None,
                                      hotwords=a.names or None, beam_size=5, condition_on_previous_text=False,
                                      vad_filter=a.vad, word_timestamps=True)
        segments, dropped, heard = [], [], []
        for s in segs:
            if not s.text.strip():
                continue
            bad = hallucination(s)
            (dropped if bad else segments).append({"start": s.start, "end": s.end, "text": s.text.strip()})
            if not bad:
                ws = [w for w in (s.words or []) if w.word.strip()]
                heard += [(w.start, w.end, w.word.strip(), w.probability, k == 0) for k, w in enumerate(ws)]
        language = a.language or info.language
        with open(a.out + ".txt", "w", encoding="utf-8") as f:
            f.write("\n".join(s["text"] for s in segments) + "\n")
        write_srt(segments, a.out + ".srt")
        words = align(wav, segments, language) if segments else []
    save_words(words, a.out + ".words.json")
    listen = moments_to_listen(heard, a.listen)
    with open(a.out + ".listen.json", "w", encoding="utf-8") as f:
        json.dump(listen, f, ensure_ascii=False, indent=1)
    print(f"language: {language}  phrases: {len(segments)}  words: {len(words)}")
    if listen:
        print(f"listen to these {len(listen)} moments (Whisper was unsure: a stumble, a cut word, a mumble, a name):")
        for m in listen:
            print(f"  {m['start']:7.2f}-{m['end']:6.2f} s  {m['context']}")
    else:
        print("Whisper was sure of every word (still listen to the takes you keep).")
    for x in dropped:
        print(f"dropped as a likely Whisper hallucination ({x['start']:.1f}-{x['end']:.1f} s): {x['text']!r}"
              " (if it was really said, add it back to the .srt and run align)")
    print(f"→ {a.out}.txt  {a.out}.srt  {a.out}.words.json")


def cmd_align(a):
    segments = read_srt(a.srt)
    if not segments:
        sys.exit(f"error: no cues in {a.srt}")
    with tempfile.TemporaryDirectory() as tmp:
        words = align(to_wav(a.media, tmp), segments, a.language)
    save_words(words, a.out)
    print(f"{len(words)} words aligned → {a.out}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("transcribe")
    t.add_argument("media")
    t.add_argument("out")
    t.add_argument("--language", default=None, help="es, en, pt... (default: detect)")
    t.add_argument("--names", default="", help="proper nouns said in the video, so Whisper spells them right")
    t.add_argument("--model", default=os.environ.get("TIGER_REEL_EDITOR_WHISPER_MODEL", "large-v3-turbo"))
    t.add_argument("--vad", action="store_true", help="skip long non-speech parts (faster; may drop short words)")
    t.add_argument("--listen", type=float, default=0.6, help="flag words heard with less confidence than this (0.6)")
    al = sub.add_parser("align")
    al.add_argument("media")
    al.add_argument("srt")
    al.add_argument("out")
    al.add_argument("--language", default="en")
    a = p.parse_args()
    {"transcribe": cmd_transcribe, "align": cmd_align}[a.cmd](a)


if __name__ == "__main__":
    main()
