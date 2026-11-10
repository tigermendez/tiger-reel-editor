#!/usr/bin/env python3
"""edit-reel: one entry point for every tool. Standard library only; runs with Python 3.9+ on macOS and Windows.

  reel.py setup [--module core|voice|all] [--language en,es] [--yes]   install what is missing (asks before system programs)
  reel.py doctor                                                     what is installed
  reel.py new <slug> [--dir reels]                                   project folder: raw/ refs/ out/ plan.md
  reel.py transcribe <video> <out-prefix> [--language es] [--names "Claude, Ana"]
                                                                     .txt, .srt by phrase, .words.json (time of every word)
  reel.py align <video> <phrases.srt> <out.words.json> [--language es] re-time words after fixing the .srt
  reel.py captions <words.json> <out.srt> [--words 2] [--upper]      short caption cues that follow the voice
  reel.py silences <video> [--db -38] [--min 0.3]                    where the pauses are (start end length)
  reel.py face <video> [--texts captions.srt --band 1150-1250] [--json face.json]
                                                                     where the face is; does any text cover it?
  reel.py review <video> [--platform reels|tiktok|shorts] [--sheet]  final technical check (exit 0 = passes)
  reel.py voice <video> <out.wav>                                    clean voice (module 'voice')
  reel.py ff <tool> [args...]                                        run an ffmpeg-skill tool (cut, silence, caption, loudness, export, check, look...)
  reel.py ff                                                         where ffmpeg-skill's own SKILL.md is
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env as E  # noqa: E402

os.environ.update(E.env())  # FFmpeg from ffmpeg-full / winget is visible to everything below


def cmd_setup(rest):
    import _setup
    p = argparse.ArgumentParser(prog="reel.py setup")
    p.add_argument("--module", default="core", help="core (default), voice, or all; several with commas")
    p.add_argument("--language", default="en", help="languages to prepare word timings for, e.g. en,es")
    p.add_argument("--model", default=None, help="speech model (default large-v3-turbo; 'small' for a quick test)")
    p.add_argument("--yes", action="store_true", help="allow installing FFmpeg/uv with Homebrew or winget")
    p.add_argument("--ffmpeg-skill-from", default=None, help="local .tgz or folder of ffmpeg-skill (offline/backup)")
    a = p.parse_args(rest)
    mods = list(_setup.MODULES) if a.module == "all" else [m.strip() for m in a.module.split(",")]
    for m in mods:
        if m not in _setup.MODULES:
            sys.exit(f"error: unknown module '{m}' (core, voice, all)")
    if "core" not in mods and not E.venv_python("core").exists():
        mods.insert(0, "core")
    _setup.setup(mods, a.yes, [x.strip() for x in a.language.split(",") if x.strip()], a.model, a.ffmpeg_skill_from)
    return 0


def cmd_doctor(rest):
    import _setup
    return _setup.doctor()


def cmd_new(rest):
    p = argparse.ArgumentParser(prog="reel.py new")
    p.add_argument("slug")
    p.add_argument("--dir", default="reels")
    a = p.parse_args(rest)
    root = Path(a.dir) / a.slug
    if root.exists():
        sys.exit(f"error: {root} already exists")
    for d in ("raw", "refs", "out"):
        (root / d).mkdir(parents=True)
    plan = (E.SKILL_DIR / "templates" / "plan.md").read_text(encoding="utf-8").replace("{slug}", a.slug)
    (root / "plan.md").write_text(plan, encoding="utf-8")
    print(f"ready: {root}  (put the footage in raw/; it is never modified)")
    return 0


def cmd_transcribe(rest):
    return E.in_venv("core", "speech.py", ["transcribe", *rest])


def cmd_align(rest):
    return E.in_venv("core", "speech.py", ["align", *rest])


def ts(t):
    ms = max(0, round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def cmd_captions(rest):
    p = argparse.ArgumentParser(prog="reel.py captions",
                                description="Group timed words into short cues (1-3 words) that follow the voice.")
    p.add_argument("words")
    p.add_argument("out")
    p.add_argument("--words", dest="n", type=int, default=2, help="max words per cue (2)")
    p.add_argument("--max-chars", type=int, default=16, help="max characters per cue (16)")
    p.add_argument("--gap", type=float, default=0.35, help="a pause this long (s) always starts a new cue")
    p.add_argument("--upper", action="store_true")
    g = p.add_argument_group("styled .ass output (when <out> ends in .ass)")
    g.add_argument("--y", type=int, default=1150, help="top of the caption in px; use what `face` says fits (1150)")
    g.add_argument("--size", type=int, default=86, help="font size in px (86)")
    g.add_argument("--font", default="Arial", help="font family installed on this machine (Arial)")
    g.add_argument("--color", default="FFFFFF", help="text colour, hex RRGGBB (FFFFFF)")
    g.add_argument("--accent", default=None, help="colour of the word being said, hex (e.g. FFD400); off by default")
    g.add_argument("--outline", type=float, default=6, help="black outline in px (6)")
    g.add_argument("--width", type=int, default=1080)
    g.add_argument("--height", type=int, default=1920)
    a = p.parse_args(rest)
    words = json.loads(Path(a.words).read_text(encoding="utf-8"))
    cues, cur = [], []
    for i, w in enumerate(words):
        if cur and (len(cur) >= a.n or len(" ".join(x["w"] for x in cur + [w])) > a.max_chars
                    or w["start"] - cur[-1]["end"] >= a.gap or re.search(r"[.,!?;:]$", cur[-1]["w"])):
            cues.append(cur)
            cur = []
        cur.append(w)
    if cur:
        cues.append(cur)
    timed = []
    for i, c in enumerate(cues):
        nxt = cues[i + 1][0]["start"] if i + 1 < len(cues) else c[-1]["end"] + 0.4
        end = min(nxt, c[-1]["end"] + 0.4)  # hold a little after the last word, never over the next cue
        timed.append((c, c[0]["start"], end))
    fix = (lambda s: s.upper()) if a.upper else (lambda s: s)
    if a.out.lower().endswith(".ass"):
        write_ass(a, timed, fix)
    else:
        with open(a.out, "w", encoding="utf-8") as f:
            for i, (c, start, end) in enumerate(timed):
                f.write(f"{i + 1}\n{ts(start)} --> {ts(end)}\n{fix(' '.join(x['w'] for x in c).strip(' ,;:'))}\n\n")
    print(f"{len(cues)} cues from {len(words)} words → {a.out}")
    return 0


def ass_color(hex6):
    h = hex6.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def write_ass(a, timed, fix):
    """An .ass on the reel's real canvas (default 1080x1920), centred at a pixel height.

    Burning an .srt on a vertical video lets the renderer assume a 384x288 landscape canvas, which can push
    captions off centre; an .ass with PlayResX/PlayResY = the video size puts them exactly where asked.
    With --accent, the word being said is drawn in that colour (one event per word, from its measured start).
    """
    def t(x):
        cs = max(0, round(x * 100))
        return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"

    def esc(s):
        return s.replace("\\", "").replace("{", "(").replace("}", ")")

    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {a.width}", f"PlayResY: {a.height}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Reel,{a.font},{a.size},{ass_color(a.color)},{ass_color(a.color)},&H00000000&,&H80000000&,-1,0,0,0,"
        f"100,100,0,0,1,{a.outline},2,8,40,40,0,1", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    pos = f"{{\\an8\\pos({a.width // 2},{a.y})}}"
    lines = []
    for c, start, end in timed:
        words = [esc(fix(x["w"])) for x in c]
        if not a.accent:
            lines.append(f"Dialogue: 0,{t(start)},{t(end)},Reel,,0,0,0,,{pos}{' '.join(words).strip(' ,;:')}")
            continue
        for k in range(len(c)):
            s = start if k == 0 else c[k]["start"]
            e = end if k == len(c) - 1 else c[k + 1]["start"]
            text = " ".join(f"{{\\c{ass_color(a.accent)}}}{w}{{\\c{ass_color(a.color)}}}" if j == k else w
                            for j, w in enumerate(words))
            lines.append(f"Dialogue: 0,{t(s)},{t(e)},Reel,,0,0,0,,{pos}{text}")
    Path(a.out).write_text("\n".join(head + lines) + "\n", encoding="utf-8")


def cmd_silences(rest):
    p = argparse.ArgumentParser(prog="reel.py silences")
    p.add_argument("video")
    p.add_argument("--db", type=float, default=-38, help="quieter than this is silence (-38 dB)")
    p.add_argument("--min", type=float, default=0.3, help="shortest pause to list, in seconds (0.3)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(rest)
    E.need("ffmpeg", "FFmpeg is required.")
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", a.video, "-vn", "-af",
                        f"highpass=f=100,silencedetect=n={a.db}dB:d={a.min}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out, start = [], None
    for line in r.stderr.splitlines():
        if m := re.search(r"silence_start: ([\d.]+)", line):
            start = float(m[1])
        elif (m := re.search(r"silence_end: ([\d.]+)", line)) and start is not None:
            out.append({"start": round(start, 2), "end": round(float(m[1]), 2), "length": round(float(m[1]) - start, 2)})
            start = None
    if a.json:
        print(json.dumps(out))
    else:
        for s in out:
            print(f"{s['start']:.2f} {s['end']:.2f} {s['length']:.2f}")
        print(f"{len(out)} pauses of {a.min}+ s", file=sys.stderr)
    return 0


def cmd_face(rest):
    if not E.FACE_MODEL.exists():
        sys.exit("error: face model missing. Run: reel.py setup")
    return E.in_venv("face", "face.py", [E.FACE_MODEL, *rest])


def cmd_review(rest):
    import review
    sys.argv = ["review.py", *rest]
    return review.main()


def cmd_voice(rest):
    return E.in_venv("voice", "voice.py", rest)


def cmd_ff(rest):
    d = E.FFMPEG_SKILL_DIR
    if not (d / "SKILL.md").exists():
        sys.exit("error: ffmpeg-skill is not installed. Run: reel.py setup")
    if not rest:
        print(f"ffmpeg-skill {E.FFMPEG_SKILL_VERSION}\n  instructions: {d / 'SKILL.md'}\n  tools: {d / 'scripts'}")
        return 0
    tool = rest[0][:-3] if rest[0].endswith(".py") else rest[0]
    script = d / "scripts" / f"{tool}.py"
    if not script.exists() or tool.startswith("_") and tool != "_contract":
        sys.exit(f"error: ffmpeg-skill has no tool '{tool}'. See: {d / 'SKILL.md'}")
    py = E.venv_python("core") if E.venv_python("core").exists() else Path(sys.executable)  # needs Python 3.10+
    return subprocess.run([str(py), str(script), *rest[1:]]).returncode


COMMANDS = {"setup": cmd_setup, "doctor": cmd_doctor, "new": cmd_new, "transcribe": cmd_transcribe,
            "align": cmd_align, "captions": cmd_captions, "silences": cmd_silences, "face": cmd_face,
            "review": cmd_review, "voice": cmd_voice, "ff": cmd_ff}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help") or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 0 if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help") else 2
    return COMMANDS[sys.argv[1]](sys.argv[2:]) or 0


if __name__ == "__main__":
    sys.exit(main())
