# Reels made of pieces

For reels that mix the camera with a voice recorded apart, screenshots and screen recordings. Write one
`out/build.py` with a list of pieces — what is heard (take + its words) and what is seen — so any change is one line.

## Each piece, exactly as long as what is heard
- **What is heard:** find the words in the take's `.words.json` (first word's start − 0.08 s, last word's end
  + 0.18 s) and `ff cut <take> --start --end --accurate`. Camera pieces keep their own sound.
- **Camera:** `ff fit --aspect 9:16 --fit crop`; to punch in, render wider (`--width 1620` for 1.5x) and
  `ff crop` a 1080x1920 window around the face (`reel.py face --json` gives where it is).
- **A screenshot:** `ff insert img.png --duration <piece length> --width 1080 --height 1920 [--zoom in]`. Make
  the image even-sized first (`ffmpeg -i in.png -vf scale=trunc(iw/2)*2:trunc(ih/2)*2 even.png`): insert fails on
  odd sizes. Skip the zoom when the number being said sits at an edge — a centre zoom would cut it off.
- **A screen recording:** `ff cut` the stretch, `ff crop` the box that is being read (at least 1.25x once
  enlarged; small text is unreadable on a phone), `ff fit --aspect 9:16 --fit blur --width 1080 --fps 30`.
- **Voice on the picture:** `ff audio <picture> --replace <voice.wav>`.
- **Even the loudness of every piece:** `ff loudness <piece> -I -16 --tp -1.5`, then join:
  `ff join p01.mp4 p02.mp4 ... --transition none --width 1080 --fps 30`.

## Words and captions for the joined cut
Write `pieces.json` — one `{"words": "<take>.words.json", "from": a, "to": z, "file": "p01.mp4"}` per piece, in
order — and run `reel.py words pieces.json -o out/cut.words.json --check <transcript of the cut>.words.json`.
The words come from the takes (already checked and fixed), shifted by each rendered piece's real length; the check
lists the places where a fresh transcript of the cut disagrees: listen there before captioning.
