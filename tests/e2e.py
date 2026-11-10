#!/usr/bin/env python3
"""End-to-end test: a synthetic talking clip goes through the whole core module.

  python tests/e2e.py [--keep DIR]

Makes speech with the OS's own text-to-speech (macOS `say`, Windows SAPI), builds a 1080x1920 clip with a
deliberate 1.5 s pause, then: transcribe → word timings → silences → captions → align → burn captions (ffmpeg-skill)
→ export for Reels (ffmpeg-skill) → face check → final review. Fails loudly on the first wrong result.
Needs `reel.py setup` done first. Standard library only.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REEL = ROOT / "skills" / "edit-reel" / "scripts" / "reel.py"
sys.path.insert(0, str(REEL.parent))
import _env as E  # noqa: E402

os.environ.update(E.env())  # Windows resolves programs with this process's PATH, not the env= of the child

# Windows consoles default to a legacy code page that cannot print "→", "≤" or accents: always write UTF-8.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

LINE_A = "Hello, this is a test of the reel editor."
LINE_B = "Captions follow every single word you say."
PAUSE = 1.5


def sh(*cmd, ok=(0,)):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], env=E.env(), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout[-3000:])
    if r.returncode not in ok:
        sys.stdout.write(r.stderr[-3000:])
        raise SystemExit(f"FAILED (exit {r.returncode}): {' '.join(str(c) for c in cmd)}")
    return r


def reel(*args, ok=(0,)):
    return sh(sys.executable, REEL, *args, ok=ok)


def seconds(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def tts(text, out):
    """Speech with no silence before or after it, so the test knows exactly where the pause it adds is."""
    raw = out.with_name(out.stem + "_raw.wav")
    _tts(text, raw)
    trim = "silenceremove=start_periods=1:start_threshold=-45dB"
    sh("ffmpeg", "-nostdin", "-v", "error", "-y", "-i", raw, "-af", f"{trim},areverse,{trim},areverse",
       "-ar", "48000", "-ac", "1", out)


def _tts(text, out):
    """Speech from the OS's own voice; CI machines may have none, so fall back to espeak-ng."""
    if E.IS_MAC and shutil.which("say"):
        sh("say", "-o", out.with_suffix(".aiff"), text, ok=(0, 1))
        if seconds(out.with_suffix(".aiff")) > 0.5:
            sh("ffmpeg", "-nostdin", "-v", "error", "-y", "-i", out.with_suffix(".aiff"), "-ar", "48000", "-ac", "1", out)
            return
    if E.IS_WIN:
        ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.Rate = -1; $s.SetOutputToWaveFile('{out}'); $s.Speak('{text}'); $s.Dispose()")
        sh("powershell", "-NoProfile", "-Command", ps, ok=(0, 1))
        if seconds(out) > 0.5:
            return
    if shutil.which("espeak-ng"):
        sh("espeak-ng", "-s", "150", "-w", out, text)
        if seconds(out) > 0.5:
            return
    raise SystemExit("no working text-to-speech on this machine (install espeak-ng)")


def check(cond, msg):
    print(("  ok  " if cond else "  XX  ") + msg, flush=True)
    if not cond:
        raise SystemExit(f"FAILED: {msg}")


