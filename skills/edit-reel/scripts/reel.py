#!/usr/bin/env python3
"""edit-reel: one entry point for every tool. Standard library only; runs with Python 3.9+ on macOS and Windows.

  reel.py setup [--module core|voice|graphics|all] [--language en,es] [--yes]   install what is missing (asks before system programs)
  reel.py doctor                                                     what is installed
  reel.py new <slug> [--dir reels]                                   project folder: raw/ refs/ out/ plan.md
  reel.py transcribe <video> <out-prefix> [--language es] [--names "Claude, Ana"]
                                                                     .txt, .srt by phrase, .words.json (time of every word)
  reel.py align <video> <phrases.srt> <out.words.json> [--language es] re-time words after fixing the .srt
  reel.py fix <video> <out-prefix> --replace Club=Claude [--language es]  fix misheard words everywhere and re-time
  reel.py words <pieces.json> -o cut.words.json [--check heard.json] words of a cut made of pieces, from the takes
  reel.py captions <words.json> <out.ass> [--words 2] [--y 1150] [--y-at 20-60=1380]  captions that follow the voice
  reel.py silences <video> [--db -38] [--min 0.3]                    where the pauses are (start end length)
  reel.py face <video> [--texts captions.srt --band 1150-1250] [--json face.json]
                                                                     where the face is; does any text cover it?
  reel.py sfx <video> -o <out> --at "1.2 whoosh" [--at ...]        sound effects at exact times (--starter DIR: basic set)
  reel.py level <video> -o <out>                                     final mix to -14 LUFS, peaks safe, no distortion
  reel.py review <video> [--platform reels|tiktok|shorts] [--sheet]  final technical check (exit 0 = passes)
  reel.py voice <video> <out.wav>                                    clean voice (module 'voice')
  reel.py ff <tool> [args...]                                        run an ffmpeg-skill tool (cut, silence, caption, loudness, export, check, look...)
  reel.py ff                                                         where ffmpeg-skill's own SKILL.md is
  reel.py hf <args...>                                               pinned HyperFrames CLI (module 'graphics'): init, render, lint...
  reel.py cutout <video> -o person.webm                              the person alone, transparent (text behind the head)
  reel.py overlaps <composition> [--face face.json]                  graphics that overlap each other or cover the face
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

# Windows consoles default to a legacy code page that cannot print "→", "≤" or accents: always write UTF-8.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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


def cmd_fix(rest):
    p = argparse.ArgumentParser(prog="reel.py fix", description=(
        "Fix misheard words in a transcript and re-time it: replaces whole words in <prefix>.srt and <prefix>.txt "
        "(case-insensitive) and re-aligns <prefix>.words.json on the audio. Example: "
        "reel.py fix raw/take.mp4 out/take --replace Club=Claude --replace 'Cloud=Claude' --language es"))
    p.add_argument("media")
    p.add_argument("prefix", help="what transcribe wrote: <prefix>.srt, .txt, .words.json")
    p.add_argument("--replace", action="append", required=True, metavar="WRONG=RIGHT")
    p.add_argument("--language", default="en")
    a = p.parse_args(rest)
    pairs = []
    for r in a.replace:
        if "=" not in r:
            p.error(f"--replace needs WRONG=RIGHT, got {r!r}")
        wrong, right = (x.strip() for x in r.split("=", 1))
        pairs.append((re.compile(rf"(?<!\w){re.escape(wrong)}(?!\w)", re.I), right, wrong))
    total = 0
    for ext in (".srt", ".txt"):
        f = Path(a.prefix + ext)
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for rx, right, wrong in pairs:
            text, n = rx.subn(right, text)
            if ext == ".srt":
                total += n
                print(f"  {wrong} → {right}: {n}")
        f.write_text(text, encoding="utf-8")
    if not total:
        print("nothing to replace in the .srt")
        return 0
    return E.in_venv("core", "speech.py", ["align", a.media, a.prefix + ".srt", a.prefix + ".words.json",
                                           "--language", a.language])


def _seconds(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def _key(w):
    k = re.sub(r"[^\w]", "", w.lower())
    return k


def cmd_words(rest):
    p = argparse.ArgumentParser(prog="reel.py words", description=(
        "Words for a cut built from pieces: each piece's words come from its take's own (checked) .words.json, "
        "shifted to where the piece starts in the cut, using each rendered piece's real length. Safer than "
        "re-transcribing the cut, which can drop words or mishear numbers. With --check, lists where a transcript "
        "of the cut disagrees, so the person can listen there."))
    p.add_argument("pieces", help='JSON list: [{"words": "take.words.json", "from": 12.3, "to": 15.8, '
                                  '"file": "piece01.mp4"} ...] in cut order ("length": s instead of "file" is ok)')
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--check", help="a .words.json from transcribing the cut, to compare")
    a = p.parse_args(rest)
    pieces = json.loads(Path(a.pieces).read_text(encoding="utf-8"))
    base = Path(a.pieces).parent
    out, t = [], 0.0
    for pc in pieces:
        src = json.loads((base / pc["words"]).read_text(encoding="utf-8"))
        f, z = float(pc["from"]), float(pc["to"])
        for w in src:
            if w["start"] >= f - 0.02 and w["end"] <= z + 0.05:
                out.append({"w": w["w"], "start": round(w["start"] - f + t, 2), "end": round(w["end"] - f + t, 2)})
        t += float(pc["length"]) if "length" in pc else _seconds(base / pc["file"])
    Path(a.output).write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(out)} words from {len(pieces)} pieces ({t:.2f} s) → {a.output}")
    if a.check:
        import difflib
        heard = json.loads(Path(a.check).read_text(encoding="utf-8"))
        A, B = [_key(w["w"]) for w in out], [_key(w["w"]) for w in heard]
        diffs = [op for op in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes() if op[0] != "equal"]
        for op, i1, i2, j1, j2 in diffs:
            when = out[i1]["start"] if i1 < len(out) else (out[-1]["end"] if out else 0)
            print(f"  {when:7.2f} s  takes: {' '.join(w['w'] for w in out[i1:i2]) or '—'}"
                  f"   |   cut: {' '.join(w['w'] for w in heard[j1:j2]) or '—'}")
        print(f"{len(diffs)} difference(s): listen there" if diffs else "the cut's transcript agrees with the takes")
    return 0


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
    g.add_argument("--y-at", action="append", default=[], metavar="START-END=Y",
                   help="a different height for a stretch, e.g. 23.5-85=1350 (screens: keep the text being read free)")
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
    stretches = []
    for spec in a.y_at:
        span, y = spec.split("=")
        s0, s1 = (float(x) for x in span.split("-"))
        stretches.append((s0, s1, int(y)))
    lines = []
    for c, start, end in timed:
        y = next((yy for s0, s1, yy in stretches if s0 <= start < s1), a.y)
        pos = f"{{\\an8\\pos({a.width // 2},{y})}}"
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
    return E.in_venv("face", "face.py", [E.FACE_MODEL, *rest], quiet=r"^(I\d{4} |W\d{4} |INFO: )")


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


def cmd_hf(rest):
    """The pinned HyperFrames CLI (module graphics). Runs in the current folder, like `npx hyperframes`."""
    if not (E.GRAPHICS / "node_modules" / "hyperframes").exists():
        sys.exit("error: the 'graphics' module is not installed. Run: reel.py setup --module graphics")
    return subprocess.run([*E.hyperframes_cmd(), *rest]).returncode


def cmd_cutout(rest):
    """Cut the person out of a video (transparent WebM/MOV/PNG) with HyperFrames' local model (module graphics)."""
    if not (E.GRAPHICS / "node_modules" / "hyperframes").exists():
        sys.exit("error: the 'graphics' module is not installed. Run: reel.py setup --module graphics")
    p = argparse.ArgumentParser(prog="reel.py cutout", description=(
        "Cut the person out of a clip: a transparent layer of just them (and optionally the background with a "
        "person-shaped hole). Use it to put text or graphics BEHIND the head: cut video, then the text layer, then "
        "this cutout on top. Cut out the final cut itself so every frame lines up. The model (~170 MB) downloads "
        "the first time; on a Mac it runs on the Apple chip."))
    p.add_argument("video")
    p.add_argument("-o", "--output", required=True, help=".webm (default), .mov (ProRes 4444) or .png for an image")
    p.add_argument("--background", help="also write the background with a hole where the person is (.webm/.mov)")
    p.add_argument("--quality", choices=["fast", "balanced", "best"], default="balanced")
    a = p.parse_args(rest)
    cmd = [*E.hyperframes_cmd(), "remove-background", str(Path(a.video).resolve()), "-o",
           str(Path(a.output).resolve()), "--quality", a.quality]
    if a.background:
        cmd += ["-b", str(Path(a.background).resolve())]
    r = subprocess.run(cmd, cwd=E.GRAPHICS, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"error: cutout failed:\n{(r.stderr or r.stdout)[-1500:]}")
    print(f"cutout → {a.output}" + (f"  background → {a.background}" if a.background else ""))
    return 0


