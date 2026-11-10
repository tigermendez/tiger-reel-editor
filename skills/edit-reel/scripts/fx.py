"""Named effects for reels, each one asked for in plain words (catalogue: references/effects.md). Standard library +
FFmpeg (+ ffmpeg-skill for freeze and speed). Called by `reel.py fx <effect> ...`.

  zoom    <video> -o out --at 3.2 [--dur 0.8] [--amount 1.25] [--face face.json]   punch in on a key word
  shake   <video> -o out --at 5.0 [--dur 0.5] [--amount 18]                       camera shake on the punchline
  freeze  <video> -o out --at 4.0 [--hold 1.2] [--sound scratch]                  freeze frame + record scratch
  speed   <video> -o out --at 2.0 --dur 1.5 --factor 0.5                           slow motion (0.5) / fast (2)
  split   <before> <after> -o out [--labels "ANTES,DESPUÉS"] [--dur 4]            before / after, top and bottom
  focus   <video> -o out --at 3 --box x,y,w,h [--dur 2.5]                         smooth zoom into part of a screen
  pushin  <video> -o out --at 0 [--dur 4] [--amount 1.08]                         slow push-in over a sentence
  flash   <video> -o out --at 12.0                                                white flash at a topic change
  reveal  <video> -o out --at 1.5 [--mode bw|blur]                                B&W / blurred until the reveal
  film    <video> -o out [--grain 8] [--vignette 5]                               soft grain + vignette
  progress <video> -o out [--color F8C300]                                        progress bar over the reel
  bubble  <screen> <face> -o out [--corner bottom-right]                          your face in a round bubble
  stack   <top> <bottom> -o out                                                    screen on top, you below
  backdrop <video> <picture|video> -o out                                          you cut out over a background
  emoji   <video> -o out --at 2 --emoji 💸 [--x --y --size]                        an emoji that pops on a word
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


def encode(src_args, filt, out, audio="copy", extra=()):
    ffmpeg(*src_args, "-filter_complex", filt, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", audio, *extra, out)


def ease(t0, t1):
    """0→1 between t0 and t1 with a smooth (cosine) ease, as an ffmpeg expression of t."""
    return f"(0.5-0.5*cos(PI*min(max((t-{t0})/{t1 - t0}\\,0)\\,1)))"


def focus(a):
    """Smooth zoom into a box of the picture (a button, a line of text) and back out: the screen-tutorial zoom."""
    w, h = size(a.video)
    x, y, bw, bh = (float(v) for v in a.box.split(","))
    z = min(w / bw, h / bh, a.max)  # zoom that makes the box fill the frame, capped
    t0, t1, t2, t3 = a.at, a.at + a.ease, a.at + a.dur - a.ease, a.at + a.dur
    k = f"({ease(t0, t1)}-{ease(t2, t3)})"  # 0 → 1 → 0
    zz = f"(1+({z}-1)*{k})"
    cx, cy = x + bw / 2, y + bh / 2
    # Scale the whole frame by zz, then crop a w x h window that moves from the centre to the box centre.
    filt = (f"[0:v]scale=w='trunc({w}*{zz}/2)*2':h='trunc({h}*{zz}/2)*2':eval=frame,"
            f"crop={w}:{h}:x='min(max(({w / 2}+({cx}-{w / 2})*{k})*{zz}-{w / 2}\\,0)\\,iw-{w})':"
            f"y='min(max(({h / 2}+({cy}-{h / 2})*{k})*{zz}-{h / 2}\\,0)\\,ih-{h})'[v]")
    encode(["-i", a.video], filt, a.output)
    print(f"focus {z:.2f}x on {a.box} at {t0:.2f}–{t3:.2f} s → {a.output}")


def pushin(a):
    """A slow, continuous push-in (100 % → amount) over a stretch: life on a static shot without a visible edit."""
    w, h = size(a.video)
    t0, t1 = a.at, a.at + a.dur
    zz = f"(1+({a.amount}-1)*min(max((t-{t0})/{a.dur}\\,0)\\,1))"
    filt = (f"[0:v]scale=w='trunc({w}*{zz}/2)*2':h='trunc({h}*{zz}/2)*2':eval=frame,"
            f"crop={w}:{h}:x='(iw-{w})/2':y='(ih-{h})*0.4'[v]")
    encode(["-i", a.video], filt, a.output)
    print(f"push-in to {a.amount}x over {t0:.2f}–{t1:.2f} s → {a.output}")


def flash(a):
    """A quick white flash at a topic change (the rest of the reel keeps hard cuts)."""
    filt = (f"[0:v]eq=brightness='if(between(t\\,{a.at - 0.08}\\,{a.at + 0.14})\\,"
            f"0.9*(1-abs(t-{a.at})/0.14)\\,0)':eval=frame[v]")
    encode(["-i", a.video], filt, a.output)
    print(f"flash at {a.at:.2f} s → {a.output}")


def reveal(a):
    """Black and white (or blurred) until --at, then the colour (or focus) comes in over --dur."""
    if a.mode == "bw":
        filt = f"[0:v]hue=s='min(max((t-{a.at})/{a.dur}\\,0)\\,1)'[v]"
    else:
        filt = (f"[0:v]split[s][b];[b]gblur=sigma=25[bl];"
                f"[s][bl]overlay=0:0:enable='lt(t\\,{a.at})'[v]")
    encode(["-i", a.video], filt, a.output)
    print(f"reveal ({a.mode}) at {a.at:.2f} s → {a.output}")


def film(a):
    """Soft film grain and a vignette (darker edges): a cinematic look, best for aesthetic reels."""
    filt = f"[0:v]noise=alls={a.grain}:allf=t,vignette=angle=PI/{a.vignette}[v]"
    encode(["-i", a.video], filt, a.output)
    print(f"film look (grain {a.grain}, vignette PI/{a.vignette}) → {a.output}")


def progress(a):
    """A thin bar that fills from left to right over the whole reel, kept above the app's bottom bar."""
    w, h = size(a.video)
    dur = seconds(a.video)
    y = int(h * a.y)
    col = a.color.lstrip("#")
    filt = (f"color=c=0x{col}:s={w}x{a.thick}:r=30[bar];"
            f"[0:v][bar]overlay=x='-{w}+{w}*t/{dur}':y={y}:shortest=1[v]")
    encode(["-i", a.video], filt, a.output)
    print(f"progress bar at {y}px ({dur:.1f} s) → {a.output}")


