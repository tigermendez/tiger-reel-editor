"""Where the face and the mouth are over time (MediaPipe), and whether any text covers them. Runs in the 'face' env.

  face.py <model.tflite> <video> [--step 0.2] [--json face.json]
  face.py <model.tflite> <video> --texts captions.ass|captions.srt|texts.json [--band 1150-1250]

Footage wider than 1080 px is measured at 1080 px wide, so the pixels match a 1080x1920 export.
Prints the stretches with a face: forehead to chin, the mouth, and from which height captions fit below the chin.
--texts checks every text against the face: an .ass from `reel.py captions` (its real position), an .srt
(uses --band as its vertical box) or a JSON list of
{"start", "end", "text"?, "box"?: [x0, y0, x1, y1]}. Exit code 1 if any text covers the face or the mouth.

The detector (BlazeFace short range) looks at 128 px squares, so in a full vertical frame a face is tiny and often
missed; it scans three overlapping squares instead. It keeps detections above 0.8 (a hand holding a mic scores
0.5–0.78). A face in profile, covered or far away may not be found: this is a warning system, not a guarantee.
"""
import argparse
import json
import re
import subprocess
import sys

import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
# -I ignores PYTHONUTF8, and Windows consoles cannot print "→" or accents in their legacy code page.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

CHIN = 0.15   # BlazeFace's box ends at the lower lip: stretch it 15 % to reach the chin
MARGIN = 40   # air between the chin and a caption


def size(video):
    """Displayed size: ffmpeg applies a phone's rotation metadata when decoding, ffprobe's width/height do not."""
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height:stream_side_data=rotation", "-of", "json", video],
                                  capture_output=True, text=True, check=True).stdout)["streams"][0]
    w, h = s["width"], s["height"]
    rot = next((int(x.get("rotation", 0)) for x in s.get("side_data_list", []) if "rotation" in x), 0)
    return (h, w) if abs(rot) % 180 == 90 else (w, h)


def iou(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def detect(model, video, step, threshold):
    w, h = size(video)
    if w > 1080:  # work at reel width: faster on 4K phone footage, and pixels match a 1080-wide export
        w, h = 1080, round(h * 1080 / w / 2) * 2
    det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=mpt.BaseOptions(model_asset_path=model), min_detection_confidence=threshold))
    side = min(w, h)
    n = max(1, round((max(w, h) - side) / (side * 0.4)) + 1)
    offs = [round(i * (max(w, h) - side) / max(1, n - 1)) for i in range(n)]
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", video, "-vf", f"fps=1/{step},scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    samples, i = [], 0
    while len(b := p.stdout.read(w * h * 3)) == w * h * 3:
        f = np.frombuffer(b, np.uint8).reshape(h, w, 3)
        faces = []
        for o in offs:
            x, y = (0, o) if h >= w else (o, 0)
            crop = np.ascontiguousarray(f[y:y + side, x:x + side])
            for d in det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=crop)).detections:
                bb, s = d.bounding_box, d.categories[0].score
                c = {"box": [x + bb.origin_x, y + bb.origin_y, x + bb.origin_x + bb.width,
                             y + bb.origin_y + round(bb.height * (1 + CHIN))],
                     "mouth": [round(x + d.keypoints[3].x * side), round(y + d.keypoints[3].y * side)],
                     "score": round(s, 2)}
                same = next((k for k in faces if iou(k["box"], c["box"]) > 0.3), None)
                if same is None:
                    faces.append(c)
                elif s > same["score"]:
                    faces[faces.index(same)] = c
        samples.append({"t": round(i * step, 2), "faces": faces})
        i += 1
    p.wait()
    return {"video": video, "w": w, "h": h, "step": step, "samples": samples}


def stretches(d):
    out = []
    for m in d["samples"]:
        if not m["faces"]:
            continue
        c = max(m["faces"], key=lambda k: k["score"])
        last = out[-1] if out else None
        if last and m["t"] - last["to"] <= d["step"] * 1.5:
            last["to"] = m["t"]
            last["boxes"].append(c["box"])
            last["mouths"].append(c["mouth"][1])
        else:
            out.append({"from": m["t"], "to": m["t"], "boxes": [c["box"]], "mouths": [c["mouth"][1]]})
    return [s for s in out if len(s["boxes"]) > 1]  # a lone sample is usually a false positive