def cmd_overlaps(rest):
    if not (E.GRAPHICS / "node_modules" / "hyperframes").exists():
        sys.exit("error: the 'graphics' module is not installed. Run: reel.py setup --module graphics")
    if not rest or rest[0] in ("-h", "--help"):
        print("usage: reel.py overlaps <composition dir|index.html> [--step 0.1] [--face face.json]\n"
              "Lists elements that overlap on screen, and with --face (from `reel.py face <cut> --json`) the ones\n"
              "that cover the face. Mark what to check with data-check=\"name\"; otherwise every visible text and image.")
        return 0
    chrome = subprocess.run([*E.hyperframes_cmd(), "browser", "path"], capture_output=True, text=True,
                            cwd=E.GRAPHICS).stdout.strip().splitlines()[-1:]
    if not chrome or not Path(chrome[0]).exists():
        sys.exit("error: HyperFrames' Chrome is missing. Run: reel.py setup --module graphics")
    return subprocess.run([E.which("node") or "node", str(E.SCRIPTS / "overlaps.mjs"), str(E.GRAPHICS), chrome[0],
                           *rest]).returncode


def _ff(*args):
    """Run one ffmpeg-skill tool quietly; stop with its message if it fails."""
    d = E.FFMPEG_SKILL_DIR
    py = E.venv_python("core") if E.venv_python("core").exists() else Path(sys.executable)
    r = subprocess.run([str(py), str(d / "scripts" / f"{args[0]}.py"), *map(str, args[1:]), "--overwrite"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"error: ffmpeg-skill {args[0]} failed:\n{(r.stderr or r.stdout)[-1500:]}")


def _loudness(path):
    """(integrated LUFS, true peak dBTP) of the whole mix."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af",
                        "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    tail = r.stderr.rsplit("Summary:", 1)[-1]
    i = re.search(r"\bI:\s*([-\d.]+)\s+LUFS", tail)
    tp = re.search(r"\bPeak:\s*([-\d.]+)\s+dBFS", tail)
    if not i or not tp:
        sys.exit(f"error: could not measure the loudness of {path}")
    return float(i[1]), float(tp[1])


def cmd_level(rest):
    p = argparse.ArgumentParser(prog="reel.py level", description=(
        "Bring the final mix to -14 LUFS without distortion. Measures it; if its peaks would not let it reach the "
        "target (a peaky voice), a gentle compressor and a limiter shave them just enough; then a linear two-pass "
        "loudness pass with headroom for the AAC encode; then measures the result. Exit 1 if it is still off."))
    p.add_argument("video")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--target", type=float, default=-14.0, help="integrated loudness, LUFS (-14)")
    p.add_argument("--tp", type=float, default=-1.5, help="true-peak ceiling before AAC, dBTP (-1.5)")
    a = p.parse_args(rest)
    src, out = Path(a.video), Path(a.output)
    i, tp = _loudness(src)
    print(f"before: {i:.1f} LUFS, peak {tp:.1f} dBTP")
    room = a.tp - a.target  # how far above the average the peaks may sit
    temps = []
    for n in range(1, 4):  # a limiter also lowers the average a little: measure again and repeat if needed
        if tp - i <= room:
            break
        ceiling = max(-24.0, round(i + room - 1.0, 1))
        shaved = out.with_name(f"{out.stem}.shaved{n}{out.suffix}")
        print(f"pass {n}: peaks {tp - i:.1f} dB above the average (max {room:.1f}) → compressor + limiter at {ceiling} dBFS")
        _ff("audio", src, "--compress", "--limit", "--limit-ceiling", ceiling, "-o", shaved)
        temps.append(shaved)
        src = shaved
        i, tp = _loudness(src)
    _ff("loudness", src, "-I", a.target, "--tp", a.tp, "-o", out)
    for t in temps:
        t.unlink(missing_ok=True)
    i2, tp2 = _loudness(out)
    good = abs(i2 - a.target) <= 1 and tp2 <= -1
    print(f"after:  {i2:.1f} LUFS, peak {tp2:.1f} dBTP → {out}" + ("" if good else "  (still off: check the mix)"))
    return 0 if good else 1


def cmd_sfx(rest):
    import sfx
    p = argparse.ArgumentParser(prog="reel.py sfx", description=(
        "Sound effects. --starter DIR makes a basic set (whoosh, pop, click, ding, riser, impact) from scratch, free "
        "to use. Otherwise places effects at exact times under the voice: --at '1.2 whoosh' (repeat), or --cues "
        "file with one 'time sound [dB]' per line. Sounds are looked up by name in --dir, ./sounds and the set "
        "made at setup. Run `reel.py level` after: effects change the mix loudness."))
    p.add_argument("video", nargs="?")
    p.add_argument("-o", "--output")
    p.add_argument("--at", action="append", default=[], help="'time sound [dB]', e.g. '3.2 whoosh -4'")
    p.add_argument("--cues", help="text file, one 'time sound [dB]' per line (# comments)")
    p.add_argument("--dir", action="append", default=[], help="folder with your own sounds (repeatable)")
    p.add_argument("--level", type=float, default=-10.0, help="effects level vs. their -3 dBFS peak (-10 dB)")
    p.add_argument("--starter", metavar="DIR", help="make the starter set in DIR and stop")
    p.add_argument("--list", action="store_true", help="list the sounds that can be called by name, with descriptions")
    p.add_argument("--describe", nargs=2, metavar=("NAME", "TEXT"),
                   help="write NAME's line in sounds.txt (first --dir, else ./sounds): 'what it is — when to use it'")
    a = p.parse_args(rest)
    E.need("ffmpeg", "FFmpeg is required.")
    folders = [Path(x) for x in a.dir] + [Path("sounds"), E.SOUNDS]
    if a.starter:
        names = sfx.make_starter(a.starter)
        print(f"starter set in {a.starter}: {', '.join(names)}")
        return 0
    if a.describe:
        name, text = a.describe
        target = Path(a.dir[0]) if a.dir else Path("sounds")
        sfx.describe(target, name, text)
        print(f"{target / sfx.CATALOG}: {name}: {text}")
        return 0
    if a.list:
        rows, missing = sfx.listing(folders)
        last = None
        for d, name, desc in rows:
            if d != last:
                print(f"{d}:")
                last = d
            print(f"  {name:18} {desc or '(no description yet)'}")
        if not rows:
            print("no sounds found. Make the starter set: reel.py sfx --starter sounds")
        if missing:
            print(f"\n{len(missing)} sound(s) without a description. Ask the person what each one sounds like and when "
                  "they want it, then: reel.py sfx --describe NAME 'what it is — when to use it' --dir <folder>")
        return 0
    lines = list(a.at)
    if a.cues:
        lines += [l.split("#")[0].strip() for l in Path(a.cues).read_text(encoding="utf-8").splitlines()]
    cues = [sfx.parse_cue(l) for l in lines if l]
    if not (a.video and a.output and cues):
        p.error("give a video, -o OUTPUT and at least one --at or --cues")
    sfx.place(a.video, a.output, cues, folders, a.level)
    print(f"{len(cues)} effects → {a.output}  (now run: reel.py level {a.output} -o <final>)")
    return 0


COMMANDS = {"setup": cmd_setup, "doctor": cmd_doctor, "new": cmd_new, "transcribe": cmd_transcribe,
            "align": cmd_align, "fix": cmd_fix, "words": cmd_words, "captions": cmd_captions, "silences": cmd_silences, "face": cmd_face,
            "review": cmd_review, "voice": cmd_voice, "ff": cmd_ff,
            "hf": cmd_hf, "overlaps": cmd_overlaps, "cutout": cmd_cutout, "level": cmd_level, "sfx": cmd_sfx}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help") or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 0 if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help") else 2
    return COMMANDS[sys.argv[1]](sys.argv[2:]) or 0


if __name__ == "__main__":
    sys.exit(main())