def bubble(a):
    """Your face in a round bubble over a screen recording (or picture), in a corner."""
    w, h = size(a.screen)
    d = int(w * a.size) // 2 * 2
    pos = {"bottom-right": (w - d - 40, int(h * 0.62)), "bottom-left": (40, int(h * 0.62)),
           "top-right": (w - d - 40, 260), "top-left": (40, 260)}[a.corner]
    side = f"min(iw\\,ih)*{a.tight}"  # a square around the face, not the whole frame
    filt = (f"[1:v]crop='{side}':'{side}':'(iw-{side})/2':'(ih-{side})*{a.face_y}',"
            f"scale={d}:{d},format=yuva420p,geq=lum='p(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':"
            f"a='if(lte(hypot(X-{d / 2}\\,Y-{d / 2})\\,{d / 2 - 2})\\,255\\,0)'[f];"
            f"[0:v][f]overlay={pos[0]}:{pos[1]}:shortest=1[v]")
    ffmpeg("-i", a.screen, "-i", a.face, "-filter_complex", filt, "-map", "[v]", "-map", "1:a?", "-c:v", "libx264",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", a.output)
    print(f"face bubble ({d}px, {a.corner}) → {a.output}")


def stack(a):
    """Screen on top, you below (each half of the 1080x1920 frame), with your sound."""
    filt = ("[0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,setsar=1[t];"
            "[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,setsar=1[b];[t][b]vstack=2[v]")
    ffmpeg("-i", a.top, "-i", a.bottom, "-filter_complex", filt, "-map", "[v]", "-map", f"{a.audio_from}:a?",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", a.output)
    print(f"stacked (top: {Path(a.top).name}, bottom: {Path(a.bottom).name}) → {a.output}")


def backdrop(a):
    """Green screen without a green screen: you, cut out, in front of a picture or a screen recording."""
    out = Path(a.output)
    person = out.with_suffix(".person.webm")
    hf = E.hyperframes_cmd()
    if not (E.GRAPHICS / "node_modules" / "hyperframes").exists():
        sys.exit("error: needs the 'graphics' module (cutout). Run: reel.py setup --module graphics")
    r = subprocess.run([*hf, "remove-background", str(Path(a.video).resolve()), "-o", str(person.resolve())],
                       cwd=E.GRAPHICS, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"error: cutout failed: {(r.stderr or r.stdout)[-800:]}")
    w, h = size(a.video)
    dur = seconds(a.video)
    still = Path(a.background).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    bg_in = (["-loop", "1", "-t", f"{dur:.3f}"] if still else ["-stream_loop", "-1", "-t", f"{dur:.3f}"]) + \
        ["-i", str(a.background)]
    filt = (f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30[bg];"
            f"[2:v]format=yuva420p[p];[bg][p]overlay=0:0:shortest=1[v]")
    ffmpeg("-i", a.video, *bg_in, "-c:v", "libvpx-vp9", "-i", str(person), "-filter_complex", filt, "-map", "[v]",
           "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", f"{dur:.3f}",
           a.output)
    person.unlink(missing_ok=True)
    print(f"you in front of {Path(a.background).name} → {a.output}")


def emoji(a):
    """An emoji that pops (small bounce) on a key word, from Google's Noto Emoji (3D or flat), cached locally."""
    import urllib.request
    code = "_".join(f"{ord(c):x}" for c in a.emoji if ord(c) != 0xFE0F)
    cache = E.HOME / "emoji"
    cache.mkdir(parents=True, exist_ok=True)
    png = cache / f"{a.style}_emoji_u{code}.png"
    if not png.exists():
        for style in dict.fromkeys([a.style, "2D"]):  # 3D first when asked, flat 2D as the fallback
            url = f"https://raw.githubusercontent.com/googlefonts/noto-emoji/main/{style}/png/512/emoji_u{code}.png"
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    png.write_bytes(r.read())
                break
            except Exception:
                continue
        else:
            sys.exit(f"error: could not get the emoji {a.emoji} (no internet, or not in Noto Emoji)")
    t0, t1 = a.at, a.at + a.dur
    # Pop: 0 → 115 % → 100 % in 0.25 s, gone at t1.
    s = (f"if(lt(t-{t0}\\,0.15)\\,1.15*(t-{t0})/0.15\\,if(lt(t-{t0}\\,0.25)\\,1.15-0.15*(t-{t0}-0.15)/0.1"
         f"\\,1))")
    px = a.size
    filt = (f"[1:v]format=rgba,scale=w='max(2\\,trunc({px}*{s}/2)*2)':h=-2:eval=frame[e];"
            f"[0:v][e]overlay=x='{a.x}-overlay_w/2':y='{a.y}-overlay_h/2':enable='between(t\\,{t0}\\,{t1})'"
            f":eof_action=pass[v]")
    encode(["-i", a.video, "-loop", "1", "-i", str(png)], filt, a.output, extra=("-shortest",))
    print(f"emoji {a.emoji} at {t0:.2f}–{t1:.2f} s → {a.output}")


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
    q = base("focus", "smooth zoom into a box of a screen recording and back")
    q.add_argument("--dur", type=float, default=2.5)
    q.add_argument("--box", required=True, help="x,y,w,h of what to show, in the video's pixels")
    q.add_argument("--ease", type=float, default=0.45)
    q.add_argument("--max", type=float, default=2.5, help="maximum zoom (2.5)")
    q = base("pushin", "slow continuous push-in over a stretch")
    q.add_argument("--dur", type=float, default=4.0)
    q.add_argument("--amount", type=float, default=1.08)
    base("flash", "white flash at a topic change")
    q = base("reveal", "black and white (or blurred) until a moment, then colour")
    q.add_argument("--dur", type=float, default=0.4)
    q.add_argument("--mode", choices=["bw", "blur"], default="bw")
    q = sub.add_parser("film", help="soft film grain + vignette")
    q.add_argument("video")
    q.add_argument("-o", "--output", required=True)
    q.add_argument("--grain", type=int, default=8)
    q.add_argument("--vignette", type=int, default=5, help="PI/N: smaller N = darker edges (5)")
    q = sub.add_parser("progress", help="a bar that fills over the whole reel")
    q.add_argument("video")
    q.add_argument("-o", "--output", required=True)
    q.add_argument("--color", default="F8C300")
    q.add_argument("--thick", type=int, default=10)
    q.add_argument("--y", type=float, default=0.78, help="height as a fraction of the frame (0.78, above the app UI)")
    q = sub.add_parser("bubble", help="your face in a round bubble over a screen recording")
    q.add_argument("screen")
    q.add_argument("face")
    q.add_argument("-o", "--output", required=True)
    q.add_argument("--corner", choices=["bottom-right", "bottom-left", "top-right", "top-left"], default="bottom-right")
    q.add_argument("--size", type=float, default=0.34, help="bubble width as a fraction of the frame (0.34)")
    q.add_argument("--face-y", type=float, default=0.22, help="where the face sits in the camera clip, 0 top – 1 bottom")
    q.add_argument("--tight", type=float, default=0.6, help="how close to the face: 0.4 close – 1 whole width (0.6)")
    q = sub.add_parser("stack", help="screen on top, you below")
    q.add_argument("top")
    q.add_argument("bottom")
    q.add_argument("-o", "--output", required=True)
    q.add_argument("--audio-from", type=int, default=1, help="0 = top, 1 = bottom (1)")
    q = sub.add_parser("backdrop", help="green screen without a green screen: you in front of a picture or video")
    q.add_argument("video")
    q.add_argument("background")
    q.add_argument("-o", "--output", required=True)
    q = base("emoji", "an emoji that pops on a key word")
    q.add_argument("--emoji", required=True)
    q.add_argument("--dur", type=float, default=1.2)
    q.add_argument("--x", type=int, default=820)
    q.add_argument("--y", type=int, default=700)
    q.add_argument("--size", type=int, default=180)
    q.add_argument("--style", choices=["3D", "2D"], default="3D", help="3D (default) or flat 2D emoji")
    a = p.parse_args(argv)
    for f in [getattr(a, k, None) for k in ("video", "before", "after", "screen", "face", "top", "bottom",
                                            "background")]:
        if f and not Path(f).is_file():
            sys.exit(f"error: file not found: {f}")
    {"zoom": zoom, "shake": shake, "freeze": freeze, "speed": speed, "split": split, "focus": focus,
     "pushin": pushin, "flash": flash, "reveal": reveal, "film": film, "progress": progress, "bubble": bubble,
     "stack": stack, "backdrop": backdrop, "emoji": emoji}[a.effect](a)
    return 0
