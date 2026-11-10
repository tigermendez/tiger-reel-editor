#!/usr/bin/env python3
"""End-to-end test of the graphics module: compose → overlap check → render a transparent layer → lay it over a clip
→ review. Needs `reel.py setup --module graphics` first. Standard library only.

  python tests/e2e_graphics.py [--keep DIR]
"""
import json
import os
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

PAGE = """<!doctype html>
<html><head><meta charset="UTF-8" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; }} html, body {{ width: 1080px; height: 1920px; background: transparent; overflow: hidden; }}
  .t {{ position: absolute; left: 90px; width: 900px; height: 160px; background: rgba(0,0,0,.7); color: #fc3;
        font: 800 80px Arial, sans-serif; display: flex; align-items: center; justify-content: center; }}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="4" data-width="1080" data-height="1920">
  <div class="clip t" id="a" data-check="title" data-start="0" data-duration="4" data-track-index="0" style="top:300px">Hello</div>
  <div class="clip t" id="b" data-check="tag" data-start="1" data-duration="2" data-track-index="1" style="top:{second}px">World</div>
</div>
<script>
  const tl = gsap.timeline({{ paused: true }});
  tl.from("#b", {{ opacity: 0, y: 20, duration: 0.2 }}, 1);
  tl.to({{}}, {{ duration: 4 }}, 0);
  window.__timelines["main"] = tl;
</script></body></html>
"""


def sh(*cmd, ok=(0,)):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], env=E.env(), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    sys.stdout.write(r.stdout[-2000:])
    if r.returncode not in ok:
        sys.stdout.write(r.stderr[-3000:])
        raise SystemExit(f"FAILED (exit {r.returncode})")
    return r


def check(cond, msg):
    print(("  ok  " if cond else "  XX  ") + msg, flush=True)
    if not cond:
        raise SystemExit(f"FAILED: {msg}")


def main():
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    d = Path(keep or tempfile.mkdtemp(prefix="edit-reel-gfx-"))
    d.mkdir(parents=True, exist_ok=True)
    reel = (sys.executable, REEL)
    for name, second, expect in (("bad", 380, 1), ("good", 700, 0)):
        g = d / name
        g.mkdir(exist_ok=True)
        (g / "index.html").write_text(PAGE.format(second=second), encoding="utf-8")
        r = sh(*reel, "overlaps", g, ok=(0, 1))
        check(r.returncode == expect, f"overlaps on the '{name}' layout exits {expect}")
    check("tag × title" in sh(*reel, "overlaps", d / "bad", ok=(1,)).stdout, "names what overlaps and when")
    # A face where 'good' puts its second box: the face check must catch it.
    face = {"w": 1080, "h": 1920, "step": 0.2,
            "samples": [{"t": round(i * 0.2, 2), "faces": [{"box": [300, 650, 780, 1200], "mouth": [540, 1000],
                                                             "score": 0.95}]} for i in range(20)]}
    (d / "face.json").write_text(json.dumps(face), encoding="utf-8")
    r = sh(*reel, "overlaps", d / "good", "--face", d / "face.json", ok=(1,))
    check("FACE" in r.stdout, "a graphic over the face is reported")

    sh(*reel, "hf", "render", d / "good", "--format", "webm", "-o", d / "overlay.webm", "--quiet")
    alpha = sh("ffprobe", "-v", "error", "-show_entries", "stream_tags=alpha_mode", "-of", "csv=p=0",
               d / "overlay.webm").stdout.strip()
    check(alpha == "1", "the layer is transparent (VP9 alpha)")
    sh("ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x2a3b4c:s=1080x1920:r=30:d=4",
       "-f", "lavfi", "-i", "sine=f=220:d=4", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
       d / "clip.mp4")
    sh(*reel, "ff", "overlay", d / "clip.mp4", "--video", d / "overlay.webm", "--position", "center", "--scale", "1080",
       "--margin", "0", "-o", d / "composed.mp4", "--overwrite")
    # The background stays visible (alpha honoured) and the title box is drawn at y 300–460.
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", "2", "-i", str(d / "composed.mp4"), "-frames:v",
                          "1", "-vf", "format=gray,scale=1:1920", "-f", "rawvideo", "-"], env=E.env(),
                         capture_output=True, check=True).stdout
    check(abs(raw[100] - raw[1800]) < 8 and raw[1800] > 30, f"background visible outside the graphics ({raw[1800]})")
    check(raw[380] != raw[100], "title drawn where it was placed")
    sh(*reel, "ff", "export", d / "composed.mp4", "--preset", "reels", "-o", d / "final.mp4",
       "--overwrite")
    rep = json.loads(sh(*reel, "review", d / "final.mp4", "--json", ok=(0, 1)).stdout)
    for c in rep["checks"]:
        if c["name"] != "Loudness of the mix":  # a sine tone, not a voice: loudness is checked in e2e.py
            check(c["pass"], f"review: {c['name']} = {c['actual']}")
    # Cutout runs and gives a transparent layer (no person in a synthetic clip: we only check the pipeline).
    sh(*reel, "ff", "cut", d / "clip.mp4", "--start", "0", "--end", "1", "-o", d / "short.mp4", "--overwrite")
    sh(*reel, "cutout", d / "short.mp4", "-o", d / "person.webm", "--quality", "fast")
    alpha = sh("ffprobe", "-v", "error", "-show_entries", "stream_tags=alpha_mode", "-of", "csv=p=0",
               d / "person.webm").stdout.strip()
    check(alpha == "1", "cutout writes a transparent layer")
    print(f"\nGRAPHICS END TO END OK  ({d})")
    if not keep:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