def main():
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    d = Path(keep or tempfile.mkdtemp(prefix="edit-reel-e2e-"))
    d.mkdir(parents=True, exist_ok=True)
    reel("doctor")

    # 1. A talking clip: line A, a 1.5 s pause, line B, on a 1080x1920 30 fps background.
    tts(LINE_A, d / "a.wav")
    tts(LINE_B, d / "b.wav")
    sh("ffmpeg", "-nostdin", "-v", "error", "-y", "-i", d / "a.wav", "-f", "lavfi", "-t", PAUSE, "-i",
       "anullsrc=r=48000:cl=mono", "-i", d / "b.wav", "-f", "lavfi", "-i", "color=c=0x1d2433:s=1080x1920:r=30",
       "-filter_complex", "[0:a]aresample=48000[x];[2:a]aresample=48000[y];[x][1:a][y]concat=n=3:v=0:a=1[a]",
       "-map", "3:v", "-map", "[a]", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
       d / "raw.mp4")
    a_len = float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                     d / "a.wav").stdout.strip())

    # 2. Transcribe with word timings.
    reel("transcribe", d / "raw.mp4", d / "raw", "--language", "en", "--names", "reel editor")
    words = json.loads((d / "raw.words.json").read_text(encoding="utf-8"))
    text = " ".join(w["w"] for w in words).lower()
    check(len(words) >= 12, f"{len(words)} words transcribed")
    for key in ("test", "editor", "captions", "word"):
        check(key in text, f"heard '{key}'")
    check(re.search(r"\b(reel|real)\b", text) is not None, "heard 'reel' (or its homophone 'real', fixed below)")
    check(all(w["start"] <= w["end"] for w in words), "every word starts before it ends")
    check(all(a["start"] <= b["start"] for a, b in zip(words, words[1:])), "words are in order")
    inside = [w for w in words if a_len + 0.25 < w["start"] < a_len + PAUSE - 0.25]
    check(not inside, f"no word starts inside the pause ({a_len:.2f}–{a_len + PAUSE:.2f} s)")

    # 3. Silences: the deliberate pause is found.
    pauses = json.loads(reel("silences", d / "raw.mp4", "--json").stdout)
    check(any(abs(p["start"] - a_len) < 0.4 and p["length"] > PAUSE - 0.4 for p in pauses),
          f"the {PAUSE} s pause is listed ({pauses})")

    # 4. Captions (2 words per cue) and re-alignment from the edited .srt.
    reel("captions", d / "raw.words.json", d / "captions.srt", "--words", "2")
    cues = re.findall(r"-->", (d / "captions.srt").read_text(encoding="utf-8"))
    check(len(cues) >= 6, f"{len(cues)} caption cues")
    srt = (d / "raw.srt").read_text(encoding="utf-8")
    (d / "fixed.srt").write_text(re.sub(r"(?i)real editor|reel editor", "reel editor", srt), encoding="utf-8")
    reel("align", d / "raw.mp4", d / "fixed.srt", d / "fixed.words.json", "--language", "en")
    fixed = json.loads((d / "fixed.words.json").read_text(encoding="utf-8"))
    check(len(fixed) >= 12, "re-aligned after an .srt fix")
    check(any(w["w"].lower().strip(".,") == "reel" for w in fixed), "the fixed word 'reel' has its own timing")

    # 5. The hands (ffmpeg-skill): burn captions below where a face would be, then export for Reels.
    reel("captions", d / "fixed.words.json", d / "captions.ass", "--words", "2", "--y", "1200", "--accent", "FFD400")
    ass = (d / "captions.ass").read_text(encoding="utf-8")
    check("PlayResX: 1080" in ass and "\\pos(540,1200)" in ass, "styled captions on the 1080x1920 canvas")
    reel("ff", "caption", d / "raw.mp4", "--ass", d / "captions.ass", "-o", d / "captioned.mp4", "--overwrite")
    reel("ff", "export", d / "captioned.mp4", "--preset", "reels", "-o", d / "exported.mp4", "--overwrite")
    reel("ff", "loudness", d / "exported.mp4", "-I", "-14", "--tp", "-1", "-o", d / "reel_v1.mp4", "--overwrite")

    # 6. Face check runs (no face in a synthetic clip) and the final review passes.
    r = reel("face", d / "reel_v1.mp4", "--texts", d / "captions.ass")
    check("face in 0 of" in r.stdout and "none covers" in r.stdout, "face check ran")
    rep = json.loads(reel("review", d / "reel_v1.mp4", "--platform", "reels", "--sheet", "--json").stdout)
    for c in rep["checks"]:
        check(c["pass"], f"review: {c['name']} = {c['actual']}")
    check(Path(rep["sheet"]).exists(), "contact sheet written")
    # The caption is drawn centred where asked: bright pixels around x=540, y=1200..1300 while a word is on screen.
    px = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", "1.0", "-i", str(d / "reel_v1.mp4"), "-frames:v",
                         "1", "-vf", "crop=1080:110:0:1200,format=gray,scale=108:11", "-f", "rawvideo", "-"],
                        env=E.env(), capture_output=True, check=True).stdout
    cols = [x for x in range(108) if any(px[y * 108 + x] > 200 for y in range(11) if y * 108 + x < len(px))]
    centre = (cols[0] + cols[-1]) / 2 if cols else -1
    check(cols and abs(centre - 54) <= 6, f"caption centred at the asked height (centre column {centre} of 108)")
    print(f"\nEND TO END OK  ({d})")
    if not keep:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