def ass_time(x):
    h, m, sec = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def load_texts(path, band, width):
    if path.lower().endswith(".ass"):  # from `reel.py captions ... out.ass`: real position and size
        raw = open(path, encoding="utf-8-sig").read()
        size = int(m[1]) if (m := re.search(r"^Style: [^,]*,[^,]*,(\d+)", raw, re.M)) else band[1] - band[0]
        texts = []
        for line in raw.splitlines():
            if not line.startswith("Dialogue:"):
                continue
            f = line.split(",", 9)
            y = int(m[1]) if (m := re.search(r"\\pos\(\d+,(\d+)\)", f[9])) else band[0]
            texts.append({"start": ass_time(f[1]), "end": ass_time(f[2]), "text": re.sub(r"\{[^}]*\}", "", f[9]),
                          "box": [0, y, width, y + round(size * 1.25)]})
        return texts
    if path.lower().endswith(".srt"):
        cues = []
        for block in re.split(r"\n\s*\n", open(path, encoding="utf-8-sig").read().strip()):
            lines = block.strip().splitlines()
            k = next((j for j, l in enumerate(lines) if "-->" in l), None)
            if k is None:
                continue
            a, z = [sum(float(x) * m for x, m in zip(re.split("[:,.]", t.strip()), (3600, 60, 1, 0.001)))
                    for t in lines[k].split("-->")]
            cues.append({"start": a, "end": z, "text": " ".join(lines[k + 1:])})
        texts = cues
    else:
        texts = json.load(open(path, encoding="utf-8"))
    for x in texts:
        x.setdefault("box", [0, band[0], width, band[1]])
    return texts


def check_texts(d, texts):
    hits = []
    for x in texts:
        a, b, box = x.get("start", x.get("from")), x.get("end", x.get("to")), x["box"]
        for m in d["samples"]:
            if not (a - d["step"] / 2 <= m["t"] <= b + d["step"] / 2):
                continue
            for c in m["faces"]:
                k = c["box"]
                if min(box[2], k[2]) - max(box[0], k[0]) > 4 and min(box[3], k[3]) - max(box[1], k[1]) > 4:
                    what = "the mouth" if box[1] <= c["mouth"][1] + 30 and box[3] >= c["mouth"][1] - 30 else "the face"
                    hits.append((m["t"], x.get("text", ""), what, k))
                    break
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("video")
    ap.add_argument("--step", type=float, default=0.2, help="seconds between samples (0.2)")
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--json", help="save every sample here")
    ap.add_argument("--texts", help=".srt or JSON with the on-screen texts and their times")
    ap.add_argument("--band", default="1150-1250", help="vertical box (px) for texts without a box (1150-1250)")
    a = ap.parse_args()
    d = detect(a.model, a.video, a.step, a.threshold)
    if a.json:
        json.dump(d, open(a.json, "w", encoding="utf-8"), ensure_ascii=False)
    found = sum(1 for m in d["samples"] if m["faces"])
    print(f"{a.video}: {d['w']}x{d['h']}, face in {found} of {len(d['samples'])} samples (every {a.step} s)")
    for s in stretches(d):
        top = min(c[1] for c in s["boxes"])
        chin = max(c[3] for c in s["boxes"])
        mouth = round(sum(s["mouths"]) / len(s["mouths"]))
        print(f"  {s['from']:6.1f}–{s['to']:6.1f} s  face {top}–{chin} px  mouth ~{mouth} px"
              f"  → captions fit from {chin + MARGIN} px down"
              f" (reel.py captions ... --y {chin + MARGIN})")
    if a.texts:
        y0, y1 = map(int, a.band.split("-"))
        hits = check_texts(d, load_texts(a.texts, (y0, y1), d["w"]))
        print("Texts: none covers the face." if not hits else f"Texts: {len(hits)} cover the face:")
        for t, txt, what, k in hits:
            print(f"  x {t:6.1f} s  '{txt}' covers {what} (face {k[1]}–{k[3]} px)")
        sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
