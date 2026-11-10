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
  reel.py text <video> "a *fixed* sentence" -o out [--font --color --accent --y]   fixed text block, not captions
  reel.py fx zoom|shake|freeze|speed|split ...                      named effects (catalogue: references/effects.md)
  reel.py silences <video> [--db -38] [--min 0.3]                    where the pauses are (start end length)
  reel.py face <video> [--texts captions.srt --band 1150-1250] [--json face.json]
                                                                     where the face is; does any text cover it?
  reel.py study <example video> -o study/<name>                      measure an example's style (hook, cuts, rhythm, text, sound)
  reel.py font "Bebas Neue" | --list                                fonts as files in fonts/ (Google Fonts), same on every OS
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
    p.add_argument("--module", default="core", help="core (default), voice, graphics, or all; several with commas")
    p.add_argument("--language", default="en", help="languages to prepare word timings for, e.g. en,es")
    p.add_argument("--model", default=None, help="speech model (default large-v3-turbo; 'small' for a quick test)")
    p.add_argument("--yes", action="store_true", help="allow installing FFmpeg/uv with Homebrew or winget")
    p.add_argument("--ffmpeg-skill-from", default=None, help="local .tgz or folder of ffmpeg-skill (offline/backup)")
    a = p.parse_args(rest)
    mods = list(_setup.MODULES) if a.module == "all" else [m.strip() for m in a.module.split(",")]
    for m in mods:
        if m not in _setup.MODULES:
            sys.exit(f"error: unknown module '{m}' (core, voice, graphics, all)")
    if "core" not in mods and not E.venv_python("core").exists():
        print(f"The core module (~{_setup.MODULES['core']['size_gb']} GB) is required first and will be installed too.")
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
    if rest and not rest[0].startswith("-"):
        _need_media(rest[0], audio=True)
    return E.in_venv("core", "speech.py", ["transcribe", *rest])


def cmd_align(rest):
    if "--language" not in rest and len(rest) >= 2:
        srt = rest[1]
        rest = [*rest, "--language", _language(srt[:-4] if srt.endswith(".srt") else srt, None)]
    if rest:
        _need_media(rest[0], audio=True)
    return E.in_venv("core", "speech.py", ["align", *rest])


def cmd_fix(rest):
    p = argparse.ArgumentParser(prog="reel.py fix", description=(
        "Fix misheard words in a transcript and re-time it: replaces whole words in the text of <prefix>.srt and "
        "<prefix>.txt (case-insensitive; cue numbers and times are left alone) and re-aligns <prefix>.words.json on "
        "the audio. Example: reel.py fix raw/take.mp4 out/take --replace Club=Claude --replace Cloud=Claude"))
    p.add_argument("media")
    p.add_argument("prefix", help="what transcribe wrote: <prefix>.srt, .txt, .words.json")
    p.add_argument("--replace", action="append", required=True, metavar="WRONG=RIGHT")
    p.add_argument("--language", default=None, help="default: the language transcribe detected")
    a = p.parse_args(rest)
    srt = Path(a.prefix + ".srt")
    if not srt.is_file():
        sys.exit(f"error: {srt} not found (the prefix is what you gave transcribe as its output)")
    _need_media(a.media, audio=True)
    language = _language(a.prefix, a.language)  # before touching anything
    pairs = []
    for r in a.replace:
        wrong, _, right = r.partition("=")
        wrong, right = wrong.strip(), right.strip()
        if not wrong or "=" not in r:
            p.error(f"--replace needs WRONG=RIGHT with a word on the left, got {r!r}")
        pairs.append((re.compile(rf"(?<!\w){re.escape(wrong)}(?!\w)", re.I), right, wrong))

    def sub_text(line, counts):
        for k, (rx, right, _) in enumerate(pairs):
            line, n = rx.subn(right, line)
            counts[k] += n
        return line

    counts = [0] * len(pairs)
    out = []
    for line in srt.read_text(encoding="utf-8-sig").splitlines():
        timing = "-->" in line or line.strip().isdigit() or not line.strip()
        out.append(line if timing else sub_text(line, counts))
    srt.write_text("\n".join(out) + "\n", encoding="utf-8")
    txt = Path(a.prefix + ".txt")
    if txt.exists():
        txt.write_text(sub_text(txt.read_text(encoding="utf-8"), [0] * len(pairs)), encoding="utf-8")
    for (_, right, wrong), n in zip(pairs, counts):
        print(f"  {wrong} → {right}: {n}")
    if not sum(counts):
        print("nothing to replace in the .srt")
        return 0
    return E.in_venv("core", "speech.py", ["align", a.media, str(srt), a.prefix + ".words.json",
                                           "--language", language])


