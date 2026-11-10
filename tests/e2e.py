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
    reel("level", d / "exported.mp4", "-o", d / "reel_v1.mp4")

    # 6. Face check runs (no face in a synthetic clip) and the final review passes.
    r = reel("face", d / "reel_v1.mp4", "--texts", d / "captions.ass")
    check("face in 0 of" in r.stdout and "none covers" in r.stdout, "face check ran")
    rep = json.loads(reel("review", d / "reel_v1.mp4", "--platform", "reels", "--sheet", "--json").stdout)
    for c in rep["checks"]:
        check(c["pass"], f"review: {c['name']} = {c['actual']}")
    check(Path(rep["sheet"]).exists(), "contact sheet written")
    # The caption is drawn centred where asked: light pixels around x=540, y=1200..1310, in the middle of a cue.
    first = next(l for l in ass.splitlines() if l.startswith("Dialogue:")).split(",")
    t0 = sum(float(x) * m for x, m in zip(first[1].split(":"), (3600, 60, 1)))
    t1 = sum(float(x) * m for x, m in zip(first[2].split(":"), (3600, 60, 1)))
    px = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{(t0 + t1) / 2:.2f}", "-i", str(d / "reel_v1.mp4"),
                         "-frames:v", "1", "-vf", "crop=1080:110:0:1200,format=gray,scale=108:11", "-f", "rawvideo", "-"],
                        env=E.env(), capture_output=True, check=True).stdout
    cols = [x for x in range(108) if any(px[y * 108 + x] > 120 for y in range(11) if y * 108 + x < len(px))]
    centre = (cols[0] + cols[-1]) / 2 if cols else -1
    check(cols and abs(centre - 54) <= 6, f"caption centred at the asked height (centre column {centre} of 108)")
    # 6b. Captions can change height per shot.
    reel("captions", d / "fixed.words.json", d / "two.ass", "--y", "900", "--y-at", f"{a_len + 0.5:.2f}-99=1400")
    two = (d / "two.ass").read_text(encoding="utf-8")
    check("\\pos(540,900)" in two and "\\pos(540,1400)" in two, "captions change height per stretch (--y-at)")

    # 6c. Words of a cut made of pieces come from the takes, shifted by each piece's real length.
    words_all = json.loads((d / "fixed.words.json").read_text(encoding="utf-8"))
    b_start = next(w["start"] for w in words_all if w["start"] > a_len + 0.5)
    reel("ff", "cut", d / "raw.mp4", "--start", f"{b_start - 0.08:.2f}", "--accurate", "-o", d / "pb.mp4", "--overwrite")
    reel("ff", "cut", d / "raw.mp4", "--end", f"{a_len + 0.1:.2f}", "--accurate", "-o", d / "pa.mp4", "--overwrite")
    (d / "pieces.json").write_text(json.dumps([
        {"words": "fixed.words.json", "from": b_start - 0.08, "to": 99, "file": "pb.mp4"},
        {"words": "fixed.words.json", "from": 0, "to": a_len + 0.1, "file": "pa.mp4"}]), encoding="utf-8")
    reel("words", d / "pieces.json", "-o", d / "swapped.words.json")
    sw = json.loads((d / "swapped.words.json").read_text(encoding="utf-8"))
    check(sw and sw[0]["w"].lower().startswith("caption") and sw[0]["start"] < 0.3,
          f"pieces put line B first ({sw[0]['w'] if sw else '-'} at {sw[0]['start'] if sw else '-'} s)")
    check(any(w["w"].lower().startswith("hello") and w["start"] > 1.5 for w in sw), "and line A after it")

    # 7. Sound effects: the starter set exists and an effect lands at its time (silence before, sound at 1.0 s).
    listed = reel("sfx", "--list").stdout
    check(all(n in listed for n in ("whoosh", "pop", "ding")), "starter sound effects are available")
    check("something slides in" in listed, "each starter sound says when to use it (sounds.txt)")
    sh("ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30:d=3", "-f",
       "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
       d / "silent.mp4")
    reel("sfx", d / "silent.mp4", "-o", d / "sfx.mp4", "--at", "1.0 pop")

    def peak(start, length):
        r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-ss", str(start), "-t", str(length), "-i",
                            str(d / "sfx.mp4"), "-af", "volumedetect", "-f", "null", "-"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        m = re.search(r"max_volume: ([-\d.]+) dB", r.stderr)
        return float(m[1]) if m else -120.0
    quiet, hit = peak(0, 0.8), peak(0.98, 0.25)
    check(quiet < -60 and hit > -30, f"effect placed at 1.0 s (before: {quiet} dB, at the cue: {hit} dB)")
    # 7b. Study an example: frames, rhythm and transcript.
    reel("study", d / "raw.mp4", "-o", d / "study", "--language", "en")
    st = json.loads((d / "study" / "stats.json").read_text(encoding="utf-8"))
    check((d / "study" / "hook.jpg").exists() and (d / "study" / "sheet.jpg").exists(), "study writes the frames")
    check(st.get("words", 0) >= 12 and st.get("words_per_minute"), f"study measures speech ({st.get('words_per_minute')} wpm)")

    # 7c. Fonts as files: download one (needs internet; skipped if GitHub is unreachable) and burn captions with it.
    r = reel("font", "Bebas Neue", "--dir", d / "fonts", ok=(0, 1))
    if r.returncode == 0:
        ttf = next((d / "fonts").rglob("*.ttf"))
        reel("captions", d / "fixed.words.json", d / "font.ass", "--y", "1200", "--font", ttf)
        check("Style: Reel,Bebas Neue," in (d / "font.ass").read_text(encoding="utf-8"),
              "captions use the family name read from the font file")
        reel("ff", "caption", d / "raw.mp4", "--ass", d / "font.ass", "--fonts-dir", ttf.parent, "-o",
             d / "font.mp4", "--overwrite")
        check((d / "font.mp4").exists(), "captions burn with a font file (no installed font needed)")
        reel("text", d / "raw.mp4", "A *fixed* sentence", "-o", d / "text.mp4", "--font", ttf, "--color", "F8C300",
             "--accent", "FFF8B5", "--y", "900")
        ass = (d / "text.text.ass").read_text(encoding="utf-8")
        check("Dialogue: 0,0:00:00.00," in ass and "&H00B5F8FF&" in ass and (d / "text.mp4").exists(),
              "fixed text stays the whole clip, marked word in the accent colour")
        reel("text", d / "raw.mp4", "Curvy letters", "-o", d / "curvy.mp4", "--font", ttf, "--color", "F8C300",
             "--y", "900", "--fisheye", "0.3")
        check((d / "curvy.text" / "warped.png").exists() and (d / "curvy.mp4").exists(),
              "fisheye text: transparent bulged layer laid over the clip")
    else:
        print("  --  font download skipped (no access to GitHub)")

    # 7d. Effects by name.
    reel("fx", "zoom", d / "raw.mp4", "-o", d / "fx_zoom.mp4", "--at", "1.0", "--dur", "1.0")
    reel("fx", "shake", d / "raw.mp4", "-o", d / "fx_shake.mp4", "--at", "1.0")
    reel("fx", "freeze", d / "raw.mp4", "-o", d / "fx_freeze.mp4", "--at", "1.0", "--hold", "1.0")
    reel("fx", "speed", d / "raw.mp4", "-o", d / "fx_speed.mp4", "--at", "1.0", "--dur", "1.0", "--factor", "0.5")
    base_len = seconds(d / "raw.mp4")
    check(abs(seconds(d / "fx_freeze.mp4") - base_len - 1.0) < 0.2, "freeze adds its hold to the length")
    check(abs(seconds(d / "fx_speed.mp4") - base_len - 1.0) < 0.25, "half speed for 1 s adds 1 s")
    check(abs(seconds(d / "fx_zoom.mp4") - base_len) < 0.1 and (d / "fx_shake.mp4").exists(), "zoom and shake keep the length")
    for name, colour in (("a.png", "red"), ("b.png", "blue")):
        sh("ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=600x900", "-frames:v",
           "1", d / name)
    reel("fx", "split", d / "a.png", d / "b.png", "-o", d / "fx_split.mp4", "--dur", "2")
    check(abs(seconds(d / "fx_split.mp4") - 2.0) < 0.1, "before/after from two images")
    reel("text", d / "raw.mp4", "Typed text", "-o", d / "typed.mp4", "--typewriter", "1.0")
    check((d / "typed.text.ass").read_text(encoding="utf-8").count("Dialogue:") >= 9, "typewriter reveals letter by letter")

    # 8. Clear errors instead of wrong answers.
    sh("ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=720x1280:r=30:d=2",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", d / "mute.mp4")
    r = reel("silences", d / "mute.mp4", ok=(1,))
    check("no sound track" in (r.stdout + r.stderr), "silences on a video with no sound says so (not '0 pauses')")
    r = reel("silences", d / "missing.mp4", ok=(1,))
    check("not found" in (r.stdout + r.stderr), "silences on a missing file says so")
    r = reel("transcribe", d / "mute.mp4", d / "mute", ok=(1,))
    check("no sound track" in (r.stdout + r.stderr), "transcribe on a video with no sound says so")
    r = reel("face", d / "mute.mp4", "--step", "1")
    check("1080x1920" in r.stdout, "face measures a 720x1280 video on the 1080x1920 canvas")
    srt_before = (d / "fixed.srt").read_text(encoding="utf-8")
    r = reel("fix", d / "raw.mp4", d / "fixed", "--replace", "editor=Editor", ok=(1,))
    check("--language" in (r.stdout + r.stderr), "fix asks for the language when no transcript metadata exists")
    reel("fix", d / "raw.mp4", d / "fixed", "--replace", "1=one", "--replace", "editor=Editor", "--language", "en")
    srt_after = (d / "fixed.srt").read_text(encoding="utf-8")
    check(srt_after.splitlines()[0] == srt_before.splitlines()[0] and "-->" in srt_after.splitlines()[1],
          "fix leaves cue numbers and times alone")
    check("Editor" in srt_after, "fix replaced the word and re-aligned")
    check(json.loads((d / "raw.meta.json").read_text())["language"] == "en", "transcribe saved the detected language")
    reel("sfx", d / "silent.mp4", "-o", d / "sfx2.mp4", "--at", "1,0 pop")
    check(peak(0.98, 0.25) > -30, "a comma decimal time ('1,0 pop') works")
    print(f"\nEND TO END OK  ({d})")
    if not keep:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
