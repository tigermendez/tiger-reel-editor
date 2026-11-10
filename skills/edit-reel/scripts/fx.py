"""Named effects for reels, each one asked for in plain words (catalogue: references/effects.md). Standard library +
FFmpeg (+ ffmpeg-skill for freeze and speed). Called by `reel.py fx <effect> ...`.

  zoom    <video> -o out --at 3.2 [--dur 0.8] [--amount 1.25] [--face face.json]   punch in on a key word
  shake   <video> -o out --at 5.0 [--dur 0.5] [--amount 18]                       camera shake on the punchline
  freeze  <video> -o out --at 4.0 [--hold 1.2] [--sound scratch]                  freeze frame + record scratch
  speed   <video> -o out --at 2.0 --dur 1.5 --factor 0.5                           slow motion (0.5) / fast (2)
  split   <before> <after> -o out [--labels "ANTES,DESPUÉS"] [--dur 4]            before / after, top and bottom
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import _env as E


def ffmpeg(*args):
    ff = E.need("ffmpeg", "FFmpeg is required.")
    r = subprocess.run([ff, "-nostdin", "-hide_banner", "-v", "error", "-y", *map(str, args)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"error: ffmpeg failed: {r.stderr.strip()[-800:]}")


def seconds(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return float(r.stdout.strip())


def size(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, encoding="utf-8")
    w, h = map(int, r.stdout.strip().split(",")[:2])
    return w, h


def face_centre(face_json, at, w, h):
    """Where the face is around `at` (from `reel.py face --json`), scaled to this video; else the frame centre."""
    if not face_json:
        return w / 2, h * 0.4
    d = json.loads(Path(face_json).read_text(encoding="utf-8"))
    near = [f for m in d["samples"] if abs(m["t"] - at) <= 1.0 for f in m["faces"]]
    if not near:
        return w / 2, h * 0.4
    b = max(near, key=lambda f: f["score"])["box"]
    k = w / d["w"]
    return (b[0] + b[2]) / 2 * k, (b[1] + b[3]) / 2 * k


def zoom(a):
    """Punch in instantly at --at, hold for --dur, back out: the classic jump zoom on a key word."""
    w, h = size(a.video)
    cx, cy = face_centre(a.face, a.at, w, h)
    cw, ch = int(w / a.amount) // 2 * 2, int(h / a.amount) // 2 * 2
    x = int(min(max(cx - cw / 2, 0), w - cw))
    y = int(min(max(cy - ch / 2, 0), h - ch))
    end = a.at + a.dur
    ffmpeg("-i", a.video, "-filter_complex",
           f"[0:v]split[base][z];[z]crop={cw}:{ch}:{x}:{y},scale={w}:{h}[zoomed];"
           f"[base][zoomed]overlay=0:0:enable='between(t,{a.at},{end})'[v]",
           "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy",
           a.output)
    print(f"zoom {a.amount}x at {a.at:.2f}–{end:.2f} s → {a.output}")


def shake(a):
    """A short camera shake (slightly zoomed so the edges never show) at --at for --dur."""
    w, h = size(a.video)
    m = int(a.amount)
    end = a.at + a.dur
    ffmpeg("-i", a.video, "-filter_complex",
           f"[0:v]split[base][s];[s]scale={w + 2 * m}:{h + 2 * m},"
           f"crop={w}:{h}:x='{m}+{m}*sin(t*71)*cos(t*13)':y='{m}+{m}*cos(t*67)*sin(t*17)'[shaken];"
           f"[base][shaken]overlay=0:0:enable='between(t,{a.at},{end})'[v]",
           "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy",
           a.output)
    print(f"shake ±{m}px at {a.at:.2f}–{end:.2f} s → {a.output}")


def run_ff(*args):
    d = E.FFMPEG_SKILL_DIR
    py = E.venv_python("core") if E.venv_python("core").exists() else Path(sys.executable)
    r = subprocess.run([str(py), str(d / "scripts" / f"{args[0]}.py"), *map(str, args[1:]), "--overwrite"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"error: ffmpeg-skill {args[0]} failed:\n{(r.stderr or r.stdout)[-1200:]}")


def freeze(a):
    """Freeze the frame at --at for --hold seconds (inserted, so the video gets longer) with a record scratch."""
    import sfx
    tmp = Path(a.output).with_suffix(".freeze.mp4")
    run_ff("freeze", a.video, "--at", a.at, "--hold", a.hold, "-o", tmp)
    if a.sound and a.sound != "none":
        folders = [Path("sounds"), E.SOUNDS]
        if not sfx.find_sound(a.sound, folders):
            sfx.make_starter(E.SOUNDS)
        sfx.place(tmp, a.output, [(a.at, a.sound, -4.0)], folders, -6.0)
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(a.output)
    print(f"freeze {a.hold}s at {a.at:.2f} s" + (f" + {a.sound}" if a.sound != "none" else "") + f" → {a.output}")


def speed(a):
    """Slow motion (factor < 1) or fast forward (> 1) for one stretch; the rest stays at normal speed."""
    total = seconds(a.video)
    end = min(a.at + a.dur, total)
    segs = []
    if a.at > 0:
        segs += ["--segment", f"0-{a.at:.3f}:1.0"]
    segs += ["--segment", f"{a.at:.3f}-{end:.3f}:{a.factor}"]
    if end < total:
        segs += ["--segment", f"{end:.3f}-{total:.3f}:1.0"]
    run_ff("speedramp", a.video, *segs, "-o", a.output)
    print(f"speed x{a.factor} at {a.at:.2f}–{end:.2f} s → {a.output}")


def split(a):
    """Before on top, after below, each filling half of the 1080x1920 frame, with a label on each."""
    labels = (a.labels or "ANTES,DESPUÉS").split(",")
    inputs, chains = [], []
    for k, src in enumerate((a.before, a.after)):
        still = Path(src).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        inputs += (["-loop", "1", "-t", str(a.dur)] if still else []) + ["-i", str(src)]
        chains.append(f"[{k}:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,setsar=1,fps=30,"
                      f"format=yuv420p[p{k}]")
    dur = a.dur if all(Path(s).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") for s in (a.before, a.after)) \
        else min(a.dur, *(seconds(s) for s in (a.before, a.after)
                          if Path(s).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")))
    ass = Path(a.output).with_suffix(".labels.ass")
    rows = [f"Dialogue: 0,0:00:00.00,9:00:00.00,L,,0,0,0,,{{\\an8\\pos(540,{y})}}{t.strip()}"
            for t, y in zip(labels, (270, 1000))]  # 270: below the app's top bar
    ass.write_text("\n".join([
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: L,{a.font},64,&H00FFFFFF&,&H00FFFFFF&,&H00000000&,&HA0000000&,-1,0,0,0,100,100,2,0,3,14,0,8,0,0,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text", *rows])
        + "\n", encoding="utf-8")
    esc = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    ffmpeg(*inputs, "-filter_complex", ";".join(chains) + f";[p0][p1]vstack=2,ass=filename='{esc}'[v]",
           "-map", "[v]", "-t", f"{dur:.3f}", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-an", a.output)
    print(f"before/after ({dur:.1f} s, labels {', '.join(labels)}) → {a.output}  (silent: add the voice with "
          "`ff audio --replace` or join it into the cut)")


def main(argv):
    p = argparse.ArgumentParser(prog="reel.py fx", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="effect", required=True)

    def base(name, help_):
        q = sub.add_parser(name, help=help_)
        q.add_argument("video")
        q.add_argument("-o", "--output", required=True)
        q.add_argument("--at", type=float, required=True, help="second where it happens (from .words.json)")
        return q

    q = base("zoom", "punch in on a key word")
    q.add_argument("--dur", type=float, default=0.8)
    q.add_argument("--amount", type=float, default=1.25)
    q.add_argument("--face", help="face.json from `reel.py face --json`, to zoom on the face")
    q = base("shake", "camera shake on the punchline")
    q.add_argument("--dur", type=float, default=0.5)
    q.add_argument("--amount", type=float, default=18, help="pixels (18)")
    q = base("freeze", "freeze frame + record scratch")
    q.add_argument("--hold", type=float, default=1.2)
    q.add_argument("--sound", default="scratch", help="sound name ('none' for silence)")
    q = base("speed", "slow motion or fast forward for one stretch")
    q.add_argument("--dur", type=float, required=True)
    q.add_argument("--factor", type=float, required=True, help="0.5 = half speed, 2 = double")
    q = sub.add_parser("split", help="before / after")
    q.add_argument("before")
    q.add_argument("after")
    q.add_argument("-o", "--output", required=True)
    q.add_argument("--labels", default="ANTES,DESPUÉS")
    q.add_argument("--dur", type=float, default=4.0, help="length when both are images (4)")
    q.add_argument("--font", default="Arial")
    a = p.parse_args(argv)
    for f in [getattr(a, "video", None), getattr(a, "before", None), getattr(a, "after", None)]:
        if f and not Path(f).is_file():
            sys.exit(f"error: file not found: {f}")
    {"zoom": zoom, "shake": shake, "freeze": freeze, "speed": speed, "split": split}[a.effect](a)
    return 0