def _has_audio(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0 and r.stdout.strip() != ""


def _need_media(path, audio=False):
    if not Path(path).is_file():
        sys.exit(f"error: file not found: {path}")
    if audio and not _has_audio(path):
        sys.exit(f"error: {path} has no sound track")


def _language(prefix, given):
    """The language to align with: the one given, else the one transcribe detected (saved next to the .srt)."""
    if given:
        return given
    meta = Path(str(prefix) + ".meta.json")
    if meta.exists():
        return json.loads(meta.read_text(encoding="utf-8")).get("language") or "en"
    sys.exit("error: say the language with --language (es, en, pt...): no transcript metadata found next to it")


def _seconds(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return float(r.stdout.strip())
    except ValueError:
        sys.exit(f"error: cannot read the length of {path}")


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
    for k, pc in enumerate(pieces, 1):
        missing = [x for x in ("words", "from", "to") if x not in pc]
        if missing or not ("length" in pc or "file" in pc):
            sys.exit(f"error: piece {k} needs words, from, to and file (or length); missing: "
                     f"{', '.join(missing) or 'file/length'}")
        if not (base / pc["words"]).is_file() or ("file" in pc and not (base / pc["file"]).is_file()):
            sys.exit(f"error: piece {k}: file not found ({pc.get('file') if 'file' in pc else pc['words']})")
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
    g.add_argument("--font", default="Arial", help="a font file (fonts/Bangers.ttf), a family in ./fonts, or an "
                   "installed family (Arial). Files are the same on every computer: burn with --fonts-dir")
    g.add_argument("--color", default="FFFFFF", help="text colour, hex RRGGBB (FFFFFF)")
    g.add_argument("--accent", default=None, help="colour of the word being said, hex (e.g. FFD400); off by default")
    g.add_argument("--outline", type=float, default=6, help="black outline in px (6; 0 for none)")
    g.add_argument("--shadow", type=float, default=2, help="soft drop shadow in px (2)")
    g.add_argument("--wrap", type=int, default=0, metavar="PX",
                   help="let a cue wrap onto several centred lines within this width (e.g. 900); 0 = one line")
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
    import fonts
    ffile, fam = fonts.find(a.font)
    if ffile:
        a.font = fam
        print(f"font: {fam} from {ffile} — burn with: ff caption <video> --ass {a.out} --fonts-dir {ffile.parent}")
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
    margin = max(40, (a.width - a.wrap) // 2) if a.wrap else 40

    def t(x):
        cs = max(0, round(x * 100))
        return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"

    def esc(s):
        return s.replace("\\", "").replace("{", "(").replace("}", ")")

    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {a.width}", f"PlayResY: {a.height}",
        f"WrapStyle: {0 if a.wrap else 2}", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Reel,{a.font},{a.size},{ass_color(a.color)},{ass_color(a.color)},&H00000000&,&H80000000&,-1,0,0,0,"
        f"100,100,0,0,1,{a.outline},{a.shadow},8,{margin},{margin},0,1", "",
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


def _warped_text(ass, fontsdir, k, out):
    """The text of an .ass as a transparent 1080x1920 PNG, bulged like a fisheye lens around the text block.

    libass draws colour but no transparency, so the text is drawn twice — in colour, and in white as its alpha
    mask — and merged. Then every pixel inside the block's circle is pulled from radius r**k (k > 1 magnifies the
    centre and curves the edges)."""
    ff = E.need("ffmpeg", "FFmpeg is required.")
    work = out.with_suffix(".text")
    work.mkdir(parents=True, exist_ok=True)
    src = Path(ass).read_text(encoding="utf-8")
    mask_lines = []
    for line in src.splitlines():
        if line.startswith("Style:"):
            f = line.split(",")
            f[3] = f[4] = f[5] = "&H00FFFFFF&"
            f[6] = "&H80FFFFFF&"
            line = ",".join(f)
        elif line.startswith("Dialogue:"):
            line = re.sub(r"\\c&H[0-9A-Fa-f]+&", r"\\c&H00FFFFFF&", line)
        mask_lines.append(line)
    mask = work / "mask.ass"
    mask.write_text("\n".join(mask_lines) + "\n", encoding="utf-8")

    def esc(p):  # a path inside an ffmpeg filter argument
        return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")

    def draw(a_file, png, gray=False):
        vf = f"ass=filename='{esc(a_file)}'" + (f":fontsdir='{esc(fontsdir)}'" if fontsdir else "") + \
             (",format=gray" if gray else "")
        subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920", "-vf", vf,
                        "-frames:v", "1", str(png)], check=True)
    draw(ass, work / "colour.png")
    draw(mask, work / "mask.png", gray=True)
    flat = work / "flat.png"
    subprocess.run([ff, "-v", "error", "-y", "-i", str(work / "colour.png"), "-i", str(work / "mask.png"),
                    "-filter_complex", "[0]format=rgb24[c];[1]format=gray[m];[c][m]alphamerge,format=rgba",
                    str(flat)], check=True)
    raw = subprocess.run([ff, "-v", "error", "-i", str(flat), "-vf", "alphaextract", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    W, H = 1080, 1920
    rows = [y for y in range(H) if max(raw[y * W:(y + 1) * W]) > 20]
    if not rows:
        sys.exit("error: the text came out empty (check the font name)")
    cols = [x for x in range(W) if any(raw[y * W + x] > 20 for y in range(rows[0], rows[-1] + 1, 2))]
    cx, cy = (cols[0] + cols[-1]) / 2, (rows[0] + rows[-1]) / 2
    R = max(cols[-1] - cols[0], rows[-1] - rows[0]) / 2 * 1.05
    rr = f"hypot((X-{cx})/{R}\\,(Y-{cy})/{R})"
    # A smooth barrel lens: pixels at distance r come from r*(1 - a*(1 - r^2)). The centre is magnified by
    # 1/(1-a) and the effect fades to nothing at the edge of the block, so lines bend evenly instead of a bubble.
    a_ = k - 1
    scale = f"if(lt({rr}\\,1)\\,1-{a_}*(1-{rr}*{rr})\\,1)"
    sx, sy = f"{cx}+(X-{cx})*{scale}", f"{cy}+(Y-{cy})*{scale}"
    expr = {c: f"{c}({sx}\\,{sy})" for c in ("r", "g", "b", "alpha")}
    script = work / "warp.vf"
    script.write_text(f"format=rgba,geq=r='{expr['r']}':g='{expr['g']}':b='{expr['b']}':a='{expr['alpha']}'",
                      encoding="utf-8")
    png = work / "warped.png"
    subprocess.run([ff, "-v", "error", "-y", "-i", str(flat), "-/vf", str(script), str(png)], check=True)
    return png


def cmd_text(rest):
    p = argparse.ArgumentParser(prog="reel.py text", description=(
        "A fixed block of text on the video (not captions): the same sentence on screen for the whole clip or a "
        "stretch, wrapped on centred lines. Words between *asterisks* take the --accent colour. Burns it with "
        "ffmpeg-skill, using a font file from fonts/ when given, so it looks the same on every computer."))
    p.add_argument("video")
    p.add_argument("text", help='e.g. "Te enseño a poner estas letras *curvas* porque nadie te dice cómo"')
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--font", default="Arial", help="font file, family in ./fonts, or installed family")
    p.add_argument("--size", type=int, default=72)
    p.add_argument("--color", default="FFFFFF")
    p.add_argument("--accent", default=None, help="colour for *marked* words")
    p.add_argument("--y", type=int, default=700, help="top of the block in px on the 1080x1920 frame (700)")
    p.add_argument("--wrap", type=int, default=760, help="line width in px (760)")
    p.add_argument("--outline", type=float, default=0)
    p.add_argument("--shadow", type=float, default=3)
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--end", type=float, default=None, help="default: the end of the video")
    p.add_argument("--typewriter", type=float, default=0.0, metavar="SECONDS",
                   help="type the text letter by letter over this many seconds, then keep it")
    p.add_argument("--fisheye", type=float, default=0.0, metavar="AMOUNT",
                   help="bulge the text like a fisheye lens (the 'curvy letters' effect): 0.15 soft, 0.25 strong")
    a = p.parse_args(rest)
    _need_media(a.video)
    import fonts
    ffile, fam = fonts.find(a.font)
    family = fam if ffile else a.font
    end = a.end if a.end is not None else _seconds(a.video)

    def t(x):
        cs = max(0, round(x * 100))
        return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"

    clean = a.text.replace("\\", "").replace("{", "(").replace("}", ")")
    chars, marked = [], False  # each visible character with whether it is *marked*
    for ch in clean:
        if ch == "*":
            marked = not marked
        else:
            chars.append((ch, marked and bool(a.accent)))

    def render(shown):
        """The text with the first `shown` characters visible and the rest invisible (layout never moves)."""
        out, cur, hidden = [], False, False
        for i, (ch, acc) in enumerate(chars):
            if acc != cur:
                out.append(f"{{\\c{ass_color(a.accent if acc else a.color)}}}")
                cur = acc
            if i == shown and not hidden:
                out.append("{\\alpha&HFF&}")
                hidden = True
            out.append(ch)
        return "".join(out)
    margin = max(40, (1080 - a.wrap) // 2)
    pos = f"{{\\an8\\pos(540,{a.y})}}"
    if a.typewriter > 0 and chars:
        n = len(chars)
        step = a.typewriter / n
        dialogues = [f"Dialogue: 0,{t(a.start + i * step)},{t(a.start + (i + 1) * step)},Text,,0,0,0,,{pos}{render(i + 1)}"
                     for i in range(n - 1)]
        dialogues.append(f"Dialogue: 0,{t(a.start + (n - 1) * step)},{t(end)},Text,,0,0,0,,{pos}{render(n)}")
    else:
        dialogues = [f"Dialogue: 0,{t(a.start)},{t(end)},Text,,0,0,0,,{pos}{render(len(chars))}"]
    ass = Path(a.output).with_suffix(".text.ass")
    ass.write_text("\n".join([
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Text,{family},{a.size},{ass_color(a.color)},{ass_color(a.color)},&H00000000&,&H80000000&,0,0,0,0,"
        f"100,100,0,0,1,{a.outline},{a.shadow},8,{margin},{margin},0,1", "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *dialogues]) + "\n", encoding="utf-8")
    if a.fisheye > 0 and a.typewriter > 0:
        sys.exit("error: --fisheye and --typewriter cannot be combined yet (the bulge is drawn once, still)")
    if a.fisheye > 0:
        png = _warped_text(ass, ffile.parent if ffile else None, 1 + a.fisheye, Path(a.output))
        rc = cmd_ff([str(x) for x in ["overlay", a.video, "--image", png, "--position", "center", "--scale", 1080,
                                      "--margin", 0, "--start", a.start, "--end", end, "-o", a.output, "--overwrite"]])
        if rc == 0:
            print(f"text ({family}, fisheye {a.fisheye}) on {a.start:.1f}–{end:.1f} s → {a.output}")
        return rc
    args = ["caption", a.video, "--ass", ass, "-o", a.output, "--overwrite"]
    if ffile:
        args += ["--fonts-dir", ffile.parent]
    rc = cmd_ff([str(x) for x in args])
    if rc == 0:
        print(f"text ({family}) on {a.start:.1f}–{end:.1f} s → {a.output}")
    return rc


def cmd_fx(rest):
    import fx
    return fx.main(rest)


def cmd_silences(rest):
    p = argparse.ArgumentParser(prog="reel.py silences")
    p.add_argument("video")
    p.add_argument("--db", type=float, default=-38, help="quieter than this is silence (-38 dB)")
    p.add_argument("--min", type=float, default=0.3, help="shortest pause to list, in seconds (0.3)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(rest)
    E.need("ffmpeg", "FFmpeg is required.")
    _need_media(a.video, audio=True)
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", a.video, "-vn", "-af",
                        f"highpass=f=100,silencedetect=n={a.db}dB:d={a.min}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"error: could not read {a.video}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}")
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


def cmd_study(rest):
    p = argparse.ArgumentParser(prog="reel.py study", description=(
        "Measure an example video so its style can be written down as a recipe: the first 3 s frame by frame (the "
        "hook), 40 frames over the whole video, every cut and the shot rhythm, loudness, size, and — with sound and "
        "the core module — the transcript and words per minute. Look at the images; the numbers are in stats.json."))
    p.add_argument("video")
    p.add_argument("-o", "--out", required=True, help="folder for the results")
    p.add_argument("--language", default=None)
    p.add_argument("--scene", type=float, default=0.3, help="cut sensitivity, 0–1 (0.3)")
    a = p.parse_args(rest)
    _need_media(a.video)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dur = _seconds(a.video)
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                       "stream=width,height,avg_frame_rate", "-of", "json", a.video],
                                      capture_output=True, text=True, encoding="utf-8").stdout)["streams"][0]
    run = lambda *c: subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *map(str, c)],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace")
    run("-t", 3, "-i", a.video, "-vf", "fps=4,scale=240:-1,tile=6x2", "-frames:v", 1, out / "hook.jpg")
    run("-i", a.video, "-vf", f"fps=1/{max(dur, 1) / 40:.3f},scale=200:-1,tile=8x5", "-frames:v", 1, out / "sheet.jpg")
    # Every frame's scene score: big jumps are cuts; small isolated spikes are jump cuts and graphics entering.
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", a.video, "-an", "-vf",
                        "select='gte(scene,0)',metadata=print:file=-", "-f", "null", "-"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    times = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stdout)]
    scores = [float(x) for x in re.findall(r"scene_score=([\d.]+)", r.stdout)]
    cuts, changes = [], []
    import statistics
    for i, (t, x) in enumerate(zip(times, scores)):
        if x > a.scene:
            cuts.append(round(t, 2))
        around = scores[max(0, i - 15):i] + scores[i + 1:i + 16]
        if x > 0.03 and x > 4 * max(statistics.median(around) if around else 0, 0.004) and \
                (not changes or t - changes[-1] > 0.2):
            changes.append(round(t, 2))
    (out / "cuts.txt").write_text("# big cuts\n" + "\n".join(map(str, cuts)) + "\n# all visual changes "
                                  "(jump cuts, graphics entering)\n" + "\n".join(map(str, changes)) + "\n",
                                  encoding="utf-8")
    shots = [b - a_ for a_, b in zip([0.0] + cuts, cuts + [dur])]
    stats = {"file": str(a.video), "seconds": round(dur, 2), "size": [probe.get("width"), probe.get("height")],
             "fps": probe.get("avg_frame_rate"), "big_cuts": len(cuts),
             "average_shot_s": round(sum(shots) / len(shots), 2) if shots else None,
             "visual_changes": len(changes),
             "something_new_every_s": round(dur / (len(changes) + 1), 2) if dur else None}
    if _has_audio(a.video):
        i, tp = _loudness(a.video)
        stats.update({"loudness_lufs": i, "true_peak_dbtp": tp})
        if E.venv_python("core").exists():
            args = ["transcribe", a.video, str(out / "transcript")] + (["--language", a.language] if a.language else [])
            E.in_venv("core", "speech.py", args)
            words = json.loads((out / "transcript.words.json").read_text(encoding="utf-8"))
            speech = sum(w["end"] - w["start"] for w in words)
            stats.update({"words": len(words), "words_per_minute": round(len(words) / dur * 60) if dur else None,
                          "first_word_at_s": words[0]["start"] if words else None,
                          "speech_share": round(speech / dur, 2) if dur else None})
    (out / "stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))
    print(f"→ {out}/hook.jpg (first 3 s), sheet.jpg (whole video), cuts.txt, stats.json"
          + (", transcript.*" if (out / "transcript.txt").exists() else ""))
    return 0


def cmd_font(rest):
    import fonts
    p = argparse.ArgumentParser(prog="reel.py font", description=(
        "Fonts as files in the project's fonts/ folder, so captions and graphics look the same on every computer. "
        "'reel.py font Bangers' downloads it from Google Fonts (open licences, with its licence file); "
        "'reel.py font --list' shows what is there and each file's family name (the name to use)."))
    p.add_argument("name", nargs="?", help="Google Fonts family name, e.g. 'Bebas Neue'")
    p.add_argument("--dir", default="fonts")
    p.add_argument("--list", action="store_true")
    a = p.parse_args(rest)
    if a.list or not a.name:
        d = Path(a.dir)
        files = sorted(f for f in d.rglob("*") if f.suffix.lower() in fonts.FONT_SUFFIXES) if d.is_dir() else []
        for f in files:
            print(f"  {fonts.family_name(f):28} {f}")
        if not files:
            print(f"no fonts in {d}/ yet. Put font files there, or: reel.py font 'Family Name'")
        return 0
    got = fonts.download(a.name, a.dir)
    got.sort(key=lambda f: (0 if "regular" in f.name.lower() else 1 if "italic" not in f.name.lower() else 2, f.name))
    fams = sorted({fonts.family_name(f) for f in got})
    print(f"{len(got)} file(s) in {got[0].parent}: family {', '.join(fams)}")
    print(f"captions: --font '{got[0]}'   graphics: @font-face {{ src: url('{got[0].as_posix()}') }}")
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
                            encoding="utf-8", errors="replace", cwd=E.GRAPHICS).stdout.strip().splitlines()[-1:]
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
    _need_media(a.video, audio=True)
    sfx.place(a.video, a.output, cues, folders, a.level)
    print(f"{len(cues)} effects → {a.output}  (now run: reel.py level {a.output} -o <final>)")
    return 0


COMMANDS = {"setup": cmd_setup, "doctor": cmd_doctor, "new": cmd_new, "transcribe": cmd_transcribe,
            "align": cmd_align, "fix": cmd_fix, "words": cmd_words, "captions": cmd_captions, "text": cmd_text, "fx": cmd_fx, "silences": cmd_silences, "face": cmd_face,
            "review": cmd_review, "voice": cmd_voice, "ff": cmd_ff,
            "hf": cmd_hf, "overlaps": cmd_overlaps, "cutout": cmd_cutout, "font": cmd_font, "study": cmd_study, "level": cmd_level, "sfx": cmd_sfx}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help") or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 0 if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help") else 2
    return COMMANDS[sys.argv[1]](sys.argv[2:]) or 0


if __name__ == "__main__":
    sys.exit(main())
