#!/usr/bin/env python3
"""Final technical review of an exported reel. Never modifies the file. Needs only FFmpeg; standard library only.

  review.py <video> [--platform reels|tiktok|shorts] [--sheet] [--json]

Checks: 1080x1920, 30 fps average, H.264 yuv420p, AAC, decodes end to end, length within the platform limit,
loudness of the FINAL MIX at -14 LUFS (±1) and true peak at or below -1 dBTP. --sheet writes <video>.sheet.jpg,
one frame every 2 s, to look at before delivering. Exit 0 = passes, 1 = something to fix, 2 = could not review.

Passing is not approval: captions in sync and spelled right, the face free, cuts that sound natural and the story
itself are still the person's call. This only proves the file will not be rejected or sound quieter than the rest.
"""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

# Windows consoles default to a legacy code page that cannot print "→", "≤" or accents: always write UTF-8.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

MAX_SECONDS = {"reels": 180, "tiktok": 600, "shorts": 180}  # Instagram allows 3-minute Reels since 2025


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise ValueError(f"{cmd[0]} failed: {r.stderr[-1500:].strip()}")
    return r


def inspect(video, platform="reels", target=-14.0, tolerance=1.0, max_peak=-1.0):
    for tool in ("ffprobe", "ffmpeg"):
        if not shutil.which(tool):
            raise ValueError(f"{tool} is not installed.")
    if not video.is_file():
        raise ValueError(f"No such file: {video}")
    meta = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]).stdout)
    checks = []

    def check(name, passed, actual, expected):
        checks.append({"name": name, "pass": bool(passed), "actual": actual, "expected": expected})

    streams = meta.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    check("Video track", v is not None, bool(v), True)
    check("Audio track", a is not None, bool(a), True)
    duration = float(meta.get("format", {}).get("duration", 0) or 0)
    check("Length", 0 < duration <= MAX_SECONDS[platform], round(duration, 2), f"≤ {MAX_SECONDS[platform]} s ({platform})")
    if v:
        size = [v.get("width"), v.get("height")]
        check("Resolution", size == [1080, 1920], size, [1080, 1920])
        try:
            fps = float(Fraction(v.get("avg_frame_rate", "0/1")))
        except (ValueError, ZeroDivisionError):
            fps = 0
        check("Average FPS", abs(fps - 30) < 0.01, round(fps, 3), 30)
        check("Video codec", v.get("codec_name") == "h264", v.get("codec_name"), "h264")
        check("Pixel format", v.get("pix_fmt") == "yuv420p", v.get("pix_fmt"), "yuv420p")
    if a:
        check("Audio codec", a.get("codec_name") == "aac", a.get("codec_name"), "aac")
    # Decode everything: catches broken files and measures the final mix, not the isolated voice.
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-xerror", "-i", str(video)]
    if v:
        cmd += ["-map", f"0:{v['index']}"]
    if a:
        cmd += ["-map", f"0:{a['index']}", "-af", "ebur128=peak=true"]
    r = run(cmd + ["-f", "null", "-"])
    check("Decodes end to end", True, "no errors", "no errors")
    if a:
        summary = r.stderr.rsplit("Summary:", 1)[-1]
        lufs = re.search(r"\bI:\s*([-+\d.inf]+)\s+LUFS", summary)
        peak = re.search(r"\bPeak:\s*([-+\d.inf]+)\s+dBFS", summary)
        if not lufs or not peak:
            raise ValueError("FFmpeg did not return the loudness summary.")
        lufs, peak = float(lufs[1]), float(peak[1])
        check("Loudness of the mix", math.isfinite(lufs) and abs(lufs - target) <= tolerance,
              lufs if math.isfinite(lufs) else str(lufs), f"{target} ± {tolerance} LUFS")
        check("True peak", peak <= max_peak, peak if math.isfinite(peak) else str(peak), f"≤ {max_peak} dBTP")
    return {
        "file": str(video),
        "passes": all(c["pass"] for c in checks),
        "checks": checks,
        "still_yours_to_check": [
            "Face and mouth free (reel.py face --texts), nothing important in the bottom 20 % or the right edge.",
            "Captions in sync, spelled right, names correct.",
            "Cuts sound natural; voice, music and effects balanced.",
            "The story: does the first second say what the reel is about?",
        ],
    }


def sheet(video):
    out = video.with_suffix(".sheet.jpg")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(video), "-vf", "fps=1/2,scale=200:-1,tile=8x5",
         "-frames:v", "1", "-update", "1", str(out)])
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video", type=Path)
    p.add_argument("--platform", choices=sorted(MAX_SECONDS), default="reels")
    p.add_argument("--sheet", action="store_true", help="also write a contact sheet to look at")
    p.add_argument("--json", action="store_true")
    p.add_argument("--target-lufs", type=float, default=-14)
    p.add_argument("--tolerance", type=float, default=1)
    p.add_argument("--max-peak", type=float, default=-1)
    a = p.parse_args()
    try:
        rep = inspect(a.video.resolve(), a.platform, a.target_lufs, a.tolerance, a.max_peak)
        if a.sheet:
            rep["sheet"] = str(sheet(a.video.resolve()))
    except (ValueError, OSError) as e:
        print(json.dumps({"error": str(e)}) if a.json else f"ERROR: {e}", file=sys.stdout if a.json else sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"Review: {rep['file']}")
        for c in rep["checks"]:
            print(f"{'PASS' if c['pass'] else 'FIX '}  {c['name']}: {c['actual']} (expected {c['expected']})")
        if rep.get("sheet"):
            print(f"Sheet: {rep['sheet']}")
        print("\nStill yours to check:")
        for item in rep["still_yours_to_check"]:
            print(f"- {item}")
        print("\n" + ("Technical checks pass." if rep["passes"] else "Some technical checks need fixing."))
    return 0 if rep["passes"] else 1


if __name__ == "__main__":
    sys.exit(main())
