"""Sound effects: a starter set made from scratch (free to use, no licence questions) and placing effects at exact
times under the voice. Standard library + FFmpeg. Called by `reel.py sfx`.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Each sound is synthesised with FFmpeg's own generators, so the set is ours (MIT) and needs no download.
STARTER = {
    "whoosh": ["-f", "lavfi", "-i", "anoisesrc=d=0.55:c=pink:a=0.9:r=48000", "-af",
               "highpass=f=250,lowpass=f=4000,afade=t=in:d=0.28:curve=qsin,afade=t=out:st=0.28:d=0.27:curve=qsin"],
    "pop": ["-f", "lavfi", "-i", "aevalsrc='0.9*sin(2*PI*(1100-700*t/0.09)*t)*exp(-t*35)':s=48000:d=0.15"],
    "click": ["-f", "lavfi", "-i", "aevalsrc='0.8*(random(0)*2-1)*exp(-t*350)':s=48000:d=0.04", "-af", "highpass=f=1500"],
    "ding": ["-f", "lavfi", "-i",
             "aevalsrc='0.5*sin(2*PI*1320*t)*exp(-t*3)+0.25*sin(2*PI*1980*t)*exp(-t*4)':s=48000:d=1.2"],
    "riser": ["-f", "lavfi", "-i", "aevalsrc='0.35*sin(2*PI*(200+600*t*t/1.5)*t)*(t/1.5)':s=48000:d=1.5",
              "-f", "lavfi", "-i", "anoisesrc=d=1.5:c=white:a=0.3:r=48000", "-filter_complex",
              "[1:a]highpass=f=2000,afade=t=in:d=1.5:curve=tri[n];[0:a][n]amix=inputs=2:normalize=0,"
              "afade=t=out:st=1.42:d=0.08"],
    "impact": ["-f", "lavfi", "-i", "aevalsrc='0.9*sin(2*PI*(70-30*t)*t)*exp(-t*6)':s=48000:d=0.9",
               "-f", "lavfi", "-i", "anoisesrc=d=0.9:c=brown:a=0.8:r=48000", "-filter_complex",
               "[1:a]lowpass=f=400,afade=t=out:d=0.25:curve=exp[n];[0:a][n]amix=inputs=2:normalize=0"],
}
SUFFIXES = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac")


def ff(*args, capture=False):
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"error: ffmpeg failed: {r.stderr[-800:]}")
    return r.stderr


def peak_db(path):
    m = re.search(r"max_volume:\s*([-\d.]+) dB", ff("-i", path, "-af", "volumedetect", "-f", "null", "-"))
    return float(m[1]) if m else 0.0


def make_starter(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, recipe in STARTER.items():
            raw = Path(tmp) / f"{name}.wav"
            ff("-v", "error", "-y", *recipe, "-ac", "1", raw)
            gain = -3.0 - peak_db(raw)  # every sound peaks at -3 dBFS, so levels are comparable
            ff("-v", "error", "-y", "-i", raw, "-af", f"volume={gain:.2f}dB", "-ac", "2", folder / f"{name}.wav")
    (folder / "README.txt").write_text(
        "Starter sound effects made by edit-reel from FFmpeg's generators (no samples, free to use anywhere).\n"
        "Add your own files here (wav, mp3...) and call them by name: reel.py sfx ... --at '3.2 whoosh'.\n",
        encoding="utf-8")
    return sorted(p.stem for p in folder.glob("*.wav"))


def find_sound(name, folders):
    p = Path(name)
    if p.suffix and p.exists():
        return p
    for d in folders:
        for suf in ("",) + SUFFIXES:
            c = Path(d) / f"{name}{suf}"
            if c.is_file():
                return c
    return None


def parse_cue(text):
    """'3.2 whoosh', '3.2 whoosh -6' or '0:03.2 sounds/pop.mp3 -4' → (seconds, name, dB)."""
    parts = text.replace(",", " ").split()
    if len(parts) < 2:
        sys.exit(f"error: a cue needs a time and a sound: {text!r}")
    t = parts[0]
    sec = sum(float(x) * m for x, m in zip(reversed(t.split(":")), (1, 60, 3600)))
    db = float(parts[2]) if len(parts) > 2 else 0.0
    return sec, parts[1], db


def place(video, out, cues, folders, level):
    """Mix every effect at its time under the existing audio. The video stream is copied untouched."""
    found = []
    for sec, name, db in cues:
        path = find_sound(name, folders)
        if not path:
            sys.exit(f"error: no sound '{name}' in {', '.join(map(str, folders))}. "
                     "Make the starter set with: reel.py sfx --starter sounds")
        found.append((sec, path, db))
    args, chains = ["-y", "-i", video], []
    for k, (sec, path, db) in enumerate(found, 1):
        args += ["-i", path]
        ms = max(0, round(sec * 1000))
        chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}:all=1,"
                      f"volume={level + db:.1f}dB[s{k}]")
    mix = "[0:a]aresample=48000,aformat=channel_layouts=stereo[v];" + ";".join(chains) + ";" + \
          "[v]" + "".join(f"[s{k}]" for k in range(1, len(found) + 1)) + \
          f"amix=inputs={len(found) + 1}:normalize=0:duration=first[a]"
    ff("-v", "error", *args, "-filter_complex", mix, "-map", "0:v?", "-map", "[a]", "-c:v", "copy",
       "-c:a", "aac", "-b:a", "192k", out)
    for sec, path, db in found:
        print(f"  {sec:7.2f} s  {path.name}  ({level + db:+.1f} dB)")
    return found
